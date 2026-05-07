/**
 * WhisperEngine — Yaar's discreet reminder system.
 *
 * Polls /api/reminders/poll every 30s. When a reminder is due:
 *   1. Plays a soft chime (and optionally speaks the user's chosen name very
 *      quietly via TTS). Repeats every `gap_seconds`.
 *   2. Listens for any voice trigger (`life:wake`) OR an in-app tap on the
 *      summon banner. Either acknowledges & moves to step 3.
 *   3. Speaks the full reminder body in normal voice via /api/voice/speak.
 *      Shows action banner: "Mark done", "Snooze 10 min", "Dismiss".
 *   4. If user never responds within `max_attempts × gap_seconds`, applies
 *      the fallback (badge / silent / vibrate).
 */
import React, { useEffect, useRef, useState } from "react";
import { api, API } from "../lib/api";
import { Bell, Check, Clock, X } from "lucide-react";

const POLL_MS = 30_000;
const CHIME_URL = "/sounds/whisper-chime.mp3";
const CHIME_FALLBACK_FREQ = 660; // gentle bell tone if mp3 missing

// Active summon UI state
function SummonBanner({ envelope, onAck, onSnooze, onDismiss }) {
  const r = envelope.reminder;
  return (
    <div
      className="fixed top-4 left-1/2 -translate-x-1/2 z-[140] w-[92%] max-w-md
                 bg-[#FDFBF7] border border-[#59745D]/40 rounded-2xl shadow-2xl px-5 py-4
                 animate-in slide-in-from-top-3 fade-in"
      data-testid="whisper-summon-banner"
    >
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-full bg-[#59745D]/10 flex items-center justify-center text-[#59745D] flex-shrink-0">
          <Bell size={16} strokeWidth={1.5}/>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C]">Yaar</p>
          <p className="font-medium text-[#2D312E] truncate">{r.title}</p>
          {r.body && <p className="text-xs text-[#6B7270] mt-0.5 line-clamp-2">{r.body}</p>}
        </div>
      </div>
      <div className="flex gap-2 mt-3">
        <button
          onClick={onAck}
          className="flex-1 py-2 rounded-full bg-[#59745D] hover:bg-[#4A604D] text-white text-sm font-medium flex items-center justify-center gap-1"
          data-testid="summon-ack-btn"
        >
          <Check size={13}/> I'm here
        </button>
        <button
          onClick={onSnooze}
          className="px-3 py-2 rounded-full bg-white border border-sand text-[#6B7270] text-sm flex items-center justify-center gap-1"
          data-testid="summon-snooze-btn"
        >
          <Clock size={13}/> 10m
        </button>
        <button
          onClick={onDismiss}
          className="w-9 h-9 rounded-full bg-white border border-sand text-[#9A9F9D] flex items-center justify-center"
          data-testid="summon-dismiss-btn"
        >
          <X size={13}/>
        </button>
      </div>
    </div>
  );
}

export default function WhisperEngine() {
  const [active, setActive] = useState(null); // current envelope being summoned
  const attemptsRef = useRef(0);
  const tickerRef = useRef(null);
  const audioCtxRef = useRef(null);
  const acknowledgedRef = useRef(false);

  const playChime = async (style, name) => {
    // Soft tone — try mp3 first, fall back to WebAudio sine
    try {
      const a = new Audio(CHIME_URL);
      a.volume = 0.5;
      await a.play();
    } catch {
      try {
        if (!audioCtxRef.current) {
          audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
        }
        const ctx = audioCtxRef.current;
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.frequency.value = CHIME_FALLBACK_FREQ;
        g.gain.value = 0.0;
        o.connect(g).connect(ctx.destination);
        o.start();
        const t = ctx.currentTime;
        g.gain.linearRampToValueAtTime(0.18, t + 0.05);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 1.4);
        o.stop(t + 1.5);
      } catch (_) { /* silent */ }
    }
    if (style === "chime_name" || style === "name") {
      // Tiny quiet TTS of the user's name
      try {
        const res = await fetch(`${API}/voice/speak`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: `${name}?`, voice: "coral" }),
        });
        if (res.ok) {
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          const a = new Audio(url);
          a.volume = 0.45;
          await a.play().catch(() => {});
          a.onended = () => URL.revokeObjectURL(url);
        }
      } catch (_) {}
    }
  };

  const speakReminder = async (r) => {
    try {
      const text = r.body ? `${r.title}. ${r.body}` : r.title;
      const res = await fetch(`${API}/voice/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice: "coral" }),
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = new Audio(url);
        await a.play().catch(() => {});
        a.onended = () => URL.revokeObjectURL(url);
      }
    } catch (_) {}
  };

  const stopSummoning = () => {
    if (tickerRef.current) {
      clearInterval(tickerRef.current);
      tickerRef.current = null;
    }
    attemptsRef.current = 0;
    acknowledgedRef.current = true;
  };

  const acknowledge = async (env) => {
    if (acknowledgedRef.current) return;
    stopSummoning();
    try {
      await api.post(`/reminders/${env.reminder.id}/resolve`, {
        status: "acknowledged",
        attempts_made: attemptsRef.current,
      });
    } catch (_) {}
    speakReminder(env.reminder);
  };

  const snooze = async (env, mins = 10) => {
    if (acknowledgedRef.current) return;
    stopSummoning();
    try {
      await api.post(`/reminders/${env.reminder.id}/resolve`, {
        status: "snoozed",
        snooze_minutes: mins,
        attempts_made: attemptsRef.current,
      });
    } catch (_) {}
    setActive(null);
  };

  const dismiss = async (env) => {
    if (acknowledgedRef.current) return;
    stopSummoning();
    try {
      await api.post(`/reminders/${env.reminder.id}/resolve`, {
        status: "dismissed",
        attempts_made: attemptsRef.current,
      });
    } catch (_) {}
    setActive(null);
  };

  const failOut = async (env) => {
    if (acknowledgedRef.current) return;
    stopSummoning();
    try {
      await api.post(`/reminders/${env.reminder.id}/resolve`, {
        status: "failed",
        attempts_made: attemptsRef.current,
      });
    } catch (_) {}
    // Fallback: vibrate
    if (env.whisper.fallback === "vibrate" && navigator.vibrate) {
      navigator.vibrate([200, 80, 200]);
    }
    setActive(null);
  };

  const startSummoning = (env) => {
    acknowledgedRef.current = false;
    attemptsRef.current = 0;
    setActive(env);

    const w = env.whisper;
    const fire = async () => {
      attemptsRef.current += 1;
      await playChime(w.summon_style, w.summon_name);
      if (attemptsRef.current >= w.max_attempts) {
        failOut(env);
      }
    };
    fire(); // immediate first chime
    tickerRef.current = setInterval(fire, w.gap_seconds * 1000);
  };

  // Listen for life:wake while summon is active — acknowledges
  useEffect(() => {
    const onWake = () => {
      if (!active || acknowledgedRef.current) return;
      acknowledge(active);
    };
    window.addEventListener("life:wake", onWake);
    return () => window.removeEventListener("life:wake", onWake);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  // Poller
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      if (active) return; // don't queue while one is running
      try {
        const { data } = await api.get("/reminders/poll");
        if (cancelled || !data?.length) return;
        startSummoning(data[0]);
      } catch (_) {}
    };
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => { cancelled = true; clearInterval(id); stopSummoning(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  if (!active) return null;
  return (
    <SummonBanner
      envelope={active}
      onAck={() => acknowledge(active)}
      onSnooze={() => snooze(active, 10)}
      onDismiss={() => dismiss(active)}
    />
  );
}
