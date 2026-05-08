import React, { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Switch } from '../../components/ui/switch';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs';
import { ShoppingCart, MailWarning, Sparkles, RefreshCw, Save, Send, Lock, Users } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const KPI = ({ icon: Icon, label, value, subtitle, color = 'bg-emerald-50 text-emerald-700 border-emerald-200' }) => (
  <Card data-testid={`abandoned-kpi-${label.toLowerCase().replace(/\s+/g, '-')}`}>
    <CardContent className="p-4 flex items-start gap-3">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color} border`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-wider text-gray-500">{label}</p>
        <p className="text-xl font-bold text-gray-900">{value}</p>
        {subtitle && <p className="text-[11px] text-gray-400">{subtitle}</p>}
      </div>
    </CardContent>
  </Card>
);

export default function AbandonedCartsAdmin() {
  const { token, user } = useAuth();
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const [settings, setSettings] = useState(null);
  const [stats, setStats] = useState(null);
  const [carts, setCarts] = useState([]);
  const [statusFilter, setStatusFilter] = useState('abandoned');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [referralStats, setReferralStats] = useState(null);

  const isSuperAdmin = user?.role === 'super_admin';
  const isAdminish = ['super_admin', 'admin', 'manager'].includes(user?.role);

  const load = async (filter = statusFilter) => {
    try {
      setLoading(true);
      const [s, st, cartsRes, refRes] = await Promise.all([
        axios.get(`${API}/abandoned-carts/settings`),
        axios.get(`${API}/abandoned-carts/stats`, { headers }),
        axios.get(`${API}/abandoned-carts/list`, { headers, params: { status: filter, limit: 50 } }),
        axios.get(`${API}/shop/referrals/stats`, { headers }).catch(() => ({ data: null })),
      ]);
      setSettings(s.data);
      setStats(st.data);
      setCarts(cartsRes.data.carts || []);
      setReferralStats(refRes.data);
    } catch (err) {
      console.error(err);
      toast.error(err?.response?.data?.detail || 'Failed to load abandoned carts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (token) load(); /* eslint-disable-next-line */ }, [token]);
  useEffect(() => { if (token && !loading) load(statusFilter); /* eslint-disable-next-line */ }, [statusFilter]);

  const saveSettings = async () => {
    if (!isSuperAdmin) return;
    try {
      setSaving(true);
      const payload = {
        enabled: !!settings.enabled,
        day_0_hours: Number(settings.day_0_hours) || 3,
        day_1_hours: Number(settings.day_1_hours) || 24,
        discount_percent: Number(settings.discount_percent) || 10,
        expires_days: Number(settings.expires_days) || 7,
        last_chance_enabled: !!settings.last_chance_enabled,
        last_chance_hours_before_expiry: Number(settings.last_chance_hours_before_expiry) || 24,
        whatsapp_enabled: !!settings.whatsapp_enabled,
        whatsapp_template_name: (settings.whatsapp_template_name || 'abandoned_cart_promo').trim(),
        whatsapp_language_code: (settings.whatsapp_language_code || 'en').trim(),
      };
      const res = await axios.put(`${API}/abandoned-carts/settings`, payload, { headers });
      setSettings(res.data);
      toast.success('Settings saved');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const triggerSend = async () => {
    try {
      setTriggering(true);
      const res = await axios.post(`${API}/abandoned-carts/send-reminders`, {}, { headers });
      const { day_0_sent = 0, day_1_sent = 0, last_chance_sent = 0, status } = res.data || {};
      if (status === 'disabled') {
        toast.info('Sequence is currently disabled — no emails sent');
      } else {
        toast.success(`Sent ${day_0_sent} day-0 + ${day_1_sent} day-1 + ${last_chance_sent} last-chance emails`);
      }
      load(statusFilter);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Trigger failed');
    } finally {
      setTriggering(false);
    }
  };

  if (!isAdminish) {
    return (
      <div className="p-8" data-testid="abandoned-no-access">
        <Card>
          <CardContent className="p-8 text-center">
            <Lock className="w-12 h-12 mx-auto text-gray-400 mb-3" />
            <h2 className="text-lg font-semibold mb-1">Admin only</h2>
            <p className="text-sm text-gray-500">You don't have access to abandoned baskets.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-5" data-testid="abandoned-carts-admin">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <ShoppingCart className="w-7 h-7 text-emerald-600" />
          <div>
            <h1 className="text-2xl font-bold">Abandoned Baskets</h1>
            <p className="text-sm text-gray-500">Recovery sequence — day-0 reminder, day-1 promo, last-chance nudge</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => load(statusFilter)} data-testid="abandoned-refresh">
            <RefreshCw className="w-4 h-4 mr-1" /> Refresh
          </Button>
          <Button onClick={triggerSend} disabled={triggering} data-testid="abandoned-trigger">
            <Send className="w-4 h-4 mr-1" />
            {triggering ? 'Sending…' : 'Send pending now'}
          </Button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <KPI icon={ShoppingCart} label="Abandoned" value={stats.total_abandoned} subtitle={`£${(stats.total_value || 0).toFixed(2)}`} color="bg-amber-50 text-amber-700 border-amber-200" />
          <KPI icon={Sparkles} label="Recovered" value={stats.recovered} subtitle={`£${(stats.recovered_value || 0).toFixed(2)}`} color="bg-emerald-50 text-emerald-700 border-emerald-200" />
          <KPI icon={MailWarning} label="Pending sends" value={stats.pending_reminders} color="bg-blue-50 text-blue-700 border-blue-200" />
          <KPI icon={Sparkles} label="Conversion" value={`${stats.conversion_rate || 0}%`} color="bg-violet-50 text-violet-700 border-violet-200" />
          <KPI icon={ShoppingCart} label="Total value" value={`£${((stats.total_value || 0) + (stats.recovered_value || 0)).toFixed(2)}`} subtitle="abandoned + recovered" color="bg-slate-50 text-slate-700 border-slate-200" />
          <KPI icon={Send} label="Sequence" value={settings?.enabled ? 'ON' : 'OFF'} color={settings?.enabled ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-gray-100 text-gray-500 border-gray-200'} />
        </div>
      )}

      <Tabs defaultValue="settings" className="w-full">
        <TabsList>
          <TabsTrigger value="settings" data-testid="tab-settings">Sequence Settings</TabsTrigger>
          <TabsTrigger value="carts" data-testid="tab-carts">Baskets</TabsTrigger>
          <TabsTrigger value="referrals" data-testid="tab-referrals">Referrals</TabsTrigger>
        </TabsList>

        <TabsContent value="settings" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recovery sequence</CardTitle>
              {!isSuperAdmin && (
                <p className="text-xs text-amber-600">Read-only — only Super Admin can change these.</p>
              )}
            </CardHeader>
            <CardContent className="space-y-5">
              {settings && (
                <>
                  <div className="flex items-center justify-between border rounded-lg p-3">
                    <div>
                      <Label className="text-sm font-semibold">Sequence enabled</Label>
                      <p className="text-xs text-gray-500">Pause to stop all day-0 and day-1 emails immediately.</p>
                    </div>
                    <Switch
                      checked={!!settings.enabled}
                      onCheckedChange={(v) => setSettings({ ...settings, enabled: v })}
                      disabled={!isSuperAdmin}
                      data-testid="settings-enabled"
                    />
                  </div>

                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <Label className="text-xs uppercase tracking-wider text-gray-500">Day-0 reminder delay (hours)</Label>
                      <Input
                        type="number" min={1} max={48}
                        value={settings.day_0_hours}
                        onChange={(e) => setSettings({ ...settings, day_0_hours: e.target.value })}
                        disabled={!isSuperAdmin}
                        data-testid="settings-day0"
                      />
                      <p className="text-[11px] text-gray-400 mt-1">A gentle "you left something behind" reminder. Default: 3 hours.</p>
                    </div>
                    <div>
                      <Label className="text-xs uppercase tracking-wider text-gray-500">Day-1 promo delay (hours)</Label>
                      <Input
                        type="number" min={2} max={168}
                        value={settings.day_1_hours}
                        onChange={(e) => setSettings({ ...settings, day_1_hours: e.target.value })}
                        disabled={!isSuperAdmin}
                        data-testid="settings-day1"
                      />
                      <p className="text-[11px] text-gray-400 mt-1">Email with promo code. Default: 24 hours.</p>
                    </div>
                    <div>
                      <Label className="text-xs uppercase tracking-wider text-gray-500">Discount %</Label>
                      <Input
                        type="number" min={0} max={50}
                        value={settings.discount_percent}
                        onChange={(e) => setSettings({ ...settings, discount_percent: e.target.value })}
                        disabled={!isSuperAdmin}
                        data-testid="settings-discount"
                      />
                      <p className="text-[11px] text-gray-400 mt-1">Used in the day-1 email's BACK-XXXXXX code. Default: 10%.</p>
                    </div>
                    <div>
                      <Label className="text-xs uppercase tracking-wider text-gray-500">Code expiry (days)</Label>
                      <Input
                        type="number" min={1} max={60}
                        value={settings.expires_days}
                        onChange={(e) => setSettings({ ...settings, expires_days: e.target.value })}
                        disabled={!isSuperAdmin}
                        data-testid="settings-expiry"
                      />
                      <p className="text-[11px] text-gray-400 mt-1">How long each promo code stays valid. Default: 7 days.</p>
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <Button onClick={saveSettings} disabled={!isSuperAdmin || saving} data-testid="settings-save">
                      <Save className="w-4 h-4 mr-1" />
                      {saving ? 'Saving…' : 'Save settings'}
                    </Button>
                  </div>

                  {/* Last-chance reminder */}
                  <div className="border-t pt-5 mt-2">
                    <div className="flex items-center justify-between border rounded-lg p-3 bg-rose-50/30">
                      <div className="min-w-0 pr-3">
                        <Label className="text-sm font-semibold flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                          Send a final "last chance" reminder before the code expires
                        </Label>
                        <p className="text-xs text-gray-500">
                          Only fires if the basket is still abandoned AND the promo code hasn't been used yet. No new code is minted — same BACK-XXXXXX, urgency message.
                        </p>
                      </div>
                      <Switch
                        checked={!!settings.last_chance_enabled}
                        onCheckedChange={(v) => setSettings({ ...settings, last_chance_enabled: v })}
                        disabled={!isSuperAdmin}
                        data-testid="settings-last-chance-enabled"
                      />
                    </div>
                    {settings.last_chance_enabled && (
                      <div className="mt-3 max-w-xs">
                        <Label className="text-xs uppercase tracking-wider text-gray-500">Send hours BEFORE code expiry</Label>
                        <Input
                          type="number" min={1} max={168}
                          value={settings.last_chance_hours_before_expiry || 24}
                          onChange={(e) => setSettings({ ...settings, last_chance_hours_before_expiry: e.target.value })}
                          disabled={!isSuperAdmin}
                          data-testid="settings-last-chance-hours"
                        />
                        <p className="text-[11px] text-gray-400 mt-1">Default: 24h before expiry — i.e. day-6 if your codes expire on day-7.</p>
                      </div>
                    )}
                  </div>

                  {/* WhatsApp augmentation */}
                  <div className="border-t pt-5 mt-2">
                    <div className="flex items-center justify-between border rounded-lg p-3 bg-emerald-50/30">
                      <div className="min-w-0 pr-3">
                        <Label className="text-sm font-semibold flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                          Also send Day-1 promo over WhatsApp
                        </Label>
                        <p className="text-xs text-gray-500">
                          Sends the same BACK-XXXXXX code to the customer's phone (if provided) using your approved WhatsApp template.
                          Requires <code className="bg-gray-100 px-1 rounded">WHATSAPP_PHONE_NUMBER_ID</code> &amp; <code className="bg-gray-100 px-1 rounded">WHATSAPP_ACCESS_TOKEN</code> env vars.
                        </p>
                      </div>
                      <Switch
                        checked={!!settings.whatsapp_enabled}
                        onCheckedChange={(v) => setSettings({ ...settings, whatsapp_enabled: v })}
                        disabled={!isSuperAdmin}
                        data-testid="settings-whatsapp-enabled"
                      />
                    </div>
                    {settings.whatsapp_enabled && (
                      <div className="grid md:grid-cols-2 gap-4 mt-3">
                        <div>
                          <Label className="text-xs uppercase tracking-wider text-gray-500">Approved template name</Label>
                          <Input
                            value={settings.whatsapp_template_name || ''}
                            onChange={(e) => setSettings({ ...settings, whatsapp_template_name: e.target.value })}
                            placeholder="abandoned_cart_promo"
                            disabled={!isSuperAdmin}
                            data-testid="settings-whatsapp-template"
                          />
                          <p className="text-[11px] text-gray-400 mt-1">
                            Must match an APPROVED template in your WhatsApp Manager. Body should accept 3 variables: {'{{1}}'} = first name, {'{{2}}'} = % off, {'{{3}}'} = code.
                          </p>
                        </div>
                        <div>
                          <Label className="text-xs uppercase tracking-wider text-gray-500">Template language</Label>
                          <Input
                            value={settings.whatsapp_language_code || 'en'}
                            onChange={(e) => setSettings({ ...settings, whatsapp_language_code: e.target.value })}
                            placeholder="en"
                            disabled={!isSuperAdmin}
                            data-testid="settings-whatsapp-language"
                          />
                          <p className="text-[11px] text-gray-400 mt-1">e.g. <code>en</code> or <code>en_GB</code> — must match the template's locale.</p>
                        </div>
                      </div>
                    )}
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="carts" className="mt-4">
          <Card>
            <CardHeader className="pb-3 border-b">
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="text-base">Baskets</CardTitle>
                <div className="flex items-center gap-2">
                  {['abandoned', 'recovered'].map((s) => (
                    <Button
                      key={s}
                      size="sm"
                      variant={statusFilter === s ? 'default' : 'outline'}
                      onClick={() => setStatusFilter(s)}
                      data-testid={`filter-${s}`}
                    >
                      {s.charAt(0).toUpperCase() + s.slice(1)}
                    </Button>
                  ))}
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {loading && <p className="p-6 text-sm text-gray-400">Loading…</p>}
              {!loading && carts.length === 0 && (
                <p className="p-8 text-center text-sm text-gray-400">No {statusFilter} baskets right now.</p>
              )}
              {!loading && carts.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="text-left p-3 font-semibold">Customer</th>
                        <th className="text-left p-3 font-semibold">Items</th>
                        <th className="text-right p-3 font-semibold">Total</th>
                        <th className="text-center p-3 font-semibold">Day-0</th>
                        <th className="text-center p-3 font-semibold">Day-1</th>
                        <th className="text-center p-3 font-semibold">Last-chance</th>
                        <th className="text-left p-3 font-semibold">Promo</th>
                        <th className="text-left p-3 font-semibold">Updated</th>
                      </tr>
                    </thead>
                    <tbody>
                      {carts.map((c) => (
                        <tr key={c.id || c.customer_email} className="border-t hover:bg-gray-50" data-testid={`cart-row-${c.customer_email}`}>
                          <td className="p-3">
                            <div className="font-medium text-gray-900">{c.customer_name || '—'}</div>
                            <div className="text-xs text-gray-500">{c.customer_email}</div>
                          </td>
                          <td className="p-3 text-gray-700">
                            {(c.items || []).slice(0, 3).map((i, idx) => (
                              <div key={idx} className="text-xs">
                                {i.name} <span className="text-gray-400">× {Number(i.quantity || 0).toFixed(2)}</span>
                              </div>
                            ))}
                            {(c.items || []).length > 3 && (
                              <div className="text-xs text-gray-400">+{c.items.length - 3} more</div>
                            )}
                          </td>
                          <td className="p-3 text-right font-semibold tabular-nums">£{Number(c.cart_total || 0).toFixed(2)}</td>
                          <td className="p-3 text-center">
                            {c.reminder_sent_day_0
                              ? <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">sent</Badge>
                              : <Badge variant="secondary">pending</Badge>}
                          </td>
                          <td className="p-3 text-center">
                            {c.reminder_sent_day_1
                              ? <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">sent</Badge>
                              : <Badge variant="secondary">pending</Badge>}
                            {c.whatsapp_sent && (
                              <Badge className="ml-1 bg-green-600 text-white hover:bg-green-600" title="WhatsApp also sent">WA</Badge>
                            )}
                          </td>
                          <td className="p-3 text-center">
                            {c.reminder_sent_last_chance
                              ? (c.last_chance_skipped_reason
                                  ? <Badge className="bg-gray-100 text-gray-500" title={c.last_chance_skipped_reason}>skipped</Badge>
                                  : <Badge className="bg-rose-100 text-rose-700 hover:bg-rose-100">sent</Badge>)
                              : (c.promo_code ? <Badge variant="secondary">pending</Badge> : <span className="text-xs text-gray-400">—</span>)}
                          </td>
                          <td className="p-3">
                            {c.promo_code ? (
                              <code className="text-xs bg-amber-50 text-amber-800 px-1.5 py-0.5 rounded border border-amber-200">{c.promo_code}</code>
                            ) : <span className="text-xs text-gray-400">—</span>}
                          </td>
                          <td className="p-3 text-xs text-gray-500">
                            {c.updated_at ? new Date(c.updated_at).toLocaleString('en-GB') : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="referrals" className="mt-4">
          <Card>
            <CardHeader className="pb-3 border-b">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Users className="w-4 h-4" /> Friend referrals
                  </CardTitle>
                  <p className="text-xs text-gray-500 mt-0.5">FRIEND-XXXXXX codes generated by your day-1 customers via the share block.</p>
                </div>
                <a
                  href="/shop/refer"
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-emerald-700 hover:underline"
                  data-testid="open-public-refer-page"
                >
                  Open public share page →
                </a>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {referralStats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-4 border-b">
                  <KPI icon={Sparkles} label="Total codes" value={referralStats.total_codes || 0} color="bg-violet-50 text-violet-700 border-violet-200" />
                  <KPI icon={Sparkles} label="Active" value={referralStats.active_codes || 0} color="bg-emerald-50 text-emerald-700 border-emerald-200" />
                  <KPI icon={Sparkles} label="Redeemed" value={`${referralStats.paid_redemptions || 0}/${referralStats.total_redemptions || 0}`} subtitle="paid / total" color="bg-blue-50 text-blue-700 border-blue-200" />
                  <KPI icon={Sparkles} label="Revenue" value={`£${(referralStats.revenue_from_referrals || 0).toFixed(2)}`} color="bg-amber-50 text-amber-700 border-amber-200" />
                </div>
              )}
              {referralStats && (referralStats.codes || []).length === 0 && (
                <p className="p-8 text-center text-sm text-gray-400">No referral codes generated yet. They appear once a day-1 customer clicks "Get my friend's code" in their email.</p>
              )}
              {referralStats && (referralStats.codes || []).length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="text-left p-3 font-semibold">Code</th>
                        <th className="text-left p-3 font-semibold">Referrer</th>
                        <th className="text-center p-3 font-semibold">Uses</th>
                        <th className="text-center p-3 font-semibold">% off</th>
                        <th className="text-left p-3 font-semibold">Expires</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(referralStats.codes || []).map((c) => (
                        <tr key={c.code} className="border-t hover:bg-gray-50" data-testid={`referral-row-${c.code}`}>
                          <td className="p-3"><code className="text-xs bg-violet-50 text-violet-800 px-1.5 py-0.5 rounded border border-violet-200">{c.code}</code></td>
                          <td className="p-3 text-gray-700">{c.referrer_email || '—'}</td>
                          <td className="p-3 text-center tabular-nums">{c.used_count || 0} / {c.max_uses || 0}</td>
                          <td className="p-3 text-center">{c.percent_off}%</td>
                          <td className="p-3 text-xs text-gray-500">{c.expires_at ? new Date(c.expires_at).toLocaleDateString('en-GB') : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
