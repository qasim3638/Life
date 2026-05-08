import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Loader2, AlertTriangle, CheckCircle2, Clock, XCircle, Phone, Mail, RefreshCw } from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const auth = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } });

const BADGE = {
  recovered: 'bg-emerald-100 text-emerald-900 border-emerald-200',
  pending: 'bg-amber-100 text-amber-900 border-amber-200',
  abandoned: 'bg-rose-100 text-rose-900 border-rose-200',
};

const ICON = {
  recovered: <CheckCircle2 className="w-3.5 h-3.5" />,
  pending: <Clock className="w-3.5 h-3.5" />,
  abandoned: <XCircle className="w-3.5 h-3.5" />,
};

function fmtGBP(n) {
  return `£${Number(n || 0).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('en-GB', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

export default function FailedPayments() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(30);
  const [statusFilter, setStatusFilter] = useState(null);

  const load = async (d = days, s = statusFilter) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ days: String(d) });
      if (s) params.set('status', s);
      const r = await axios.get(`${API_URL}/api/admin/failed-payments?${params}`, auth());
      setData(r.data);
    } catch (e) {
      // Silent — surface in UI via empty state.
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(days, statusFilter); /* eslint-disable-next-line */ }, [days, statusFilter]);

  const t = data?.totals || {};
  const rows = data?.rows || [];
  const topCodes = data?.top_decline_codes || [];

  const empty = !loading && rows.length === 0;
  const totalUnrecovered = useMemo(
    () => Math.max(0, (t.amount || 0) - (t.recovered_amount || 0)),
    [t.amount, t.recovered_amount],
  );

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-5" data-testid="failed-payments-page">
      <header className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2 text-rose-950">
            <AlertTriangle className="w-6 h-6 text-rose-600" /> Failed payments
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Stripe declines + recovery status. Phone the pending ones today — recovery rate is highest within 24 hours.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {[7, 14, 30, 60, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition ${
                days === d
                  ? 'bg-rose-600 text-white border-rose-600'
                  : 'bg-white text-rose-900 border-rose-200 hover:border-rose-400'
              }`}
              data-testid={`failed-window-${d}d`}
            >
              {d}d
            </button>
          ))}
          <Button
            onClick={() => load()}
            variant="ghost"
            size="sm"
            className="ml-1"
            data-testid="failed-refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </header>

      {/* Summary stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="failed-stat-cards">
        <Card className="p-4 bg-rose-50/40 border-rose-200">
          <div className="text-xs text-rose-700 font-semibold">Total declines</div>
          <div className="text-2xl font-bold text-rose-950 mt-1">{t.count || 0}</div>
          <div className="text-xs text-rose-700/70 mt-0.5">{fmtGBP(t.amount)} attempted</div>
        </Card>
        <Card className="p-4 bg-emerald-50/40 border-emerald-200">
          <div className="text-xs text-emerald-700 font-semibold">Recovered</div>
          <div className="text-2xl font-bold text-emerald-950 mt-1">
            {t.recovered_count || 0}
            <span className="text-sm font-normal text-emerald-700 ml-1">
              ({t.recovery_rate_pct || 0}%)
            </span>
          </div>
          <div className="text-xs text-emerald-700/70 mt-0.5">{fmtGBP(t.recovered_amount)} won back</div>
        </Card>
        <Card className="p-4 bg-amber-50/40 border-amber-200">
          <div className="text-xs text-amber-800 font-semibold">Pending recovery</div>
          <div className="text-2xl font-bold text-amber-950 mt-1">{t.pending_count || 0}</div>
          <div className="text-xs text-amber-800/70 mt-0.5">Inside 7-day window</div>
        </Card>
        <Card className="p-4 bg-gray-50 border-gray-200">
          <div className="text-xs text-gray-700 font-semibold">Lost / abandoned</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{t.abandoned_count || 0}</div>
          <div className="text-xs text-gray-600/70 mt-0.5">{fmtGBP(totalUnrecovered)} still outstanding</div>
        </Card>
      </div>

      {/* Top decline codes */}
      {topCodes.length > 0 && (
        <Card className="p-4" data-testid="failed-top-codes">
          <h3 className="text-sm font-semibold text-gray-800 mb-2">Top decline reasons</h3>
          <div className="flex flex-wrap gap-2">
            {topCodes.map(([code, count]) => (
              <span
                key={code}
                className="text-xs px-2.5 py-1 rounded-md bg-rose-50 text-rose-900 border border-rose-200 font-mono"
                title={`${count} declines with code "${code}" in the last ${days} days`}
              >
                {code} <strong className="font-bold">×{count}</strong>
              </span>
            ))}
          </div>
        </Card>
      )}

      {/* Status filter chips */}
      <div className="flex flex-wrap items-center gap-2" data-testid="failed-status-filter">
        <span className="text-xs text-gray-500 mr-1">Filter:</span>
        {[null, 'recovered', 'pending', 'abandoned'].map((s) => (
          <button
            key={String(s)}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition ${
              statusFilter === s
                ? 'bg-gray-900 text-white border-gray-900'
                : 'bg-white text-gray-800 border-gray-200 hover:border-gray-400'
            }`}
            data-testid={`failed-filter-${s || 'all'}`}
          >
            {s ? s.charAt(0).toUpperCase() + s.slice(1) : 'All'}
            {s && ` (${t[`${s}_count`] || 0})`}
          </button>
        ))}
      </div>

      {/* Table */}
      <Card className="p-0 overflow-hidden">
        {loading && (
          <div className="p-10 text-center text-gray-500">
            <Loader2 className="w-5 h-5 animate-spin mx-auto" />
          </div>
        )}
        {empty && !loading && (
          <div className="p-10 text-center text-gray-500" data-testid="failed-empty">
            No failed payments in the last {days} days. 🎉
          </div>
        )}
        {!loading && rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-[11px] uppercase text-gray-500 bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2">Failed at</th>
                  <th className="text-left px-3 py-2">Order</th>
                  <th className="text-left px-3 py-2">Customer</th>
                  <th className="text-left px-3 py-2">Decline</th>
                  <th className="text-right px-3 py-2">Amount</th>
                  <th className="text-center px-3 py-2">Status</th>
                  <th className="text-right px-3 py-2">Reach out</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.id}
                    className="border-t border-gray-100 hover:bg-gray-50/50"
                    data-testid={`failed-row-${r.id}`}
                  >
                    <td className="px-3 py-2 text-gray-700 whitespace-nowrap">{fmtDate(r.payment_failed_at)}</td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-800">{r.order_number || '—'}</td>
                    <td className="px-3 py-2 text-gray-800">
                      <div className="font-medium">{r.customer_name || '—'}</div>
                      <div className="text-xs text-gray-500">{r.customer_email}</div>
                    </td>
                    <td className="px-3 py-2 text-xs text-rose-800 max-w-[220px]">
                      <code className="font-mono text-[11px] bg-rose-50 px-1 rounded">{r.payment_failed_code}</code>
                      <div className="text-rose-700/80 italic mt-0.5 truncate" title={r.payment_failed_reason}>
                        {r.payment_failed_reason}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-gray-900">{fmtGBP(r.total)}</td>
                    <td className="px-3 py-2 text-center">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${BADGE[r.recovery_status]}`}>
                        {ICON[r.recovery_status]} {r.recovery_status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right space-x-1 whitespace-nowrap">
                      {r.customer_phone && (
                        <a
                          href={`tel:${r.customer_phone}`}
                          className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-emerald-100 text-emerald-900 hover:bg-emerald-200"
                          data-testid={`failed-call-${r.id}`}
                        >
                          <Phone className="w-3 h-3" /> Call
                        </a>
                      )}
                      {r.customer_email && (
                        <a
                          href={`mailto:${r.customer_email}?subject=Tile%20Station%20order%20${encodeURIComponent(r.order_number || '')}`}
                          className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-blue-100 text-blue-900 hover:bg-blue-200"
                          data-testid={`failed-email-${r.id}`}
                        >
                          <Mail className="w-3 h-3" /> Email
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
