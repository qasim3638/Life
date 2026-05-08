/**
 * Visualizer Admin — /admin/visualizer
 *
 * Three-in-one cockpit for launch day:
 *   1. Live stats (renders, fal.ai spend, waitlist totals)
 *   2. Pricing config (adhesive/grout/wastage) — pulls into the
 *      Add-to-Basket quote calculator without a code deploy
 *   3. 1-click waitlist launch email + dry-run preview
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import {
  Loader2, Sparkles, Mail, Send, RefreshCw, PoundSterling,
  Image as ImageIcon, Users, Eye, Home, EyeOff, Trash2, RotateCcw,
  Edit3, Plus, ShieldCheck, AlertTriangle, CheckCircle2,
} from 'lucide-react';
import SampleRoomEditor from '../../components/admin/SampleRoomEditor';

const API = process.env.REACT_APP_BACKEND_URL;
const tokenHdr = () => {
  const t = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
  return t ? { Authorization: `Bearer ${t}` } : {};
};

const StatTile = ({ icon, label, value, sub, testid }) => (
  <Card className="p-4" data-testid={testid}>
    <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-slate-500 font-semibold">
      {icon} {label}
    </div>
    <div className="mt-1 text-2xl font-bold text-slate-900">{value}</div>
    {sub && <div className="text-xs text-slate-500 mt-0.5">{sub}</div>}
  </Card>
);


// --- Launch status toggle ---------------------------------------
// DB-backed on/off for the public /visualizer page. Env var (if set)
// still overrides so there's a Railway-side kill-switch for
// emergencies — when that happens we surface a warning so the admin
// knows their toggle won't have an effect until the env var is
// cleared.
const LaunchStatusCard = ({ launch, busy, onToggle }) => {
  const [alsoEmail, setAlsoEmail] = useState(false);
  const unnotified = launch?.waitlist_unnotified || 0;
  const everGoneLive = !!launch?.ever_gone_live;
  const isLive = !!launch?.enabled;
  // Default the email checkbox ON when this is the first-ever go-live
  // AND there are waitlist subscribers to notify — the most common
  // launch-day flow. Admin can still untick if they want to email
  // later from the Launch Email card below. Hooks MUST be called on
  // every render (no early-return before this) to satisfy
  // react-hooks/rules-of-hooks.
  useEffect(() => {
    if (!isLive && !everGoneLive && unnotified > 0) {
      setAlsoEmail(true);
    }
  }, [isLive, everGoneLive, unnotified]);

  if (!launch) return null;
  const envOverride = launch.env_override;  // null = unset, true/false = hard override
  const envLocked = envOverride !== null && envOverride !== undefined;
  const updatedAt = launch.updated_at ? new Date(launch.updated_at).toLocaleString('en-GB') : null;

  return (
    <Card
      className={`mb-6 p-5 border-2 ${isLive ? 'border-emerald-300 bg-emerald-50/40' : 'border-amber-300 bg-amber-50/40'}`}
      data-testid="visualizer-launch-card"
    >
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3 flex-1 min-w-[260px]">
          <div className={`mt-0.5 ${isLive ? 'text-emerald-600' : 'text-amber-600'}`}>
            {isLive ? <CheckCircle2 className="w-7 h-7" /> : <EyeOff className="w-7 h-7" />}
          </div>
          <div>
            <div className="text-xs uppercase tracking-widest font-bold text-slate-500">
              Public visibility
            </div>
            <div className={`text-lg font-bold ${isLive ? 'text-emerald-800' : 'text-amber-800'}`}
                 data-testid="visualizer-launch-state">
              {isLive ? 'LIVE — customers can use the Visualizer' : 'HIDDEN — customers see the Coming Soon page'}
            </div>
            <div className="text-xs text-slate-600 mt-1">
              {isLive
                ? 'Anyone on /visualizer will render against real fal.ai — spend tracked in the stats above.'
                : 'Customers who hit /visualizer see the waitlist-capture page. You can keep improving the feature privately.'}
            </div>
            <div className="text-xs text-slate-500 mt-1.5 flex items-center gap-2 flex-wrap">
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-200 text-slate-700 font-mono text-[10px]">
                DB toggle: {launch.db_enabled ? 'ON' : 'OFF'}
              </span>
              {envLocked && (
                <span
                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-red-100 text-red-800 font-mono text-[10px] border border-red-300"
                  title="The Railway env var VISUALIZER_PUBLIC_ENABLED is forcing this value — clear it to let the toggle take effect"
                >
                  <AlertTriangle className="w-3 h-3" />
                  Env override: {envOverride ? 'TRUE' : 'FALSE'}
                </span>
              )}
              {updatedAt && (
                <span className="text-[11px] text-slate-500">
                  Last changed {updatedAt}{launch.updated_by ? ` by ${launch.updated_by}` : ''}
                </span>
              )}
            </div>
            {/* One-click "Go live + email waitlist" option — only shown
                when the toggle is currently OFF and there are
                unnotified subscribers. Idempotent on the backend
                (notified=true won't re-email). */}
            {!isLive && unnotified > 0 && !envLocked && (
              <label
                className="mt-3 flex items-center gap-2 cursor-pointer text-xs text-slate-700 hover:text-slate-900"
                data-testid="visualizer-launch-also-email-label"
              >
                <input
                  type="checkbox"
                  checked={alsoEmail}
                  onChange={(e) => setAlsoEmail(e.target.checked)}
                  className="rounded border-slate-400 text-emerald-600 focus:ring-emerald-500"
                  data-testid="visualizer-launch-also-email"
                />
                <Mail className="w-3.5 h-3.5 text-emerald-700" />
                <span>
                  Also email the <strong>{unnotified}</strong> waitlist
                  {unnotified === 1 ? ' subscriber' : ' subscribers'} now (one launch email, idempotent)
                </span>
              </label>
            )}
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button
            onClick={() => onToggle(true, alsoEmail)}
            disabled={busy || isLive}
            className={isLive
              ? 'bg-emerald-100 text-emerald-700 cursor-not-allowed border border-emerald-200'
              : 'bg-emerald-600 hover:bg-emerald-700 text-white font-bold'}
            data-testid="visualizer-launch-go-live-btn"
          >
            {busy ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <CheckCircle2 className="w-4 h-4 mr-1" />}
            {isLive
              ? 'Already live'
              : (alsoEmail && unnotified > 0
                  ? `Go live + email ${unnotified}`
                  : 'Go live publicly')}
          </Button>
          <Button
            onClick={() => onToggle(false, false)}
            disabled={busy || !isLive}
            variant="outline"
            className={!isLive
              ? 'border-slate-300 text-slate-400 cursor-not-allowed'
              : 'border-amber-400 text-amber-800 hover:bg-amber-50 font-bold'}
            data-testid="visualizer-launch-hide-btn"
          >
            {busy ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <EyeOff className="w-4 h-4 mr-1" />}
            Hide from public
          </Button>
        </div>
      </div>
      {envLocked && (
        <div className="mt-3 text-xs text-red-800 bg-red-50 border border-red-200 rounded px-3 py-2" data-testid="visualizer-launch-env-warning">
          <strong>Railway env var is forcing this value.</strong> The DB toggle below is saved but won't take effect until
          {' '}<code>VISUALIZER_PUBLIC_ENABLED</code> is cleared on the backend Railway service.
        </div>
      )}
    </Card>
  );
};


