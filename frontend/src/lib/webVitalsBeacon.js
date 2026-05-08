/**
 * Web Vitals beacon — measures LCP, INP, CLS using native browser APIs
 * (no extra deps), and POSTs them to /api/health/web-vitals when the
 * page is being unloaded.
 *
 * One observer per page load. We dispatch on `visibilitychange:hidden`
 * so we capture the FINAL value of each metric (LCP can keep updating
 * until interaction, INP needs accumulated input delays).
 */
const API = process.env.REACT_APP_BACKEND_URL || '';

let installed = false;

export function installWebVitalsBeacon() {
  if (installed || typeof window === 'undefined') return;
  installed = true;

  // Skip admin and obvious bot UAs — we only care about real shop traffic.
  const path = window.location.pathname || '/';
  if (path.startsWith('/admin')) return;
  if (/bot|crawl|spider|preview|lighthouse/i.test(navigator.userAgent || '')) return;

  let lcp = null, inp = null, cls = 0, ttfb = null;

  // TTFB — easy, from Navigation Timing
  try {
    const nav = performance.getEntriesByType('navigation')[0];
    if (nav) ttfb = Math.round(nav.responseStart - nav.requestStart);
  } catch { /* old browser */ }

  const trySetup = (type, cb) => {
    try {
      const po = new PerformanceObserver((list) => list.getEntries().forEach(cb));
      po.observe({ type, buffered: true });
    } catch { /* not supported */ }
  };

  // LCP — keep the largest value observed
  trySetup('largest-contentful-paint', (e) => {
    lcp = Math.round(e.startTime || e.renderTime || 0);
  });

  // CLS — accumulate (excluding shifts caused by user input)
  trySetup('layout-shift', (e) => {
    if (!e.hadRecentInput) cls += e.value;
  });

  // INP — track each interaction's processing time, keep the worst
  let worstInteraction = 0;
  trySetup('event', (e) => {
    if (e.duration && e.duration > worstInteraction) {
      worstInteraction = e.duration;
    }
  });

  const send = () => {
    inp = worstInteraction ? Math.round(worstInteraction) : null;
    const payload = {
      path,
      lcp_ms: lcp,
      inp_ms: inp,
      cls: cls > 0 ? Number(cls.toFixed(4)) : null,
      ttfb_ms: ttfb,
    };
    try {
      const url = `${API}/api/health/web-vitals`;
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      // sendBeacon survives page unload — fire-and-forget
      if (navigator.sendBeacon && navigator.sendBeacon(url, blob)) return;
      // Fallback for browsers without sendBeacon
      fetch(url, {
        method: 'POST',
        body: JSON.stringify(payload),
        headers: { 'Content-Type': 'application/json' },
        keepalive: true,
      }).catch(() => {});
    } catch { /* never let beacon failures break the page */ }
  };

  // Send when the user navigates away or backgrounds the tab.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') send();
  });
  window.addEventListener('pagehide', send, { once: true });
}
