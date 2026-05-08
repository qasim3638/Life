import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from '../../components/ui/dialog';
import { Ticket, Plus, Search, Power, Sparkles, Lock, Copy, Check } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SOURCE_LABELS = {
  abandoned_cart: { label: 'Abandoned cart', class: 'bg-amber-100 text-amber-800 border-amber-200' },
  referral: { label: 'Referral', class: 'bg-violet-100 text-violet-800 border-violet-200' },
  welcome_popup: { label: 'Welcome popup', class: 'bg-blue-100 text-blue-800 border-blue-200' },
  manual: { label: 'Manual', class: 'bg-slate-100 text-slate-800 border-slate-200' },
};

const SUMMARY_BLOCKS = [
  { key: 'abandoned_cart', label: 'Abandoned cart', color: 'bg-amber-50 text-amber-700 border-amber-200' },
  { key: 'referral', label: 'Referral', color: 'bg-violet-50 text-violet-700 border-violet-200' },
  { key: 'welcome_popup', label: 'Welcome popup', color: 'bg-blue-50 text-blue-700 border-blue-200' },
  { key: 'manual', label: 'Manual', color: 'bg-slate-50 text-slate-700 border-slate-200' },
];

export default function PromoCodesAdmin() {
  const { token, user } = useAuth();
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const [codes, setCodes] = useState([]);
  const [bySource, setBySource] = useState({});
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [activeOnly, setActiveOnly] = useState(false);
  const [copiedCode, setCopiedCode] = useState('');

  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    code: '', percent_off: 10, expires_days: 30, max_uses: 1, email: '', min_subtotal: 0,
  });

  const isAdminish = ['super_admin', 'admin', 'manager'].includes(user?.role);
  const canCreate = ['super_admin', 'admin'].includes(user?.role);

  const load = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API}/shop/discount-codes`, {
        headers,
        params: {
          q: q.trim() || undefined,
          source: sourceFilter || undefined,
          active_only: activeOnly,
          limit: 500,
        },
      });
      setCodes(res.data.codes || []);
      setBySource(res.data.by_source || {});
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load codes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (token) load(); /* eslint-disable-next-line */ }, [token]);
  useEffect(() => {
    if (!token) return;
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, sourceFilter, activeOnly]);

  const submitCreate = async () => {
    const code = (form.code || '').trim().toUpperCase();
    const percent = Number(form.percent_off);
    if (!code || !(percent > 0 && percent <= 100)) {
      toast.error('Code and a discount % between 1-100 are required');
      return;
    }
    try {
      await axios.post(`${API}/shop/discount-codes`, {
        code,
        percent_off: percent,
        expires_days: Number(form.expires_days) || 30,
        max_uses: Number(form.max_uses) || 1,
        email: (form.email || '').trim().toLowerCase() || undefined,
        min_subtotal: Number(form.min_subtotal) || 0,
      }, { headers });
      toast.success(`${code} created`);
      setShowCreate(false);
      setForm({ code: '', percent_off: 10, expires_days: 30, max_uses: 1, email: '', min_subtotal: 0 });
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Create failed');
    }
  };

  const toggle = async (code) => {
    try {
      const res = await axios.put(`${API}/shop/discount-codes/${encodeURIComponent(code)}/toggle`, {}, { headers });
      toast.success(`${code} ${res.data.active ? 'reactivated' : 'deactivated'}`);
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Toggle failed');
    }
  };

  const copy = async (code) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedCode(code);
      setTimeout(() => setCopiedCode(''), 1500);
    } catch { /* noop */ }
  };

  if (!isAdminish) {
    return (
      <div className="p-8">
        <Card>
          <CardContent className="p-8 text-center">
            <Lock className="w-12 h-12 mx-auto text-gray-400 mb-3" />
            <h2 className="text-lg font-semibold mb-1">Admin only</h2>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-5" data-testid="promo-codes-admin">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <Ticket className="w-7 h-7 text-emerald-600" />
          <div>
            <h1 className="text-2xl font-bold">Promo Codes</h1>
            <p className="text-sm text-gray-500">Every code from every source — abandoned cart, referrals, welcome popup &amp; manual</p>
          </div>
        </div>
        {canCreate && (
          <Button onClick={() => setShowCreate(true)} data-testid="create-promo-btn">
            <Plus className="w-4 h-4 mr-1" /> New code
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {SUMMARY_BLOCKS.map(({ key, label, color }) => {
          const s = bySource[key] || { count: 0, active: 0, redeemed_value: 0 };
          return (
            <Card key={key} data-testid={`promo-summary-${key}`}>
              <CardContent className="p-4">
                <div className={`inline-flex text-[11px] uppercase tracking-wider px-2 py-0.5 rounded-md border ${color} mb-2`}>{label}</div>
                <p className="text-xl font-bold tabular-nums">{s.count}</p>
                <p className="text-[11px] text-gray-500 mt-0.5">{s.active} active • £{Number(s.redeemed_value || 0).toFixed(2)} redeemed</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader className="pb-3 border-b">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <CardTitle className="text-base">All codes</CardTitle>
            <div className="flex items-center gap-2 flex-wrap">
              <div className="relative">
                <Search className="w-4 h-4 absolute left-2 top-2.5 text-gray-400" />
                <Input
                  placeholder="Search code or email"
                  value={q}
                  onChange={e => setQ(e.target.value)}
                  className="pl-8 w-56"
                  data-testid="promo-search"
                />
              </div>
              <select
                value={sourceFilter}
                onChange={e => setSourceFilter(e.target.value)}
                className="text-sm border rounded-md px-2 py-1.5 bg-white"
                data-testid="promo-source-filter"
              >
                <option value="">All sources</option>
                <option value="abandoned_cart">Abandoned cart</option>
                <option value="referral">Referral</option>
                <option value="welcome_popup">Welcome popup</option>
                <option value="manual">Manual</option>
              </select>
              <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={activeOnly}
                  onChange={e => setActiveOnly(e.target.checked)}
                  data-testid="promo-active-only"
                />
                Active only
              </label>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {loading && <p className="p-6 text-sm text-gray-400">Loading…</p>}
          {!loading && codes.length === 0 && (
            <p className="p-8 text-center text-sm text-gray-400">No codes match.</p>
          )}
          {!loading && codes.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="text-left p-3 font-semibold">Code</th>
                    <th className="text-left p-3 font-semibold">Source</th>
                    <th className="text-left p-3 font-semibold">Owner / target email</th>
                    <th className="text-center p-3 font-semibold">% off</th>
                    <th className="text-center p-3 font-semibold">Uses</th>
                    <th className="text-right p-3 font-semibold">Redeemed £</th>
                    <th className="text-left p-3 font-semibold">Expires</th>
                    <th className="text-center p-3 font-semibold">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {codes.map(c => {
                    const meta = SOURCE_LABELS[c.source] || SOURCE_LABELS.manual;
                    const isExhausted = c.used_count >= c.max_uses;
                    return (
                      <tr key={c.code} className="border-t hover:bg-gray-50" data-testid={`promo-row-${c.code}`}>
                        <td className="p-3">
                          <div className="flex items-center gap-1.5">
                            <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded border font-mono">{c.code}</code>
                            <button
                              onClick={() => copy(c.code)}
                              className="text-gray-400 hover:text-gray-700 p-0.5"
                              title="Copy code"
                              data-testid={`copy-${c.code}`}
                            >
                              {copiedCode === c.code ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        </td>
                        <td className="p-3">
                          <span className={`inline-flex text-[11px] px-1.5 py-0.5 rounded-md border ${meta.class}`}>{meta.label}</span>
                        </td>
                        <td className="p-3 text-gray-700">{c.owner_email || <span className="text-gray-400 text-xs">— (anyone)</span>}</td>
                        <td className="p-3 text-center font-semibold">{c.percent_off}%</td>
                        <td className="p-3 text-center tabular-nums">
                          <span className={isExhausted ? 'text-gray-400' : ''}>{c.used_count} / {c.max_uses}</span>
                        </td>
                        <td className="p-3 text-right tabular-nums">
                          {c.redeemed_value > 0
                            ? <span className="text-emerald-700 font-semibold">£{c.redeemed_value.toFixed(2)}</span>
                            : <span className="text-gray-400">£0.00</span>}
                        </td>
                        <td className="p-3 text-xs text-gray-500">{c.expires_at ? new Date(c.expires_at).toLocaleDateString('en-GB') : '—'}</td>
                        <td className="p-3 text-center">
                          {c.active
                            ? <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">live</Badge>
                            : <Badge variant="secondary">off</Badge>}
                          {canCreate && (
                            <button
                              onClick={() => toggle(c.code)}
                              className="ml-1 text-gray-400 hover:text-gray-700 p-1 align-middle"
                              title={c.active ? 'Deactivate' : 'Reactivate'}
                              data-testid={`toggle-${c.code}`}
                            >
                              <Power className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create a custom promo code</DialogTitle>
            <DialogDescription>
              Use this for VIP customers, one-off campaigns, or any code you want to mint by hand.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3 py-2">
            <div className="col-span-2">
              <Label className="text-xs">Code</Label>
              <Input
                placeholder="VIP20 / SUMMER10 / CUSTOM-XYZ"
                value={form.code}
                onChange={e => setForm({ ...form, code: e.target.value.toUpperCase() })}
                data-testid="new-promo-code"
              />
            </div>
            <div>
              <Label className="text-xs">Discount %</Label>
              <Input
                type="number" min={1} max={100}
                value={form.percent_off}
                onChange={e => setForm({ ...form, percent_off: e.target.value })}
                data-testid="new-promo-percent"
              />
            </div>
            <div>
              <Label className="text-xs">Expiry (days)</Label>
              <Input
                type="number" min={1} max={365}
                value={form.expires_days}
                onChange={e => setForm({ ...form, expires_days: e.target.value })}
                data-testid="new-promo-expiry"
              />
            </div>
            <div>
              <Label className="text-xs">Max uses</Label>
              <Input
                type="number" min={1} max={10000}
                value={form.max_uses}
                onChange={e => setForm({ ...form, max_uses: e.target.value })}
                data-testid="new-promo-max-uses"
              />
            </div>
            <div>
              <Label className="text-xs">Min subtotal £ (optional)</Label>
              <Input
                type="number" min={0}
                value={form.min_subtotal}
                onChange={e => setForm({ ...form, min_subtotal: e.target.value })}
                data-testid="new-promo-min-subtotal"
              />
            </div>
            <div className="col-span-2">
              <Label className="text-xs">Lock to email (optional)</Label>
              <Input
                placeholder="leave empty to allow anyone to redeem"
                value={form.email}
                onChange={e => setForm({ ...form, email: e.target.value })}
                data-testid="new-promo-email"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button onClick={submitCreate} data-testid="confirm-create-promo">
              <Sparkles className="w-4 h-4 mr-1" />
              Create code
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
