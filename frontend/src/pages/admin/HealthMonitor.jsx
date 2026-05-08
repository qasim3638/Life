/**
 * Health Monitor admin page — /admin/health
 *
 * Three sections:
 *   1. Status grid — every monitored endpoint, healthy / unhealthy
 *      indicator, last response time, last failure reason.
 *   2. Active alerts — unacknowledged outages, ack one or all.
 *   3. Settings — email recipients, Telegram bot token & chat id,
 *      "Send test alert" button.
 *   4. Recent incidents — past 30 days, sortable.
 */
import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import {
  Activity, AlertTriangle, CheckCircle2, RefreshCw, Loader2,
  Mail, MessageSquare, Send, Bell, Clock, ShieldAlert,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const tokenHdr = () => {
  const t = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
  return t ? { Authorization: `Bearer ${t}` } : {};
};

const fmtTime = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return `${Math.round(diff)}s ago`;
    if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
    return d.toLocaleString();
  } catch (_e) { return iso; }
};

const HealthMonitor = () => {
  const [status, setStatus] = useState(null);
  const [active, setActive] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [settings, setSettings] = useState(null);
  const [emailDraft, setEmailDraft] = useState('');
  const [tgToken, setTgToken] = useState('');
  const [tgChat, setTgChat] = useState('');
  const [savingSettings, setSavingSettings] = useState(false);
  const [testingAlert, setTestingAlert] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [s, a, i, cfg] = await Promise.all([
        axios.get(`${API}/api/admin/health/status`, { headers: tokenHdr() }),
        axios.get(`${API}/api/admin/health/active`, { headers: tokenHdr() }),
        axios.get(`${API}/api/admin/health/incidents?days=30`, { headers: tokenHdr() }),
        axios.get(`${API}/api/admin/health/settings`, { headers: tokenHdr() }),
      ]);
      setStatus(s.data);
      setActive(a.data?.alerts || []);
      setIncidents(i.data?.incidents || []);
      setSettings(cfg.data);
      setEmailDraft((cfg.data?.email_recipients || []).join(', '));
      setTgChat(cfg.data?.telegram_chat_id || '');
      setTgToken('');  // never echo the saved token
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load monitor data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);
  useEffect(() => {
    const id = setInterval(fetchAll, 30_000);
    return () => clearInterval(id);
  }, []);

  const summary = useMemo(() => status?.summary || {}, [status]);

  const ackOne = async (id) => {
    try {
      await axios.post(`${API}/api/admin/health/active/${id}/ack`, {}, { headers: tokenHdr() });
      toast.success('Acknowledged');
      setActive((p) => p.filter((a) => a.id !== id));
    } catch (e) {
      toast.error('Could not acknowledge');
    }
  };

  const ackAll = async () => {
    if (!window.confirm(`Acknowledge ALL ${active.length} unresolved alerts? Use this when you've already triaged them and they're known/expected (e.g. cache-miss timeouts that customers don't see thanks to bulletproof caching).`)) return;
    try {
      const r = await axios.post(`${API}/api/admin/health/active/ack-all`, {}, { headers: tokenHdr() });
      toast.success(`Acknowledged ${r.data?.acknowledged ?? active.length} alerts`);
      setActive([]);
    } catch (e) {
      toast.error('Bulk acknowledge failed');
    }
  };

  const cleanupZombies = async () => {
    if (!window.confirm('Clean up zombie alerts?\n\nThis automatically resolves duplicate incidents (same endpoint listed multiple times) and any incidents whose endpoint is currently healthy. It does NOT touch incidents that are still genuinely failing.')) return;
    try {
      const r = await axios.post(`${API}/api/admin/health/active/cleanup-zombies`, {}, { headers: tokenHdr() });
      const total = r.data?.total_resolved ?? 0;
      const dup = r.data?.duplicates_resolved ?? 0;
      const healthy = r.data?.healthy_endpoints_resolved ?? 0;
      toast.success(`Cleaned up ${total} zombie alerts (${dup} duplicates, ${healthy} already healthy)`);
      fetchAll();
    } catch (e) {
      toast.error('Zombie cleanup failed');
    }
  };

  const saveSettings = async () => {
    setSavingSettings(true);
    try {
      const recipients = emailDraft
        .split(/[,\n;]/).map((x) => x.trim()).filter(Boolean);
      const payload = {
        email_recipients: recipients,
        telegram_chat_id: tgChat,
      };
      if (tgToken.trim().length > 10) payload.telegram_bot_token = tgToken.trim();
      const r = await axios.put(`${API}/api/admin/health/settings`, payload, { headers: tokenHdr() });
      setSettings(r.data);
      setTgToken('');
      toast.success('Settings saved');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not save settings');
    } finally {
      setSavingSettings(false);
    }
  };

  const sendTest = async () => {
    setTestingAlert(true);
    try {
      const r = await axios.post(`${API}/api/admin/health/test-alert`, {}, { headers: tokenHdr() });
      const ch = [
        r.data.email ? '✓ Email' : '✗ Email',
        r.data.telegram ? '✓ Telegram' : '✗ Telegram',
      ].join(' · ');
      toast.success(`Test sent: ${ch}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Test alert failed');
    } finally {
      setTestingAlert(false);
    }
  };

  if (loading && !status) {
    return (
      <div className="p-8 flex items-center justify-center text-slate-500">
        <Loader2 className="w-6 h-6 animate-spin text-red-500 mr-2" /> Loading health monitor…
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="health-monitor-page">
      <div className="mb-6 flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-2">
            <ShieldAlert className="w-7 h-7 text-red-600" /> Health Monitor
          </h1>
          <p className="text-sm text-slate-600 mt-1 max-w-2xl">
            Pings every customer-facing endpoint every 60 seconds. Fires email + Telegram alerts on 2 consecutive failures and re-alerts every 5 minutes until acknowledged.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchAll} data-testid="health-monitor-refresh">
          <RefreshCw className="w-4 h-4 mr-1" /> Refresh
        </Button>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <Card className={`p-4 ${summary.unhealthy > 0 ? 'bg-red-50 border-red-300' : 'bg-emerald-50 border-emerald-300'}`}>
          <div className="text-[10px] uppercase font-bold tracking-wider text-slate-700 flex items-center gap-1">
            <Activity className="w-3 h-3" /> Endpoints
          </div>
          <div className="text-2xl font-black mt-1">{summary.healthy ?? 0}/{summary.monitored ?? 0}</div>
          <div className="text-xs text-slate-600">healthy right now</div>
        </Card>
        <Card className="p-4 bg-amber-50 border-amber-300" data-testid="health-summary-active">
          <div className="text-[10px] uppercase font-bold tracking-wider text-amber-800 flex items-center gap-1">
            <Bell className="w-3 h-3" /> Active alerts
          </div>
          <div className="text-2xl font-black mt-1 text-amber-900">{status?.active_unack_alerts ?? 0}</div>
          <div className="text-xs text-amber-700">unacknowledged</div>
        </Card>
        <Card className="p-4">
          <div className="text-[10px] uppercase font-bold tracking-wider text-slate-500 flex items-center gap-1">
            <Clock className="w-3 h-3" /> Past 30 days
          </div>
          <div className="text-2xl font-black mt-1">{incidents.length}</div>
          <div className="text-xs text-slate-500">total incidents</div>
        </Card>
        <Card className="p-4 bg-slate-50">
          <div className="text-[10px] uppercase font-bold tracking-wider text-slate-500">Channels</div>
          <div className="mt-1 flex items-center gap-3 text-xs">
            <span className={`flex items-center gap-1 font-bold ${(settings?.email_recipients || []).length > 0 ? 'text-emerald-700' : 'text-slate-400'}`}>
              <Mail className="w-3 h-3" /> {(settings?.email_recipients || []).length > 0 ? 'Email ON' : 'Email off'}
            </span>
            <span className={`flex items-center gap-1 font-bold ${settings?.telegram_chat_id && (settings?.telegram_bot_token_masked) ? 'text-emerald-700' : 'text-slate-400'}`}>
              <MessageSquare className="w-3 h-3" /> {settings?.telegram_chat_id && settings?.telegram_bot_token_masked ? 'Telegram ON' : 'Telegram off'}
            </span>
          </div>
        </Card>
      </div>

      {/* Active alerts */}
      {active.length > 0 && (
        <Card className="p-5 mb-6 border-2 border-red-400 bg-red-50" data-testid="health-active-alerts">
          <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
            <h2 className="text-lg font-bold text-red-900 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5" /> Unacknowledged outage alerts ({active.length})
            </h2>
            {active.length > 1 && (
              <div className="flex gap-2 flex-wrap">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={cleanupZombies}
                  className="border-red-300 text-red-800 hover:bg-red-100 font-semibold"
                  data-testid="health-alert-cleanup-zombies"
                  title="Auto-resolve duplicate incidents and any incidents whose endpoint is currently healthy"
                >
                  Clean up zombies
                </Button>
                <Button
                  size="sm"
                  onClick={ackAll}
                  className="bg-red-700 hover:bg-red-800 text-white font-bold"
                  data-testid="health-alert-ack-all"
                >
                  Acknowledge all {active.length}
                </Button>
              </div>
            )}
          </div>
          <div className="space-y-2">
            {active.map((a) => (
              <div key={a.id} className="bg-white border border-red-200 rounded-lg p-3 flex items-start justify-between gap-3 flex-wrap" data-testid={`health-alert-${a.id}`}>
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-slate-900">{a.label}</div>
                  <div className="text-xs text-slate-600 mt-0.5">
                    Started {fmtTime(a.first_failure_at)} · {a.alert_count} alert{a.alert_count === 1 ? '' : 's'} sent
                  </div>
                  <div className="text-xs text-red-700 mt-1 font-mono break-all">
                    {a.last_failure_reason || a.first_failure_reason}
                  </div>
                </div>
                <Button size="sm" onClick={() => ackOne(a.id)} className="bg-red-700 hover:bg-red-800 text-white font-bold" data-testid={`health-alert-ack-${a.id}`}>
                  Acknowledge
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Status grid */}
      <Card className="p-5 mb-6">
        <h2 className="text-lg font-bold text-slate-900 mb-3 flex items-center gap-2">
          <Activity className="w-5 h-5 text-slate-500" /> Endpoint status
        </h2>
        <div className="grid sm:grid-cols-2 gap-2">
          {(status?.endpoints || []).map((ep) => {
            const last = ep.last_check;
            const healthy = last?.healthy === true;
            const unknown = !last;
            return (
              <div
                key={ep.label}
                className={`border rounded-lg p-3 flex items-start justify-between gap-2 ${
                  unknown ? 'bg-slate-50 border-slate-200' :
                  healthy ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-300'
                }`}
                data-testid={`health-endpoint-${ep.label.toLowerCase().replace(/\s+/g, '-')}`}
              >
                <div className="flex items-start gap-2 flex-1 min-w-0">
                  {unknown
                    ? <Clock className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" />
                    : healthy
                      ? <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                      : <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />}
                  <div className="min-w-0">
                    <div className="font-bold text-slate-900 text-sm">{ep.label}</div>
                    <div className="text-[11px] text-slate-500 font-mono truncate">{ep.path}</div>
                    {!unknown && (
                      <div className="text-[11px] text-slate-600 mt-0.5">
                        {last.elapsed_ms}ms · {fmtTime(last.checked_at)}
                        {!healthy && last.failure_reason && (
                          <div className="text-red-700 font-mono mt-0.5 break-all">{last.failure_reason}</div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Notification settings */}
      <Card className="p-5 mb-6" data-testid="health-settings-card">
        <h2 className="text-lg font-bold text-slate-900 mb-1 flex items-center gap-2">
          <Bell className="w-5 h-5 text-amber-500" /> Notification settings
        </h2>
        <p className="text-xs text-slate-500 mb-4">
          Where outage alerts get sent. Re-sent every 5 min until you acknowledge.
        </p>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1 flex items-center gap-1">
              <Mail className="w-3 h-3" /> Email recipients (comma-separated)
            </label>
            <Textarea
              value={emailDraft}
              onChange={(e) => setEmailDraft(e.target.value)}
              rows={2}
              placeholder="alerts@yourdomain.com, you@gmail.com"
              className="text-sm"
              data-testid="health-email-input"
            />
          </div>

          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1 flex items-center gap-1">
                <MessageSquare className="w-3 h-3" /> Telegram bot token
                {settings?.telegram_bot_token_masked && (
                  <span className="ml-1 text-[10px] font-mono text-slate-500">saved: {settings.telegram_bot_token_masked}</span>
                )}
              </label>
              <Input
                type="password"
                value={tgToken}
                onChange={(e) => setTgToken(e.target.value)}
                placeholder={settings?.telegram_bot_token_masked ? '(leave blank to keep)' : 'paste from @BotFather'}
                className="text-sm font-mono"
                data-testid="health-telegram-token-input"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Telegram chat ID</label>
              <Input
                value={tgChat}
                onChange={(e) => setTgChat(e.target.value)}
                placeholder="e.g. 123456789"
                className="text-sm font-mono"
                data-testid="health-telegram-chat-input"
              />
            </div>
          </div>

          <details className="text-xs text-slate-600 bg-slate-50 rounded-lg p-3">
            <summary className="font-semibold cursor-pointer">📲 How to set up Telegram (60 seconds)</summary>
            <ol className="list-decimal list-inside mt-2 space-y-1 text-slate-700">
              <li>Open Telegram, search <code>@BotFather</code> → click Start</li>
              <li>Send <code>/newbot</code> → give it a name like "Tile Station Alerts" → choose a username ending in <code>_bot</code></li>
              <li>BotFather replies with a token like <code>1234567890:AAH...</code> — paste it above</li>
              <li>Search for your new bot, send it any message (eg "hi") to open the chat</li>
              <li>In a browser, visit <code>https://api.telegram.org/botYOUR_TOKEN/getUpdates</code> — find <code>"chat":{`{`}"id": <b>123456789</b>{`}`}</code> in the response — paste that number above</li>
              <li>Save → click "Send test alert" — your phone should ping</li>
            </ol>
          </details>

          <div className="flex items-center gap-2 flex-wrap pt-2">
            <Button
              onClick={saveSettings}
              disabled={savingSettings}
              className="bg-slate-900 hover:bg-slate-800 text-yellow-300 font-bold"
              data-testid="health-save-settings-btn"
            >
              {savingSettings ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
              Save settings
            </Button>
            <Button
              onClick={sendTest}
              disabled={testingAlert}
              variant="outline"
              className="border-amber-300 text-amber-900 hover:bg-amber-50 font-bold"
              data-testid="health-test-alert-btn"
            >
              {testingAlert ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />}
              Send test alert
            </Button>
          </div>
        </div>
      </Card>

      {/* Recent incidents */}
      <Card className="p-5" data-testid="health-incidents-card">
        <h2 className="text-lg font-bold text-slate-900 mb-3 flex items-center gap-2">
          <Clock className="w-5 h-5 text-slate-500" /> Past 30 days incidents
        </h2>
        {incidents.length === 0 ? (
          <div className="text-sm text-slate-500 text-center py-6">
            No incidents in the last 30 days. 🎉
          </div>
        ) : (
          <div className="text-xs">
            <div className="grid grid-cols-12 gap-2 font-bold text-slate-500 uppercase tracking-wide pb-2 border-b">
              <div className="col-span-3">Endpoint</div>
              <div className="col-span-2">Started</div>
              <div className="col-span-2">Resolved</div>
              <div className="col-span-1">Alerts</div>
              <div className="col-span-1">Status</div>
              <div className="col-span-3">Reason</div>
            </div>
            {incidents.slice(0, 50).map((i) => (
              <div key={i.id} className="grid grid-cols-12 gap-2 py-2 border-b border-slate-100">
                <div className="col-span-3 font-bold truncate">{i.label}</div>
                <div className="col-span-2 text-slate-600">{fmtTime(i.first_failure_at)}</div>
                <div className="col-span-2 text-slate-600">{i.resolved ? fmtTime(i.resolved_at) : '—'}</div>
                <div className="col-span-1">{i.alert_count}</div>
                <div className="col-span-1">
                  {i.resolved
                    ? <span className="bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded text-[10px] font-bold">RESOLVED</span>
                    : i.acknowledged
                      ? <span className="bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded text-[10px] font-bold">ACKED</span>
                      : <span className="bg-red-100 text-red-700 px-1.5 py-0.5 rounded text-[10px] font-bold">LIVE</span>}
                </div>
                <div className="col-span-3 text-slate-600 font-mono truncate" title={i.last_failure_reason || i.first_failure_reason}>
                  {i.last_failure_reason || i.first_failure_reason || '—'}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};

export default HealthMonitor;
