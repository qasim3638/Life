/**
 * EnrollVoiceprint — 3-sample Eagle enrollment flow.
 *
 * Loaded inline from WakeSettings. Records audio via @picovoice/eagle-web's
 * EagleProfiler.create() + WebVoiceProcessor, until enrollment hits 100%.
 * Exports profile bytes → POSTs to backend `/api/speaker/profile`.
 */
import React, { useEffect, useRef, useState } from "react";
import { Mic, Check, RotateCcw, X } from "lucide-react";
import { EagleProfiler } from "@picovoice/eagle-web";
import { WebVoiceProcessor } from "@picovoice/web-voice-processor";
import { api } from "../lib/api";
import { getPicovoiceKey } from "./HiYaarListener";
import { toast } from "sonner";

const EAGLE_MODEL = {
  publicPath: "/models/eagle_params.pv",
  forceWrite: true,
};

const FEEDBACK_TEXT = {
  AUDIO_OK: "Sounds great",
  AUDIO_TOO_SHORT: "Speak a bit longer",
  AUDIO_TOO_NOISY: "Quieter spot, please",
  UNKNOWN_SPEAKER: "Try again, more naturally",
  NO_VOICE_FOUND: "Couldn't hear you",
  QUALITY_ISSUE: "Speak naturally, no whispering",
};

