/**
 * LiveVisitors — Real-time admin page showing who's on the site right now.
 * Click any row → opens a detail modal with:
 *   - Location (UK map pin + flag),
 *   - Page-by-page history with time on each page,
 *   - Cart contents (live),
 *   - "Send message" composer to ping the visitor in real time.
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  Eye, Users, Activity, ArrowLeft, RefreshCw, Loader2, Globe, X,
  ShoppingCart, Send, Clock, Smartphone, ChevronDown, ChevronUp, Tag, MapPin,
} from 'lucide-react';
import axios from 'axios';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';
import UkMap from '../../components/admin/UkMap';
import TelegramNotifications from './TelegramNotifications';
import CustomerErrorsPanel from '../../components/admin/CustomerErrorsPanel';
import VisitorHistoryPanel from '../../components/admin/VisitorHistoryPanel';
import TopPagesPanel from '../../components/admin/TopPagesPanel';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const POLL_INTERVAL_MS = 5_000;
const DETAIL_POLL_INTERVAL_MS = 5_000;

function timeAgo(iso) {
  if (!iso) return '—';
  try {
    const diff = Math.max(0, Date.now() - new Date(iso).getTime());
    const s = Math.floor(diff / 1000);
    if (s < 5) return 'just now';
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    return `${Math.floor(m / 60)}h ago`;
  } catch { return '—'; }
}

function formatDuration(secs) {
  const s = Math.max(0, Number(secs || 0));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m < 60) return r > 0 ? `${m}m ${r}s` : `${m}m`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

/**
 * Tiny SVG sparkline for the "Hot sessions" header chip.
 * `values` is oldest→newest (length 7). Renders 56×16 with an orange polyline
 * + filled area, plus a dot on the most recent point. Pure CSS-coloured SVG,
 * no library, no extra HTTP.
 */
function HotSparkline({ values }) {
  if (!Array.isArray(values) || values.length === 0) return null;
  const w = 56;
  const h = 16;
  const max = Math.max(1, ...values);
  const stepX = values.length > 1 ? w / (values.length - 1) : w;
  const points = values.map((v, i) => {
    const x = i * stepX;
    const y = h - 1 - (v / max) * (h - 2);
    return [x, y];
  });
  const polyline = points.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const area = `0,${h} ${polyline} ${w},${h}`;
  const last = points[points.length - 1];
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      className="ml-1 shrink-0"
      aria-hidden="true"
      data-testid="hot-sessions-sparkline"
    >
      <polygon points={area} fill="rgba(251, 146, 60, 0.18)" />
      <polyline
        points={polyline}
        fill="none"
        stroke="rgb(234, 88, 12)"
        strokeWidth="1.2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={last[0]} cy={last[1]} r="1.6" fill="rgb(234, 88, 12)" />
    </svg>
  );
}

