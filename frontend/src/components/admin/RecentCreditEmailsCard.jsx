import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Mail, RefreshCw, CheckCircle2, AlertCircle, Send, Loader2, ChevronDown, ChevronUp, ClipboardCopy, Check } from 'lucide-react';
import { Button } from '../ui/button';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Recent Credit-Earned Emails — visibility log + one-click re-send for the
 * "You just earned £X credit at {showroom}" trade re-engagement email.
 *
 * Renders on /admin/sales-hub above the regular hub cards. Reads from
 * `GET /api/invoices/credit-emails/recent` and re-fires via
 * `POST /api/invoices/{id}/credit-emails/resend`.
 */
function relativeTime(iso) {
  if (!iso) return '';
  const ts = new Date(iso).getTime();
  if (!Number.isFinite(ts)) return '';
  const seconds = Math.max(1, Math.floor((Date.now() - ts) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function RecentCreditEmailsCard() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ sent_count: 0, failed_count: 0, total: 0 });
  const [resendingId, setResendingId] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
      const res = await axios.get(`${API_URL}/api/invoices/credit-emails/recent?limit=20`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setRows(res.data?.rows || []);
      setStats({
        sent_count: res.data?.sent_count || 0,
        failed_count: res.data?.failed_count || 0,
        total: res.data?.total || 0,
      });
    } catch (err) {
      toast.error('Could not load credit-email history');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleResend = async (invoiceId, invoiceNo) => {
    if (!window.confirm(`Re-send the credit-earned email for invoice ${invoiceNo}?`)) return;
    try {
      setResendingId(invoiceId);
      const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
      const res = await axios.post(
        `${API_URL}/api/invoices/${invoiceId}/credit-emails/resend`,
        {},
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      if (res.data?.ok) {
        toast.success(`Email re-sent to ${res.data.customer_email}`);
      } else {
        toast.error(`Re-send failed: ${res.data?.error || 'unknown error'}`);
      }
      await load();
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      toast.error(`Re-send failed: ${detail}`);
    } finally {
      setResendingId(null);
    }
  };

  // Copy an itemised plain-text breakdown of a single invoice so admins can
  // paste it into a reply/WhatsApp when a trader queries their statement.
  // Matches the monospace layout used on the EPOS TradeCustomerChip so the
  // two surfaces feel identical.
  const handleCopyBreakdown = async (row) => {
    const breakdown = Array.isArray(row?.trade_credit_breakdown) ? row.trade_credit_breakdown : [];
    if (breakdown.length === 0) return;
    const biz = row.trade_business_name || row.customer_name || 'Trade customer';
    const tRef = row.trade_account_number ? ` (${row.trade_account_number})` : '';
    const header = `Credit-back breakdown — ${biz}${tRef} · ${row.invoice_no || ''}`;
    const separator = '─'.repeat(Math.min(56, header.length + 2));
    const nameCol = 28;
    const calcCol = 18;
    const lines = breakdown.map((r) => {
      const name = (r.product_name || r.sku || 'Unnamed line').toString();
      const rate = Number(r.rate) || 0;
      const net = Number(r.net) || 0;
      const credit = Number(r.credit) || 0;
      const rateTxt = `${rate.toFixed(rate % 1 === 0 ? 0 : 1)}% × £${net.toFixed(2)}`;
      const namePart =
        name.length > nameCol ? `${name.slice(0, nameCol - 1)}…` : name.padEnd(nameCol);
      return `${namePart}  ${rateTxt.padEnd(calcCol)} £${credit.toFixed(2)}`;
    });
    const total = Number(row.trade_credit_earned || 0).toFixed(2);
    const totalLine = `${'Total credit'.padEnd(nameCol)}  ${' '.padEnd(calcCol)} £${total}`;
    const plain = [header, separator, ...lines, separator, totalLine].join('\n');

    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(plain);
      } else {
        const ta = document.createElement('textarea');
        ta.value = plain;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      setCopiedId(row.id);
      toast.success('Breakdown copied — ready to paste', { duration: 2200 });
      setTimeout(() => setCopiedId((cur) => (cur === row.id ? null : cur)), 1800);
    } catch {
      toast.error('Could not copy — please try again');
    }
  };

  if (!loading && rows.length === 0) return null;

  return (
    <div
      className="rounded-lg border border-emerald-200 bg-white shadow-sm"
      data-testid="credit-emails-card"
    >
      <div className="flex items-center justify-between p-4 border-b border-gray-100 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-md bg-emerald-100 flex items-center justify-center">
            <Mail className="w-4 h-4 text-emerald-700" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">Trade Credit Emails — recent dispatches</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {stats.total > 0 ? (
                <>
                  Last {stats.total}:{' '}
                  <span className="text-emerald-700 font-medium">{stats.sent_count} sent</span>
                  {stats.failed_count > 0 && (
                    <>
                      {' · '}
                      <span className="text-rose-700 font-medium">{stats.failed_count} failed</span>
                    </>
                  )}
                </>
              ) : (
                'No emails dispatched yet'
              )}
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={load}
          disabled={loading}
          data-testid="credit-emails-refresh"
        >
          {loading ? (
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
          ) : (
            <RefreshCw className="w-3 h-3 mr-1" />
          )}
          Refresh
        </Button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="text-left py-2 px-4 font-semibold">Invoice</th>
              <th className="text-left py-2 px-4 font-semibold">Trader</th>
              <th className="text-right py-2 px-4 font-semibold">Credit</th>
              <th className="text-left py-2 px-4 font-semibold">Email</th>
              <th className="text-left py-2 px-4 font-semibold">When</th>
              <th className="text-right py-2 px-4 font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const sent = r.credit_email_sent;
              const breakdown = Array.isArray(r.trade_credit_breakdown) ? r.trade_credit_breakdown : [];
              const hasBreakdown = breakdown.length > 0;
              const isExpanded = expandedId === r.id;
              const isCopied = copiedId === r.id;
              return (
                <React.Fragment key={r.id}>
                  <tr
                    className="border-t border-gray-100 hover:bg-gray-50/60"
                    data-testid={`credit-email-row-${r.id}`}
                  >
                    <td className="py-2 px-4 font-mono text-xs text-gray-900">
                      {r.invoice_no}
                    </td>
                    <td className="py-2 px-4">
                      <div className="text-xs">
                        <div className="font-medium text-gray-900">
                          {r.trade_business_name || r.customer_name || '—'}
                        </div>
                        <div className="text-gray-500 truncate max-w-[200px]">
                          {r.customer_email}
                        </div>
                        {r.trade_account_number && (
                          <div className="text-amber-700 font-mono text-[10px] mt-0.5">
                            {r.trade_account_number}
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="py-2 px-4 text-right tabular-nums">
                      <span className="font-semibold text-emerald-700">
                        £{Number(r.trade_credit_earned || 0).toFixed(2)}
                      </span>
                      {r.trade_credit_rate ? (
                        <div className="text-[10px] text-gray-500">
                          @ {Number(r.trade_credit_rate).toFixed(1)}%
                        </div>
                      ) : null}
                      {hasBreakdown && (
                        <button
                          type="button"
                          onClick={() => setExpandedId(isExpanded ? null : r.id)}
                          className="mt-1 inline-flex items-center gap-0.5 text-[10px] font-semibold text-emerald-700 hover:text-emerald-900 hover:underline"
                          data-testid={`credit-email-preview-toggle-${r.id}`}
                          aria-expanded={isExpanded}
                        >
                          {isExpanded ? 'Hide' : 'Preview'}{' '}
                          {isExpanded ? (
                            <ChevronUp className="w-2.5 h-2.5" />
                          ) : (
                            <ChevronDown className="w-2.5 h-2.5" />
                          )}
                        </button>
                      )}
                    </td>
                    <td className="py-2 px-4">
                      {sent ? (
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-1 rounded">
                          <CheckCircle2 className="w-3 h-3" /> Sent
                        </span>
                      ) : (
                        <div>
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-rose-700 bg-rose-50 px-2 py-1 rounded">
                            <AlertCircle className="w-3 h-3" /> Failed
                          </span>
                          {r.credit_email_error && (
                            <div
                              className="text-[10px] text-rose-600/80 mt-1 truncate max-w-[180px]"
                              title={r.credit_email_error}
                            >
                              {r.credit_email_error}
                            </div>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="py-2 px-4 text-xs text-gray-600 whitespace-nowrap">
                      {relativeTime(r.credit_email_at)}
                    </td>
                    <td className="py-2 px-4 text-right">
                      {!sent && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleResend(r.id, r.invoice_no)}
                          disabled={resendingId === r.id}
                          className="text-xs h-7 border-rose-200 text-rose-700 hover:bg-rose-50"
                          data-testid={`credit-email-resend-${r.id}`}
                        >
                          {resendingId === r.id ? (
                            <>
                              <Loader2 className="w-3 h-3 mr-1 animate-spin" /> Sending…
                            </>
                          ) : (
                            <>
                              <Send className="w-3 h-3 mr-1" /> Re-send
                            </>
                          )}
                        </Button>
                      )}
                    </td>
                  </tr>
                  {isExpanded && hasBreakdown && (
                    <tr
                      className="bg-emerald-50/30 border-t border-emerald-100"
                      data-testid={`credit-email-breakdown-${r.id}`}
                    >
                      <td colSpan={6} className="py-3 px-4">
                        <div className="max-w-2xl rounded-md border border-emerald-200 bg-white overflow-hidden">
                          <div className="flex items-center justify-between gap-2 px-3 py-2 bg-emerald-50 border-b border-emerald-100">
                            <div>
                              <p className="text-[11px] font-bold uppercase tracking-wide text-emerald-800">
                                What the trader received
                              </p>
                              <p className="text-[11px] text-emerald-700/80 mt-0.5">
                                Per-product credit breakdown — mirrors the email body sent to {r.customer_email}.
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => handleCopyBreakdown(r)}
                              className={`inline-flex items-center gap-1 text-[10.5px] font-semibold px-2 py-1 rounded border transition-colors ${
                                isCopied
                                  ? 'text-emerald-900 bg-emerald-100 border-emerald-300'
                                  : 'text-emerald-800 bg-white border-emerald-200 hover:bg-emerald-50'
                              }`}
                              data-testid={`credit-email-copy-${r.id}`}
                              title="Copy breakdown as plain text"
                            >
                              {isCopied ? (
                                <>
                                  <Check className="w-3 h-3" />
                                  Copied
                                </>
                              ) : (
                                <>
                                  <ClipboardCopy className="w-3 h-3" />
                                  Copy
                                </>
                              )}
                            </button>
                          </div>
                          <table className="w-full text-[12px]">
                            <tbody>
                              {breakdown.map((b, idx) => {
                                const name = (b.product_name || b.sku || 'Unnamed line').toString();
                                const truncated = name.length > 44 ? `${name.slice(0, 42)}…` : name;
                                const rate = Number(b.rate) || 0;
                                const net = Number(b.net) || 0;
                                const credit = Number(b.credit) || 0;
                                return (
                                  <tr
                                    key={`${b.sku || b.product_id || idx}-${idx}`}
                                    className="border-b border-emerald-50 last:border-b-0"
                                    data-testid={`credit-email-breakdown-row-${r.id}-${idx}`}
                                  >
                                    <td className="px-3 py-1.5 text-gray-900" title={name}>
                                      {truncated}
                                    </td>
                                    <td className="px-3 py-1.5 text-gray-600 tabular-nums whitespace-nowrap text-right">
                                      {rate.toFixed(rate % 1 === 0 ? 0 : 1)}% × £{net.toFixed(2)}
                                    </td>
                                    <td className="px-3 py-1.5 text-right font-semibold text-emerald-800 tabular-nums whitespace-nowrap">
                                      £{credit.toFixed(2)}
                                    </td>
                                  </tr>
                                );
                              })}
                              <tr className="bg-emerald-50">
                                <td className="px-3 py-1.5 font-bold text-emerald-900" colSpan={2}>
                                  Total credit earned
                                </td>
                                <td className="px-3 py-1.5 text-right font-bold text-emerald-900 tabular-nums">
                                  £{Number(r.trade_credit_earned || 0).toFixed(2)}
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
