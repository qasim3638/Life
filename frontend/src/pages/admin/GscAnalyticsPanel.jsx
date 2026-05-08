/**
 * GscAnalyticsPanel — Phase 2 dashboard for Google Search Console data.
 *
 * Sits below the GscConnectCard on /admin/seo. Pulls four data shapes
 * from the backend (overview, top queries, top pages, city pages) and
 * renders:
 *   1. 4 metric cards — clicks, impressions, CTR, avg position
 *   2. Top queries table (top 25 by clicks)
 *   3. City landing pages performance — every /tiles/ URL with traffic
 *
 * The panel renders nothing until the connect card resolves to
 * `connected: true` (we receive that flag via prop) so it never wastes
 * an API call on a disconnected admin.
 *
 * Empty-state: when GSC has no rows yet (typical for the first 24-48h
 * after a fresh property verification) we show a friendly hourglass
 * card explaining when data will appear.
 */
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import axios from 'axios';
import { ArrowUpRight, BarChart3, Eye, Loader2, MapPin, MousePointerClick, Search, Target } from 'lucide-react';
import { MetricInfoTooltip, SEO_EXPLAINERS } from '../../components/admin/MetricInfoTooltip';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const token = () => localStorage.getItem('token') || localStorage.getItem('access_token') || '';

const WINDOW_OPTIONS = [
  { label: 'Last 7 days', value: 7 },
  { label: 'Last 28 days', value: 28 },
  { label: 'Last 90 days', value: 90 },
];

function formatNumber(n) {
  if (n == null || Number.isNaN(n)) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return Math.round(n).toLocaleString();
}

function formatCtr(ctr) {
  if (ctr == null) return '—';
  return `${(ctr * 100).toFixed(2)}%`;
}

function formatPosition(p) {
  if (!p || p === 0) return '—';
  return p.toFixed(1);
}

const MetricCard = ({ icon: Icon, label, value, sub, accent, testid }) => (
  <div
    className={`rounded-2xl border bg-white p-5 ${accent || 'border-slate-200'}`}
    data-testid={testid}
  >
    <div className="flex items-center justify-between mb-3">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </span>
      <Icon className="w-4 h-4 text-slate-400" />
    </div>
    <div className="text-3xl font-bold text-slate-900 leading-none">{value}</div>
    {sub ? <div className="text-xs text-slate-500 mt-1.5">{sub}</div> : null}
  </div>
);

const EmptyState = ({ days }) => (
  <div
    className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center"
    data-testid="gsc-analytics-empty"
  >
    <div className="text-4xl mb-3">⏳</div>
    <h3 className="text-base font-semibold text-slate-900 mb-1">
      No search data yet
    </h3>
    <p className="text-sm text-slate-600 max-w-md mx-auto">
      Google Search Console has connected successfully but hasn&apos;t reported
      any clicks or impressions for the last {days} days yet. Data
      typically starts appearing <strong>24-48 hours</strong> after a
      property is verified — so this card will come to life automatically
      once Googlebot has crawled and indexed enough of <code>tilestation.co.uk</code>.
    </p>
    <p className="text-xs text-slate-500 mt-3">
      If it&apos;s still empty after 5 days, double-check
      that <code>sitemap.xml</code> is submitted and that the canonical
      meta tags are rendering on every page.
    </p>
  </div>
);

