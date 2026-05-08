/**
 * Public status page — /status
 *
 * Read-only system health for B2B customers and curious visitors.
 * Built on the same data the internal health monitor produces but
 * stripped of incident IDs, internal traces, and failure reasons.
 *
 * Three sections:
 *   1. Overall status banner (operational / degraded / outage)
 *   2. Per-service status grid
 *   3. Last 7 days uptime %
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { CheckCircle2, AlertTriangle, AlertOctagon, Clock, Mail } from 'lucide-react';
import { ShopHeader, ShopFooter } from './TileStationHome';

const API = process.env.REACT_APP_BACKEND_URL;

const STATUS_META = {
  operational: { label: 'All systems operational', cls: 'bg-emerald-500', icon: CheckCircle2, sub: "Everything is running normally." },
  degraded:    { label: 'Partial system disruption', cls: 'bg-amber-500',  icon: AlertTriangle, sub: 'Some features are temporarily slower or unavailable.' },
  major_outage:{ label: 'Major system outage',       cls: 'bg-red-600',     icon: AlertOctagon, sub: 'Multiple core systems are affected. We are actively investigating.' },
  unknown:     { label: 'Status unavailable',        cls: 'bg-slate-500',   icon: Clock,        sub: 'Status data is loading. Please check again in a moment.' },
};

const SERVICE_STATUS_PILL = {
  operational: 'bg-emerald-100 text-emerald-800',
  degraded: 'bg-amber-100 text-amber-800',
  unknown: 'bg-slate-100 text-slate-600',
};

const fmtTime = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  } catch (_e) { return iso; }
};

const StatusPage = () => {
  const [overall, setOverall] = useState(null);
  const [uptime, setUptime] = useState(null);

  useEffect(() => {
    const load = () => {
      axios.get(`${API}/api/website/status`).then((r) => setOverall(r.data)).catch(() => {});
      axios.get(`${API}/api/website/status/uptime?days=7`).then((r) => setUptime(r.data)).catch(() => {});
    };
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, []);

  const meta = overall ? (STATUS_META[overall.overall] || STATUS_META.unknown) : STATUS_META.unknown;
  const Icon = meta.icon;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col" data-testid="public-status-page">
      <ShopHeader />
      <main className="flex-1 max-w-4xl mx-auto px-4 sm:px-6 py-10 w-full">
        <div className="mb-8">
          <div className="text-xs uppercase tracking-wider text-yellow-600 font-bold mb-1">System Status</div>
          <h1 className="text-3xl sm:text-4xl font-bold text-slate-900">Tile Station — live status</h1>
          <p className="text-slate-600 mt-1 text-sm">
            Real-time view of every system that powers tilestation.co.uk. Auto-refreshes every 30 seconds.
          </p>
        </div>

        {/* Overall banner */}
        <div className={`${meta.cls} text-white rounded-2xl p-5 mb-6 shadow-md`} data-testid="status-overall-banner">
          <div className="flex items-center gap-3">
            <Icon className="w-8 h-8 flex-shrink-0" />
            <div>
              <div className="text-xl sm:text-2xl font-bold leading-tight" data-testid="status-overall-label">{meta.label}</div>
              <div className="text-sm opacity-95 mt-0.5">{meta.sub}</div>
            </div>
          </div>
          {overall?.checked_at && (
            <div className="mt-3 text-[11px] opacity-90 font-mono">Last checked: {fmtTime(overall.checked_at)}</div>
          )}
        </div>

        {/* Per-service grid */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden mb-6">
          <div className="px-5 py-3 border-b border-slate-200 font-bold text-slate-900 flex items-center justify-between">
            <span>Components</span>
            <span className="text-xs font-normal text-slate-500">
              {overall?.services?.length || 0} services monitored
            </span>
          </div>
          {(overall?.services || []).map((s) => (
            <div
              key={s.name}
              className="px-5 py-3 border-b border-slate-100 last:border-b-0 flex items-center justify-between gap-3"
              data-testid={`status-service-${s.name.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <div className="text-sm font-semibold text-slate-800">{s.name}</div>
              <div className="flex items-center gap-3">
                {s.response_ms != null && <span className="text-xs text-slate-500 font-mono">{s.response_ms}ms</span>}
                <span className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wide ${SERVICE_STATUS_PILL[s.status] || SERVICE_STATUS_PILL.unknown}`}>
                  {s.status === 'operational' ? 'Operational' : s.status === 'degraded' ? 'Degraded' : 'Unknown'}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* 7-day uptime */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden mb-6">
          <div className="px-5 py-3 border-b border-slate-200 font-bold text-slate-900 flex items-center justify-between">
            <span>Last 7 days uptime</span>
            <span className="text-xs font-normal text-slate-500">Rolling window</span>
          </div>
          {(uptime?.services || []).map((s) => {
            const pct = s.uptime_percent;
            const noData = pct == null;
            const tone = noData ? 'text-slate-400' : pct >= 99.5 ? 'text-emerald-700' : pct >= 95 ? 'text-amber-600' : 'text-red-600';
            return (
              <div
                key={s.name}
                className="px-5 py-3 border-b border-slate-100 last:border-b-0 flex items-center justify-between gap-3"
                data-testid={`status-uptime-${s.name.toLowerCase().replace(/\s+/g, '-')}`}
              >
                <div className="text-sm font-semibold text-slate-800">{s.name}</div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-500">
                    {s.incidents > 0 ? `${s.incidents} incident${s.incidents === 1 ? '' : 's'}` : 'No incidents'}
                  </span>
                  <span className={`text-sm font-bold tabular-nums ${tone}`}>
                    {noData ? '—' : `${pct.toFixed(2)}%`}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Trade trust block */}
        <div className="bg-slate-900 text-yellow-100 rounded-2xl p-5 text-sm" data-testid="status-trade-block">
          <div className="font-bold text-yellow-300 mb-2 flex items-center gap-1.5">
            <Mail className="w-4 h-4" /> For trade customers
          </div>
          <p className="opacity-90 leading-relaxed">
            We commit to 99.5% uptime on the catalogue and ordering systems. If you experience an issue not reflected here, please email{' '}
            <a href="mailto:trade@tilestation.co.uk" className="underline font-bold">trade@tilestation.co.uk</a> and we'll investigate within 1 hour during business hours.
          </p>
        </div>
      </main>
      <ShopFooter />
    </div>
  );
};

export default StatusPage;
