import React, { useEffect, useState, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import {
  QrCode, Gift, ClipboardList, Search as SearchIcon,
  Download, Copy, Check, AlertTriangle, Printer, ExternalLink,
  Loader2, RefreshCw, ChevronDown, ChevronUp,
  FileEdit, Save, Sparkles, SkipForward, History, Wand2,
  TrendingDown, TrendingUp, Target,
} from 'lucide-react';
import { QRCodeCanvas } from 'qrcode.react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Card } from '../ui/card';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Marketing & SEO extensions — 4 admin panels appended to the existing
 * /admin/marketing page (campaigns / showrooms / customers stay untouched).
 *
 * Tabs:
 *   - qr        Trade-signup QR code generator (per-showroom landing + UTM)
 *   - referrals Referral programme rule editor (3 configurable triggers)
 *   - leads     Showroom email-capture leads viewer + CSV export
 *   - seo       Read-only audit (sitemap, robots, homepage meta, product desc coverage)
 *
 * Each panel is gated by `activeTab` so only one mounts at a time. Settings
 * live under the `marketing` key in `website_settings` (see backend).
 */
export const MarketingExtensions = ({ activeTab }) => {
  const [settings, setSettings] = useState(null);
  const [loadingSettings, setLoadingSettings] = useState(false);

  const fetchSettings = async () => {
    setLoadingSettings(true);
    try {
      const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
      const res = await axios.get(`${API_URL}/api/marketing/admin/settings`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setSettings(res.data);
    } catch (e) {
      toast.error('Could not load marketing settings');
    } finally {
      setLoadingSettings(false);
    }
  };

  useEffect(() => {
    if (['qr', 'referrals', 'leads'].includes(activeTab) && !settings) {
      fetchSettings();
    }
  }, [activeTab]);

  const saveSettings = async (patch) => {
    const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
    try {
      const res = await axios.put(`${API_URL}/api/marketing/admin/settings`, patch, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setSettings(res.data);
      toast.success('Saved');
      return res.data;
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not save');
      throw e;
    }
  };

  if (!['qr', 'referrals', 'leads', 'seo', 'seo-drafts'].includes(activeTab)) return null;

  if (loadingSettings && !settings && !['seo', 'seo-drafts'].includes(activeTab)) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground py-12 justify-center">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div data-testid={`marketing-panel-${activeTab}`}>
      {activeTab === 'qr' && settings && (
        <QrPanel settings={settings} onSave={saveSettings} />
      )}
      {activeTab === 'referrals' && settings && (
        <ReferralsPanel settings={settings} onSave={saveSettings} />
      )}
      {activeTab === 'leads' && settings && (
        <LeadsPanel settings={settings} onSave={saveSettings} />
      )}
      {activeTab === 'seo' && <SeoPanel />}
      {activeTab === 'seo-drafts' && <SeoDraftsPanel />}
    </div>
  );
};


/* ───────────────────────── QR PANEL ─────────────────────────── */

const QrPanel = ({ settings, onSave }) => {
  const qr = settings.qr || {};
  const def = qr.default || {};
  const [draft, setDraft] = useState({
    label: def.label || 'Trade Signup',
    destination: def.destination || '/shop/trade/register',
    utm_source: def.utm_source || 'showroom_qr',
    utm_medium: def.utm_medium || 'print',
    utm_campaign: def.utm_campaign || 'trade_signup',
    utm_content: def.utm_content || 'default',
  });
  const qrRef = useRef(null);

  const origin = window.location.origin;
  const fullUrl = (() => {
    const dest = (draft.destination || '/').startsWith('http')
      ? draft.destination
      : `${origin}${draft.destination.startsWith('/') ? '' : '/'}${draft.destination}`;
    const params = new URLSearchParams();
    if (draft.utm_source) params.set('utm_source', draft.utm_source);
    if (draft.utm_medium) params.set('utm_medium', draft.utm_medium);
    if (draft.utm_campaign) params.set('utm_campaign', draft.utm_campaign);
    if (draft.utm_content) params.set('utm_content', draft.utm_content);
    const sep = dest.includes('?') ? '&' : '?';
    return params.toString() ? `${dest}${sep}${params.toString()}` : dest;
  })();

  const handleSave = () =>
    onSave({ qr: { ...qr, default: draft } });

  const handleDownload = () => {
    const canvas = qrRef.current?.querySelector('canvas');
    if (!canvas) return;
    const url = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = url;
    a.download = `tile-station-trade-qr-${draft.utm_content || 'default'}.png`;
    a.click();
  };

  const handleCopyUrl = async () => {
    try {
      await navigator.clipboard.writeText(fullUrl);
      toast.success('URL copied');
    } catch {
      toast.error('Could not copy');
    }
  };

  const handlePrint = () => {
    const w = window.open('', '_blank');
    if (!w) return;
    const canvas = qrRef.current?.querySelector('canvas');
    const dataUrl = canvas ? canvas.toDataURL('image/png') : '';
    w.document.write(`
      <html><head><title>${draft.label}</title>
      <style>
        body { font-family: -apple-system, system-ui, sans-serif; text-align: center; padding: 40px; }
        h1 { font-size: 28px; margin: 0 0 8px; }
        p { color: #555; margin: 0 0 24px; }
        img { width: 320px; height: 320px; }
        .url { font-family: ui-monospace, monospace; font-size: 11px; color: #777; margin-top: 16px; word-break: break-all; }
      </style></head>
      <body>
        <h1>Trade Account — Scan to Sign Up</h1>
        <p>Get exclusive trade discounts &amp; credit-back rewards</p>
        <img src="${dataUrl}" alt="QR" />
        <div class="url">${fullUrl}</div>
        <script>window.onload=()=>setTimeout(()=>window.print(),200)</script>
      </body></html>
    `);
    w.document.close();
  };

  return (
    <Card className="p-6 space-y-6" data-testid="qr-panel">
      <div>
        <h2 className="text-xl font-bold">Trade-signup QR code</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Print and place at the till. Scanning opens your trade-signup page
          with UTM tags so you can track conversions in Google Analytics.
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="space-y-3">
          <div>
            <Label>Display label (for staff reference)</Label>
            <Input
              value={draft.label}
              onChange={(e) => setDraft({ ...draft, label: e.target.value })}
              data-testid="qr-label-input"
            />
          </div>
          <div>
            <Label>Destination URL or path</Label>
            <Input
              value={draft.destination}
              onChange={(e) => setDraft({ ...draft, destination: e.target.value })}
              placeholder="/shop/trade/register"
              data-testid="qr-destination-input"
            />
            <p className="text-[11px] text-muted-foreground mt-1">
              Relative paths use the current site origin. You can paste a full
              URL to point at any campaign landing page.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>utm_source</Label>
              <Input value={draft.utm_source} onChange={(e) => setDraft({ ...draft, utm_source: e.target.value })} />
            </div>
            <div>
              <Label>utm_medium</Label>
              <Input value={draft.utm_medium} onChange={(e) => setDraft({ ...draft, utm_medium: e.target.value })} />
            </div>
            <div>
              <Label>utm_campaign</Label>
              <Input value={draft.utm_campaign} onChange={(e) => setDraft({ ...draft, utm_campaign: e.target.value })} />
            </div>
            <div>
              <Label>utm_content (showroom code)</Label>
              <Input value={draft.utm_content} onChange={(e) => setDraft({ ...draft, utm_content: e.target.value })} />
            </div>
          </div>
          <Button onClick={handleSave} className="bg-accent" data-testid="qr-save-btn">
            Save defaults
          </Button>
        </div>

        <div className="space-y-3 flex flex-col items-center bg-gray-50 p-6 rounded-lg">
          <div ref={qrRef} className="bg-white p-4 rounded">
            <QRCodeCanvas value={fullUrl} size={220} level="H" includeMargin />
          </div>
          <div className="text-[11px] font-mono text-muted-foreground break-all text-center max-w-full px-2">
            {fullUrl}
          </div>
          <div className="flex gap-2 flex-wrap justify-center">
            <Button onClick={handleDownload} variant="outline" size="sm" data-testid="qr-download-btn">
              <Download className="w-3.5 h-3.5 mr-1" />Download PNG
            </Button>
            <Button onClick={handleCopyUrl} variant="outline" size="sm" data-testid="qr-copy-url-btn">
              <Copy className="w-3.5 h-3.5 mr-1" />Copy URL
            </Button>
            <Button onClick={handlePrint} variant="outline" size="sm" data-testid="qr-print-btn">
              <Printer className="w-3.5 h-3.5 mr-1" />Print poster
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
};


/* ───────────────────────── REFERRALS PANEL ─────────────────────── */

const ReferralsPanel = ({ settings, onSave }) => {
  const r = settings.referrals || {};
  const [draft, setDraft] = useState({
    enabled: r.enabled !== false,
    trigger_signup: { ...(r.trigger_signup || {}) },
    trigger_approved: { ...(r.trigger_approved || {}) },
    trigger_first_paid: { ...(r.trigger_first_paid || {}) },
    share_message: r.share_message || '',
  });

  const updateTrigger = (key, patch) =>
    setDraft({ ...draft, [key]: { ...draft[key], ...patch } });

  const handleSave = () => onSave({ referrals: draft });

  return (
    <Card className="p-6 space-y-6" data-testid="referrals-panel">
      <div>
        <h2 className="text-xl font-bold">Referral programme</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Configure when a trader earns referral credit and how much. All three
          triggers are independent — toggle any combination ON.
        </p>
      </div>

      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={draft.enabled}
          onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
          data-testid="referrals-master-toggle"
        />
        <span className="font-medium">Programme enabled</span>
      </label>

      <TriggerCard
        title="On signup"
        subtitle="Fires the moment the referred party finishes the signup form. Highest abuse risk — recommend keeping OFF unless you trust the channel."
        trigger={draft.trigger_signup}
        onChange={(patch) => updateTrigger('trigger_signup', patch)}
        testId="trigger-signup"
      />
      <TriggerCard
        title="On trade-account approval"
        subtitle="Fires once an admin approves the referred party as a trade customer. Default — balances speed with safety."
        trigger={draft.trigger_approved}
        onChange={(patch) => updateTrigger('trigger_approved', patch)}
        testId="trigger-approved"
      />
      <TriggerCard
        title="On first paid order"
        subtitle="Fires on the referred party's first paid order at or above the minimum total. Tightest — credit only flows on real revenue."
        trigger={draft.trigger_first_paid}
        onChange={(patch) => updateTrigger('trigger_first_paid', patch)}
        testId="trigger-first-paid"
        showMinTotal
      />

      <div>
        <Label>Share message (used on the trader dashboard)</Label>
        <textarea
          value={draft.share_message}
          onChange={(e) => setDraft({ ...draft, share_message: e.target.value })}
          rows={2}
          className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
          data-testid="referrals-share-message"
        />
      </div>

      <Button onClick={handleSave} className="bg-accent" data-testid="referrals-save-btn">
        Save referral rules
      </Button>
    </Card>
  );
};

const TriggerCard = ({ title, subtitle, trigger, onChange, testId, showMinTotal }) => {
  const enabled = !!trigger.enabled;
  return (
    <div
      className={`border rounded-lg p-4 transition ${enabled ? 'bg-emerald-50/50 border-emerald-200' : 'bg-gray-50 border-gray-200'}`}
      data-testid={testId}
    >
      <label className="flex items-start gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onChange({ enabled: e.target.checked })}
          className="mt-1"
          data-testid={`${testId}-enabled`}
        />
        <div className="flex-1">
          <div className="font-semibold">{title}</div>
          <div className="text-xs text-muted-foreground mt-0.5">{subtitle}</div>
        </div>
      </label>
      {enabled && (
        <div className="grid sm:grid-cols-2 gap-3 mt-4 ml-6">
          <div>
            <Label>Referrer credit (£)</Label>
            <Input
              type="number" min={0} step={0.5}
              value={trigger.referrer_amount || 0}
              onChange={(e) => onChange({ referrer_amount: parseFloat(e.target.value || 0) })}
              data-testid={`${testId}-referrer-amount`}
            />
          </div>
          <div>
            <Label>Referee welcome credit (£)</Label>
            <Input
              type="number" min={0} step={0.5}
              value={trigger.referee_amount || 0}
              onChange={(e) => onChange({ referee_amount: parseFloat(e.target.value || 0) })}
              data-testid={`${testId}-referee-amount`}
            />
          </div>
          {showMinTotal && (
            <div className="sm:col-span-2">
              <Label>Minimum order total (£)</Label>
              <Input
                type="number" min={0} step={1}
                value={trigger.min_order_total || 0}
                onChange={(e) => onChange({ min_order_total: parseFloat(e.target.value || 0) })}
                data-testid={`${testId}-min-total`}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
};


/* ───────────────────────── LEADS PANEL ─────────────────────────── */

const LeadsPanel = ({ settings, onSave }) => {
  const lc = settings.lead_capture || {};
  const [draft, setDraft] = useState({
    enabled: lc.enabled !== false,
    title: lc.title || '',
    subtitle: lc.subtitle || '',
    consent_text: lc.consent_text || '',
    success_message: lc.success_message || '',
  });
  const [leads, setLeads] = useState({ leads: [], total: 0, loading: true });

  const fetchLeads = async () => {
    setLeads((l) => ({ ...l, loading: true }));
    try {
      const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
      const res = await axios.get(`${API_URL}/api/marketing/admin/leads?limit=100`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setLeads({ leads: res.data.leads || [], total: res.data.total || 0, loading: false });
    } catch {
      setLeads({ leads: [], total: 0, loading: false });
    }
  };

  useEffect(() => { fetchLeads(); }, []);

  const handleSave = () => onSave({ lead_capture: draft });

  const handleDownloadCsv = () => {
    const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
    fetch(`${API_URL}/api/marketing/admin/leads.csv`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'marketing-leads.csv';
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(() => toast.error('Could not download CSV'));
  };

  const publicUrl = `${window.location.origin}/showroom-signup`;

  return (
    <Card className="p-6 space-y-6" data-testid="leads-panel">
      <div>
        <h2 className="text-xl font-bold">Showroom email capture</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Public landing page <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">{publicUrl}</code>{' '}
          for the till tablet. Customers leave their email + name with explicit
          opt-in — GDPR/PECR-clean by design.
        </p>
      </div>

      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={draft.enabled}
          onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
          data-testid="leads-master-toggle"
        />
        <span className="font-medium">Lead capture enabled</span>
      </label>

      <div className="grid md:grid-cols-2 gap-3">
        <div>
          <Label>Page title</Label>
          <Input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} data-testid="leads-title" />
        </div>
        <div>
          <Label>Success message after submit</Label>
          <Input value={draft.success_message} onChange={(e) => setDraft({ ...draft, success_message: e.target.value })} />
        </div>
        <div className="md:col-span-2">
          <Label>Subtitle / explainer</Label>
          <textarea
            value={draft.subtitle}
            onChange={(e) => setDraft({ ...draft, subtitle: e.target.value })}
            rows={2}
            className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
          />
        </div>
        <div className="md:col-span-2">
          <Label>Consent checkbox text (legally important)</Label>
          <textarea
            value={draft.consent_text}
            onChange={(e) => setDraft({ ...draft, consent_text: e.target.value })}
            rows={2}
            className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
          />
        </div>
      </div>

      <Button onClick={handleSave} className="bg-accent" data-testid="leads-save-btn">
        Save copy
      </Button>

      <div className="border-t pt-6">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="font-semibold">Captured leads — {leads.total}</h3>
            <p className="text-xs text-muted-foreground">Most recent 100 shown</p>
          </div>
          <div className="flex gap-2">
            <Button onClick={fetchLeads} variant="outline" size="sm" data-testid="leads-refresh-btn">
              <RefreshCw className="w-3.5 h-3.5 mr-1" />Refresh
            </Button>
            <Button onClick={handleDownloadCsv} variant="outline" size="sm" data-testid="leads-csv-btn">
              <Download className="w-3.5 h-3.5 mr-1" />Export CSV
            </Button>
          </div>
        </div>

        {leads.loading ? (
          <div className="text-muted-foreground py-6 text-center"><Loader2 className="w-4 h-4 animate-spin inline mr-2" />Loading…</div>
        ) : leads.leads.length === 0 ? (
          <div className="text-muted-foreground py-8 text-center text-sm">
            No leads captured yet. Open the public page on a tablet at the till.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="leads-table">
              <thead className="text-left bg-gray-50">
                <tr>
                  <th className="px-3 py-2">When</th>
                  <th className="px-3 py-2">Name</th>
                  <th className="px-3 py-2">Email</th>
                  <th className="px-3 py-2">Showroom</th>
                  <th className="px-3 py-2">Source</th>
                </tr>
              </thead>
              <tbody>
                {leads.leads.map((l, i) => (
                  <tr key={i} className="border-t">
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {l.created_at ? new Date(l.created_at).toLocaleString('en-GB') : ''}
                    </td>
                    <td className="px-3 py-2">{l.name}</td>
                    <td className="px-3 py-2 font-mono text-xs">{l.email}</td>
                    <td className="px-3 py-2 text-xs">{l.showroom_id || '—'}</td>
                    <td className="px-3 py-2 text-xs">{l.source || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Card>
  );
};


/* ───────────────────────── SEO PANEL ─────────────────────────── */

const SeoPanel = () => {
  const [audit, setAudit] = useState(null);
  const [loading, setLoading] = useState(false);
  // Bulk SEO description generator state — tracks coverage + batch state
  // PER collection (products / tiles / supplier_products). The existing
  // *Bulk Edit Categories* tool generates richer series-level copy for
  // tiles/supplier_products; this card exposes the cheaper per-product
  // path for every collection so nothing is ever left orphaned.
  const [counts, setCounts] = useState(null);
  const [bulkRunning, setBulkRunning] = useState(null); // collection name or null
  const [bulkResult, setBulkResult] = useState(null);

  const runAudit = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
      const res = await axios.get(`${API_URL}/api/marketing/admin/seo-audit`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setAudit(res.data);
    } catch (e) {
      toast.error('Could not run SEO audit');
    } finally {
      setLoading(false);
    }
  };

  const fetchCounts = async () => {
    try {
      const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
      const res = await axios.get(`${API_URL}/api/products/missing-descriptions/count`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setCounts(res.data);
    } catch (e) {
      // Silent — non-blocking; user can still see the audit.
    }
  };

  const handleBulkGenerate = async (collection, limit) => {
    if (bulkRunning) return;
    setBulkRunning(collection);
    setBulkResult(null);
    try {
      const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
      const res = await axios.post(
        `${API_URL}/api/products/bulk-generate-descriptions`,
        { limit, collection },
        { headers: token ? { Authorization: `Bearer ${token}` } : {}, timeout: 120000 },
      );
      setBulkResult({ ...res.data, collection });
      const { succeeded = 0, failed = 0, remaining = 0 } = res.data;
      if (succeeded > 0) {
        toast.success(`${collection}: generated ${succeeded}, ${remaining} remaining`);
      } else if (failed > 0) {
        toast.error(`${collection}: all ${failed} attempts failed — see error details`);
      } else {
        toast.success(`${collection}: no products needed descriptions.`);
      }
      fetchCounts();
      runAudit();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Bulk generator failed');
    } finally {
      setBulkRunning(null);
    }
  };

  useEffect(() => { runAudit(); fetchCounts(); }, []);

  const checks = audit?.checks || {};
  const renderRow = (key, label) => {
    const c = checks[key];
    if (!c) return null;
    const ok = !!c.ok;
    return (
      <div
        key={key}
        className={`flex items-start gap-3 p-3 rounded-md border ${ok ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}
        data-testid={`seo-check-${key}`}
      >
        {ok ? <Check className="w-4 h-4 text-emerald-700 mt-0.5" /> : <AlertTriangle className="w-4 h-4 text-amber-700 mt-0.5" />}
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm">{label}</div>
          <div className="text-xs text-muted-foreground mt-0.5 break-words">{c.detail}</div>
        </div>
      </div>
    );
  };

  const CollectionRow = ({ collectionKey, label, subtitle }) => {
    const data = counts?.[collectionKey] || { total: 0, missing: 0, with_description: 0 };
    const pct = data.total > 0 ? Math.round((data.with_description / data.total) * 100) : 0;
    const running = bulkRunning === collectionKey;
    return (
      <div
        className="rounded-lg border border-amber-200 bg-white/60 p-3"
        data-testid={`seo-bulk-row-${collectionKey}`}
      >
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <div className="font-semibold text-amber-900 text-sm">{label}</div>
            <div className="text-[11px] text-amber-900/70 mt-0.5">{subtitle}</div>
          </div>
          <div className="text-right shrink-0">
            <div className="text-xs font-mono text-amber-900">
              <strong>{data.with_description}</strong> / {data.total}
              <span className="text-amber-900/60"> · {pct}%</span>
            </div>
            <div className="text-[11px] text-amber-900/70">{data.missing} missing</div>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-2.5">
          <Button
            onClick={() => handleBulkGenerate(collectionKey, 10)}
            disabled={!!bulkRunning || data.missing === 0}
            className="bg-amber-600 hover:bg-amber-700 text-white h-8 px-3 text-xs"
            data-testid={`seo-bulk-${collectionKey}-10-btn`}
          >
            {running ? <><Loader2 className="w-3 h-3 animate-spin mr-1" />Running…</> : 'Generate 10'}
          </Button>
          <Button
            onClick={() => handleBulkGenerate(collectionKey, 25)}
            disabled={!!bulkRunning || data.missing === 0}
            variant="outline"
            className="h-8 px-3 text-xs"
            data-testid={`seo-bulk-${collectionKey}-25-btn`}
          >
            Generate 25
          </Button>
          <Button
            onClick={() => handleBulkGenerate(collectionKey, 50)}
            disabled={!!bulkRunning || data.missing === 0}
            variant="outline"
            className="h-8 px-3 text-xs"
            data-testid={`seo-bulk-${collectionKey}-50-btn`}
          >
            Generate 50
          </Button>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <SearchInsightsCard />
      <Card className="p-6" data-testid="seo-audit-card">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <h2 className="text-xl font-bold">SEO health audit</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Read-only checks against the live site. Run before any major
              storefront launch to catch indexing regressions early.
            </p>
            {audit?.origin && (
              <div className="text-xs text-muted-foreground mt-1 font-mono">
                {audit.origin} <a href={audit.origin} target="_blank" rel="noopener noreferrer" className="underline inline-flex items-center gap-1"><ExternalLink className="w-3 h-3" /></a>
              </div>
            )}
          </div>
          <Button onClick={runAudit} disabled={loading} variant="outline" size="sm" data-testid="seo-rerun-btn">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <RefreshCw className="w-3.5 h-3.5 mr-1" />}
            Re-run audit
          </Button>
        </div>

        <div className="space-y-2">
          {loading && !audit && <div className="text-muted-foreground py-4 text-center"><Loader2 className="w-4 h-4 animate-spin inline mr-2" />Probing site…</div>}
          {renderRow('sitemap', 'sitemap.xml — discoverable')}
          {renderRow('robots', 'robots.txt — present and valid')}
          {renderRow('homepage_meta', 'Homepage meta tags (canonical / og:title / description)')}
          {renderRow('product_descriptions', 'Product description coverage (products collection)')}
        </div>
      </Card>

      {/* Bulk AI description generator — per-product, covers all three
          storefront product collections. Complements the series-level tool
          that already exists inside Bulk Edit Categories. */}
      <Card className="p-6 bg-gradient-to-br from-amber-50 to-yellow-50 border-amber-200" data-testid="seo-bulk-generator-card">
        <div className="flex items-start gap-3 mb-3">
          <div className="w-10 h-10 rounded-lg bg-amber-500 text-white flex items-center justify-center shrink-0">
            <SearchIcon className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-bold text-amber-900">AI per-product description generator</h3>
            <p className="text-sm text-amber-900/80 mt-1">
              Uses <strong>Claude Haiku 4.5</strong> via the Emergent universal
              key (~£0.0001 each) to write a fresh 60-word description for every
              product missing one. Writes straight to the DB. Idempotent — only
              empty rows are touched.
            </p>
          </div>
        </div>

        <div className="space-y-2.5 mt-4">
          <CollectionRow
            collectionKey="products"
            label="Products collection"
            subtitle="Shop homepage categories (tools, grouts, adhesives, published tiles)."
          />
          <CollectionRow
            collectionKey="tiles"
            label="Tiles collection"
            subtitle="Storefront tile catalogue — individual SKU-level rows."
          />
          <CollectionRow
            collectionKey="supplier_products"
            label="Supplier products"
            subtitle="Raw supplier imports — usually grouped into series for rich copy (see link below)."
          />
        </div>

        {bulkResult && (
          <div className="mt-5 pt-4 border-t border-amber-200 space-y-2" data-testid="seo-bulk-result">
            <div className="text-sm font-semibold text-amber-900">
              Last batch — <code className="font-mono">{bulkResult.collection}</code> · succeeded {bulkResult.succeeded} · failed {bulkResult.failed} · {bulkResult.remaining} remaining in this collection
            </div>
            {bulkResult.samples?.length > 0 && (
              <div className="space-y-1.5">
                {bulkResult.samples.map((s) => (
                  <div key={s.id} className="text-xs bg-white/70 rounded p-2 border border-amber-100">
                    <div className="font-semibold text-amber-900">{s.name}</div>
                    <div className="text-amber-900/70 mt-0.5 italic">{s.preview}…</div>
                  </div>
                ))}
              </div>
            )}
            {bulkResult.errors?.length > 0 && (
              <div className="space-y-1.5">
                {bulkResult.errors.map((e, i) => (
                  <div key={i} className="text-xs bg-rose-50 rounded p-2 border border-rose-200">
                    <div className="font-semibold text-rose-900">{e.name}</div>
                    <div className="text-rose-700 mt-0.5">{e.error}</div>
                  </div>
                ))}
              </div>
            )}
            <p className="text-[11px] text-amber-900/60 mt-2">
              Generated rows have <code className="font-mono">description_source: ai_bulk_haiku</code> — easy to find and polish later via the per-product editor.
            </p>
          </div>
        )}

        <div className="mt-5 pt-4 border-t border-amber-200">
          <div className="text-xs text-amber-900/80">
            <strong>Need richer, series-aware copy?</strong> The existing{' '}
            <a
              href="/admin/supplier-products"
              className="text-amber-900 font-semibold underline hover:text-amber-950"
              data-testid="seo-bulk-series-link"
            >
              Bulk Edit Categories → AI Series Description
            </a>{' '}
            tool groups products by series and writes one unified description
            per series (longer, cross-referenced, better for branded collections).
            Use that for flagship ranges; use this per-product tool to fill the
            long tail fast.
          </div>
        </div>
      </Card>

      <Card className="p-6 bg-gray-50" data-testid="seo-meta-editor-placeholder">
        <h3 className="font-bold flex items-center gap-2"><SearchIcon className="w-4 h-4" />Per-page meta editor</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Coming soon — a unified editor for page titles, meta descriptions,
          and Open Graph images across the storefront. Until then, edit
          per-product SEO fields under <strong>Products & Suppliers → Edit
          product</strong> and per-category copy under <strong>Website →
          Categories</strong>.
        </p>
      </Card>
    </div>
  );
};


/* ───────────────────────── SEARCH INSIGHTS CARD ─────────────── */
/*
 * Surfaces the signal hidden inside `search_query_log`:
 *   • Top missed searches (zero results) — SEO gap candidates
 *   • Top successful searches — SEO reinforcement candidates
 *   • "Did you mean?" chip conversion rate
 *
 * Admin can copy a keyword to clipboard (paste into product meta
 * descriptions, category copy) or download the full list as CSV.
 */
const SearchInsightsCard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(7);
  const [copied, setCopied] = useState('');

  const fetchInsights = async (d = days) => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
      const res = await axios.get(`${API_URL}/api/marketing/admin/search-insights`, {
        params: { days: d, limit: 20 },
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setData(res.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not load search insights');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchInsights(days); /* eslint-disable-next-line */ }, [days]);

  const copyKeyword = async (kw) => {
    try {
      await navigator.clipboard.writeText(kw);
      setCopied(kw);
      setTimeout(() => setCopied(''), 1200);
      toast.success(`Copied: ${kw}`);
    } catch {
      toast.error('Clipboard blocked by browser');
    }
  };

  const downloadCsv = () => {
    if (!data) return;
    const rows = [['type', 'query', 'count', 'avg_results', 'last_seen']];
    (data.top_missed || []).forEach((r) => rows.push(['missed', r.query, r.count, r.avg_results, r.last_seen]));
    (data.top_hits || []).forEach((r) => rows.push(['hit', r.query, r.count, r.avg_results, r.last_seen]));
    const csv = rows
      .map((r) => r.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(','))
      .join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `search-insights-${days}d.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const totals = data?.totals || { total_searches: 0, zero_result_searches: 0 };
  const conv = data?.suggestion_conversion || { chips_offered: 0, chips_clicked: 0, rate: 0 };
  const missed = data?.top_missed || [];
  const hits = data?.top_hits || [];

  return (
    <Card className="p-6 bg-gradient-to-br from-rose-50 to-orange-50 border-rose-200" data-testid="search-insights-card">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <h3 className="text-lg font-bold text-rose-950 flex items-center gap-2">
            <Target className="w-5 h-5" /> Search insights — what customers type
          </h3>
          <p className="text-sm text-rose-900/80 mt-1 max-w-2xl">
            Every storefront search is logged. "Missed" searches = your SEO
            gap: customers want these, you don't rank for them. "Hits" =
            intent that's already working — reinforce with more product copy.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value, 10))}
            className="h-8 px-2 text-sm border rounded bg-white"
            data-testid="search-insights-days"
          >
            <option value={1}>Last 24h</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <Button onClick={() => fetchInsights(days)} disabled={loading} variant="outline" className="h-8 px-2" data-testid="search-insights-refresh">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          </Button>
          <Button onClick={downloadCsv} disabled={!data || totals.total_searches === 0} variant="outline" className="h-8 px-2 text-xs" data-testid="search-insights-csv">
            <Download className="w-3.5 h-3.5 mr-1" /> CSV
          </Button>
          <Button
            onClick={async () => {
              if (!window.confirm('Send the weekly SEO digest to all admins now? Useful for preview / recovering from a missed cron.')) return;
              try {
                const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
                const res = await axios.post(
                  `${API_URL}/api/marketing/admin/search-insights/send-digest`, {},
                  { headers: token ? { Authorization: `Bearer ${token}` } : {} },
                );
                const r = res.data || {};
                if (r.ok && !r.skipped) {
                  toast.success(`Digest sent to ${r.recipients} admin${r.recipients === 1 ? '' : 's'} · ${r.plugged_count} plugged · ${r.still_open_count} still open`);
                } else {
                  toast.info(`Skipped — ${r.reason || 'no recipients'}`);
                }
              } catch (e) {
                toast.error(e?.response?.data?.detail || 'Could not send digest');
              }
            }}
            variant="outline"
            className="h-8 px-2 text-xs"
            data-testid="search-insights-send-digest"
          >
            ✉️ Send digest
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
        <StatCell label="Total searches" value={totals.total_searches} />
        <StatCell label="Zero-result" value={totals.zero_result_searches} color="rose" />
        <StatCell label="Suggestions offered" value={conv.chips_offered} />
        <StatCell label="Chip click rate" value={conv.chips_offered ? `${Math.round(conv.rate * 100)}%` : '—'} color="emerald" />
      </div>

      {totals.total_searches === 0 && !loading && (
        <div className="py-8 text-center text-sm text-rose-900/70" data-testid="search-insights-empty">
          No searches logged yet in this window. Come back after the site has had some traffic.
        </div>
      )}

      {missed.length > 0 && (
        <div className="mt-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-rose-900 mb-2">
            <TrendingDown className="w-4 h-4" /> SEO gap · top missed searches
          </div>
          <ul className="space-y-1" data-testid="search-insights-missed">
            {missed.map((r) => (
              <InsightRow key={`m-${r.query}`} row={r} copied={copied} onCopy={copyKeyword} variant="missed" />
            ))}
          </ul>
          <p className="text-[11px] text-rose-900/60 mt-2">
            💡 Tip: copy a keyword and paste it into a Product/Category name, description, or meta
            tag. The <a href="/admin/marketing?tab=seo-drafts" className="underline font-medium">SEO Drafts</a> queue can regenerate a draft
            with a custom steer like <em>"target the phrase marble effect"</em>.
          </p>
        </div>
      )}

      {hits.length > 0 && (
        <div className="mt-5">
          <div className="flex items-center gap-2 text-sm font-semibold text-emerald-900 mb-2">
            <TrendingUp className="w-4 h-4" /> Proven intent · top successful searches
          </div>
          <ul className="space-y-1" data-testid="search-insights-hits">
            {hits.slice(0, 10).map((r) => (
              <InsightRow key={`h-${r.query}`} row={r} copied={copied} onCopy={copyKeyword} variant="hit" />
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
};


const StatCell = ({ label, value, color }) => {
  const colorCls = color === 'rose' ? 'text-rose-800 bg-white/70 border-rose-200'
    : color === 'emerald' ? 'text-emerald-800 bg-white/70 border-emerald-200'
    : 'text-gray-800 bg-white/70 border-gray-200';
  return (
    <div className={`rounded border p-2 ${colorCls}`}>
      <div className="text-[11px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className="text-xl font-bold font-mono">{value}</div>
    </div>
  );
};


const InsightRow = ({ row, copied, onCopy, variant }) => {
  const isCopied = copied === row.query;
  const accent = variant === 'missed' ? 'text-rose-900' : 'text-emerald-900';
  const sugg = (row.sample_suggestions || []).slice(0, 2);
  return (
    <li
      className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-white/60 group"
      data-testid={`search-insights-row-${variant}-${row.query.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <code className={`flex-1 min-w-0 truncate font-mono text-sm ${accent}`}>{row.query}</code>
      {variant === 'missed' && row.products_targeting > 0 && (
        <span
          className="text-[10px] font-bold uppercase tracking-wide bg-emerald-100 text-emerald-900 px-1.5 py-0.5 rounded shrink-0"
          title={`${row.products_targeting} approved draft(s) target this phrase`}
          data-testid={`search-insights-targeted-${row.query.toLowerCase().replace(/\s+/g, '-')}`}
        >
          ✓ {row.products_targeting} targeting
        </span>
      )}
      <span className="text-[11px] text-gray-500 shrink-0">
        <strong className="text-gray-800">{row.count}×</strong>
        {variant === 'hit' && row.avg_results > 0 && <> · avg {row.avg_results} hits</>}
        {variant === 'missed' && sugg.length > 0 && (
          <span className="ml-2 text-rose-700/70">→ {sugg.join(', ')}</span>
        )}
      </span>
      {variant === 'missed' && (
        <a
          href={`/admin/marketing?tab=seo-drafts&target=${encodeURIComponent(row.query)}`}
          className="opacity-0 group-hover:opacity-100 transition px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-100 text-indigo-900 hover:bg-indigo-200 whitespace-nowrap"
          title="Create SEO draft targeting this keyword"
          data-testid={`search-insights-seodraft-${row.query.toLowerCase().replace(/\s+/g, '-')}`}
        >
          <Wand2 className="w-3 h-3 inline mr-0.5" /> SEO draft
        </a>
      )}
      <button
        onClick={() => onCopy(row.query)}
        className="opacity-0 group-hover:opacity-100 transition p-1 hover:bg-gray-200 rounded"
        title="Copy as SEO keyword"
        data-testid={`search-insights-copy-${row.query.toLowerCase().replace(/\s+/g, '-')}`}
      >
        {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-700" /> : <Copy className="w-3.5 h-3.5 text-gray-500" />}
      </button>
    </li>
  );
};


/* ───────────────────────── SEO DRAFTS PANEL ─────────────────────────── */
/*
 * Review-then-save flow — unlike the bulk generator which writes straight
 * to the product, this inbox stages AI suggestions for admin approval.
 * Scanner runs nightly (04:30 UTC) and populates `seo_description_drafts`;
 * admin can also click "Scan now" for an immediate run.
 *
 * Per-draft actions: Save (edit in place + publish), Regenerate (variant
 * dropdown + free-text custom steer), Skip (scanner stops suggesting),
 * History (browse all prior drafts for the same product).
 */

const VARIANT_OPTIONS = [
  { value: 'default', label: 'Default — 55-65 words, balanced' },
  { value: 'shorter', label: 'Shorter — 35-45 words, tighter' },
  { value: 'more_technical', label: 'More technical — specs, material science' },
  { value: 'warmer', label: 'Warmer — inviting, evoke the space' },
  { value: 'benefits_focused', label: 'Benefits-first — lead with outcomes' },
];


const relativeTime = (iso) => {
  if (!iso) return '—';
  try {
    const ms = Date.now() - new Date(iso).getTime();
    const s = Math.round(ms / 1000);
    if (s < 60) return `${s}s ago`;
    const m = Math.round(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.round(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.round(h / 24);
    return `${d}d ago`;
  } catch {
    return iso;
  }
};


const SeoDraftsPanel = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [searchParams, setSearchParams] = useSearchParams();
  // A missed-keyword deep-link from the Search Insights card — when set,
  // every draft card gets a pre-filled custom_instruction targeting this
  // phrase, so the admin just clicks Regenerate on a relevant product.
  const targetKeyword = (searchParams.get('target') || '').trim();
  const prefillInstruction = targetKeyword
    ? `Rewrite to naturally target the search phrase "${targetKeyword}". Include the phrase once (verbatim) and one or two near-synonyms customers actually search for. Do not stuff; keep it factual.`
    : '';

  const clearTarget = () => {
    const next = new URLSearchParams(searchParams);
    next.delete('target');
    setSearchParams(next, { replace: true });
  };

  const fetchDrafts = async (status = statusFilter) => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
      const res = await axios.get(`${API_URL}/api/marketing/seo-drafts`, {
        params: { status, limit: 100 },
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setData(res.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not load SEO drafts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDrafts(statusFilter); /* eslint-disable-next-line */ }, [statusFilter]);

  const handleScanNow = async () => {
    if (scanning) return;
    if (!window.confirm('Scan the catalogue now for products missing descriptions and stage fresh drafts? This uses the Emergent LLM key (~£0.0001 per draft).')) return;
    setScanning(true);
    try {
      const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
      const res = await axios.post(`${API_URL}/api/marketing/seo-drafts/scan`, {}, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        timeout: 180000,
      });
      const { generated = 0, processed = 0, skipped, reason } = res.data || {};
      if (skipped) {
        toast.info(`Scan skipped — ${reason || 'daily budget exhausted'}`);
      } else {
        toast.success(`Scanned: generated ${generated} new draft${generated === 1 ? '' : 's'} (processed ${processed})`);
      }
      fetchDrafts(statusFilter);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Scan failed');
    } finally {
      setScanning(false);
    }
  };

  const drafts = data?.drafts || [];
  const totals = data?.totals || { pending: 0, approved: 0, skipped: 0 };
  const lastRun = data?.last_run;
  const limits = data?.limits || {};

  return (
    <div className="space-y-5" data-testid="seo-drafts-panel">
      {targetKeyword && (
        <Card className="p-4 bg-gradient-to-r from-indigo-100 to-violet-100 border-indigo-300 flex items-start justify-between gap-3" data-testid="seo-drafts-target-banner">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-indigo-950 font-semibold text-sm">
              <Target className="w-4 h-4" /> Targeting keyword: <code className="bg-white/70 px-1.5 rounded">{targetKeyword}</code>
            </div>
            <p className="text-xs text-indigo-900/80 mt-1">
              Customers searched this but found nothing. Find a relevant product below and click
              <strong> Regenerate</strong> — the custom-instruction is pre-filled to weave this phrase in naturally.
            </p>
          </div>
          <button
            onClick={clearTarget}
            className="text-xs text-indigo-900 hover:bg-white/60 rounded px-2 py-1 shrink-0"
            data-testid="seo-drafts-clear-target"
          >
            Clear
          </button>
        </Card>
      )}

      {/* Header / status strip */}
      <Card className="p-5 bg-gradient-to-br from-indigo-50 to-violet-50 border-indigo-200">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-xl font-bold text-indigo-950 flex items-center gap-2">
              <FileEdit className="w-5 h-5" /> SEO Drafts — review queue
            </h2>
            <p className="text-sm text-indigo-900/80 mt-1 max-w-2xl">
              AI-generated descriptions staged here for your review. Nothing
              is published to the live storefront until you click <strong>Save</strong>.
              The scanner runs nightly at 04:30 UTC; run it now for fresh suggestions.
            </p>
            <div className="text-xs text-indigo-900/70 mt-2 font-mono">
              Last run: <strong>{lastRun?.at ? relativeTime(lastRun.at) : 'never'}</strong>
              {lastRun?.generated != null && <> · generated {lastRun.generated}</>}
              {lastRun?.force && <> · manual</>}
              {limits?.max_per_run && <> · per-run cap {limits.max_per_run}</>}
              {limits?.max_per_day && <> · daily cap {limits.max_per_day}</>}
            </div>
          </div>
          <Button
            onClick={handleScanNow}
            disabled={scanning}
            className="bg-indigo-600 hover:bg-indigo-700 text-white"
            data-testid="seo-drafts-scan-now-btn"
          >
            {scanning ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Scanning…</> : <><Sparkles className="w-4 h-4 mr-2" />Scan now</>}
          </Button>
        </div>

        <div className="flex flex-wrap gap-2 mt-4">
          {['pending', 'approved', 'skipped'].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition ${
                statusFilter === s
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-white text-indigo-900 border-indigo-200 hover:border-indigo-400'
              }`}
              data-testid={`seo-drafts-filter-${s}`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)} ({totals[s] || 0})
            </button>
          ))}
        </div>
      </Card>

      {loading && !data && (
        <div className="text-center text-muted-foreground py-8">
          <Loader2 className="w-4 h-4 animate-spin inline mr-2" /> Loading drafts…
        </div>
      )}

      {data && drafts.length === 0 && (
        <Card className="p-10 text-center" data-testid="seo-drafts-empty">
          <FileEdit className="w-10 h-10 text-gray-400 mx-auto mb-2" />
          <p className="text-muted-foreground">
            {statusFilter === 'pending'
              ? 'No pending drafts — click “Scan now” to search for products missing descriptions.'
              : `No ${statusFilter} drafts yet.`}
          </p>
        </Card>
      )}

      {drafts.map((draft) => (
        <SeoDraftCard key={draft.id} draft={draft} onChanged={() => fetchDrafts(statusFilter)} prefillInstruction={prefillInstruction} />
      ))}
    </div>
  );
};


const SeoDraftCard = ({ draft, onChanged, prefillInstruction = '' }) => {
  const lastDraft = (draft.drafts && draft.drafts[draft.drafts.length - 1]) || {};
  const [editText, setEditText] = useState(lastDraft.text || '');
  const [variant, setVariant] = useState('default');
  const [customInstruction, setCustomInstruction] = useState(prefillInstruction);
  const [regenerating, setRegenerating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [skipping, setSkipping] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showCustom, setShowCustom] = useState(Boolean(prefillInstruction));
  // Read the current ?target= keyword (if any) so we can stamp it onto
  // the draft when the admin approves — Search Insights uses these stamps
  // to display "✓ N products targeting this phrase".
  const [currentSearchParams] = useSearchParams();
  const activeTargetKeyword = (currentSearchParams.get('target') || '').trim();

  useEffect(() => {
    // Re-sync edit area when the draft history grows (regenerate appended).
    const fresh = (draft.drafts || [])[(draft.drafts || []).length - 1];
    if (fresh) setEditText(fresh.text || '');
    // eslint-disable-next-line
  }, [draft.drafts?.length]);

  // When a missed-keyword deep-link arrives after the card has mounted,
  // pre-fill the custom instruction + auto-open the drawer so the admin
  // can just hit Regenerate.
  useEffect(() => {
    if (prefillInstruction) {
      setCustomInstruction(prefillInstruction);
      setShowCustom(true);
    }
  }, [prefillInstruction]);

  const token = () => localStorage.getItem('token') || localStorage.getItem('access_token') || '';

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const res = await axios.post(
        `${API_URL}/api/marketing/seo-drafts/${draft.id}/regenerate`,
        { variant, custom_instruction: customInstruction || null },
        { headers: { Authorization: `Bearer ${token()}` }, timeout: 60000 },
      );
      const updated = res.data?.draft;
      const latest = updated?.drafts?.[updated.drafts.length - 1];
      if (latest) setEditText(latest.text || '');
      toast.success('Fresh draft generated');
      if (onChanged) onChanged();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Regenerate failed');
    } finally {
      setRegenerating(false);
    }
  };

  const handleApprove = async () => {
    if (!editText.trim()) {
      toast.error('Description cannot be empty');
      return;
    }
    setApproving(true);
    try {
      await axios.post(
        `${API_URL}/api/marketing/seo-drafts/${draft.id}/approve`,
        {
          description: editText.trim(),
          target_keyword: activeTargetKeyword || null,
        },
        { headers: { Authorization: `Bearer ${token()}` } },
      );
      toast.success(
        activeTargetKeyword
          ? `Published — ${draft.product_name} now targets "${activeTargetKeyword}"`
          : `Published — ${draft.product_name} is now live`
      );
      if (onChanged) onChanged();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally {
      setApproving(false);
    }
  };

  const handleSkip = async () => {
    if (!window.confirm(`Skip this draft? The scanner will stop suggesting for "${draft.product_name}" until you reset it.`)) return;
    setSkipping(true);
    try {
      await axios.post(
        `${API_URL}/api/marketing/seo-drafts/${draft.id}/skip`,
        {},
        { headers: { Authorization: `Bearer ${token()}` } },
      );
      toast.success('Skipped');
      if (onChanged) onChanged();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Skip failed');
    } finally {
      setSkipping(false);
    }
  };

  const isPending = draft.status === 'pending';
  const historyCount = (draft.drafts || []).length;

  return (
    <Card className="p-5" data-testid={`seo-draft-card-${draft.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <div className="font-semibold text-gray-900 flex items-center gap-2 flex-wrap">
            {draft.product_name}
            <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
              {draft.collection}
            </span>
            {draft.product_category && (
              <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                {draft.product_category}
              </span>
            )}
            <span className={`text-xs px-2 py-0.5 rounded capitalize ${
              draft.status === 'pending' ? 'bg-amber-100 text-amber-900'
              : draft.status === 'approved' ? 'bg-emerald-100 text-emerald-900'
              : 'bg-gray-200 text-gray-700'
            }`}>
              {draft.status}
            </span>
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            Draft #{historyCount} · suggested {relativeTime(draft.last_generated_at)}
            {draft.approved_at && <> · approved {relativeTime(draft.approved_at)} by {draft.approved_by || '—'}</>}
          </div>
        </div>
      </div>

      {draft.current_description && (
        <details className="mb-3 group">
          <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
            Show current (live) description ▾
          </summary>
          <div className="mt-2 p-3 bg-gray-50 rounded text-xs text-gray-700 border border-gray-200">
            {draft.current_description}
          </div>
        </details>
      )}

      <div className="text-xs font-semibold text-gray-700 mb-1 flex items-center gap-2">
        Suggested copy {lastDraft.variant && lastDraft.variant !== 'default' && (
          <span className="bg-violet-100 text-violet-900 px-1.5 py-0.5 rounded font-normal">{lastDraft.variant}</span>
        )}
      </div>
      <textarea
        value={editText}
        onChange={(e) => setEditText(e.target.value)}
        disabled={!isPending}
        className="w-full border rounded-md p-3 text-sm min-h-[110px] font-serif leading-relaxed focus:ring-2 focus:ring-indigo-300"
        data-testid={`seo-draft-textarea-${draft.id}`}
      />
      <div className="text-[11px] text-muted-foreground mt-1">
        {editText.length} chars · you can edit freely before saving
      </div>

      {isPending && (
        <>
          <div className="flex flex-wrap gap-2 items-end mt-4">
            <div className="flex-1 min-w-[220px]">
              <Label className="text-xs">Variant</Label>
              <select
                value={variant}
                onChange={(e) => setVariant(e.target.value)}
                className="w-full border rounded-md px-2 py-1.5 text-sm"
                data-testid={`seo-draft-variant-${draft.id}`}
              >
                {VARIANT_OPTIONS.map((v) => (
                  <option key={v.value} value={v.value}>{v.label}</option>
                ))}
              </select>
            </div>
            <Button
              onClick={() => setShowCustom((v) => !v)}
              variant="outline"
              className="h-9"
              data-testid={`seo-draft-toggle-custom-${draft.id}`}
            >
              <Wand2 className="w-4 h-4 mr-1" /> {showCustom ? 'Hide' : 'Custom'} tweak
            </Button>
            <Button
              onClick={handleRegenerate}
              disabled={regenerating}
              variant="outline"
              className="h-9 border-violet-300 text-violet-900 hover:bg-violet-50"
              data-testid={`seo-draft-regenerate-${draft.id}`}
            >
              {regenerating ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <RefreshCw className="w-4 h-4 mr-1" />}
              Regenerate
            </Button>
          </div>

          {showCustom && (
            <div className="mt-3">
              <Label className="text-xs">Extra instruction (optional, e.g. “mention underfloor heating”, “shorter”, “no adjectives”)</Label>
              <Input
                value={customInstruction}
                onChange={(e) => setCustomInstruction(e.target.value.slice(0, 400))}
                placeholder="Keep concise, mention that it's rectified, no marketing fluff"
                data-testid={`seo-draft-custom-${draft.id}`}
              />
              <div className="text-[11px] text-muted-foreground mt-1">
                Max 400 chars · augments the preset variant, doesn't override it
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t">
            <Button
              onClick={handleApprove}
              disabled={approving || !editText.trim()}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              data-testid={`seo-draft-approve-${draft.id}`}
            >
              {approving ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Save className="w-4 h-4 mr-1" />}
              Save &amp; publish
            </Button>
            <Button
              onClick={handleSkip}
              disabled={skipping}
              variant="outline"
              className="text-gray-700"
              data-testid={`seo-draft-skip-${draft.id}`}
            >
              {skipping ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <SkipForward className="w-4 h-4 mr-1" />}
              Skip
            </Button>
            {historyCount > 1 && (
              <Button
                onClick={() => setShowHistory((v) => !v)}
                variant="ghost"
                className="text-indigo-700"
                data-testid={`seo-draft-history-toggle-${draft.id}`}
              >
                <History className="w-4 h-4 mr-1" /> {showHistory ? 'Hide' : 'Show'} history ({historyCount})
              </Button>
            )}
          </div>
        </>
      )}

      {draft.status === 'approved' && draft.approved_text && (
        <div className="mt-3 p-3 bg-emerald-50 rounded text-sm text-emerald-900 border border-emerald-200">
          <strong>Published copy:</strong> {draft.approved_text}
        </div>
      )}

      {showHistory && historyCount > 1 && (
        <div className="mt-4 space-y-2" data-testid={`seo-draft-history-${draft.id}`}>
          {(draft.drafts || []).slice(0, -1).reverse().map((h, i) => (
            <div key={h.id || i} className="p-3 bg-gray-50 border rounded text-xs">
              <div className="flex items-center justify-between mb-1">
                <div className="font-semibold text-gray-700">
                  {h.variant || 'default'}
                  {h.custom_instruction && <span className="ml-2 text-violet-700 font-normal">· “{h.custom_instruction}”</span>}
                </div>
                <div className="text-gray-500">{relativeTime(h.created_at)}</div>
              </div>
              <div className="text-gray-800 leading-relaxed">{h.text}</div>
              {isPending && (
                <button
                  onClick={() => setEditText(h.text || '')}
                  className="text-indigo-700 hover:underline mt-2 text-[11px]"
                  data-testid={`seo-draft-history-restore-${draft.id}-${i}`}
                >
                  Use this version →
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};


export default MarketingExtensions;
