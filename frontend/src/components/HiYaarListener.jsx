/**
 * HiYaarListener — Phase A web-based wake word + voiceprint verification.
 *
 * Flow (when both wake + voiceprint enrolled):
 *   1. Porcupine listens for "Hi Yaar"
 *   2. Wake fires → unsubscribe Porcupine, subscribe Eagle (verifier)
 *   3. Eagle reads ~1.5s of audio, averages similarity score
 *   4. If score >= threshold → dispatch `life:wake` (mic opens for chat)
 *   5. If score < threshold → silently re-subscribe Porcupine (impostor ignored)
 *   6. After VoiceMicButton recording done → `life:resume-wake` → re-subscribe Porcupine
 *
 * Without an enrolled voiceprint, step 2-5 are skipped — wake fires immediately.
 */
import { useEffect, useRef, useState } from "react";
import { PorcupineWorker } from "@picovoice/porcupine-web";
import { Eagle } from "@picovoice/eagle-web";
import { WebVoiceProcessor } from "@picovoice/web-voice-processor";
import { api } from "../lib/api";

const WAKE_PREF_KEY = "life_wake_enabled";
const KEY_STORAGE = "life_picovoice_key";

export const getWakeEnabled = () =>
  (localStorage.getItem(WAKE_PREF_KEY) || "off") === "on";
export const setWakeEnabled = (on) =>
  localStorage.setItem(WAKE_PREF_KEY, on ? "on" : "off");
export const getPicovoiceKey = () => localStorage.getItem(KEY_STORAGE) || "";
export const setPicovoiceKey = (k) => localStorage.setItem(KEY_STORAGE, k || "");

const VERIFY_FRAMES = 50;          // ~1.6s at 32-frame/s typical
const DEFAULT_THRESHOLD = 0.6;

export default function HiYaarListener() {
  const porcupineRef = useRef(null);
  const eagleRef = useRef(null);
  const eagleScoresRef = useRef([]);
  const eagleThresholdRef = useRef(DEFAULT_THRESHOLD);
  const subscribedPorcupineRef = useRef(false);
  const subscribedEagleRef = useRef(false);
  const verifyingRef = useRef(false);
  const [, setTick] = useState(0);

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

    const fireWake = () => {
      window.dispatchEvent(new CustomEvent("life:wake", { detail: { label: "Hi Yaar" } }));
    };

    const verifySpeaker = async (eagle) => {
      verifyingRef.current = true;
      eagleScoresRef.current = [];
      // Subscribe Eagle to mic
      try {
        await WebVoiceProcessor.subscribe(eagle);
        subscribedEagleRef.current = true;
      } catch {
        verifyingRef.current = false;
        return false;
      }
      // Wait for enough frames
      await new Promise((r) => setTimeout(r, 1700));
      // Unsubscribe
      try {
        await WebVoiceProcessor.unsubscribe(eagle);
        subscribedEagleRef.current = false;
      } catch {}
      verifyingRef.current = false;

      const scores = eagleScoresRef.current;
      if (scores.length < 8) return false;
      const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
      return avg >= eagleThresholdRef.current;
    };

    const stopAll = async () => {
      try {
        if (subscribedPorcupineRef.current && porcupineRef.current) {
          await WebVoiceProcessor.unsubscribe(porcupineRef.current);
          subscribedPorcupineRef.current = false;
        }
        if (subscribedEagleRef.current && eagleRef.current) {
          await WebVoiceProcessor.unsubscribe(eagleRef.current);
          subscribedEagleRef.current = false;
        }
        if (porcupineRef.current) {
          await porcupineRef.current.terminate();
          porcupineRef.current = null;
        }
        if (eagleRef.current) {
          await eagleRef.current.release?.();
          eagleRef.current = null;
        }
      } catch {}
    };

    const start = async () => {
      if (!enabled || !accessKey) return;
      if (!navigator.mediaDevices?.getUserMedia) return;

      // Try to load voiceprint (optional)
      let eagle = null;
      try {
        const { data } = await api.get("/speaker/profile");
        if (data?.profile_base64) {
          eagleThresholdRef.current = data.threshold || DEFAULT_THRESHOLD;
          // Decode base64 → Uint8Array
          const bin = atob(data.profile_base64);
          const bytes = new Uint8Array(bin.length);
          for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
          try {
            const profile = { bytes };
            eagle = await Eagle.create(
              accessKey,
              { publicPath: "/models/eagle_params.pv", forceWrite: true },
              profile,
              (scores) => {
                if (Array.isArray(scores) && scores.length > 0) {
                  eagleScoresRef.current.push(scores[0]);
                }
              },
            );
            eagleRef.current = eagle;
          } catch (eagleErr) {
            console.warn("Eagle init failed, falling back to no voiceprint:", eagleErr?.message);
          }
        }
      } catch {
        // 404 = not enrolled — fine, just skip Eagle
      }

      try {
        const keyword = {
          publicPath: "/models/hi_yaar.ppn",
          label: "Hi Yaar",
          forceWrite: true,
        };
        const model = {
          publicPath: "/models/porcupine_params.pv",
          forceWrite: true,
        };
        const worker = await PorcupineWorker.create(
          accessKey,
          keyword,
          async () => {
            // Verify before opening mic for chat
            if (verifyingRef.current) return;
            // Pause Porcupine first to free mic
            try {
              if (subscribedPorcupineRef.current && porcupineRef.current) {
                await WebVoiceProcessor.unsubscribe(porcupineRef.current);
                subscribedPorcupineRef.current = false;
              }
            } catch {}

            if (eagleRef.current) {
              const ok = await verifySpeaker(eagleRef.current);
              if (ok) {
                fireWake();
              } else {
                // Imposter — silently resume Porcupine
                try {
                  await WebVoiceProcessor.subscribe(porcupineRef.current);
                  subscribedPorcupineRef.current = true;
                } catch {}
              }
            } else {
              fireWake();
            }
          },
          model,
        );
        if (cancelled) { await worker.terminate(); return; }
        porcupineRef.current = worker;
        await WebVoiceProcessor.subscribe(worker);
        subscribedPorcupineRef.current = true;
      } catch (err) {
        console.warn("HiYaar wake word init failed:", err?.message || err);
      }
    };

    start();

    const onResume = async () => {
      if (!getWakeEnabled() || !getPicovoiceKey()) return;
      if (subscribedPorcupineRef.current) return;
      if (!porcupineRef.current) { await start(); return; }
      try {
        await WebVoiceProcessor.subscribe(porcupineRef.current);
        subscribedPorcupineRef.current = true;
      } catch {}
    };
    window.addEventListener("life:resume-wake", onResume);

    return () => {
      cancelled = true;
      window.removeEventListener("life:resume-wake", onResume);
      stopAll();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getWakeEnabled(), getPicovoiceKey()]);

  return null;
}
