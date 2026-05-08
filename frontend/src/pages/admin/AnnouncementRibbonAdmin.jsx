import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Megaphone, Save, Eye, RefreshCw, Calendar, CheckCircle2, Zap, History, RotateCcw } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Switch } from '../../components/ui/switch';
import { Textarea } from '../../components/ui/textarea';
import AnnouncementRibbon from '../../components/shop/AnnouncementRibbon';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const PRESET_THEMES = [
  { name: 'Charcoal · Yellow', bg: '#1C1917', fg: '#F7EA1C', link: '#FFFFFF' },
  { name: 'Tile Yellow · Black', bg: '#F7EA1C', fg: '#1C1917', link: '#1C1917' },
  { name: 'Holiday Red', bg: '#9F1239', fg: '#FFFFFF', link: '#FDE68A' },
  { name: 'Spring Green', bg: '#065F46', fg: '#ECFDF5', link: '#FCD34D' },
  { name: 'Trade Slate', bg: '#1E293B', fg: '#FBBF24', link: '#FFFFFF' },
  { name: 'Soft Cream', bg: '#FEF3C7', fg: '#78350F', link: '#9F1239' },
];

const DEFAULTS = {
  enabled: false,
  message: 'Free delivery on orders over £499 · 28-day returns · Trade pricing live now',
  link_url: '',
  link_label: '',
  speed: 'medium',          // slow | medium | fast
  background_color: '#1C1917',
  text_color: '#F7EA1C',
  link_color: '#FFFFFF',
  icon: true,
  version: 1,
  schedule_enabled: false,
  scheduled_start: null,
  scheduled_end: null,
  history: [],
};

