import React, { useEffect, useRef, useState, useCallback } from "react";
import { api, API, authStore } from "../lib/api";
import { Sparkles, Play, X, Volume2 } from "lucide-react";
import { loadBriefs, isFiredToday, markFiredToday } from "../lib/briefs";
import { isNative, syncBriefsToNative, onBriefTap, requestNativePermission } from "../lib/nativeBridge";

/**
 * BriefScheduler — runs invisible every 30s.
 * When a brief is due (current time >= brief.time AND not fired today AND enabled):
 *   1. Generate the spoken text via /api/voice/brief
 *   2. Show an in-app toast UI with a Play button
 *   3. If document.visibilityState === "visible" AND user has interacted at least once,
 *      try to auto-play. Otherwise wait for tap.
 *   4. If not on the page, fire a Notification (if granted) so user gets pinged.
 */

const TICK_MS = 30 * 1000;

function nowHHMM() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export default function BriefScheduler() {
  const [pending, setPending] = useState(null); // { brief, text }
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef(null);
  const userInteractedRef = useRef(false);

  // Track ANY user interaction so we know we can auto-play with sound
  useEffect(() => {
    const onAct = () => { userInteractedRef.current = true; };
    window.addEventListener("pointerdown", onAct, { once: true });
    window.addEventListener("keydown", onAct, { once: true });
    return () => {
      window.removeEventListener("pointerdown", onAct);
      window.removeEventListener("keydown", onAct);
    };
  }, []);

  // ---- NATIVE (Android/iOS via Capacitor) ----
  // On launch: ask permission once, sync every enabled brief to OS-level local notifications,
  // and subscribe to taps so a tapped notification opens the corresponding brief.
  useEffect(() => {
    if (!isNative()) return;
    let unsub = () => {};
    (async () => {
      try {
        await requestNativePermission();
        await syncBriefsToNative(loadBriefs());
        unsub = onBriefTap(async ({ briefId, kind }) => {
          // Re-fetch fresh brief text and play it
          try {
            const briefs = loadBriefs();
            const b = briefs.find(x => x.id === briefId) || { kind };
            const body = b.kind === "custom"
              ? { kind: "custom", custom_prompt: b.prompt || "" }
              : { kind: b.kind };
            const { data } = await api.post("/voice/brief", body);
            const text = (data?.text || "").trim();
            if (!text) return;
            markFiredToday(briefId);
            setPending({ brief: b, text });
            if (((localStorage.getItem("yaar_voice_replies") || "on") === "on")) {
              play(text);
            }
          } catch {}
        });
      } catch {}
    })();
    // Re-sync whenever the brief list changes in another tab/dialog
    const onStorage = (e) => {
      if (e.key === "yaar_brief_schedule_v1") {
        syncBriefsToNative(loadBriefs());
      }
    };
    window.addEventListener("storage", onStorage);
    return () => {
      unsub?.();
      window.removeEventListener("storage", onStorage);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stop = useCallback(() => {
    if (audioRef.current) {
      try { audioRef.current.pause(); } catch {}
      try { URL.revokeObjectURL(audioRef.current.src); } catch {}
      audioRef.current = null;
    }
    setPlaying(false);
  }, []);

  const play = useCallback(async (text) => {
    if (!text) return;
    stop();
    try {
      const token = authStore.getToken();
      const res = await fetch(`${API}/voice/speak`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ text: text.slice(0, 4000), voice: "coral", provider: "openai" }),
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = new Audio(url);
      audioRef.current = a;
      a.onended = stop;
      a.onerror = stop;
      setPlaying(true);
      try { await a.play(); } catch { stop(); }
    } catch { stop(); }
  }, [stop]);

  const fireNotification = useCallback((brief, preview) => {
    if (typeof Notification === "undefined") return;
    if (Notification.permission !== "granted") return;
    if (document.visibilityState === "visible") return; // they're on the app already
    try {
      const n = new Notification(`Yaar's ${brief.label.toLowerCase()}`, {
        body: preview.slice(0, 140),
        tag: `yaar-brief-${brief.id}`,
        icon: "/favicon.ico",
      });
      n.onclick = () => { window.focus(); n.close(); };
    } catch {}
  }, []);

  // Tick
  useEffect(() => {
    let timer;
    const ttsOn = () => (localStorage.getItem("yaar_voice_replies") || "on") === "on";

    const tick = async () => {
      try {
        const briefs = loadBriefs().filter(b => b.enabled);
        if (!briefs.length) return;
        const cur = nowHHMM();
        // A brief is "due" if it has the same HH:MM and hasn't fired today, OR
        // if its time is earlier today and we haven't fired (catch-up if app was closed).
        for (const b of briefs) {
          if (isFiredToday(b.id)) continue;
          // Time comparison HH:MM (string compare works for zero-padded 24h)
          if (cur < b.time) continue;
          // Build the text
          const body = b.kind === "custom"
            ? { kind: "custom", custom_prompt: b.prompt || "" }
            : { kind: b.kind };
          let text = "";
          try {
            const { data } = await api.post("/voice/brief", body);
            text = (data?.text || "").trim();
          } catch {}
          if (!text) continue;
          markFiredToday(b.id);
          setPending({ brief: b, text });
          fireNotification(b, text);
          // Try auto-play if we're on the page AND user interacted
          if (document.visibilityState === "visible" && userInteractedRef.current && ttsOn()) {
            play(text);
          }
          break; // one brief at a time
        }
      } catch {}
    };

    // First tick after 5s, then every TICK_MS
    const initial = setTimeout(tick, 5000);
    timer = setInterval(tick, TICK_MS);
    return () => { clearTimeout(initial); clearInterval(timer); stop(); };
  }, [play, stop, fireNotification]);

  if (!pending) return null;

  const { brief, text } = pending;

  return (
    <div
      className="fixed top-6 right-6 z-[95] max-w-sm pointer-events-auto animate-fade-in-up"
      data-testid="brief-toast"
    >
      <div className="rounded-2xl bg-white border border-sand shadow-xl px-4 py-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="w-7 h-7 rounded-full bg-gradient-to-br from-[#59745D] to-[#A3897C] flex items-center justify-center">
            <Sparkles size={12} strokeWidth={1.5} className="text-white"/>
          </span>
          <p className="text-[10px] uppercase tracking-widest text-[#C27A62]" data-testid="brief-toast-label">
            Yaar · {brief.label}
          </p>
          <button
            onClick={() => { stop(); setPending(null); }}
            className="ml-auto w-7 h-7 rounded-full hover:bg-[#F4F1EA] text-[#9A9F9D] flex items-center justify-center"
            title="Dismiss"
            data-testid="brief-toast-close"
          >
            <X size={13} strokeWidth={1.5}/>
          </button>
        </div>
        <p className="text-sm text-[#2D312E] leading-relaxed line-clamp-4" data-testid="brief-toast-text">
          {text.length > 280 ? text.slice(0, 280) + "…" : text}
        </p>
        <div className="mt-3 flex items-center gap-2">
          {playing ? (
            <button
              onClick={stop}
              className="flex items-center gap-1.5 px-4 h-9 rounded-full bg-[#59745D] text-white text-xs font-medium hover:bg-[#4a6350]"
              data-testid="brief-toast-stop"
            >
              <Volume2 size={13} strokeWidth={1.5} className="animate-pulse"/> Speaking…
            </button>
          ) : (
            <button
              onClick={() => play(text)}
              className="flex items-center gap-1.5 px-4 h-9 rounded-full bg-[#59745D] text-white text-xs font-medium hover:bg-[#4a6350]"
              data-testid="brief-toast-play"
            >
              <Play size={12} strokeWidth={1.5} fill="currentColor"/> Play brief
            </button>
          )}
          <button
            onClick={() => { stop(); setPending(null); }}
            className="text-xs text-[#9A9F9D] hover:text-[#2D312E]"
            data-testid="brief-toast-later"
          >
            Later
          </button>
        </div>
      </div>
    </div>
  );
}
