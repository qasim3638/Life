/**
 * WebSpeechWakeWord — free, no-API-key wake-word listener using
 * the browser's built-in Web Speech API (Android uses Google's
 * on-device speech recognizer; Chrome uses cloud).
 *
 * Listens continuously for phrases like "hi yaar" / "hey yaar" / "ok yaar"
 * etc. When matched, dispatches `life:wake` (same event the floating mic
 * already listens for).
 *
 * Robustness:
 *   - Auto-restarts on `onend` (Android recognizer naturally times out)
 *   - Restart on `onerror` (with throttle)
 *   - Pauses while Yaar is speaking (avoid self-triggering on TTS)
 *   - Pauses while floating mic is actively recording
 *   - Respects the existing `life_wake_enabled` setting + `life:wake-settings` event
 */
import { useEffect, useRef, useState } from "react";

const WAKE_PREF_KEY = "life_wake_enabled";

export const getWakeEnabled = () =>
  (localStorage.getItem(WAKE_PREF_KEY) || "off") === "on";
export const setWakeEnabled = (on) =>
  localStorage.setItem(WAKE_PREF_KEY, on ? "on" : "off");

// Phrases we accept as the wake word — be generous because Web Speech
// transcripts vary (yaar/yar/yarr/your/etc).
const WAKE_PATTERNS = [
  /\b(hi|hey|ok|okay)\s+(yaar|yar|yarr|year|your|ya)\b/i,
  /\byaar\b/i, // bare "yaar" with strong intent
];

function looksLikeWake(text) {
  if (!text) return false;
  const t = text.toLowerCase().trim();
  // Bare "yaar" only fires if the phrase is short — avoid catching mid-conversation words
  if (/^(hi|hey|ok|okay)?\s*(yaar|yar|yarr|year)\s*$/.test(t)) return true;
  return WAKE_PATTERNS[0].test(t);
}

export default function WebSpeechWakeWord() {
  const [enabled, setEnabledState] = useState(getWakeEnabled());
  const recognitionRef = useRef(null);
  const shouldRunRef = useRef(false);
  const restartTimerRef = useRef(null);
  const lastRestartRef = useRef(0);
  const pausedRef = useRef(false); // paused while Yaar speaks or recording

  // Detect support
  const SR = typeof window !== "undefined"
    ? (window.SpeechRecognition || window.webkitSpeechRecognition)
    : null;

  // React to the existing wake-settings event (Settings page toggles this)
  useEffect(() => {
    const handler = () => setEnabledState(getWakeEnabled());
    window.addEventListener("life:wake-settings", handler);
    return () => window.removeEventListener("life:wake-settings", handler);
  }, []);

  // Pause while floating mic is recording or Yaar is speaking or voiceprint enrollment is open
  useEffect(() => {
    const onMicStart = () => { pausedRef.current = true; safeStop(); };
    const onMicEnd = () => { pausedRef.current = false; scheduleRestart(50); };
    window.addEventListener("life:mic-recording-start", onMicStart);
    window.addEventListener("life:mic-recording-end", onMicEnd);
    window.addEventListener("life:yaar-speaking-start", onMicStart);
    window.addEventListener("life:yaar-speaking-end", onMicEnd);
    window.addEventListener("life:wake-pause", onMicStart);
    window.addEventListener("life:wake-resume", onMicEnd);
    return () => {
      window.removeEventListener("life:mic-recording-start", onMicStart);
      window.removeEventListener("life:mic-recording-end", onMicEnd);
      window.removeEventListener("life:yaar-speaking-start", onMicStart);
      window.removeEventListener("life:yaar-speaking-end", onMicEnd);
      window.removeEventListener("life:wake-pause", onMicStart);
      window.removeEventListener("life:wake-resume", onMicEnd);
    };
  }, []);

  const safeStop = () => {
    const rec = recognitionRef.current;
    if (rec) {
      try { rec.stop(); } catch {}
    }
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
  };

  const scheduleRestart = (delay = 200) => {
    if (!shouldRunRef.current || pausedRef.current) return;
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
    // Throttle: if we restarted very recently, back off a bit
    const sinceLast = Date.now() - lastRestartRef.current;
    const realDelay = sinceLast < 400 ? 600 : delay;
    restartTimerRef.current = setTimeout(() => {
      restartTimerRef.current = null;
      startRecognition();
    }, realDelay);
  };

  const startRecognition = () => {
    if (!SR || !shouldRunRef.current || pausedRef.current) return;
    // If already running, don't double-start
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch {}
    }
    const r = new SR();
    r.continuous = true;
    r.interimResults = true;
    r.lang = "en-US";
    r.maxAlternatives = 1;

    r.onresult = (evt) => {
      for (let i = evt.resultIndex; i < evt.results.length; i++) {
        const res = evt.results[i];
        const transcript = (res[0]?.transcript || "").trim();
        if (!transcript) continue;
        if (looksLikeWake(transcript)) {
          // Fire wake event — VoiceMicButton (which listens for life:wake) opens mic
          window.dispatchEvent(new CustomEvent("life:wake", { detail: { label: "Hi Yaar (web)" } }));
          // Stop listening; floating mic will restart us via life:mic-recording-end
          pausedRef.current = true;
          safeStop();
          return;
        }
      }
    };

    r.onend = () => {
      // Android auto-stops; just restart unless we were told to pause
      if (shouldRunRef.current && !pausedRef.current) scheduleRestart(150);
    };

    r.onerror = (e) => {
      const err = e?.error || "";
      // "no-speech" / "aborted" are routine; "not-allowed" means permission
      if (err === "not-allowed" || err === "service-not-allowed") {
        shouldRunRef.current = false;
        setEnabledState(false);
        setWakeEnabled(false);
        return;
      }
      if (shouldRunRef.current && !pausedRef.current) scheduleRestart(600);
    };

    try {
      lastRestartRef.current = Date.now();
      r.start();
      recognitionRef.current = r;
    } catch (e) {
      // Already started, etc. — back off and retry
      scheduleRestart(800);
    }
  };

  // Master on/off
  useEffect(() => {
    if (!SR) return;
    if (enabled) {
      shouldRunRef.current = true;
      pausedRef.current = false;
      startRecognition();
    } else {
      shouldRunRef.current = false;
      safeStop();
      recognitionRef.current = null;
    }
    return () => {
      shouldRunRef.current = false;
      safeStop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, SR]);

  // Render nothing — pure background service
  return null;
}
