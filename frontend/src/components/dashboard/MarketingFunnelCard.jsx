import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '../ui/card';
import {
  Megaphone,
  Mail,
  ShoppingBag,
  MessageCircle,
  Tag,
  CheckCircle2,
  PoundSterling,
  ArrowRight,
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SOURCE_LABELS = {
  welcome_popup: 'Welcome popup',
  cart_save_banner: 'Cart save banner',
  abandoned_cart: 'Abandoned cart',
  referral: 'Refer-a-friend',
  manual: 'Manual',
};

function Metric({ icon: Icon, label, value, suffix, testId, accent = 'text-gray-900' }) {
  return (
    <div className="flex items-start gap-2.5 min-w-0" data-testid={testId}>
      <div className="w-8 h-8 rounded-md bg-white/70 border border-gray-200 flex items-center justify-center shrink-0">
        <Icon className="w-4 h-4 text-gray-700" />
      </div>
      <div className="min-w-0">
        <p className="text-[10px] uppercase tracking-wider text-gray-500 truncate">{label}</p>
        <p className={`text-lg font-bold tabular-nums ${accent}`}>
          {value}
          {suffix && <span className="text-xs font-normal text-gray-500 ml-0.5">{suffix}</span>}
        </p>
      </div>
    </div>
  );
}

/**
 * Last-N-days marketing-funnel snapshot for the admin dashboard.
 * Shows captures (popup + banner), abandoned-cart channel activity, and promo redemptions.
 */
export default function MarketingFunnelCard() {
  const { token, user } = useAuth();
  const [days, setDays] = useState(7);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const isAdminish = ['super_admin', 'admin', 'manager'].includes(user?.role);

  useEffect(() => {
    if (!token || !isAdminish) return;
    let cancelled = false;
    setLoading(true);
    axios.get(`${API}/marketing/funnel?days=${days}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(res => { if (!cancelled) setData(res.data); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [token, isAdminish, days]);

  if (!isAdminish) return null;

  const captures = data?.captures || { welcome_popup: 0, cart_save_banner: 0, total: 0 };
  const abandoned = data?.abandoned || {};
  const codes = data?.codes || { minted: 0, redeemed: 0, by_source: [] };

  return (
    <Card
      className="border-gray-200 hover:shadow-md transition-shadow"
      data-testid="dashboard-marketing-funnel-card"
    >
      <CardContent className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-md bg-amber-100 text-amber-700 flex items-center justify-center">
              <Megaphone className="w-4 h-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900">Marketing funnel</p>
              <p className="text-[11px] text-gray-500">
                Last {data?.days ?? days} day{(data?.days ?? days) === 1 ? '' : 's'} of lead capture, recovery & promo activity
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1" data-testid="funnel-range-toggle">
            {[7, 30].map(d => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-2 py-1 text-[11px] rounded border transition-colors ${
                  days === d
                    ? 'bg-gray-900 text-white border-gray-900'
                    : 'bg-white text-gray-700 border-gray-200 hover:border-gray-400'
                }`}
                data-testid={`funnel-range-${d}d`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>

        {/* Top-line metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
          <Metric
            icon={Mail}
            label="Popups"
            value={captures.welcome_popup}
            testId="funnel-metric-popup"
          />
          <Metric
            icon={ShoppingBag}
            label="Cart banners"
            value={captures.cart_save_banner}
            testId="funnel-metric-banner"
          />
          <Metric
            icon={MessageCircle}
            label="WhatsApp"
            value={abandoned.whatsapp_sent || 0}
            testId="funnel-metric-whatsapp"
          />
          <Metric
            icon={Tag}
            label="Codes minted"
            value={codes.minted}
            testId="funnel-metric-minted"
          />
          <Metric
            icon={CheckCircle2}
            label="Redeemed"
            value={codes.redeemed}
            testId="funnel-metric-redeemed"
            accent="text-emerald-700"
          />
          <Metric
            icon={PoundSterling}
            label="Recovered"
            value={`£${(abandoned.revenue_recovered || 0).toFixed(0)}`}
            testId="funnel-metric-recovered"
            accent="text-emerald-700"
          />
        </div>

        {/* By-source breakdown */}
        {codes.by_source && codes.by_source.length > 0 ? (
          <div
            className="rounded-lg border border-gray-200 bg-gray-50/60 px-3 py-2"
            data-testid="funnel-source-breakdown"
          >
            <p className="text-[10px] uppercase tracking-wider text-gray-500 mb-1.5">Codes by channel</p>
            <div className="flex flex-wrap gap-x-4 gap-y-1.5">
              {codes.by_source.map(row => (
                <div
                  key={row.source}
                  className="flex items-center gap-1.5 text-xs"
                  data-testid={`funnel-source-${row.source}`}
                >
                  <span className="text-gray-600">{SOURCE_LABELS[row.source] || row.source}</span>
                  <span className="font-semibold tabular-nums text-gray-900">{row.minted}</span>
                  <span className="text-gray-400">→</span>
                  <span className="font-semibold tabular-nums text-emerald-700">{row.redeemed}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          !loading && (
            <p className="text-xs text-gray-500 italic" data-testid="funnel-empty-state">
              No promo codes minted in this window.
            </p>
          )
        )}

        {/* Footer link */}
        <div className="mt-4 flex items-center justify-end">
          <Link
            to="/admin/promo-codes"
            className="inline-flex items-center gap-1 text-xs font-medium text-gray-700 hover:text-gray-900"
            data-testid="funnel-view-codes-link"
          >
            View all promo codes
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
