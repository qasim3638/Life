/**
 * StealthAttributionCard
 * ─────────────────────
 * Keyword-level attribution timeline — sits below StealthPerformanceCard.
 *
 * For each tracked stealth keyword (auto-promoted or admin-set), shows:
 *   • added_at + days_live
 *   • clicks / impressions / CTR over the selected window
 *   • 28-day sparkline of daily clicks (inline SVG)
 *   • ROI badge (winner / ok / slow / quiet) based on clicks ÷ median
 *
 * Uses the backend `/attribution/timeline` endpoint which reads the
 * daily cache refreshed at 09:00 BST. Refresh button calls `/rebuild`
 * for on-demand GSC pull.
 *
 * Collapsed by default like the sibling Performance card — the
 * timeline request can be 1-2s on cold cache, don't want to block
 * every /admin/seo page load.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import {
  Loader2, LineChart, RefreshCw, Eye, Trophy, Sparkles, Clock,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const token = () => localStorage.getItem('token') || localStorage.getItem('access_token') || '';
const authHeaders = () => ({ headers: { Authorization: `Bearer ${token()}` } });

const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString());
const pct = (v) => (v == null ? '—' : `${(Number(v) * 100).toFixed(1)}%`);


const StealthAttributionCard = () => {
  const [opened, setOpened] = useState(false);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [scopeFilter, setScopeFilter] = useState('all');
  const [minDaysLive, setMinDaysLive] = useState(0);
  const [days, setDays] = useState(28);

  const load = useCallback(async (force = false) => {
    if (!opened) return;
    setLoading(!report);
    setRefreshing(force);
    try {
      const params = { days, limit: 100 };
      if (scopeFilter !== 'all') params.scope = scopeFilter;
      if (minDaysLive > 0) params.min_days_live = minDaysLive;
      const r = await axios.get(
        `${API_URL}/api/admin/seo/stealth-keywords/attribution/timeline`,
        { ...authHeaders(), params, timeout: 20000 },
      );
      setReport(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not load attribution');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [opened, days, scopeFilter, minDaysLive, report]);

  useEffect(() => { load(false); /* eslint-disable-next-line */ }, [opened, days, scopeFilter, minDaysLive]);

  const rebuild = async () => {
    setRebuilding(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/seo/stealth-keywords/attribution/rebuild?days=${days}`,
        {}, { ...authHeaders(), timeout: 60000 },
      );
      if (r.data.ok) {
        toast.success(`Cache refreshed · ${r.data.rows_pulled} GSC rows · ${r.data.matched_pairs} matches across ${r.data.keywords_with_data} keyword(s)`);
        load(true);
      } else {
        toast.error(`Rebuild failed: ${r.data.reason}`);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Rebuild failed');
    } finally {
      setRebuilding(false);
    }
  };

  if (!opened) {
    return (
      <Card
        className="p-4 bg-gradient-to-br from-violet-50 to-indigo-50 border-violet-200 cursor-pointer hover:border-violet-400 transition"
        onClick={() => setOpened(true)}
        data-testid="stealth-attr-collapsed"
      >
        <div className="flex items-center gap-3">
          <div className="shrink-0 w-10 h-10 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center">
            <LineChart className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <div className="font-semibold text-slate-900">
              Keyword → Click Attribution
            </div>
            <div className="text-xs text-slate-600">
              Click to load · 28-day sparkline + ROI score per keyword. Shows
              which specific stealth keywords are actually driving traffic.
            </div>
          </div>
          <Button size="sm" variant="ghost" className="text-violet-800" data-testid="stealth-attr-open-btn">
            <Eye className="w-4 h-4 mr-1" /> Open
          </Button>
        </div>
      </Card>
    );
  }

  const rows = report?.rows || [];
  const summary = report?.summary || {};

  return (
    <Card className="overflow-hidden" data-testid="stealth-attr-card">
      <div className="bg-gradient-to-br from-slate-900 to-violet-950 text-white px-6 py-5">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-widest text-violet-300 font-semibold flex items-center gap-1.5">
              <LineChart className="w-3 h-3" /> Keyword Attribution Timeline
            </div>
            <h3 className="text-xl font-bold mt-1 flex items-center gap-2">
              <Trophy className="w-5 h-5 text-violet-300" />
              Which keywords are actually earning?
            </h3>
            <p className="text-sm text-violet-200/80 mt-1 max-w-2xl">
              Every tracked stealth keyword with its 28-day sparkline + ROI badge.
              Spot the winners you should double down on · and the quiet ones worth auditing.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={days} onChange={(e) => setDays(parseInt(e.target.value, 10))}
              className="bg-white/10 text-white border border-white/20 rounded text-xs px-2 py-1"
              data-testid="stealth-attr-days"
            >
              {[7, 28, 90].map((d) => <option key={d} value={d} className="text-slate-900">{d}d</option>)}
            </select>
            <Button
              size="sm" variant="ghost" onClick={rebuild} disabled={rebuilding}
              className="text-white hover:bg-white/10"
              data-testid="stealth-attr-rebuild-btn"
            >
              {rebuilding ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Sparkles className="w-4 h-4 mr-1" />}
              Rebuild cache
            </Button>
            <Button
              size="sm" variant="ghost" onClick={() => load(true)} disabled={refreshing}
              className="text-white hover:bg-white/10"
              data-testid="stealth-attr-refresh-btn"
            >
              {refreshing ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <RefreshCw className="w-4 h-4 mr-1" />}
              Refresh
            </Button>
          </div>
        </div>

        {report && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-4 text-xs" data-testid="stealth-attr-summary">
            <MiniStat label="Tracked" value={fmt(summary.tracked_kws)} hint="keywords we know the added_at for" />
            <MiniStat label="With traffic" value={fmt(summary.with_traffic)} hint="kw(s) with ≥1 GSC click this window" highlight />
            <MiniStat label="Winners" value={fmt(summary.winners)} hint="ROI ≥ 1.5×" />
            <MiniStat label="Median clicks/kw" value={fmt(summary.median_kw_clicks)} hint="used as ROI baseline" />
          </div>
        )}
      </div>

      <div className="p-5 space-y-5">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <div className="flex items-center gap-1">
            <span className="text-slate-600">Scope</span>
            <select
              value={scopeFilter} onChange={(e) => setScopeFilter(e.target.value)}
              className="border rounded px-2 py-1 bg-white"
              data-testid="stealth-attr-scope"
            >
              <option value="all">all</option>
              <option value="collection">collection</option>
              <option value="city_page">city page</option>
            </select>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-slate-600">Min days live</span>
            <select
              value={minDaysLive} onChange={(e) => setMinDaysLive(parseInt(e.target.value, 10))}
              className="border rounded px-2 py-1 bg-white"
              data-testid="stealth-attr-min-days"
            >
              <option value={0}>0 (any)</option>
              <option value={7}>≥ 7 days</option>
              <option value={14}>≥ 14 days</option>
              <option value={28}>≥ 28 days</option>
            </select>
          </div>
        </div>

        {loading && !report && (
          <div className="text-center py-8 text-slate-500 text-sm">
            <Loader2 className="w-4 h-4 animate-spin inline mr-1.5" />
            Loading attribution timeline…
          </div>
        )}

        {!loading && report && rows.length === 0 && (
          <div className="rounded-lg border border-violet-200 bg-violet-50 p-4 text-sm text-violet-900 text-center" data-testid="stealth-attr-empty">
            No tracked keywords found yet.
            <div className="text-xs text-violet-700 mt-2">
              Enable <strong>Auto-promote</strong> in the Performance card, or manually set collection-wide keywords — they'll appear here with 28-day sparklines once data arrives.
            </div>
          </div>
        )}

        {!loading && rows.length > 0 && (
          <div className="overflow-x-auto" data-testid="stealth-attr-table-wrap">
            <table className="w-full text-sm">
              <thead className="text-[11px] text-slate-500 uppercase">
                <tr>
                  <th className="text-left py-2 pr-3">Keyword</th>
                  <th className="text-left">Target</th>
                  <th className="text-right">Added</th>
                  <th className="text-right">Clicks</th>
                  <th className="text-right">Impr.</th>
                  <th className="text-right">CTR</th>
                  <th className="text-center">28-day clicks</th>
                  <th className="text-right pr-2">ROI</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-t hover:bg-slate-50" data-testid={`stealth-attr-row-${i}`}>
                    <td className="py-2 pr-3">
                      <span className="font-mono font-semibold text-violet-900">{r.keyword}</span>
                      {r.scope === 'city_page' && (
                        <span className="ml-1.5 text-[9px] bg-emerald-100 text-emerald-800 px-1 py-0.5 rounded uppercase font-semibold tracking-wide">local</span>
                      )}
                    </td>
                    <td className="text-xs text-slate-600 truncate max-w-[200px]">{r.target_label || '—'}</td>
                    <td className="text-right text-xs text-slate-600 whitespace-nowrap">
                      <Clock className="w-3 h-3 inline mr-0.5 text-slate-400" />
                      {r.days_live}d
                    </td>
                    <td className="text-right font-mono font-semibold">{fmt(r.clicks_total)}</td>
                    <td className="text-right font-mono text-slate-600">{fmt(r.impressions_total)}</td>
                    <td className="text-right font-mono text-slate-600">{pct(r.ctr)}</td>
                    <td className="text-center">
                      <Sparkline values={r.spark || []} />
                    </td>
                    <td className="text-right pr-2">
                      <RoiBadge score={r.roi_score} band={r.roi_band} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {report?.generated_at && (
          <div className="text-[10px] text-slate-400 italic">
            generated {new Date(report.generated_at).toLocaleString('en-GB')} · cache refreshes daily at 09:00 BST
          </div>
        )}
      </div>
    </Card>
  );
};


const MiniStat = ({ label, value, hint, highlight }) => (
  <div className={`rounded p-2 border ${highlight ? 'bg-emerald-500/15 border-emerald-300/40' : 'bg-white/10 border-white/20'}`}>
    <div className="text-[10px] uppercase tracking-wide text-violet-200/70">{label}</div>
    <div className="text-lg font-bold font-mono mt-0.5">{value}</div>
    {hint && <div className="text-[10px] text-violet-200/60 mt-0.5">{hint}</div>}
  </div>
);


const Sparkline = ({ values = [], width = 120, height = 30 }) => {
  if (!values.length) return <span className="text-[10px] text-slate-300">—</span>;
  const max = Math.max(1, ...values);
  const stepX = width / Math.max(1, values.length - 1);
  const pts = values.map((v, i) => {
    const x = i * stepX;
    const y = height - (v / max) * (height - 2) - 1;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  // Area fill under the line for readability at small sizes
  const areaPts = `0,${height} ${pts} ${width},${height}`;
  const total = values.reduce((a, b) => a + b, 0);
  const colour = total > 0 ? '#7c3aed' : '#cbd5e1';
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="28-day click sparkline">
      <polygon points={areaPts} fill={colour} opacity="0.15" />
      <polyline points={pts} fill="none" stroke={colour} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      {/* Mark the most recent point */}
      {total > 0 && (
        <circle
          cx={(values.length - 1) * stepX}
          cy={height - (values[values.length - 1] / max) * (height - 2) - 1}
          r="2" fill={colour}
        />
      )}
    </svg>
  );
};


const RoiBadge = ({ score, band }) => {
  const map = {
    winner: { bg: 'bg-emerald-100', text: 'text-emerald-900', border: 'border-emerald-300' },
    ok: { bg: 'bg-sky-100', text: 'text-sky-900', border: 'border-sky-300' },
    slow: { bg: 'bg-amber-100', text: 'text-amber-900', border: 'border-amber-300' },
    quiet: { bg: 'bg-slate-100', text: 'text-slate-700', border: 'border-slate-300' },
  };
  const style = map[band] || map.quiet;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${style.bg} ${style.text} ${style.border}`}>
      {score != null ? `${score.toFixed(2)}×` : '—'}
      <span className="text-[9px] uppercase tracking-wide opacity-70">{band}</span>
    </span>
  );
};


export default StealthAttributionCard;
