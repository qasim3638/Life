import React, { useEffect, useRef, useState, useCallback } from "react";
import { Mic, Square, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { VoiceRecorder } from "capacitor-voice-recorder";
import { Capacitor } from "@capacitor/core";

const IS_NATIVE = Capacitor?.isNativePlatform?.() || false;

function base64ToBlob(b64, mime) {
  const byteChars = atob(b64);
  const arr = new Uint8Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) arr[i] = byteChars.charCodeAt(i);
  return new Blob([arr], { type: mime || "audio/aac" });
}

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
    const ok = IS_NATIVE
      || (typeof navigator !== "undefined"
          && navigator.mediaDevices
          && navigator.mediaDevices.getUserMedia
          && typeof MediaRecorder !== "undefined");
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

  const transcribeBlob = useCallback(async (blob, mimeHint) => {
    setPhase("transcribing");
    try {
      const mt = (mimeHint || blob.type || "").toLowerCase();
      const ext = mt.includes("aac") || mt.includes("m4a") ? "m4a"
        : mt.includes("mp4") ? "mp4"
        : mt.includes("ogg") ? "ogg"
        : mt.includes("wav") ? "wav"
        : "webm";
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
  }, [onTranscribed]);

  const handleStop = useCallback(async () => {
    const blob = new Blob(chunksRef.current, { type: chunksRef.current[0]?.type || "audio/webm" });
    cleanup();

    if (blob.size < 800) {
      setPhase("idle");
      setSeconds(0);
      toast.message("Too short — try holding a second longer.");
      return;
    }
    await transcribeBlob(blob, blob.type);
  }, [cleanup, transcribeBlob]);

  const startRecording = useCallback(async () => {
    if (recordingRef.current || phase !== "idle") return;

    // Native (Capacitor APK): use VoiceRecorder plugin
    if (IS_NATIVE) {
      try {
        const can = await VoiceRecorder.canDeviceVoiceRecord();
        if (!can?.value) {
          toast.error("This device cannot record audio.");
          return;
        }
        const perm = await VoiceRecorder.hasAudioRecordingPermission();
        if (!perm?.value) {
          const req = await VoiceRecorder.requestAudioRecordingPermission();
          if (!req?.value) {
            toast.error("Microphone permission denied.");
            return;
          }
        }
        const start = await VoiceRecorder.startRecording();
        if (!start?.value) {
          toast.error("Couldn't start recording.");
          return;
        }
        recordingRef.current = true;
        setPhase("recording");
        setSeconds(0);
        tickRef.current = setInterval(() => setSeconds(s => s + 1), 1000);
        autoStopRef.current = setTimeout(async () => {
          // Auto-stop at MAX_SECONDS
          if (recordingRef.current) {
            try {
              const result = await VoiceRecorder.stopRecording();
              recordingRef.current = false;
              if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null; }
              const v = result?.value;
              if (v?.recordDataBase64) {
                const blob = base64ToBlob(v.recordDataBase64, v.mimeType || "audio/aac");
                await transcribeBlob(blob, v.mimeType);
              } else {
                setPhase("idle"); setSeconds(0);
              }
            } catch {
              setPhase("idle"); setSeconds(0); recordingRef.current = false;
            }
          }
        }, MAX_SECONDS * 1000);
      } catch (e) {
        const name = e?.name || "Error";
        const msg = (e?.message || "").slice(0, 80);
        console.error("[VoiceNote NATIVE] start failed:", name, msg, e);
        toast.error(`Mic error: ${name} — ${msg}`);
        setPhase("idle");
      }
      return;
    }

    // Browser path
    try {
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
            sampleRate: 16000,
            channelCount: 1,
          },
        });
      } catch (firstErr) {
        console.warn("[VoiceNote] explicit constraints failed, trying basic:", firstErr?.name);
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      }
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
      tickRef.current = setInterval(() => setSeconds(s => s + 1), 1000);
      autoStopRef.current = setTimeout(() => {
        try { rec.stop(); } catch {}
      }, MAX_SECONDS * 1000);
    } catch (e) {
      const name = e?.name || "Error";
      const msg = (e?.message || "").toString().slice(0, 80);
      console.error("[VoiceNote] getUserMedia failed:", name, msg, e);
      toast.error(`Mic error: ${name} — ${msg}`);
      cleanup();
      setPhase("idle");
    }
  }, [phase, handleStop, cleanup, transcribeBlob]);

  const stopRecording = useCallback(async () => {
    if (!recordingRef.current) return;
    if (IS_NATIVE) {
      try {
        const result = await VoiceRecorder.stopRecording();
        recordingRef.current = false;
        if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null; }
        if (autoStopRef.current) { clearTimeout(autoStopRef.current); autoStopRef.current = null; }
        const v = result?.value;
        if (!v?.recordDataBase64) {
          setPhase("idle"); setSeconds(0);
          toast.message("Too short — try holding a second longer.");
          return;
        }
        const blob = base64ToBlob(v.recordDataBase64, v.mimeType || "audio/aac");
        await transcribeBlob(blob, v.mimeType);
      } catch (e) {
        const msg = (e?.message || "").slice(0, 80);
        toast.error(`Mic stop error: ${msg}`);
        setPhase("idle"); setSeconds(0); recordingRef.current = false;
      }
      return;
    }
    const rec = mediaRecorderRef.current;
    if (!rec) return;
    try { rec.stop(); } catch {}
  }, [transcribeBlob]);

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
