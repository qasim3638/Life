/**
 * UptimeSparklineWidget — 30-day per-service uptime visualisation for the
 * maintenance dashboard.
 *
 * Each service gets one row:
 *   • Status pill — current vs avg uptime, incident count
 *   • SVG sparkline of last 30 days, one cell per day (red <99%, amber
 *     <99.9%, green ≥99.9%, gray no-data)
 *
 * Mounts on /admin/maintenance just below the existing tasks list.
 *
 * Data source: GET /api/admin/uptime/rollup?days=30
 *   Backed by uptime_probes collection (5-min tick, see services/uptime.py)
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Activity, AlertTriangle, CheckCircle2, Database, Globe, Loader2, MessageSquare, RefreshCw, Server, X } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { MetricInfoTooltip, SEO_EXPLAINERS } from '../../components/admin/MetricInfoTooltip';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const token = () => localStorage.getItem('token') || localStorage.getItem('access_token') || '';

const SERVICE_META = {
  storefront: { label: 'Storefront', icon: Globe },
  backend:    { label: 'Backend API', icon: Server },
  database:   { label: 'MongoDB', icon: Database },
  stripe:     { label: 'Stripe API', icon: Activity },
  telegram:   { label: 'Telegram', icon: MessageSquare },
};

// Cell colour ladder. Tweak in one place if SLA targets change.
const cellColor = (pct) => {
  if (pct == null) return '#e2e8f0';   // slate-200 — no data
  if (pct >= 99.9) return '#10b981';   // emerald-500 — healthy
  if (pct >= 99)   return '#f59e0b';   // amber-500 — degraded
  return '#ef4444';                    // red-500 — outage
};

const formatPct = (p) => (p == null ? '—' : `${p.toFixed(2)}%`);

const Sparkline = ({ days, service, onCellClick }) => {
  const cellW = 8;
  const gap = 2;
  const totalW = days.length * (cellW + gap) - gap;
  const cellH = 22;
  return (
    <svg width={totalW} height={cellH} style={{ display: 'block' }} role="img" aria-label={`30-day uptime for ${service}`}>
      {days.map((d, i) => {
        const pct = d[service];
        // Cells become click-targets when something interesting happened.
        // Healthy cells stay non-interactive so a misclick doesn't open
        // an empty drawer.
        const interactive = pct != null && pct < 100;
        return (
          <rect
            key={d.date}
            x={i * (cellW + gap)}
            y={0}
            width={cellW}
            height={cellH}
            rx={2}
            fill={cellColor(pct)}
            data-date={d.date}
            data-pct={pct}
            style={{ cursor: interactive ? 'pointer' : 'default' }}
            onClick={interactive ? () => onCellClick(d.date, service, pct) : undefined}
          >
            <title>{d.date} — {pct == null ? 'no data' : `${pct.toFixed(3)}%`}{interactive ? ' · click for details' : ''}</title>
          </rect>
        );
      })}
    </svg>
  );
};

const UptimeSparklineWidget = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [probing, setProbing] = useState(false);
  const [error, setError] = useState(null);
  // Drilldown drawer state — closed when null.
  const [drawer, setDrawer] = useState(null);  // { date, service, payload, loading, error }

  const openDrawer = useCallback(async (date, service, pct) => {
    setDrawer({ date, service, pct, loading: true, payload: null, error: null });
    try {
      const res = await axios.get(
        `${API_URL}/api/admin/uptime/day?date=${date}&service=${service}`,
        { headers: { Authorization: `Bearer ${token()}` } },
      );
      setDrawer({ date, service, pct, loading: false, payload: res.data, error: null });
    } catch (e) {
      setDrawer({ date, service, pct, loading: false, payload: null, error: e?.response?.data?.detail || 'Failed to load incidents' });
    }
  }, []);
  const closeDrawer = useCallback(() => setDrawer(null), []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${API_URL}/api/admin/uptime/rollup?days=30`, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      setData(res.data);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Failed to load uptime rollup');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleProbeNow = async () => {
    setProbing(true);
    try {
      await axios.post(`${API_URL}/api/admin/uptime/probe-now`, {}, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      // Slight delay so the new row settles before re-aggregating.
      setTimeout(fetchData, 600);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Probe failed');
    } finally {
      setProbing(false);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden mt-6" data-testid="uptime-sparkline-widget">
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-600" /> 30-day uptime
            <MetricInfoTooltip explainer={SEO_EXPLAINERS.sla_target} />
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Probes every 5 min · 99.9% target · click a cell for the date
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={handleProbeNow}
            disabled={probing}
            className="border-slate-300 text-slate-700 hover:bg-slate-50"
            data-testid="uptime-probe-now-btn"
          >
            {probing ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
            Probe now
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="px-5 py-10 flex items-center justify-center text-slate-500">
          <Loader2 className="w-4 h-4 animate-spin mr-2" /> Loading uptime data…
        </div>
      ) : error ? (
        <div className="px-5 py-6 text-sm text-rose-700 bg-rose-50 border-l-4 border-rose-400">
          {error}
        </div>
      ) : !data || !data.days || data.days.length === 0 ? (
        <div className="px-5 py-10 text-center text-sm text-slate-500">
          No probe data yet. The first row will appear ~5 minutes after backend boot,
          or click <strong>Probe now</strong> to fire a one-off check.
        </div>
      ) : (
        <div className="px-5 py-4 space-y-4">
          {(data.services || []).map((svc) => {
            const meta = SERVICE_META[svc] || { label: svc, icon: Activity };
            const Icon = meta.icon;
            const summary = data.summary?.[svc] || {};
            const allGreen = (summary.incidents || 0) === 0 && summary.data_points > 0;
            return (
              <div key={svc} className="grid grid-cols-12 gap-3 items-center" data-testid={`uptime-row-${svc}`}>
                {/* Service identity + current pct */}
                <div className="col-span-12 md:col-span-3 flex items-center gap-3 min-w-0">
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${allGreen ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-slate-900 truncate">{meta.label}</div>
                    <div className="text-[11px] text-slate-500 inline-flex items-center flex-wrap">
                      <span className="inline-flex items-center">{formatPct(summary.current_pct)} today<MetricInfoTooltip explainer={SEO_EXPLAINERS.uptime_current} /></span>
                      <span className="mx-1">·</span>
                      <span className="inline-flex items-center">avg {formatPct(summary.avg_pct)}<MetricInfoTooltip explainer={SEO_EXPLAINERS.uptime_avg} /></span>
                    </div>
                  </div>
                </div>

                {/* Sparkline */}
                <div className="col-span-12 md:col-span-7 overflow-x-auto">
                  <Sparkline days={data.days} service={svc} onCellClick={openDrawer} />
                </div>

                {/* Incident pill */}
                <div className="col-span-12 md:col-span-2 flex justify-end">
                  {allGreen ? (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                      <CheckCircle2 className="w-3 h-3" /> All good
                    </span>
                  ) : (summary.incidents || 0) > 0 ? (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-100 text-amber-700" data-testid={`uptime-incidents-${svc}`}>
                      <AlertTriangle className="w-3 h-3" /> {summary.incidents} incident{summary.incidents === 1 ? '' : 's'}
                      <MetricInfoTooltip explainer={SEO_EXPLAINERS.uptime_incidents} />
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                      Awaiting data
                    </span>
                  )}
                </div>
              </div>
            );
          })}

          {/* Legend */}
          <div className="flex flex-wrap items-center gap-4 pt-2 border-t border-slate-100 text-[11px] text-slate-500">
            <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ background: '#10b981' }} /> ≥99.9%</span>
            <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ background: '#f59e0b' }} /> 99–99.9%</span>
            <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ background: '#ef4444' }} /> &lt;99%</span>
            <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ background: '#e2e8f0' }} /> No data</span>
            <span className="ml-auto italic">Tip: click any non-green cell to see what failed.</span>
          </div>
        </div>
      )}

      {drawer && <IncidentDrawer drawer={drawer} onClose={closeDrawer} />}
    </div>
  );
};

