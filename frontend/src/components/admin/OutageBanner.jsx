/**
 * OutageBanner — system-wide red bar shown across every admin page
 * when ANY customer-facing endpoint is unhealthy and the alert has
 * not been acknowledged.
 *
 * Polls /api/admin/health/active every 30 seconds. Visually stands
 * out so the admin can't miss it even when buried in other tasks.
 *
 * Snooze: the admin can silence ALL alerts for a set number of hours
 * (default 24) — useful when a root cause is known and being worked
 * on. Banner auto-restores when the snooze window expires.
 */
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { AlertTriangle, X, BellOff, Clock } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const POLL_MS = 30_000;

const tokenHdr = () => {
  const t = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
  return t ? { Authorization: `Bearer ${t}` } : {};
};

const OutageBanner = () => {
  const [alerts, setAlerts] = useState([]);
  const [suppressedUntil, setSuppressedUntil] = useState(null);
  const [acking, setAcking] = useState(false);
  const [snoozing, setSnoozing] = useState(false);
  const [resuming, setResuming] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetchActive = () => {
      axios.get(`${API}/api/admin/health/active`, { headers: tokenHdr() })
        .then((r) => {
          if (cancelled) return;
          setAlerts(r.data?.alerts || []);
          setSuppressedUntil(r.data?.suppressed_until || null);
        })
        .catch(() => {});
    };
    fetchActive();
    const id = setInterval(fetchActive, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // Flash the document title so the admin notices the outage even
  // when they're on a different browser tab. Skipped while snoozed.
  useEffect(() => {
    if (alerts.length === 0 || suppressedUntil) return;
    const orig = document.title;
    let on = false;
    const id = setInterval(() => {
      on = !on;
      document.title = on ? `🚨 PROD OUTAGE — ${alerts.length} alert${alerts.length === 1 ? '' : 's'}` : orig;
    }, 1500);
    return () => { clearInterval(id); document.title = orig; };
  }, [alerts.length, suppressedUntil]);

  const ackAll = async () => {
    setAcking(true);
    try {
      await axios.post(`${API}/api/admin/health/active/ack-all`, {}, { headers: tokenHdr() });
      setAlerts([]);
      toast.success('Alerts acknowledged');
    } catch (_e) { /* leave it red */ }
    finally { setAcking(false); }
  };

  const snooze24h = async () => {
    const reason = window.prompt(
      'Snoozing silences the outage banner for 24 hours.\n\n'
      + 'Optionally type a note so future-you remembers why:',
      '',
    );
    if (reason === null) return;  // user clicked cancel
    setSnoozing(true);
    try {
      const r = await axios.post(
        `${API}/api/admin/health/active/snooze`,
        { hours: 24, reason },
        { headers: tokenHdr() },
      );
      setAlerts([]);
      setSuppressedUntil(r.data?.suppressed_until || null);
      toast.success('Outage alerts snoozed for 24h');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Snooze failed');
    } finally { setSnoozing(false); }
  };

  const resumeAlerts = async () => {
    setResuming(true);
    try {
      await axios.post(`${API}/api/admin/health/active/resume`, {}, { headers: tokenHdr() });
      setSuppressedUntil(null);
      toast.success('Alerts resumed');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Resume failed');
    } finally { setResuming(false); }
  };

  // While snoozed, show a muted amber strip so admin knows they've
  // silenced the alarm on purpose. Click "Resume" to bring it back.
  if (suppressedUntil) {
    const until = new Date(suppressedUntil);
    return (
      <div
        className="w-full bg-amber-100 border-b border-amber-300 text-amber-900 sticky top-14 md:top-16 z-30"
        data-testid="outage-banner-snoozed"
      >
        <div className="max-w-7xl mx-auto px-4 py-2 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2 text-xs font-semibold">
            <BellOff className="w-4 h-4" />
            <span>
              Outage alerts snoozed until <strong>{until.toLocaleString()}</strong>
              {' '}(in {Math.max(0, Math.round((until - new Date()) / 3600000))}h)
            </span>
          </div>
          <button
            onClick={resumeAlerts}
            disabled={resuming}
            className="text-xs font-bold underline hover:text-amber-700 disabled:opacity-50"
            data-testid="outage-banner-resume"
          >
            {resuming ? 'Resuming…' : 'Resume alerts now'}
          </button>
        </div>
      </div>
    );
  }

  if (alerts.length === 0) return null;

  return (
    <div
      className="w-full bg-gradient-to-r from-red-700 via-red-600 to-red-700 text-white shadow-lg border-b-4 border-red-900 animate-pulse-slow sticky top-14 md:top-16 z-30"
      data-testid="outage-banner"
    >
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <AlertTriangle className="w-6 h-6 flex-shrink-0 animate-bounce" />
          <div className="min-w-0">
            <div className="text-xs font-black uppercase tracking-widest leading-none mb-0.5">
              🚨🚨🚨 Production Outage Alert
            </div>
            <div className="text-sm font-bold truncate">
              {alerts.length === 1
                ? `${alerts[0].label} is DOWN — ${alerts[0].last_failure_reason || alerts[0].first_failure_reason}`
                : `${alerts.length} endpoints reporting failures right now`}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Link
            to="/admin/health"
            className="bg-white text-red-700 hover:bg-yellow-300 hover:text-red-800 px-4 py-1.5 rounded-md text-sm font-black transition"
            data-testid="outage-banner-investigate"
          >
            Investigate →
          </Link>
          <button
            onClick={ackAll}
            disabled={acking}
            className="bg-red-900 hover:bg-red-800 text-white px-3 py-1.5 rounded-md text-xs font-bold transition flex items-center gap-1"
            data-testid="outage-banner-ack-all"
          >
            <X className="w-3 h-3" /> {acking ? 'Acking…' : 'Acknowledge'}
          </button>
          <button
            onClick={snooze24h}
            disabled={snoozing}
            className="bg-amber-500 hover:bg-amber-400 text-red-900 px-3 py-1.5 rounded-md text-xs font-bold transition flex items-center gap-1"
            data-testid="outage-banner-snooze"
            title="Mute all outage alerts for 24 hours — useful while you're fixing the root cause."
          >
            <Clock className="w-3 h-3" /> {snoozing ? 'Snoozing…' : 'Snooze 24h'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default OutageBanner;
