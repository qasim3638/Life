/**
 * GscSitemapCard — Phase 3 panel showing sitemap submission status
 * with a "Resubmit to Google" button + a single-URL inspector.
 *
 * Lives below GscAnalyticsPanel on /admin/seo. Only mounts when GSC
 * is connected (parent passes connected=true).
 *
 * The sitemap auto-submit hook fires on backend boot + after every
 * successful city-pages drain (throttled 12h). This UI gives an
 * admin a manual fallback + visibility into what Google has fetched.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  AlertTriangle, CheckCircle2, FileSearch, Loader2, Mail,
  RefreshCw, Sparkles, XCircle,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { MetricInfoTooltip, SEO_EXPLAINERS } from '../../components/admin/MetricInfoTooltip';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const token = () => localStorage.getItem('token') || localStorage.getItem('access_token') || '';

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' });
  } catch { return iso; }
}

const verdictAccent = (v) => {
  if (v === 'PASS') return 'text-emerald-700 bg-emerald-50 border-emerald-200';
  if (v === 'PARTIAL') return 'text-amber-700 bg-amber-50 border-amber-200';
  if (v === 'FAIL') return 'text-rose-700 bg-rose-50 border-rose-200';
  return 'text-slate-700 bg-slate-50 border-slate-200';
};

const GscSitemapCard = ({ connected }) => {
  const [sitemaps, setSitemaps] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [inspecting, setInspecting] = useState(false);
  const [inspectUrl, setInspectUrl] = useState('');
  const [inspectResult, setInspectResult] = useState(null);
  const [sendingDigest, setSendingDigest] = useState(false);

  const fetchSitemaps = useCallback(async () => {
    if (!connected) return;
    setLoading(true);
    try {
      const res = await axios.get(`${API_URL}/api/admin/gsc/sitemaps`, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      setSitemaps(res.data?.sitemaps || []);
    } catch (e) {
      // Don't toast on first-load failure — most likely just "no sitemaps yet"
    } finally {
      setLoading(false);
    }
  }, [connected]);

  useEffect(() => { fetchSitemaps(); }, [fetchSitemaps]);

  const handleSubmit = async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      await axios.post(`${API_URL}/api/admin/gsc/sitemaps/submit`, {}, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      toast.success('Sitemap submitted to Google — Googlebot will recrawl shortly');
      // Give Google a moment to process before we reload the list.
      setTimeout(fetchSitemaps, 1500);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to submit sitemap');
    } finally {
      setSubmitting(false);
    }
  };

  const handleInspect = async () => {
    if (!inspectUrl.trim()) {
      toast.error('Enter a URL to inspect');
      return;
    }
    setInspecting(true);
    setInspectResult(null);
    try {
      const res = await axios.get(
        `${API_URL}/api/admin/gsc/inspect?url=${encodeURIComponent(inspectUrl.trim())}`,
        { headers: { Authorization: `Bearer ${token()}` } },
      );
      setInspectResult(res.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Inspection failed');
    } finally {
      setInspecting(false);
    }
  };

  const handleSendDigest = async () => {
    if (sendingDigest) return;
    setSendingDigest(true);
    try {
      const res = await axios.post(
        `${API_URL}/api/admin/gsc/digest/send-now?force=true`, {},
        { headers: { Authorization: `Bearer ${token()}` } },
      );
      const data = res.data || {};
      if (data.skipped) {
        toast.info(`Digest skipped: ${data.reason || 'no data'}`);
      } else if (data.ok && data.recipients) {
        toast.success(`Digest sent to ${data.recipients} admin${data.recipients === 1 ? '' : 's'}`);
      } else {
        toast.error(data.error || 'Digest send failed');
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Digest send failed');
    } finally {
      setSendingDigest(false);
    }
  };

  if (!connected) return null;

  const totalErrors = sitemaps.reduce((sum, s) => sum + (s.errors || 0), 0);
  const totalWarnings = sitemaps.reduce((sum, s) => sum + (s.warnings || 0), 0);

  return (
    <div className="space-y-5" data-testid="gsc-sitemap-card">
      {/* Sitemap section */}
      <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
          <h4 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-blue-600" /> Sitemap submission
            <MetricInfoTooltip explainer={SEO_EXPLAINERS.sitemap} />
          </h4>
          <div className="flex items-center gap-2">
            {loading && <Loader2 className="w-4 h-4 animate-spin text-slate-400" />}
            <Button
              size="sm"
              onClick={handleSubmit}
              disabled={submitting}
              className="bg-blue-600 hover:bg-blue-700 text-white"
              data-testid="gsc-sitemap-submit-btn"
            >
              {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
              {submitting ? 'Submitting…' : 'Resubmit to Google'}
            </Button>
          </div>
        </div>

        {sitemaps.length === 0 ? (
          <div className="px-5 py-6 text-sm text-slate-500 text-center">
            No sitemaps registered with Google yet. Click <strong>Resubmit to Google</strong> above to
            register <code>{(process.env.REACT_APP_PUBLIC_SITE_URL || 'https://tilestation.co.uk').replace(/\/$/, '')}/sitemap.xml</code>.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wider">
                <tr>
                  <th className="text-left font-semibold px-5 py-2.5">Sitemap URL</th>
                  <th className="text-left font-semibold px-5 py-2.5">Last submitted</th>
                  <th className="text-left font-semibold px-5 py-2.5">Last fetched</th>
                  <th className="text-right font-semibold px-5 py-2.5">Errors</th>
                  <th className="text-right font-semibold px-5 py-2.5">Warnings</th>
                  <th className="text-right font-semibold px-5 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody>
                {sitemaps.map((s) => (
                  <tr key={s.path} className="border-t border-slate-100 hover:bg-slate-50/50">
                    <td className="px-5 py-2.5 text-slate-800 truncate max-w-[420px]" title={s.path}>
                      {s.path}
                    </td>
                    <td className="px-5 py-2.5 text-slate-600">{fmtDate(s.last_submitted)}</td>
                    <td className="px-5 py-2.5 text-slate-600">{fmtDate(s.last_downloaded)}</td>
                    <td className={`px-5 py-2.5 text-right tabular-nums ${(s.errors || 0) > 0 ? 'text-rose-700 font-semibold' : 'text-slate-600'}`}>
                      {s.errors || 0}
                    </td>
                    <td className={`px-5 py-2.5 text-right tabular-nums ${(s.warnings || 0) > 0 ? 'text-amber-700 font-semibold' : 'text-slate-600'}`}>
                      {s.warnings || 0}
                    </td>
                    <td className="px-5 py-2.5 text-right">
                      {s.is_pending ? (
                        <span className="inline-flex items-center gap-1 text-[11px] text-amber-700">
                          <Loader2 className="w-3 h-3 animate-spin" /> Pending
                        </span>
                      ) : (s.errors || 0) > 0 ? (
                        <span className="inline-flex items-center gap-1 text-[11px] text-rose-700">
                          <AlertTriangle className="w-3 h-3" /> Errors
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700">
                          <CheckCircle2 className="w-3 h-3" /> OK
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(totalErrors > 0 || totalWarnings > 0) && (
              <div className="px-5 py-2 text-xs text-slate-500 border-t border-slate-100 bg-slate-50">
                {totalErrors} error{totalErrors === 1 ? '' : 's'} · {totalWarnings} warning{totalWarnings === 1 ? '' : 's'} across {sitemaps.length} sitemap{sitemaps.length === 1 ? '' : 's'}
              </div>
            )}
          </div>
        )}
      </div>

      {/* URL Inspection */}
      <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden" data-testid="gsc-url-inspector">
        <div className="px-5 py-3 border-b border-slate-100">
          <h4 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <FileSearch className="w-4 h-4 text-violet-600" /> URL inspector
          </h4>
          <p className="text-xs text-slate-500 mt-0.5">
            Ask Google whether a specific URL is indexed, last crawl time, and any coverage issues. Results cached 6h.
          </p>
        </div>
        <div className="px-5 py-4 space-y-3">
          <div className="flex flex-wrap gap-2">
            <Input
              placeholder="https://tilestation.co.uk/tiles/tile-shop-london"
              value={inspectUrl}
              onChange={(e) => setInspectUrl(e.target.value)}
              className="flex-1 min-w-[280px]"
              data-testid="gsc-inspect-url-input"
              onKeyDown={(e) => e.key === 'Enter' && handleInspect()}
            />
            <Button
              onClick={handleInspect}
              disabled={inspecting}
              className="bg-violet-600 hover:bg-violet-700 text-white"
              data-testid="gsc-inspect-btn"
            >
              {inspecting ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <FileSearch className="w-3.5 h-3.5 mr-1.5" />}
              {inspecting ? 'Inspecting…' : 'Inspect'}
            </Button>
          </div>

          {inspectResult && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2" data-testid="gsc-inspect-result">
              <Field label={<span className="inline-flex items-center">Verdict<MetricInfoTooltip explainer={SEO_EXPLAINERS.url_inspect_verdict} /></span>}>
                <span className={`inline-block px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider rounded-full border ${verdictAccent(inspectResult.verdict)}`}>
                  {inspectResult.verdict || 'unknown'}
                </span>
              </Field>
              <Field label="Coverage state">{inspectResult.coverage_state || '—'}</Field>
              <Field label="Indexing state">{inspectResult.indexing_state || '—'}</Field>
              <Field label="Robots.txt">{inspectResult.robots_txt_state || '—'}</Field>
              <Field label="Page fetch">{inspectResult.page_fetch_state || '—'}</Field>
              <Field label="Mobile usability">{inspectResult.mobile_friendly || '—'}</Field>
              <Field label="Last crawl">{fmtDate(inspectResult.last_crawl_time)}</Field>
              <Field label={<span className="inline-flex items-center">Google canonical<MetricInfoTooltip explainer={SEO_EXPLAINERS.canonical} /></span>}>
                <span className="break-all text-xs text-slate-700">{inspectResult.google_canonical || '—'}</span>
              </Field>
              {inspectResult.user_canonical && inspectResult.user_canonical !== inspectResult.google_canonical && (
                <Field label="Your canonical (mismatch!)">
                  <span className="break-all text-xs text-amber-700">
                    <XCircle className="inline w-3 h-3 mr-1" />
                    {inspectResult.user_canonical}
                  </span>
                </Field>
              )}
              {inspectResult.inspection_link && (
                <div className="md:col-span-2">
                  <a
                    href={inspectResult.inspection_link}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    Open full report in Search Console →
                  </a>
                </div>
              )}
              {inspectResult.from_cache && (
                <div className="md:col-span-2 text-[11px] text-slate-400">
                  Result served from cache (refreshes after 6 hours)
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Weekly digest + alerts mini-card */}
      <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-amber-50 via-white to-white p-5 flex flex-wrap items-center justify-between gap-3" data-testid="gsc-digest-card">
        <div className="flex items-start gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center flex-shrink-0">
            <Mail className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <h4 className="text-sm font-semibold text-slate-900">Daily digest + CTR-drop alerts</h4>
            <p className="text-xs text-slate-600 mt-0.5 max-w-2xl">
              Every day at 09:30 UK time you&apos;ll get an email summarising the last 7 days&apos; clicks,
              impressions, top queries and top pages. Daily at 08:00 a Telegram alert fires
              when any page&apos;s CTR drops 50%+ from baseline.
            </p>
          </div>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={handleSendDigest}
          disabled={sendingDigest}
          className="border-amber-300 text-amber-800 hover:bg-amber-50 flex-shrink-0"
          data-testid="gsc-send-digest-btn"
        >
          {sendingDigest ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Mail className="w-3.5 h-3.5 mr-1.5" />}
          Send test digest now
        </Button>
      </div>
    </div>
  );
};

const Field = ({ label, children }) => (
  <div>
    <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-0.5">
      {label}
    </div>
    <div className="text-sm text-slate-800">{children}</div>
  </div>
);

export default GscSitemapCard;
