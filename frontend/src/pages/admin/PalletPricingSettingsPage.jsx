import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Save, Info } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';

const API = process.env.REACT_APP_BACKEND_URL;
const tokenHdr = () => {
  const t = localStorage.getItem('admin_token') || localStorage.getItem('token');
  return t ? { Authorization: `Bearer ${t}` } : {};
};

const MODE_OPTIONS = [
  {
    value: 'same',
    title: 'Same rate for retail and trade',
    description:
      'Pallet £/m² rate applies to both retail and trade customers. Any global trade discount you have configured still applies on top, exactly like per-m² pricing.',
  },
  {
    value: 'trade_only',
    title: 'Trade customers only',
    description:
      'Retail customers don\'t see pallet pricing at all — they only see per-m² and per-unit prices. Trade customers see all options. Use when you want pallet rates to be a trade-account perk.',
  },
  {
    value: 'trade_extra_discount',
    title: 'Same rate, with extra trade discount',
    description:
      'Pallet rate is published to retail customers. Trade customers get an EXTRA % off the pallet rate (separate from any global trade discount). Set the extra % below.',
  },
];

const PalletPricingSettingsPage = () => {
  const [mode, setMode] = useState('same');
  const [extraPct, setExtraPct] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/admin/pallet-settings`, { headers: tokenHdr() });
      setMode(r.data?.pallet_pricing_mode || 'same');
      setExtraPct(r.data?.pallet_trade_extra_discount_pct || 0);
    } catch {
      toast.error('Failed to load pallet settings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchSettings(); }, []);

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(
        `${API}/api/admin/pallet-settings`,
        {
          pallet_pricing_mode: mode,
          pallet_trade_extra_discount_pct: parseFloat(extraPct) || 0,
        },
        { headers: tokenHdr() },
      );
      toast.success('Pallet settings saved');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6" data-testid="pallet-pricing-settings-page">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Pallet Pricing Rules</h1>
        <p className="text-sm text-gray-600 mb-6">
          Choose how pallet rates apply when both retail and trade customers visit
          a tile. The rate values themselves live on each product (set in Edit
          Product or the Bulk Category Editor).
        </p>

        {loading ? (
          <div className="text-center text-gray-500 py-12">Loading…</div>
        ) : (
          <>
            <div className="space-y-3" data-testid="pallet-mode-options">
              {MODE_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={`block border-2 rounded-lg p-4 cursor-pointer transition ${
                    mode === opt.value
                      ? 'border-amber-500 bg-amber-50'
                      : 'border-gray-200 bg-white hover:border-gray-300'
                  }`}
                  data-testid={`pallet-mode-${opt.value}`}
                >
                  <div className="flex items-start gap-3">
                    <input
                      type="radio"
                      name="pallet_mode"
                      value={opt.value}
                      checked={mode === opt.value}
                      onChange={() => setMode(opt.value)}
                      className="w-4 h-4 mt-1 accent-amber-600"
                    />
                    <div className="flex-1">
                      <div className="font-semibold text-gray-900">{opt.title}</div>
                      <div className="text-sm text-gray-600 mt-1 leading-relaxed">{opt.description}</div>
                    </div>
                  </div>
                </label>
              ))}
            </div>

            {mode === 'trade_extra_discount' && (
              <div className="mt-5 bg-white rounded-lg p-4 border border-gray-200" data-testid="extra-discount-pct-wrap">
                <label className="block text-sm font-semibold text-gray-900 mb-2">
                  Extra trade discount on pallet rate
                </label>
                <div className="flex items-center gap-2 max-w-xs">
                  <Input
                    type="number"
                    step="0.5"
                    min="0"
                    max="50"
                    value={extraPct}
                    onChange={(e) => setExtraPct(e.target.value)}
                    data-testid="extra-discount-pct-input"
                  />
                  <span className="text-gray-700 font-medium">%</span>
                </div>
                <p className="text-xs text-gray-500 mt-2 leading-relaxed">
                  Example: if a tile's pallet rate is £30/m² and this is 10%, trade
                  customers pay £27/m² at pallet quantity. Capped at 0–50%.
                </p>
              </div>
            )}

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mt-5 flex gap-3">
              <Info className="w-5 h-5 text-blue-700 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-900">
                <strong>Heads up:</strong> Pallet pricing is hidden by default on the
                storefront. It only renders on a tile's PDP if BOTH "m² per pallet"
                AND "pallet £/m²" are filled in for that product. Use the Bulk
                Category Editor to set values for many tiles at once.
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <Button
                onClick={save}
                disabled={saving}
                className="bg-amber-600 hover:bg-amber-700 text-white"
                data-testid="save-pallet-settings-btn"
              >
                <Save className="w-4 h-4 mr-1" />
                {saving ? 'Saving…' : 'Save settings'}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default PalletPricingSettingsPage;
