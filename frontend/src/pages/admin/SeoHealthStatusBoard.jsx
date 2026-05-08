/**
 * SEO Health Status Board
 *
 * Single card on /admin/seo that shows traffic-light status for the
 * four "manual external" lock-in items + autopilot sanity:
 *   - Stripe webhook         (live URL + required events)
 *   - Resend custom domain   (verified for tilestation.co.uk)
 *   - Google Business Profile API (allowlisted + connected)
 *   - Google Ads API token   (real CPCs vs heuristic)
 *
 * Data: GET /api/admin/seo-health/status (parallel checks, ~3s).
 *
 * Dismiss: admin can mark a non-green item as "I've handled this"
 * which suppresses the red/amber banner for 30 days (configurable).
 * Auto-clears early if the live check goes green. Dismissal writes
 * to `seo_health_overrides` server-side — survives page reload.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import {
  CheckCircle2, AlertTriangle, XCircle, Loader2, RefreshCw,
  ExternalLink, Crown, Bot, BellOff,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const tok = () => localStorage.getItem('token') || localStorage.getItem('access_token') || '';

const STATUS_META = {
  green:          { icon: CheckCircle2, color: 'text-emerald-700', bg: 'bg-emerald-50',  border: 'border-emerald-200', label: 'LOCKED' },
  acknowledged:   { icon: BellOff,      color: 'text-slate-600',   bg: 'bg-slate-50',    border: 'border-slate-200',   label: 'ACKNOWLEDGED' },
  amber:          { icon: AlertTriangle, color: 'text-amber-700',  bg: 'bg-amber-50',    border: 'border-amber-200',   label: 'PENDING' },
  red:            { icon: XCircle,       color: 'text-red-700',    bg: 'bg-red-50',      border: 'border-red-200',     label: 'ACTION NEEDED' },
  error:          { icon: XCircle,       color: 'text-red-700',    bg: 'bg-red-50',      border: 'border-red-200',     label: 'ERROR' },
  not_configured: { icon: AlertTriangle, color: 'text-slate-600',  bg: 'bg-slate-50',    border: 'border-slate-200',   label: 'NOT SET' },
};

const ITEMS = [
  {
    key: 'stripe_webhook',
    title: 'Stripe webhook',
    desc: 'Live payment events route to Railway',
    actionLabel: 'Open Stripe webhooks',
    actionUrl: 'https://dashboard.stripe.com/webhooks',
  },
  {
    key: 'resend_domain',
    title: 'Resend custom domain',
    desc: 'tilestation.co.uk verified for branded sender',
    actionLabel: 'Open Resend domains',
    actionUrl: 'https://resend.com/domains',
  },
  {
    key: 'gbp_api',
    title: 'Google Business Profile API',
    desc: 'Reviews, insights & posts in admin',
    actionLabel: 'Apply for API access',
    actionUrl: 'https://support.google.com/business/contact/api_default',
  },
  {
    key: 'ads_api',
    title: 'Google Ads developer token',
    desc: 'Real Keyword Planner CPCs vs heuristic',
    actionLabel: 'Open Google Ads',
    actionUrl: 'https://ads.google.com/aw/signup/landing',
  },
];


const StatusPill = ({ status }) => {
  const meta = STATUS_META[status] || STATUS_META.error;
  const Icon = meta.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${meta.bg} ${meta.color} border ${meta.border}`}
      data-testid={`seo-health-pill-${status}`}
    >
      <Icon className="w-3 h-3" /> {meta.label}
    </span>
  );
};


const HealthRow = ({ item, check, onDismiss, onUndismiss, busyKey }) => {
  const status = check?.status || 'error';
  const meta = STATUS_META[status] || STATUS_META.error;
  const Icon = meta.icon;
  const isOverridden = !!check?.overridden;
  const canDismiss = !isOverridden && status !== 'green' && status !== 'not_configured';
  const expiresAt = check?.override_expires_at;
  return (
    <div
      className={`flex items-start gap-3 p-3 rounded-lg border ${meta.bg} ${meta.border}`}
      data-testid={`seo-health-row-${item.key}`}
    >
      <div className={`mt-0.5 ${meta.color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="font-semibold text-sm text-slate-900">{item.title}</div>
          <StatusPill status={status} />
        </div>
        <div className="text-xs text-slate-600 mt-0.5">{item.desc}</div>
        <div className="text-xs text-slate-700 mt-1.5 font-medium">
          {isOverridden ? (
            <>
              Dismissed{check.override_by ? ` by ${check.override_by}` : ''}
              {expiresAt ? ` · auto-restores ${new Date(expiresAt).toLocaleDateString('en-GB')}` : ''}
              {check.override_reason ? ` — "${check.override_reason}"` : ''}
            </>
          ) : (check?.message || '—')}
        </div>
        {isOverridden && check.live_message && (
          <div className="text-[11px] text-slate-500 mt-1 italic">
            Live check: {check.live_message}
          </div>
        )}
        <div className="mt-2 flex items-center gap-3 flex-wrap">
          {!isOverridden && status !== 'green' && (
            <a
              href={item.actionUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-700 hover:text-indigo-900"
              data-testid={`seo-health-action-${item.key}`}
            >
              {item.actionLabel} <ExternalLink className="w-3 h-3" />
            </a>
          )}
          {canDismiss && (
            <button
              type="button"
              onClick={() => onDismiss(item)}
              disabled={busyKey === item.key}
              className="text-xs font-semibold text-slate-600 hover:text-slate-900 underline"
              data-testid={`seo-health-dismiss-${item.key}`}
              title="Mark this as handled. Banner hides for 30 days; auto-restores if the live check doesn't recover."
            >
              {busyKey === item.key ? 'Dismissing…' : 'Dismiss 30 days'}
            </button>
          )}
          {isOverridden && (
            <button
              type="button"
              onClick={() => onUndismiss(item)}
              disabled={busyKey === item.key}
              className="text-xs font-semibold text-indigo-700 hover:text-indigo-900 underline"
              data-testid={`seo-health-undismiss-${item.key}`}
              title="Restore the live check."
            >
              {busyKey === item.key ? 'Restoring…' : 'Un-dismiss'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};


const SeoHealthStatusBoard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busyKey, setBusyKey] = useState(null);

  const load = async (manual = false) => {
    if (manual) setRefreshing(true);
    try {
      const r = await axios.get(`${API_URL}/api/admin/seo-health/status`, {
        headers: { Authorization: `Bearer ${tok()}` },
        timeout: 15000,
      });
      setData(r.data);
      if (manual) toast.success('Status refreshed');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not load status board');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { load(false); }, []);

  const dismiss = async (item) => {
    const reason = window.prompt(
      `Dismiss "${item.title}"?\n\n`
      + 'The banner will hide for 30 days. Optionally add a short note so '
      + 'future-you remembers why:',
      '',
    );
    if (reason === null) return;
    setBusyKey(item.key);
    try {
      await axios.post(
        `${API_URL}/api/admin/seo-health/${item.key}/dismiss`,
        { reason, days: 30 },
        { headers: { Authorization: `Bearer ${tok()}` } },
      );
      toast.success(`${item.title} dismissed for 30 days`);
      await load(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not dismiss');
    } finally { setBusyKey(null); }
  };

  const undismiss = async (item) => {
    setBusyKey(item.key);
    try {
      await axios.post(
        `${API_URL}/api/admin/seo-health/${item.key}/undismiss`,
        {},
        { headers: { Authorization: `Bearer ${tok()}` } },
      );
      toast.success(`${item.title} — live check restored`);
      await load(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not un-dismiss');
    } finally { setBusyKey(null); }
  };

  if (loading) {
    return (
      <Card className="p-6 flex items-center gap-2 text-slate-500">
        <Loader2 className="w-5 h-5 animate-spin" /> Loading SEO 100% status board…
      </Card>
    );
  }

  const summary = data?.summary || { locked_count: 0, locked_total: 4, percent: 0, all_green: false };
  const checks = data?.checks || {};
  const allGreen = summary.all_green;
  const autopilot = checks.autopilot_jobs || {};
  const lastAction = checks.autopilot_last_action || {};

  return (
    <Card
      className={`overflow-hidden border-2 ${allGreen ? 'border-emerald-300' : 'border-amber-300'}`}
      data-testid="seo-health-status-board"
    >
      {/* Header */}
      <div className={`${allGreen ? 'bg-gradient-to-r from-emerald-600 to-emerald-700' : 'bg-gradient-to-r from-amber-600 to-orange-700'} text-white px-5 py-4`}>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <Crown className="w-6 h-6 text-yellow-200" />
            <div>
              <div className="text-xs uppercase tracking-widest opacity-80 font-semibold">King's-Right-Hand Status</div>
              <div className="text-lg font-bold">
                SEO Lock-in: {summary.locked_count} / {summary.locked_total}
                <span className="ml-2 text-sm font-mono opacity-80">({summary.percent}%)</span>
              </div>
            </div>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => load(true)}
            disabled={refreshing}
            className="bg-white/20 text-white hover:bg-white/30 border-0"
            data-testid="seo-health-refresh-btn"
          >
            {refreshing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            <span className="ml-1 text-xs">Re-check</span>
          </Button>
        </div>
        {/* Progress bar */}
        <div className="mt-3 h-2 rounded-full bg-white/20 overflow-hidden">
          <div
            className="h-full bg-yellow-300 transition-all"
            style={{ width: `${summary.percent}%` }}
            data-testid="seo-health-progress"
          />
        </div>
      </div>

      {/* Body */}
      <div className="p-5 space-y-3">
        {ITEMS.map((it) => (
          <HealthRow
            key={it.key}
            item={it}
            check={checks[it.key]}
            onDismiss={dismiss}
            onUndismiss={undismiss}
            busyKey={busyKey}
          />
        ))}

        {/* Autopilot mini-bar */}
        <div
          className="flex items-start gap-3 p-3 rounded-lg border border-indigo-200 bg-indigo-50"
          data-testid="seo-health-autopilot-row"
        >
          <Bot className="w-5 h-5 text-indigo-700 mt-0.5" />
          <div className="flex-1">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="font-semibold text-sm text-slate-900">SEO Autopilot — running silently</div>
              <StatusPill status={autopilot.status || 'amber'} />
            </div>
            <div className="text-xs text-slate-700 mt-1">
              {autopilot.message || '—'}
              {lastAction?.last_action_at && (
                <> · last action: <span className="font-mono">{new Date(lastAction.last_action_at).toLocaleString('en-GB')}</span></>
              )}
            </div>
            {Array.isArray(autopilot.next_runs) && autopilot.next_runs.length > 0 && (
              <div className="text-[11px] text-slate-500 mt-1.5 space-y-0.5">
                <div className="font-semibold uppercase tracking-wide text-slate-400">Next 3 cron runs</div>
                {autopilot.next_runs.slice(0, 3).map((j) => (
                  <div key={j.id} className="font-mono">
                    · {j.id.replace('seo_autopilot_', '')} → {j.next_run ? new Date(j.next_run).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' }) : '—'}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {allGreen && (
          <div
            className="text-center p-4 bg-emerald-50 rounded-lg border border-emerald-200 text-emerald-800 font-semibold"
            data-testid="seo-health-all-green-banner"
          >
            👑 All four lock-ins are green — King may now watch the kingdom run itself.
          </div>
        )}
      </div>
    </Card>
  );
};

export default SeoHealthStatusBoard;
