import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Mail, Eye, X, Send, Check, AlertCircle, Tag, Inbox, RefreshCw,
} from 'lucide-react';
import { Button } from '../../components/ui/button';

const API = process.env.REACT_APP_BACKEND_URL;

const tokenHdr = () => {
  const t = localStorage.getItem('admin_token') || localStorage.getItem('token');
  return t ? { Authorization: `Bearer ${t}` } : {};
};

const tierBadge = (sampleType, priceGbp) => {
  if (priceGbp > 0) {
    return (
      <span className="inline-block bg-amber-100 text-amber-800 text-[10px] font-bold px-1.5 py-0.5 rounded uppercase">
        Full Size £{priceGbp.toFixed(2)}
      </span>
    );
  }
  return (
    <span className="inline-block bg-emerald-100 text-emerald-800 text-[10px] font-medium px-1.5 py-0.5 rounded uppercase">
      Free
    </span>
  );
};

/**
 * Sample Followups — manual review screen.
 *
 * Lists every sample order delivered 4-14 days ago that hasn't yet
 * been followed up. The owner picks each row, optionally toggles "send
 * with £5 discount per Full Size sample", then clicks Send. No daily
 * cron auto-emails — this is fully manual.
 */
const SampleFollowupsPage = () => {
  const [actionable, setActionable] = useState([]);
  const [skipped, setSkipped] = useState([]);
  const [voucherPerFullSize, setVoucherPerFullSize] = useState(5);
  const [loading, setLoading] = useState(true);
  const [previewOrder, setPreviewOrder] = useState(null);
  const [previewIncludeVoucher, setPreviewIncludeVoucher] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [sending, setSending] = useState(false);

  // Sent history (read-only audit trail)
  const [recentSent, setRecentSent] = useState([]);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [pendingRes, sentRes] = await Promise.all([
        axios.get(`${API}/api/admin/sample-followups/pending`, { headers: tokenHdr() }),
        axios.get(`${API}/api/admin/sample-followups/sent?days=30`, { headers: tokenHdr() }),
      ]);
      setActionable(pendingRes.data?.actionable || []);
      setSkipped(pendingRes.data?.skipped || []);
      setVoucherPerFullSize(pendingRes.data?.voucher_per_full_size_gbp || 5);
      setRecentSent(sentRes.data?.rows || []);
    } catch (e) {
      toast.error('Failed to load followups');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const openPreview = async (row) => {
    setPreviewOrder({ loading: true, _row: row });
    setPreviewIncludeVoucher(true);
    setPreviewLoading(true);
    try {
      const r = await axios.get(
        `${API}/api/admin/sample-followups/${row.sample_order_id}/preview?include_voucher=true`,
        { headers: tokenHdr() },
      );
      setPreviewOrder(r.data);
    } catch (e) {
      toast.error('Could not load preview');
      setPreviewOrder(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const sendNow = async () => {
    if (!previewOrder?.sample_order_id) return;
    if (!window.confirm(
      `Send the follow-up email to ${previewOrder.customer_email}?\n\n${
        previewIncludeVoucher && previewOrder.paid_count > 0
          ? `A £${(previewOrder.paid_count * voucherPerFullSize).toFixed(2)} discount voucher will be created and included.`
          : 'No discount voucher will be included.'
      }`
    )) return;
    setSending(true);
    try {
      const r = await axios.post(
        `${API}/api/admin/sample-followups/${previewOrder.sample_order_id}/send`,
        null,
        {
          headers: tokenHdr(),
          params: { include_voucher: previewIncludeVoucher },
        },
      );
      const code = r.data?.voucher_code;
      toast.success(
        code
          ? `Sent. Voucher ${code} (£${r.data.voucher_amount_gbp.toFixed(2)}) created.`
          : 'Email sent.',
      );
      setPreviewOrder(null);
      fetchAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Send failed');
    } finally {
      setSending(false);
    }
  };

  const skip = async (row) => {
    if (!window.confirm(`Skip the followup for ${row.customer_email}? This won't send an email and the order won't appear here again.`)) return;
    try {
      await axios.post(
        `${API}/api/admin/sample-followups/${row.sample_order_id}/skip`,
        null,
        { headers: tokenHdr() },
      );
      toast.success('Skipped.');
      fetchAll();
    } catch (e) {
      toast.error('Skip failed');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6" data-testid="sample-followups-page">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
              <Mail className="w-7 h-7 text-amber-600" />
              Sample Followups
            </h1>
            <p className="text-sm text-gray-600 mt-1">
              Sample orders delivered 4–14 days ago. Review each one and decide
              whether to send a follow-up email — with or without a £
              {voucherPerFullSize.toFixed(2)} voucher per Full Size sample.
            </p>
          </div>
          <Button onClick={fetchAll} variant="outline" size="sm" data-testid="followups-refresh-btn">
            <RefreshCw className="w-4 h-4 mr-1" /> Refresh
          </Button>
        </div>

        {loading ? (
          <div className="text-center py-16 text-gray-500">Loading…</div>
        ) : actionable.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center" data-testid="followups-empty">
            <Inbox className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-gray-700">Nothing to review right now</h3>
            <p className="text-sm text-gray-500 mt-2">
              When sample orders are delivered, they'll appear here 4 days later
              for you to review and send a follow-up email.
            </p>
          </div>
        ) : (
          <>
            <div className="bg-white rounded-lg shadow-sm overflow-hidden">
              <div className="px-4 py-3 bg-amber-50 border-b border-amber-200 flex items-center justify-between">
                <span className="text-sm font-semibold text-amber-900">
                  {actionable.length} awaiting your review
                </span>
                <span className="text-xs text-amber-700">
                  Each row = one sample order delivered 4–14 days ago
                </span>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-xs uppercase text-gray-600 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left">Customer</th>
                    <th className="px-4 py-3 text-left">Order #</th>
                    <th className="px-4 py-3 text-center">Samples</th>
                    <th className="px-4 py-3 text-right">Paid £</th>
                    <th className="px-4 py-3 text-right">Voucher</th>
                    <th className="px-4 py-3 text-right">Delivered</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {actionable.map((row) => (
                    <tr key={row.sample_order_id} className="hover:bg-gray-50" data-testid="followup-row">
                      <td className="px-4 py-3">
                        <div className="font-medium text-gray-900">{row.customer_name || '—'}</div>
                        <div className="text-xs text-gray-500">{row.customer_email}</div>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{row.order_number}</td>
                      <td className="px-4 py-3 text-center">
                        <div className="text-xs">
                          {row.free_sample_count > 0 && <span className="text-emerald-700">{row.free_sample_count} free</span>}
                          {row.free_sample_count > 0 && row.paid_sample_count > 0 && ' + '}
                          {row.paid_sample_count > 0 && <span className="text-amber-700 font-semibold">{row.paid_sample_count} Full Size</span>}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right font-medium">
                        {row.total_paid_gbp > 0 ? `£${row.total_paid_gbp.toFixed(2)}` : '—'}
                      </td>
                      <td className="px-4 py-3 text-right text-amber-700 font-semibold">
                        {row.would_redeem_gbp > 0 ? `£${row.would_redeem_gbp.toFixed(2)}` : '—'}
                      </td>
                      <td className="px-4 py-3 text-right text-xs text-gray-500">
                        {row.delivered_at ? new Date(row.delivered_at).toLocaleDateString('en-GB') : '—'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => openPreview(row)}
                            className="px-3 py-1.5 text-xs font-medium rounded-md bg-amber-500 hover:bg-amber-600 text-white inline-flex items-center gap-1"
                            data-testid="followup-review-btn"
                          >
                            <Eye className="w-3.5 h-3.5" /> Review
                          </button>
                          <button
                            onClick={() => skip(row)}
                            className="px-3 py-1.5 text-xs font-medium rounded-md bg-gray-100 hover:bg-gray-200 text-gray-700 inline-flex items-center gap-1"
                            data-testid="followup-skip-btn"
                          >
                            <X className="w-3.5 h-3.5" /> Skip
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {skipped.length > 0 && (
              <details className="mt-6 text-sm">
                <summary className="cursor-pointer text-gray-600 hover:text-gray-900">
                  Show {skipped.length} hidden (already sent / opted out / already ordered)
                </summary>
                <div className="mt-2 bg-white rounded-md shadow-sm p-3 space-y-1">
                  {skipped.map((s) => (
                    <div key={s.sample_order_id} className="text-xs text-gray-500 flex items-center gap-2">
                      <AlertCircle className="w-3 h-3" />
                      {s.customer_email} — <span className="text-gray-400">{s.skip_reason}</span>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </>
        )}

        {/* Recent sent history */}
        {recentSent.length > 0 && (
          <details className="mt-8 bg-white rounded-lg shadow-sm">
            <summary className="px-4 py-3 cursor-pointer font-semibold text-gray-700 flex items-center gap-2">
              <Check className="w-4 h-4 text-emerald-600" />
              Recently sent / skipped ({recentSent.length} in last 30 days)
            </summary>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs uppercase text-gray-600 border-y border-gray-200">
                <tr>
                  <th className="px-4 py-2 text-left">Customer</th>
                  <th className="px-4 py-2 text-left">Order</th>
                  <th className="px-4 py-2 text-left">Voucher</th>
                  <th className="px-4 py-2 text-right">Sent</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {recentSent.slice(0, 50).map((r) => (
                  <tr key={r.sample_order_id} data-testid="sent-history-row">
                    <td className="px-4 py-2 text-gray-700">{r.customer_email}</td>
                    <td className="px-4 py-2 font-mono text-xs">{r.order_number}</td>
                    <td className="px-4 py-2">
                      {r.voucher_code ? (
                        <span className="font-mono text-xs text-amber-700">
                          {r.voucher_code} (£{(r.voucher_amount_gbp || 0).toFixed(2)})
                        </span>
                      ) : r.manually_skipped ? (
                        <span className="text-gray-400 text-xs">Skipped</span>
                      ) : (
                        <span className="text-gray-400 text-xs">No discount</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right text-xs text-gray-500">
                      {r.sent_at ? new Date(r.sent_at).toLocaleString('en-GB') : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        )}
      </div>

      {/* Preview modal */}
      {previewOrder && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" data-testid="followup-preview-modal">
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {previewLoading || previewOrder.loading ? (
              <div className="p-12 text-center text-gray-500">Loading preview…</div>
            ) : (
              <>
                <div className="flex items-center justify-between p-4 border-b border-gray-200 sticky top-0 bg-white">
                  <div>
                    <h3 className="font-semibold text-gray-900">Email Preview</h3>
                    <div className="text-xs text-gray-500">{previewOrder.customer_email}</div>
                  </div>
                  <button onClick={() => setPreviewOrder(null)} className="text-gray-400 hover:text-gray-700">
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="p-6 space-y-5">
                  <div>
                    <div className="text-xs uppercase text-gray-500 font-semibold">Subject line</div>
                    <div className="font-medium text-gray-900 mt-1" data-testid="preview-subject">
                      {previewIncludeVoucher && previewOrder.paid_count > 0
                        ? `Hi ${(previewOrder.customer_name || 'there').split(' ')[0]}, here's £${(previewOrder.paid_count * voucherPerFullSize).toFixed(0)} off your tile order`
                        : `Hi ${(previewOrder.customer_name || 'there').split(' ')[0]}, ready to order your tiles?`}
                    </div>
                  </div>

                  <div>
                    <div className="text-xs uppercase text-gray-500 font-semibold mb-2">Samples in this order</div>
                    <div className="grid grid-cols-3 gap-3">
                      {previewOrder.products?.slice(0, 6).map((p, i) => (
                        <div key={i} className="text-center">
                          <img
                            src={p.image || 'https://images.tilestation.co.uk/placeholder.jpg'}
                            alt={p.name}
                            className="w-full h-20 object-cover rounded border border-gray-200"
                            onError={(e) => { e.target.style.display = 'none'; }}
                          />
                          <div className="text-[11px] text-gray-700 mt-1 truncate" title={p.name}>{p.name}</div>
                          <div className="mt-1">{tierBadge(p.sample_type, p.price_gbp)}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {previewOrder.paid_count > 0 && (
                    <div className="border-2 border-amber-300 bg-amber-50 rounded-lg p-4">
                      <label className="flex items-start gap-3 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={previewIncludeVoucher}
                          onChange={(e) => setPreviewIncludeVoucher(e.target.checked)}
                          className="w-4 h-4 mt-1 accent-amber-600"
                          data-testid="preview-include-voucher-toggle"
                        />
                        <div>
                          <div className="font-semibold text-amber-900 flex items-center gap-2">
                            <Tag className="w-4 h-4" />
                            Include £{(previewOrder.paid_count * voucherPerFullSize).toFixed(2)} discount voucher
                          </div>
                          <div className="text-xs text-amber-800 mt-1">
                            Refunds the £{previewOrder.total_paid_gbp.toFixed(2)} this customer paid for {previewOrder.paid_count} Full Size
                            sample{previewOrder.paid_count !== 1 ? 's' : ''} against their next order. Single-use,
                            email-locked, expires in 30 days.
                          </div>
                        </div>
                      </label>
                    </div>
                  )}

                  {previewOrder.paid_count === 0 && (
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-xs text-gray-600">
                      This customer only ordered free samples. Soft "ready to order?" CTA — no
                      discount voucher will be included.
                    </div>
                  )}

                  <div className="bg-gray-100 rounded-md p-3 text-xs text-gray-600">
                    Email body includes: greeting, sample thumbnails (above), {previewOrder.paid_count > 0 ? 'voucher block, ' : ''}
                    "place order online" button, showroom CTA, and unsubscribe footer.
                  </div>
                </div>

                <div className="border-t border-gray-200 p-4 bg-gray-50 flex justify-end gap-2 sticky bottom-0">
                  <Button
                    variant="outline"
                    onClick={() => setPreviewOrder(null)}
                    disabled={sending}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={sendNow}
                    disabled={sending}
                    className="bg-amber-600 hover:bg-amber-700 text-white"
                    data-testid="preview-send-btn"
                  >
                    <Send className="w-4 h-4 mr-1" />
                    {sending ? 'Sending…' : 'Send email'}
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default SampleFollowupsPage;
