/**
 * useVisitorBeacon — heartbeat from any visitor page; reports cart contents
 * and listens for admin messages.
 *
 *   - On mount + every URL change: send a heartbeat
 *   - Every 30s while the tab is visible: send a heartbeat
 *   - Each heartbeat includes a cart_summary read from localStorage
 *   - Each heartbeat *response* may include pending admin messages →
 *     dispatched on `window` as a CustomEvent('tilestation:admin-message')
 *     so the AdminLiveMessage widget can render them.
 *
 * Admin pages skip the beacon (internal team isn't a visitor).
 */
import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const HEARTBEAT_INTERVAL_MS = 30_000;
const SESSION_KEY = 'tilestation_visitor_session';

function getSessionId() {
  try {
    let id = sessionStorage.getItem(SESSION_KEY);
    if (!id) {
      id = Math.random().toString(36).slice(2, 8) + Math.random().toString(36).slice(2, 8);
      sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
  } catch {
    return 'no-storage-' + Math.random().toString(36).slice(2, 10);
  }
}

/** Read shopper's cart from localStorage and produce a small summary. */
function readCartSummary() {
  try {
    const raw = localStorage.getItem('tilestation_cart');
    if (!raw) return null;
    const cart = JSON.parse(raw);
    if (!Array.isArray(cart) || cart.length === 0) return null;
    let value = 0;
    cart.forEach(i => { value += Number(i.price || 0) * Number(i.quantity || 0); });
    return {
      items_count: cart.length,
      value: Number(value.toFixed(2)),
      top_items: cart.slice(0, 5).map(i => ({
        name: String(i.display_name || i.name || '').slice(0, 200),
        qty: Number(i.quantity || 0),
        price: Number(i.price || 0),
      })),
    };
  } catch {
    return null;
  }
}

async function sendBeacon(path, referrer) {
  try {
    const body = JSON.stringify({
      session_id: getSessionId(),
      path: path || '/',
      referrer: referrer || '',
      user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
      cart_summary: readCartSummary(),
    });
    const res = await fetch(`${API_URL}/api/live-analytics/heartbeat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
    });
    if (!res.ok) return;
    const data = await res.json().catch(() => null);
    const messages = data?.pending_messages || [];
    if (messages.length > 0 && typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('tilestation:admin-message', { detail: messages }));
    }
  } catch {
    /* silent — beacon must never break UX */
  }
}

export default function useVisitorBeacon() {
  const location = useLocation();
  const lastPathRef = useRef('');

  useEffect(() => {
    if (location.pathname.startsWith('/admin')) return undefined;

    const path = location.pathname;
    lastPathRef.current = path;
    sendBeacon(path, document.referrer || '');

    const id = setInterval(() => {
      if (document.visibilityState === 'visible') {
        sendBeacon(lastPathRef.current, document.referrer || '');
      }
    }, HEARTBEAT_INTERVAL_MS);

    return () => clearInterval(id);
  }, [location.pathname]);
}
