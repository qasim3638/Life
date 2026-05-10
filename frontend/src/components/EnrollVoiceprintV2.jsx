/**
 * EnrollVoiceprintV2 — Resemblyzer-based voiceprint enrollment.
 *
 * UX: Bottom sheet that walks the user through 3 takes of a passphrase.
 * Each take is ~3-5s. Captured via Capacitor VoiceRecorder on native,
 * MediaRecorder in browser. All 3 are converted to WAV in-browser and
 * uploaded to /api/voiceprint/enroll.
 */
import React, { useEffect, useRef, useState, useCallback } from "react";
import { Mic, Square, Check, Loader2, X, ShieldCheck } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { VoiceRecorder } from "capacitor-voice-recorder";
import { Capacitor } from "@capacitor/core";
import { convertBlobToWav } from "../lib/audioConvert";

const IS_NATIVE = Capacitor?.isNativePlatform?.() || false;
const PASSPHRASE_DEFAULT = "Yaar, it's me. Open the safe.";
const TAKE_MAX_SECONDS = 6;

function base64ToBlob(b64, mime) {
  const byteChars = atob(b64);
  const arr = new Uint8Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) arr[i] = byteChars.charCodeAt(i);
  return new Blob([arr], { type: mime || "audio/aac" });
}

function pickMime() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  for (const c of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c)) {
      return c;
    }
  }
  return "";
}