// "2 mins ago" / "3 hours ago" / "Yesterday 14:05" — compact relative time
// for the Quick Post history log. Falls back to the full local date after 6 days.
const timeAgo = (iso) => {
  if (!iso) return '—';
  try {
    const then = new Date(iso).getTime();
    if (Number.isNaN(then)) return '—';
    const diffMs = Date.now() - then;
    const sec = Math.round(diffMs / 1000);
    if (sec < 10) return 'just now';
    if (sec < 60) return `${sec}s ago`;
    const min = Math.round(sec / 60);
    if (min < 60) return `${min} min${min === 1 ? '' : 's'} ago`;
    const hr = Math.round(min / 60);
    if (hr < 24) return `${hr} hour${hr === 1 ? '' : 's'} ago`;
    const days = Math.round(hr / 24);
    if (days < 7) return `${days} day${days === 1 ? '' : 's'} ago`;
    return new Date(iso).toLocaleString(undefined, {
      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
};

// Convert a UTC ISO string ↔ a value the <input type="datetime-local"> can show.
// The input is timezone-naive so we render in the browser's local TZ for editing,
// then convert back to UTC ISO when saving.
const isoToLocalInput = (iso) => {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch { return ''; }
};
const localInputToIso = (val) => {
  if (!val) return null;
  try {
    const d = new Date(val);
    return Number.isNaN(d.getTime()) ? null : d.toISOString();
  } catch { return null; }
};

const formatLocal = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: 'short', day: 'numeric', month: 'short',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
};

// ----- Quick-preset date helpers -----
// Each preset returns local-time anchored Date objects; the form converts
// to UTC ISO before saving. Kept as plain functions (not memoised) since
// they're invoked at click-time only.
const addHours = (h) => new Date(Date.now() + h * 3600 * 1000);

const startOfDay = (d) => { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; };
const endOfDay = (d) => { const x = new Date(d); x.setHours(23, 59, 0, 0); return x; };

// Friday 17:00 → Monday 08:00 of the upcoming weekend
const nextWeekend = () => {
  const now = new Date();
  const day = now.getDay();           // 0=Sun … 6=Sat
  const daysUntilFri = (5 - day + 7) % 7 || 7;
  const fri = new Date(now);
  fri.setDate(now.getDate() + daysUntilFri);
  fri.setHours(17, 0, 0, 0);
  const mon = new Date(fri);
  mon.setDate(fri.getDate() + 3);
  mon.setHours(8, 0, 0, 0);
  return { start: fri, end: mon };
};

// Next UK bank-holiday Monday (last Monday of May or August — close enough
// for an out-of-the-box preset; admins can tweak the dates after).
const bankHoliday = () => {
  const now = new Date();
  const candidates = [];
  for (let monthOffset = 0; monthOffset < 14; monthOffset++) {
    const probe = new Date(now.getFullYear(), now.getMonth() + monthOffset, 1);
    if (![4, 7].includes(probe.getMonth())) continue;  // May=4, Aug=7
    // last Monday of probe.month
    const last = new Date(probe.getFullYear(), probe.getMonth() + 1, 0);
    while (last.getDay() !== 1) last.setDate(last.getDate() - 1);
    if (last > now) candidates.push(last);
  }
  const target = candidates[0] || addHours(24 * 30);
  // Friday 17:00 of that week → Tuesday 08:00 (covers the long weekend)
  const start = new Date(target);
  start.setDate(target.getDate() - 3);
  start.setHours(17, 0, 0, 0);
  const end = new Date(target);
  end.setDate(target.getDate() + 1);
  end.setHours(8, 0, 0, 0);
  return { start, end };
};

// Black Friday (4th Friday of November) → Cyber Monday end-of-day
const blackFriday = () => {
  const now = new Date();
  let year = now.getFullYear();
  // If we're past this year's window, jump to next year
  if (now.getMonth() === 10 && now.getDate() > 30) year += 1;
  if (now.getMonth() === 11) year += 1;
  const novFirst = new Date(year, 10, 1);
  // 4th Thursday = Thanksgiving, then +1 = Black Friday
  let thanksgiving = new Date(novFirst);
  while (thanksgiving.getDay() !== 4) thanksgiving.setDate(thanksgiving.getDate() + 1);
  thanksgiving.setDate(thanksgiving.getDate() + 21);  // 4th Thursday
  const friday = new Date(thanksgiving);
  friday.setDate(thanksgiving.getDate() + 1);
  friday.setHours(0, 0, 0, 0);
  const cyberMonday = new Date(friday);
  cyberMonday.setDate(friday.getDate() + 3);
  cyberMonday.setHours(23, 59, 0, 0);
  return { start: friday, end: cyberMonday };
};

// Friendly "lasts X days, starts in Y hours" copy beneath the schedule
const describeWindow = (startIso, endIso) => {
  if (!startIso || !endIso) return '';
  try {
    const start = new Date(startIso).getTime();
    const end = new Date(endIso).getTime();
    const now = Date.now();
    if (Number.isNaN(start) || Number.isNaN(end)) return '';
    const durationH = Math.round((end - start) / 3600 / 1000);
    const days = Math.floor(durationH / 24);
    const hours = durationH % 24;
    const durationStr = days > 0
      ? `${days}d${hours ? ` ${hours}h` : ''}`
      : `${durationH}h`;

    if (now < start) {
      const inH = Math.round((start - now) / 3600 / 1000);
      const inDays = Math.floor(inH / 24);
      const inLeft = inH % 24;
      const inStr = inDays > 0
        ? `${inDays}d${inLeft ? ` ${inLeft}h` : ''}`
        : `${inH}h`;
      return `Lasts ${durationStr}. Will go live in ${inStr}.`;
    }
    if (now > end) return `Lasts ${durationStr}. This window has already ended.`;
    const remH = Math.round((end - now) / 3600 / 1000);
    return `Lasts ${durationStr}. Currently active — ends in ~${remH}h.`;
  } catch { return ''; }
};

export default function AnnouncementRibbonAdmin() {
  const [cfg, setCfg] = useState(DEFAULTS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewKey, setPreviewKey] = useState(0);
  // Quick Post — single-field composer that publishes a ribbon with sensible
  // defaults in one click. Used for "stock alert / promo just dropped" cases
  // where you don't want to scroll through 8 fields.
  const [quickMessage, setQuickMessage] = useState('');
  const [quickPosting, setQuickPosting] = useState(false);

  const auth = { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } };

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/website-admin/announcement-ribbon`, auth);
      setCfg({ ...DEFAULTS, ...(r.data || {}) });
    } catch {
      setCfg(DEFAULTS);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  const update = (patch) => setCfg((c) => ({ ...c, ...patch }));

  const save = async (bumpVersion = false) => {
    setSaving(true);
    try {
      const payload = {
        ...cfg,
        version: bumpVersion ? (cfg.version || 1) + 1 : (cfg.version || 1),
      };
      const r = await axios.put(`${API_URL}/api/website-admin/announcement-ribbon`, payload, auth);
      setCfg({ ...DEFAULTS, ...(r.data || {}) });
      setPreviewKey((k) => k + 1);
      toast.success(bumpVersion
        ? 'Saved and re-shown to dismissed visitors'
        : 'Announcement saved');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not save');
    } finally {
      setSaving(false);
    }
  };

  /**
   * Quick Post — pushes the typed message live with safe defaults regardless
   * of whatever's been edited in the form below. Bumps version so dismissed
   * visitors see it again. One-click "publish right now" path.
   *
   * `overrides` lets the History "re-publish" button supply the original
   * theme/CTA for that past post instead of the default charcoal-yellow.
   */
  const quickPost = async (overrides = null) => {
    const source = overrides || { message: quickMessage };
    const msg = (source.message || '').trim();
    if (!msg) {
      toast.error('Type a message first');
      return;
    }
    setQuickPosting(true);
    try {
      const payload = {
        enabled: true,
        message: msg,
        link_url: source.link_url || '',
        link_label: source.link_label || '',
        speed: source.speed || 'medium',
        background_color: source.background_color || '#1C1917',
        text_color: source.text_color || '#F7EA1C',
        link_color: source.link_color || '#FFFFFF',
        icon: source.icon !== undefined ? source.icon : true,
        schedule_enabled: false,
        scheduled_start: null,
        scheduled_end: null,
        version: (cfg.version || 1) + 1,
        record_history: true,
      };
      const r = await axios.put(`${API_URL}/api/website-admin/announcement-ribbon`, payload, auth);
      setCfg({ ...DEFAULTS, ...(r.data || {}) });
      if (!overrides) setQuickMessage('');
      setPreviewKey((k) => k + 1);
      toast.success(overrides
        ? 'Re-published — live to all customers'
        : 'Live now — visible to all customers');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not publish');
    } finally {
      setQuickPosting(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-gray-500">Loading…</div>;
  }

  return (
    <div className="p-6 max-w-5xl mx-auto" data-testid="announcement-ribbon-admin">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 rounded-xl bg-amber-500 text-white flex items-center justify-center">
          <Megaphone className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Announcement Ribbon</h1>
          <p className="text-sm text-gray-500">Slow-scrolling banner above the storefront header.</p>
        </div>
      </div>

      {/* Quick Post — one-line composer for "publish right now" use-cases.
          Pre-fills medium speed / charcoal-yellow theme / no schedule / show=on
          and bumps version so previously-dismissed visitors see it again. */}
      <section
        className="mt-6 rounded-xl border-2 border-amber-300 bg-gradient-to-br from-amber-50 to-white p-4 sm:p-5"
        data-testid="ribbon-quick-post"
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-600" />
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wide">
              Quick post
            </h2>
            <span className="text-[11px] text-gray-500 font-normal">
              Publishes immediately with sensible defaults
            </span>
          </div>
          <div className="hidden sm:flex items-center gap-1 text-[10px] text-gray-500 uppercase tracking-wide">
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
            Show on · Medium speed · Charcoal/Yellow
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={quickMessage}
            onChange={(e) => setQuickMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                quickPost();
              }
            }}
            placeholder="Type a message and hit Enter — e.g. 'Stock alert: only 12 boxes of Carrara left'"
            maxLength={240}
            className="flex-1 px-4 py-3 rounded-lg border-2 border-gray-200 focus:border-amber-400 focus:outline-none text-sm bg-white"
            data-testid="ribbon-quick-message-input"
          />
          <Button
            onClick={() => quickPost()}
            disabled={quickPosting || !quickMessage.trim()}
            className="bg-amber-500 hover:bg-amber-600 text-white font-semibold sm:w-auto sm:px-6"
            data-testid="ribbon-quick-publish-btn"
          >
            {quickPosting ? (
              <><RefreshCw className="w-4 h-4 mr-2 animate-spin" /> Publishing…</>
            ) : (
              <><Zap className="w-4 h-4 mr-2" /> Publish now</>
            )}
          </Button>
        </div>

        <div className="flex flex-wrap gap-1.5 mt-3">
          {[
            'Free Saturday delivery this weekend only',
            'Stock alert — only a few boxes left of selected ranges',
            'Bank Holiday Sale — extra 10% off all porcelain',
            'Trade pricing now live — log in to see your discount',
            'New arrivals just landed — 30+ exclusive lines',
          ].map((preset) => (
            <button
              key={preset}
              type="button"
              onClick={() => setQuickMessage(preset)}
              className="text-[11px] text-gray-600 px-2 py-1 rounded-full bg-white border border-gray-200 hover:border-amber-400 hover:text-amber-700 transition"
              data-testid={`ribbon-quick-preset-${preset.slice(0, 20).replace(/\s+/g, '-').toLowerCase()}`}
            >
              {preset.length > 50 ? preset.slice(0, 50) + '…' : preset}
            </button>
          ))}
        </div>

        <p className="text-[11px] text-gray-500 mt-2 italic">
          Need to fine-tune the colour, schedule, or add a CTA link? Use the full editor below.
        </p>

        {/* History Log — last 10 Quick Posts. Click any row to instantly
            re-publish it with its original theme/CTA. */}
        {Array.isArray(cfg.history) && cfg.history.length > 0 && (
          <div
            className="mt-4 pt-4 border-t border-amber-200/70"
            data-testid="ribbon-quick-history"
          >
            <div className="flex items-center gap-2 mb-2">
              <History className="w-3.5 h-3.5 text-gray-500" />
              <h3 className="text-[11px] font-semibold text-gray-600 uppercase tracking-wide">
                Recent posts · last {cfg.history.length}
              </h3>
              <span className="text-[10px] text-gray-400 font-normal">click to re-publish</span>
            </div>
            <ul className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
              {cfg.history.map((h, idx) => (
                <li
                  key={h.id || `${h.published_at}-${idx}`}
                  className="group flex items-start gap-2 rounded-lg border border-gray-200 bg-white/80 hover:border-amber-400 hover:bg-white transition p-2"
                  data-testid={`ribbon-history-item-${idx}`}
                >
                  <span
                    className="shrink-0 mt-0.5 inline-block h-4 w-7 rounded text-[9px] font-bold text-center leading-[16px] shadow-sm"
                    style={{
                      background: h.background_color || '#1C1917',
                      color: h.text_color || '#F7EA1C',
                    }}
                    aria-hidden
                  >
                    ★
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] text-gray-800 truncate" title={h.message}>
                      {h.message}
                    </p>
                    <p className="text-[10.5px] text-gray-500 mt-0.5">
                      <span data-testid={`ribbon-history-time-${idx}`}>{timeAgo(h.published_at)}</span>
                      {h.published_by && (
                        <>
                          {' · by '}
                          <span className="font-medium text-gray-600">{h.published_by}</span>
                        </>
                      )}
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={quickPosting}
                    onClick={() => quickPost(h)}
                    className="shrink-0 h-7 px-2 text-[11px] border-amber-300 text-amber-700 hover:bg-amber-50 opacity-0 group-hover:opacity-100 focus:opacity-100 transition"
                    data-testid={`ribbon-history-republish-${idx}`}
                    title="Re-publish this announcement now"
                  >
                    <RotateCcw className="w-3 h-3 mr-1" />
                    Re-publish
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {/* Live preview — uses the actual <AnnouncementRibbon> component but we render
          it with the in-memory config by remounting on every save. */}
      <div className="mt-6 rounded-xl border-2 border-dashed border-gray-300 bg-white">
        <div className="px-3 py-2 text-xs uppercase tracking-wider text-gray-500 border-b border-gray-200 flex items-center gap-2">
          <Eye className="w-3.5 h-3.5" /> Live preview
        </div>
        {/* Inline preview that doesn't fetch — mirrors <AnnouncementRibbon> visuals */}
        <RibbonPreview key={previewKey} cfg={cfg} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        <section className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
          <h2 className="text-base font-semibold text-gray-900">Content</h2>

          <div className="flex items-center justify-between">
            <Label htmlFor="ribbon-enabled" className="cursor-pointer">
              Show now (manual override)
              <p className="text-xs text-gray-500 font-normal">Forces the ribbon visible immediately, bypassing schedule.</p>
            </Label>
            <Switch
              id="ribbon-enabled"
              checked={!!cfg.enabled}
              onCheckedChange={(v) => update({ enabled: v })}
              data-testid="ribbon-enabled-toggle"
            />
          </div>

          <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3 text-xs text-amber-900 flex items-start gap-2">
            {cfg._now_visible ? (
              <>
                <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0 text-emerald-600" />
                <span>
                  <span className="font-semibold">Visible right now</span>
                  {' '}({cfg._now_reason === 'manual' ? 'manual override' : 'inside scheduled window'})
                </span>
              </>
            ) : (
              <>
                <Calendar className="w-4 h-4 mt-0.5 shrink-0 text-gray-400" />
                <span>Hidden right now. Toggle "Show now" or set an active schedule below.</span>
              </>
            )}
          </div>

          <div>
            <Label>Message</Label>
            <Textarea
              value={cfg.message}
              onChange={(e) => update({ message: e.target.value })}
              rows={2}
              className="mt-1"
              placeholder="e.g. Bank Holiday Sale — extra 10% off all porcelain this weekend"
              data-testid="ribbon-message-input"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>CTA link URL (optional)</Label>
              <Input
                value={cfg.link_url}
                onChange={(e) => update({ link_url: e.target.value })}
                placeholder="/shop/clearance"
                className="mt-1 font-mono text-sm"
                data-testid="ribbon-link-url"
              />
            </div>
            <div>
              <Label>CTA link label</Label>
              <Input
                value={cfg.link_label}
                onChange={(e) => update({ link_label: e.target.value })}
                placeholder="Shop the sale"
                className="mt-1"
                data-testid="ribbon-link-label"
              />
            </div>
          </div>

          <div>
            <Label>Scroll speed</Label>
            <div className="flex gap-2 mt-1">
              {['slow', 'medium', 'fast'].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => update({ speed: s })}
                  className={`flex-1 py-2 px-3 rounded-lg border text-sm capitalize transition ${
                    cfg.speed === s
                      ? 'bg-gray-900 text-white border-gray-900'
                      : 'bg-white text-gray-700 border-gray-200 hover:border-gray-400'
                  }`}
                  data-testid={`ribbon-speed-${s}`}
                >
                  {s}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-1">Slow ≈ 18 s/50 chars · Medium ≈ 12 s · Fast ≈ 8 s. Pauses on hover.</p>
          </div>

          <div className="flex items-center justify-between">
            <Label htmlFor="ribbon-icon" className="cursor-pointer">
              Show star icon
              <p className="text-xs text-gray-500 font-normal">Adds a ★ before each repeat.</p>
            </Label>
            <Switch
              id="ribbon-icon"
              checked={!!cfg.icon}
              onCheckedChange={(v) => update({ icon: v })}
            />
          </div>
        </section>

        <section className="rounded-xl border border-gray-200 bg-white p-5 space-y-4" data-testid="ribbon-schedule-section">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <Calendar className="w-4 h-4 text-amber-500" />
              Schedule
            </h2>
            <Switch
              checked={!!cfg.schedule_enabled}
              onCheckedChange={(v) => update({ schedule_enabled: v })}
              data-testid="ribbon-schedule-enabled-toggle"
            />
          </div>
          <p className="text-xs text-gray-500 -mt-2">
            Set start &amp; end and the ribbon auto-shows / auto-hides for you. Times are saved in UTC; the inputs below show your browser's local timezone.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label className="text-sm">Starts (your local time)</Label>
              <Input
                type="datetime-local"
                value={isoToLocalInput(cfg.scheduled_start)}
                onChange={(e) => update({ scheduled_start: localInputToIso(e.target.value) })}
                disabled={!cfg.schedule_enabled}
                className="mt-1"
                data-testid="ribbon-schedule-start"
              />
              <p className="text-[11px] text-gray-400 mt-1 font-mono">{cfg.scheduled_start || 'not set'}</p>
            </div>
            <div>
              <Label className="text-sm">Ends (your local time)</Label>
              <Input
                type="datetime-local"
                value={isoToLocalInput(cfg.scheduled_end)}
                onChange={(e) => update({ scheduled_end: localInputToIso(e.target.value) })}
                disabled={!cfg.schedule_enabled}
                className="mt-1"
                data-testid="ribbon-schedule-end"
              />
              <p className="text-[11px] text-gray-400 mt-1 font-mono">{cfg.scheduled_end || 'not set'}</p>
            </div>
          </div>

          {/* Quick-pick presets — common UK retail windows */}
          <div>
            <Label className="text-xs text-gray-500">Quick presets</Label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-1">
              {[
                { label: 'This weekend', start: () => nextWeekend().start, end: () => nextWeekend().end },
                { label: 'Next 24 h', start: () => new Date(), end: () => addHours(24) },
                { label: 'Next 7 days', start: () => new Date(), end: () => addHours(24 * 7) },
                { label: 'Bank holiday Mon', start: () => bankHoliday().start, end: () => bankHoliday().end },
                { label: 'Black Friday weekend', start: () => blackFriday().start, end: () => blackFriday().end },
                { label: 'Clear', start: null, end: null },
              ].map((p) => (
                <button
                  key={p.label}
                  type="button"
                  disabled={!cfg.schedule_enabled && p.start !== null}
                  onClick={() => update({
                    scheduled_start: p.start ? p.start().toISOString() : null,
                    scheduled_end: p.end ? p.end().toISOString() : null,
                    ...(p.start && !cfg.schedule_enabled ? { schedule_enabled: true } : {}),
                  })}
                  className="px-2 py-1.5 text-xs rounded-md border border-gray-200 bg-white hover:border-amber-400 hover:bg-amber-50 disabled:opacity-40 disabled:cursor-not-allowed transition"
                  data-testid={`ribbon-preset-${p.label.toLowerCase().replace(/\s+/g, '-')}`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {cfg.schedule_enabled && cfg.scheduled_start && cfg.scheduled_end && (
            <div className="rounded-lg bg-gray-50 border border-gray-200 p-3 text-xs space-y-1" data-testid="ribbon-schedule-preview">
              <p className="font-semibold text-gray-700">Schedule summary</p>
              <p className="text-gray-600">From <span className="font-medium text-gray-900">{formatLocal(cfg.scheduled_start)}</span></p>
              <p className="text-gray-600">Until <span className="font-medium text-gray-900">{formatLocal(cfg.scheduled_end)}</span></p>
              <p className="text-gray-500 italic">{describeWindow(cfg.scheduled_start, cfg.scheduled_end)}</p>
            </div>
          )}
        </section>
      </div>

      <section className="rounded-xl border border-gray-200 bg-white p-5 space-y-4 mt-6">
        <h2 className="text-base font-semibold text-gray-900">Appearance</h2>

          <div>
            <Label className="text-sm">Preset themes</Label>
            <div className="grid grid-cols-2 gap-2 mt-1">
              {PRESET_THEMES.map((t) => (
                <button
                  key={t.name}
                  type="button"
                  onClick={() => update({ background_color: t.bg, text_color: t.fg, link_color: t.link })}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 hover:border-amber-400 hover:shadow-sm transition text-left"
                  data-testid={`ribbon-theme-${t.name.replace(/\s+/g, '-').toLowerCase()}`}
                >
                  <span
                    className="inline-block h-5 w-10 rounded shadow-sm"
                    style={{ background: t.bg, color: t.fg, fontSize: '10px', textAlign: 'center', lineHeight: '20px', fontWeight: 700 }}
                  >★</span>
                  <span className="text-xs text-gray-700">{t.name}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <ColorPicker label="Background" value={cfg.background_color} onChange={(v) => update({ background_color: v })} testid="ribbon-bg-color" />
            <ColorPicker label="Text" value={cfg.text_color} onChange={(v) => update({ text_color: v })} testid="ribbon-text-color" />
            <ColorPicker label="CTA link" value={cfg.link_color} onChange={(v) => update({ link_color: v })} testid="ribbon-link-color" />
          </div>

          <div className="text-xs text-gray-500 pt-2 border-t border-gray-100">
            Current version: <span className="font-mono">{cfg.version}</span> · Visitors who dismissed earlier versions will see this one.
          </div>
        </section>

      <div className="flex flex-col sm:flex-row gap-3 mt-6">
        <Button
          onClick={() => save(false)}
          disabled={saving}
          className="bg-gray-900 hover:bg-gray-800 text-white"
          data-testid="ribbon-save-btn"
        >
          {saving ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
          Save
        </Button>
        <Button
          onClick={() => save(true)}
          disabled={saving}
          variant="outline"
          className="border-amber-300 text-amber-700 hover:bg-amber-50"
          data-testid="ribbon-save-bump-btn"
        >
          Save & re-show to dismissed visitors
        </Button>
        <p className="text-xs text-gray-500 self-center">
          Bumping version forces visitors who dismissed the previous announcement to see this fresh one again.
        </p>
      </div>
    </div>
  );
}

function ColorPicker({ label, value, onChange, testid }) {
  return (
    <div>
      <Label className="text-xs">{label}</Label>
      <div className="flex items-center gap-2 mt-1">
        <input
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-9 h-9 rounded border border-gray-300 cursor-pointer"
          data-testid={testid}
        />
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1 font-mono text-xs uppercase"
        />
      </div>
    </div>
  );
}

/**
 * Inline preview that mirrors the live <AnnouncementRibbon> visuals but
 * sources its config from props instead of fetching. Lets admins see
 * changes live before saving.
 */
function RibbonPreview({ cfg }) {
  if (!cfg.enabled) {
    return (
      <div className="px-4 py-6 text-center text-xs text-gray-400">
        Ribbon disabled — toggle "Enabled" above to preview.
      </div>
    );
  }
  if (!(cfg.message || '').trim()) {
    return (
      <div className="px-4 py-6 text-center text-xs text-gray-400">
        Add a message to preview.
      </div>
    );
  }

  const speedMultipliers = { slow: 18, medium: 12, fast: 8 };
  const baseSecondsPer50 = speedMultipliers[cfg.speed] ?? 12;
  const duration = Math.max(20, Math.round((Math.max(40, cfg.message.length) / 50) * baseSecondsPer50));

  const segment = (
    <span className="inline-flex items-center gap-3 px-12">
      {cfg.icon !== false && <span aria-hidden>★</span>}
      <span>{cfg.message}</span>
      {cfg.link_url && cfg.link_label && (
        <span className="underline underline-offset-2 font-semibold" style={{ color: cfg.link_color }}>
          {cfg.link_label} →
        </span>
      )}
    </span>
  );

  return (
    <div
      className="relative overflow-hidden text-sm font-medium tracking-wide"
      style={{ background: cfg.background_color, color: cfg.text_color }}
    >
      <style>{`
        @keyframes ribbonPreviewScroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
        .ribbon-preview-track {
          display: inline-flex;
          white-space: nowrap;
          animation: ribbonPreviewScroll ${duration}s linear infinite;
        }
        .ribbon-preview-track:hover { animation-play-state: paused; }
      `}</style>
      <div className="py-2">
        <div className="ribbon-preview-track">{segment}{segment}{segment}{segment}</div>
      </div>
    </div>
  );
}
