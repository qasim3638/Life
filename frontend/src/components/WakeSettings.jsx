/**
 * WakeSettings — bottom-sheet dialog to configure "Hi Yaar" wake word + shake.
 * Accessible from the voice mic cluster. Stores settings in localStorage;
 * HiYaarListener + useShakeToTalk both react via the `life:wake-settings` event.
 */
import React, { useState } from "react";
import { Settings as SettingsIcon, X, ExternalLink } from "lucide-react";
import {
  getWakeEnabled, setWakeEnabled,
  getPicovoiceKey, setPicovoiceKey,
} from "./HiYaarListener";
import {
  getShakeEnabled, setShakeEnabled, requestShakePermissionIfNeeded,
} from "../lib/useShakeToTalk";
import { toast } from "sonner";

export default function WakeSettings() {
  const [open, setOpen] = useState(false);
  const [wake, setWake] = useState(getWakeEnabled());
  const [shake, setShake] = useState(getShakeEnabled());
  const [key, setKey] = useState(getPicovoiceKey());

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
              <label className="block text-[10px] uppercase tracking-[0.3em] text-[#A3897C] mt-3">
                Picovoice AccessKey
              </label>
              <div className="flex gap-2 mt-1">
                <input
                  type="password"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  placeholder="Paste your AccessKey"
                  className="flex-1 px-3 py-2 rounded-xl border border-sand bg-[#FDFBF7] text-sm text-[#2D312E] focus:outline-none focus:border-[#59745D]"
                  data-testid="picovoice-key-input"
                />
                <button
                  onClick={saveKey}
                  disabled={!key.trim()}
                  className="px-4 py-2 rounded-xl bg-[#59745D] text-white text-sm disabled:opacity-40"
                  data-testid="picovoice-key-save"
                >
                  Save
                </button>
              </div>
              <a
                href="https://console.picovoice.ai"
                target="_blank"
                rel="noreferrer"
                className="text-xs text-[#59745D] underline underline-offset-4 mt-3 inline-flex items-center gap-1"
              >
                Get free AccessKey <ExternalLink size={11}/>
              </a>
              <p className="text-[11px] text-[#9A9F9D] mt-3 leading-relaxed">
                Also drop <code className="bg-[#F4F1EA] px-1 rounded">hi_yaar.ppn</code> and <code className="bg-[#F4F1EA] px-1 rounded">porcupine_params.pv</code> in <code className="bg-[#F4F1EA] px-1 rounded">/public/models/</code> then redeploy.
              </p>
            </div>

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

            <p className="text-[11px] text-[#9A9F9D] leading-relaxed text-center">
              Works while the app is open. Screen-off listening is a native feature coming in a later build.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
