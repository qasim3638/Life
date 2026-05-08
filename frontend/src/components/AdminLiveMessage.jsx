/**
 * AdminLiveMessage — floating chat bubble that appears on the visitor's
 * screen when a Tile Station admin sends a live message via
 * /admin/live-visitors → "Send message".
 *
 * Listens to `window` CustomEvents emitted by useVisitorBeacon.js and
 * stacks incoming messages into a bottom-right pop-over with a soft
 * entrance animation + a subtle ding.
 *
 * Auto-dismisses each message after 30 seconds (or on click).
 *
 * No back-channel from visitor → admin (intentionally; that's a future
 * proper live-chat feature with WebSockets and consent).
 */
import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageCircle, X } from 'lucide-react';

const AUTO_DISMISS_MS = 30_000;

function playDing() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(660, now);
    osc.frequency.setValueAtTime(990, now + 0.10);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.14, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.35);
    osc.connect(gain).connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.4);
    setTimeout(() => ctx.close().catch(() => {}), 600);
  } catch {
    /* silent */
  }
}

export default function AdminLiveMessage() {
  const [messages, setMessages] = useState([]); // newest at top

  useEffect(() => {
    const onMessage = (ev) => {
      const incoming = (ev.detail || []).filter(m => m && m.id && m.message);
      if (incoming.length === 0) return;
      // Dedupe by id in case of resend
      setMessages(prev => {
        const ids = new Set(prev.map(p => p.id));
        const fresh = incoming.filter(m => !ids.has(m.id));
        if (fresh.length === 0) return prev;
        playDing();
        // Schedule auto-dismiss for each new one
        fresh.forEach(m => {
          setTimeout(() => {
            setMessages(curr => curr.filter(c => c.id !== m.id));
          }, AUTO_DISMISS_MS);
        });
        return [...fresh, ...prev].slice(0, 5); // cap visible at 5
      });
    };
    window.addEventListener('tilestation:admin-message', onMessage);
    return () => window.removeEventListener('tilestation:admin-message', onMessage);
  }, []);

  const dismiss = (id) => setMessages(m => m.filter(x => x.id !== id));

  if (messages.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 max-w-[340px]"
      data-testid="admin-live-messages"
    >
      <AnimatePresence initial={false}>
        {messages.map(m => (
          <motion.div
            key={m.id}
            initial={{ opacity: 0, y: 14, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, x: 24, scale: 0.96 }}
            transition={{ type: 'spring', damping: 18, stiffness: 220 }}
            className="bg-white rounded-2xl shadow-[0_10px_40px_-10px_rgba(0,0,0,0.25)] border border-emerald-100 overflow-hidden"
            data-testid={`admin-message-${m.id}`}
          >
            <div className="bg-gradient-to-br from-emerald-500 to-emerald-700 px-4 py-2 text-white flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inset-0 rounded-full bg-white opacity-75 animate-ping" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-white" />
                </span>
                <MessageCircle className="w-3.5 h-3.5" />
                <span className="text-[12px] font-semibold tracking-wide">{m.from_name || 'Tile Station'}</span>
              </div>
              <button
                onClick={() => dismiss(m.id)}
                aria-label="Dismiss"
                className="p-1 hover:bg-white/15 rounded-full transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <p className="px-4 py-3 text-[13px] text-[#1C1917] leading-snug whitespace-pre-wrap">
              {m.message}
            </p>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
