/**
 * Google Ads ↔ SEO Money-Saver
 *
 * For every keyword we rank for organically (data from Search Console),
 * estimate what we'd be paying Google Ads to send that same traffic.
 * The headline number — "£X / mo saved by ranking organically" — turns
 * SEO from a vague cost centre into a measurable revenue protection
 * line item.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, RefreshCw, PoundSterling, Search, TrendingUp, TrendingDown, Calendar,
  Award, ChevronDown, Calculator, Loader2, ArrowUpRight, ArrowDownRight, History,
  FileDown,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { toast } from 'sonner';
import { MetricInfoTooltip } from '../../components/admin/MetricInfoTooltip';

const API = process.env.REACT_APP_BACKEND_URL || '';

const ADS_EXPLAINERS = {
  monthly_savings: {
    title: 'Saved ad spend per month',
    what: 'The estimated £ you\'d be paying Google Ads each month to buy the same traffic SEO is sending you for free. Calculated as Σ (clicks × estimated UK top-of-page CPC) for every keyword you rank for, projected to a 30-day window.',
    why: 'Most owners think of SEO as "free traffic" without putting a price on it. This number lets you compare SEO spend against an Ads-equivalent budget — usually 5-15× cheaper.',
    good: 'Watch the trend. A growing figure month-on-month means SEO is compounding. A shrinking figure with stable Ads-equivalent CPCs is the earliest signal of a ranking drop.',
    example: '450 keywords × avg 2 clicks/month × avg £1.40 CPC = ~£1,260/month of ad spend you\'re NOT paying Google.',
  },
  annual_value: {
    title: 'Annual SEO value',
    what: 'Monthly saved ad spend × 12. The dollar figure that makes the case for renewing or growing the SEO investment.',
    why: 'Most SEO budgets are decided once a year. Walking into that meeting with "SEO saved us £X this year" wins approval faster than ranking screenshots.',
  },
  cpc_estimate: {
    title: 'Estimated CPC',
    what: 'What we\'d expect to pay Google Ads to win one click on this query — based on UK tile/stone vertical bid data, the keyword\'s commercial intent, and any local-city modifier.',
    why: 'Different keywords have wildly different ad-bid economics. "tile shop maidstone" might cost £2.20/click; "how to grout tiles" might cost £0.30. Multiplying by clicks gives the realistic Ads price tag.',
  },
  high_value: {
    title: 'High-value keywords',
    what: 'Keywords where the saved ad spend would be £50+ in this window. The ones worth defending hardest if a ranking dip hits.',
    why: 'Concentrate optimisation effort on these. Losing a £200/month keyword hurts more than losing 100 £2 ones.',
  },
  trend: {
    title: 'Monthly trend',
    what: 'Each bar is one calendar month\'s saved-ad-spend total, captured by an automated nightly snapshot. The number above the latest bar shows the % change vs the previous month.',
    why: 'SEO compounds — every new city landing page adds keywords, and every month\'s ranking improvements stack on top of the last. Tracked over time, this chart turns "SEO is working" from a feeling into a P&L line item you can defend at the next budget meeting.',
    good: 'Steady month-on-month growth (anything green). A red bar two months running is the trigger to investigate (a ranking drop, a Google update, or content that was deleted).',
  },
};

const StatCard = ({ title, value, subtitle, icon: Icon, color, explainerKey }) => (
  <Card className="border-slate-200">
    <CardContent className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide flex items-center">
            <span>{title}</span>
            {explainerKey && <MetricInfoTooltip explainer={ADS_EXPLAINERS[explainerKey]} side="top" align="start" />}
          </p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
          {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
        </div>
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </CardContent>
  </Card>
);

const formatGBP = (n) => `£${(n || 0).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const formatNum = (n) => (n || 0).toLocaleString('en-GB');

const MONTH_LABELS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

const DeltaChip = ({ delta }) => {
  if (delta === null || delta === undefined) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 text-xs font-medium">
        First month — building history
      </span>
    );
  }
  const positive = delta >= 0;
  const Icon = positive ? ArrowUpRight : ArrowDownRight;
  const cls = positive
    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
    : 'bg-red-50 text-red-700 border-red-200';
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-semibold ${cls}`}
      data-testid="ads-savings-delta-chip"
    >
      <Icon className="w-3 h-3" />
      {positive ? '+' : ''}{delta.toFixed(1)}% vs last month
    </span>
  );
};

// Mini bar chart — pure CSS, no new deps. Each bar is a column whose
// height encodes the monthly_value relative to the max in the series.
const TrendBars = ({ history }) => {
  if (!history || history.length === 0) return null;
  const max = Math.max(...history.map((h) => h.totals?.estimated_monthly_value_gbp || 0), 1);
  return (
    <div className="flex items-end gap-2 h-40 pt-4" data-testid="ads-savings-trend-bars">
      {history.map((h, idx) => {
        const v = h.totals?.estimated_monthly_value_gbp || 0;
        const heightPct = (v / max) * 100;
        const delta = h.delta_pct_vs_prev_month;
        const positive = delta == null ? null : delta >= 0;
        const isLast = idx === history.length - 1;
        const monthLabel = `${MONTH_LABELS[(h.month_num || 1) - 1]} ${String(h.year || '').slice(2)}`;
        return (
          <div key={h.month} className="flex-1 flex flex-col items-center min-w-0 group">
            <div className={`text-[10px] font-semibold mb-1 transition-opacity ${isLast || delta != null ? 'opacity-100' : 'opacity-0'}`}>
              {delta == null ? <span className="text-slate-400">—</span> : (
                <span className={positive ? 'text-emerald-600' : 'text-red-600'}>
                  {positive ? '+' : ''}{delta.toFixed(0)}%
                </span>
              )}
            </div>
            <div className="w-full flex items-end h-full">
              <div
                className={`w-full rounded-t transition-all group-hover:opacity-90 ${
                  isLast ? 'bg-gradient-to-t from-emerald-500 to-emerald-400' :
                  positive === false ? 'bg-gradient-to-t from-red-400 to-red-300' :
                  'bg-gradient-to-t from-emerald-400 to-emerald-300'
                }`}
                style={{ height: `${Math.max(heightPct, 4)}%` }}
                title={`${monthLabel}: ${formatGBP(v)}`}
              />
            </div>
            <div className="text-[10px] text-slate-500 mt-1.5 truncate w-full text-center">{monthLabel}</div>
            <div className="text-[10px] font-mono text-slate-700 truncate w-full text-center">{formatGBP(v).replace('.00', '')}</div>
          </div>
        );
      })}
    </div>
  );
};

export default function GoogleAdsSavings() {
  const navigate = useNavigate();
  const [days, setDays] = useState(28);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [history, setHistory] = useState([]);
  const [snapshotting, setSnapshotting] = useState(false);

  const token = useMemo(() => localStorage.getItem('token') || '', []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [oRes, hRes] = await Promise.all([
        fetch(`${API}/api/admin/ads-savings/overview?days=${days}&limit=500`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }),
        fetch(`${API}/api/admin/ads-savings/history?months=12`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }),
      ]);
      const ojson = await oRes.json();
      if (!oRes.ok) throw new Error(ojson.detail || 'Failed to load');
      setData(ojson);
      if (hRes.ok) {
        const hjson = await hRes.json();
        setHistory(hjson.history || []);
      }
    } catch (e) {
      toast.error(e.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [days, token]);

  useEffect(() => { load(); }, [load]);

  const handleSnapshotNow = async () => {
    setSnapshotting(true);
    try {
      const res = await fetch(`${API}/api/admin/ads-savings/snapshot/run-now`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Snapshot failed');
      if (json.skipped) {
        toast.info(`Snapshot skipped: ${json.reason}`);
      } else {
        toast.success(`Snapshot saved for ${json.month}`);
      }
      await load();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSnapshotting(false);
    }
  };

  const handleSendPnlEmail = async () => {
    if (!window.confirm('Send the monthly SEO P&L email to all admins right now? (Force-send — bypasses the once-per-month guard.)')) return;
    try {
      const res = await fetch(`${API}/api/admin/ads-savings/pnl-digest/send-now?force=true`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Send failed');
      if (json.skipped) {
        toast.info(`Skipped: ${json.reason}`);
      } else if (json.ok) {
        toast.success(`Sent to ${json.recipients} admin${json.recipients === 1 ? '' : 's'} — ${json.subject}`);
      }
    } catch (e) {
      toast.error(e.message);
    }
  };

  const handleEmailQuarterlyDeck = async () => {
    if (!window.confirm('Email the quarterly board-deck PDF to all admins right now? (Force-send — attaches a freshly-rendered PDF for the previous quarter.)')) return;
    try {
      const res = await fetch(`${API}/api/admin/ads-savings/quarterly-pdf/email-now?force=true`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Send failed');
      if (json.skipped) {
        toast.info(`Skipped: ${json.reason}`);
      } else if (json.ok) {
        toast.success(`Quarterly PDF emailed to ${json.recipients} admin${json.recipients === 1 ? '' : 's'} — ${json.quarter}`);
      }
    } catch (e) {
      toast.error(e.message);
    }
  };

  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const handleDownloadQuarterlyPdf = async () => {
    setDownloadingPdf(true);
    try {
      const res = await fetch(`${API}/api/admin/ads-savings/quarterly-pdf`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        const txt = await res.text();
        let detail = txt;
        try { detail = JSON.parse(txt).detail || txt; } catch { /* keep raw */ }
        throw new Error(detail || 'PDF download failed');
      }
      const blob = await res.blob();
      const filename = (res.headers.get('Content-Disposition') || '')
        .match(/filename="?([^";]+)"?/)?.[1] || 'tile-station-seo-quarterly.pdf';
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Downloaded ${filename}`);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setDownloadingPdf(false);
    }
  };

  const totals = data?.totals;
  const rows = data?.rows || [];
  const latestSnapshot = history.length > 0 ? history[history.length - 1] : null;
  const monthlyDelta = latestSnapshot?.delta_pct_vs_prev_month;

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-10">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/admin/seo')}
              className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
              data-testid="ads-savings-back-btn"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <div className="bg-emerald-100 p-2 rounded-lg">
                <Calculator className="w-6 h-6 text-emerald-600" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">SEO ↔ Google Ads money-saver</h1>
                <p className="text-sm text-slate-500">
                  What you'd be paying Google Ads if you weren't ranking organically.
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Select value={String(days)} onValueChange={(v) => setDays(parseInt(v, 10))}>
              <SelectTrigger className="w-36" data-testid="ads-savings-days-select">
                <Calendar className="w-4 h-4 mr-2" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7">Last 7 days</SelectItem>
                <SelectItem value="28">Last 28 days</SelectItem>
                <SelectItem value="90">Last 90 days</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={handleSnapshotNow} disabled={snapshotting} data-testid="ads-savings-snapshot-btn">
              <History className={`w-4 h-4 mr-2 ${snapshotting ? 'animate-spin' : ''}`} />
              Snapshot now
            </Button>
            <Button
              variant="outline"
              onClick={handleDownloadQuarterlyPdf}
              disabled={downloadingPdf}
              data-testid="ads-savings-quarterly-pdf-btn"
            >
              <FileDown className={`w-4 h-4 mr-2 ${downloadingPdf ? 'animate-spin' : ''}`} />
              {downloadingPdf ? 'Generating…' : 'Quarterly PDF'}
            </Button>
            <Button variant="outline" onClick={load} disabled={loading} data-testid="ads-savings-refresh-btn">
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6 space-y-6">

        {loading && (
          <div className="text-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-emerald-600 mx-auto" />
            <p className="text-slate-500 mt-2">Calculating saved ad spend…</p>
          </div>
        )}

        {!loading && data && data.connected === false && (
          <Card className="border-amber-200 bg-amber-50">
            <CardContent className="p-6 flex items-start gap-3">
              <Search className="w-5 h-5 text-amber-600 mt-0.5" />
              <div>
                <p className="font-semibold text-amber-900">Connect Google Search Console first</p>
                <p className="text-sm text-amber-800 mt-1">
                  This calculator uses Search Console keyword data to estimate ad-equivalent value.
                  Connect GSC in the SEO Command Centre to start seeing your savings.
                </p>
                <Button
                  className="mt-3 bg-amber-600 hover:bg-amber-700 text-white"
                  onClick={() => navigate('/admin/seo')}
                >
                  Go to SEO Command Centre
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {!loading && data?.connected && (
          <>
            {/* Hero card — the headline number */}
            <Card className="bg-gradient-to-br from-emerald-50 via-white to-blue-50 border-emerald-200">
              <CardContent className="p-8 text-center">
                <p className="text-sm font-semibold uppercase tracking-wider text-emerald-700 inline-flex items-center justify-center">
                  <PoundSterling className="w-4 h-4 mr-1" /> Estimated saved ad spend
                  <MetricInfoTooltip explainer={ADS_EXPLAINERS.monthly_savings} side="top" align="start" />
                </p>
                <p className="text-5xl font-bold text-slate-900 mt-3" data-testid="ads-savings-monthly-headline">
                  {formatGBP(totals?.estimated_monthly_value_gbp)}
                  <span className="text-xl text-slate-500 font-normal"> / month</span>
                </p>
                <div className="mt-3 flex items-center justify-center">
                  <DeltaChip delta={monthlyDelta} />
                </div>
                <p className="text-slate-600 mt-2">
                  That's <span className="font-semibold text-emerald-700">{formatGBP(totals?.estimated_annual_value_gbp)}</span> a year you're not paying Google Ads — because SEO is doing the work.
                </p>
                <p className="text-xs text-slate-500 mt-3">
                  Based on {formatNum(totals?.keywords_ranked)} keywords driving {formatNum(totals?.total_clicks)} organic clicks
                  in the last {totals?.window_days} days.
                </p>
              </CardContent>
            </Card>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard title="Window saved" value={formatGBP(totals?.estimated_window_value_gbp)} subtitle={`Last ${totals?.window_days} days`} icon={PoundSterling} color="bg-emerald-100 text-emerald-600" />
              <StatCard title="Annualised" value={formatGBP(totals?.estimated_annual_value_gbp)} subtitle="If trend holds" icon={TrendingUp} color="bg-blue-100 text-blue-600" explainerKey="annual_value" />
              <StatCard title="Keywords ranking" value={formatNum(totals?.keywords_ranked)} subtitle={`${formatNum(totals?.total_clicks)} clicks`} icon={Search} color="bg-purple-100 text-purple-600" />
              <StatCard title="High-value keywords" value={formatNum(totals?.high_value_keywords)} subtitle="Worth £50+ each" icon={Award} color="bg-amber-100 text-amber-600" explainerKey="high_value" />
            </div>

            {/* Monthly trend — sparkline of saved spend across months */}
            <Card data-testid="ads-savings-trend-card">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-emerald-600" />
                  Monthly trend
                  <MetricInfoTooltip explainer={ADS_EXPLAINERS.trend} side="top" align="start" />
                </CardTitle>
                <CardDescription>
                  {history.length === 0 && 'No snapshots yet. Click "Snapshot now" to capture this month\'s baseline.'}
                  {history.length === 1 && 'Building history. The MoM trend chip activates once we have a second month\'s data.'}
                  {history.length > 1 && `${history.length} months of saved-spend history. Bars show monthly £ value, % above each bar shows change vs the prior month.`}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {history.length === 0 ? (
                  <div className="text-center py-12 text-slate-400 text-sm italic">
                    The nightly scheduler will start filling this in automatically — or click "Snapshot now" above to capture month 1 right now.
                  </div>
                ) : (
                  <TrendBars history={history} />
                )}
                <div className="mt-6 pt-4 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div className="text-xs text-slate-500">
                    📧 Monthly P&amp;L on the 1st · 📄 Quarterly deck on Jan/Apr/Jul/Oct 1st — auto-emailed to all admins.
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleSendPnlEmail}
                      data-testid="ads-savings-send-pnl-btn"
                    >
                      Send P&amp;L email now
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleEmailQuarterlyDeck}
                      data-testid="ads-savings-email-quarterly-deck-btn"
                    >
                      Email quarterly deck now
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Per-keyword table */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  Top earning keywords
                  <MetricInfoTooltip explainer={ADS_EXPLAINERS.cpc_estimate} side="top" align="start" />
                </CardTitle>
                <CardDescription>
                  Sorted by saved ad spend. Defend rankings on these first.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="text-left text-xs text-slate-500 border-b">
                        <th className="pb-3 font-medium">#</th>
                        <th className="pb-3 font-medium">Keyword</th>
                        <th className="pb-3 font-medium text-right">Clicks</th>
                        <th className="pb-3 font-medium text-right">Position</th>
                        <th className="pb-3 font-medium text-right">Est. CPC</th>
                        <th className="pb-3 font-medium text-right">Saved spend</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.slice(0, 50).map((r, idx) => (
                        <tr key={`${r.query}-${idx}`} className="border-b last:border-0 hover:bg-slate-50" data-testid={`ads-savings-row-${idx}`}>
                          <td className="py-3 text-sm text-slate-500">{idx + 1}</td>
                          <td className="py-3">
                            <p className="font-medium text-slate-900 truncate max-w-md">{r.query || '(unknown)'}</p>
                          </td>
                          <td className="py-3 text-right text-sm">{formatNum(r.clicks)}</td>
                          <td className="py-3 text-right text-sm text-slate-600">{r.position || '—'}</td>
                          <td className="py-3 text-right text-sm">{formatGBP(r.estimated_cpc_gbp)}</td>
                          <td className="py-3 text-right font-semibold text-emerald-600">{formatGBP(r.estimated_value_gbp)}</td>
                        </tr>
                      ))}
                      {rows.length === 0 && (
                        <tr>
                          <td colSpan="6" className="py-6 text-center text-sm text-slate-500 italic">
                            No keyword data yet. Once Search Console has indexed traffic, savings will appear here.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                {rows.length > 50 && (
                  <p className="text-xs text-slate-500 mt-3 italic">
                    Showing top 50 of {formatNum(rows.length)} keywords ranked.
                  </p>
                )}
              </CardContent>
            </Card>

            <Card className="bg-slate-50 border-slate-200">
              <CardContent className="p-4 text-xs text-slate-600">
                <p className="font-semibold text-slate-700 mb-1">How is this calculated?</p>
                <p>
                  CPCs are estimated from a UK tile/stone vertical heuristic model (commercial intent + local modifier + product category).
                  When Google Ads API access is enabled, this panel will swap to live Keyword Planner CPCs without changing the layout.
                </p>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
