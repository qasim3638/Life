/**
 * PushOptIn
 * ─────────
 * Tasteful 30-day-cooldown banner that asks customers to enable web
 * push notifications for sale/restock alerts. Quietly hides itself
 * forever once dismissed (or accepted).
 *
 * Strategy:
 *   • Wait 25 seconds after page load before showing (don't interrupt
 *     the first impression)
 *   • Only show on storefront routes (NOT /admin/*)
 *   • Skip if the user has already answered (yes OR no)
 *   • Respect Notification.permission === 'denied' silently
 *   • Use Notification API + ServiceWorkerRegistration.pushManager
 *
 * Stores state in localStorage:
 *   tilestation.push.opt_at  — ISO date when user opted in/out
 *   tilestation.push.opt    — 'yes' | 'no' | undefined
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Bell, X } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const STORAGE_KEY = 'tilestation.push.opt';
const STORAGE_DATE = 'tilestation.push.opt_at';
const RE_PROMPT_DAYS = 30;

const urlBase64ToUint8Array = (base64) => {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = window.atob(b64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
};

const PushOptIn = () => {
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Skip in admin
    if (typeof window === 'undefined') return;
    if (window.location.pathname.startsWith('/admin')) return;

    // Skip if browser doesn't support push
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return;

    // Skip if user has already explicitly said yes/no within window
    try {
      const opt = localStorage.getItem(STORAGE_KEY);
      const at = localStorage.getItem(STORAGE_DATE);
      if (opt === 'yes') return; // already opted in — don't show again
      if (opt === 'no' && at) {
        const ageDays = (Date.now() - new Date(at).getTime()) / 86400000;
        if (ageDays < RE_PROMPT_DAYS) return;
      }
    } catch { /* ignore */ }

    // Skip if browser-level permission is already 'granted' (we still
    // try to register if missing)
    if (Notification.permission === 'denied') return;

    // Wait 25s before prompting — let user explore first
    const t = setTimeout(() => setShow(true), 25_000);
    return () => clearTimeout(t);
  }, []);

  const optIn = async () => {
    setBusy(true);
    setError(null);
    try {
      // Permission
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') {
        localStorage.setItem(STORAGE_KEY, 'no');
        localStorage.setItem(STORAGE_DATE, new Date().toISOString());
        setShow(false);
        return;
      }

      // Get VAPID key
      const cfg = await axios.get(`${API_URL}/api/push/config`);
      const pubKey = cfg.data.public_key;
      if (!pubKey) throw new Error('Push not configured');

      // Make sure SW is registered (it is, from index.js — wait for ready)
      const reg = await navigator.serviceWorker.ready;

      // Subscribe
      const existing = await reg.pushManager.getSubscription();
      const sub =
        existing ||
        (await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(pubKey),
        }));

      // Persist on backend
      await axios.post(`${API_URL}/api/push/subscribe`, {
        subscription: sub.toJSON(),
      });

      localStorage.setItem(STORAGE_KEY, 'yes');
      localStorage.setItem(STORAGE_DATE, new Date().toISOString());
      setShow(false);
    } catch (e) {
      setError(e?.message || 'Could not subscribe — try again later');
    } finally {
      setBusy(false);
    }
  };

  const dismiss = () => {
    try {
      localStorage.setItem(STORAGE_KEY, 'no');
      localStorage.setItem(STORAGE_DATE, new Date().toISOString());
    } catch { /* ignore */ }
    setShow(false);
  };

  if (!show) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-[9998] max-w-sm bg-white border-2 border-pink-200 rounded-xl shadow-2xl p-4 animate-in fade-in slide-in-from-bottom-4 duration-500"
      data-testid="push-opt-in-banner"
      role="dialog"
      aria-label="Enable notifications"
    >
      <button
        onClick={dismiss}
        className="absolute top-1.5 right-1.5 p-1 rounded-full hover:bg-slate-100 text-slate-400"
        aria-label="Dismiss"
        data-testid="push-opt-in-dismiss"
      >
        <X className="w-4 h-4" />
      </button>
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-pink-500 to-rose-600 flex items-center justify-center shrink-0">
          <Bell className="w-5 h-5 text-white" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-bold text-slate-900">Get sale alerts first</div>
          <div className="text-xs text-slate-600 mt-0.5">
            Tap "Allow" and we'll ping you when stock you like is restocked or 25%+ sales drop. No
            email. Off by default — turn off any time.
          </div>
          {error && <div className="text-xs text-rose-600 mt-1.5">{error}</div>}
          <div className="flex gap-2 mt-3">
            <button
              onClick={optIn}
              disabled={busy}
              className="bg-pink-600 hover:bg-pink-700 text-white px-3 py-1.5 rounded-md text-xs font-bold disabled:opacity-60"
              data-testid="push-opt-in-allow"
            >
              {busy ? 'Enabling…' : 'Allow notifications'}
            </button>
            <button
              onClick={dismiss}
              disabled={busy}
              className="text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-md text-xs font-medium"
              data-testid="push-opt-in-decline"
            >
              No thanks
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PushOptIn;
