import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, Plus, X, Send, Clock } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Switch } from '../ui/switch';
import { Label } from '../ui/label';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Manages the nightly reconciliation-email schedule. Settings are persisted
 * server-side at `website_settings.reconciliation_schedule_settings` and the
 * APScheduler probe checks them hourly.
 */
export default function ReconciliationScheduleDialog({ open, onOpenChange }) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [hourUtc, setHourUtc] = useState(6);
  const [recipients, setRecipients] = useState([]);
  const [newEmail, setNewEmail] = useState('');
  const [logEntries, setLogEntries] = useState([]);

  const auth = () => {
    const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const loadLog = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/invoices/reconciliation/schedule/log`, { headers: auth() });
      setLogEntries(Array.isArray(res.data?.entries) ? res.data.entries : []);
    } catch {
      setLogEntries([]);
    }
  };

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    Promise.all([
      axios.get(`${API_URL}/api/invoices/reconciliation/schedule`, { headers: auth() })
        .then(res => {
          setEnabled(!!res.data.enabled);
          setHourUtc(Number.isFinite(res.data.hour_utc) ? res.data.hour_utc : 6);
          setRecipients(Array.isArray(res.data.recipient_emails) ? res.data.recipient_emails : []);
        }),
      loadLog(),
    ])
      .catch(() => toast.error('Could not load schedule'))
      .finally(() => setLoading(false));
  }, [open]);

  const addEmail = () => {
    const e = newEmail.trim().toLowerCase();
    if (!e || !e.includes('@')) { toast.error('Enter a valid email'); return; }
    if (recipients.includes(e)) { toast.error('Already added'); return; }
    setRecipients([...recipients, e]);
    setNewEmail('');
  };

  const removeEmail = (e) => setRecipients(recipients.filter(r => r !== e));

  const save = async () => {
    if (enabled && recipients.length === 0) {
      toast.error('Add at least one recipient before enabling');
      return;
    }
    setSaving(true);
    try {
      await axios.put(
        `${API_URL}/api/invoices/reconciliation/schedule`,
        { enabled, hour_utc: hourUtc, recipient_emails: recipients },
        { headers: auth() }
      );
      toast.success(enabled ? `Schedule on — fires daily at ${String(hourUtc).padStart(2,'0')}:00 UTC` : 'Schedule saved (off)');
      onOpenChange?.(false);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not save');
    } finally {
      setSaving(false);
    }
  };

  const sendTest = async () => {
    if (recipients.length === 0) { toast.error('Add a recipient first'); return; }
    setTesting(true);
    try {
      // Persist current settings first so the test reflects what the cron will actually send.
      await axios.put(
        `${API_URL}/api/invoices/reconciliation/schedule`,
        { enabled, hour_utc: hourUtc, recipient_emails: recipients },
        { headers: auth() }
      );
      const res = await axios.post(
        `${API_URL}/api/invoices/reconciliation/schedule/send-now`,
        {},
        { headers: auth() }
      );
      toast.success(`Sent test to ${res.data.recipients.join(', ')}`, {
        description: `${res.data.date} · Net £${Number(res.data.net_takings).toFixed(2)}`,
      });
      await loadLog();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not send');
    } finally {
      setTesting(false);
    }
  };

  // Local-time hint for the chosen UTC hour, helps non-UTC ops staff.
  const localHint = (() => {
    try {
      const d = new Date();
      d.setUTCHours(hourUtc, 0, 0, 0);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch { return null; }
  })();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="reconciliation-schedule-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-emerald-700" />
            Schedule daily reconciliation email
          </DialogTitle>
          <DialogDescription>
            We&apos;ll email yesterday&apos;s Z-read every morning at the time you choose.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-gray-500">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading...
          </div>
        ) : (
          <div className="space-y-5 py-2">
            <div className="flex items-center justify-between gap-3">
              <div>
                <Label htmlFor="recon-enabled" className="text-sm font-medium">Auto-send enabled</Label>
                <p className="text-[11px] text-gray-500">Hourly probe — fires at the configured UTC hour.</p>
              </div>
              <Switch
                id="recon-enabled"
                checked={enabled}
                onCheckedChange={setEnabled}
                data-testid="recon-enabled-switch"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs text-gray-600">Send time (UTC)</Label>
              <div className="flex items-center gap-2">
                <select
                  value={hourUtc}
                  onChange={(e) => setHourUtc(Number(e.target.value))}
                  className="border border-gray-200 rounded px-2 py-1.5 text-sm w-28"
                  data-testid="recon-hour-select"
                >
                  {Array.from({ length: 24 }).map((_, h) => (
                    <option key={h} value={h}>{String(h).padStart(2,'0')}:00</option>
                  ))}
                </select>
                {localHint && (
                  <span className="text-[11px] text-gray-500">≈ {localHint} your time</span>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-xs text-gray-600">Recipients</Label>
              <div className="flex flex-wrap gap-1.5">
                {recipients.length === 0 && (
                  <span className="text-xs text-gray-400 italic">No recipients yet — add your bookkeeper below.</span>
                )}
                {recipients.map((e) => (
                  <span
                    key={e}
                    className="inline-flex items-center gap-1.5 bg-gray-100 border border-gray-200 rounded-full pl-2.5 pr-1 py-0.5 text-xs"
                    data-testid={`recon-recipient-${e}`}
                  >
                    {e}
                    <button
                      type="button"
                      onClick={() => removeEmail(e)}
                      className="rounded-full hover:bg-gray-300 p-0.5"
                      aria-label={`Remove ${e}`}
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex gap-2">
                <Input
                  type="email"
                  placeholder="bookkeeper@example.com"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addEmail())}
                  className="text-sm"
                  data-testid="recon-new-email-input"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={addEmail}
                  data-testid="recon-add-email-btn"
                  className="gap-1"
                >
                  <Plus className="w-3.5 h-3.5" /> Add
                </Button>
              </div>
            </div>

            {logEntries.length > 0 && (
              <div className="space-y-1.5 pt-1">
                <Label className="text-xs text-gray-600">Last sent</Label>
                <ul className="rounded-md border border-gray-200 divide-y divide-gray-100 bg-gray-50/40" data-testid="recon-log-list">
                  {logEntries.map((e, i) => {
                    const ts = e.sent_at ? new Date(e.sent_at) : null;
                    const when = ts ? ts.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—';
                    const recipientCount = Array.isArray(e.recipients) ? e.recipients.length : 0;
                    const sourceLabel = e.source === 'manual' ? 'test' : 'auto';
                    return (
                      <li
                        key={`${e.sent_at}-${i}`}
                        className="flex items-center justify-between gap-2 px-2.5 py-1.5 text-[12px]"
                        data-testid={`recon-log-entry-${i}`}
                      >
                        <span className="flex items-center gap-1.5 text-gray-700 min-w-0">
                          <span className={`shrink-0 inline-block w-1.5 h-1.5 rounded-full ${e.source === 'manual' ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                          <span className="font-medium">{e.date}</span>
                          <span className="text-gray-400">·</span>
                          <span className="truncate text-gray-500">{when}</span>
                          <span className="text-gray-400">·</span>
                          <span className="text-gray-500">{recipientCount} recipient{recipientCount === 1 ? '' : 's'}</span>
                        </span>
                        <span className="flex items-center gap-1.5 shrink-0">
                          <span className="tabular-nums font-semibold text-gray-800">£{Number(e.net_takings || 0).toFixed(2)}</span>
                          <span className="text-[10px] uppercase tracking-wider text-gray-400">{sourceLabel}</span>
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>
        )}

        <DialogFooter className="flex-row justify-between sm:justify-between gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={sendTest}
            disabled={testing || saving || loading || recipients.length === 0}
            className="gap-1.5 text-emerald-700 hover:text-emerald-800"
            data-testid="recon-send-test-btn"
          >
            {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
            Send test now
          </Button>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange?.(false)}>
              Cancel
            </Button>
            <Button type="button" onClick={save} disabled={saving || loading} data-testid="recon-save-btn">
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}
              Save
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
