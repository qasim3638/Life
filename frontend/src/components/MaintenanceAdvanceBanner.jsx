import React, { useState, useEffect } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { useMaintenanceCheck } from '../contexts/MaintenanceContext';

/**
 * Storefront status ribbon. Shows up to 24h before a scheduled maintenance
 * window so customers get a fair warning before placing orders. Dismissible
 * per scheduled_start, so a fresh window re-shows the ribbon to everyone.
 */
const ADVANCE_WINDOW_MS = 24 * 60 * 60 * 1000; // 24h

export default function MaintenanceAdvanceBanner() {
  const { site } = useMaintenanceCheck();
  const [dismissed, setDismissed] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  // Tick every 60s so the relative time stays accurate without re-rendering the
  // whole storefront. Cheap, only when banner is visible.
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);

  const start = site?.scheduled_start ? new Date(site.scheduled_start).getTime() : null;
  const end = site?.scheduled_end ? new Date(site.scheduled_end).getTime() : null;
  const dismissKey = start ? `maintenance-banner-dismissed:${start}` : null;

  // Re-check dismissal whenever the scheduled_start changes (a new schedule
  // means the previous dismissal no longer applies).
  useEffect(() => {
    if (!dismissKey) { setDismissed(false); return; }
    setDismissed(localStorage.getItem(dismissKey) === '1');
  }, [dismissKey]);

  // Don't render if: site already offline (the maintenance page covers it),
  // no schedule, schedule already finished, or more than 24h away.
  if (!start || !end) return null;
  if (site?.enabled) return null;
  if (now >= end) return null;
  if (start - now > ADVANCE_WINDOW_MS) return null;
  if (dismissed) return null;

  const startDate = new Date(start);
  const endDate = new Date(end);

  // Friendly relative phrasing.
  const minsToStart = Math.max(0, Math.round((start - now) / 60_000));
  let when;
  if (minsToStart === 0) {
    when = 'starting now';
  } else if (minsToStart < 60) {
    when = `in ${minsToStart} minute${minsToStart === 1 ? '' : 's'}`;
  } else if (minsToStart < 24 * 60) {
    const hrs = Math.round(minsToStart / 60);
    when = `in about ${hrs} hour${hrs === 1 ? '' : 's'}`;
  } else {
    when = 'tomorrow';
  }

  // Time format: short, includes timezone abbreviation if available.
  const tFmt = { hour: '2-digit', minute: '2-digit' };
  const sameDay = startDate.toDateString() === endDate.toDateString();
  const range = sameDay
    ? `${startDate.toLocaleTimeString([], tFmt)}–${endDate.toLocaleTimeString([], tFmt)}`
    : `${startDate.toLocaleString([], { ...tFmt, day: 'numeric', month: 'short' })} → ${endDate.toLocaleString([], { ...tFmt, day: 'numeric', month: 'short' })}`;

  // Try to grab a tz abbreviation (e.g. "BST", "GMT")
  let tz = '';
  try {
    const parts = new Intl.DateTimeFormat([], { timeZoneName: 'short' }).formatToParts(startDate);
    tz = parts.find(p => p.type === 'timeZoneName')?.value || '';
  } catch { /* ignore */ }

  const handleDismiss = () => {
    if (dismissKey) localStorage.setItem(dismissKey, '1');
    setDismissed(true);
  };

  return (
    <div
      className="w-full bg-amber-500 text-white text-sm relative z-40"
      role="status"
      aria-live="polite"
      data-testid="maintenance-advance-banner"
    >
      <div className="max-w-7xl mx-auto flex items-center justify-center gap-2 px-4 py-2 pr-10">
        <AlertTriangle className="w-4 h-4 shrink-0" />
        <p className="text-center">
          <span className="font-semibold">Heads up:</span>{' '}
          site offline <span className="font-semibold">{range}{tz ? ` ${tz}` : ''}</span> — {when}, for scheduled upgrades.
        </p>
      </div>
      <button
        type="button"
        onClick={handleDismiss}
        className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-amber-600 transition-colors"
        aria-label="Dismiss notice"
        data-testid="maintenance-advance-dismiss"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
