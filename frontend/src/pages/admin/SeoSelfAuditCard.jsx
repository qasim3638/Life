/**
 * SeoSelfAuditCard
 * ────────────────
 * One-glance grade (A-F) of every critical SEO subsystem. Top of
 * `/admin/seo`. Click "Run audit now" for a fresh probe (~5-10s),
 * otherwise shows the nightly cached result.
 *
 * Each check is colour-coded (green pass, amber warn, red fail) with
 * a one-line detail + (when present) a concrete fix-hint so the
 * admin doesn't have to interpret the issue — they just follow the
 * hint.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import {
  Loader2, RefreshCw, ShieldCheck, ChevronDown, ChevronUp,
  CheckCircle2, AlertTriangle, XCircle, Zap, ArrowDown, ArrowUp,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const token = () => localStorage.getItem('token') || localStorage.getItem('access_token') || '';

const GRADE_TONE = {
  'A+': { bg: 'from-emerald-700 to-emerald-900', text: 'text-emerald-50' },
  'A':  { bg: 'from-emerald-700 to-emerald-900', text: 'text-emerald-50' },
  'B':  { bg: 'from-blue-700 to-blue-900',       text: 'text-blue-50'    },
  'C':  { bg: 'from-amber-700 to-amber-900',     text: 'text-amber-50'   },
  'D':  { bg: 'from-orange-700 to-orange-900',   text: 'text-orange-50'  },
  'F':  { bg: 'from-rose-700 to-rose-900',       text: 'text-rose-50'    },
  'N/A':{ bg: 'from-slate-600 to-slate-800',     text: 'text-slate-50'   },
};

const STATUS_TONE = {
  pass: 'border-emerald-300 bg-emerald-50',
  warn: 'border-amber-300 bg-amber-50',
  fail: 'border-rose-300 bg-rose-50',
};

const STATUS_ICON = {
  pass: <CheckCircle2 className="w-4 h-4 text-emerald-600" />,
  warn: <AlertTriangle className="w-4 h-4 text-amber-600" />,
  fail: <XCircle className="w-4 h-4 text-rose-600" />,
};

const SeoSelfAuditCard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [trend, setTrend] = useState(null);

  const headers = { headers: { Authorization: `Bearer ${token()}` } };

  const load = useCallback(async () => {
    try {
      const [latest, hist] = await Promise.all([
        axios.get(`${API_URL}/api/admin/seo/stealth-keywords/self-audit/latest`, headers),
        axios.get(`${API_URL}/api/admin/seo/stealth-keywords/self-audit/history?limit=14`, headers),
      ]);
      setData(latest.data);
      setTrend(hist.data?.rows || []);
    } catch {
      // Non-fatal
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { load(); }, [load]);

  const runNow = async () => {
    setRunning(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/seo/stealth-keywords/self-audit/run-now`,
        {}, headers,
      );
      setData(r.data);
      toast.success(`Audit complete · Grade ${r.data.grade} · ${r.data.score}%`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Audit failed');
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-5 flex items-center gap-2 text-slate-500">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading SEO audit…
      </Card>
    );
  }

  const score = data?.score;
  const grade = data?.grade || 'N/A';
  const tone = GRADE_TONE[grade] || GRADE_TONE['N/A'];
  const checks = data?.checks || {};
  const checkArray = Object.entries(checks).map(([k, v]) => ({ key: k, ...v }));
  const fails = checkArray.filter((c) => c.status === 'fail');
  const warns = checkArray.filter((c) => c.status === 'warn');
  const passes = checkArray.filter((c) => c.status === 'pass');

  // Trend indicator: compare last score with the one before it
  let trendChip = null;
  if (trend && trend.length >= 2) {
    const delta = (trend[0]?.score || 0) - (trend[1]?.score || 0);
    if (delta > 0.5) {
      trendChip = (
        <span className="text-emerald-300 text-xs flex items-center gap-1">
          <ArrowUp className="w-3 h-3" /> +{delta.toFixed(1)} vs last
        </span>
      );
    } else if (delta < -0.5) {
      trendChip = (
        <span className="text-rose-300 text-xs flex items-center gap-1">
          <ArrowDown className="w-3 h-3" /> {delta.toFixed(1)} vs last
        </span>
      );
    }
  }

  return (
    <Card className="overflow-hidden border-slate-200 shadow-md" data-testid="seo-self-audit-card">
      <div className={`bg-gradient-to-br ${tone.bg} ${tone.text} px-6 py-5`}>
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div className="min-w-0 flex items-start gap-4">
            <div
              className={`text-6xl font-black font-mono leading-none drop-shadow ${tone.text}`}
              data-testid="seo-audit-grade"
            >
              {grade}
            </div>
            <div className="min-w-0 mt-1">
              <div className="text-[10px] uppercase tracking-widest opacity-80 font-semibold">
                SEO Self-Audit · {data?.site_url?.replace(/^https?:\/\//, '') || 'tilestation'}
              </div>
              <div className="text-3xl font-bold mt-0.5" data-testid="seo-audit-score">
                {score !== null && score !== undefined ? `${score}%` : '—'}
              </div>
              <div className="text-xs opacity-90 mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5">
                {data?.pass_count !== undefined && (
                  <>
                    <span data-testid="seo-audit-pass-count">{passes.length} pass</span>
                    <span data-testid="seo-audit-warn-count">{warns.length} warn</span>
                    <span data-testid="seo-audit-fail-count">{fails.length} fail</span>
                  </>
                )}
                {trendChip}
              </div>
              <div className="text-[10px] opacity-70 mt-1">
                {data?.ran_at ? `Last: ${new Date(data.ran_at).toLocaleString('en-GB')}` : 'Never run'}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {checkArray.length > 0 && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setExpanded((v) => !v)}
                className={`${tone.text} hover:bg-white/10`}
                data-testid="seo-audit-toggle"
              >
                {expanded ? (
                  <><ChevronUp className="w-4 h-4 mr-1" /> Hide details</>
                ) : (
                  <><ChevronDown className="w-4 h-4 mr-1" /> Show {checkArray.length} checks</>
                )}
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              onClick={runNow}
              disabled={running}
              className={`${tone.text} hover:bg-white/10`}
              data-testid="seo-audit-run-now"
            >
              {running ? (
                <><Loader2 className="w-4 h-4 animate-spin mr-1" /> Running…</>
              ) : (
                <><Zap className="w-4 h-4 mr-1" /> Run now</>
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Summary banner — shown when not expanded — surfaces top urgent items */}
      {!expanded && checkArray.length > 0 && (
        <div className="p-4 bg-slate-50 border-b border-slate-200">
          {fails.length > 0 ? (
            <div className="flex items-start gap-2 text-rose-900" data-testid="seo-audit-summary-fails">
              <XCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <div className="text-sm">
                <strong>{fails.length} critical issue{fails.length !== 1 ? 's' : ''}</strong> need
                attention. Click <strong>Show checks</strong> above for the full list with fixes.
              </div>
            </div>
          ) : warns.length > 0 ? (
            <div className="flex items-start gap-2 text-amber-900" data-testid="seo-audit-summary-warns">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <div className="text-sm">
                <strong>All critical checks pass.</strong> {warns.length} minor warning
                {warns.length !== 1 ? 's' : ''} you might want to address.
              </div>
            </div>
          ) : (
            <div className="flex items-start gap-2 text-emerald-900" data-testid="seo-audit-summary-pass">
              <ShieldCheck className="w-4 h-4 mt-0.5 shrink-0" />
              <div className="text-sm">
                <strong>All {passes.length} checks pass.</strong> Production SEO is fully healthy.
              </div>
            </div>
          )}
        </div>
      )}

      {/* Detailed breakdown — collapsed by default */}
      {expanded && (
        <div className="p-4 bg-white space-y-2" data-testid="seo-audit-checks">
          {/* Group by status: fails first, warns next, passes last */}
          {[...fails, ...warns, ...passes].map((c) => (
            <div
              key={c.key}
              className={`rounded-md border-2 p-3 ${STATUS_TONE[c.status] || 'border-slate-200'}`}
              data-testid={`seo-audit-check-${c.key}`}
            >
              <div className="flex items-start gap-2">
                <span className="mt-0.5 shrink-0">{STATUS_ICON[c.status]}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2 flex-wrap">
                    <span className="font-bold text-slate-900">{c.label || c.key}</span>
                    <span className="text-[10px] uppercase tracking-wide font-semibold opacity-60">
                      weight {c.weight}
                    </span>
                  </div>
                  <div className="text-xs text-slate-700 mt-0.5">{c.detail}</div>
                  {c.fix_hint && (
                    <div className="text-xs text-blue-700 mt-1.5 flex items-start gap-1">
                      <span className="font-bold shrink-0">→ Fix:</span>
                      <span>{c.fix_hint}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state when nothing has run yet */}
      {checkArray.length === 0 && (
        <div className="p-6 text-center text-slate-600">
          <p className="text-sm font-semibold">No audit has run yet.</p>
          <p className="text-xs mt-1 mb-3">
            Click <strong>Run now</strong> above to probe all 19 SEO subsystems on production.
            Takes ~10 seconds.
          </p>
          <Button
            size="sm"
            onClick={runNow}
            disabled={running}
            className="bg-slate-900 text-white hover:bg-slate-800"
          >
            {running ? (
              <><Loader2 className="w-4 h-4 animate-spin mr-1" /> Running…</>
            ) : (
              <><Zap className="w-4 h-4 mr-1" /> Run audit now</>
            )}
          </Button>
        </div>
      )}
    </Card>
  );
};

export default SeoSelfAuditCard;
