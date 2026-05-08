import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Switch } from '../../components/ui/switch';
import { Label } from '../../components/ui/label';
import { Input } from '../../components/ui/input';
import { Sliders, Save, GitCompare, Users, MailOpen, Lock, Gift, MessageSquare, LogIn, LogOut, Eye, Wallet } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ROW = ({ icon: Icon, title, desc, children }) => (
  <div className="flex items-start justify-between gap-4 border rounded-lg p-4">
    <div className="flex items-start gap-3 min-w-0">
      <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center shrink-0">
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0">
        <p className="font-semibold text-gray-900">{title}</p>
        <p className="text-xs text-gray-500 mt-0.5">{desc}</p>
      </div>
    </div>
    <div className="shrink-0">{children}</div>
  </div>
);

export default function StorefrontFeaturesAdmin() {
  const { token, user } = useAuth();
  const isSuperAdmin = user?.role === 'super_admin';
  const isAdminish = ['super_admin', 'admin', 'manager'].includes(user?.role);
  const headers = { Authorization: `Bearer ${token}` };

  const [features, setFeatures] = useState(null);
  const [popup, setPopup] = useState(null); // welcome popup config
  const [messages, setMessages] = useState(null); // storefront toast messages
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const [f, p, m] = await Promise.all([
        axios.get(`${API}/storefront-features`, { headers }),
        axios.get(`${API}/website-admin/welcome-popup`, { headers }),
        axios.get(`${API}/storefront-messages`, { headers }),
      ]);
      setFeatures(f.data);
      setPopup(p.data);
      setMessages(m.data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load features');
    }
  };

  useEffect(() => { if (token) load(); /* eslint-disable-next-line */ }, [token]);

  const saveFeatures = async (patch) => {
    if (!isSuperAdmin) return;
    try {
      setSaving(true);
      const res = await axios.put(`${API}/storefront-features`, { ...features, ...patch }, { headers });
      setFeatures(res.data);
      toast.success('Saved');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const savePopup = async () => {
    if (!isSuperAdmin) return;
    try {
      setSaving(true);
      await axios.put(`${API}/website-admin/welcome-popup`, popup, { headers });
      toast.success('Welcome popup saved');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const saveMessages = async (key, patch) => {
    if (!isSuperAdmin || !messages) return;
    try {
      setSaving(true);
      const next = {
        ...messages,
        [key]: { ...(messages[key] || {}), ...patch },
      };
      const res = await axios.put(`${API}/storefront-messages`, next, { headers });
      setMessages(res.data);
      toast.success('Saved');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (!isAdminish) {
    return (
      <div className="p-8">
        <Card><CardContent className="p-8 text-center">
          <Lock className="w-12 h-12 mx-auto text-gray-400 mb-3" />
          <h2 className="text-lg font-semibold mb-1">Admin only</h2>
        </CardContent></Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-5" data-testid="storefront-features-admin">
      <div className="flex items-center gap-3">
        <Sliders className="w-7 h-7 text-emerald-600" />
        <div>
          <h1 className="text-2xl font-bold">Storefront Features</h1>
          <p className="text-sm text-gray-500">Show or hide each customer-facing feature on the live website.</p>
        </div>
      </div>

      {/* Top-level toggles */}
      {features && (
        <Card>
          <CardHeader><CardTitle className="text-base">Visibility</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <ROW
              icon={GitCompare}
              title="Compare tiles"
              desc="Floating tray + dedicated /shop/compare page. Shoppers can stack up to N tiles side-by-side."
            >
              <Switch
                checked={!!features.compare_enabled}
                onCheckedChange={(v) => saveFeatures({ compare_enabled: v })}
                disabled={!isSuperAdmin || saving}
                data-testid="feature-compare"
              />
            </ROW>
            {features.compare_enabled && (
              <div className="ml-14 max-w-xs">
                <Label className="text-xs uppercase tracking-wider text-gray-500">Max tiles to compare</Label>
                <Input
                  type="number" min={2} max={6}
                  value={features.compare_max || 3}
                  onChange={(e) => setFeatures({ ...features, compare_max: e.target.value })}
                  onBlur={() => saveFeatures({ compare_max: Number(features.compare_max) || 3 })}
                  disabled={!isSuperAdmin}
                  data-testid="feature-compare-max"
                />
              </div>
            )}

            <ROW
              icon={Users}
              title="Refer-a-friend page"
              desc="Public /shop/refer page lets customers mint FRIEND-XXXXXX codes and share them."
            >
              <Switch
                checked={!!features.refer_a_friend_enabled}
                onCheckedChange={(v) => saveFeatures({ refer_a_friend_enabled: v })}
                disabled={!isSuperAdmin || saving}
                data-testid="feature-refer"
              />
            </ROW>

            <ROW
              icon={MailOpen}
              title="Welcome popup"
              desc="Master toggle for the welcome popup. Disabling here hides it on every page regardless of its own settings below."
            >
              <Switch
                checked={!!features.welcome_popup_visible}
                onCheckedChange={(v) => saveFeatures({ welcome_popup_visible: v })}
                disabled={!isSuperAdmin || saving}
                data-testid="feature-welcome-popup"
              />
            </ROW>

            <ROW
              icon={Gift}
              title='"Save 10%" cart banner'
              desc="Small in-cart banner that catches guests who closed the popup but are still actively shopping. Only shows when 'Email a discount code on signup' is also ON below."
            >
              <Switch
                checked={!!features.cart_save_banner_enabled}
                onCheckedChange={(v) => saveFeatures({ cart_save_banner_enabled: v })}
                disabled={!isSuperAdmin || saving}
                data-testid="feature-cart-save-banner"
              />
            </ROW>
          </CardContent>
        </Card>
      )}

      {/* Welcome popup deep config */}
      {popup && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Welcome popup details</CardTitle>
            <p className="text-xs text-gray-500">Email + auto-coupon. The code is sent via email only — never shown in the popup, so visitors must check their inbox (which encourages registration).</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <Label className="text-xs uppercase tracking-wider text-gray-500">Heading</Label>
                <Input
                  value={popup.heading || ''}
                  onChange={(e) => setPopup({ ...popup, heading: e.target.value })}
                  placeholder="Welcome to Tile Station"
                  disabled={!isSuperAdmin}
                  data-testid="popup-heading"
                />
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider text-gray-500">Submit button text</Label>
                <Input
                  value={popup.email_button_text || ''}
                  onChange={(e) => setPopup({ ...popup, email_button_text: e.target.value })}
                  placeholder="Email me my code"
                  disabled={!isSuperAdmin}
                  data-testid="popup-btn-text"
                />
              </div>
              <div className="md:col-span-2">
                <Label className="text-xs uppercase tracking-wider text-gray-500">Message</Label>
                <Input
                  value={popup.message || ''}
                  onChange={(e) => setPopup({ ...popup, message: e.target.value })}
                  placeholder="Drop your email and we'll send you 10% off your first order"
                  disabled={!isSuperAdmin}
                  data-testid="popup-message"
                />
              </div>
            </div>

            <div className="grid md:grid-cols-3 gap-4">
              <div>
                <Label className="text-xs uppercase tracking-wider text-gray-500">Show every</Label>
                <select
                  value={popup.frequency || 'once'}
                  onChange={(e) => setPopup({ ...popup, frequency: e.target.value })}
                  disabled={!isSuperAdmin}
                  className="w-full text-sm border rounded-md px-2 py-2 bg-white disabled:bg-gray-50"
                  data-testid="popup-frequency"
                >
                  <option value="once">Once per visitor</option>
                  <option value="session">Once per session</option>
                  <option value="always">Every visit</option>
                </select>
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider text-gray-500">Show after (seconds)</Label>
                <Input
                  type="number" min={0} max={60}
                  value={popup.delay_seconds ?? 2}
                  onChange={(e) => setPopup({ ...popup, delay_seconds: Number(e.target.value) })}
                  disabled={!isSuperAdmin}
                  data-testid="popup-delay"
                />
              </div>
              <div className="flex items-end">
                <div className="flex items-center justify-between gap-3 border rounded-lg p-2.5 w-full">
                  <Label className="text-xs">Email capture</Label>
                  <Switch
                    checked={!!popup.show_email_capture}
                    onCheckedChange={(v) => setPopup({ ...popup, show_email_capture: v })}
                    disabled={!isSuperAdmin}
                    data-testid="popup-email-capture"
                  />
                </div>
              </div>
            </div>

            {popup.show_email_capture && (
              <div className="border-t pt-4">
                <div className="flex items-center justify-between border rounded-lg p-3 bg-amber-50/30">
                  <div className="min-w-0 pr-3">
                    <Label className="text-sm font-semibold flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                      Email a discount code on signup
                    </Label>
                    <p className="text-xs text-gray-500 mt-0.5">Mints a single-use WELCOME-XXXXXX code and emails it. The popup shows "Check your inbox" — code is never displayed on screen.</p>
                  </div>
                  <Switch
                    checked={!!popup.coupon_enabled}
                    onCheckedChange={(v) => setPopup({ ...popup, coupon_enabled: v })}
                    disabled={!isSuperAdmin}
                    data-testid="popup-coupon-toggle"
                  />
                </div>
                {popup.coupon_enabled && (
                  <div className="grid md:grid-cols-2 gap-4 mt-3">
                    <div>
                      <Label className="text-xs uppercase tracking-wider text-gray-500">Discount %</Label>
                      <Input
                        type="number" min={1} max={50}
                        value={popup.coupon_percent ?? 10}
                        onChange={(e) => setPopup({ ...popup, coupon_percent: Number(e.target.value) })}
                        disabled={!isSuperAdmin}
                        data-testid="popup-coupon-percent"
                      />
                    </div>
                    <div>
                      <Label className="text-xs uppercase tracking-wider text-gray-500">Code expiry (days)</Label>
                      <Input
                        type="number" min={1} max={120}
                        value={popup.coupon_expires_days ?? 30}
                        onChange={(e) => setPopup({ ...popup, coupon_expires_days: Number(e.target.value) })}
                        disabled={!isSuperAdmin}
                        data-testid="popup-coupon-expiry"
                      />
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="flex justify-end">
              <Button onClick={savePopup} disabled={!isSuperAdmin || saving} data-testid="popup-save">
                <Save className="w-4 h-4 mr-1" />
                {saving ? 'Saving…' : 'Save welcome popup'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Storefront toast messages */}
      {messages && (
        <Card data-testid="storefront-messages-card">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-emerald-600" />
              Storefront messages
            </CardTitle>
            <p className="text-xs text-gray-500">
              Edit the wording, on/off and duration of transient toast messages shown on the live storefront.
              Use <code className="bg-gray-100 px-1 rounded text-[11px]">{'{savings}'}</code> in the trade-login text — it gets replaced with the £ amount the user just saved on their cart.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {[
              { key: 'trade_login_toast', icon: LogIn, title: 'Trade login (cart re-priced)', desc: 'Shown when a guest signs in as trade and the cart switches to trade pricing. Skipped if the cart is empty or savings are £0.' },
              { key: 'trade_logout_toast', icon: LogOut, title: 'Trade logout', desc: 'Shown when a logged-in trade user logs out and the cart reverts to retail pricing.' },
            ].map(({ key, icon: Icon, title, desc }) => {
              const m = messages[key] || {};
              const previewMessage = () => {
                // Fire the actual toast with sample {savings} so admins can see
                // exactly how their wording will land — same style + duration as
                // the live storefront watcher uses.
                const text = (m.text || '').replace('{savings}', '42.50');
                const opts = {
                  duration: m.duration_ms || 5000,
                  id: `preview-${key}`,
                };
                if (key === 'trade_login_toast') {
                  toast.success(text, opts);
                } else {
                  toast(text, opts);
                }
              };
              return (
                <div key={key} className="border rounded-lg p-4 space-y-3" data-testid={`message-${key}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 min-w-0">
                      <div className="w-9 h-9 rounded-md bg-emerald-50 text-emerald-700 flex items-center justify-center shrink-0">
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-semibold text-gray-900 text-sm">{title}</p>
                        <p className="text-xs text-gray-500 mt-0.5">{desc}</p>
                      </div>
                    </div>
                    <Switch
                      checked={!!m.enabled}
                      onCheckedChange={(v) => saveMessages(key, { enabled: v })}
                      disabled={!isSuperAdmin || saving}
                      data-testid={`message-${key}-toggle`}
                    />
                  </div>
                  {m.enabled && (
                    <div className="ml-12 space-y-3">
                      <div>
                        <Label className="text-xs uppercase tracking-wider text-gray-500">Message text</Label>
                        <Input
                          value={m.text || ''}
                          onChange={(e) => setMessages({ ...messages, [key]: { ...m, text: e.target.value } })}
                          onBlur={() => saveMessages(key, { text: m.text })}
                          placeholder="Welcome back…"
                          maxLength={280}
                          disabled={!isSuperAdmin}
                          data-testid={`message-${key}-text`}
                        />
                        <p className="text-[11px] text-gray-400 mt-1">{(m.text || '').length}/280</p>
                      </div>
                      <div className="flex items-end gap-3">
                        <div className="max-w-xs flex-1">
                          <Label className="text-xs uppercase tracking-wider text-gray-500">Duration (seconds)</Label>
                          <Input
                            type="number"
                            min={1.5}
                            max={30}
                            step={0.5}
                            value={Math.round(((m.duration_ms ?? 5000) / 1000) * 10) / 10}
                            onChange={(e) => setMessages({ ...messages, [key]: { ...m, duration_ms: Math.round(Number(e.target.value) * 1000) } })}
                            onBlur={() => saveMessages(key, { duration_ms: m.duration_ms })}
                            disabled={!isSuperAdmin}
                            data-testid={`message-${key}-duration`}
                          />
                        </div>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={previewMessage}
                          disabled={!m.text}
                          data-testid={`message-${key}-preview`}
                          title={key === 'trade_login_toast' ? 'Sample: {savings} = £42.50' : undefined}
                        >
                          <Eye className="w-4 h-4 mr-1" />
                          Preview
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
      {/* In-store trade credit accrual */}
      {messages && (
        <Card data-testid="in-store-credit-card">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Wallet className="w-4 h-4 text-amber-600" />
              In-store trade credit
            </CardTitle>
            <p className="text-xs text-gray-500">
              When ON, every EPOS invoice whose customer email or phone matches a trade account
              will automatically credit-back the customer at their tier rate (same as online orders).
              Lifetime spend & their <code className="bg-gray-100 px-1 rounded text-[11px]">T-NNNNN</code> reference are stamped on the invoice for full audit.
            </p>
          </CardHeader>
          <CardContent>
            <div className="border rounded-lg p-4 flex items-start justify-between gap-3" data-testid="message-in_store_credit">
              <div className="flex items-start gap-3 min-w-0">
                <div className="w-9 h-9 rounded-md bg-amber-50 text-amber-700 flex items-center justify-center shrink-0">
                  <Wallet className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <p className="font-semibold text-gray-900 text-sm">Accrue trade credit on EPOS invoices</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Default: OFF. Turn this on once you&apos;re ready for in-store purchases to feed into the same
                    credit balance trade customers earn online.
                  </p>
                </div>
              </div>
              <Switch
                checked={!!messages?.in_store_credit?.enabled}
                onCheckedChange={(v) => saveMessages('in_store_credit', { enabled: v })}
                disabled={!isSuperAdmin || saving}
                data-testid="in-store-credit-toggle"
              />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