export default function EnrollVoiceprint({ onClose, onEnrolled }) {
  const [profiler, setProfiler] = useState(null);
  const [percentage, setPercentage] = useState(0);
  const [feedback, setFeedback] = useState("");
  const [phase, setPhase] = useState("idle"); // idle | recording | processing | done | error
  const [errorMsg, setErrorMsg] = useState("");
  const subscribed = useRef(false);

  // Init Eagle profiler
  useEffect(() => {
    let p = null;
    (async () => {
      const key = getPicovoiceKey();
      if (!key) {
        setErrorMsg("Save your Picovoice AccessKey first.");
        setPhase("error");
        return;
      }
      try {
        p = await EagleProfiler.create(key, EAGLE_MODEL);
        setProfiler(p);
      } catch (e) {
        setErrorMsg(e?.message || "Couldn't load Eagle.");
        setPhase("error");
      }
    })();
    return () => {
      (async () => {
        try {
          if (subscribed.current && p) await WebVoiceProcessor.unsubscribe(p);
          if (p) await p.release();
        } catch (_) {}
      })();
    };
  }, []);

  // Wire profiler → WebVoiceProcessor when recording
  useEffect(() => {
    if (!profiler) return;
    profiler.onenrollProgress = (pct, fb) => {
      setPercentage(pct || 0);
      setFeedback(FEEDBACK_TEXT[fb] || "");
    };
  }, [profiler]);

  const startRecording = async () => {
    if (!profiler) return;
    try {
      await WebVoiceProcessor.subscribe(profiler);
      subscribed.current = true;
      setPhase("recording");
    } catch (e) {
      setErrorMsg(e?.message || "Mic permission needed.");
      setPhase("error");
    }
  };

  const stopRecording = async () => {
    if (!profiler) return;
    try {
      await WebVoiceProcessor.unsubscribe(profiler);
      subscribed.current = false;
    } catch (_) {}
    setPhase(percentage >= 100 ? "done" : "idle");
  };

  const finalize = async () => {
    if (!profiler || percentage < 100) return;
    setPhase("processing");
    try {
      const profile = profiler.export();
      const bytes = profile.bytes || profile; // SDK shape
      // Convert Uint8Array → base64
      let s = "";
      for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
      const base64 = btoa(s);
      await api.put("/speaker/profile", { profile_base64: base64, threshold: 0.6 });
      toast.success("Voiceprint saved");
      onEnrolled?.();
      onClose?.();
    } catch (e) {
      setErrorMsg(e?.response?.data?.detail || e?.message || "Couldn't save.");
      setPhase("error");
    }
  };

  const reset = async () => {
    if (!profiler) return;
    try {
      if (subscribed.current) {
        await WebVoiceProcessor.unsubscribe(profiler);
        subscribed.current = false;
      }
      profiler.reset();
      setPercentage(0);
      setFeedback("");
      setPhase("idle");
      setErrorMsg("");
    } catch (_) {}
  };

  return (
    <div className="fixed inset-0 z-[130] bg-black/40 flex items-end sm:items-center justify-center" data-testid="enroll-voiceprint">
      <div
        className="w-full sm:max-w-md bg-[#FDFBF7] rounded-t-3xl sm:rounded-3xl shadow-2xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C]">Yaar</p>
            <h2 className="font-serif text-2xl text-[#2D312E]">Teach Yaar your voice</h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white border border-sand flex items-center justify-center text-[#9A9F9D]"
          >
            <X size={16}/>
          </button>
        </div>

        <p className="text-sm text-[#6B7270] mb-5 leading-relaxed">
          Speak naturally for ~30 seconds. Different sentences work best — read a paragraph, talk about your day, count to 30. We'll keep going until Yaar's confident.
        </p>

        {/* Progress ring */}
        <div className="flex flex-col items-center my-6">
          <div className="relative w-36 h-36">
            <svg className="w-36 h-36 -rotate-90" viewBox="0 0 144 144">
              <circle cx="72" cy="72" r="64" fill="none" stroke="#E5DED3" strokeWidth="8"/>
              <circle
                cx="72" cy="72" r="64" fill="none" stroke="#59745D" strokeWidth="8"
                strokeDasharray={`${(percentage / 100) * 402} 402`}
                strokeLinecap="round"
                style={{ transition: "stroke-dasharray 0.4s ease" }}
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="font-serif text-3xl text-[#2D312E]">{Math.round(percentage)}%</span>
            </div>
          </div>
          {feedback && phase === "recording" && (
            <p className="text-xs text-[#6B7270] mt-3">{feedback}</p>
          )}
        </div>

        {errorMsg && (
          <p className="text-sm text-[#C27A62] text-center mb-3" data-testid="enroll-error">{errorMsg}</p>
        )}

        {/* Controls */}
        <div className="flex gap-2">
          {phase === "idle" && percentage < 100 && (
            <button
              onClick={startRecording}
              disabled={!profiler}
              className="flex-1 py-3 rounded-full bg-[#59745D] hover:bg-[#4A604D] text-white font-medium flex items-center justify-center gap-2 disabled:opacity-40"
              data-testid="enroll-start"
            >
              <Mic size={16}/>
              Start
            </button>
          )}
          {phase === "recording" && (
            <button
              onClick={stopRecording}
              className="flex-1 py-3 rounded-full bg-[#C27A62] hover:bg-[#A65F4A] text-white font-medium"
              data-testid="enroll-stop"
            >
              Pause
            </button>
          )}
          {phase === "idle" && percentage > 0 && percentage < 100 && (
            <button
              onClick={startRecording}
              className="flex-1 py-3 rounded-full bg-[#59745D] hover:bg-[#4A604D] text-white font-medium flex items-center justify-center gap-2"
            >
              <Mic size={16}/>
              Continue
            </button>
          )}
          {percentage >= 100 && phase !== "processing" && (
            <button
              onClick={finalize}
              className="flex-1 py-3 rounded-full bg-[#59745D] hover:bg-[#4A604D] text-white font-medium flex items-center justify-center gap-2"
              data-testid="enroll-finish"
            >
              <Check size={16}/>
              Save voiceprint
            </button>
          )}
          {percentage > 0 && (
            <button
              onClick={reset}
              className="px-4 py-3 rounded-full bg-white border border-sand text-[#6B7270] hover:bg-[#F4F1EA]"
              title="Restart"
              data-testid="enroll-reset"
            >
              <RotateCcw size={14}/>
            </button>
          )}
        </div>

        <p className="text-[11px] text-[#9A9F9D] mt-4 leading-relaxed text-center">
          Voiceprint is stored in your private database. Yaar uses it on-device only.
        </p>
      </div>
    </div>
  );
}
