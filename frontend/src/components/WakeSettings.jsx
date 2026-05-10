/**
 * WakeSettings — bottom-sheet dialog to configure "Hi Yaar" wake word + shake.
 * Accessible from the voice mic cluster. Stores settings in localStorage;
 * HiYaarListener + useShakeToTalk both react via the `life:wake-settings` event.
 */
import React, { useEffect, useState } from "react";
import { Settings as SettingsIcon, X, ExternalLink, ShieldCheck } from "lucide-react";
import {
  getWakeEnabled, setWakeEnabled,
  getPicovoiceKey, setPicovoiceKey,
} from "./HiYaarListener";
import {
  getShakeEnabled, setShakeEnabled, requestShakePermissionIfNeeded,
} from "../lib/useShakeToTalk";
import EnrollVoiceprintV2 from "./EnrollVoiceprintV2";
import { api } from "../lib/api";
import { isNative, startHandsFree, stopHandsFree, onHandsFreeWake } from "../lib/handsFreeBridge";
import { toast } from "sonner";

const ALWAYS_ON_KEY = "life_handsfree_always_on";
export const getAlwaysOn = () => (localStorage.getItem(ALWAYS_ON_KEY) || "off") === "on";
export const setAlwaysOn = (on) => localStorage.setItem(ALWAYS_ON_KEY, on ? "on" : "off");

