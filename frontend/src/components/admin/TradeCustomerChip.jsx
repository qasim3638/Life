import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Wallet, Award, Building2, Sparkles, AlertTriangle, ExternalLink, ChevronDown, ChevronUp, ClipboardCopy, Check } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Live trade-buyer recognition chip for the EPOS Customer Details panel.
 * As staff types an email or phone, we debounce a lookup against
 * `/api/shop/customers/lookup` and surface the customer's `T-NNNNN`
 * reference, current balance, and credit-back rate so the till operator
 * can announce the saving out loud at point of sale.
 *
 * Renders nothing for non-trade lookups — silent by design.
 */
export default function TradeCustomerChip({
  email,
  phone,
  onApplyCredit,
  applied = 0,
  maxRedeemable,
  netSubtotal = 0,
  earnedCredit = null,
  blendedRate = null,
  creditBreakdown = null,
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [accrualEnabled, setAccrualEnabled] = useState(null); // null = unknown, true/false once loaded
  const [showBreakdown, setShowBreakdown] = useState(false);
  const [copied, setCopied] = useState(false);
  const debounceRef = useRef(null);

  // Load the in-store credit-accrual master toggle once. Public endpoint, no auth needed.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await axios.get(`${API_URL}/api/storefront-messages/public`);
        if (!alive) return;
        const enabled = !!res.data?.in_store_credit?.enabled;
        setAccrualEnabled(enabled);
      } catch {
        // Keep accrualEnabled=null on transient network errors so neither
        // the green earned-pill nor the rose OFF-warning renders until we
        // actually know — avoids flashing a misleading "credit OFF" warning
        // on a brief blip when the toggle is genuinely ON.
        if (alive) setAccrualEnabled(null);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    const cleanEmail = (email || '').trim();
    const cleanPhone = (phone || '').trim();
    // Need at least 5 chars on the email or 6 digits on the phone to bother
    const emailReady = cleanEmail.length > 5 && cleanEmail.includes('@');
    const phoneReady = cleanPhone.replace(/\D/g, '').length >= 6;
    if (!emailReady && !phoneReady) {
      setData(null);
      return undefined;
    }

    debounceRef.current = setTimeout(async () => {
      try {
        setLoading(true);
        const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
        const params = {};
        if (emailReady) params.email = cleanEmail;
        if (phoneReady && !emailReady) params.phone = cleanPhone;
        const res = await axios.get(`${API_URL}/api/shop/customers/lookup`, {
          params,
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        setData(res.data?.customer || null);
      } catch {
        setData(null);
      } finally {
        setLoading(false);
      }
    }, 350);

    return () => debounceRef.current && clearTimeout(debounceRef.current);
  }, [email, phone]);

  if (loading || !data) return null;

  // ── Retail (non-trade) variant ───────────────────────────────────────
  // The lookup endpoint now returns ANY matched online customer (trade or
  // retail). For retail we render a slim sky chip — the till has confirmed
  // identity and the invoice will get stamped with `linked_shop_customer_id`
  // so the receipt appears on their online "Orders" tab and they receive
  // the VAT-invoice email automatically. No credit/discount/T-NNNNN UI.
  if (data.is_trade === false) {
    const retailName = data.name || data.business_name || 'Online customer';
    const retailEmail = data.email || '';
    const lifetimeSpend = Number(data.total_spent || 0);
    return (
      <div
        className="rounded-lg border border-sky-200 bg-gradient-to-br from-sky-50 to-blue-50 px-3 py-2.5 flex items-start gap-3"
        data-testid="epos-retail-customer-chip"
      >
        <div className="w-9 h-9 rounded-md bg-sky-500 text-white flex items-center justify-center shrink-0 shadow-sm mt-0.5">
          <Sparkles className="w-4 h-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center flex-wrap gap-x-2 gap-y-0.5">
            <p className="text-sm font-bold text-sky-900 leading-none">
              {retailName}
            </p>
            <span
              className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-sky-200 text-sky-900"
              data-testid="retail-customer-badge"
            >
              🌐 Online · Retail
            </span>
          </div>
          {retailEmail && (
            <p className="text-[11px] text-sky-800/80 mt-0.5 truncate" title={retailEmail}>
              {retailEmail}
            </p>
          )}
          <p className="text-[11px] text-sky-700 mt-1 leading-snug">
            Receipt will appear on their online <strong>Orders</strong> tab and the
            HMRC VAT invoice email is sent automatically.
            {lifetimeSpend > 0 && (
              <> Lifetime spend: <strong>£{lifetimeSpend.toFixed(2)}</strong>.</>
            )}
          </p>
        </div>
      </div>
    );
  }

  const balance = Number(data.credit_balance || 0);
  const rate = Number(data.credit_rate || 0);
  const tier = data.trade_tier || 'bronze';
  const appliedNum = Number(applied) || 0;
  const remaining = Math.max(0, balance - appliedNum);
  const canApply = !!onApplyCredit && balance > 0 && data.trade_account_number;

  // Earned-credit preview — backend mirrors this exact maths in invoices.py.
  // EPOS now accrues credit *line-by-line* using each product's
  // `credit_back_rate` (with a 2% global fallback). The parent passes the
  // pre-computed total via `earnedCredit` so the preview matches the saved
  // figure exactly. We fall back to the legacy customer-level flat-% calc
  // only for callers that haven't migrated yet (defensive, not expected).
  const netForCredit = Number(netSubtotal) || 0;
  const propEarned = earnedCredit !== null && Number.isFinite(Number(earnedCredit))
    ? Number(earnedCredit)
    : null;
  const earnedPreview = propEarned !== null
    ? Math.round(propEarned * 100) / 100
    : (rate > 0 && netForCredit > 0
      ? Math.round(netForCredit * (rate / 100) * 100) / 100
      : 0);
  const effectiveRate = blendedRate !== null && Number.isFinite(Number(blendedRate))
    ? Number(blendedRate)
    : rate;
  const previewSubtitle = propEarned !== null
    ? (effectiveRate > 0
      ? `${effectiveRate.toFixed(1)}% blended of £${netForCredit.toFixed(2)} net`
      : `across this invoice`)
    : `${rate}% of £${netForCredit.toFixed(2)} net`;

  const handleApply = () => {
    if (!canApply) return;
    if (appliedNum > 0) {
      // Toggle off — reset
      onApplyCredit({ amount: 0, account: data.trade_account_number, customer: data });
      return;
    }
    const cap = Number(maxRedeemable);
    const amount = Math.min(balance, Number.isFinite(cap) && cap > 0 ? cap : balance);
    if (amount <= 0) return;
    onApplyCredit({ amount: Math.round(amount * 100) / 100, account: data.trade_account_number, customer: data });
  };

  // Build a plain-text version of the breakdown table that pastes cleanly
  // into WhatsApp / email / SMS. Monospace alignment via padEnd so each
  // column stays readable in fixed-width fonts. Copy-to-clipboard with a
  // brief Check-icon confirmation inline — no dialog, no toast spam.
  const handleCopyBreakdown = async () => {
    if (!Array.isArray(creditBreakdown) || creditBreakdown.length === 0) return;
    const biz = data?.business_name || data?.name || 'Trade customer';
    const tRef = data?.trade_account_number ? ` (${data.trade_account_number})` : '';
    const header = `Credit-back breakdown — ${biz}${tRef}`;
    const separator = '─'.repeat(Math.min(56, header.length + 2));
    const nameCol = 28;
    const calcCol = 18;
    const lines = creditBreakdown.map((row) => {
      const name = (row.product_name || row.sku || 'Unnamed line').toString();
      const rate = Number(row.rate) || 0;
      const net = Number(row.net) || 0;
      const credit = Number(row.credit) || 0;
      const rateTxt = `${rate.toFixed(rate % 1 === 0 ? 0 : 1)}% × £${net.toFixed(2)}`;
      const namePart = name.length > nameCol ? `${name.slice(0, nameCol - 1)}…` : name.padEnd(nameCol);
      return `${namePart}  ${rateTxt.padEnd(calcCol)} £${credit.toFixed(2)}`;
    });
    const total = earnedPreview.toFixed(2);
    const totalLine = `${'Total credit'.padEnd(nameCol)}  ${' '.padEnd(calcCol)} £${total}`;
    const plain = [header, separator, ...lines, separator, totalLine].join('\n');

    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(plain);
      } else {
        // Fallback for older browsers / non-HTTPS contexts
        const ta = document.createElement('textarea');
        ta.value = plain;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      setCopied(true);
      toast.success('Breakdown copied — ready to paste', { duration: 2200 });
      setTimeout(() => setCopied(false), 1800);
    } catch (err) {
      toast.error('Could not copy — please try again');
    }
  };

  return (
    <div
      className="rounded-lg border border-amber-200 bg-gradient-to-br from-amber-50 to-yellow-50 px-3 py-2.5 flex items-start gap-3"
      data-testid="epos-trade-customer-chip"
    >
      <div className="w-9 h-9 rounded-md bg-amber-500 text-white flex items-center justify-center shrink-0 shadow-sm mt-0.5">
        <Award className="w-4 h-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center flex-wrap gap-x-2 gap-y-0.5">
          <p className="text-sm font-bold text-amber-900 leading-none flex items-center gap-1">
            <Building2 className="w-3.5 h-3.5" />
            {data.business_name || data.name}
          </p>
          {data.trade_account_number && (
            <span className="text-[11px] font-mono font-semibold text-amber-800 bg-white/60 px-1.5 py-0.5 rounded">
              {data.trade_account_number}
            </span>
          )}
          {/* Tier pill hidden 29-Apr-2026 per user request — re-enable when tier launch is ready
          <span className="text-[10px] uppercase tracking-wide text-amber-700/80 font-semibold bg-amber-100 px-1.5 py-0.5 rounded">
            {tier}
          </span>
          */}
        </div>
        <div className="flex items-center flex-wrap gap-x-3 gap-y-0.5 mt-1.5 text-[11px]">
          <span className="text-amber-800/80 inline-flex items-center gap-1">
            <Wallet className="w-3.5 h-3.5" />
            Balance{' '}
            <strong className="text-amber-900 tabular-nums">£{balance.toFixed(2)}</strong>
          </span>
          {/* "X% credit-back rate" label hidden 29-Apr-2026 — keeps the
              earned-credit preview pill (showing the actual £ to be earned)
              which is still useful, but removes the bare percentage that
              looked tier-medal-adjacent on the till.
          {rate > 0 && (
            <span className="text-amber-800/80">
              {rate}% credit-back rate
            </span>
          )}
          */}
        </div>

        {/* Earned-credit preview — live updates as line items change.
            With per-product rates we render whenever the parent supplies a
            non-zero pre-computed total OR the legacy flat-rate path yields a
            value. Hidden when the master accrual toggle is OFF. */}
        {earnedPreview > 0 && accrualEnabled === true && (
          <div className="mt-2">
            <div
              className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2 py-1 rounded-md flex-wrap"
              data-testid="epos-earned-credit-preview"
            >
              <Sparkles className="w-3 h-3" />
              Will earn{' '}
              <span className="tabular-nums">£{earnedPreview.toFixed(2)}</span>{' '}
              credit on this invoice
              <span className="text-emerald-600/80 font-normal">
                ({previewSubtitle})
              </span>
              {Array.isArray(creditBreakdown) && creditBreakdown.length > 0 && (
                <button
                  type="button"
                  onClick={() => setShowBreakdown((s) => !s)}
                  className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-emerald-700 hover:text-emerald-900 underline-offset-2 hover:underline"
                  data-testid="epos-credit-breakdown-toggle"
                  aria-expanded={showBreakdown}
                >
                  {showBreakdown ? 'Hide' : 'Show'} breakdown
                  {showBreakdown ? (
                    <ChevronUp className="w-2.5 h-2.5" />
                  ) : (
                    <ChevronDown className="w-2.5 h-2.5" />
                  )}
                </button>
              )}
            </div>

            {/* Per-line breakdown panel — receipt-style audit trail so staff
                can confidently answer "how did you get £X?" at the till. */}
            {showBreakdown && Array.isArray(creditBreakdown) && creditBreakdown.length > 0 && (
              <div
                className="mt-1.5 max-w-md border border-emerald-200 bg-white rounded-md overflow-hidden text-[11px]"
                data-testid="epos-credit-breakdown-panel"
              >
                <table className="w-full">
                  <tbody>
                    {creditBreakdown.map((row, idx) => {
                      const name = (row.product_name || row.sku || 'Unnamed line').toString();
                      const truncated = name.length > 38 ? `${name.slice(0, 36)}…` : name;
                      const rate = Number(row.rate) || 0;
                      const net = Number(row.net) || 0;
                      const credit = Number(row.credit) || 0;
                      return (
                        <tr
                          key={`${row.sku || row.product_id || idx}`}
                          className="border-b border-emerald-50 last:border-b-0"
                          data-testid={`epos-credit-breakdown-row-${idx}`}
                        >
                          <td className="px-2 py-1 text-emerald-900" title={name}>
                            {truncated}
                          </td>
                          <td className="px-2 py-1 text-emerald-700/80 tabular-nums whitespace-nowrap">
                            {rate.toFixed(rate % 1 === 0 ? 0 : 1)}% × £{net.toFixed(2)}
                          </td>
                          <td className="px-2 py-1 text-right font-semibold text-emerald-900 tabular-nums whitespace-nowrap">
                            £{credit.toFixed(2)}
                          </td>
                        </tr>
                      );
                    })}
                    <tr className="bg-emerald-50">
                      <td className="px-2 py-1 font-bold text-emerald-900" colSpan={2}>
                        Total credit
                      </td>
                      <td
                        className="px-2 py-1 text-right font-bold text-emerald-900 tabular-nums"
                        data-testid="epos-credit-breakdown-total"
                      >
                        £{earnedPreview.toFixed(2)}
                      </td>
                    </tr>
                  </tbody>
                </table>
                {/* Copy-to-clipboard action — lets staff paste the table
                    straight into WhatsApp / email / SMS when a trader asks
                    for the numbers in writing. */}
                <div className="flex justify-end px-2 py-1.5 bg-emerald-50/40 border-t border-emerald-100">
                  <button
                    type="button"
                    onClick={handleCopyBreakdown}
                    className={`inline-flex items-center gap-1 text-[10.5px] font-semibold px-2 py-0.5 rounded border transition-colors ${
                      copied
                        ? 'text-emerald-900 bg-emerald-100 border-emerald-300'
                        : 'text-emerald-800 bg-white border-emerald-200 hover:bg-emerald-50'
                    }`}
                    data-testid="epos-credit-breakdown-copy"
                    title="Copy breakdown as plain text — paste into WhatsApp, email or SMS"
                  >
                    {copied ? (
                      <>
                        <Check className="w-3 h-3" />
                        Copied
                      </>
                    ) : (
                      <>
                        <ClipboardCopy className="w-3 h-3" />
                        Copy breakdown
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Master toggle OFF warning — staff must know credit-back won't accrue.
            Show whenever a trade match exists and accrual is OFF, regardless
            of whether the cart has earnable lines yet. */}
        {accrualEnabled === false && (
          <div
            className="mt-2 inline-flex items-start gap-1.5 text-[11px] text-rose-800 bg-rose-50 border border-rose-200 px-2 py-1 rounded-md"
            data-testid="epos-credit-accrual-off"
          >
            <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
            <span>
              Credit-back accrual is currently <strong>OFF</strong> store-wide — no credit
              will be earned on this invoice.{' '}
              <a
                href="/admin/storefront-features"
                target="_blank"
                rel="noopener noreferrer"
                className="underline font-semibold inline-flex items-center gap-0.5"
              >
                Turn on
                <ExternalLink className="w-2.5 h-2.5" />
              </a>
            </span>
          </div>
        )}

        {canApply && (
          <div className="mt-2 flex items-center gap-2 flex-wrap">
            <button
              type="button"
              onClick={handleApply}
              className={`text-[11px] font-semibold px-2.5 py-1 rounded-md border transition-colors ${
                appliedNum > 0
                  ? 'bg-emerald-600 text-white border-emerald-700 hover:bg-emerald-700'
                  : 'bg-white text-amber-900 border-amber-300 hover:bg-amber-100'
              }`}
              data-testid="epos-apply-credit-btn"
            >
              {appliedNum > 0
                ? `✓ £${appliedNum.toFixed(2)} applied — undo`
                : `Apply credit (up to £${(Number.isFinite(Number(maxRedeemable)) && Number(maxRedeemable) > 0 ? Math.min(balance, Number(maxRedeemable)) : balance).toFixed(2)})`}
            </button>
            {appliedNum > 0 && (
              <span className="text-[10px] text-amber-800/70">
                Remaining balance after redemption: £{remaining.toFixed(2)}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