const VisualizerAdmin = () => {
  const [stats, setStats] = useState(null);
  const [pricing, setPricing] = useState(null);
  const [pricingDirty, setPricingDirty] = useState(false);
  const [savingPricing, setSavingPricing] = useState(false);
  const [loading, setLoading] = useState(true);

  // Sample rooms management
  const [rooms, setRooms] = useState([]);
  const [roomsBusy, setRoomsBusy] = useState(false);
  const [reseeding, setReseeding] = useState(false);
  const [editorRoom, setEditorRoom] = useState(null);  // null=closed, {} = new, {id,...} = edit existing
  const [editorOpen, setEditorOpen] = useState(false);
  const [validation, setValidation] = useState(null);  // {summary, results: [{id, status, reasons, ...}]}
  const [validating, setValidating] = useState(false);

  // Launch-email form state
  const [emailSubject, setEmailSubject] = useState('Tile Visualizer is live ✨');
  const [emailHeadline, setEmailHeadline] = useState('Your tile visualizer is ready');
  const [emailCta, setEmailCta] = useState('Try the Visualizer');
  const [emailCtaUrl, setEmailCtaUrl] = useState('https://tilestation.co.uk/visualizer');
  const [emailBody, setEmailBody] = useState(
    "<p>You signed up to be notified when our Tile Visualizer went live — and today's the day. Pick any tile from our catalogue, drop it into a sample room or your own photo, and see exactly how it'll look. Free preview, no signup required.</p>"
    + "<p>As a thank-you for waiting, your first photoreal render is on us.</p>"
  );
  const [sending, setSending] = useState(false);
  const [dryRunResult, setDryRunResult] = useState(null);

  // Launch-status toggle — DB-backed feature flag that replaces the
  // old VISUALIZER_PUBLIC_ENABLED env-only switch. Env var still wins
  // when set, which the UI surfaces so admin knows a Railway var is
  // overriding the toggle.
  const [launch, setLaunch] = useState(null);  // {enabled, db_enabled, env_override, updated_by, updated_at}
  const [launchBusy, setLaunchBusy] = useState(false);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [s, p, r, l] = await Promise.all([
        axios.get(`${API}/api/admin/visualizer/stats`, { headers: tokenHdr() }),
        axios.get(`${API}/api/admin/visualizer/pricing`, { headers: tokenHdr() }),
        axios.get(`${API}/api/admin/visualizer/sample-rooms`, { headers: tokenHdr() }),
        axios.get(`${API}/api/admin/visualizer/launch-status`, { headers: tokenHdr() }),
      ]);
      setStats(s.data);
      setPricing(p.data.pricing);
      setRooms(r.data?.rooms || []);
      setLaunch(l.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not load visualizer admin data');
    } finally {
      setLoading(false);
    }
  };

  const setLaunchEnabled = async (nextEnabled, alsoEmail = false) => {
    const isGoingLive = !!nextEnabled && !launch?.enabled;
    if (isGoingLive) {
      const msg = alsoEmail
        ? `Go live publicly AND email the ${launch?.waitlist_unnotified || 0} waitlist subscribers?\n\n`
          + 'Every visitor to /visualizer will see the real tool from the next request onward. '
          + 'One launch email will be sent to unnotified waitlist members (idempotent — '
          + 'nobody gets emailed twice).'
        : 'Go live publicly?\n\n'
          + 'Every visitor to /visualizer will see the real tool (not the Coming Soon page) '
          + 'from the next request onward. You can flip it back off any time.';
      if (!window.confirm(msg)) return;
    }
    setLaunchBusy(true);
    try {
      const r = await axios.post(
        `${API}/api/admin/visualizer/launch-status`,
        { enabled: !!nextEnabled, also_email_waitlist: !!alsoEmail },
        { headers: tokenHdr() },
      );
      setLaunch((prev) => ({ ...(prev || {}), ...r.data, updated_at: new Date().toISOString() }));
      if (nextEnabled) {
        if (alsoEmail && r.data?.email_result?.sent !== undefined) {
          toast.success(
            `Visualizer LIVE ✨ · emailed ${r.data.email_result.sent} waitlist subscribers`
            + (r.data.email_result.failed ? ` (${r.data.email_result.failed} failed)` : ''),
          );
        } else if (alsoEmail && r.data?.email_result?.error) {
          toast.error(`Visualizer is LIVE, but the launch email failed: ${r.data.email_result.error}`);
        } else {
          toast.success('Visualizer is now live for customers');
        }
        await fetchAll();  // refresh waitlist_unnotified + stats
      } else {
        toast.success('Visualizer hidden from customers — admins can still preview via ?preview=1');
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Toggle failed');
    } finally {
      setLaunchBusy(false);
    }
  };

  const toggleRoomActive = async (room) => {
    setRoomsBusy(true);
    try {
      await axios.patch(`${API}/api/admin/visualizer/sample-rooms/${room.id}/toggle`,
        { active: !room.active }, { headers: tokenHdr() });
      setRooms((rs) => rs.map((r) => r.id === room.id ? { ...r, active: !room.active } : r));
      toast.success(`${room.label} ${!room.active ? 'enabled' : 'hidden'}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Toggle failed');
    } finally {
      setRoomsBusy(false);
    }
  };

  const deleteRoom = async (room) => {
    if (!window.confirm(`Delete "${room.label}"? This cannot be undone — re-seed defaults to restore curated rooms.`)) return;
    setRoomsBusy(true);
    try {
      await axios.delete(`${API}/api/admin/visualizer/sample-rooms/${room.id}`, { headers: tokenHdr() });
      setRooms((rs) => rs.filter((r) => r.id !== room.id));
      toast.success(`Deleted ${room.label}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Delete failed');
    } finally {
      setRoomsBusy(false);
    }
  };

  const reseedRooms = async (force) => {
    setReseeding(true);
    try {
      const r = await axios.post(`${API}/api/admin/visualizer/sample-rooms/reseed`,
        null, { params: { force: !!force }, headers: tokenHdr() });
      if (r.data.skipped) {
        toast.message(`Skipped — ${r.data.existing} rooms already exist. Use Force re-seed to overwrite.`);
      } else {
        toast.success(`Re-seeded ${r.data.seeded} curated rooms`);
      }
      await fetchAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Re-seed failed');
    } finally {
      setReseeding(false);
    }
  };

  const validatePolygons = async () => {
    setValidating(true);
    try {
      const r = await axios.post(
        `${API}/api/admin/visualizer/sample-rooms/validate-polygons`,
        null,
        { headers: tokenHdr(), timeout: 120000 },
      );
      setValidation(r.data);
      const s = r.data.summary || {};
      if (s.bad > 0) {
        toast.error(`${s.bad} room(s) need fixing — see issues below`);
      } else if (s.warn > 0) {
        toast.warning(`${s.warn} room(s) have warnings — review below`);
      } else {
        toast.success(`All ${s.total} polygons look good!`);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Validation failed');
    } finally {
      setValidating(false);
    }
  };

  // Lookup the validation status for a given room id (for the status pill)
  const validationFor = (roomId) => {
    if (!validation?.results) return null;
    return validation.results.find((r) => r.id === roomId) || null;
  };

  useEffect(() => { fetchAll(); }, []);

  const updatePricing = (key, val) => {
    setPricing((p) => ({ ...p, [key]: val }));
    setPricingDirty(true);
  };

  const savePricing = async () => {
    setSavingPricing(true);
    try {
      const r = await axios.put(`${API}/api/admin/visualizer/pricing`, {
        adhesive_price_per_bag: Number(pricing.adhesive_price_per_bag),
        grout_price_per_bag: Number(pricing.grout_price_per_bag),
        wastage_percent: Number(pricing.wastage_percent),
        floor_m2_per_adhesive_bag: Number(pricing.floor_m2_per_adhesive_bag),
        wall_m2_per_adhesive_bag: Number(pricing.wall_m2_per_adhesive_bag),
        m2_per_grout_bag: Number(pricing.m2_per_grout_bag),
      }, { headers: tokenHdr() });
      setPricing(r.data.pricing);
      setPricingDirty(false);
      toast.success('Pricing updated — all new quotes use these values');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not save pricing');
    } finally {
      setSavingPricing(false);
    }
  };

  const sendLaunchEmail = async (dryRun) => {
    setSending(true);
    setDryRunResult(null);
    try {
      const r = await axios.post(`${API}/api/admin/visualizer/waitlist/send-launch-email`, {
        subject: emailSubject,
        headline: emailHeadline,
        body_html: emailBody,
        cta_text: emailCta,
        cta_url: emailCtaUrl,
        dry_run: !!dryRun,
      }, { headers: tokenHdr() });
      if (dryRun) {
        setDryRunResult(r.data);
        toast.message(`Dry run: would email ${r.data.would_send} people`);
      } else {
        toast.success(`Sent to ${r.data.sent} waitlist members${r.data.failed ? ` (${r.data.failed} failed)` : ''}`);
        await fetchAll();  // refresh waitlist counts
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Email send failed');
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center text-slate-500">
        <Loader2 className="w-6 h-6 animate-spin text-yellow-500 mr-2" /> Loading visualizer admin…
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto" data-testid="visualizer-admin-page">
      <div className="mb-6 flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-2">
            <Sparkles className="w-7 h-7 text-yellow-500" /> Tile Visualizer
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Live stats, pricing config, and 1-click launch email for the waitlist.
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.open('/visualizer?preview=1', '_blank')}
            className="border-slate-300"
            data-testid="visualizer-admin-preview-btn"
          >
            <Eye className="w-4 h-4 mr-1" /> Preview as customer
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchAll}
            className="border-slate-300"
            data-testid="visualizer-admin-refresh-btn"
          >
            <RefreshCw className="w-4 h-4 mr-1" /> Refresh
          </Button>
        </div>
      </div>

      {/* Launch toggle — DB-backed, replaces the old Railway env-var only switch */}
      <LaunchStatusCard
        launch={launch}
        busy={launchBusy}
        onToggle={setLaunchEnabled}
      />

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <StatTile
            icon={<ImageIcon className="w-3.5 h-3.5 text-yellow-500" />}
            label="Total renders"
            value={stats.totals?.renders ?? 0}
            sub={`${stats.totals?.fast ?? 0} fast · ${stats.totals?.photoreal ?? 0} photoreal`}
            testid="visualizer-admin-stat-renders"
          />
          <StatTile
            icon={<PoundSterling className="w-3.5 h-3.5 text-emerald-500" />}
            label="fal.ai spend"
            value={`$${(stats.totals?.fal_spend_usd ?? 0).toFixed(2)}`}
            sub={`≈ £${(stats.totals?.fal_spend_gbp_estimate ?? 0).toFixed(2)}`}
            testid="visualizer-admin-stat-spend"
          />
          <StatTile
            icon={<Users className="w-3.5 h-3.5 text-blue-500" />}
            label="Waitlist"
            value={stats.waitlist?.total ?? 0}
            sub={`${stats.waitlist?.unnotified ?? 0} unnotified`}
            testid="visualizer-admin-stat-waitlist"
          />
          <StatTile
            icon={<Eye className="w-3.5 h-3.5 text-purple-500" />}
            label="Sessions"
            value={stats.sessions ?? 0}
            sub={`${stats.active_rooms ?? 0} active rooms`}
            testid="visualizer-admin-stat-sessions"
          />
        </div>
      )}

      {/* Sample rooms */}
      <Card className="p-5 mb-6" data-testid="visualizer-admin-rooms-card">
        <div className="flex items-start justify-between gap-3 mb-3 flex-wrap">
          <div>
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Home className="w-5 h-5 text-yellow-600" /> Sample rooms
              <span className="text-xs font-normal text-slate-500">({rooms.length})</span>
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Customers see active rooms on <code>/visualizer</code>. Hide rooms to remove from the picker without deleting them.
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button
              size="sm"
              onClick={() => { setEditorRoom({}); setEditorOpen(true); }}
              className="bg-slate-900 hover:bg-slate-800 text-yellow-300 font-bold"
              data-testid="visualizer-admin-add-room-btn"
            >
              <Plus className="w-4 h-4 mr-1" /> Add room
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={validatePolygons}
              disabled={validating}
              className="border-blue-300 text-blue-800 hover:bg-blue-50"
              data-testid="visualizer-admin-validate-btn"
              title="Download every active room's image, detect its real dimensions, and flag broken polygons."
            >
              {validating ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <ShieldCheck className="w-4 h-4 mr-1" />}
              Validate polygons
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => reseedRooms(false)}
              disabled={reseeding}
              className="border-slate-300"
              data-testid="visualizer-admin-reseed-btn"
            >
              {reseeding ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <RotateCcw className="w-4 h-4 mr-1" />}
              Re-seed if empty
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (!window.confirm('Force re-seed will overwrite ALL 10 curated rooms with their default polygons. Custom edits to those room IDs will be lost. Continue?')) return;
                reseedRooms(true);
              }}
              disabled={reseeding}
              className="border-amber-300 text-amber-800 hover:bg-amber-50"
              data-testid="visualizer-admin-reseed-force-btn"
            >
              {reseeding ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <RotateCcw className="w-4 h-4 mr-1" />}
              Force re-seed
            </Button>
          </div>
        </div>

        {validation && (
          <div className="mb-3 p-3 rounded-lg border bg-slate-50 border-slate-200 text-sm" data-testid="visualizer-admin-validation-summary">
            <div className="flex items-center gap-3 flex-wrap mb-1">
              <span className="font-bold text-slate-900">Polygon validation</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold">
                <CheckCircle2 className="w-3 h-3 inline mr-0.5" />
                {validation.summary?.ok} OK
              </span>
              {(validation.summary?.warn || 0) > 0 && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-bold">
                  <AlertTriangle className="w-3 h-3 inline mr-0.5" />
                  {validation.summary.warn} warn
                </span>
              )}
              {(validation.summary?.bad || 0) > 0 && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-800 font-bold">
                  <AlertTriangle className="w-3 h-3 inline mr-0.5" />
                  {validation.summary.bad} bad
                </span>
              )}
            </div>
            {validation.results.filter((r) => r.status !== 'ok').length > 0 && (
              <ul className="text-xs text-slate-700 space-y-1 mt-2" data-testid="visualizer-admin-validation-issues">
                {validation.results.filter((r) => r.status !== 'ok').map((r) => (
                  <li key={r.id} className="flex items-start gap-2" data-testid={`visualizer-admin-validation-issue-${r.id}`}>
                    <span className={`shrink-0 mt-0.5 inline-block w-1.5 h-1.5 rounded-full ${r.status === 'bad' ? 'bg-red-500' : 'bg-amber-500'}`}></span>
                    <span>
                      <span className="font-semibold">{r.label}</span> — {(r.reasons || []).join('; ')}
                      {' '}
                      <button
                        type="button"
                        onClick={() => { const room = rooms.find((x) => x.id === r.id); if (room) { setEditorRoom(room); setEditorOpen(true); } }}
                        className="text-blue-700 hover:underline"
                        data-testid={`visualizer-admin-validation-fix-${r.id}`}
                      >
                        (Fix in editor)
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {rooms.length === 0 ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" data-testid="visualizer-admin-rooms-empty">
            <div className="font-bold mb-1">No sample rooms yet</div>
            <div className="text-xs">
              The visualizer will only show the "Upload your own" card to customers. Click <span className="font-semibold">Re-seed if empty</span> to install the 10 curated rooms.
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3" data-testid="visualizer-admin-rooms-grid">
            {rooms.map((r) => {
              const v = validationFor(r.id);
              return (
              <div
                key={r.id}
                className={`relative rounded-lg overflow-hidden border ${r.active === false ? 'border-slate-300 opacity-60' : 'border-slate-200'}`}
                data-testid={`visualizer-admin-room-${r.id}`}
              >
                <img
                  src={r.image_url}
                  alt={r.label}
                  className="w-full h-28 object-cover bg-slate-100"
                  loading="lazy"
                  onError={(e) => {
                    // Unsplash CDN URLs occasionally 404 on stale photo IDs —
                    // swap in an inline SVG placeholder so admins still see
                    // something (label + room type) and can decide to replace.
                    e.currentTarget.style.display = 'none';
                    if (e.currentTarget.nextSibling) e.currentTarget.nextSibling.style.display = 'flex';
                  }}
                />
                <div className="hidden w-full h-28 bg-slate-100 items-center justify-center text-[10px] text-slate-500 px-2 text-center" data-testid={`visualizer-admin-room-fallback-${r.id}`}>
                  Image unavailable<br />(upstream 404)
                </div>
                {v && v.status !== 'ok' && (
                  <div
                    className={`absolute top-1 left-1 text-[9px] font-bold px-1.5 py-0.5 rounded shadow flex items-center gap-1 ${
                      v.status === 'bad' ? 'bg-red-600 text-white' : 'bg-amber-500 text-white'
                    }`}
                    title={(v.reasons || []).join('; ')}
                    data-testid={`visualizer-admin-room-status-${r.id}`}
                  >
                    <AlertTriangle className="w-2.5 h-2.5" />
                    {v.status === 'bad' ? 'BAD' : 'WARN'}
                  </div>
                )}
                <div className="p-2">
                  <div className="text-xs font-semibold text-slate-900 truncate">{r.label}</div>
                  <div className="text-[10px] text-slate-500 uppercase tracking-wide">
                    {r.room_type} · {r.surface_kind} · {r.default_surface_m2}m²
                  </div>
                  <div className="mt-1.5 flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => toggleRoomActive(r)}
                      disabled={roomsBusy}
                      className={`text-[10px] px-1.5 py-0.5 rounded font-semibold flex items-center gap-1 ${
                        r.active === false
                          ? 'bg-slate-200 text-slate-700 hover:bg-slate-300'
                          : 'bg-emerald-100 text-emerald-800 hover:bg-emerald-200'
                      }`}
                      data-testid={`visualizer-admin-room-toggle-${r.id}`}
                    >
                      {r.active === false ? <><EyeOff className="w-3 h-3" /> Hidden</> : <><Eye className="w-3 h-3" /> Active</>}
                    </button>
                    <button
                      type="button"
                      onClick={() => { setEditorRoom(r); setEditorOpen(true); }}
                      disabled={roomsBusy}
                      className="text-[10px] px-1.5 py-0.5 rounded font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 flex items-center gap-1"
                      data-testid={`visualizer-admin-room-edit-${r.id}`}
                      title="Edit room"
                    >
                      <Edit3 className="w-3 h-3" /> Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteRoom(r)}
                      disabled={roomsBusy}
                      className="ml-auto text-[10px] px-1.5 py-0.5 rounded font-semibold bg-red-50 text-red-700 hover:bg-red-100 flex items-center gap-1"
                      data-testid={`visualizer-admin-room-delete-${r.id}`}
                      title="Delete room"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Pricing config */}
      <Card className="p-5 mb-6" data-testid="visualizer-admin-pricing-card">
        <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
          <div>
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <PoundSterling className="w-5 h-5 text-emerald-600" /> Quote calculator pricing
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              These values feed every "Add to basket" quote on the visualizer. Update here without a code deploy.
            </p>
          </div>
          <Button
            onClick={savePricing}
            disabled={!pricingDirty || savingPricing}
            className="bg-slate-900 hover:bg-slate-800 text-yellow-300 font-bold"
            data-testid="visualizer-admin-pricing-save-btn"
          >
            {savingPricing ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
            Save pricing
          </Button>
        </div>
        {pricing && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <PricingField label="Adhesive £ / bag" value={pricing.adhesive_price_per_bag} step="0.01" onChange={(v) => updatePricing('adhesive_price_per_bag', v)} testid="adhesive-price-input" />
            <PricingField label="Grout £ / bag" value={pricing.grout_price_per_bag} step="0.01" onChange={(v) => updatePricing('grout_price_per_bag', v)} testid="grout-price-input" />
            <PricingField label="Wastage %" value={pricing.wastage_percent} step="1" onChange={(v) => updatePricing('wastage_percent', v)} testid="wastage-percent-input" />
            <PricingField label="Floor m² per adhesive bag" value={pricing.floor_m2_per_adhesive_bag} step="0.5" onChange={(v) => updatePricing('floor_m2_per_adhesive_bag', v)} testid="floor-adhesive-ratio-input" />
            <PricingField label="Wall m² per adhesive bag" value={pricing.wall_m2_per_adhesive_bag} step="0.5" onChange={(v) => updatePricing('wall_m2_per_adhesive_bag', v)} testid="wall-adhesive-ratio-input" />
            <PricingField label="m² per grout bag" value={pricing.m2_per_grout_bag} step="0.5" onChange={(v) => updatePricing('m2_per_grout_bag', v)} testid="grout-ratio-input" />
          </div>
        )}
      </Card>

      {/* Launch email */}
      <Card className="p-5" data-testid="visualizer-admin-launch-email-card">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2 mb-1">
          <Mail className="w-5 h-5 text-blue-600" /> Email the waitlist
        </h2>
        <p className="text-xs text-slate-500 mb-4">
          Sends to everyone marked <code>notified=false</code> ({stats?.waitlist?.unnotified ?? 0} people).
          After a successful send they're auto-marked notified so you can re-edit + re-send to fresh signups later.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
          <FormField label="Subject" value={emailSubject} onChange={setEmailSubject} testid="email-subject-input" />
          <FormField label="Headline (in-email)" value={emailHeadline} onChange={setEmailHeadline} testid="email-headline-input" />
          <FormField label="CTA button text" value={emailCta} onChange={setEmailCta} testid="email-cta-input" />
          <FormField label="CTA button URL" value={emailCtaUrl} onChange={setEmailCtaUrl} testid="email-cta-url-input" />
        </div>
        <label className="block text-xs font-semibold text-slate-700 mb-1">Body HTML</label>
        <Textarea
          value={emailBody}
          onChange={(e) => setEmailBody(e.target.value)}
          rows={6}
          className="font-mono text-xs"
          data-testid="email-body-input"
        />

        <div className="mt-4 flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            onClick={() => sendLaunchEmail(true)}
            disabled={sending}
            className="border-slate-300"
            data-testid="visualizer-admin-launch-dryrun-btn"
          >
            {sending ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Eye className="w-4 h-4 mr-1" />}
            Dry run (preview recipients)
          </Button>
          <Button
            onClick={() => {
              if (!window.confirm(`Send to ${stats?.waitlist?.unnotified ?? 0} waitlist members? This cannot be undone.`)) return;
              sendLaunchEmail(false);
            }}
            disabled={sending || (stats?.waitlist?.unnotified ?? 0) === 0}
            className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold"
            data-testid="visualizer-admin-launch-send-btn"
          >
            {sending ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />}
            Send launch email
          </Button>
        </div>

        {dryRunResult && (
          <div className="mt-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs" data-testid="visualizer-admin-dryrun-result">
            <div className="font-bold text-amber-900 mb-1">Dry run — would send to {dryRunResult.would_send} people</div>
            <div className="text-amber-800 break-words">
              First 25: {(dryRunResult.recipients_preview || []).join(', ') || '—'}
            </div>
          </div>
        )}
      </Card>

      {editorOpen && (
        <SampleRoomEditor
          room={editorRoom}
          onClose={() => { setEditorOpen(false); setEditorRoom(null); }}
          onSaved={async () => {
            setEditorOpen(false);
            setEditorRoom(null);
            await fetchAll();
          }}
        />
      )}
    </div>
  );
};

const PricingField = ({ label, value, step, onChange, testid }) => (
  <div>
    <label className="block text-xs font-semibold text-slate-700 mb-1">{label}</label>
    <Input
      type="number"
      step={step}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      data-testid={testid}
    />
  </div>
);

const FormField = ({ label, value, onChange, testid }) => (
  <div>
    <label className="block text-xs font-semibold text-slate-700 mb-1">{label}</label>
    <Input value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid} />
  </div>
);

export default VisualizerAdmin;