function deviceFromUA(ua = '') {
  const s = ua.toLowerCase();
  if (/iphone|android.*mobile|mobile/.test(s)) return 'Mobile';
  if (/ipad|tablet/.test(s)) return 'Tablet';
  return 'Desktop';
}
function browserFromUA(ua = '') {
  if (/Edg\//.test(ua)) return 'Edge';
  if (/Chrome\//.test(ua) && !/Chromium/.test(ua)) return 'Chrome';
  if (/Firefox\//.test(ua)) return 'Firefox';
  if (/Safari\//.test(ua)) return 'Safari';
  return 'Other';
}

/* ------------------ Visitor detail modal ------------------ */

function VisitorDetailModal({ sessionId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const tokenRef = useRef(localStorage.getItem('token'));

  const fetchDetail = useCallback(async () => {
    try {
      const res = await axios.get(`${API_URL}/api/live-analytics/visitors/${sessionId}`, {
        headers: { Authorization: `Bearer ${tokenRef.current}` },
      });
      setData(res.data);
    } catch (err) {
      const code = err?.response?.status;
      if (code === 404) {
        toast.message('Visitor session expired (gone)', { description: 'They left or stopped pinging.' });
        onClose();
      } else {
        toast.error(err?.response?.data?.detail || 'Failed to load visitor detail');
      }
    } finally {
      setLoading(false);
    }
  }, [sessionId, onClose]);

  useEffect(() => {
    fetchDetail();
    const id = setInterval(fetchDetail, DETAIL_POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchDetail]);

  const handleSend = async () => {
    const m = message.trim();
    if (!m) return;
    setSending(true);
    try {
      await axios.post(`${API_URL}/api/live-analytics/admin-message`, {
        session_id: sessionId, message: m,
      }, { headers: { Authorization: `Bearer ${tokenRef.current}` } });
      setMessage('');
      toast.success('Message queued — will appear on visitor\'s screen within 30s');
      fetchDetail();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to send');
    } finally {
      setSending(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto"
      onClick={onClose}
      data-testid="visitor-detail-modal"
    >
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-5xl my-8 max-h-[92vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h2 className="text-lg font-bold text-gray-900">Visitor session</h2>
            <p className="text-xs text-gray-500 font-mono mt-0.5">{sessionId}</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-md hover:bg-gray-100" aria-label="Close" data-testid="visitor-modal-close">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {loading && !data ? (
            <div className="flex items-center justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>
          ) : data && (
            <>
              {/* Top row: location | metadata */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div data-testid="visitor-location-block">
                  <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
                    <Globe className="w-4 h-4 text-gray-400" /> Location
                  </h3>
                  <UkMap
                    pin={data.geo_precise?.lat && data.geo_precise?.lon ? {
                      lat: data.geo_precise.lat,
                      lon: data.geo_precise.lon,
                      label: [data.geo_precise.town, data.geo_precise.postcode].filter(Boolean).join(' · '),
                      flag_emoji: '📍',
                    } : (data.geo?.lat && data.geo?.lon ? {
                      lat: data.geo.lat,
                      lon: data.geo.lon,
                      label: [data.geo.city, data.geo.country_code].filter(Boolean).join(', '),
                      flag_emoji: data.geo.flag_emoji,
                    } : null)}
                  />
                  {data.geo_precise ? (
                    <>
                      <p className="text-xs mt-2 flex items-center gap-1.5">
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200" data-testid="precise-location-badge">
                          📍 Precise
                        </span>
                        <strong className="text-gray-900">{data.geo_precise.town}</strong>
                        {data.geo_precise.postcode && (
                          <span className="text-gray-600">· {data.geo_precise.postcode}</span>
                        )}
                      </p>
                      <p className="text-[11px] text-gray-400 mt-1 leading-snug">
                        {data.geo_precise.source === 'browser'
                          ? `Visitor opted in to share their browser location${data.geo_precise.accuracy_m ? ` (±${Math.round(data.geo_precise.accuracy_m)}m)` : ''}.`
                          : `Pulled from a postcode field the visitor typed into a form.`}
                        {data.geo && data.geo.city && (
                          <> Coarse IP location: <span className="text-gray-500">{data.geo.city}</span>.</>
                        )}
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="text-xs text-gray-600 mt-2">
                        {data.geo ? (
                          <>
                            <span className="text-base mr-1">{data.geo.flag_emoji}</span>
                            <strong>{data.geo.city || data.geo.region || '—'}</strong>{data.geo.country ? `, ${data.geo.country}` : ''}
                          </>
                        ) : (
                          <span className="text-gray-400 italic">Resolving location… (next heartbeat will populate)</span>
                        )}
                      </p>
                      <p className="text-[11px] text-gray-400 mt-1 leading-snug">
                        Approximate — based on the visitor's ISP routing, not their actual address. UK mobile carriers and broadband providers typically register their network's central server location (often London or Slough), so this can be off by 100+ miles.
                      </p>
                    </>
                  )}
                </div>

                <div className="space-y-3">
                  <div className="border border-gray-200 rounded-xl p-4">
                    <h3 className="text-sm font-semibold text-gray-900 mb-2">Session timing</h3>
                    <div className="text-sm space-y-1.5 text-gray-700">
                      <div>First seen: <strong>{timeAgo(data.first_seen)}</strong></div>
                      <div>Last seen: <strong>{timeAgo(data.last_seen)}</strong></div>
                      <div>Total time on site: <strong className="tabular-nums">{formatDuration(data.total_seconds)}</strong></div>
                      <div>Pages viewed: <strong>{(data.page_history || []).length}</strong></div>
                    </div>
                  </div>
                  {data.nearest_showroom && (
                    <div
                      className="border border-emerald-200 bg-emerald-50/40 rounded-xl p-4"
                      data-testid="nearest-showroom-block"
                    >
                      <h3 className="text-sm font-semibold text-emerald-900 mb-2 flex items-center gap-2">
                        <MapPin className="w-4 h-4 text-emerald-600" /> Nearest showroom
                      </h3>
                      <div className="text-sm space-y-1 text-gray-800">
                        <div className="flex items-baseline gap-2">
                          <strong className="text-emerald-700 tabular-nums text-base">
                            {data.nearest_showroom.distance_miles} mi
                          </strong>
                          <span className="text-gray-700">from <strong>{data.nearest_showroom.name}</strong></span>
                        </div>
                        {data.nearest_showroom.postcode && (
                          <div className="text-xs text-gray-500">{data.nearest_showroom.postcode}{data.nearest_showroom.phone ? ` · ${data.nearest_showroom.phone}` : ''}</div>
                        )}
                        {data.nearest_showroom.coord_source === 'approx' && (
                          <div className="text-[10px] text-amber-700 italic">Distance based on coarse IP location — could be wildly off until visitor opts in to GPS or types a postcode.</div>
                        )}
                      </div>
                    </div>
                  )}
                  <div className="border border-gray-200 rounded-xl p-4">
                    <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
                      <Smartphone className="w-4 h-4 text-gray-400" /> Device
                    </h3>
                    <div className="text-sm space-y-1.5 text-gray-700">
                      <div>{deviceFromUA(data.user_agent)} · {browserFromUA(data.user_agent)}</div>
                      {data.referrer && (<div className="text-xs text-gray-500 truncate">From: {data.referrer}</div>)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Cart */}
              <div className="border border-gray-200 rounded-xl overflow-hidden" data-testid="visitor-cart-block">
                <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
                  <ShoppingCart className="w-4 h-4 text-gray-400" />
                  <h3 className="text-sm font-semibold text-gray-900">Basket</h3>
                  {data.cart_summary && (
                    <span className="ml-auto text-xs text-gray-500 tabular-nums">
                      {data.cart_summary.items_count} item(s) · £{Number(data.cart_summary.value || 0).toFixed(2)}
                    </span>
                  )}
                </div>
                {data.cart_summary && data.cart_summary.top_items?.length > 0 ? (
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-xs text-gray-500 border-b border-gray-100">
                      <tr><th className="text-left px-4 py-1.5 font-medium">Item</th><th className="text-right px-4 py-1.5 font-medium">Qty</th><th className="text-right px-4 py-1.5 font-medium">Price</th></tr>
                    </thead>
                    <tbody>
                      {data.cart_summary.top_items.map((it, i) => (
                        <tr key={i} className="border-b last:border-b-0 border-gray-50">
                          <td className="px-4 py-2 text-gray-900">{it.name || '—'}</td>
                          <td className="px-4 py-2 text-right tabular-nums text-gray-700">{Number(it.qty).toFixed(2)}</td>
                          <td className="px-4 py-2 text-right tabular-nums text-gray-700">£{Number(it.price).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="px-4 py-4 text-sm text-gray-400 italic">Basket is empty</p>
                )}
              </div>

              {/* Page-by-page history */}
              <div className="border border-gray-200 rounded-xl overflow-hidden" data-testid="visitor-history-block">
                <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-gray-400" />
                  <h3 className="text-sm font-semibold text-gray-900">Page history</h3>
                  <span className="ml-auto text-xs text-gray-500">newest first</span>
                </div>
                {(data.page_history || []).length === 0 ? (
                  <p className="px-4 py-4 text-sm text-gray-400">No history yet.</p>
                ) : (
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-xs text-gray-500 border-b border-gray-100">
                      <tr>
                        <th className="text-left px-4 py-1.5 font-medium">Page</th>
                        <th className="text-left px-4 py-1.5 font-medium">Entered</th>
                        <th className="text-right px-4 py-1.5 font-medium">Time on page</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.page_history.map((p, i) => (
                        <tr key={i} className="border-b last:border-b-0 border-gray-50 hover:bg-gray-50">
                          <td className="px-4 py-2 text-gray-900 max-w-[420px] truncate" title={p.path}>{p.path}</td>
                          <td className="px-4 py-2 text-gray-500 text-xs">{timeAgo(p.entered_at)}</td>
                          <td className="px-4 py-2 text-right tabular-nums text-gray-700">{formatDuration(p.seconds_on_page)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Live message composer */}
              <div className="border border-emerald-200 bg-emerald-50/40 rounded-xl p-4" data-testid="visitor-message-composer">
                <h3 className="text-sm font-semibold text-emerald-900 mb-2 flex items-center gap-2">
                  <Send className="w-4 h-4" /> Send a live message
                </h3>
                <p className="text-[12px] text-emerald-900/80 mb-3">
                  Visitor sees a soft pop-up with this message within 30 seconds. Use this like a friendly sales assistant — offer help, share a discount, or answer a question.
                </p>
                {/* Message history */}
                {(data.messages || []).length > 0 && (
                  <div className="mb-3 max-h-40 overflow-y-auto space-y-2">
                    {data.messages.map(m => (
                      <div key={m.id} className="bg-white border border-emerald-100 rounded-lg px-3 py-2 text-[12px]">
                        <div className="text-gray-700">{m.message}</div>
                        <div className="text-[10px] text-gray-400 mt-1 flex items-center gap-2">
                          <span>{timeAgo(m.created_at)}</span>
                          <span>·</span>
                          <span className={m.delivered ? 'text-emerald-600' : 'text-amber-600'}>
                            {m.delivered ? '✓ delivered' : 'queued'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex items-end gap-2">
                  <Input
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Hi! Can I help you find what you're looking for?"
                    onKeyDown={(e) => { if (e.key === 'Enter' && !sending) handleSend(); }}
                    maxLength={500}
                    data-testid="visitor-message-input"
                  />
                  <Button onClick={handleSend} disabled={sending || !message.trim()} className="bg-emerald-600 hover:bg-emerald-700" data-testid="visitor-message-send">
                    {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Send className="w-4 h-4 mr-1.5" /> Send</>}
                  </Button>
                </div>
                <div className="text-[10px] text-emerald-900/60 mt-2">{message.length} / 500</div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------ List page ------------------ */

/* ------------------ Tag device modal ------------------ */

function TagDeviceModal({ initial, onClose, onSaved }) {
  const [label, setLabel] = useState(initial.label || '');
  const [excludeFromStats, setExcludeFromStats] = useState(
    initial.exclude_from_stats === undefined ? true : initial.exclude_from_stats
  );
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const isExisting = !!initial.label;

  const save = async () => {
    if (!label.trim()) {
      toast.error('Give it a name first (e.g. "Tonbridge iPad")');
      return;
    }
    setSaving(true);
    try {
      await axios.put(
        `${API_URL}/api/live-analytics/known-devices/${initial.visitor_id}`,
        { visitor_id: initial.visitor_id, label: label.trim(), exclude_from_stats: excludeFromStats },
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );
      toast.success(`Tagged as "${label.trim()}"`);
      onSaved();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to tag device');
    } finally { setSaving(false); }
  };

  const remove = async () => {
    if (!window.confirm('Remove this tag? The device will reappear in stats.')) return;
    setRemoving(true);
    try {
      await axios.delete(
        `${API_URL}/api/live-analytics/known-devices/${initial.visitor_id}`,
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );
      toast.success('Tag removed');
      onSaved();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to remove tag');
    } finally { setRemoving(false); }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      onClick={onClose}
      data-testid="tag-device-modal"
    >
      <div
        className="bg-white rounded-xl shadow-2xl max-w-md w-full overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Tag className="w-4 h-4 text-purple-600" />
            <h3 className="text-sm font-semibold text-gray-900">
              {isExisting ? 'Edit device tag' : 'Tag this device'}
            </h3>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Device name</label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Tonbridge iPad, Qasim's laptop, Showroom desktop"
              maxLength={80}
              autoFocus
              className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              data-testid="tag-device-label"
            />
            <p className="text-[10px] text-gray-500 mt-1">
              Same device, same browser → matches every visit forever (uses IP + user-agent fingerprint).
            </p>
          </div>

          <label className="flex items-start gap-3 cursor-pointer p-3 bg-amber-50 border border-amber-200 rounded-md">
            <input
              type="checkbox"
              checked={excludeFromStats}
              onChange={(e) => setExcludeFromStats(e.target.checked)}
              className="mt-0.5 w-4 h-4 rounded text-amber-600 focus:ring-amber-500"
              data-testid="tag-device-exclude"
            />
            <div className="flex-1">
              <p className="text-sm font-semibold text-amber-900">Skip Telegram notifications for this device</p>
              <p className="text-xs text-amber-800 mt-0.5">
                You'll still see this device in the live visitors list (so you can observe site behavior while testing) — but Telegram won't ping you when this device adds to basket, lands on the site, or hits an error.
              </p>
            </div>
          </label>

          <div className="flex items-center justify-between gap-2 pt-2">
            {isExisting ? (
              <button
                type="button"
                onClick={remove}
                disabled={removing}
                className="text-xs font-medium text-rose-600 hover:text-rose-800 hover:underline"
                data-testid="tag-device-remove"
              >
                {removing ? 'Removing…' : 'Remove tag'}
              </button>
            ) : <span />}
            <div className="flex gap-2">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={save}
                disabled={saving || !label.trim()}
                className="px-4 py-2 text-sm font-medium text-white bg-purple-600 rounded-md hover:bg-purple-700 disabled:opacity-50"
                data-testid="tag-device-save"
              >
                {saving ? 'Saving…' : isExisting ? 'Update' : 'Save tag'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


export default function LiveVisitors() {
  const [data, setData] = useState({ total: 0, by_page: [], visitors: [] });
  const [loading, setLoading] = useState(true);
  const [paused, setPaused] = useState(false);
  const [, setTick] = useState(0);
  const [activeSession, setActiveSession] = useState(null);
  const [telegramEnabled, setTelegramEnabled] = useState(null); // null = unknown
  const [telegramOpen, setTelegramOpen] = useState(false);
  const [tagDevice, setTagDevice] = useState(null); // { visitor_id, label, exclude_from_stats }
  const tokenRef = useRef(localStorage.getItem('token'));

  const fetchData = useCallback(async () => {
    try {
      const res = await axios.get(`${API_URL}/api/live-analytics/visitors`, {
        headers: { Authorization: `Bearer ${tokenRef.current}` },
      });
      setData(res.data || { total: 0, by_page: [], visitors: [] });
    } catch (err) {
      if (!loading) toast.error(err?.response?.data?.detail || 'Failed to load live visitors');
    } finally {
      setLoading(false);
    }
  }, [loading]);

  // Pull Telegram config so we can show enabled/disabled state on the CTA.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API_URL}/api/notifications/telegram/config`, {
          headers: { Authorization: `Bearer ${tokenRef.current}` },
        });
        if (cancelled) return;
        const visitorOn = !!(r.data?.enabled && r.data?.events?.visitor_landed && r.data?.bot_token);
        setTelegramEnabled(visitorOn);
      } catch {
        // 403 (non-super-admin) or any error — just hide the badge
        if (!cancelled) setTelegramEnabled(null);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    fetchData();
    if (paused) return undefined;
    const id = setInterval(fetchData, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchData, paused]);

  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 5000);
    return () => clearInterval(id);
  }, []);

  const total = data.total || 0;

  return (
    <div className="min-h-screen bg-gray-50" data-testid="live-visitors-page">
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <div className="flex items-center gap-3">
            <Link to="/admin" className="text-gray-500 hover:text-gray-900 transition-colors" aria-label="Back to admin">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                <Activity className="w-6 h-6 text-emerald-500" /> Live Visitors
              </h1>
              <p className="text-sm text-gray-500 mt-0.5">Real-time pulse — refreshes every {POLL_INTERVAL_MS / 1000}s</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {data.precise_coverage && data.precise_coverage.total > 0 && (
              <span
                className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1.5 rounded-md bg-sky-50 text-sky-800 border border-sky-200"
                title={`${data.precise_coverage.precise} of ${data.precise_coverage.total} unique visitors in the last 7 days have a precise location (browser GPS, form postcode, persisted from a previous visit, or pulled from a logged-in account).`}
                data-testid="precise-coverage-chip"
              >
                <span className="text-sm leading-none">📍</span>
                {data.precise_coverage.precise}/{data.precise_coverage.total} ({data.precise_coverage.pct}%) precise
              </span>
            )}
            {((data.hot_today_count > 0) || (data.hot_sparkline_7d || []).some(n => n > 0)) && (
              <span
                className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1.5 rounded-md bg-orange-50 text-orange-700 border border-orange-200"
                title={`${data.hot_today_count || 0} hot session(s) today · last 7 days: ${(data.hot_sparkline_7d || []).join(', ')}`}
                data-testid="hot-sessions-today-chip"
              >
                <span className="text-sm leading-none">🔥</span>
                Hot today: {data.hot_today_count || 0}
                <HotSparkline values={data.hot_sparkline_7d || []} />
              </span>
            )}
            <button
              type="button"
              onClick={() => setTelegramOpen(o => !o)}
              data-testid="live-visitors-telegram-cta"
              className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-md border transition-colors ${
                telegramEnabled === true
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                  : telegramEnabled === false
                  ? 'bg-amber-50 text-amber-800 border-amber-200 hover:bg-amber-100'
                  : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'
              }`}
              title={
                telegramOpen
                  ? 'Hide Telegram settings'
                  : telegramEnabled === true
                  ? 'Telegram alerts ON for new visitors — click to manage'
                  : telegramEnabled === false
                  ? 'Telegram alerts OFF for new visitors — click to enable'
                  : 'Open Telegram alerts settings'
              }
            >
              <Smartphone className="w-3.5 h-3.5" />
              Telegram Alerts
              {telegramEnabled === true && (
                <span className="ml-1 inline-flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  ON
                </span>
              )}
              {telegramEnabled === false && (
                <span className="ml-1 inline-flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                  OFF
                </span>
              )}
              {telegramOpen
                ? <ChevronUp className="w-3.5 h-3.5 ml-0.5" />
                : <ChevronDown className="w-3.5 h-3.5 ml-0.5" />}
            </button>
            <Button onClick={() => setPaused(p => !p)} variant="outline" size="sm" data-testid="toggle-poll-btn">
              {paused ? 'Resume' : 'Pause'}
            </Button>
            <Button onClick={fetchData} variant="outline" size="sm" data-testid="refresh-btn">
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </Button>
          </div>
        </div>

        {/* Hero counter */}
        <div className="bg-gradient-to-br from-emerald-500 to-emerald-700 rounded-2xl p-8 mb-6 text-white shadow-lg shadow-emerald-500/20" data-testid="visitors-hero">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 text-emerald-100 text-sm font-medium mb-1">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="absolute inset-0 rounded-full bg-white opacity-75 animate-ping" />
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-white" />
                </span>
                LIVE
              </div>
              <div className="text-6xl font-bold tabular-nums leading-none" data-testid="visitor-total-count">
                {loading ? <Loader2 className="w-12 h-12 animate-spin" /> : total}
              </div>
              <div className="text-emerald-100 mt-2 text-base">
                {total === 1 ? 'visitor on the site right now' : 'visitors on the site right now'}
              </div>
            </div>
            <Users className="w-24 h-24 text-emerald-300/40" />
          </div>
          {total > 0 && (
            <button
              type="button"
              onClick={() => {
                document.querySelector('[data-testid="visitors-list"]')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }}
              className="mt-4 inline-flex items-center gap-2 text-xs font-semibold text-emerald-100 hover:text-white bg-white/10 hover:bg-white/20 backdrop-blur px-3 py-1.5 rounded-md transition-colors"
              data-testid="hero-show-visitors"
            >
              👇 See what they're browsing
            </button>
          )}
        </div>

        {/* Inline Telegram Alerts manager — opens from the header pill */}
        {telegramOpen && (
          <div
            className="mb-6 bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden"
            data-testid="live-visitors-telegram-panel"
          >
            <TelegramNotifications onConfigChange={(cfg) => {
              setTelegramEnabled(!!(cfg?.enabled && cfg?.events?.visitor_landed && cfg?.bot_token));
            }} />
          </div>
        )}

        {/* LIVE: Active by page + Recent activity (clickable rows) — moved up */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          {/* Per-page breakdown */}
          <div className="lg:col-span-1 bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-200 bg-gray-50 flex items-center gap-2">
              <Globe className="w-4 h-4 text-gray-500" />
              <h3 className="text-sm font-semibold text-gray-900">Active by page</h3>
            </div>
            <div className="divide-y divide-gray-100" data-testid="by-page-list">
              {data.by_page.length === 0 ? (
                <p className="px-5 py-8 text-center text-sm text-gray-400">No active pages</p>
              ) : (
                data.by_page.map((row) => {
                  const pct = total > 0 ? Math.round((row.count / total) * 100) : 0;
                  return (
                    <div key={row.path} className="px-5 py-3" data-testid={`page-row-${row.path}`}>
                      <div className="flex items-baseline justify-between gap-2 mb-1.5">
                        <span className="text-xs font-medium text-gray-700 truncate" title={row.path}>{row.path}</span>
                        <span className="text-sm font-bold text-gray-900 tabular-nums">{row.count}</span>
                      </div>
                      <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-emerald-400 to-emerald-600 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Recent activity (clickable rows) */}
          <div className="lg:col-span-2 bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-200 bg-gray-50 flex items-center gap-2">
              <Eye className="w-4 h-4 text-gray-500" />
              <h3 className="text-sm font-semibold text-gray-900">Live visitors — click any row to see what they're browsing</h3>
              {(() => {
                const visible = data.visitors.length;
                const totalCount = data.total || 0;
                // The visitor list is capped at 50 server-side, so a higher
                // total IS expected when traffic is heavy. Anything else is a
                // data-integrity warning (today's orphan bug, e.g.).
                const expectedDiscrepancy = totalCount > 50 && visible === 50;
                const healthy = visible === totalCount || expectedDiscrepancy;
                const tooltip = healthy
                  ? expectedDiscrepancy
                    ? `Healthy — ${totalCount} live visitors, list capped at 50.`
                    : 'Healthy — count matches list exactly.'
                  : `Mismatch: headline says ${totalCount} but list has ${visible}. May indicate orphan or stale docs.`;
                return (
                  <span
                    className={`inline-flex items-center gap-1.5 text-[10px] font-semibold ml-auto px-2 py-0.5 rounded-full border ${
                      healthy
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-amber-50 text-amber-700 border-amber-200'
                    }`}
                    title={tooltip}
                    data-testid="live-visitors-health-dot"
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${healthy ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'}`} />
                    {visible} visible{!healthy && ` / ${totalCount} counted`}
                  </span>
                );
              })()}
            </div>
            {data.visitors.length === 0 ? (
              <p className="px-5 py-12 text-center text-sm text-gray-400">No live visitors right now. Open your shop in another tab to test.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-500 border-b border-gray-100">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium">Location</th>
                    <th className="text-left px-4 py-2 font-medium">Currently on</th>
                    <th className="text-right px-4 py-2 font-medium">Cart</th>
                    <th className="text-right px-4 py-2 font-medium">Pages</th>
                    <th className="text-left px-4 py-2 font-medium">Last seen</th>
                    <th className="text-right px-4 py-2 font-medium">Tag</th>
                  </tr>
                </thead>
                <tbody data-testid="visitors-list">
                  {data.visitors.map((v) => (
                    <tr
                      key={v.session_id}
                      className="border-b last:border-b-0 border-gray-50 hover:bg-emerald-50/40 cursor-pointer transition-colors"
                      onClick={() => setActiveSession(v.session_id)}
                      data-testid={`visitor-row-${v.session_id}`}
                    >
                      <td className="px-4 py-2.5 text-gray-700 max-w-[180px]">
                        {v.geo_precise ? (
                          <div className="text-xs">
                            <span className="inline-flex items-center text-[9px] font-bold uppercase px-1 py-0 rounded bg-emerald-100 text-emerald-800 border border-emerald-200 mr-1" title="Precise location from browser GPS or form postcode">📍</span>
                            <span className="font-medium text-gray-900">{v.geo_precise.town || v.geo_precise.postcode}</span>
                            {v.geo_precise.postcode && v.geo_precise.town && (
                              <span className="text-gray-500"> · {v.geo_precise.postcode}</span>
                            )}
                          </div>
                        ) : v.geo ? (
                          <div className="text-xs">
                            <span className="text-base mr-1.5">{v.geo.flag_emoji}</span>
                            <span className="font-medium text-gray-900">{v.geo.city || v.geo.country || '—'}</span>
                            {v.geo.country && v.geo.city && <span className="text-gray-500"> · {v.geo.country_code}</span>}
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400 italic">Resolving…</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 max-w-[260px]">
                        <div className="font-medium text-gray-900 truncate flex items-center gap-1.5" title={v.path}>
                          {v.is_hot && (
                            <span
                              className="inline-flex items-center text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 border border-orange-200 shrink-0"
                              title="Hot session — 3+ products viewed and 2+ min on site. Telegram alert already fired."
                              data-testid={`hot-session-badge-${v.session_id}`}
                            >
                              🔥 Hot
                            </span>
                          )}
                          <span className="truncate">{v.path || '/'}</span>
                        </div>
                        <div className="text-[11px] text-gray-400">{deviceFromUA(v.user_agent)} · {browserFromUA(v.user_agent)}</div>
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums">
                        {v.cart_count > 0 ? (
                          <span className="text-emerald-700 font-semibold">{v.cart_count} · £{Number(v.cart_value || 0).toFixed(0)}</span>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-gray-700">{v.page_count || 0}</td>
                      <td className="px-4 py-2.5 text-gray-500 text-xs">{timeAgo(v.last_seen)}</td>
                      <td className="px-4 py-2.5 text-right">
                        {v.known_device_label ? (
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); setTagDevice({ visitor_id: v.visitor_id, label: v.known_device_label, exclude_from_stats: v.known_device_excluded }); }}
                            className="inline-flex items-center gap-1 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-purple-100 text-purple-800 border border-purple-200 hover:bg-purple-200"
                            title={v.known_device_excluded ? 'Tagged · excluded from stats' : 'Tagged · counted in stats'}
                            data-testid={`device-tag-${v.session_id}`}
                          >
                            <Tag className="w-3 h-3" />
                            {v.known_device_label}
                          </button>
                        ) : v.visitor_id ? (
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); setTagDevice({ visitor_id: v.visitor_id, label: '', exclude_from_stats: true }); }}
                            className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-50 text-gray-500 border border-gray-200 hover:bg-gray-100 hover:text-gray-700"
                            title="Tag this device — e.g. 'Tonbridge iPad' — and optionally exclude from stats"
                            data-testid={`device-tag-${v.session_id}`}
                          >
                            <Tag className="w-3 h-3" />
                            Tag
                          </button>
                        ) : (
                          <span className="text-gray-300 text-xs">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Customer issues feed — last 24h of red toasts / API 5xx / JS crashes */}
        <div className="mb-6">
          <CustomerErrorsPanel />
        </div>

        {/* Visitor history with per-page dwell time */}
        <div className="mb-6">
          <VisitorHistoryPanel />
        </div>

        {/* Top visited pages leaderboard */}
        <div className="mb-6">
          <TopPagesPanel />
        </div>

        {/* Footer note */}
        <p className="text-xs text-gray-400 mt-4">
          Heartbeat every 30s. Active = pinged within last 90s. Admin pages don't count. Geo-location resolved via IP (cached 24h). Messages reach the visitor within 30s.
        </p>

        {activeSession && (
          <VisitorDetailModal sessionId={activeSession} onClose={() => setActiveSession(null)} />
        )}

        {tagDevice && (
          <TagDeviceModal
            initial={tagDevice}
            onClose={() => setTagDevice(null)}
            onSaved={() => { setTagDevice(null); fetchData(); }}
          />
        )}
      </div>
    </div>
  );
}