const GscAnalyticsPanel = ({ connected }) => {
  const [days, setDays] = useState(28);
  const [overview, setOverview] = useState(null);
  const [topQueries, setTopQueries] = useState([]);
  const [cityPages, setCityPages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchAll = useCallback(async () => {
    if (!connected) return;
    setLoading(true);
    setError(null);
    try {
      const headers = { Authorization: `Bearer ${token()}` };
      const [ov, tq, cp] = await Promise.all([
        axios.get(`${API_URL}/api/admin/gsc/analytics/overview?days=${days}`, { headers }),
        axios.get(`${API_URL}/api/admin/gsc/analytics/top-queries?days=${days}&limit=25`, { headers }),
        axios.get(`${API_URL}/api/admin/gsc/analytics/city-pages?days=${days}&limit=200`, { headers }),
      ]);
      setOverview(ov.data);
      setTopQueries(tq.data?.rows || []);
      setCityPages(cp.data?.rows || []);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Failed to load Search Console analytics');
    } finally {
      setLoading(false);
    }
  }, [days, connected]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const totals = overview?.totals;
  const hasData = useMemo(
    () => (totals?.impressions || 0) > 0 || (totals?.clicks || 0) > 0,
    [totals],
  );

  if (!connected) return null;

  return (
    <div className="space-y-5" data-testid="gsc-analytics-panel">
      {/* Header + window picker */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-blue-600" />
            Search Console performance
          </h3>
          {overview?.start_date && (
            <p className="text-xs text-slate-500 mt-0.5">
              {overview.start_date} → {overview.end_date}
              {' · '}
              <span className="text-slate-400">data is delayed ~2 days</span>
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="text-xs px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="gsc-window-picker"
          >
            {WINDOW_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          {loading && <Loader2 className="w-4 h-4 animate-spin text-slate-400" />}
        </div>
      </div>

      {error ? (
        <div
          className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"
          data-testid="gsc-analytics-error"
        >
          {error}
        </div>
      ) : null}

      {/* Metric cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          icon={MousePointerClick}
          label="Clicks"
          explainer={SEO_EXPLAINERS.clicks}
          value={formatNumber(totals?.clicks)}
          sub={`${formatCtr(totals?.ctr)} click-through`}
          accent="border-emerald-200"
          testid="gsc-metric-clicks"
        />
        <MetricCard
          icon={Eye}
          label="Impressions"
          explainer={SEO_EXPLAINERS.impressions}
          value={formatNumber(totals?.impressions)}
          sub="times shown in search"
          accent="border-blue-200"
          testid="gsc-metric-impressions"
        />
        <MetricCard
          icon={Target}
          label="Avg position"
          explainer={SEO_EXPLAINERS.avg_position}
          value={formatPosition(totals?.avg_position)}
          sub="lower is better"
          accent="border-amber-200"
          testid="gsc-metric-position"
        />
        <MetricCard
          icon={Search}
          label="Queries tracked"
          explainer={SEO_EXPLAINERS.queries_tracked}
          value={formatNumber(topQueries.length || 0)}
          sub="distinct keywords"
          accent="border-violet-200"
          testid="gsc-metric-queries"
        />
      </div>

      {!hasData && !loading && !error ? (
        <EmptyState days={days} />
      ) : null}

      {hasData ? (
        <>
          {/* Top queries */}
          <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden" data-testid="gsc-top-queries">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
              <h4 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <Search className="w-4 h-4 text-slate-500" /> Top queries
              </h4>
              <span className="text-xs text-slate-500">{topQueries.length} keywords</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wider">
                  <tr>
                    <th className="text-left font-semibold px-5 py-2.5">
                      <span className="inline-flex items-center">Query<MetricInfoTooltip explainer={SEO_EXPLAINERS.query_row} side="bottom" /></span>
                    </th>
                    <th className="text-right font-semibold px-5 py-2.5">
                      <span className="inline-flex items-center">Clicks<MetricInfoTooltip explainer={SEO_EXPLAINERS.clicks} side="bottom" /></span>
                    </th>
                    <th className="text-right font-semibold px-5 py-2.5">
                      <span className="inline-flex items-center">Impr.<MetricInfoTooltip explainer={SEO_EXPLAINERS.impressions} side="bottom" /></span>
                    </th>
                    <th className="text-right font-semibold px-5 py-2.5">
                      <span className="inline-flex items-center">CTR<MetricInfoTooltip explainer={SEO_EXPLAINERS.ctr} side="bottom" /></span>
                    </th>
                    <th className="text-right font-semibold px-5 py-2.5">
                      <span className="inline-flex items-center">Position<MetricInfoTooltip explainer={SEO_EXPLAINERS.position_row} side="bottom" /></span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {topQueries.slice(0, 25).map((row, idx) => (
                    <tr key={`${row.query}-${idx}`} className="border-t border-slate-100 hover:bg-slate-50/50">
                      <td className="px-5 py-2.5 text-slate-800 font-medium">{row.query || '(unknown)'}</td>
                      <td className="px-5 py-2.5 text-right text-slate-900 tabular-nums">{formatNumber(row.clicks)}</td>
                      <td className="px-5 py-2.5 text-right text-slate-600 tabular-nums">{formatNumber(row.impressions)}</td>
                      <td className="px-5 py-2.5 text-right text-slate-600 tabular-nums">{formatCtr(row.ctr)}</td>
                      <td className="px-5 py-2.5 text-right text-slate-600 tabular-nums">{formatPosition(row.position)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* City landing pages */}
          <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden" data-testid="gsc-city-pages">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
              <h4 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-slate-500" /> City landing pages
              </h4>
              <span className="text-xs text-slate-500">
                {cityPages.length} {cityPages.length === 1 ? 'page' : 'pages'} with traffic
              </span>
            </div>
            {cityPages.length === 0 ? (
              <div className="px-5 py-6 text-sm text-slate-500 text-center">
                No /tiles/ URLs reported any clicks or impressions yet.
                Once the AI-generated city pages get crawled they&apos;ll appear here.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wider">
                    <tr>
                      <th className="text-left font-semibold px-5 py-2.5">
                        <span className="inline-flex items-center">URL<MetricInfoTooltip explainer={SEO_EXPLAINERS.page_row} side="bottom" /></span>
                      </th>
                      <th className="text-right font-semibold px-5 py-2.5">
                        <span className="inline-flex items-center">Clicks<MetricInfoTooltip explainer={SEO_EXPLAINERS.clicks} side="bottom" /></span>
                      </th>
                      <th className="text-right font-semibold px-5 py-2.5">
                        <span className="inline-flex items-center">Impr.<MetricInfoTooltip explainer={SEO_EXPLAINERS.impressions} side="bottom" /></span>
                      </th>
                      <th className="text-right font-semibold px-5 py-2.5">
                        <span className="inline-flex items-center">CTR<MetricInfoTooltip explainer={SEO_EXPLAINERS.ctr} side="bottom" /></span>
                      </th>
                      <th className="text-right font-semibold px-5 py-2.5">
                        <span className="inline-flex items-center">Position<MetricInfoTooltip explainer={SEO_EXPLAINERS.position_row} side="bottom" /></span>
                      </th>
                      <th className="px-5 py-2.5"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {cityPages.slice(0, 50).map((row) => (
                      <tr key={row.page} className="border-t border-slate-100 hover:bg-slate-50/50">
                        <td className="px-5 py-2.5 text-slate-800 truncate max-w-[420px]">
                          {(row.page || '').replace(/^https?:\/\/[^/]+/, '')}
                        </td>
                        <td className="px-5 py-2.5 text-right text-slate-900 tabular-nums">{formatNumber(row.clicks)}</td>
                        <td className="px-5 py-2.5 text-right text-slate-600 tabular-nums">{formatNumber(row.impressions)}</td>
                        <td className="px-5 py-2.5 text-right text-slate-600 tabular-nums">{formatCtr(row.ctr)}</td>
                        <td className="px-5 py-2.5 text-right text-slate-600 tabular-nums">{formatPosition(row.position)}</td>
                        <td className="px-5 py-2.5 text-right">
                          <a
                            href={row.page}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
                          >
                            <ArrowUpRight className="w-3 h-3" />
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
};

export default GscAnalyticsPanel;
