/**
 * useNewOrderNotifier — pop a toast + play a soft "ding" the moment a new
 * online order lands.
 *
 * Workflow:
 *   1. On mount (admin logged in), set the cursor to "now" so we never
 *      re-notify orders that came in before the admin opened the tab.
 *   2. Every POLL_INTERVAL_MS, GET /api/shop/admin/online-orders/recent?since=<cursor>
 *   3. For each fresh order, call toast.success(...) + play a Web Audio ding.
 *   4. Advance the cursor to the latest order's created_at.
 *
 * Only runs when:
 *   - a JWT is in localStorage,
 *   - the tab is visible,
 *   - the polling endpoint returns 200 (silently no-ops on 401/403/network).
 */
import { useEffect, useRef } from 'react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const POLL_INTERVAL_MS = 10_000;
const STORAGE_KEY = 'tilestation_admin_orders_cursor';

/** Generate a soft "ding" via the Web Audio API (no audio file needed). */
function playDing() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    // Two-note pleasant chime: 880 Hz → 1320 Hz
    osc.frequency.setValueAtTime(880, now);
    osc.frequency.setValueAtTime(1320, now + 0.12);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.18, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.4);
    osc.connect(gain).connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.45);
    setTimeout(() => ctx.close().catch(() => {}), 600);
  } catch {
    /* silent — sound is a nice-to-have */
  }
}

async function fetchRecent(token, since) {
  const url = new URL(`${API_URL}/api/shop/admin/online-orders/recent`);
  if (since) url.searchParams.set('since', since);
  url.searchParams.set('limit', '20');
  const res = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return null;
  return res.json();
}

export default function useNewOrderNotifier() {
  const intervalRef = useRef(null);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) return undefined;

    // Initialise cursor to "now" so existing pending orders don't ding on mount
    if (!localStorage.getItem(STORAGE_KEY)) {
      localStorage.setItem(STORAGE_KEY, new Date().toISOString());
    }

    let stopped = false;

    const poll = async () => {
      if (stopped || document.visibilityState !== 'visible') return;
      const cursor = localStorage.getItem(STORAGE_KEY);
      const data = await fetchRecent(token, cursor);
      if (!data || !Array.isArray(data.orders) || data.orders.length === 0) return;

      // Iterate oldest → newest so the most recent toast lands on top
      const fresh = [...data.orders].sort(
        (a, b) => new Date(a.created_at) - new Date(b.created_at),
      );
      let latest = cursor;
      let dinged = false;

      fresh.forEach((order) => {
        if (!order?.created_at) return;
        if (cursor && order.created_at <= cursor) return; // belt-and-braces
        const total = Number(order.total || 0).toFixed(2);
        const num = order.order_number || (order.id || '').slice(0, 8);
        const customer = order.customer_name || 'Guest';
        toast.success(`🛒 New order #${num} — £${total}`, {
          description: `${customer} · ${order.delivery_method === 'collect' ? 'Click & Collect' : 'Delivery'}`,
          duration: 8000,
          action: {
            label: 'View',
            onClick: () => { window.location.href = `/admin/online-orders`; },
          },
        });
        if (!dinged) { playDing(); dinged = true; }
        if (!latest || order.created_at > latest) latest = order.created_at;
      });

      if (latest && latest !== cursor) {
        localStorage.setItem(STORAGE_KEY, latest);
      }
    };

    // First poll after a tiny delay so it doesn't race with admin login
    const initial = setTimeout(poll, 2000);
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      stopped = true;
      clearTimeout(initial);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);
}
