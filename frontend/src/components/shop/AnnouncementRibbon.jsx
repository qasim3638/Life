import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const SS_DISMISS_KEY = 'announcement_ribbon_dismissed_v';
// 60 s localStorage cache — internal navigation reuses the response so the
// ribbon paints instantly on the next page (no flash of nothing) and saves
// a network round-trip per click. Stale-while-revalidate: even when fresh
// we still fetch in the background to catch admin updates within ~60 s.
const CACHE_KEY = 'tile_announcement_ribbon_cache';
const CACHE_TTL_MS = 60 * 1000;

const readCache = () => {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.cached_at || !parsed?.data) return null;
    const age = Date.now() - parsed.cached_at;
    return { fresh: age < CACHE_TTL_MS, data: parsed.data };
  } catch { return null; }
};

const writeCache = (data) => {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({ cached_at: Date.now(), data }));
  } catch {/* quota / private mode */}
};

// Module-scoped in-flight promise so React StrictMode's intentional
// double-mount (and rapid client-side navigations) coalesce into a single
// fetch instead of firing two parallel requests.
let _inFlight = null;
const fetchRibbonOnce = async () => {
  if (_inFlight) return _inFlight;
  _inFlight = (async () => {
    try {
      const res = await fetch(`${API_URL}/api/website-admin/public/announcement-ribbon`);
      if (!res.ok) return null;
      return await res.json();
    } finally {
      // Release the lock on next tick so simultaneous mounts coalesce but
      // a later TTL-stale revalidate still fires.
      setTimeout(() => { _inFlight = null; }, 0);
    }
  })();
  return _inFlight;
};

/**
 * Slow-scrolling marquee ribbon pinned above the storefront header.
 * Admin-managed via /admin/announcement-ribbon (single document).
 *
 * Behaviour:
 *  - Renders nothing if disabled, empty, or dismissed for this session+version.
 *  - Animation duration scales with text length so long messages scroll
 *    at a comfortable readable pace regardless of copy.
 *  - Pauses on hover so customers can read the full message.
 *  - Optional CTA link rendered inline; opens in same tab.
 *  - Version field bumps the dismiss key so a fresh announcement
 *    re-appears even if the customer dismissed the previous one.
 */
export default function AnnouncementRibbon() {
  const [config, setConfig] = useState(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let cancelled = false;

    // Stage 1 — paint from cache instantly if available. Even stale entries
    // get rendered (admin marketing copy is rarely time-critical and the
    // background revalidate will correct stale data within ~60 s).
    const cached = readCache();
    if (cached?.data) {
      const data = cached.data;
      if (data.enabled && (data.message || '').trim()) {
        const dismissKey = SS_DISMISS_KEY + (data.version || 1);
        if (sessionStorage.getItem(dismissKey) === '1') setDismissed(true);
        setConfig(data);
      }
    }

    // Stage 2 — always revalidate from network. Skip only if the cache is
    // fresh AND we already painted, to halve traffic during quick repeated
    // navigations within the TTL window.
    const shouldRevalidate = !(cached?.fresh && cached?.data);
    if (!shouldRevalidate) return () => { cancelled = true; };

    (async () => {
      try {
        const data = await fetchRibbonOnce();
        if (data === null) return;
        // Write cache BEFORE the cancelled-check so a fast-clicking customer
        // who unmounts mid-fetch still benefits — the next page paints from
        // the freshly-warmed cache instead of refetching.
        writeCache(data);
        if (cancelled) return;
        if (data?.enabled && (data.message || '').trim()) {
          const dismissKey = SS_DISMISS_KEY + (data.version || 1);
          if (sessionStorage.getItem(dismissKey) === '1') {
            setDismissed(true);
          } else {
            // If the server's version differs from what we previously
            // dismissed, allow it to show again (admin rolled out fresh copy).
            setDismissed(false);
          }
          setConfig(data);
        } else {
          // Admin disabled or schedule expired — clear UI immediately.
          setConfig(null);
        }
      } catch {/* silent — keep cached paint if any */}
    })();

    return () => { cancelled = true; };
  }, []);

  if (!config || dismissed) return null;

  const handleDismiss = () => {
    setDismissed(true);
    try {
      sessionStorage.setItem(SS_DISMISS_KEY + (config.version || 1), '1');
    } catch {/* private mode */}
  };

  // Speed mapping: slower for short text, faster otherwise. Customers complain
  // about marquees that scroll either too fast (can't read) or too slow (annoying).
  // Anchor the duration to character count so cadence stays consistent.
  const speedMultipliers = { slow: 18, medium: 12, fast: 8 }; // seconds per ~50 chars
  const baseSecondsPer50 = speedMultipliers[config.speed] ?? 12;
  const charCount = Math.max(40, (config.message || '').length);
  const duration = Math.max(20, Math.round((charCount / 50) * baseSecondsPer50));

  const bg = config.background_color || '#1C1917';
  const fg = config.text_color || '#F7EA1C';
  const linkColor = config.link_color || '#FFFFFF';

  // Repeat the message a few times in the moving track so the loop feels
  // continuous rather than the typical "gap and reappear" jolt.
  const segment = (
    <span className="inline-flex items-center gap-3 px-12">
      {config.icon !== false && (
        <span aria-hidden="true" className="inline-block">★</span>
      )}
      <span>{config.message}</span>
      {config.link_url && config.link_label && (
        <a
          href={config.link_url}
          className="underline underline-offset-2 font-semibold hover:opacity-90 transition-opacity"
          style={{ color: linkColor }}
          data-testid="announcement-ribbon-link"
        >
          {config.link_label} →
        </a>
      )}
    </span>
  );

  return (
    <div
      className="relative overflow-hidden text-sm font-medium tracking-wide select-none"
      style={{ background: bg, color: fg }}
      data-testid="announcement-ribbon"
      role="region"
      aria-label="Site announcement"
    >
      <style>{`
        @keyframes ribbonScroll {
          from { transform: translateX(0); }
          to { transform: translateX(-50%); }
        }
        .ribbon-track {
          display: inline-flex;
          white-space: nowrap;
          animation: ribbonScroll ${duration}s linear infinite;
        }
        .ribbon-track:hover { animation-play-state: paused; }
        @media (prefers-reduced-motion: reduce) {
          .ribbon-track { animation: none; transform: translateX(0); }
        }
      `}</style>

      <div className="py-2 pr-10">
        <div className="ribbon-track">
          {/* Two copies for the seamless loop. Length anchors at translateX(-50%). */}
          {segment}{segment}{segment}{segment}
        </div>
      </div>

      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss announcement"
        className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1 hover:bg-white/10 transition-colors"
        style={{ color: fg }}
        data-testid="announcement-ribbon-dismiss"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
