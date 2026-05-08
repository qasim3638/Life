/**
 * StealthPerformanceCard
 * ──────────────────────
 * Stealth-keyword PERFORMANCE attribution — sits below
 * StealthKeywordsCard on /admin/seo.
 *
 * Shows the admin which of the supplier-original names ARE actually
 * driving Google clicks (vs the customer-facing brand names) by
 * joining live GSC data with the catalogue's stealth keywords.
 *
 * Sections:
 *   • 3 KPI cards — stealth clicks / brand clicks / other clicks
 *     with share % of the total
 *   • Top winners — the supplier names ranked by attributed clicks
 *   • "Missed wins" — high-impression GSC queries we DON'T yet
 *     target with stealth keywords; one-click promote to a product
 *     or collection
 *   • Underperformers — keywords set in the DB but with zero GSC
 *     traffic (delete or accept as long-tail)
 *
 * Cached server-side for 1 hour; the Refresh button bypasses the cache.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import {
  Loader2, BarChart3, TrendingUp, Target, AlertTriangle, Plus,
  RefreshCw, Trophy, Search, Eye, Mail, Send,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const token = () => localStorage.getItem('token') || localStorage.getItem('access_token') || '';
const authHeaders = () => ({ headers: { Authorization: `Bearer ${token()}` } });

const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString());
const pct = (v) => (v == null ? '—' : `${(Number(v) * 100).toFixed(1)}%`);


const StealthPerformanceCard = () => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [opened, setOpened] = useState(false);
  const [days, setDays] = useState(28);
  const [refreshing, setRefreshing] = useState(false);
  const [collections, setCollections] = useState([]);
  const [promoting, setPromoting] = useState(null);
  const [digest, setDigest] = useState(null);
  const [digestSaving, setDigestSaving] = useState(false);
  const [digestSending, setDigestSending] = useState(false);
  const [recipientsDraft, setRecipientsDraft] = useState('');
  const [apHistory, setApHistory] = useState([]);
  const [apUndoing, setApUndoing] = useState(null);
  const [minImprDraft, setMinImprDraft] = useState(20);
  const [batchMaxDraft, setBatchMaxDraft] = useState(5);

  const load = useCallback(async (force = false) => {
    if (!opened) return;
    setLoading(!report);
    setRefreshing(force);
    try {
      const r = await axios.get(`${API_URL}/api/admin/seo/stealth-keywords/performance`, {
        ...authHeaders(),
        params: { days, refresh: force },
        timeout: 60000,
      });
      setReport(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not load performance data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [days, opened, report]);

  useEffect(() => { load(false); /* eslint-disable-next-line */ }, [days, opened]);

  const loadCollections = useCallback(async () => {
    if (collections.length > 0) return;
    try {
      const c = await axios.get(`${API_URL}/api/admin/seo/stealth-keywords/collections`, authHeaders());
      setCollections(c.data.collections || []);
    } catch {
      // soft-fail — promote dialog will fall back to free-form input
    }
  }, [collections.length]);

  useEffect(() => { if (opened) loadCollections(); }, [opened, loadCollections]);

  const loadDigestSettings = useCallback(async () => {
    if (!opened) return;
    try {
      const r = await axios.get(`${API_URL}/api/admin/seo/stealth-keywords/digest/settings`, authHeaders());
      setDigest(r.data);
      setRecipientsDraft((r.data.recipients || []).join(', '));
      setMinImprDraft(r.data.auto_promote_min_impressions || 20);
      setBatchMaxDraft(r.data.auto_promote_batch_max || 5);
    } catch (e) {
      // soft-fail — not critical
    }
  }, [opened]);

  useEffect(() => { loadDigestSettings(); }, [loadDigestSettings]);

  const loadApHistory = useCallback(async () => {
    if (!opened) return;
    try {
      const r = await axios.get(
        `${API_URL}/api/admin/seo/stealth-keywords/auto-promote/history`,
        { ...authHeaders(), params: { limit: 10 } },
      );
      setApHistory(r.data.rows || []);
    } catch (e) {
      // soft-fail
    }
  }, [opened]);

  useEffect(() => { loadApHistory(); }, [loadApHistory]);

  const toggleAutoPromote = async (enabled) => {
    setDigestSaving(true);
    try {
      const r = await axios.put(
        `${API_URL}/api/admin/seo/stealth-keywords/digest/settings`,
        { auto_promote_enabled: enabled }, authHeaders(),
      );
      setDigest(r.data);
      toast.success(enabled
        ? 'Auto-promote enabled — runs every Monday 08:00 BST'
        : 'Auto-promote paused');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not update');
    } finally {
      setDigestSaving(false);
    }
  };

  const saveMinImpressions = async () => {
    setDigestSaving(true);
    try {
      const r = await axios.put(
        `${API_URL}/api/admin/seo/stealth-keywords/digest/settings`,
        { auto_promote_min_impressions: minImprDraft }, authHeaders(),
      );
      setDigest(r.data);
      setMinImprDraft(r.data.auto_promote_min_impressions);
      toast.success(`Auto-promote threshold set to ${r.data.auto_promote_min_impressions} impressions`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not update');
    } finally {
      setDigestSaving(false);
    }
  };

  const toggleBatchMode = async (enabled) => {
    setDigestSaving(true);
    try {
      const r = await axios.put(
        `${API_URL}/api/admin/seo/stealth-keywords/digest/settings`,
        { auto_promote_batch_mode: enabled }, authHeaders(),
      );
      setDigest(r.data);
      toast.success(enabled
        ? `Batch mode ON — up to ${r.data.auto_promote_batch_max} promotions/week (2× impressions bar)`
        : 'Batch mode OFF — back to 1 promotion/week');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not update');
    } finally {
      setDigestSaving(false);
    }
  };

  const toggleLocalSeed = async (enabled) => {
    setDigestSaving(true);
    try {
      const r = await axios.put(
        `${API_URL}/api/admin/seo/stealth-keywords/digest/settings`,
        { auto_local_seed_enabled: enabled }, authHeaders(),
      );
      setDigest(r.data);
      toast.success(enabled
        ? 'Local keyword seeding ON — GSC queries mentioning a UK town auto-seed the matching city-page'
        : 'Local keyword seeding OFF');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not update');
    } finally {
      setDigestSaving(false);
    }
  };

  const saveBatchMax = async () => {
    setDigestSaving(true);
    try {
      const r = await axios.put(
        `${API_URL}/api/admin/seo/stealth-keywords/digest/settings`,
        { auto_promote_batch_max: batchMaxDraft }, authHeaders(),
      );
      setDigest(r.data);
      setBatchMaxDraft(r.data.auto_promote_batch_max);
      toast.success(`Batch cap set to ${r.data.auto_promote_batch_max} promotions/week`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not update');
    } finally {
      setDigestSaving(false);
    }
  };

  const undoAp = async (rec) => {
    if (!window.confirm(
      `Undo this auto-promotion?\n\n"${rec.query}" will be removed from the "${rec.collection}" collection's stealth keywords.`
    )) return;
    setApUndoing(rec.id);
    try {
      await axios.post(
        `${API_URL}/api/admin/seo/stealth-keywords/auto-promote/undo/${rec.id}`,
        {}, authHeaders(),
      );
      toast.success(`Undone — "${rec.query}" removed from ${rec.collection}`);
      loadApHistory();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Undo failed');
    } finally {
      setApUndoing(null);
    }
  };

  const toggleDigest = async (enabled) => {
    setDigestSaving(true);
    try {
      const r = await axios.put(
        `${API_URL}/api/admin/seo/stealth-keywords/digest/settings`,
        { enabled }, authHeaders(),
      );
      setDigest(r.data);
      toast.success(enabled ? 'Weekly digest enabled' : 'Weekly digest paused');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not update');
    } finally {
      setDigestSaving(false);
    }
  };

  const saveRecipients = async () => {
    setDigestSaving(true);
    try {
      const list = recipientsDraft
        .split(/[,\n]+/)
        .map((s) => s.trim())
        .filter((s) => s.includes('@'));
      const r = await axios.put(
        `${API_URL}/api/admin/seo/stealth-keywords/digest/settings`,
        { recipients: list }, authHeaders(),
      );
      setDigest(r.data);
      setRecipientsDraft((r.data.recipients || []).join(', '));
      toast.success(`${r.data.recipients.length} recipient(s) saved`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not save');
    } finally {
      setDigestSaving(false);
    }
  };

  const sendDigestNow = async () => {
    if (!window.confirm('Send the weekly digest email right now? (Uses the configured recipients — ADMIN_EMAIL if none set.)')) return;
    setDigestSending(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/seo/stealth-keywords/digest/send-now`, {}, authHeaders(),
      );
      if (r.data?.ok) {
        toast.success(`Digest sent to ${(r.data.recipients || []).join(', ')}`);
        loadDigestSettings();
      } else if (r.data?.reason === 'no_recipients') {
        toast.error('No recipients configured — add emails above or set ADMIN_EMAIL on the server');
      } else {
        toast.error(`Couldn't send: ${r.data?.reason || 'unknown'}`);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Send failed');
    } finally {
      setDigestSending(false);
    }
  };

  const promoteMissed = async (query) => {
    const choices = collections.length > 0
      ? collections.slice(0, 30).map((c) => c.collection).filter(Boolean)
      : [];
    let collection;
    if (choices.length === 0) {
      collection = window.prompt(
        `Add "${query}" as a collection-wide stealth keyword.\n\n` +
        `Type the collection name to attach this keyword to. ` +
        `It'll be indexed by Google + Bing on /collections/<slug> pages.`
      );
    } else {
      const list = choices.map((c, i) => `  ${i + 1}. ${c}`).join('\n');
      const pick = window.prompt(
        `Add "${query}" as a stealth keyword on which collection?\n\n` +
        `Pick a number, or type a collection name:\n\n${list}`
      );
      if (!pick) return;
      const idx = parseInt(pick, 10);
      if (!Number.isNaN(idx) && idx >= 1 && idx <= choices.length) {
        collection = choices[idx - 1];
      } else {
        collection = pick.trim();
      }
    }
    if (!collection) return;
    setPromoting(query);
    try {
      await axios.post(
        `${API_URL}/api/admin/seo/stealth-keywords/performance/promote-missed-win`,
        { target: 'collection', query, collection },
        authHeaders(),
      );
      toast.success(`"${query}" added as stealth keyword on "${collection}"`);
      load(true);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not promote');
    } finally {
      setPromoting(null);
    }
  };

  if (!opened) {
    return (
      <Card
        className="p-4 bg-gradient-to-br from-amber-50 to-orange-50 border-amber-200 cursor-pointer hover:border-amber-400 transition"
        onClick={() => setOpened(true)}
        data-testid="stealth-perf-collapsed"
      >
        <div className="flex items-center gap-3">
          <div className="shrink-0 w-10 h-10 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center">
            <BarChart3 className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <div className="font-semibold text-slate-900">
              Stealth-Keyword Performance
            </div>
            <div className="text-xs text-slate-600">
              Click to load · pulls live Google Search Console data and shows
              which supplier names are driving clicks vs your brand names. Spot
              "missed wins" — searches we should ADD as stealth keywords.
            </div>
          </div>
          <Button
            size="sm"
            variant="ghost"
            className="text-amber-800"
            data-testid="stealth-perf-open-btn"
          >
            <Eye className="w-4 h-4 mr-1" /> Open
          </Button>
        </div>
      </Card>
    );
  }

  const r = report || {};
  const t = r.totals || {};
  const stealth = r.stealth || {};
  const brand = r.brand || {};
  const other = r.other || {};

  return (
    <Card className="overflow-hidden" data-testid="stealth-perf-card">
      <div className="bg-gradient-to-br from-slate-900 to-amber-900 text-white px-6 py-5">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-widest text-amber-300 font-semibold flex items-center gap-1.5">
              <BarChart3 className="w-3 h-3" /> Stealth-Keyword Performance
            </div>
            <h3 className="text-xl font-bold mt-1 flex items-center gap-2">
              <Trophy className="w-5 h-5 text-amber-300" />
              How much traffic supplier names actually drive
            </h3>
            <p className="text-sm text-amber-200/80 mt-1 max-w-2xl">
              Live join: every Google query that surfaced your site in the last {days} days
              vs every stealth keyword in the catalogue. Real attribution — not a guess.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={days}
              onChange={(e) => setDays(parseInt(e.target.value, 10))}
              className="bg-white/10 text-white border border-white/20 rounded text-xs px-2 py-1"
              data-testid="stealth-perf-days"
            >
              {[7, 28, 90].map((d) => <option key={d} value={d} className="text-slate-900">{d} days</option>)}
            </select>
            <Button
              size="sm" variant="ghost"
              onClick={() => load(true)}
              disabled={refreshing}
              className="text-white hover:bg-white/10"
              data-testid="stealth-perf-refresh-btn"
            >
              {refreshing ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <RefreshCw className="w-4 h-4 mr-1" />}
              Refresh
            </Button>
          </div>
        </div>
      </div>

      <div className="p-5 space-y-5">
        {loading && !report && (
          <div className="text-center py-8 text-slate-500 text-sm">
            <Loader2 className="w-4 h-4 animate-spin inline mr-1.5" />
            Pulling Google Search Console data — this can take 5-10s on first call…
          </div>
        )}

        {!loading && r.gsc_connected === false && (
          <div className="rounded-lg border-2 border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" data-testid="stealth-perf-no-gsc">
            <strong>Google Search Console isn't connected yet.</strong> The performance report
            needs GSC clicks to attribute traffic to stealth keywords.
            Scroll up and click the green <em>"Connect Google Search Console"</em> card.
            Once connected GSC data takes 24-48h to populate.
          </div>
        )}

        {!loading && r.gsc_connected && r.reason && (
          <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-900" data-testid="stealth-perf-error">
            GSC error: {r.reason}
          </div>
        )}

        {report && r.gsc_connected && !r.reason && (
          <>
            {/* KPI strip */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="stealth-perf-kpis">
              <KpiCard
                title="Stealth wins" tone="emerald"
                clicks={stealth.clicks} impressions={stealth.impressions}
                ctr={stealth.ctr} share_pct={stealth.share_pct}
                queries_count={stealth.queries_count}
                blurb="customers found you via supplier names"
              />
              <KpiCard
                title="Brand wins" tone="indigo"
                clicks={brand.clicks} impressions={brand.impressions}
                ctr={brand.ctr} share_pct={brand.share_pct}
                queries_count={brand.queries_count}
                blurb="customers searched your re-branded names"
              />
              <KpiCard
                title="Other queries" tone="slate"
                clicks={other.clicks} impressions={other.impressions}
                ctr={other.ctr} share_pct={other.share_pct}
                queries_count={other.queries_count}
                blurb="generic phrases ('porcelain tile UK' etc)"
              />
            </div>

            {/* Top winners */}
            <Section
              title="Top winning supplier names" icon={Trophy}
              empty="No stealth keywords have driven clicks yet — wait for the next Google crawl after enabling auto-fill."
              testid="stealth-perf-winners"
            >
              {(r.top_winners || []).length > 0 && (
                <table className="w-full text-sm">
                  <thead className="text-xs text-slate-500 uppercase">
                    <tr>
                      <th className="text-left py-2">Stealth keyword</th>
                      <th className="text-left">Attributed to</th>
                      <th className="text-right">Clicks</th>
                      <th className="text-right">Impressions</th>
                      <th className="text-right">CTR</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.top_winners.map((w, i) => (
                      <tr key={i} className="border-t hover:bg-slate-50" data-testid={`stealth-perf-winner-${i}`}>
                        <td className="py-2 font-mono text-emerald-900 font-semibold">{w.keyword}</td>
                        <td className="text-slate-600 text-xs truncate max-w-[280px]">
                          {w.scope === 'product'
                            ? `${w.product_name || '?'} (product)`
                            : `${w.collection || '?'} (collection)`}
                        </td>
                        <td className="text-right font-mono">{fmt(w.clicks)}</td>
                        <td className="text-right font-mono">{fmt(w.impressions)}</td>
                        <td className="text-right font-mono">{pct(w.ctr)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>

            {/* Missed wins */}
            <Section
              title="Missed wins" icon={Target} tone="amber"
              empty="No high-impression queries are slipping through — your stealth keyword set is comprehensive."
              testid="stealth-perf-missed"
              blurb="High-impression GSC queries that DON'T match any stealth keyword. Click '+ Add' to promote one."
            >
              {(r.missed_wins || []).length > 0 && (
                <table className="w-full text-sm">
                  <thead className="text-xs text-slate-500 uppercase">
                    <tr>
                      <th className="text-left py-2">Query</th>
                      <th className="text-right">Clicks</th>
                      <th className="text-right">Impressions</th>
                      <th className="text-right">CTR</th>
                      <th className="text-right">Pos.</th>
                      <th className="text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.missed_wins.map((m, i) => (
                      <tr key={i} className="border-t hover:bg-amber-50/40" data-testid={`stealth-perf-missed-${i}`}>
                        <td className="py-2 font-medium text-slate-900">{m.query}</td>
                        <td className="text-right font-mono">{fmt(m.clicks)}</td>
                        <td className="text-right font-mono">{fmt(m.impressions)}</td>
                        <td className="text-right font-mono">{pct(m.ctr)}</td>
                        <td className="text-right font-mono">{m.position}</td>
                        <td className="text-right">
                          <Button
                            size="sm" variant="ghost"
                            disabled={promoting === m.query}
                            onClick={() => promoteMissed(m.query)}
                            className="h-7 px-2 text-xs text-amber-800 hover:bg-amber-100"
                            data-testid={`stealth-perf-promote-${i}`}
                          >
                            {promoting === m.query
                              ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                              : <Plus className="w-3.5 h-3.5 mr-1" />}
                            Add
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>

            {/* Underperformers */}
            <Section
              title="Underperforming stealth keywords" icon={AlertTriangle} tone="rose"
              empty="Every stealth keyword set has driven at least one impression — full coverage."
              testid="stealth-perf-under"
              blurb="Set in your catalogue but with zero GSC traffic. Could be: not crawled yet · low search demand · or noise to remove."
            >
              {(r.underperformers || []).length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {(r.underperformers || []).slice(0, 30).map((u, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border bg-rose-50 text-rose-800 border-rose-200"
                      title={u.scope === 'product' ? `Product: ${u.product_name}` : `Collection: ${u.collection}`}
                      data-testid={`stealth-perf-under-${i}`}
                    >
                      {u.keyword}
                      <span className="text-[9px] text-rose-500 ml-0.5">
                        {u.scope === 'product' ? 'P' : 'C'}
                      </span>
                    </span>
                  ))}
                  {r.underperformers.length > 30 && (
                    <span className="text-[11px] text-rose-700 italic ml-2">
                      +{r.underperformers.length - 30} more
                    </span>
                  )}
                </div>
              )}
            </Section>

            <div className="text-[10px] text-slate-400 italic flex items-center gap-1.5">
              <Search className="w-3 h-3" /> Window: {r.start_date} → {r.end_date} · {fmt(t.queries_count)} queries analysed · cached 1h
            </div>

            {/* Weekly digest email */}
            <div
              className="border-t pt-4 rounded-lg bg-gradient-to-br from-indigo-50 to-sky-50 border border-indigo-200 p-3"
              data-testid="stealth-digest-strip"
            >
              <div className="flex items-start gap-3">
                <div className="shrink-0 w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center">
                  <Mail className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <div className="font-semibold text-slate-900 text-sm">
                      Weekly digest email — every Monday 08:00 BST
                    </div>
                    {digest && (
                      <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer select-none ml-auto">
                        <input
                          type="checkbox"
                          checked={!!digest.enabled}
                          onChange={(e) => toggleDigest(e.target.checked)}
                          disabled={digestSaving}
                          className="h-3.5 w-3.5 accent-indigo-600"
                          data-testid="stealth-digest-enabled"
                        />
                        <span className={digest.enabled ? 'text-emerald-700 font-semibold' : 'text-slate-500'}>
                          {digest.enabled ? 'Enabled' : 'Paused'}
                        </span>
                      </label>
                    )}
                  </div>
                  <div className="text-[11px] text-slate-600 mt-0.5">
                    WoW stealth-click delta · top winners · new missed-wins · underperformer count.
                    Skipped automatically when GSC data has no signal yet.
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <input
                      type="text"
                      value={recipientsDraft}
                      onChange={(e) => setRecipientsDraft(e.target.value)}
                      placeholder="admin@tilestation.co.uk · comma-separated · leave blank to use ADMIN_EMAIL"
                      className="flex-1 text-xs border rounded px-2 py-1.5 bg-white"
                      data-testid="stealth-digest-recipients-input"
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); saveRecipients(); } }}
                    />
                    <Button
                      size="sm" variant="outline"
                      onClick={saveRecipients} disabled={digestSaving}
                      className="h-7 px-2 text-xs"
                      data-testid="stealth-digest-save-recipients"
                    >
                      Save
                    </Button>
                    <Button
                      size="sm"
                      onClick={sendDigestNow} disabled={digestSending}
                      className="h-7 px-2 text-xs bg-indigo-600 hover:bg-indigo-700 text-white"
                      data-testid="stealth-digest-send-now"
                    >
                      {digestSending
                        ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                        : <Send className="w-3.5 h-3.5 mr-1" />}
                      Send now
                    </Button>
                  </div>
                  {digest?.last_sent_at && (
                    <div className="text-[10px] text-slate-500 mt-1.5 font-mono" data-testid="stealth-digest-last-sent">
                      last sent {new Date(digest.last_sent_at).toLocaleString('en-GB')} · {digest.last_sent_snapshot?.clicks ?? 0} clicks · {digest.last_sent_snapshot?.new_missed_count ?? 0} new missed wins
                    </div>
                  )}

                  {/* Auto-promote controls */}
                  {digest && (
                    <div
                      className="mt-3 pt-3 border-t border-indigo-200/60"
                      data-testid="stealth-ap-block"
                    >
                      <div className="flex items-center flex-wrap gap-3">
                        <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer select-none">
                          <input
                            type="checkbox"
                            checked={!!digest.auto_promote_enabled}
                            onChange={(e) => toggleAutoPromote(e.target.checked)}
                            disabled={digestSaving}
                            className="h-3.5 w-3.5 accent-fuchsia-600"
                            data-testid="stealth-ap-enabled"
                          />
                          <span className={digest.auto_promote_enabled ? 'text-fuchsia-800 font-semibold' : 'text-slate-600'}>
                            Auto-promote top missed-win into matching collection
                          </span>
                        </label>
                        {digest.auto_promote_enabled && (
                          <div className="flex items-center gap-1.5 ml-auto">
                            <span className="text-[10px] text-slate-600">min impressions</span>
                            <input
                              type="number"
                              min={5}
                              max={500}
                              value={minImprDraft}
                              onChange={(e) => setMinImprDraft(parseInt(e.target.value, 10) || 20)}
                              className="w-16 text-xs border rounded px-1.5 py-1 bg-white"
                              data-testid="stealth-ap-min-impressions"
                            />
                            <Button
                              size="sm" variant="outline"
                              disabled={digestSaving || minImprDraft === (digest.auto_promote_min_impressions || 20)}
                              onClick={saveMinImpressions}
                              className="h-6 px-2 text-[10px]"
                              data-testid="stealth-ap-save-min"
                            >
                              Set
                            </Button>
                          </div>
                        )}
                      </div>
                      {digest.auto_promote_enabled && (
                        <div className="text-[10px] text-slate-600 mt-1.5">
                          Each Monday: the top new missed-win with ≥{digest.auto_promote_min_impressions || 20} impressions
                          that cleanly matches a collection name gets added as a collection-wide stealth keyword.
                          One promotion per week max · [Undo] link in the digest email.
                        </div>
                      )}

                      {/* Batch mode — only available when auto-promote itself is enabled */}
                      {digest.auto_promote_enabled && (
                        <div
                          className="mt-2 pt-2 border-t border-fuchsia-100"
                          data-testid="stealth-ap-batch-block"
                        >
                          <div className="flex items-center flex-wrap gap-3">
                            <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={!!digest.auto_promote_batch_mode}
                                onChange={(e) => toggleBatchMode(e.target.checked)}
                                disabled={digestSaving}
                                className="h-3.5 w-3.5 accent-fuchsia-600"
                                data-testid="stealth-ap-batch-mode"
                              />
                              <span className={digest.auto_promote_batch_mode
                                ? 'text-fuchsia-800 font-semibold' : 'text-slate-600'}>
                                Batch mode — promote up to N/week (stricter 2× impressions bar)
                              </span>
                            </label>
                            {digest.auto_promote_batch_mode && (
                              <div className="flex items-center gap-1.5 ml-auto">
                                <span className="text-[10px] text-slate-600">max/week</span>
                                <input
                                  type="number"
                                  min={2} max={10}
                                  value={batchMaxDraft}
                                  onChange={(e) => setBatchMaxDraft(parseInt(e.target.value, 10) || 5)}
                                  className="w-14 text-xs border rounded px-1.5 py-1 bg-white"
                                  data-testid="stealth-ap-batch-max"
                                />
                                <Button
                                  size="sm" variant="outline"
                                  disabled={digestSaving || batchMaxDraft === (digest.auto_promote_batch_max || 5)}
                                  onClick={saveBatchMax}
                                  className="h-6 px-2 text-[10px]"
                                  data-testid="stealth-ap-save-batch-max"
                                >
                                  Set
                                </Button>
                              </div>
                            )}
                          </div>
                          {digest.auto_promote_batch_mode && (
                            <div className="text-[10px] text-slate-600 mt-1.5">
                              Effective threshold: <strong className="font-mono">{(digest.auto_promote_min_impressions || 20) * 2} impressions</strong>.
                              One promotion per collection per run · compounds SEO gains {digest.auto_promote_batch_max || 5}× faster.
                            </div>
                          )}
                        </div>
                      )}

                      {/* Local keyword seeder — targets UK city landing pages */}
                      {digest.auto_promote_enabled && (
                        <div
                          className="mt-2 pt-2 border-t border-fuchsia-100"
                          data-testid="stealth-ap-local-block"
                        >
                          <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer select-none">
                            <input
                              type="checkbox"
                              checked={!!digest.auto_local_seed_enabled}
                              onChange={(e) => toggleLocalSeed(e.target.checked)}
                              disabled={digestSaving}
                              className="h-3.5 w-3.5 accent-fuchsia-600"
                              data-testid="stealth-ap-local-seed"
                            />
                            <span className={digest.auto_local_seed_enabled
                              ? 'text-fuchsia-800 font-semibold' : 'text-slate-600'}>
                              Local keyword seeding — auto-seed matching UK city pages
                            </span>
                          </label>
                          {digest.auto_local_seed_enabled && (
                            <div className="text-[10px] text-slate-600 mt-1.5">
                              When a new missed-win contains a UK town name (e.g. <span className="font-mono">"tiles gravesend"</span>),
                              auto-seed it into the matching city-landing-page's stealth keywords instead of a collection.
                              Catches the 40% of tile searches with local intent · same weekly budget shared with the collection auto-promote.
                            </div>
                          )}
                        </div>
                      )}

                      {apHistory.length > 0 && (
                        <div className="mt-3" data-testid="stealth-ap-history">
                          <div className="text-[11px] font-semibold text-slate-700 mb-1">
                            Recent auto-promotions ({apHistory.filter((r) => !r.undone_at).length} active)
                          </div>
                          <div className="space-y-1">
                            {apHistory.map((rec) => {
                              const dt = rec.promoted_at ? new Date(rec.promoted_at).toLocaleDateString('en-GB') : '—';
                              const undone = !!rec.undone_at;
                              const isLocal = rec.scope === 'city_page';
                              const target = isLocal
                                ? `${rec.town || rec.city_slug || '—'} · local page`
                                : rec.collection || '—';
                              return (
                                <div
                                  key={rec.id}
                                  className="flex items-center gap-2 text-[11px] bg-white/60 rounded px-2 py-1.5 border border-indigo-100"
                                  data-testid={`stealth-ap-row-${rec.id}`}
                                >
                                  <span className="font-mono font-semibold text-fuchsia-900">{rec.query}</span>
                                  <span className="text-slate-500">→</span>
                                  <span className="text-slate-800">{target}</span>
                                  {isLocal && (
                                    <span className="text-[9px] bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded uppercase tracking-wide font-semibold">
                                      local
                                    </span>
                                  )}
                                  <span className="text-slate-400 ml-auto">{dt} · {rec.impressions} impr</span>
                                  {undone ? (
                                    <span className="text-[9px] bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded uppercase tracking-wide">
                                      Undone
                                    </span>
                                  ) : (
                                    <Button
                                      size="sm" variant="ghost"
                                      onClick={() => undoAp(rec)}
                                      disabled={apUndoing === rec.id}
                                      className="h-5 px-1.5 text-[10px] text-rose-700 hover:bg-rose-50"
                                      data-testid={`stealth-ap-undo-${rec.id}`}
                                    >
                                      {apUndoing === rec.id
                                        ? <Loader2 className="w-3 h-3 animate-spin" />
                                        : 'Undo'}
                                    </Button>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </Card>
  );
};


const KpiCard = ({ title, tone, clicks, impressions, ctr, share_pct, queries_count, blurb }) => {
  const tones = {
    emerald: 'border-emerald-300 bg-emerald-50',
    indigo: 'border-indigo-300 bg-indigo-50',
    slate: 'border-slate-300 bg-slate-50',
  };
  const accent = {
    emerald: 'text-emerald-900',
    indigo: 'text-indigo-900',
    slate: 'text-slate-700',
  };
  return (
    <div
      className={`rounded-lg border-2 p-3 ${tones[tone]}`}
      data-testid={`stealth-perf-kpi-${tone}`}
    >
      <div className={`text-xs uppercase tracking-wide font-semibold ${accent[tone]}`}>{title}</div>
      <div className="flex items-baseline gap-2 mt-1">
        <div className={`text-2xl font-bold font-mono ${accent[tone]}`}>{fmt(clicks)}</div>
        <div className="text-xs text-slate-500 ml-1">clicks</div>
        {share_pct != null && (
          <div className={`text-xs font-mono ml-auto ${accent[tone]}`}>{share_pct}% share</div>
        )}
      </div>
      <div className="text-[11px] text-slate-600 mt-1 grid grid-cols-3 gap-2">
        <div><strong className="font-mono mr-1">{fmt(impressions)}</strong>impr</div>
        <div>CTR <strong className="font-mono ml-1">{pct(ctr)}</strong></div>
        <div><strong className="font-mono mr-1">{fmt(queries_count)}</strong>qrys</div>
      </div>
      <div className="text-[10px] text-slate-500 mt-1.5 italic">{blurb}</div>
    </div>
  );
};


const Section = ({ title, icon: Icon, tone = 'slate', empty, blurb, children, testid }) => {
  const headTones = {
    slate: 'text-slate-800',
    amber: 'text-amber-900',
    rose: 'text-rose-900',
  };
  // children is an empty/falsy <table> when no rows — detect "empty" via React.Children
  const hasContent = children && children.props && children.props.children !== undefined;
  return (
    <div className="border-t pt-4" data-testid={testid}>
      <h4 className={`text-sm font-semibold flex items-center gap-1.5 ${headTones[tone]}`}>
        <Icon className="w-4 h-4" /> {title}
      </h4>
      {blurb && <div className="text-[11px] text-slate-500 mt-0.5 mb-2">{blurb}</div>}
      <div className="overflow-x-auto mt-2">
        {hasContent ? children : (
          <div className="text-[12px] text-slate-500 italic py-2">{empty}</div>
        )}
      </div>
    </div>
  );
};


export default StealthPerformanceCard;
