import React, { useState, useEffect, useCallback } from 'react';
import {
  MessageCircle, Send, Clock, CheckCircle, XCircle, AlertTriangle,
  Settings, Save, Loader2, RefreshCw, Trash2, TestTube, Phone,
  Power, PowerOff, ChevronDown, ChevronRight, X, Eye
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function WhatsAppManager() {
  const [settings, setSettings] = useState(null);
  const [queue, setQueue] = useState({ messages: [], counts: { total: 0, pending: 0, sent: 0, failed: 0 } });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testPhone, setTestPhone] = useState('');
  const [testName, setTestName] = useState('');
  const [sendingTest, setSendingTest] = useState(false);
  const [queueFilter, setQueueFilter] = useState('');

  const headers = useCallback(() => ({
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'Content-Type': 'application/json',
  }), []);

  const fetchData = useCallback(async () => {
    try {
      const [settingsRes, queueRes] = await Promise.all([
        fetch(`${API_URL}/api/whatsapp/settings`, { headers: headers() }),
        fetch(`${API_URL}/api/whatsapp/queue${queueFilter ? `?status=${queueFilter}` : ''}`, { headers: headers() }),
      ]);
      if (settingsRes.ok) setSettings(await settingsRes.json());
      if (queueRes.ok) setQueue(await queueRes.json());
    } catch {
      toast.error('Failed to load WhatsApp settings');
    } finally {
      setLoading(false);
    }
  }, [headers, queueFilter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const saveSettings = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/whatsapp/settings`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify(settings),
      });
      if (res.ok) toast.success('Settings saved');
      else throw new Error();
    } catch {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const sendTestMessage = async () => {
    if (!testPhone) { toast.error('Enter a phone number'); return; }
    setSendingTest(true);
    try {
      const res = await fetch(`${API_URL}/api/whatsapp/test`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ phone: testPhone, name: testName || 'Test' }),
      });
      if (res.ok) {
        toast.success('Test message sent!');
        fetchData();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Send failed');
      }
    } catch {
      toast.error('Failed to send test message');
    } finally {
      setSendingTest(false);
    }
  };

  const cancelMessage = async (id) => {
    try {
      const res = await fetch(`${API_URL}/api/whatsapp/queue/${id}`, {
        method: 'DELETE',
        headers: headers(),
      });
      if (res.ok) { toast.success('Message cancelled'); fetchData(); }
      else toast.error('Failed to cancel');
    } catch {
      toast.error('Failed to cancel');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-green-500" />
      </div>
    );
  }

  const isEnabled = settings?.enabled;
  const hasCreds = settings?.credentials_configured;

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6" data-testid="whatsapp-manager">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-green-500 rounded-xl flex items-center justify-center">
            <MessageCircle className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">WhatsApp Messages</h1>
            <p className="text-sm text-gray-500">Automated welcome messages for new trade customers</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchData}>
            <RefreshCw className="w-4 h-4 mr-1" /> Refresh
          </Button>
          <Button onClick={saveSettings} disabled={saving} className="bg-green-600 hover:bg-green-700" data-testid="save-whatsapp-settings">
            {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Save className="w-4 h-4 mr-1" />}
            Save Settings
          </Button>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatusCard icon={Clock} label="Pending" value={queue.counts.pending} color="amber" />
        <StatusCard icon={CheckCircle} label="Sent" value={queue.counts.sent} color="green" />
        <StatusCard icon={XCircle} label="Failed" value={queue.counts.failed} color="red" />
        <StatusCard icon={Send} label="Total" value={queue.counts.total} color="gray" />
      </div>

      {/* Credentials Warning */}
      {!hasCreds && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3" data-testid="creds-warning">
          <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-amber-800">WhatsApp API Credentials Not Configured</p>
            <p className="text-sm text-amber-700 mt-1">
              To send real messages, add these to your backend environment variables:
            </p>
            <ul className="text-sm text-amber-700 mt-2 space-y-1 list-disc list-inside">
              <li><code className="bg-amber-100 px-1 rounded">WHATSAPP_PHONE_NUMBER_ID</code> — from Meta App Dashboard</li>
              <li><code className="bg-amber-100 px-1 rounded">WHATSAPP_ACCESS_TOKEN</code> — from Meta App Dashboard</li>
            </ul>
            <p className="text-xs text-amber-600 mt-2">Messages will be queued but won't send until credentials are configured.</p>
          </div>
        </div>
      )}

      {/* Main Toggle + Settings */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        {/* Toggle Bar */}
        <div className={`flex items-center justify-between px-6 py-4 ${isEnabled ? 'bg-green-50' : 'bg-gray-50'}`}>
          <div className="flex items-center gap-3">
            {isEnabled ? (
              <><Power className="w-5 h-5 text-green-600" /><span className="font-semibold text-green-700">Auto-messaging is ON</span></>
            ) : (
              <><PowerOff className="w-5 h-5 text-gray-400" /><span className="font-semibold text-gray-500">Auto-messaging is OFF</span></>
            )}
          </div>
          <button
            onClick={() => setSettings(s => ({ ...s, enabled: !s.enabled }))}
            className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors shadow-sm ${isEnabled ? 'bg-green-500' : 'bg-gray-300'}`}
            data-testid="whatsapp-toggle"
          >
            <span className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform shadow ${isEnabled ? 'translate-x-6' : 'translate-x-1'}`} />
          </button>
        </div>

        {/* Settings Form */}
        <div className="p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">WhatsApp Template Name</label>
            <Input
              value={settings?.template_name || ''}
              onChange={e => setSettings(s => ({ ...s, template_name: e.target.value }))}
              placeholder="e.g., trade_welcome"
              className="max-w-md"
              data-testid="template-name-input"
            />
            <p className="text-xs text-gray-400 mt-1">The approved template name from your WhatsApp Manager (Meta Business)</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Message Preview</label>
            <textarea
              value={settings?.message_preview || ''}
              onChange={e => setSettings(s => ({ ...s, message_preview: e.target.value }))}
              placeholder="Hi {name}, welcome to Tile Station Trade!..."
              className="w-full border rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-green-400"
              rows={3}
              data-testid="message-preview-input"
            />
            <p className="text-xs text-gray-400 mt-1">
              This is for your reference only. The actual message is controlled by your WhatsApp template.
              Use <code className="bg-gray-100 px-1 rounded">{'{name}'}</code> where the customer's first name should appear.
            </p>
          </div>

          {/* Scheduling Info */}
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-blue-500" />
              <span className="font-medium text-sm text-blue-800">Scheduling Rules</span>
            </div>
            <ul className="text-sm text-blue-700 space-y-1">
              <li>Registration <strong>9am - 6pm</strong> : Message sent <strong>1 hour after</strong> registration</li>
              <li>Registration <strong>6pm - 9am</strong> : Message sent at <strong>9am next morning</strong></li>
            </ul>
          </div>
        </div>
      </div>

      {/* Test Message */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="flex items-center gap-2 mb-4">
          <TestTube className="w-4 h-4 text-purple-500" />
          <h3 className="font-semibold text-gray-900">Send Test Message</h3>
        </div>
        <div className="flex gap-3 items-end">
          <div className="flex-1 max-w-xs">
            <label className="block text-xs font-medium text-gray-500 mb-1">Phone Number</label>
            <Input
              value={testPhone}
              onChange={e => setTestPhone(e.target.value)}
              placeholder="+447700900000"
              data-testid="test-phone-input"
            />
          </div>
          <div className="flex-1 max-w-xs">
            <label className="block text-xs font-medium text-gray-500 mb-1">Name (for {'{name}'} variable)</label>
            <Input
              value={testName}
              onChange={e => setTestName(e.target.value)}
              placeholder="John"
              data-testid="test-name-input"
            />
          </div>
          <Button
            onClick={sendTestMessage}
            disabled={sendingTest || !hasCreds}
            className="bg-purple-600 hover:bg-purple-700"
            data-testid="send-test-btn"
          >
            {sendingTest ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />}
            Send Test
          </Button>
        </div>
        {!hasCreds && <p className="text-xs text-red-400 mt-2">Configure API credentials first to send test messages</p>}
      </div>

      {/* Message Queue */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="font-semibold text-gray-900">Message Queue</h3>
          <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
            {['', 'pending', 'sent', 'failed'].map(f => (
              <button
                key={f}
                onClick={() => setQueueFilter(f)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  queueFilter === f ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {f || 'All'}
              </button>
            ))}
          </div>
        </div>
        <div className="divide-y max-h-96 overflow-auto">
          {queue.messages.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              <MessageCircle className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">No messages yet</p>
              <p className="text-xs mt-1">Messages will appear here when trade customers register</p>
            </div>
          ) : (
            queue.messages.map(msg => (
              <MessageRow key={msg.id} msg={msg} onCancel={cancelMessage} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function StatusCard({ icon: Icon, label, value, color }) {
  const colors = {
    amber: 'bg-amber-50 text-amber-600 border-amber-100',
    green: 'bg-green-50 text-green-600 border-green-100',
    red: 'bg-red-50 text-red-600 border-red-100',
    gray: 'bg-gray-50 text-gray-600 border-gray-100',
  };
  return (
    <div className={`rounded-xl border p-4 ${colors[color]}`} data-testid={`status-${label.toLowerCase()}`}>
      <div className="flex items-center justify-between">
        <Icon className="w-5 h-5 opacity-60" />
        <span className="text-2xl font-bold">{value}</span>
      </div>
      <p className="text-xs mt-1 opacity-70">{label}</p>
    </div>
  );
}

function MessageRow({ msg, onCancel }) {
  const statusConfig = {
    pending: { icon: Clock, color: 'text-amber-500', bg: 'bg-amber-50', label: 'Pending' },
    sent: { icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-50', label: 'Sent' },
    failed: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-50', label: 'Failed' },
    cancelled: { icon: X, color: 'text-gray-400', bg: 'bg-gray-50', label: 'Cancelled' },
  };
  const config = statusConfig[msg.status] || statusConfig.pending;
  const Icon = config.icon;

  const formatTime = (iso) => {
    if (!iso) return '-';
    try {
      return new Date(iso).toLocaleString('en-GB', {
        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
      });
    } catch { return iso; }
  };

  return (
    <div className="flex items-center gap-4 px-4 py-3 hover:bg-gray-50 transition-colors" data-testid={`message-row-${msg.id}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${config.bg}`}>
        <Icon className={`w-4 h-4 ${config.color}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm text-gray-900 truncate">{msg.customer_name || 'Unknown'}</span>
          {msg.is_test && <span className="px-1.5 py-0.5 bg-purple-100 text-purple-600 text-[10px] font-medium rounded">TEST</span>}
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-400 mt-0.5">
          <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{msg.phone}</span>
          {msg.customer_email && <span>{msg.customer_email}</span>}
        </div>
      </div>
      <div className="text-right flex-shrink-0">
        <div className={`text-xs font-medium ${config.color}`}>{config.label}</div>
        <div className="text-[10px] text-gray-400 mt-0.5">
          {msg.status === 'sent' ? `Sent ${formatTime(msg.sent_at)}` : `Scheduled ${formatTime(msg.scheduled_at)}`}
        </div>
      </div>
      {msg.status === 'pending' && (
        <button onClick={() => onCancel(msg.id)} className="p-1.5 rounded-md text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors" title="Cancel">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      )}
      {msg.error && (
        <span className="text-[10px] text-red-400 max-w-32 truncate" title={msg.error}>{msg.error}</span>
      )}
    </div>
  );
}
