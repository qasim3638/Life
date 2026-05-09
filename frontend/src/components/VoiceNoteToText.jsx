import React, { useEffect, useRef, useState, useCallback } from "react";
import { Mic, Square, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

/**
 * Inline voice-to-text recorder for journal/reflection inputs.
 *
 * UX:
 *  - Tap mic → starts recording (max 60s, auto-stops)
 *  - Tap stop → stops & uploads to /api/voice/transcribe (Whisper)
 *  - Transcript is delivered via onTranscribed(text) callback
 *
 * Designed to be embedded inline next to a textarea (NOT floating).
 */

const MAX_SECONDS = 60;

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

export default function VoiceNoteToText({ onTranscribed, label = "Voice note" }) {
  const [phase, setPhase] = useState("idle"); // idle | recording | transcribing
  const [seconds, setSeconds] = useState(0);
  const [unsupported, setUnsupported] = useState(false);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const tickRef = useRef(null);
  const autoStopRef = useRef(null);
  const recordingRef = useRef(false);

  useEffect(() => {
    const ok = typeof navigator !== "undefined"
      && navigator.mediaDevices
      && navigator.mediaDevices.getUserMedia
      && typeof MediaRecorder !== "undefined";
    setUnsupported(!ok);
  }, []);

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

  const handleStop = useCallback(async () => {
    const blob = new Blob(chunksRef.current, { type: chunksRef.current[0]?.type || "audio/webm" });
    cleanup();

    if (blob.size < 800) {
      setPhase("idle");
      setSeconds(0);
      toast.message("Too short — try holding a second longer.");
      return;
    }

    setPhase("transcribing");
    try {
      const ext = (blob.type.includes("mp4") ? "mp4" : blob.type.includes("ogg") ? "ogg" : "webm");
      const fd = new FormData();
      fd.append("audio", blob, `voice-note.${ext}`);
      const { data } = await api.post("/voice/transcribe", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const text = (data?.text || "").trim();
      if (!text) {
        toast.message("Didn't catch that. Try again, a bit louder.");
      } else if (typeof onTranscribed === "function") {
        onTranscribed(text);
        toast.success("Captured.");
      }
    } catch (e) {
      toast.error("Couldn't transcribe — try again.");
    } finally {
      setPhase("idle");
      setSeconds(0);
    }
  }, [cleanup, onTranscribed]);

  const startRecording = useCallback(async () => {
    if (recordingRef.current || phase !== "idle") return;
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
      setPhase("recording");
      setSeconds(0);
      tickRef.current = setInterval(() => {
        setSeconds(s => s + 1);
      }, 1000);
      autoStopRef.current = setTimeout(() => {
        try { rec.stop(); } catch {}
      }, MAX_SECONDS * 1000);
    } catch (e) {
      toast.error(e?.name === "NotAllowedError"
        ? "Microphone permission denied."
        : "Couldn't access microphone.");
      cleanup();
      setPhase("idle");
    }
  }, [phase, handleStop, cleanup]);

  const stopRecording = useCallback(() => {
    const rec = mediaRecorderRef.current;
    if (!rec || !recordingRef.current) return;
    try { rec.stop(); } catch {}
  }, []);

  const onClick = () => {
    if (phase === "idle") startRecording();
    else if (phase === "recording") stopRecording();
  };

  if (unsupported) return null;

  const remaining = Math.max(0, MAX_SECONDS - seconds);

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={phase === "transcribing"}
      title={phase === "recording" ? "Tap to stop" : "Tap to start a voice note"}
      data-testid="voice-note-btn"
      aria-label={label}
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
        phase === "recording"
          ? "bg-[#B85C50] text-white"
          : phase === "transcribing"
          ? "bg-[#A3897C] text-white"
          : "bg-[#F4F1EA] text-[#59745D] hover:bg-[#E9E4D8]"
      }`}
    >
      {phase === "idle" && (
        <>
          <Mic size={13} strokeWidth={1.7} />
          <span>{label}</span>
        </>
      )}
      {phase === "recording" && (
        <>
          <span className="relative flex items-center justify-center">
            <Square size={11} strokeWidth={2.4} fill="currentColor" />
            <span className="absolute -inset-1 rounded-full bg-white/40 animate-ping" />
          </span>
          <span className="tabular-nums">Stop · {remaining}s</span>
        </>
      )}
      {phase === "transcribing" && (
        <>
          <Loader2 size={13} strokeWidth={1.7} className="animate-spin" />
          <span>Writing it down…</span>
        </>
      )}
    </button>
  );
}
