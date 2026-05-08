/**
 * MaintenanceTasks — admin one-shot data migrators dashboard.
 *
 * Surfaces every "run once after deploy" backend script (hyphen URL fix,
 * tools+accessories merge, legacy `/shop/tiles` link rewrite) with a Run
 * button + last-run timestamp + result summary, so admins don't have to
 * paste curl into the dev console.
 *
 * Backend persistence in `website_settings` under `_id = maintenance_run_*`
 * — see `_record_maintenance_run()` in backend/routes/website_admin.py.
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { Wrench, Loader2, CheckCircle2, AlertTriangle, RefreshCw, ExternalLink, Package, ShoppingCart, ShoppingBag, CreditCard, ShieldCheck, ShieldAlert, Clock, Mail, Send, Activity, FileText, Download } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import { toast } from 'sonner';
import UptimeSparklineWidget from './UptimeSparklineWidget';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Registry — single source of truth. Adding a new migrator? Append a row
// here AND make the backend route call `_record_maintenance_run(task_id…)`.
const TASKS = [
  {
    id: 'hyphen_url_fix',
    label: 'Fix legacy hyphen links',
    description:
      'Auto-corrects category links typed in the old hyphen format (/Ardesia-Slate → /Ardesia%20Slate) where the result points to a real collection. Bogus typos are flagged for manual review.',
    endpoint: '/api/website-admin/sitemap/migrate-hyphenated-urls',
    method: 'POST',
    summarise: (r) =>
      `Scanned ${r?.scanned || 0} · Auto-fixed ${r?.rewritten_count || 0} · Needs review: ${r?.needs_review_count || 0}`,
  },
  {
    id: 'tools_accessories_merge',
    label: 'Merge Tools + Accessories → Tools & Accessories',
    description:
      'Consolidates legacy tools/accessories product groups across categories, tiles, nav menus, and page settings into a single tools-accessories group.',
    endpoint: '/api/website-admin/migrate-tools-accessories',
    method: 'POST',
    summarise: (r) => {
      if (!r) return '—';
      const total = (r.categories_updated || 0) + (r.tiles_updated || 0) + (r.nav_menus_updated || 0) + (r.settings_keys_merged || 0);
      return total === 0
        ? 'Already consolidated — nothing to migrate'
        : `Categories: ${r.categories_updated || 0} · Tiles: ${r.tiles_updated || 0} · Nav menus: ${r.nav_menus_updated || 0} · Settings keys: ${r.settings_keys_merged || 0}`;
    },
  },
  {
    id: 'legacy_shop_tiles_paths',
    label: 'Rewrite legacy /shop/tiles links → /tiles',
    description:
      'One-time bulk replace of saved links across navigation menus, hero slides, banners, and settings.',
    endpoint: '/api/website-admin/migrate-links',
    method: 'POST',
    summarise: (r) => (r?.total_links_updated != null ? `${r.total_links_updated} links updated` : '—'),
  },
];

const formatRelativeTime = (iso) => {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  const diffSec = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (diffSec < 60) return 'just now';
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${Math.round(diffHr / 24)}d ago`;
};

export default function MaintenanceTasks() {
  const [runs, setRuns] = useState({});
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [runningTaskId, setRunningTaskId] = useState(null);
  // DB health snapshot — counts that confirm "everything still humming"
  // at a glance after a deploy (total products, paid orders today,
  // revenue today, draft baskets, last successful payment).
  const [health, setHealth] = useState(null);
  const [loadingHealth, setLoadingHealth] = useState(true);
  // Critical UI health checks — each loads a key page in a hidden
  // iframe and verifies must-have selectors exist. Catches accidental
  // regressions like "Trade Login Box vanished" the moment they land.
  const [uiChecks, setUiChecks] = useState([]);
  const [uiResults, setUiResults] = useState([]);
  const [uiLastRun, setUiLastRun] = useState(null);
  const [runningUi, setRunningUi] = useState(false);
  const [uiSchedule, setUiSchedule] = useState(null);  // {settings, log}
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [serverRunning, setServerRunning] = useState(false);  // background "Run now"
  const [recipientsDraft, setRecipientsDraft] = useState('');
  // Sentry status pill — live indicator showing whether error tracking is
  // active. Hits /api/monitoring/sentry which already exists and reports
  // SDK availability + DSN configured + initialised state.
  const [sentryStatus, setSentryStatus] = useState(null);
  const [sentryTesting, setSentryTesting] = useState(false);
  // Launch checklist PDFs available for download from this page
  const [checklists, setChecklists] = useState([]);
  const [downloadingId, setDownloadingId] = useState(null);
  const [regenerating, setRegenerating] = useState(false);
  const probeFrameRef = useRef(null);

  const auth = {
    headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
  };

  const fetchHealth = useCallback(async () => {
    setLoadingHealth(true);
    try {
      const res = await axios.get(`${API_URL}/api/website-admin/maintenance/health`, auth);
      setHealth(res.data || null);
    } catch {
      setHealth(null);
    } finally {
      setLoadingHealth(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchUiChecks = useCallback(async () => {
    try {
      const [registry, last, schedule] = await Promise.all([
        axios.get(`${API_URL}/api/website-admin/maintenance/ui-checks`, auth),
        axios.get(`${API_URL}/api/website-admin/maintenance/ui-checks/last`, auth),
        axios.get(`${API_URL}/api/website-admin/maintenance/ui-checks/schedule`, auth),
      ]);
      setUiChecks(registry.data?.checks || []);
      setUiLastRun(last.data || null);
      // Merge disabled flags from the registry into the results so
      // the toggle reflects the *current* state, not just the state
      // at the time of the last probe run.
      const registryByCid = {};
      (registry.data?.checks || []).forEach((c) => { registryByCid[c.id] = c; });
      const merged = (last.data?.results || []).map((r) => ({
        ...r,
        disabled: !!registryByCid[r.id]?.disabled,
        disabled_reason: registryByCid[r.id]?.disabled_reason || r.skip_reason,
      }));
      setUiResults(merged);
      setUiSchedule(schedule.data || null);
      setRecipientsDraft((schedule.data?.settings?.recipients || []).join(', '));
    } catch {
      setUiChecks([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleUiCheck = useCallback(async (checkId, nextDisabled) => {
    const reason = nextDisabled
      ? (window.prompt(
          'Optional reason (shown next to the check in the report):',
          'Toggled off by admin',
        ) ?? null)
      : null;
    if (nextDisabled && reason === null) return; // user cancelled the prompt
    try {
      const auth = { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } };
      await axios.patch(
        `${API_URL}/api/website-admin/maintenance/ui-checks/${checkId}/toggle`,
        { disabled: nextDisabled, reason },
        auth,
      );
      toast.success(nextDisabled ? 'Check disabled' : 'Check re-enabled');
      // Update local state without a full refetch
      setUiChecks((prev) => prev.map((c) =>
        c.id === checkId
          ? { ...c, disabled: nextDisabled, disabled_reason: nextDisabled ? reason : null }
          : c,
      ));
      setUiResults((prev) => prev.map((r) =>
        r.id === checkId
          ? { ...r, disabled: nextDisabled, disabled_reason: nextDisabled ? reason : null }
          : r,
      ));
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not update toggle');
    }
  }, []);

  const saveUiSchedule = async (overrides = {}) => {
    if (!uiSchedule) return;
    setSavingSchedule(true);
    try {
      const payload = { ...overrides };
      if (payload.recipients !== undefined) {
        payload.recipients = (payload.recipients || '')
          .split(/[\s,;]+/)
          .map(r => r.trim())
          .filter(Boolean);
      }
      const res = await axios.put(
        `${API_URL}/api/website-admin/maintenance/ui-checks/schedule`,
        payload,
        auth,
      );
      setUiSchedule((prev) => ({ ...(prev || {}), settings: res.data || {} }));
      toast.success('Schedule saved');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not save schedule');
    } finally {
      setSavingSchedule(false);
    }
  };

  const triggerServerRun = async () => {
    setServerRunning(true);
    toast.info('UI health probe queued — PDF will be emailed when complete (~90 s).');
    try {
      await axios.post(
        `${API_URL}/api/website-admin/maintenance/ui-checks/run-now`,
        {},
        auth,
      );
      // Poll for result every 10 s, max 12 attempts (2 min)
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts += 1;
        try {
          const r = await axios.get(`${API_URL}/api/website-admin/maintenance/ui-checks/last`, auth);
          if (r.data?.source === 'cron' && r.data?.ran_at && r.data.ran_at !== uiLastRun?.ran_at) {
            setUiLastRun(r.data);
            setUiResults(r.data.results || []);
            await fetchUiChecks();
            setServerRunning(false);
            clearInterval(poll);
            const failed = r.data.failed_count || 0;
            if (failed === 0) toast.success(`All ${r.data.passed_count} checks passed · PDF emailed`);
            else toast.error(`${failed} check(s) failing · PDF emailed`);
            return;
          }
        } catch {/* noop */}
        if (attempts >= 12) {
          setServerRunning(false);
          clearInterval(poll);
          toast.warning('Probe still running — refresh in a minute to see results.');
        }
      }, 10_000);
    } catch (e) {
      setServerRunning(false);
      toast.error(e.response?.data?.detail || 'Could not start probe');
    }
  };

  // Probe a single check by loading its URL into a hidden iframe and
  // testing the expected selectors against the rendered DOM. Resolves
  // to a pass/fail result with the missing selectors enumerated.
  const probeCheck = (check) => new Promise((resolve) => {
    const iframe = document.createElement('iframe');
    iframe.style.cssText = 'position:fixed;left:-9999px;top:-9999px;width:1280px;height:900px;visibility:hidden';
    iframe.src = check.url;
    let timeout = null;
    let settled = false;
    const finish = (status, missing) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      try { iframe.remove(); } catch { /* noop */ }
      resolve({
        id: check.id,
        label: check.label,
        url: check.url,
        status,
        missing,
        ran_at: new Date().toISOString(),
      });
    };
    iframe.onload = () => {
      // Wait a beat for React to render then probe.
      setTimeout(() => {
        try {
          const doc = iframe.contentDocument;
          if (!doc) return finish('fail', ['iframe document inaccessible']);
          const missing = (check.expected_selectors || []).filter(sel => !doc.querySelector(sel));
          finish(missing.length === 0 ? 'pass' : 'fail', missing);
        } catch (e) {
          finish('fail', [`probe error: ${e?.message || 'unknown'}`]);
        }
      }, 3500);
    };
    iframe.onerror = () => finish('fail', ['iframe load error']);
    document.body.appendChild(iframe);
    // Hard timeout — never let a slow page stall the whole run
    timeout = setTimeout(() => finish('fail', ['timeout (page took >15s to render)']), 15000);
  });

  const runUiChecks = async () => {
    if (!uiChecks.length) return;
    setRunningUi(true);
    setUiResults(uiChecks.map(c => ({
      id: c.id, label: c.label, url: c.url,
      status: c.disabled ? 'disabled' : 'running',
      missing: [],
      disabled: !!c.disabled,
      disabled_reason: c.disabled_reason,
      skip_reason: c.disabled ? (c.disabled_reason || 'Disabled by admin') : undefined,
    })));
    const results = [];
    for (const check of uiChecks) {
      // Disabled checks short-circuit — no iframe probe, no fail count
      if (check.disabled) {
        results.push({
          id: check.id, label: check.label, url: check.url,
          status: 'disabled', missing: [],
          disabled: true,
          disabled_reason: check.disabled_reason,
          skip_reason: check.disabled_reason || 'Disabled by admin',
          ran_at: new Date().toISOString(),
        });
        setUiResults([...results, ...uiChecks.slice(results.length).map(c => ({
          id: c.id, label: c.label, url: c.url,
          status: c.disabled ? 'disabled' : 'pending', missing: [],
          disabled: !!c.disabled, disabled_reason: c.disabled_reason,
        }))]);
        continue;
      }
      // Sequential to avoid 5 iframes × 1.5MB JS bundle parsed at once
      // pegging the admin's CPU.
      // eslint-disable-next-line no-await-in-loop
      const r = await probeCheck(check);
      results.push(r);
      setUiResults([...results, ...uiChecks.slice(results.length).map(c => ({
        id: c.id, label: c.label, url: c.url,
        status: c.disabled ? 'disabled' : 'pending', missing: [],
        disabled: !!c.disabled, disabled_reason: c.disabled_reason,
      }))]);
    }
    setUiResults(results);
    setRunningUi(false);
    try {
      await axios.post(
        `${API_URL}/api/website-admin/maintenance/ui-checks/result`,
        { results, ran_at: new Date().toISOString() },
        auth
      );
      const failed = results.filter(r => r.status === 'fail');
      if (failed.length) {
        toast.error(`${failed.length} critical UI element(s) missing!`, {
          description: failed.map(f => f.label).join(' · '),
          duration: 12000,
        });
      } else {
        toast.success('All critical UI elements present ✓');
      }
      await fetchUiChecks();
    } catch (e) {
      toast.error('Could not save the UI health result');
    }
  };

  const fetchRuns = useCallback(async () => {
    setLoadingRuns(true);
    try {
      const res = await axios.get(`${API_URL}/api/website-admin/maintenance/runs`, auth);
      setRuns(res.data?.runs || {});
    } catch {
      // non-fatal — page still usable, just no last-run history
    } finally {
      setLoadingRuns(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Lightweight poll for Sentry status. We don't surface every detail —
  // just the binary "is error tracking flowing" so an admin can spot a
  // misconfigured DSN immediately after deploy.
  const fetchSentryStatus = useCallback(async () => {
    try {
      const r = await axios.get(`${API_URL}/api/monitoring/sentry`, auth);
      setSentryStatus(r.data || null);
    } catch {
      setSentryStatus({ error: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch the list of downloadable launch checklist PDFs.
  const fetchChecklists = useCallback(async () => {
    try {
      const r = await axios.get(`${API_URL}/api/website-admin/maintenance/checklists`, auth);
      setChecklists(r.data?.checklists || []);
    } catch {
      setChecklists([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Download a checklist PDF — uses fetch+blob so we can attach the bearer
  // token (an <a download> link can't send custom headers).
  const downloadChecklist = async (kid, filename) => {
    setDownloadingId(kid);
    try {
      const res = await fetch(
        `${API_URL}/api/website-admin/maintenance/checklists/${kid}.pdf`,
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || `${kid}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Downloaded ${filename}`);
    } catch (e) {
      toast.error(`Download failed: ${e.message}`);
    } finally {
      setDownloadingId(null);
    }
  };

  // Re-runs the roadmap PDF generator on the backend (super_admin only).
  const regenerateRoadmap = async () => {
    setRegenerating(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/website-admin/maintenance/checklists/regenerate-roadmap`,
        {}, auth,
      );
      const sizeKb = ((r.data?.size_bytes || 0) / 1024).toFixed(1);
      toast.success(`Roadmap rebuilt — ${sizeKb} KB`);
      await fetchChecklists();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not regenerate');
    } finally {
      setRegenerating(false);
    }
  };

  // Fires a no-op test event to Sentry and toasts the result. Useful as a
  // smoke test right after setting SENTRY_DSN on Railway.
  const sendSentryTest = async () => {
    setSentryTesting(true);
    try {
      const r = await axios.post(`${API_URL}/api/monitoring/sentry/test`, {}, auth);
      if (r.data?.success) {
        toast.success('Test event sent to Sentry', {
          description: r.data.event_id ? `Event ID: ${r.data.event_id}` : 'Check your Sentry dashboard',
        });
      } else {
        toast.error(r.data?.error || 'Test failed — check DSN configuration');
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Sentry test request failed');
    } finally {
      setSentryTesting(false);
    }
  };

  useEffect(() => {
    fetchRuns();
    fetchHealth();
    fetchUiChecks();
    fetchSentryStatus();
    fetchChecklists();
  }, [fetchRuns, fetchHealth, fetchUiChecks, fetchSentryStatus, fetchChecklists]);

  const runTask = async (task) => {
    if (!window.confirm(`Run "${task.label}"?\n\n${task.description}\n\nThis is safe to re-run (idempotent).`)) return;
    setRunningTaskId(task.id);
    try {
      const res = await axios({
        method: task.method,
        url: `${API_URL}${task.endpoint}`,
        ...auth,
      });
      toast.success(task.label, { description: task.summarise(res.data), duration: 9000 });
      await fetchRuns();
    } catch (err) {
      toast.error(err?.response?.data?.detail || `Failed to run ${task.label}`);
    } finally {
      setRunningTaskId(null);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto" data-testid="maintenance-tasks-page">
      <UptimeSparklineWidget />
      <div className="flex items-start justify-between mb-6 mt-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Wrench className="w-6 h-6 text-amber-600" /> Maintenance Tasks
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            One-shot data migrators. Safe to re-run any time — each is idempotent.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <SentryStatusPill
            status={sentryStatus}
            testing={sentryTesting}
            onTest={sendSentryTest}
            onRefresh={fetchSentryStatus}
          />
          <Button variant="outline" size="sm" onClick={() => { fetchRuns(); fetchHealth(); fetchSentryStatus(); }} disabled={loadingRuns || loadingHealth} data-testid="refresh-runs">
            <RefreshCw className={`w-4 h-4 mr-1 ${(loadingRuns || loadingHealth) ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        </div>
      </div>

      {/* Launch Checklists & Roadmap — downloadable PDFs admins can grab
          straight from the live admin without pod / repo access. */}
      <Card className="p-5 mb-6 border-2 border-amber-200 bg-gradient-to-br from-amber-50 to-white" data-testid="launch-checklists-panel">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <FileText className="w-5 h-5 text-amber-600" />
              Launch Checklists &amp; Roadmap
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Pre-generated PDFs covering monitoring strategy, feature ownership, and the
              backbone health checks for Bulk Category Editor &amp; Supplier Products.
            </p>
          </div>
          <Button
            onClick={regenerateRoadmap}
            disabled={regenerating}
            variant="outline"
            size="sm"
            className="border-amber-300 text-amber-700 hover:bg-amber-100"
            data-testid="regenerate-roadmap-btn"
          >
            {regenerating ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <RefreshCw className="w-3 h-3 mr-1" />}
            Rebuild roadmap
          </Button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {checklists.length === 0 ? (
            <p className="text-xs text-gray-400 italic md:col-span-3">Loading checklists…</p>
          ) : checklists.map((c) => (
            <div
              key={c.id}
              className={`rounded-lg border p-3 bg-white transition ${
                c.available ? 'border-gray-200 hover:border-amber-400 hover:shadow-sm' : 'border-gray-100 opacity-60'
              }`}
              data-testid={`checklist-${c.id}`}
            >
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <h3 className="text-sm font-semibold text-gray-900 leading-tight">{c.title}</h3>
                <span className="text-[10px] uppercase tracking-wide font-bold px-1.5 py-0.5 rounded bg-rose-50 text-rose-700">PDF</span>
              </div>
              <p className="text-[11px] text-gray-500 leading-relaxed mb-2 line-clamp-3">
                {c.description}
              </p>
              <div className="flex items-center justify-between text-[10px] text-gray-400 mb-2">
                <span>{c.available ? `${(c.size_bytes / 1024).toFixed(1)} KB` : 'not available'}</span>
                {c.updated_at && (
                  <span title={c.updated_at}>{formatRelativeTime(c.updated_at)}</span>
                )}
              </div>
              <Button
                onClick={() => downloadChecklist(c.id, c.filename)}
                disabled={!c.available || downloadingId === c.id}
                size="sm"
                className="w-full bg-gray-900 hover:bg-gray-800 text-white text-xs h-8"
                data-testid={`download-${c.id}`}
              >
                {downloadingId === c.id ? (
                  <><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Downloading…</>
                ) : (
                  <><Download className="w-3 h-3 mr-1" /> Download</>
                )}
              </Button>
            </div>
          ))}
        </div>
      </Card>

      {/* DB health snapshot — at-a-glance "everything's still humming" */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6" data-testid="health-snapshot">
        {[
          {
            label: 'Total products',
            value: health?.total_products,
            icon: Package,
            tone: 'bg-indigo-50 text-indigo-700 border-indigo-200',
          },
          {
            label: 'Paid orders today',
            value: health?.paid_orders_today,
            icon: ShoppingBag,
            tone: 'bg-emerald-50 text-emerald-700 border-emerald-200',
            sub: health?.revenue_today != null
              ? `£${(health.revenue_today || 0).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} revenue`
              : null,
          },
          {
            label: 'Draft baskets',
            value: health?.draft_carts,
            icon: ShoppingCart,
            tone: 'bg-amber-50 text-amber-700 border-amber-200',
          },
          {
            label: 'Last paid order',
            value: health?.last_paid_order?.order_number ? `#${health.last_paid_order.order_number.slice(-6)}` : '—',
            icon: CreditCard,
            tone: 'bg-rose-50 text-rose-700 border-rose-200',
            sub: health?.last_paid_order?.at
              ? `${formatRelativeTime(health.last_paid_order.at)} · £${(health.last_paid_order.total || 0).toFixed(2)}`
              : null,
          },
        ].map((s, i) => (
          <Card key={i} className={`p-4 border ${s.tone}`} data-testid={`health-card-${i}`}>
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[11px] uppercase tracking-wide font-semibold opacity-80">{s.label}</p>
                <p className="text-2xl font-bold mt-1 tabular-nums">
                  {loadingHealth ? <Loader2 className="w-5 h-5 animate-spin opacity-60" /> : (s.value ?? '—')}
                </p>
                {s.sub && <p className="text-[11px] opacity-70 mt-0.5 truncate">{s.sub}</p>}
              </div>
              <s.icon className="w-5 h-5 opacity-60 flex-shrink-0" />
            </div>
          </Card>
        ))}
      </div>

      {/* Critical UI Health — guards against silent regressions like
          "Trade Login Box vanished" before they hit customers. */}
      <Card className="p-5 mb-6 border-2" data-testid="ui-health-panel">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              {(() => {
                const failed = (uiResults || []).filter(r => r.status === 'fail').length;
                if (runningUi) return <Loader2 className="w-5 h-5 text-amber-500 animate-spin" />;
                if (uiResults.length === 0) return <ShieldCheck className="w-5 h-5 text-gray-300" />;
                return failed > 0
                  ? <ShieldAlert className="w-5 h-5 text-rose-600" />
                  : <ShieldCheck className="w-5 h-5 text-emerald-600" />;
              })()}
              Critical UI Health
              <span className={`text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded ${
                runningUi ? 'bg-amber-100 text-amber-700' :
                uiResults.length === 0 ? 'bg-gray-100 text-gray-500' :
                (uiResults.filter(r => r.status === 'fail').length > 0 ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-700')
              }`}>
                {runningUi ? 'Running…'
                  : uiResults.length === 0 ? 'Never run'
                  : (uiResults.filter(r => r.status === 'fail').length > 0
                      ? `${uiResults.filter(r => r.status === 'fail').length} failing`
                      : 'All passing')}
              </span>
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Loads each critical page in a hidden iframe and verifies the must-have elements rendered.
              {uiLastRun?.ran_at && <> Last run <strong>{formatRelativeTime(uiLastRun.ran_at)}</strong> by {uiLastRun.ran_by}.</>}
              {uiLastRun?.failed_count > 0 && <span className="text-rose-600"> Email alert sent.</span>}
            </p>
          </div>
          <Button
            onClick={runUiChecks}
            disabled={runningUi || uiChecks.length === 0}
            className="bg-indigo-600 hover:bg-indigo-700 text-white"
            data-testid="run-ui-checks"
          >
            {runningUi ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <ShieldCheck className="w-4 h-4 mr-1" />}
            {runningUi ? 'Checking…' : 'Run all checks'}
          </Button>
        </div>
        <div className="space-y-1.5">
          {(uiResults.length ? uiResults : uiChecks).map((r) => {
            const status = r.status || 'pending';
            const isDisabled = !!r.disabled;
            const dot = isDisabled ? 'bg-slate-300'
              : status === 'pass' ? 'bg-emerald-500'
              : status === 'fail' ? 'bg-rose-500'
              : status === 'skipped' ? 'bg-blue-400'
              : status === 'disabled' ? 'bg-slate-400'
              : status === 'running' ? 'bg-amber-400 animate-pulse'
              : 'bg-gray-300';
            return (
              <div
                key={r.id}
                className={`flex items-start gap-2 text-sm ${isDisabled ? 'opacity-60' : ''}`}
                data-testid={`ui-check-${r.id}`}
              >
                <span className={`mt-1.5 inline-block h-2 w-2 rounded-full flex-shrink-0 ${dot}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="font-medium text-gray-900">{r.label}</span>
                    <code className="text-[11px] text-gray-400">{r.url}</code>
                  </div>
                  {status === 'fail' && r.missing?.length > 0 && (
                    <div className="text-[11px] text-rose-700 mt-0.5">
                      Missing: <code className="bg-rose-50 px-1 rounded">{r.missing.join(', ')}</code>
                    </div>
                  )}
                  {(status === 'skipped' || status === 'disabled' || isDisabled) && r.skip_reason && (
                    <div className="text-[11px] text-slate-500 mt-0.5 italic">
                      Skipped: {r.skip_reason}
                    </div>
                  )}
                  {isDisabled && r.disabled_reason && (
                    <div className="text-[11px] text-slate-500 mt-0.5 italic">
                      Disabled: {r.disabled_reason}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => toggleUiCheck(r.id, !isDisabled)}
                  className={`text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded flex-shrink-0 transition border ${
                    isDisabled
                      ? 'bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200'
                      : 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                  }`}
                  title={isDisabled ? 'Click to re-enable this check' : 'Click to disable this check (won\'t count as a failure)'}
                  data-testid={`ui-check-${r.id}-toggle`}
                >
                  {isDisabled ? 'Disabled' : 'Active'}
                </button>
                <span className={`text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded flex-shrink-0 ${
                  isDisabled ? 'bg-slate-50 text-slate-500'
                  : status === 'pass' ? 'bg-emerald-50 text-emerald-700'
                  : status === 'fail' ? 'bg-rose-50 text-rose-700'
                  : status === 'skipped' ? 'bg-blue-50 text-blue-700'
                  : status === 'disabled' ? 'bg-slate-50 text-slate-500'
                  : status === 'running' ? 'bg-amber-50 text-amber-700'
                  : 'bg-gray-50 text-gray-500'
                }`}>{isDisabled && status === 'pending' ? 'disabled' : status}</span>
              </div>
            );
          })}
        </div>
        <p className="text-[11px] text-gray-400 italic mt-3">
          Failures fire an email alert to all super_admin / admin users via Resend.
          Iframe ref scratch space — left here so React keeps the element alive across renders. <span ref={probeFrameRef} className="hidden" />
        </p>

        {/* Daily server-side cron + PDF email schedule */}
        {uiSchedule && (
          <div className="mt-4 pt-4 border-t border-gray-200" data-testid="ui-health-schedule">
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-1.5">
                  <Clock className="w-4 h-4 text-indigo-500" />
                  Daily PDF Report
                  <span className={`text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded ${
                    uiSchedule.settings?.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {uiSchedule.settings?.enabled ? 'On' : 'Off'}
                  </span>
                </h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  Backend runs all checks via headless Chromium and emails a PDF to recipients.
                  Even when nothing is failing, you get a green daily confirmation.
                </p>
              </div>
              <Button
                onClick={triggerServerRun}
                disabled={serverRunning}
                size="sm"
                variant="outline"
                className="border-indigo-200 text-indigo-700 hover:bg-indigo-50"
                data-testid="run-server-ui-checks"
              >
                {serverRunning ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Send className="w-4 h-4 mr-1" />}
                {serverRunning ? 'Running…' : 'Run + Email Now'}
              </Button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <label className="flex items-center gap-2 cursor-pointer p-2 rounded border border-gray-200 hover:border-indigo-300">
                <input
                  type="checkbox"
                  checked={!!uiSchedule.settings?.enabled}
                  onChange={(e) => saveUiSchedule({ enabled: e.target.checked })}
                  disabled={savingSchedule}
                  data-testid="ui-health-enabled-toggle"
                />
                <span>Run daily</span>
              </label>
              <label className="flex items-center gap-2 p-2 rounded border border-gray-200">
                <span className="text-gray-600 whitespace-nowrap">At hour (UTC)</span>
                <input
                  type="number"
                  min={0}
                  max={23}
                  value={uiSchedule.settings?.hour_utc ?? 3}
                  onChange={(e) => setUiSchedule((p) => ({ ...p, settings: { ...(p?.settings || {}), hour_utc: Number(e.target.value) } }))}
                  onBlur={(e) => saveUiSchedule({ hour_utc: Number(e.target.value) })}
                  disabled={savingSchedule}
                  className="w-14 px-1.5 py-0.5 border border-gray-300 rounded text-center"
                  data-testid="ui-health-hour-input"
                />
              </label>
              <label className="flex items-center gap-2 cursor-pointer p-2 rounded border border-gray-200 hover:border-indigo-300">
                <input
                  type="checkbox"
                  checked={!!uiSchedule.settings?.always_email}
                  onChange={(e) => saveUiSchedule({ always_email: e.target.checked })}
                  disabled={savingSchedule}
                  data-testid="ui-health-always-email-toggle"
                />
                <span>Email even when all green</span>
              </label>
            </div>

            <div className="mt-3">
              <label className="text-xs text-gray-600 flex items-center gap-1.5 mb-1">
                <Mail className="w-3.5 h-3.5" />
                Recipients (comma-separated)
                <span className="text-gray-400">— leave blank to auto-pick all super_admin/admin users</span>
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={recipientsDraft}
                  onChange={(e) => setRecipientsDraft(e.target.value)}
                  className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded font-mono"
                  placeholder="alice@tilestation.co.uk, bob@tilestation.co.uk"
                  data-testid="ui-health-recipients-input"
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => saveUiSchedule({ recipients: recipientsDraft })}
                  disabled={savingSchedule}
                  data-testid="save-recipients-btn"
                >
                  Save
                </Button>
              </div>
            </div>

            {uiSchedule.log?.length > 0 && (
              <div className="mt-3 text-[11px]">
                <div className="text-gray-500 font-medium mb-1">Recent runs</div>
                <div className="space-y-0.5">
                  {uiSchedule.log.slice(0, 5).map((row, i) => (
                    <div key={i} className="flex items-center gap-2 text-gray-600" data-testid={`ui-health-log-${i}`}>
                      <span className={`inline-block h-1.5 w-1.5 rounded-full ${
                        row.failed_count > 0 ? 'bg-rose-500' : 'bg-emerald-500'
                      }`} />
                      <span className="font-mono text-[10px]">{formatRelativeTime(row.ran_at)}</span>
                      <span>·</span>
                      <span>{row.passed_count}/{row.total} pass</span>
                      <span className="text-gray-300">·</span>
                      <span className="text-gray-400">{row.triggered_by}</span>
                      {row.email_sent && <Mail className="w-3 h-3 text-emerald-500" />}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Card>

      <div className="space-y-3">
        {TASKS.map((task) => {
          const run = runs[task.id];
          const lastAt = run?.last_run_at;
          const relative = formatRelativeTime(lastAt);
          const isRunning = runningTaskId === task.id;
          return (
            <Card key={task.id} className="p-5" data-testid={`task-${task.id}`}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h2 className="text-base font-semibold text-gray-900">{task.label}</h2>
                  <p className="text-sm text-gray-600 mt-1 leading-relaxed">{task.description}</p>
                  {run ? (
                    <div className="mt-3 flex items-center gap-2 text-xs">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" />
                      <span className="text-gray-700">
                        Last run <strong>{relative}</strong>
                        {run.last_run_by && run.last_run_by !== 'unknown' && (
                          <span className="text-gray-400"> by {run.last_run_by}</span>
                        )}
                      </span>
                      <span className="text-gray-300">·</span>
                      <span className="text-gray-600">{task.summarise(run.last_result)}</span>
                    </div>
                  ) : (
                    <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      Never run
                    </div>
                  )}
                </div>
                <Button
                  onClick={() => runTask(task)}
                  disabled={isRunning}
                  className="bg-amber-500 hover:bg-amber-600 text-white whitespace-nowrap flex-shrink-0"
                  data-testid={`run-${task.id}`}
                >
                  {isRunning ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <ExternalLink className="w-4 h-4 mr-1" />}
                  {isRunning ? 'Running…' : 'Run'}
                </Button>
              </div>
            </Card>
          );
        })}
      </div>

      <p className="text-xs text-gray-400 italic mt-6 text-center">
        Adding a new migrator? Append a row to <code>TASKS</code> in <code>MaintenanceTasks.jsx</code> and call{' '}
        <code>_record_maintenance_run()</code> from the backend route.
      </p>
    </div>
  );
}

/**
 * SentryStatusPill — at-a-glance "is error tracking flowing?" indicator.
 *
 * Colour states:
 *   green  → SDK installed + DSN configured + initialised (events flowing)
 *   amber  → SDK installed but DSN NOT configured (will silently miss errors)
 *   grey   → SDK not installed (server has no Sentry available)
 *   red    → fetch failed / endpoint errored
 *
 * Click → sends a test event via /api/monitoring/sentry/test and toasts the
 * event ID. Useful right after setting SENTRY_DSN on Railway to confirm
 * the DSN is correct without waiting for a real error.
 */
function SentryStatusPill({ status, testing, onTest, onRefresh }) {
  if (!status) {
    return (
      <span
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-gray-100 text-gray-500 border border-gray-200"
        data-testid="sentry-pill-loading"
      >
        <Loader2 className="w-3 h-3 animate-spin" />
        Sentry…
      </span>
    );
  }

  if (status.error) {
    return (
      <button
        onClick={onRefresh}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 transition"
        data-testid="sentry-pill-error"
        title="Click to retry"
      >
        <AlertTriangle className="w-3 h-3" />
        Sentry · unreachable
      </button>
    );
  }

  const sdkOk = !!status.sdk_available;
  const dsnOk = !!status.dsn_configured;
  const initOk = !!status.initialized;

  let tone, label, icon, helpText;
  if (sdkOk && dsnOk && initOk) {
    tone = 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100';
    label = `Sentry · ${status.environment || 'live'}`;
    icon = <Activity className="w-3 h-3" />;
    helpText = 'Click to send a test event';
  } else if (sdkOk && !dsnOk) {
    tone = 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100';
    label = 'Sentry · DSN missing';
    icon = <AlertTriangle className="w-3 h-3" />;
    helpText = 'Set SENTRY_DSN env var on Railway to activate';
  } else if (!sdkOk) {
    tone = 'bg-gray-100 text-gray-500 border-gray-200';
    label = 'Sentry · not installed';
    icon = <ShieldAlert className="w-3 h-3" />;
    helpText = 'sentry-sdk not in this build';
  } else {
    tone = 'bg-amber-50 text-amber-700 border-amber-200';
    label = 'Sentry · not initialised';
    icon = <AlertTriangle className="w-3 h-3" />;
    helpText = 'init_sentry() did not run on startup';
  }

  return (
    <button
      onClick={sdkOk && dsnOk ? onTest : onRefresh}
      disabled={testing}
      title={helpText}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border transition ${tone} disabled:opacity-50`}
      data-testid="sentry-status-pill"
    >
      {testing ? <Loader2 className="w-3 h-3 animate-spin" /> : icon}
      {testing ? 'Sending test…' : label}
    </button>
  );
}
