/**
 * Visitor History Panel — embedded in /admin/live-visitors.
 *
 * One row per VISITOR (unique person/device — same `visitor_id` = same row,
 * even across multiple sessions and days). Click a row to expand into all
 * their sessions, click a session to see the per-page journey with dwell
 * times. Currently-live visitors are excluded server-side (they appear
 * separately in the Live visitors panel above). Admin's own /admin/* clicks
 * are also excluded server-side.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import {
  History, RefreshCw, ChevronDown, ChevronUp, Loader2,
  Globe, Clock, Monitor, Smartphone, MapPin, MousePointerClick, Tag,
  ShoppingBag, Repeat,
} from 'lucide-react';
import { Button } from '../ui/button';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const RANGE_OPTIONS = [
  { label: 'Last 24h',  days: 1 },
  { label: 'Last 7d',   days: 7 },
  { label: 'Last 30d',  days: 30 },
  { label: 'Last 90d',  days: 90 },
];

function fmtDuration(s) {
  if (!s || s < 1) return '—';
  if (s >= 1800) return '30m+';
  if (s >= 60) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${s}s`;
}

function timeAgo(iso) {
  if (!iso) return '—';
  const diff = Math.max(0, Date.now() - new Date(iso).getTime());
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`;
}

function pageBadge(url) {
  if (!url) return null;
  const path = url.split('?')[0];
  if (/^\/(shop|tile|product|product-detail)\//.test(path)) {
    return { label: 'PDP', class: 'bg-emerald-100 text-emerald-800 border-emerald-200' };
  }
  if (/^\/checkout|\/basket|\/cart/.test(path)) {
    return { label: 'CHECKOUT', class: 'bg-amber-100 text-amber-800 border-amber-200' };
  }
  if (/^\/(shop\/?$|collections|category|categories|tiles)/.test(path)) {
    return { label: 'BROWSE', class: 'bg-blue-100 text-blue-800 border-blue-200' };
  }
  if (path === '/' || path === '/shop') {
    return { label: 'HOME', class: 'bg-slate-100 text-slate-700 border-slate-200' };
  }
  return null;
}

function SessionDetail({ s }) {
  return (
    <div className="bg-white border border-gray-200 rounded-md px-3 py-2">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="text-[11px] font-semibold text-gray-700 flex items-center gap-1.5">
          {s.is_hot && (
            <span
              className="inline-flex items-center text-[9px] font-bold uppercase px-1 py-0 rounded bg-orange-100 text-orange-700 border border-orange-200"
              title="🔥 This session hit Hot Session status — Telegram alert fired"
            >
              🔥
            </span>
          )}
          {s.page_count} {s.page_count === 1 ? 'page' : 'pages'} · {fmtDuration(s.duration_s)}
        </span>
        <span className="text-[10px] text-gray-400 font-mono">{timeAgo(s.last_seen)}</span>
      </div>
      <ol className="space-y-1">
        {(s.pages || []).map((p, idx) => {
          const badge = pageBadge(p.url);
          return (
            <li key={`${s.session_id}-${idx}`} className="flex items-start gap-2 text-xs">
              <span className="flex-shrink-0 inline-flex items-center justify-center w-4 h-4 rounded-full bg-gray-100 border border-gray-200 text-[9px] font-bold text-gray-500">
                {idx + 1}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1 flex-wrap">
                  {badge && (
                    <span className={`inline-flex items-center text-[8px] font-bold uppercase tracking-wide px-1 py-0 rounded border ${badge.class}`}>
                      {badge.label}
                    </span>
                  )}
                  <code className="font-mono text-[10px] text-gray-700 truncate">{p.url}</code>
                </div>
                {p.title && p.title !== p.url && (
                  <p className="text-[9px] text-gray-500 truncate">{p.title}</p>
                )}
              </div>
              <span
                className="flex-shrink-0 text-[10px] font-mono text-gray-500"
                title={`Time on this page: ${p.dwell_s}s`}
              >
                {idx === (s.pages.length - 1) ? '— last —' : fmtDuration(p.dwell_capped_s)}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function VisitorRow({ v }) {
  const [open, setOpen] = useState(false);
  const DeviceIcon = v.device_type === 'mobile' ? Smartphone : Monitor;
  // Engagement accent colour
  const accent =
    v.total_pdp_views > 0 ? 'from-emerald-500 to-emerald-300'
    : v.total_pages >= 5 ? 'from-indigo-500 to-indigo-300'
    : v.total_pages >= 3 ? 'from-blue-500 to-blue-300'
    : 'from-gray-300 to-gray-200';
  const flag = v.country && v.country !== 'Unknown'
    ? v.country.slice(0, 2).toUpperCase()
    : '??';

  return (
    <div
      className="relative bg-white border border-gray-200 rounded-lg overflow-hidden hover:border-indigo-300 hover:shadow-sm transition-all"
      data-testid={`visitor-history-row-${v.visitor_id}`}
    >
      <div className={`absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b ${accent}`} />

      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full text-left pl-4 pr-3 py-3 hover:bg-gray-50/60 transition-colors flex items-start gap-3"
      >
        <div className="flex-shrink-0 mt-0.5 relative">
          <div className="w-10 h-10 bg-gradient-to-br from-gray-50 to-gray-100 border border-gray-200 rounded-full flex items-center justify-center">
            <DeviceIcon className="w-4 h-4 text-gray-700" />
          </div>
          <span className="absolute -bottom-0.5 -right-0.5 bg-white border border-gray-200 rounded-full px-1 text-[8px] font-bold text-gray-600 leading-tight">
            {flag}
          </span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
            <span className="text-sm font-semibold text-gray-900">
              {v.total_pages} {v.total_pages === 1 ? 'page' : 'pages'}
              <span className="text-gray-300 font-normal mx-1.5">·</span>
              <span className="text-gray-700">{fmtDuration(v.total_dwell_s)}</span>
            </span>
            {v.is_hot && (
              <span
                className="inline-flex items-center gap-1 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 border border-orange-200"
                title="🔥 Hot session — viewed 3+ products and stayed 2+ min. A Telegram alert was sent at the time."
                data-testid={`visitor-history-hot-badge-${v.visitor_id}`}
              >
                🔥 Hot
              </span>
            )}
            {v.is_returning && (
              <span
                className="inline-flex items-center gap-1 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-purple-100 text-purple-800 border border-purple-200"
                title={`This visitor has been here ${v.visit_count} times`}
              >
                <Repeat className="w-3 h-3" />
                Returning · {v.visit_count}×
              </span>
            )}
            {v.total_pdp_views > 0 && (
              <span
                className="inline-flex items-center gap-1 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200"
                title={`${v.total_pdp_views} product detail page(s) viewed across all visits`}
              >
                <ShoppingBag className="w-3 h-3" />
                {v.total_pdp_views} PDP
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-1 text-[11px] text-gray-500">
            <span className="inline-flex items-center gap-1">
              <MapPin className="w-3 h-3" />
              {v.city ? `${v.city}, ` : ''}{v.country}
            </span>
            <span className="inline-flex items-center gap-1" title="Browser">
              {v.browser}
            </span>
            {v.first_referrer && v.first_referrer !== 'Direct' && (
              <span className="inline-flex items-center gap-1 text-blue-700" title="Referrer">
                <Tag className="w-3 h-3" />
                {v.first_referrer.replace(/^https?:\/\//, '').split('/')[0]}
              </span>
            )}
            <span className="inline-flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {timeAgo(v.last_seen)}
            </span>
          </div>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-gray-400 mt-1" /> : <ChevronDown className="w-4 h-4 text-gray-400 mt-1" />}
      </button>

      {open && (
        <div className="pl-4 pr-3 pb-3 pt-1 bg-gray-50 border-t border-gray-100 space-y-2">
          {v.is_returning && (
            <p className="text-[11px] text-purple-700 mb-1">
              <Repeat className="w-3 h-3 inline mr-1" />
              Visited <b>{v.visit_count}</b> separate sessions — most recent first:
            </p>
          )}
          {(v.sessions || []).map((s) => (
            <SessionDetail key={s.session_id} s={s} />
          ))}
          <p className="mt-2 text-[10px] text-gray-400 font-mono">
            Visitor {v.visitor_id} · first seen {v.first_seen ? new Date(v.first_seen).toLocaleString() : '—'}
          </p>
        </div>
      )}
    </div>
  );
}

export default function VisitorHistoryPanel() {
  const [data, setData] = useState({ visitors: [], summary: {} });
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(1);
  const [pdpOnly, setPdpOnly] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/website/visitor-history`, {
        params: { days, limit: 100, pdp_only: pdpOnly },
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      setData(r.data || { visitors: [], summary: {} });
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [days, pdpOnly]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const summary = data.summary || {};
  const visitors = data.visitors || [];

  return (
    <div
      className="bg-white border border-gray-200 rounded-xl overflow-hidden"
      data-testid="visitor-history-panel"
    >
      <div className="px-5 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between gap-2 flex-wrap">
        <button
          type="button"
          onClick={() => setCollapsed(c => !c)}
          className="flex items-center gap-2 hover:opacity-80 transition-opacity"
        >
          <History className="w-4 h-4 text-indigo-500" />
          <h3 className="text-sm font-semibold text-gray-900">Visitor history</h3>
          <span className="inline-flex items-center text-[11px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
            {summary.visitor_count || 0} visitors
          </span>
          {summary.returning_count > 0 && (
            <span
              className="inline-flex items-center text-[11px] font-bold px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200"
              title={`${summary.returning_count} of these visitors have been here more than once`}
            >
              <Repeat className="w-3 h-3 mr-0.5" />
              {summary.returning_count} returning
            </span>
          )}
          {summary.total_pdp_views > 0 && (
            <span
              className="inline-flex items-center text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200"
              title={`Average time on a product page: ${fmtDuration(summary.avg_pdp_dwell_s)}`}
            >
              <MousePointerClick className="w-3 h-3 mr-0.5" />
              avg PDP {fmtDuration(summary.avg_pdp_dwell_s)}
            </span>
          )}
          {collapsed ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronUp className="w-4 h-4 text-gray-400" />}
        </button>
        <div className="flex items-center gap-1 flex-wrap">
          <div className="flex items-center bg-white border border-gray-200 rounded-md p-0.5" data-testid="visitor-history-range">
            {RANGE_OPTIONS.map(opt => (
              <button
                key={opt.days}
                type="button"
                onClick={() => setDays(opt.days)}
                className={`text-[11px] font-medium px-2 py-1 rounded transition-colors ${
                  days === opt.days ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setPdpOnly(p => !p)}
            className={`text-[11px] font-medium px-2 py-1 rounded-md border transition-colors ${
              pdpOnly
                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
            }`}
            data-testid="visitor-history-pdp-only"
            title="Show only visitors who viewed a product detail page"
          >
            {pdpOnly ? '✓ ' : ''}PDP only
          </button>
          <Button
            onClick={fetchData}
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            data-testid="visitor-history-refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {!collapsed && (
        <div data-testid="visitor-history-list">
          {loading && visitors.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-gray-400">
              <Loader2 className="w-4 h-4 animate-spin inline mr-1.5" /> Loading…
            </div>
          ) : visitors.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-gray-500">
              <Globe className="w-5 h-5 text-gray-300 inline mr-1.5" />
              No visitors in the selected period
              {pdpOnly && ' that viewed a product page'}.
            </div>
          ) : (
            <div className="px-3 py-3 space-y-2 bg-gray-50/50">
              {visitors.map((v) => <VisitorRow key={v.visitor_id} v={v} />)}
            </div>
          )}
        </div>
      )}

      <div className="px-4 py-2 bg-gray-50 border-t border-gray-100 text-[10px] text-gray-400">
        One row per visitor (same device/IP groups together). Currently-live visitors appear in the Live panel above and are hidden here. Auto-purged after 90 days.
      </div>
    </div>
  );
}
