/**
 * ConversionFunnelCard — admin home dashboard widget.
 *
 * Pulls the funnel from /api/admin/conversion/funnel and renders:
 *   • 4-stage horizontal bar chart (Sessions → Product views → Checkout → Paid)
 *   • Per-source breakdown (organic / social / direct / etc.) with click-to-checkout %
 *   • Top-line conversion rates with explainers
 *
 * Why no chart library? Pure CSS bars are 1KB, render instantly, and
 * keep the dashboard initial bundle lean. Recharts would be nicer but
 * not worth the 80KB.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { ArrowDown, Loader2, ShoppingBag, ShoppingCart, Target, Users } from 'lucide-react';
import { MetricInfoTooltip, SEO_EXPLAINERS } from '../../components/admin/MetricInfoTooltip';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const token = () => localStorage.getItem('token') || localStorage.getItem('access_token') || '';

const WINDOWS = [
  { label: '7 days', value: 7 },
  { label: '28 days', value: 28 },
  { label: '90 days', value: 90 },
];

const SOURCE_META = {
  organic: { label: 'Organic search', color: 'bg-emerald-500', subtle: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  social:  { label: 'Social',         color: 'bg-violet-500',  subtle: 'bg-violet-50 text-violet-700 border-violet-200' },
  email:   { label: 'Email',          color: 'bg-amber-500',   subtle: 'bg-amber-50 text-amber-700 border-amber-200' },
  direct:  { label: 'Direct',         color: 'bg-blue-500',    subtle: 'bg-blue-50 text-blue-700 border-blue-200' },
  other:   { label: 'Other referrals',color: 'bg-slate-500',   subtle: 'bg-slate-50 text-slate-700 border-slate-200' },
};

const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString());
const fmtPct = (p) => (p == null ? '—' : `${p.toFixed(2)}%`);
const fmtMoney = (n) => (n == null ? '—' : `£${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);

const StageBar = ({ label, value, max, icon: Icon, color, sub, explainer }) => {
  const pct = max ? Math.min(100, Math.max(2, (value / max) * 100)) : 2;
  return (
    <div data-testid={`funnel-stage-${label.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-800">
          <Icon className="w-4 h-4 text-slate-500" />
          <span className="inline-flex items-center">
            {label}
            {explainer ? <MetricInfoTooltip explainer={explainer} /> : null}
          </span>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold text-slate-900 tabular-nums leading-none">{fmt(value)}</div>
          {sub ? <div className="text-[10px] text-slate-500 mt-0.5">{sub}</div> : null}
        </div>
      </div>
      <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
        <div className={`h-full ${color} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
};

const ConversionFunnelCard = () => {
  const [days, setDays] = useState(28);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${API_URL}/api/admin/conversion/funnel?days=${days}`, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      setData(res.data);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Failed to load conversion funnel');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { load(); }, [load]);

  const totals = data?.totals || {};
  const max = totals.sessions || 1;
  const rates = data?.rates || {};

  return (
    <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden" data-testid="conversion-funnel-card">
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <Target className="w-4 h-4 text-blue-600" /> Conversion funnel
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Sessions → Product views → Checkout → Paid orders, sliced by traffic source
          </p>
        </div>
        <div className="flex items-center gap-2">
          {loading && <Loader2 className="w-4 h-4 animate-spin text-slate-400" />}
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="text-xs px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="funnel-window-picker"
          >
            {WINDOWS.map((w) => <option key={w.value} value={w.value}>Last {w.label}</option>)}
          </select>
        </div>
      </div>

      {error ? (
        <div className="px-5 py-4 text-sm text-rose-700 bg-rose-50 border-l-4 border-rose-400">{error}</div>
      ) : !data ? (
        <div className="px-5 py-10 text-center text-sm text-slate-500">
          {loading ? 'Loading…' : 'No funnel data yet.'}
        </div>
      ) : (
        <div className="px-5 py-5 grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Funnel bars */}
          <div className="space-y-4">
            <StageBar
              label="Sessions"
              explainer={SEO_EXPLAINERS.session}
              value={totals.sessions}
              max={max}
              icon={Users}
              color="bg-blue-500"
              sub="Distinct visitors who landed on the site"
            />
            <div className="pl-6 -my-2 text-slate-300"><ArrowDown className="w-3 h-3" /></div>
            <StageBar
              label="Product views"
              explainer={SEO_EXPLAINERS.product_views}
              value={totals.product_viewers}
              max={max}
              icon={ShoppingBag}
              color="bg-violet-500"
              sub={rates.browse_to_product != null ? `${fmtPct(rates.browse_to_product)} of sessions` : 'Reached a /tiles/ or product page'}
            />
            <div className="pl-6 -my-2 text-slate-300"><ArrowDown className="w-3 h-3" /></div>
            <StageBar
              label="Checkout reached"
              explainer={SEO_EXPLAINERS.checkout_reached}
              value={totals.checkout_reached}
              max={max}
              icon={ShoppingCart}
              color="bg-amber-500"
              sub={rates.product_to_checkout != null ? `${fmtPct(rates.product_to_checkout)} of product viewers` : 'Sessions that loaded /checkout'}
            />
            <div className="pl-6 -my-2 text-slate-300"><ArrowDown className="w-3 h-3" /></div>
            <StageBar
              label="Paid orders"
              explainer={SEO_EXPLAINERS.paid_orders}
              value={totals.paid_orders}
              max={max}
              icon={Target}
              color="bg-emerald-500"
              sub={
                <span>
                  {rates.checkout_to_paid != null ? `${fmtPct(rates.checkout_to_paid)} of checkouts` : 'Successful payments'}
                  {totals.revenue_total ? ` · ${fmtMoney(totals.revenue_total)}` : ''}
                </span>
              }
            />
          </div>

          {/* Source breakdown */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3 inline-flex items-center">
              By traffic source
              <MetricInfoTooltip explainer={SEO_EXPLAINERS.traffic_source} />
            </h4>
            {(data.by_source || []).length === 0 ? (
              <div className="text-sm text-slate-500 bg-slate-50 rounded-xl p-4 text-center">
                No traffic in the last {days} days yet. Once Googlebot starts driving sessions, sources will appear here.
              </div>
            ) : (
              <div className="space-y-3">
                {data.by_source.map((src) => {
                  const meta = SOURCE_META[src.source] || SOURCE_META.other;
                  const totalSess = totals.sessions || 1;
                  const sharePct = (src.sessions / totalSess) * 100;
                  return (
                    <div key={src.source} data-testid={`funnel-source-${src.source}`} className="border border-slate-200 rounded-xl p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${meta.color}`} />
                          <span className="text-sm font-semibold text-slate-800">{meta.label}</span>
                        </div>
                        <span className="text-xs text-slate-500">
                          {fmt(src.sessions)} sessions · {sharePct.toFixed(0)}%
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden mb-2">
                        <div className={`h-full ${meta.color}`} style={{ width: `${Math.max(2, sharePct)}%` }} />
                      </div>
                      <div className="flex items-center gap-3 text-[11px] text-slate-500">
                        <span>{fmt(src.product_viewers)} product views</span>
                        <span>·</span>
                        <span>{fmt(src.checkout_reached)} checkouts</span>
                        {src.browse_to_checkout_pct != null && (
                          <>
                            <span>·</span>
                            <span className="font-semibold text-slate-700">
                              {fmtPct(src.browse_to_checkout_pct)} → checkout
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Top-line rates */}
            <div className="mt-5 grid grid-cols-2 gap-2 text-xs">
              <RateChip label="Visitor → product" value={rates.browse_to_product} />
              <RateChip label="Product → checkout" value={rates.product_to_checkout} />
              <RateChip label="Checkout → paid" value={rates.checkout_to_paid} />
              <RateChip label="Visitor → paid" value={rates.session_to_paid} accent explainer={SEO_EXPLAINERS.conversion_rate} />
            </div>
            <p className="text-[10px] text-slate-400 mt-2">
              Rates only shown when the source stage has 5+ events — avoids misleading
              ratios from a single visitor.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

const RateChip = ({ label, value, accent, explainer }) => (
  <div className={`rounded-lg border px-3 py-2 ${accent ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-slate-50 border-slate-200 text-slate-700'}`}>
    <div className="text-[10px] font-semibold uppercase tracking-wider opacity-80 inline-flex items-center">
      {label}
      {explainer ? <MetricInfoTooltip explainer={explainer} /> : null}
    </div>
    <div className="text-base font-bold tabular-nums">{fmtPct(value)}</div>
  </div>
);

export default ConversionFunnelCard;
