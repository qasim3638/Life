import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Switch } from '../../components/ui/switch';
import { CalendarClock, Eye, Save, Send, Lock } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export default function WeeklyDigestAdmin() {
  const { token, user } = useAuth();
  const isSuperAdmin = user?.role === 'super_admin';
  const isAdminish = ['super_admin', 'admin'].includes(user?.role);
  const headers = { Authorization: `Bearer ${token}` };

  const [settings, setSettings] = useState(null);
  const [recipientsInput, setRecipientsInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [previewHtml, setPreviewHtml] = useState('');

  const load = async () => {
    try {
      setLoading(true);
      const [s, p] = await Promise.all([
        axios.get(`${API}/weekly-digest/settings`, { headers }),
        axios.get(`${API}/weekly-digest/preview`, { headers }),
      ]);
      setSettings(s.data);
      setRecipientsInput((s.data.recipient_emails || []).join(', '));
      setPreviewHtml(p.data.html || '');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load digest');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (token) load(); /* eslint-disable-next-line */ }, [token]);

  const save = async () => {
    if (!isSuperAdmin) return;
    try {
      setSaving(true);
      const recipient_emails = recipientsInput.split(/[,\s;]+/).map(s => s.trim().toLowerCase()).filter(s => s.includes('@'));
      const res = await axios.put(`${API}/weekly-digest/settings`, {
        enabled: !!settings.enabled,
        recipient_emails,
        weekday: Number(settings.weekday),
        hour_utc: Number(settings.hour_utc),
      }, { headers });
      setSettings(res.data);
      setRecipientsInput((res.data.recipient_emails || []).join(', '));
      toast.success('Saved');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const sendNow = async () => {
    if (!isSuperAdmin) return;
    try {
      setSending(true);
      const res = await axios.post(`${API}/weekly-digest/send-now`, {}, { headers });
      const status = res.data?.status;
      if (status === 'ok') toast.success(`Digest sent to ${res.data.recipients.length} recipient(s)`);
      else if (status === 'no_recipients') toast.error('Add at least one recipient email first');
      else if (status === 'disabled') toast.error('Digest is currently disabled');
      else toast.error(`Send failed: ${status}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Send failed');
    } finally {
      setSending(false);
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
    <div className="p-6 space-y-5" data-testid="weekly-digest-admin">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <CalendarClock className="w-7 h-7 text-emerald-600" />
          <div>
            <h1 className="text-2xl font-bold">Weekly Digest</h1>
            <p className="text-sm text-gray-500">A Monday-morning email summarising recovered revenue, captured emails &amp; top referrer</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={load} disabled={loading} data-testid="digest-refresh">
            <Eye className="w-4 h-4 mr-1" /> Refresh preview
          </Button>
          {isSuperAdmin && (
            <Button onClick={sendNow} disabled={sending} data-testid="digest-send-now">
              <Send className="w-4 h-4 mr-1" />
              {sending ? 'Sending…' : 'Send now (test)'}
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <CardHeader><CardTitle className="text-base">Settings</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {settings && (
              <>
                <div className="flex items-center justify-between border rounded-lg p-3">
                  <div>
                    <Label className="text-sm font-semibold">Send weekly digest</Label>
                    <p className="text-xs text-gray-500">Pause to stop the Monday email immediately.</p>
                  </div>
                  <Switch
                    checked={!!settings.enabled}
                    onCheckedChange={(v) => setSettings({ ...settings, enabled: v })}
                    disabled={!isSuperAdmin}
                    data-testid="digest-enabled"
                  />
                </div>

                <div>
                  <Label className="text-xs uppercase tracking-wider text-gray-500">Recipient emails (comma-separated)</Label>
                  <Input
                    value={recipientsInput}
                    onChange={(e) => setRecipientsInput(e.target.value)}
                    placeholder="boss@tilestation.co.uk, ops@tilestation.co.uk"
                    disabled={!isSuperAdmin}
                    data-testid="digest-recipients"
                  />
                  <p className="text-[11px] text-gray-400 mt-1">Anyone in this list will receive the Monday email.</p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs uppercase tracking-wider text-gray-500">Day of week</Label>
                    <select
                      value={settings.weekday}
                      onChange={(e) => setSettings({ ...settings, weekday: Number(e.target.value) })}
                      disabled={!isSuperAdmin}
                      className="w-full text-sm border rounded-md px-2 py-2 bg-white disabled:bg-gray-50"
                      data-testid="digest-weekday"
                    >
                      {WEEKDAYS.map((d, i) => <option key={i} value={i}>{d}</option>)}
                    </select>
                  </div>
                  <div>
                    <Label className="text-xs uppercase tracking-wider text-gray-500">Hour (UTC)</Label>
                    <Input
                      type="number" min={0} max={23}
                      value={settings.hour_utc}
                      onChange={(e) => setSettings({ ...settings, hour_utc: e.target.value })}
                      disabled={!isSuperAdmin}
                      data-testid="digest-hour"
                    />
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button onClick={save} disabled={!isSuperAdmin || saving} data-testid="digest-save">
                    <Save className="w-4 h-4 mr-1" />
                    {saving ? 'Saving…' : 'Save settings'}
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Live preview</CardTitle></CardHeader>
          <CardContent>
            {loading
              ? <p className="text-sm text-gray-400">Loading…</p>
              : (
                <div
                  className="border rounded-lg overflow-hidden bg-gray-50 max-h-[600px] overflow-y-auto"
                  dangerouslySetInnerHTML={{ __html: previewHtml }}
                  data-testid="digest-preview"
                />
              )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
