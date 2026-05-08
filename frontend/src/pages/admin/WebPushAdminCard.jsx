/**
 * WebPushAdminCard
 * ────────────────
 * Admin tool to broadcast a push notification to every active
 * subscriber on tilestation.co.uk. Push is a 90% open-rate channel —
 * use sparingly so customers don't disable it.
 *
 * Lives on /admin/seo (or wherever marketing controls live).
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Bell, Send, Loader2, RefreshCw, Users, AlertTriangle } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const token = () => localStorage.getItem('token') || localStorage.getItem('access_token') || '';

const WebPushAdminCard = () => {
  const [stats, setStats] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [open, setOpen] = useState(false);

  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [url, setUrl] = useState('/');

  const load = useCallback(async () => {
    try {
      const [s, h] = await Promise.all([
        axios.get(`${API_URL}/api/admin/push/stats`, {
          headers: { Authorization: `Bearer ${token()}` },
        }),
        axios.get(`${API_URL}/api/admin/push/history?limit=10`, {
          headers: { Authorization: `Bearer ${token()}` },
        }),
      ]);
      setStats(s.data);
      setHistory(h.data.rows || []);
    } catch (e) {
      // Non-fatal — card just shows empty state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) load();
  }, [load, open]);

  const broadcast = async () => {
    if (!title.trim() || !body.trim()) {
      toast.error('Title and body are required');
      return;
    }
    if (!window.confirm(
      `Send push notification to all ${stats?.active_subscribers ?? 0} subscribers?\n\n` +
        `Title: ${title}\nBody: ${body}\n\nThis goes to every customer who's opted in. Use sparingly.`,
    )) return;
    setSending(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/push/broadcast`,
        { title, body, url: url || '/' },
        { headers: { Authorization: `Bearer ${token()}` } },
      );
      const d = r.data || {};
      toast.success(`Sent to ${d.sent} · ${d.failed || 0} failed · ${d.expired || 0} expired`);
      setTitle('');
      setBody('');
      setUrl('/');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Broadcast failed');
    } finally {
      setSending(false);
    }
  };

  if (!open) {
    return (
      <Card className="p-4 bg-pink-50/40 border-pink-200" data-testid="web-push-admin-collapsed">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2 min-w-0">
            <Bell className="w-5 h-5 text-pink-700" />
            <div className="min-w-0">
              <div className="font-bold text-pink-950">Web Push Notifications</div>
              <div className="text-xs text-pink-900/70">
                Push sale + restock alerts directly to customers' phone/desktop. 90% open-rate channel.
              </div>
            </div>
          </div>
          <Button
            size="sm"
            onClick={() => setOpen(true)}
            className="bg-pink-600 hover:bg-pink-700 text-white"
            data-testid="web-push-admin-open"
          >
            Open
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden border-pink-200" data-testid="web-push-admin-card">
      <div className="bg-gradient-to-br from-pink-700 to-rose-800 text-white px-6 py-4">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-pink-200 font-semibold">
              Web push notifications
            </div>
            <h3 className="text-xl font-bold mt-0.5 flex items-center gap-2">
              <Bell className="w-5 h-5" /> Customer alerts broadcast
            </h3>
          </div>
          <Button size="sm" variant="ghost" onClick={load} className="text-white hover:bg-white/10">
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {loading ? (
          <div className="flex items-center gap-2 text-slate-500">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading…
          </div>
        ) : (
          <>
            {/* Stats strip */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <Stat
                label="Active subscribers"
                value={stats?.active_subscribers ?? 0}
                icon={Users}
                tone="pink"
                testid="push-stat-active"
              />
              <Stat
                label="Lifetime subscribers"
                value={stats?.total_subscribers_lifetime ?? 0}
                icon={Users}
                tone="rose"
                testid="push-stat-total"
              />
              <Stat
                label="Status"
                value={stats?.configured ? 'Live' : 'Not configured'}
                icon={Bell}
                tone={stats?.configured ? 'emerald' : 'amber'}
                testid="push-stat-status"
              />
            </div>

            {!stats?.configured && (
              <div className="rounded-md border-2 border-amber-200 bg-amber-50 p-3 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
                <div className="text-sm text-amber-900">
                  Push not configured on the server. Set <code>VAPID_PUBLIC_KEY</code> and{' '}
                  <code>VAPID_PRIVATE_KEY</code> environment variables on Railway and redeploy.
                </div>
              </div>
            )}

            {/* Compose form */}
            {stats?.configured && (
              <div className="rounded-md border-2 border-pink-200 bg-pink-50/30 p-4 space-y-2">
                <div className="text-sm font-bold text-pink-950">Compose a broadcast</div>
                <Input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value.slice(0, 120))}
                  maxLength={120}
                  placeholder='Title — e.g. "25% off everything · Bank Holiday only"'
                  className="bg-white"
                  data-testid="push-broadcast-title"
                />
                <Input
                  type="text"
                  value={body}
                  onChange={(e) => setBody(e.target.value.slice(0, 240))}
                  maxLength={240}
                  placeholder="Body — short reason to click"
                  className="bg-white"
                  data-testid="push-broadcast-body"
                />
                <Input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="/sale or absolute URL — where the click should land"
                  className="bg-white text-xs font-mono"
                  data-testid="push-broadcast-url"
                />
                <div className="flex justify-between items-center pt-1">
                  <div className="text-[11px] text-slate-500">
                    Goes to <strong>{stats.active_subscribers}</strong> active devices · expired
                    subs are auto-pruned
                  </div>
                  <Button
                    onClick={broadcast}
                    disabled={sending || !title.trim() || !body.trim() || stats.active_subscribers === 0}
                    className="bg-pink-600 hover:bg-pink-700 text-white"
                    data-testid="push-broadcast-send"
                  >
                    {sending ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-1" />
                    ) : (
                      <Send className="w-4 h-4 mr-1" />
                    )}
                    Send broadcast
                  </Button>
                </div>
              </div>
            )}

            {/* History */}
            {history.length > 0 && (
              <div className="space-y-1">
                <div className="text-[11px] uppercase tracking-wide font-bold text-slate-600">
                  Recent broadcasts
                </div>
                <ul className="text-xs space-y-1" data-testid="push-history-list">
                  {history.map((h) => (
                    <li
                      key={h.id}
                      className="flex justify-between gap-2 px-2 py-1 rounded hover:bg-slate-50 border-l-2 border-pink-200"
                    >
                      <div className="min-w-0">
                        <div className="font-semibold truncate">{h.title}</div>
                        <div className="text-slate-500 truncate">{h.body}</div>
                      </div>
                      <div className="text-right shrink-0 text-[10px] text-slate-500 font-mono">
                        {new Date(h.sent_at).toLocaleDateString('en-GB')}
                        <div>
                          <span className="text-emerald-700 font-bold">{h.sent}</span>
                          {h.expired ? <> · {h.expired} exp</> : null}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </Card>
  );
};

const Stat = ({ label, value, icon: Icon, tone = 'pink', testid }) => {
  const tones = {
    pink: 'bg-pink-50 border-pink-200 text-pink-900',
    rose: 'bg-rose-50 border-rose-200 text-rose-900',
    emerald: 'bg-emerald-50 border-emerald-200 text-emerald-900',
    amber: 'bg-amber-50 border-amber-200 text-amber-900',
  };
  return (
    <div className={`rounded-md border-2 p-3 ${tones[tone]}`} data-testid={testid}>
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide font-semibold opacity-80">
        {Icon && <Icon className="w-3 h-3" />}
        {label}
      </div>
      <div className="text-2xl font-bold font-mono mt-0.5">{value}</div>
    </div>
  );
};

export default WebPushAdminCard;
