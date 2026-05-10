import React, { useEffect, useRef, useState, useCallback } from "react";
import { Mic, MicOff, Loader2, X, Sparkles, Check, Volume2, VolumeX } from "lucide-react";
import { api, API, authStore } from "../lib/api";
import { toast } from "sonner";
import useShakeToTalk from "../lib/useShakeToTalk";
import { elevenStore, elevenSpeak } from "../lib/elevenLabsTTS";

/**
 * Floating "Just talk to Yaar" mic button — present app-wide.
 *
 * UX:
 *  - Single tap → toggle mode (tap again to stop & send)
 *  - Long-press (≥350ms) → hold-to-record (release to stop & send)
 *  - States: idle | recording | transcribing | thinking | done
 *  - Auto-hides while user is typing in chat input on /companion
 */

const HOLD_THRESHOLD_MS = 350;
const HIDE_ON_PATHS = []; // could hide on certain paths; empty = always show
const TTS_PREF_KEY = "yaar_voice_replies";  // "on" | "off"

function pickMime() {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];
  for (const c of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c)) {
      return c;
    }
  }
  return "";
}

export default function VoiceMicButton() {
  const [phase, setPhase] = useState("idle"); // idle | recording | transcribing | thinking | done
  const [transcript, setTranscript] = useState("");
  const [resultLines, setResultLines] = useState([]);
  const [errorMsg, setErrorMsg] = useState("");
  const [hidden, setHidden] = useState(false);
  const [unsupported, setUnsupported] = useState(false);
  const [ttsOn, setTtsOn] = useState(() => (localStorage.getItem(TTS_PREF_KEY) || "on") === "on");
  const [speaking, setSpeaking] = useState(false);

  const audioElRef = useRef(null);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const holdTimerRef = useRef(null);
  const isHoldModeRef = useRef(false);
  const recordingRef = useRef(false);
  const startedAtRef = useRef(0);

  // Hide on certain paths if needed
  useEffect(() => {
    const check = () => {
      const path = window.location.pathname;
      setHidden(HIDE_ON_PATHS.some(p => path.startsWith(p)));
    };
    check();
    window.addEventListener("popstate", check);
    return () => window.removeEventListener("popstate", check);
  }, []);

  // Capability check
  useEffect(() => {
    const ok = typeof navigator !== "undefined"
      && navigator.mediaDevices
      && navigator.mediaDevices.getUserMedia
      && typeof MediaRecorder !== "undefined";
    setUnsupported(!ok);
  }, []);

  // Shake-to-talk — listens on devicemotion, dispatches life:wake
  useShakeToTalk();

  // Hi Yaar wake word + shake → auto-start recording
  useEffect(() => {
    const onWake = () => {
      // Only start if we're idle and the mic isn't busy
      if (recordingRef.current) return;
      // Small toast so the user has feedback
      toast.message("Yaar is listening…");
      // defer to next tick so Porcupine can fully release the mic stream
      setTimeout(() => { startRecording(); }, 150);
    };
    window.addEventListener("life:wake", onWake);
    return () => window.removeEventListener("life:wake", onWake);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cleanup = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    mediaRecorderRef.current = null;
    chunksRef.current = [];
    recordingRef.current = false;
  }, []);

  // ---- TTS playback (Yaar speaks back) ----
  const stopSpeaking = useCallback(() => {
    if (audioElRef.current) {
      try { audioElRef.current.pause(); } catch {}
      try { URL.revokeObjectURL(audioElRef.current.src); } catch {}
      audioElRef.current = null;
    }
    setSpeaking(false);
  }, []);

  const speak = useCallback(async (text) => {
    if (!ttsOn) return;
    const t = (text || "").trim();
    if (!t) return;
    stopSpeaking();

    // Path 1: ElevenLabs direct (if user has set their API key in Settings)
    if (elevenStore.hasKey()) {
      try {
        const blob = await elevenSpeak(t.slice(0, 800));
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audioElRef.current = audio;
        audio.onended = () => { stopSpeaking(); };
        audio.onerror = () => { stopSpeaking(); };
        setSpeaking(true);
        try {
          await audio.play();
        } catch (playErr) {
          console.warn("[Yaar TTS] autoplay blocked:", playErr?.message);
          toast.message("Tap the speaker icon to hear Yaar (browser blocked autoplay)");
          stopSpeaking();
        }
        return;
      } catch (e) {
        console.error("[Yaar TTS] ElevenLabs direct failed:", e);
        toast.message(`ElevenLabs error: ${(e?.message || "").slice(0, 80)}`);
        // fall through to OpenAI fallback below
      }
    }

    // Path 2: OpenAI via backend
    try {
      const token = authStore.getToken();
      const res = await fetch(`${API}/voice/speak`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ text: t.slice(0, 800), voice: "coral", provider: "openai" }),
      });
      if (!res.ok) {
        let detail = "";
        try { detail = (await res.text()).slice(0, 100); } catch {}
        toast.message(`Yaar can't speak: ${res.status} ${detail || ""}`.trim());
        console.error("[Yaar TTS] /voice/speak failed:", res.status, detail);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioElRef.current = audio;
      audio.onended = () => { stopSpeaking(); };
      audio.onerror = () => { stopSpeaking(); };
      setSpeaking(true);
      try {
        await audio.play();
      } catch (playErr) {
        console.warn("[Yaar TTS] autoplay blocked:", playErr?.message);
        toast.message("Tap the speaker icon to hear Yaar (browser blocked autoplay)");
        stopSpeaking();
      }
    } catch (e) {
      console.error("[Yaar TTS] speak() error:", e);
      toast.message(`Yaar TTS error: ${(e?.message || "").slice(0, 60)}`);
      stopSpeaking();
    }
  }, [ttsOn, stopSpeaking]);

  const toggleTts = () => {
    const next = !ttsOn;
    setTtsOn(next);
    localStorage.setItem(TTS_PREF_KEY, next ? "on" : "off");
    if (!next) stopSpeaking();
    toast.message(next ? "Yaar will speak back" : "Yaar will stay quiet");
  };

  // ---- Recording lifecycle ----
  const startRecording = useCallback(async () => {
    if (recordingRef.current || phase !== "idle") return;
    setErrorMsg("");
    setTranscript("");
    setResultLines([]);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = pickMime();
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      mediaRecorderRef.current = rec;
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = () => handleStop();
      rec.start();
      recordingRef.current = true;
      startedAtRef.current = Date.now();
      setPhase("recording");
    } catch (e) {
      // Show the actual error name + message so we can diagnose
      const name = e?.name || "Error";
      const msg = (e?.message || "").toString().slice(0, 80);
      console.error("[Yaar mic] getUserMedia failed:", name, msg, e);
      setErrorMsg(`Mic error: ${name} — ${msg}`);
      cleanup();
      setPhase("idle");
    }
  }, [phase, cleanup]);

  const stopRecording = useCallback(() => {
    const rec = mediaRecorderRef.current;
    if (!rec || !recordingRef.current) return;
    try { rec.stop(); } catch {}
  }, []);

  const handleStop = useCallback(async () => {
    const elapsed = Date.now() - startedAtRef.current;
    const blob = new Blob(chunksRef.current, { type: chunksRef.current[0]?.type || "audio/webm" });
    cleanup();

    if (elapsed < 400 || blob.size < 800) {
      setPhase("idle");
      toast.message("Hold a bit longer — too short to transcribe.");
      return;
    }

    setPhase("transcribing");
    try {
      const ext = (blob.type.includes("mp4") ? "mp4" : blob.type.includes("ogg") ? "ogg" : "webm");
      const fd = new FormData();
      fd.append("audio", blob, `voice.${ext}`);
      const { data } = await api.post("/voice/transcribe", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const text = (data?.text || "").trim();
      if (!text) {
        setErrorMsg("Didn't catch that. Try again, a bit louder.");
        setPhase("idle");
        return;
      }
      setTranscript(text);
      setPhase("thinking");

      // Send transcript through companion chat & auto-apply actions
      const chat = await api.post("/companion/chat", { message: text });
      const reply = chat?.data?.reply;
      const actions = reply?.actions || [];
      const applied = [];
      for (const a of actions) {
        if (a.status !== "pending") continue;
        try {
          const r = await api.post(`/companion/messages/${reply.id}/actions/${a.id}/apply`);
          applied.push(r.data?.action?.result || "Done");
        } catch {}
      }

      if (applied.length > 0) {
        setResultLines(applied);
        toast.success(applied.length === 1 ? applied[0] : `${applied.length} changes applied`);
        // Speak back a concise summary
        const spokenSummary = applied.length === 1
          ? `Done. ${applied[0]}`
          : `Done. ${applied.length} changes — ${applied.slice(0, 4).join(". ")}.`;
        speak(spokenSummary);
      } else if (reply?.content) {
        setResultLines([reply.content.slice(0, 240)]);
        speak(reply.content.slice(0, 600));
      } else {
        setResultLines(["Heard you, but nothing to do."]);
        speak("Heard you, but there was nothing to do.");
      }
      setPhase("done");
      // Auto-clear: longer if Yaar is speaking back
      const dismissDelay = (ttsOn && (applied.length > 0 || reply?.content)) ? 12000 : 5000;
      setTimeout(() => {
        setPhase("idle"); setTranscript(""); setResultLines([]);
      }, dismissDelay);
    } catch (e) {
      // Surface the actual backend error so we can diagnose production issues
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail || e?.message;
      let msg = "Couldn't reach Yaar.";
      if (status === 401) msg = "Session expired — please sign in again.";
      else if (status === 500) msg = `Yaar's brain hit an error: ${(detail || '').toString().slice(0, 80)}`;
      else if (status === 502 || status === 503 || status === 504) msg = `Backend is restarting (${status}). Try again in a minute.`;
      else if (!status) msg = `Network error: ${(e?.message || '').toString().slice(0, 60)}`;
      setErrorMsg(msg);
      setPhase("idle");
    }
  }, [cleanup]);

  // ---- Pointer interactions ----
  const onPointerDown = (e) => {
    if (phase !== "idle") return;
    e.preventDefault();
    isHoldModeRef.current = false;
    holdTimerRef.current = setTimeout(() => {
      isHoldModeRef.current = true;
      startRecording();
    }, HOLD_THRESHOLD_MS);
  };

  const onPointerUp = (e) => {
    if (holdTimerRef.current) {
      clearTimeout(holdTimerRef.current);
      holdTimerRef.current = null;
    }
    if (isHoldModeRef.current) {
      // hold mode: release to stop
      e.preventDefault();
      stopRecording();
      isHoldModeRef.current = false;
    } else {
      // tap: toggle
      if (phase === "idle") startRecording();
      else if (phase === "recording") stopRecording();
    }
  };

  const cancel = () => {
    if (recordingRef.current) {
      try { mediaRecorderRef.current?.stop(); } catch {}
      cleanup();
    }
    setPhase("idle"); setTranscript(""); setResultLines([]); setErrorMsg("");
  };

  if (hidden) return null;

  return (
    <>
      {/* Status / result toast (above the button) */}
      {(phase !== "idle" || resultLines.length > 0 || errorMsg) && (
        <div
          className="fixed bottom-24 right-6 z-[90] max-w-sm pointer-events-auto"
          data-testid="voice-status"
        >
          <div className="rounded-2xl bg-white border border-sand shadow-lg px-4 py-3">
            {phase === "recording" && (
              <p className="text-sm text-[#2D312E] flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#B85C50] animate-pulse"/>
                Listening… <span className="text-[#9A9F9D] text-xs ml-1">(release/tap to send)</span>
              </p>
            )}
            {phase === "transcribing" && (
              <p className="text-sm text-[#2D312E] flex items-center gap-2">
                <Loader2 size={14} strokeWidth={1.5} className="animate-spin text-[#A3897C]"/>
                Transcribing…
              </p>
            )}
            {phase === "thinking" && (
              <>
                <p className="text-[10px] uppercase tracking-widest text-[#9A9F9D]">You said</p>
                <p className="text-sm text-[#2D312E] mt-0.5 italic">"{transcript}"</p>
                <p className="text-xs text-[#6B7270] mt-2 flex items-center gap-2">
                  <Sparkles size={12} strokeWidth={1.5} className="text-[#59745D]"/> Yaar is acting on it…
                </p>
              </>
            )}
            {phase === "done" && (
              <>
                {transcript && (
                  <p className="text-xs text-[#9A9F9D] italic mb-1.5">"{transcript}"</p>
                )}
                <div className="space-y-0.5" data-testid="voice-result">
                  {resultLines.map((l, i) => (
                    <p key={i} className="text-sm text-[#59745D] flex items-start gap-1.5 leading-snug">
                      <Check size={14} strokeWidth={2} className="mt-0.5 shrink-0"/>
                      <span>{l}</span>
                    </p>
                  ))}
                </div>
              </>
            )}
            {errorMsg && phase === "idle" && (
              <p className="text-sm text-[#B85C50]">{errorMsg}</p>
            )}
            {(phase === "recording" || phase === "transcribing" || phase === "thinking") && (
              <button
                onClick={cancel}
                className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-white border border-sand shadow-sm flex items-center justify-center text-[#9A9F9D] hover:text-[#B85C50]"
                title="Cancel"
                data-testid="voice-cancel"
              >
                <X size={12} strokeWidth={1.5}/>
              </button>
            )}
          </div>
        </div>
      )}

      {/* The button itself */}
      <button
        type="button"
        onPointerDown={unsupported ? undefined : onPointerDown}
        onPointerUp={unsupported ? undefined : onPointerUp}
        onPointerLeave={() => {
          if (holdTimerRef.current) { clearTimeout(holdTimerRef.current); holdTimerRef.current = null; }
        }}
        onContextMenu={(e) => e.preventDefault()}
        disabled={unsupported || phase === "transcribing" || phase === "thinking"}
        className={`fixed bottom-6 right-6 z-[91] select-none transition-all duration-300 ${
          phase === "recording"
            ? "scale-110"
            : "hover:scale-105 active:scale-95"
        } ${unsupported ? "opacity-50 cursor-not-allowed" : ""}`}
        title={unsupported ? "Mic not supported on this browser" : "Tap or hold to talk to Yaar"}
        data-testid="voice-mic-button"
        aria-label="Talk to Yaar"
      >
        {/* Pulsing ring when recording */}
        {phase === "recording" && (
          <span className="absolute inset-0 rounded-full bg-[#B85C50]/30 animate-ping"/>
        )}
        <span className={`relative flex items-center justify-center w-14 h-14 rounded-full shadow-lg ring-1 ring-black/5 transition-colors ${
          phase === "recording"
            ? "bg-[#B85C50] text-white"
            : phase === "transcribing" || phase === "thinking"
            ? "bg-[#A3897C] text-white"
            : phase === "done"
            ? "bg-[#59745D] text-white"
            : "bg-gradient-to-br from-[#59745D] to-[#4a6350] text-white"
        }`}>
          {phase === "recording" && <Mic size={22} strokeWidth={1.5}/>}
          {(phase === "transcribing" || phase === "thinking") && (
            <Loader2 size={22} strokeWidth={1.5} className="animate-spin"/>
          )}
          {phase === "done" && <Check size={22} strokeWidth={2}/>}
          {phase === "idle" && (unsupported ? <MicOff size={22} strokeWidth={1.5}/> : <Mic size={22} strokeWidth={1.5}/>)}
        </span>
      </button>

      {/* Mute toggle — sits to the LEFT of the mic. Doubles as "stop speaking". */}
      <button
        type="button"
        onClick={speaking ? stopSpeaking : toggleTts}
        className={`fixed bottom-7 right-24 z-[91] w-10 h-10 rounded-full shadow ring-1 ring-black/5 flex items-center justify-center transition-all ${
          ttsOn ? "bg-white text-[#59745D]" : "bg-white text-[#9A9F9D]"
        } hover:scale-105 active:scale-95`}
        title={speaking ? "Stop Yaar's voice" : ttsOn ? "Yaar speaks replies — tap to mute" : "Voice replies muted — tap to unmute"}
        data-testid="voice-tts-toggle"
        aria-label={ttsOn ? "Mute Yaar's voice" : "Enable Yaar's voice"}
      >
        {speaking ? (
          <span className="relative flex items-center justify-center">
            <Volume2 size={16} strokeWidth={1.5}/>
            <span className="absolute -inset-1 rounded-full ring-2 ring-[#59745D]/40 animate-pulse"/>
          </span>
        ) : ttsOn ? <Volume2 size={16} strokeWidth={1.5}/> : <VolumeX size={16} strokeWidth={1.5}/>}
      </button>
    </>
  );
}
