import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { FileText, Loader2, X, ChevronLeft, ChevronRight, Send } from 'lucide-react';
import { Button } from '../ui/button';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Tiny utility component for the admin Trade Accounts page.
 * Renders a "View statement" button that pops a modal previewing the
 * trader's monthly credit-back statement HTML — exactly what the trader
 * received (or would receive) for that calendar month.
 *
 * Defaults to last full calendar month. Includes ◀▶ arrows so staff can
 * walk back through prior months on a phone-call ("what did I earn in
 * February?"). No-movement months render a friendly empty state.
 */
function getInitialPeriod() {
  const now = new Date();
  const first = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  const prev = new Date(first.getTime() - 24 * 60 * 60 * 1000);
  return { year: prev.getUTCFullYear(), month: prev.getUTCMonth() + 1 };
}

function formatPeriod(year, month) {
  const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  return `${months[month - 1]} ${year}`;
}

export default function CreditStatementPreviewButton({ email, businessName, testIdSuffix = '' }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [period, setPeriod] = useState(getInitialPeriod);
  const [sending, setSending] = useState(false);

  if (!email) return null;

  const load = async (yr, mo) => {
    try {
      setLoading(true);
      setError(null);
      const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
      const res = await axios.get(`${API_URL}/api/admin/trade-credit/statements/preview`, {
        params: { email, year: yr, month: mo },
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setData(res.data);
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      setError(detail);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const openModal = async () => {
    setOpen(true);
    await load(period.year, period.month);
  };

  const shift = (delta) => {
    let { year, month } = period;
    month += delta;
    if (month < 1) { month = 12; year -= 1; }
    if (month > 12) { month = 1; year += 1; }
    setPeriod({ year, month });
    load(year, month);
  };

  const sendNow = async () => {
    if (!data?.has_movement) return;
    if (!window.confirm(`Email this statement now to ${email}?`)) return;
    try {
      setSending(true);
      const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
      const res = await axios.post(
        `${API_URL}/api/admin/trade-credit/statements/send-one`,
        { email, year: period.year, month: period.month },
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      if (res.data?.sent) {
        toast.success(`Statement emailed to ${res.data.customer_email}`);
      } else {
        toast.error('Email dispatch failed');
      }
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      toast.error(`Could not send: ${detail}`);
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={openModal}
        title="Preview the trader's monthly credit-back statement"
        data-testid={`view-statement-btn${testIdSuffix ? '-' + testIdSuffix : ''}`}
        className="text-emerald-700 border-emerald-200 hover:bg-emerald-50"
      >
        <FileText className="h-4 w-4" />
      </Button>

      {open && (
        <div
          className="fixed inset-0 z-[200] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setOpen(false)}
          data-testid="credit-statement-modal"
        >
          <div
            className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <div className="min-w-0">
                <h3 className="font-semibold text-gray-900 text-base truncate">
                  Credit Statement Preview
                </h3>
                <p className="text-xs text-gray-500 mt-0.5 truncate">
                  {businessName || ''} · {email}
                </p>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => shift(-1)}
                  disabled={loading}
                  className="p-2 hover:bg-gray-100 rounded-md disabled:opacity-50"
                  title="Previous month"
                  data-testid="statement-prev-month"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-sm font-medium text-gray-700 min-w-[140px] text-center" data-testid="statement-period">
                  {formatPeriod(period.year, period.month)}
                </span>
                <button
                  type="button"
                  onClick={() => shift(1)}
                  disabled={loading || (period.year === new Date().getUTCFullYear() && period.month === new Date().getUTCMonth() + 1)}
                  className="p-2 hover:bg-gray-100 rounded-md disabled:opacity-50"
                  title="Next month"
                  data-testid="statement-next-month"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="p-2 hover:bg-gray-100 rounded-md ml-2"
                  data-testid="statement-close-btn"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-auto bg-gray-50">
              {loading && (
                <div className="flex items-center justify-center py-24 text-gray-500">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                  Loading statement...
                </div>
              )}
              {!loading && error && (
                <div className="p-8 text-center">
                  <p className="text-rose-700 font-medium">{error}</p>
                </div>
              )}
              {!loading && !error && data && !data.has_movement && (
                <div className="p-12 text-center" data-testid="statement-no-movement">
                  <FileText className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-700 font-medium">No credit movement in {formatPeriod(period.year, period.month)}</p>
                  <p className="text-gray-500 text-sm mt-1">No statement would be sent for this month.</p>
                </div>
              )}
              {!loading && !error && data && data.has_movement && (
                <iframe
                  title="Credit statement preview"
                  className="w-full h-[60vh] bg-white"
                  srcDoc={data.html}
                  data-testid="statement-preview-iframe"
                />
              )}
            </div>

            {/* Footer summary */}
            {data && data.has_movement && data.summary && (
              <div className="px-5 py-3 border-t bg-white text-xs text-gray-600 flex flex-wrap gap-4 items-center justify-between" data-testid="statement-summary">
                <div className="flex flex-wrap gap-4 items-center">
                  <span>📅 {data.period_label}</span>
                  <span>+ <strong className="text-emerald-700">£{Number(data.summary.earned_total).toFixed(2)}</strong> earned</span>
                  <span>– <strong className="text-rose-700">£{Number(data.summary.redeemed_total).toFixed(2)}</strong> redeemed</span>
                  <span><strong className="text-gray-900">£{Number(data.summary.closing_balance).toFixed(2)}</strong> closing balance</span>
                  <span className="text-gray-400">· {data.summary.txns_count} transactions</span>
                </div>
                <Button
                  size="sm"
                  onClick={sendNow}
                  disabled={sending || loading}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  data-testid="statement-send-now-btn"
                >
                  {sending ? (
                    <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Sending…</>
                  ) : (
                    <><Send className="w-3.5 h-3.5 mr-1.5" /> Send to trader now</>
                  )}
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