export default function WakeSettings() {
  const [open, setOpen] = useState(false);
  const [wake, setWake] = useState(getWakeEnabled());
  const [shake, setShake] = useState(getShakeEnabled());
  const [key, setKey] = useState(getPicovoiceKey());
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [voiceprintEnrolled, setVoiceprintEnrolled] = useState(false);
  const [alwaysOn, setAlwaysOnState] = useState(getAlwaysOn());
  const native = isNative();

  // Check enrollment status whenever the dialog opens
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get("/voiceprint/status");
        if (!cancelled) setVoiceprintEnrolled(!!data?.enrolled);
      } catch {
        if (!cancelled) setVoiceprintEnrolled(false);
      }
    })();
    return () => { cancelled = true; };
  }, [open]);

  // Wire native foreground-service wake events → existing life:wake event.
  useEffect(() => {
    if (!native) return;
    const off = onHandsFreeWake(() => {
      window.dispatchEvent(new CustomEvent("life:wake", { detail: { label: "Hi Yaar (native)" } }));
    });
    return off;
  }, [native]);

  const toggleAlwaysOn = async () => {
    if (!native) {
      toast.error("Always-on works only inside the installed app.");
      return;
    }
    const next = !alwaysOn;
    if (next) {
      if (!key.trim()) { toast.error("Save your AccessKey first."); return; }
      let profileBase64 = null;
      let threshold = 0.6;
      try {
        const { data } = await api.get("/speaker/profile");
        if (data?.profile_base64) {
          profileBase64 = data.profile_base64;
          threshold = data.threshold || 0.6;
        }
      } catch {}
      const res = await startHandsFree({ accessKey: key.trim(), profileBase64, threshold });
      if (!res.started) {
        toast.error(`Couldn't start: ${res.reason || "unknown"}`);
        return;
      }
      setAlwaysOn(true);
      setAlwaysOnState(true);
      toast.message("Always-on listening activated");
    } else {
      await stopHandsFree();
      setAlwaysOn(false);
      setAlwaysOnState(false);
      toast.message("Always-on stopped");
    }
  };

  const notify = () => window.dispatchEvent(new Event("life:wake-settings"));

  const saveKey = () => {
    setPicovoiceKey(key.trim());
    notify();
    toast.success("AccessKey saved");
  };

  const toggleWake = () => {
    const next = !wake;
    if (next && !key.trim()) {
      toast.error("Paste your Picovoice AccessKey first.");
      return;
    }
    setWake(next);
    setWakeEnabled(next);
    notify();
    toast.message(next ? "\"Hi Yaar\" is active" : "Wake word off");
  };

  const toggleShake = async () => {
    const next = !shake;
    if (next) {
      const perm = await requestShakePermissionIfNeeded();
      if (perm !== "granted") {
        toast.error("Motion permission denied.");
        return;
      }
    }
    setShake(next);
    setShakeEnabled(next);
    notify();
    toast.message(next ? "Shake-to-talk on" : "Shake-to-talk off");
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-7 right-[10.5rem] z-[91] w-10 h-10 rounded-full bg-white shadow ring-1 ring-black/5 flex items-center justify-center text-[#59745D] hover:scale-105 active:scale-95 transition-all"
        title="Hands-free settings"
        data-testid="wake-settings-btn"
        aria-label="Hands-free settings"
      >
        <SettingsIcon size={16} strokeWidth={1.5}/>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[120] bg-black/30 flex items-end sm:items-center justify-center"
          onClick={() => setOpen(false)}
          data-testid="wake-settings-overlay"
        >
          <div
            className="w-full sm:max-w-md bg-[#FDFBF7] rounded-t-3xl sm:rounded-3xl shadow-2xl p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <p className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C]">Yaar</p>
                <h2 className="font-serif text-2xl text-[#2D312E]">Hands-free</h2>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="w-8 h-8 rounded-full bg-white border border-sand flex items-center justify-center text-[#9A9F9D]"
                aria-label="Close"
              >
                <X size={16}/>
              </button>
            </div>

            {/* Hi Yaar wake word */}
            <div className="rounded-2xl bg-white border border-sand p-4 mb-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="font-medium text-[#2D312E]">"Hi Yaar"</p>
                  <p className="text-xs text-[#6B7270]">Say it to start recording (app open)</p>
                </div>
                <button
                  onClick={toggleWake}
                  className={`w-12 h-7 rounded-full transition-colors relative ${wake ? "bg-[#59745D]" : "bg-[#E5DED3]"}`}
                  data-testid="wake-word-toggle"
                  aria-label="Toggle wake word"
                >
                  <span className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-transform ${wake ? "translate-x-[22px]" : "translate-x-0.5"}`}/>
                </button>
              </div>
              <p className="text-[11px] text-[#9A9F9D] mt-3 leading-relaxed">
                Free — uses your device's built-in speech recognizer (Google on Android). No API key needed.
                Variants like "Hey Yaar" or "OK Yaar" also work. Pauses while Yaar speaks.
              </p>
            </div>

            {/* Voiceprint — Resemblyzer-based */}
            <div className="rounded-2xl bg-white border border-sand p-4 mb-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="font-medium text-[#2D312E] flex items-center gap-2">
                    Voiceprint
                    {voiceprintEnrolled && <ShieldCheck size={14} className="text-[#59745D]"/>}
                  </p>
                  <p className="text-xs text-[#6B7270]">
                    {voiceprintEnrolled
                      ? "Locked to your voice"
                      : "Lock private features to your voice only"}
                  </p>
                </div>
                <button
                  onClick={() => setEnrollOpen(true)}
                  className="px-3 py-1.5 rounded-xl bg-[#59745D] text-white text-xs"
                  data-testid="enroll-open-btn"
                >
                  {voiceprintEnrolled ? "Re-enroll" : "Enroll"}
                </button>
              </div>
              {voiceprintEnrolled && (
                <button
                  onClick={async () => {
                    try {
                      await api.delete("/voiceprint/delete");
                      setVoiceprintEnrolled(false);
                      toast.message("Voiceprint cleared");
                    } catch {
                      toast.error("Couldn't clear");
                    }
                  }}
                  className="text-[11px] text-[#C27A62] mt-1 hover:underline"
                >
                  Clear voiceprint
                </button>
              )}
            </div>

            {/* Voiceprint section removed (was Picovoice-dependent) */}

            {/* Shake to talk */}
            <div className="rounded-2xl bg-white border border-sand p-4 mb-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-[#2D312E]">Shake to talk</p>
                  <p className="text-xs text-[#6B7270]">Firm shake opens the mic instantly</p>
                </div>
                <button
                  onClick={toggleShake}
                  className={`w-12 h-7 rounded-full transition-colors relative ${shake ? "bg-[#59745D]" : "bg-[#E5DED3]"}`}
                  data-testid="shake-toggle"
                  aria-label="Toggle shake"
                >
                  <span className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-transform ${shake ? "translate-x-[22px]" : "translate-x-0.5"}`}/>
                </button>
              </div>
            </div>

            {/* Always-on (Phase B native) */}
            <div className="rounded-2xl bg-white border border-sand p-4 mb-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-[#2D312E]">Always-on listening</p>
                  <p className="text-xs text-[#6B7270]">Yaar listens with screen off (uses ~3% battery/day)</p>
                  {!native && <p className="text-[10px] text-[#C27A62] mt-1">Only works in installed Android app</p>}
                </div>
                <button
                  onClick={toggleAlwaysOn}
                  disabled={!native}
                  className={`w-12 h-7 rounded-full transition-colors relative ${alwaysOn ? "bg-[#59745D]" : "bg-[#E5DED3]"} disabled:opacity-40`}
                  data-testid="alwayson-toggle"
                  aria-label="Toggle always-on"
                >
                  <span className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-transform ${alwaysOn ? "translate-x-[22px]" : "translate-x-0.5"}`}/>
                </button>
              </div>
            </div>

            <p className="text-[11px] text-[#9A9F9D] leading-relaxed text-center">
              Works while the app is open. Screen-off listening is a native feature coming in a later build.
            </p>
          </div>
        </div>
      )}
      <EnrollVoiceprintV2
        open={enrollOpen}
        onClose={() => setEnrollOpen(false)}
        onEnrolled={() => setVoiceprintEnrolled(true)}
      />
    </>
  );
}