export default function EnrollVoiceprintV2({ open, onClose, passphrase = PASSPHRASE_DEFAULT, onEnrolled }) {
  const [takes, setTakes] = useState([null, null, null]); // WAV blobs
  const [currentTake, setCurrentTake] = useState(0);
  const [phase, setPhase] = useState("idle"); // idle | recording | converting | submitting
  const [seconds, setSeconds] = useState(0);
  const [enrollResult, setEnrollResult] = useState(null);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const tickRef = useRef(null);
  const autoStopRef = useRef(null);
  const recordingRef = useRef(false);

  useEffect(() => {
    if (!open) {
      setTakes([null, null, null]);
      setCurrentTake(0);
      setPhase("idle");
      setSeconds(0);
      setEnrollResult(null);
      // Resume wake-word listening (if it was running)
      window.dispatchEvent(new CustomEvent("life:wake-resume"));
    } else {
      // Pause wake-word listening so it doesn't hold the mic
      window.dispatchEvent(new CustomEvent("life:wake-pause"));
    }
    return () => {
      if (open) window.dispatchEvent(new CustomEvent("life:wake-resume"));
    };
  }, [open]);

  const cleanup = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null; }
    if (autoStopRef.current) { clearTimeout(autoStopRef.current); autoStopRef.current = null; }
    mediaRecorderRef.current = null;
    chunksRef.current = [];
    recordingRef.current = false;
  }, []);

  const handleBlobReady = useCallback(async (rawBlob, hint) => {
    setPhase("converting");
    try {
      // Convert to WAV — backend's resemblyzer wants WAV
      const wav = await convertBlobToWav(rawBlob);
      const newTakes = [...takes];
      newTakes[currentTake] = wav;
      setTakes(newTakes);
      setPhase("idle");
      setSeconds(0);
      if (currentTake < 2) {
        setCurrentTake(currentTake + 1);
      }
    } catch (e) {
      console.error("Voiceprint WAV conversion failed:", e);
      toast.error("Couldn't process that take. Try again.");
      setPhase("idle");
      setSeconds(0);
    }
  }, [takes, currentTake]);

  const startRecording = useCallback(async () => {
    if (recordingRef.current || phase !== "idle") return;

    if (IS_NATIVE) {
      try {
        const perm = await VoiceRecorder.hasAudioRecordingPermission();
        if (!perm?.value) {
          const req = await VoiceRecorder.requestAudioRecordingPermission();
          if (!req?.value) { toast.error("Microphone permission denied."); return; }
        }
        const start = await VoiceRecorder.startRecording();
        if (!start?.value) { toast.error("Couldn't start recording."); return; }
        recordingRef.current = true;
        setPhase("recording");
        setSeconds(0);
        tickRef.current = setInterval(() => setSeconds(s => s + 1), 1000);
        autoStopRef.current = setTimeout(async () => {
          if (recordingRef.current) {
            try {
              const result = await VoiceRecorder.stopRecording();
              recordingRef.current = false;
              if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null; }
              const v = result?.value;
              if (v?.recordDataBase64) {
                const blob = base64ToBlob(v.recordDataBase64, v.mimeType || "audio/aac");
                await handleBlobReady(blob);
              } else {
                setPhase("idle"); setSeconds(0);
              }
            } catch {
              setPhase("idle"); setSeconds(0);
            }
          }
        }, TAKE_MAX_SECONDS * 1000);
      } catch (e) {
        toast.error(`Mic error: ${(e?.message || "").slice(0, 60)}`);
        setPhase("idle");
      }
      return;
    }

    // Browser path
    try {
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, sampleRate: 16000, channelCount: 1 },
        });
      } catch {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      }
      streamRef.current = stream;
      const mime = pickMime();
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      mediaRecorderRef.current = rec;
      chunksRef.current = [];
      rec.ondataavailable = (e) => { if (e.data?.size > 0) chunksRef.current.push(e.data); };
      rec.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: chunksRef.current[0]?.type || "audio/webm" });
        cleanup();
        if (blob.size < 4000) {
          setPhase("idle"); setSeconds(0);
          toast.message("Too short — speak the phrase fully.");
          return;
        }
        await handleBlobReady(blob);
      };
      rec.start();
      recordingRef.current = true;
      setPhase("recording");
      setSeconds(0);
      tickRef.current = setInterval(() => setSeconds(s => s + 1), 1000);
      autoStopRef.current = setTimeout(() => { try { rec.stop(); } catch {} }, TAKE_MAX_SECONDS * 1000);
    } catch (e) {
      toast.error(`Mic error: ${(e?.name || "")} — ${(e?.message || "").slice(0, 60)}`);
      cleanup();
      setPhase("idle");
    }
  }, [phase, handleBlobReady, cleanup]);

  const stopRecording = useCallback(async () => {
    if (!recordingRef.current) return;
    if (IS_NATIVE) {
      try {
        const result = await VoiceRecorder.stopRecording();
        recordingRef.current = false;
        if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null; }
        if (autoStopRef.current) { clearTimeout(autoStopRef.current); autoStopRef.current = null; }
        const v = result?.value;
        if (v?.recordDataBase64) {
          const blob = base64ToBlob(v.recordDataBase64, v.mimeType || "audio/aac");
          await handleBlobReady(blob);
        } else {
          setPhase("idle"); setSeconds(0);
          toast.message("Hold a bit longer.");
        }
      } catch (e) {
        toast.error(`Mic stop error: ${(e?.message || "").slice(0, 60)}`);
        setPhase("idle"); setSeconds(0); recordingRef.current = false;
      }
      return;
    }
    const rec = mediaRecorderRef.current;
    if (rec) { try { rec.stop(); } catch {} }
  }, [handleBlobReady]);

  const retake = (idx) => {
    const t = [...takes]; t[idx] = null; setTakes(t); setCurrentTake(idx);
  };

  const submit = async () => {
    if (!takes[0] || !takes[1] || !takes[2]) { toast.error("Need all 3 takes."); return; }
    setPhase("submitting");
    try {
      const fd = new FormData();
      fd.append("sample1", takes[0], "take1.wav");
      fd.append("sample2", takes[1], "take2.wav");
      fd.append("sample3", takes[2], "take3.wav");
      const { data } = await api.post("/voiceprint/enroll", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setEnrollResult(data);
      toast.success(`Voiceprint enrolled! Quality: ${(data.enrollment_quality * 100).toFixed(0)}%`);
      if (typeof onEnrolled === "function") onEnrolled(data);
    } catch (e) {
      const detail = e?.response?.data?.detail || e?.message;
      toast.error(`Enrollment failed: ${(detail || "").toString().slice(0, 120)}`);
      setPhase("idle");
    }
  };

  if (!open) return null;

  const allTakesDone = takes[0] && takes[1] && takes[2];

  return (
    <div
      className="fixed inset-0 z-[140] bg-black/40 flex items-end sm:items-center justify-center"
      onClick={onClose}
      data-testid="voiceprint-overlay"
    >
      <div
        className="w-full sm:max-w-md bg-[#FDFBF7] rounded-t-3xl sm:rounded-3xl shadow-2xl p-6 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C]">Privacy</p>
            <h2 className="font-serif text-2xl text-[#2D312E]">Enroll your voice</h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white border border-sand flex items-center justify-center text-[#9A9F9D]"
            aria-label="Close"
          >
            <X size={16}/>
          </button>
        </div>

        {enrollResult ? (
          <div className="text-center py-6">
            <div className="w-16 h-16 mx-auto rounded-full bg-[#59745D]/10 flex items-center justify-center text-[#59745D] mb-3">
              <ShieldCheck size={32} strokeWidth={1.5}/>
            </div>
            <p className="font-medium text-[#2D312E] mb-1">Voiceprint locked in</p>
            <p className="text-sm text-[#6B7270] mb-4">
              Quality: <span className="font-medium text-[#59745D]">{(enrollResult.enrollment_quality * 100).toFixed(0)}%</span>
              {" · "}
              Threshold: {enrollResult.threshold}
            </p>
            <button
              onClick={onClose}
              className="px-5 py-2 rounded-full bg-[#59745D] text-white text-sm"
            >
              Done
            </button>
          </div>
        ) : (
          <>
            <div className="rounded-2xl bg-white border border-sand p-4 mb-4">
              <p className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C] mb-2">Say this 3 times</p>
              <p className="font-serif text-lg text-[#2D312E] leading-snug">"{passphrase}"</p>
              <p className="text-xs text-[#9A9F9D] mt-2">
                Speak naturally, the same way each time. ~3–5 seconds per take. Quiet room helps.
              </p>
            </div>

            <div className="space-y-2 mb-5">
              {[0, 1, 2].map((idx) => (
                <div
                  key={idx}
                  className={`flex items-center gap-3 rounded-2xl border p-3 ${
                    idx === currentTake && phase !== "submitting"
                      ? "border-[#59745D] bg-[#59745D]/5"
                      : takes[idx]
                      ? "border-sand bg-white"
                      : "border-sand bg-white opacity-60"
                  }`}
                  data-testid={`take-row-${idx}`}
                >
                  <div className="w-8 h-8 rounded-full bg-[#F4F1EA] flex items-center justify-center text-xs font-medium text-[#6B7270]">
                    {idx + 1}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm text-[#2D312E]">
                      Take {idx + 1} {takes[idx] ? "· captured" : ""}
                    </p>
                    {takes[idx] && (
                      <p className="text-[11px] text-[#9A9F9D]">{Math.round(takes[idx].size / 1024)} KB · ready</p>
                    )}
                  </div>
                  {takes[idx] ? (
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-[#59745D] text-white flex items-center justify-center">
                        <Check size={14} strokeWidth={2.5}/>
                      </div>
                      <button
                        onClick={() => retake(idx)}
                        className="text-[11px] text-[#C27A62] hover:underline"
                      >
                        Retake
                      </button>
                    </div>
                  ) : (
                    idx === currentTake && (
                      phase === "recording" ? (
                        <button
                          onClick={stopRecording}
                          className="px-3 py-1.5 rounded-full bg-[#B85C50] text-white text-xs font-medium inline-flex items-center gap-1.5"
                          data-testid={`stop-btn-${idx}`}
                        >
                          <Square size={11} fill="currentColor"/>
                          Stop · {Math.max(0, TAKE_MAX_SECONDS - seconds)}s
                        </button>
                      ) : phase === "converting" ? (
                        <span className="text-[11px] text-[#A3897C] inline-flex items-center gap-1">
                          <Loader2 size={12} className="animate-spin"/> Processing…
                        </span>
                      ) : (
                        <button
                          onClick={startRecording}
                          className="px-3 py-1.5 rounded-full bg-[#59745D] text-white text-xs font-medium inline-flex items-center gap-1.5"
                          data-testid={`record-btn-${idx}`}
                        >
                          <Mic size={11}/>
                          Record
                        </button>
                      )
                    )
                  )}
                </div>
              ))}
            </div>

            <button
              onClick={submit}
              disabled={!allTakesDone || phase === "submitting"}
              className="w-full py-3 rounded-full bg-[#59745D] text-white text-sm font-medium disabled:opacity-40 inline-flex items-center justify-center gap-2"
              data-testid="voiceprint-submit"
            >
              {phase === "submitting" ? (
                <>
                  <Loader2 size={14} className="animate-spin"/> Enrolling…
                </>
              ) : (
                <>
                  <ShieldCheck size={14}/> Lock in my voice
                </>
              )}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
