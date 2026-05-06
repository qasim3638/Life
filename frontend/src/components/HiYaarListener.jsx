/**
 * HiYaarListener — Phase A web-based wake word detection.
 *
 * Runs Picovoice Porcupine in a web worker inside the Capacitor WebView while
 * the app is in the foreground. When "Hi Yaar" is detected:
 *   1. Releases the mic (unsubscribes from WebVoiceProcessor)
 *   2. Dispatches a global `life:wake` event
 *   3. VoiceMicButton listens for that event and auto-starts recording
 *   4. When recording finishes, VoiceMicButton dispatches `life:resume-wake`
 *      and this component re-subscribes
 *
 * Phase B (native always-on background service) — see PRD.md.
 *
 * Config:
 *   - window localStorage key `life_wake_enabled` ("on" / "off") — master toggle
 *   - window localStorage key `life_picovoice_key` — user's AccessKey
 *   - public/models/hi_yaar.ppn  — custom wake word (user downloads from console)
 *   - public/models/porcupine_params.pv — english base model
 */
import { useEffect, useRef, useState } from "react";
import { PorcupineWorker } from "@picovoice/porcupine-web";
import { WebVoiceProcessor } from "@picovoice/web-voice-processor";

const WAKE_PREF_KEY = "life_wake_enabled";   // "on" | "off"
const KEY_STORAGE = "life_picovoice_key";    // AccessKey (single-user app)

export const getWakeEnabled = () =>
  (localStorage.getItem(WAKE_PREF_KEY) || "off") === "on";
export const setWakeEnabled = (on) =>
  localStorage.setItem(WAKE_PREF_KEY, on ? "on" : "off");
export const getPicovoiceKey = () => localStorage.getItem(KEY_STORAGE) || "";
export const setPicovoiceKey = (k) => localStorage.setItem(KEY_STORAGE, k || "");

export default function HiYaarListener() {
  const porcupineRef = useRef(null);
  const subscribedRef = useRef(false);
  const [, setTick] = useState(0);   // force re-render when enabled flips

  // React to settings toggles from other components
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === WAKE_PREF_KEY || e.key === KEY_STORAGE) setTick((t) => t + 1);
    };
    const onLocal = () => setTick((t) => t + 1);
    window.addEventListener("storage", onStorage);
    window.addEventListener("life:wake-settings", onLocal);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("life:wake-settings", onLocal);
    };
  }, []);

  useEffect(() => {
    const enabled = getWakeEnabled();
    const accessKey = getPicovoiceKey();
    let cancelled = false;

    const stop = async () => {
      try {
        if (subscribedRef.current && porcupineRef.current) {
          await WebVoiceProcessor.unsubscribe(porcupineRef.current);
          subscribedRef.current = false;
        }
        if (porcupineRef.current) {
          await porcupineRef.current.terminate();
          porcupineRef.current = null;
        }
      } catch (_) { /* silent */ }
    };

    const start = async () => {
      if (!enabled || !accessKey) return;
      if (!("mediaDevices" in navigator) || !navigator.mediaDevices?.getUserMedia) return;
      try {
        const keyword = {
          publicPath: `${process.env.PUBLIC_URL || ""}/models/hi_yaar.ppn`,
          label: "Hi Yaar",
          forceWrite: true,
        };
        const model = {
          publicPath: `${process.env.PUBLIC_URL || ""}/models/porcupine_params.pv`,
          forceWrite: true,
        };
        const worker = await PorcupineWorker.create(
          accessKey,
          keyword,
          (detection) => {
            // Fire a global event — VoiceMicButton will take over
            window.dispatchEvent(
              new CustomEvent("life:wake", { detail: { label: detection?.label || "Hi Yaar" } }),
            );
            // Pause ourselves so the mic is free for recording
            (async () => {
              try {
                if (subscribedRef.current && porcupineRef.current) {
                  await WebVoiceProcessor.unsubscribe(porcupineRef.current);
                  subscribedRef.current = false;
                }
              } catch (_) {}
            })();
          },
          model,
        );
        if (cancelled) { await worker.terminate(); return; }
        porcupineRef.current = worker;
        await WebVoiceProcessor.subscribe(worker);
        subscribedRef.current = true;
      } catch (err) {
        // Don't crash the app — just log. User can retry via settings toggle.
        console.warn("HiYaar wake word init failed:", err?.message || err);
      }
    };

    start();

    // Allow VoiceMicButton to re-enable us after it stops recording
    const onResume = async () => {
      if (!getWakeEnabled() || !getPicovoiceKey()) return;
      if (subscribedRef.current) return;
      if (!porcupineRef.current) { await start(); return; }
      try {
        await WebVoiceProcessor.subscribe(porcupineRef.current);
        subscribedRef.current = true;
      } catch (_) {}
    };
    window.addEventListener("life:resume-wake", onResume);

    return () => {
      cancelled = true;
      window.removeEventListener("life:resume-wake", onResume);
      stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getWakeEnabled(), getPicovoiceKey()]);

  return null;
}
