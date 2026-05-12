/**
 * PicovoiceWakeWord — production-grade wake word using Picovoice Porcupine.
 *
 * Uses the custom "Hi Yaar" model at /models/hi_yaar.ppn + the English
 * language model at /models/porcupine_params.pv.
 *
 * Activated only when:
 *   - User has Picovoice AccessKey stored (life_picovoice_key)
 *   - Wake-word toggle is ON (life_wake_enabled)
 *
 * Dispatches `life:wake` event when "Hi Yaar" is detected — same event
 * VoiceMicButton listens for. Pauses while Yaar speaks / recording / voiceprint enrollment.
 */
import { useEffect, useRef, useState } from "react";
import { PorcupineWorker } from "@picovoice/porcupine-web";
import { WebVoiceProcessor } from "@picovoice/web-voice-processor";
import { Capacitor } from "@capacitor/core";

const IS_NATIVE = Capacitor?.isNativePlatform?.() || false;
const getPicovoiceKey = () => localStorage.getItem("life_picovoice_key") || "";
const getWakeEnabled = () => (localStorage.getItem("life_wake_enabled") || "off") === "on";

export default function PicovoiceWakeWord() {
  const [enabled, setEnabledState] = useState(getWakeEnabled() && !!getPicovoiceKey());
  const workerRef = useRef(null);
  const pausedRef = useRef(false);
  const startingRef = useRef(false);

  // React to settings change
  useEffect(() => {
    const handler = () => setEnabledState(getWakeEnabled() && !!getPicovoiceKey());
    window.addEventListener("life:wake-settings", handler);
    return () => window.removeEventListener("life:wake-settings", handler);
  }, []);

  // Pause/resume in response to other voice activity
  useEffect(() => {
    const pause = async () => {
      pausedRef.current = true;
      const w = workerRef.current;
      if (!w) return;
      try { await WebVoiceProcessor.unsubscribe(w); } catch {}
      // On native (Capacitor APK), the Android mic can only be held by one
      // source at a time. Fully terminate the worker so VoiceRecorder plugin
      // can grab the mic. We'll recreate on resume.
      if (IS_NATIVE) {
        try { await w.terminate(); } catch {}
        workerRef.current = null;
      }
    };
    const resume = async () => {
      pausedRef.current = false;
      if (!enabled) return;
      if (workerRef.current) {
        try { await WebVoiceProcessor.subscribe(workerRef.current); } catch {}
      } else if (IS_NATIVE) {
        // Worker was terminated — kick off a fresh start
        window.dispatchEvent(new CustomEvent("life:wake-rebuild"));
      }
    };
    window.addEventListener("life:mic-recording-start", pause);
    window.addEventListener("life:mic-recording-end", resume);
    window.addEventListener("life:yaar-speaking-start", pause);
    window.addEventListener("life:yaar-speaking-end", resume);
    window.addEventListener("life:wake-pause", pause);
    window.addEventListener("life:wake-resume", resume);
    return () => {
      window.removeEventListener("life:mic-recording-start", pause);
      window.removeEventListener("life:mic-recording-end", resume);
      window.removeEventListener("life:yaar-speaking-start", pause);
      window.removeEventListener("life:yaar-speaking-end", resume);
      window.removeEventListener("life:wake-pause", pause);
      window.removeEventListener("life:wake-resume", resume);
    };
  }, [enabled]);

  // Start/stop the worker when enabled changes
  useEffect(() => {
    let cancelled = false;

    const start = async () => {
      if (startingRef.current) return;
      startingRef.current = true;
      try {
        const accessKey = getPicovoiceKey();
        if (!accessKey) { startingRef.current = false; return; }

        const keyword = {
          publicPath: "/models/hi_yaar.ppn",
          label: "Hi Yaar",
          sensitivity: 0.6,
        };
        const model = { publicPath: "/models/porcupine_params.pv" };

        const worker = await PorcupineWorker.create(
          accessKey,
          keyword,
          (detection) => {
            // Wake word detected
            if (pausedRef.current) return;
            window.dispatchEvent(new CustomEvent("life:wake", {
              detail: { label: detection?.label || "Hi Yaar" },
            }));
          },
          model,
        );
        if (cancelled) { try { await worker.terminate(); } catch {} ; startingRef.current = false; return; }

        workerRef.current = worker;
        await WebVoiceProcessor.subscribe(worker);
        console.log("[Picovoice] Porcupine wake word listening for 'Hi Yaar'");
      } catch (e) {
        console.error("[Picovoice] init failed:", e?.message || e);
        // Fall back gracefully — Web Speech component will take over if enabled
      } finally {
        startingRef.current = false;
      }
    };

    const stop = async () => {
      const w = workerRef.current;
      workerRef.current = null;
      if (w) {
        try { await WebVoiceProcessor.unsubscribe(w); } catch {}
        try { await w.terminate(); } catch {}
      }
    };

    if (enabled) start();
    else stop();

    const rebuildHandler = () => {
      if (enabled && !pausedRef.current) start();
    };
    window.addEventListener("life:wake-rebuild", rebuildHandler);

    return () => {
      cancelled = true;
      window.removeEventListener("life:wake-rebuild", rebuildHandler);
      stop();
    };
  }, [enabled]);

  return null;
}