export default UptimeSparklineWidget;

// ───────────────────────── Incident drawer ─────────────────────────

const fmtTime = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'medium' });
  } catch {
    return iso;
  }
};

const IncidentDrawer = ({ drawer, onClose }) => {
  const { date, service, pct, loading, payload, error } = drawer;
  const meta = SERVICE_META[service] || { label: service, icon: Activity };
  const Icon = meta.icon;

  // Close on Escape — small UX touch but expected from a drawer.
  useEffect(() => {
    const handler = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      data-testid="uptime-incident-drawer"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-xl h-full bg-white shadow-2xl flex flex-col animate-in slide-in-from-right"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-200 flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center flex-shrink-0">
              <Icon className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-semibold text-slate-900">{meta.label} · {date}</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                {pct != null ? `${pct.toFixed(3)}% uptime that day` : 'Day breakdown'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 p-1 -m-1"
            aria-label="Close drawer"
            data-testid="uptime-incident-drawer-close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5">
          {loading ? (
            <div className="flex items-center justify-center py-10 text-slate-500">
              <Loader2 className="w-4 h-4 animate-spin mr-2" /> Loading incidents…
            </div>
          ) : error ? (
            <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3">
              {error}
            </div>
          ) : !payload ? null : (
            <>
              <div className="grid grid-cols-3 gap-3 mb-5">
                <Stat label="Total probes" value={payload.total_probes ?? 0} />
                <Stat label="Failures" value={payload.failed_count ?? 0} accent={payload.failed_count > 0 ? 'rose' : 'emerald'} />
                <Stat
                  label="Success rate"
                  value={
                    payload.total_probes
                      ? `${(((payload.total_probes - payload.failed_count) / payload.total_probes) * 100).toFixed(2)}%`
                      : '—'
                  }
                />
              </div>

              {payload.failed_count === 0 ? (
                <div className="text-center py-10 text-slate-500">
                  <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-500" />
                  <p className="text-sm">No failures recorded for {service} on {date}.</p>
                  <p className="text-xs text-slate-400 mt-1">
                    The aggregated rollup may have rounded down — check adjacent
                    days, or click <strong>Probe now</strong> on the widget to
                    capture a fresh data point.
                  </p>
                </div>
              ) : (
                <div className="border border-slate-200 rounded-xl overflow-hidden" data-testid="uptime-incidents-table">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wider">
                      <tr>
                        <th className="text-left font-semibold px-4 py-2">Time (UTC)</th>
                        <th className="text-right font-semibold px-4 py-2">Latency</th>
                        <th className="text-left font-semibold px-4 py-2">Error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(payload.incidents || []).map((row, i) => (
                        <tr key={`${row.ts}-${i}`} className="border-t border-slate-100 hover:bg-slate-50/50">
                          <td className="px-4 py-2 text-slate-800 tabular-nums whitespace-nowrap">{fmtTime(row.ts)}</td>
                          <td className="px-4 py-2 text-right text-slate-600 tabular-nums">{row.latency_ms ?? '—'} ms</td>
                          <td className="px-4 py-2 text-rose-700 break-all">{row.error || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const Stat = ({ label, value, accent }) => {
  const accentClass = accent === 'rose'
    ? 'text-rose-700 bg-rose-50 border-rose-200'
    : accent === 'emerald'
      ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
      : 'text-slate-700 bg-slate-50 border-slate-200';
  return (
    <div className={`rounded-lg border ${accentClass} px-3 py-2`}>
      <div className="text-[10px] font-semibold uppercase tracking-wider opacity-80">{label}</div>
      <div className="text-lg font-bold tabular-nums">{value}</div>
    </div>
  );
};
