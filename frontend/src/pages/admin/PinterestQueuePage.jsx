/**
 * Pinterest Visual Engine — Pin Queue admin page
 *
 * Full management UI for the Pinterest visual marketing engine.
 * Lives at /admin/pinterest-queue.
 *
 * Three sections:
 *   1. Stats strip — pending/approved/posted/blocked counts + last run
 *   2. Pin Queue grid — cards with image, title, board, link, actions
 *   3. Boards config — per-board auto-approve toggles + Pinterest board ID
 *
 * Approve/Skip/Block/Edit are all one-tap actions (mobile-friendly).
 * Edit opens an inline modal with title/description/board/link/image.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, RefreshCw, Sparkles, Loader2, Check, X, Ban, Pencil,
  ExternalLink, Zap, Settings, AlertTriangle, Clock,
  TrendingUp, Image as ImageIcon, RotateCw,
} from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Switch } from '../../components/ui/switch';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../components/ui/select';
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '../../components/ui/dialog';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const token = () =>
  localStorage.getItem('token') || localStorage.getItem('access_token') || '';

const STATUS_TONE = {
  pending: 'bg-amber-100 text-amber-900 border-amber-300',
  approved: 'bg-blue-100 text-blue-900 border-blue-300',
  posted: 'bg-emerald-100 text-emerald-900 border-emerald-300',
  failed: 'bg-rose-100 text-rose-900 border-rose-300',
  skipped: 'bg-slate-100 text-slate-700 border-slate-300',
  blocked: 'bg-rose-50 text-rose-800 border-rose-300',
};

const TIER_LABEL = {
  lifestyle: { label: 'Room shot', tone: 'bg-emerald-100 text-emerald-900 border-emerald-300' },
  product: { label: 'Product cutout', tone: 'bg-slate-100 text-slate-700 border-slate-300' },
  ai: { label: 'AI generated', tone: 'bg-violet-100 text-violet-900 border-violet-300' },
};

const PinterestQueuePage = () => {
  const nav = useNavigate();
  const [tab, setTab] = useState('queue');
  const [statusFilter, setStatusFilter] = useState('pending');
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [boards, setBoards] = useState([]);
  const [blocklist, setBlocklist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [editing, setEditing] = useState(null); // candidate object

  const headers = useMemo(
    () => ({ headers: { Authorization: `Bearer ${token()}` } }),
    [],
  );

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [s, q, b] = await Promise.all([
        axios.get(`${API_URL}/api/admin/pinterest/visual/queue/summary`, headers),
        axios.get(
          `${API_URL}/api/admin/pinterest/visual/queue?status=${statusFilter}&limit=100`,
          headers,
        ),
        axios.get(`${API_URL}/api/admin/pinterest/visual/boards`, headers),
      ]);
      setSummary(s.data);
      setRows(q.data.rows || []);
      setBoards(b.data.boards || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not load queue');
    } finally {
      setLoading(false);
    }
  }, [headers, statusFilter]);

  const loadBlocklist = useCallback(async () => {
    try {
      const r = await axios.get(
        `${API_URL}/api/admin/pinterest/visual/blocklist`,
        headers,
      );
      setBlocklist(r.data.rows || []);
    } catch (e) {
      // Non-fatal
    }
  }, [headers]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (tab === 'blocklist') loadBlocklist();
  }, [tab, loadBlocklist]);

  const generateNow = async () => {
    setGenerating(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/pinterest/visual/queue/generate`,
        { target_count: 12 },
        headers,
      );
      toast.success(
        `Generated ${r.data.generated} Pin candidates (${r.data.auto_approved || 0} auto-approved)`,
      );
      loadAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Generation failed');
    } finally {
      setGenerating(false);
    }
  };

  const act = async (id, action) => {
    try {
      await axios.post(
        `${API_URL}/api/admin/pinterest/visual/queue/${id}/${action}`,
        {},
        headers,
      );
      toast.success(`${action} ✓`);
      loadAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || `Could not ${action}`);
    }
  };

  const saveEdit = async (id, fields) => {
    try {
      await axios.patch(
        `${API_URL}/api/admin/pinterest/visual/queue/${id}`,
        fields,
        headers,
      );
      toast.success('Saved');
      setEditing(null);
      loadAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    }
  };

  const updateBoardCfg = async (slug, fields) => {
    try {
      await axios.patch(
        `${API_URL}/api/admin/pinterest/visual/boards/${slug}`,
        fields,
        headers,
      );
      toast.success('Board updated');
      loadAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Update failed');
    }
  };

  const unblockImage = async (imageUrl) => {
    try {
      const b64 = btoa(imageUrl).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
      await axios.delete(
        `${API_URL}/api/admin/pinterest/visual/blocklist/${b64}`,
        headers,
      );
      toast.success('Image unblocked');
      loadBlocklist();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Unblock failed');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50" data-testid="pinterest-queue-page">
      <div className="max-w-7xl mx-auto px-6 py-6 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => nav('/admin/seo')}>
              <ArrowLeft className="w-4 h-4 mr-1" /> Back to SEO
            </Button>
            <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-rose-500" /> Pinterest Visual Engine
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={loadAll}
              disabled={loading}
              data-testid="pin-queue-refresh"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin mr-1" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-1" />
              )}
              Refresh
            </Button>
            <Button
              size="sm"
              onClick={generateNow}
              disabled={generating}
              className="bg-rose-600 hover:bg-rose-700 text-white"
              data-testid="pin-queue-generate-now"
            >
              {generating ? (
                <Loader2 className="w-4 h-4 animate-spin mr-1" />
              ) : (
                <Zap className="w-4 h-4 mr-1" />
              )}
              Generate now
            </Button>
          </div>
        </div>

        {/* Stats strip */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="pin-queue-stats">
            <Stat label="Pending review" value={summary.pending} tone="amber" testid="stat-pending" />
            <Stat label="Approved · queued" value={summary.approved} tone="blue" testid="stat-approved" />
            <Stat label="Posted to Pinterest" value={summary.posted} tone="emerald" testid="stat-posted" />
            <Stat label="Skipped / blocked" value={summary.skipped + (summary.blocked_images || 0)} tone="slate" testid="stat-skipped" />
            <Stat
              label="Last generation"
              value={
                summary.last_generated_at
                  ? new Date(summary.last_generated_at).toLocaleDateString('en-GB', {
                      day: '2-digit', month: 'short',
                    })
                  : 'Never'
              }
              tone="violet"
              testid="stat-last-gen"
            />
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 border-b border-slate-200">
          {[
            { id: 'queue', label: 'Pin Queue', icon: Clock },
            { id: 'performance', label: 'Performance', icon: TrendingUp },
            { id: 'lifestyle', label: 'AI Renders', icon: ImageIcon },
            { id: 'boards', label: 'Boards Config', icon: Settings },
            { id: 'blocklist', label: 'Blocked Images', icon: Ban },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              data-testid={`pin-tab-${id}`}
              className={`px-4 py-2 -mb-px border-b-2 font-medium text-sm flex items-center gap-1.5 transition ${
                tab === id
                  ? 'border-rose-500 text-rose-700'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              <Icon className="w-4 h-4" /> {label}
            </button>
          ))}
        </div>

        {/* Body */}
        {tab === 'queue' && (
          <div className="space-y-3" data-testid="pin-queue-tab">
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-600">Filter:</span>
              {['pending', 'approved', 'posted', 'failed', 'skipped', 'blocked'].map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  data-testid={`pin-filter-${s}`}
                  className={`px-2.5 py-1 rounded-md text-xs font-semibold border transition ${
                    statusFilter === s
                      ? STATUS_TONE[s] + ' ring-1 ring-offset-1 ring-current'
                      : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>

            {loading ? (
              <Card className="p-8 text-center text-slate-500">
                <Loader2 className="w-5 h-5 animate-spin inline" /> Loading queue…
              </Card>
            ) : rows.length === 0 ? (
              <Card className="p-8 text-center text-slate-500" data-testid="pin-queue-empty">
                <p className="text-sm">No {statusFilter} candidates yet.</p>
                {statusFilter === 'pending' && (
                  <p className="text-xs mt-1">
                    Click <strong>Generate now</strong> to create the first batch.
                  </p>
                )}
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {rows.map((c) => (
                  <PinCard
                    key={c.id}
                    candidate={c}
                    onApprove={() => act(c.id, 'approve')}
                    onSkip={() => act(c.id, 'skip')}
                    onBlock={() => act(c.id, 'block')}
                    onEdit={() => setEditing(c)}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'performance' && (
          <PerformanceTab headers={headers} />
        )}

        {tab === 'lifestyle' && (
          <LifestyleRendersTab headers={headers} />
        )}

        {tab === 'boards' && (
          <div className="space-y-3" data-testid="pin-boards-tab">
            <p className="text-sm text-slate-600">
              Toggle <strong>Auto-approve</strong> on a board to skip the review step. Brand-flagship
              boards (Bathroom Ideas, Luxury Suites, How-To) ship with auto-approve OFF — keep them
              that way until you're confident in the AI's output.
            </p>
            {boards.map((b) => (
              <Card
                key={b.slug}
                className="p-4 flex items-center justify-between flex-wrap gap-3"
                data-testid={`board-row-${b.slug}`}
              >
                <div className="min-w-0 flex-1">
                  <div className="font-bold text-slate-900 flex items-center gap-2">
                    <span className="text-xl">{b.emoji}</span>
                    {b.name}
                    {!b.is_active && (
                      <Badge variant="outline" className="text-xs">
                        Inactive
                      </Badge>
                    )}
                  </div>
                  <div className="text-xs text-slate-600 mt-1">{b.description}</div>
                  <div className="flex gap-3 text-[11px] text-slate-500 mt-2 flex-wrap">
                    <span>
                      Pinterest Board ID:{' '}
                      <code className="bg-slate-100 px-1 rounded">
                        {b.pinterest_board_id || 'auto-detect on connect'}
                      </code>
                    </span>
                    <span>Link target: {b.link_target}</span>
                    <span>Priority: {b.priority}</span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 text-sm font-medium">
                    <Switch
                      checked={!!b.auto_approve}
                      onCheckedChange={(v) =>
                        updateBoardCfg(b.slug, { auto_approve: v })
                      }
                      data-testid={`board-${b.slug}-autoapprove`}
                    />
                    <span className="text-slate-700">Auto-approve</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm font-medium">
                    <Switch
                      checked={!!b.is_active}
                      onCheckedChange={(v) =>
                        updateBoardCfg(b.slug, { is_active: v })
                      }
                      data-testid={`board-${b.slug}-active`}
                    />
                    <span className="text-slate-700">Active</span>
                  </label>
                </div>
              </Card>
            ))}
          </div>
        )}

        {tab === 'blocklist' && (
          <div className="space-y-3" data-testid="pin-blocklist-tab">
            <p className="text-sm text-slate-600">
              Images you've blocked. Future generations will never reuse these.
              Click <strong>Unblock</strong> to put one back in rotation.
            </p>
            {blocklist.length === 0 ? (
              <Card className="p-8 text-center text-slate-500">
                <p className="text-sm">No blocked images yet.</p>
                <p className="text-xs mt-1">
                  Images blocked from the Pin Queue will show up here.
                </p>
              </Card>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {blocklist.map((b) => (
                  <Card key={b.image_url} className="overflow-hidden">
                    <div className="aspect-[3/4] bg-slate-100 overflow-hidden">
                      <img
                        src={b.image_url}
                        alt="Blocked"
                        className="w-full h-full object-cover opacity-60"
                        loading="lazy"
                      />
                    </div>
                    <div className="p-2 space-y-1">
                      <div className="text-[10px] text-slate-500 truncate">
                        {b.product_slug || '—'}
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => unblockImage(b.image_url)}
                        className="w-full text-xs"
                      >
                        Unblock
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Edit dialog */}
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Pin candidate</DialogTitle>
          </DialogHeader>
          {editing && (
            <PinEditForm
              candidate={editing}
              boards={boards}
              onSave={(fields) => saveEdit(editing.id, fields)}
              onCancel={() => setEditing(null)}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

const Stat = ({ label, value, tone = 'slate', testid }) => {
  const tones = {
    amber: 'bg-amber-50 border-amber-200 text-amber-900',
    blue: 'bg-blue-50 border-blue-200 text-blue-900',
    emerald: 'bg-emerald-50 border-emerald-200 text-emerald-900',
    slate: 'bg-slate-50 border-slate-200 text-slate-900',
    violet: 'bg-violet-50 border-violet-200 text-violet-900',
  };
  return (
    <Card className={`p-3 border-2 ${tones[tone]}`} data-testid={testid}>
      <div className="text-[10px] uppercase tracking-wide font-semibold opacity-80">{label}</div>
      <div className="text-2xl font-bold font-mono mt-0.5">{value}</div>
    </Card>
  );
};

const PinCard = ({ candidate, onApprove, onSkip, onBlock, onEdit }) => {
  const tier = TIER_LABEL[candidate.image_tier] || TIER_LABEL.product;
  const status = STATUS_TONE[candidate.status] || STATUS_TONE.pending;
  return (
    <Card
      className="overflow-hidden flex flex-col"
      data-testid={`pin-card-${candidate.id}`}
    >
      <div className="relative aspect-[3/4] bg-slate-100 overflow-hidden">
        <img
          src={candidate.image_url}
          alt={candidate.alt_text || candidate.title}
          className="w-full h-full object-cover"
          loading="lazy"
        />
        <div className="absolute top-2 left-2 flex flex-wrap gap-1">
          <Badge className={`text-[10px] uppercase tracking-wide border ${tier.tone}`}>
            {tier.label}
          </Badge>
          <Badge className={`text-[10px] uppercase tracking-wide border ${status}`}>
            {candidate.status}
          </Badge>
        </div>
      </div>
      <div className="p-3 space-y-1.5 flex-1 flex flex-col">
        <div className="text-[10px] uppercase tracking-wide font-bold text-rose-700">
          → {candidate.board_name}
        </div>
        <h3 className="font-bold text-slate-900 leading-tight line-clamp-2">
          {candidate.title}
        </h3>
        <p className="text-xs text-slate-600 line-clamp-3 flex-1">
          {candidate.description}
        </p>
        <a
          href={candidate.link_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-600 hover:underline truncate flex items-center gap-1"
          data-testid={`pin-card-${candidate.id}-link`}
        >
          <ExternalLink className="w-3 h-3" />
          {candidate.product_name}
        </a>
        {candidate.last_error && (
          <div className="text-xs text-rose-700 bg-rose-50 px-2 py-1 rounded flex items-start gap-1">
            <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
            <span className="line-clamp-2">{candidate.last_error}</span>
          </div>
        )}
        {candidate.status === 'pending' && (
          <div className="grid grid-cols-4 gap-1 pt-1">
            <Button
              size="sm"
              onClick={onApprove}
              className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs h-8"
              data-testid={`pin-${candidate.id}-approve`}
            >
              <Check className="w-3 h-3 mr-1" /> OK
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={onEdit}
              className="text-xs h-8"
              data-testid={`pin-${candidate.id}-edit`}
            >
              <Pencil className="w-3 h-3 mr-1" /> Edit
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={onSkip}
              className="text-xs h-8"
              data-testid={`pin-${candidate.id}-skip`}
            >
              <X className="w-3 h-3 mr-1" /> Skip
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={onBlock}
              className="text-xs h-8 text-rose-700 border-rose-300 hover:bg-rose-50"
              data-testid={`pin-${candidate.id}-block`}
            >
              <Ban className="w-3 h-3 mr-1" /> Block
            </Button>
          </div>
        )}
        {candidate.status === 'approved' && candidate.scheduled_for && (
          <div className="text-xs text-slate-500 pt-1">
            <Clock className="w-3 h-3 inline mr-1" />
            Scheduled: {new Date(candidate.scheduled_for).toLocaleString('en-GB')}
          </div>
        )}
        {candidate.pinterest_pin_url && (
          <a
            href={candidate.pinterest_pin_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-rose-600 hover:underline pt-1 flex items-center gap-1"
          >
            <ExternalLink className="w-3 h-3" /> View live Pin
          </a>
        )}
      </div>
    </Card>
  );
};

const PinEditForm = ({ candidate, boards, onSave, onCancel }) => {
  const [form, setForm] = useState({
    title: candidate.title || '',
    description: candidate.description || '',
    board_slug: candidate.board_slug || '',
    link_url: candidate.link_url || '',
    image_url: candidate.image_url || '',
    alt_text: candidate.alt_text || '',
  });
  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs font-bold text-slate-700">Title</label>
        <Input
          value={form.title}
          onChange={(e) => update('title', e.target.value.slice(0, 100))}
          maxLength={100}
          data-testid="pin-edit-title"
        />
        <div className="text-[10px] text-slate-400 text-right">{form.title.length}/100</div>
      </div>
      <div>
        <label className="text-xs font-bold text-slate-700">Description</label>
        <Textarea
          value={form.description}
          onChange={(e) => update('description', e.target.value.slice(0, 500))}
          maxLength={500}
          rows={4}
          data-testid="pin-edit-description"
        />
        <div className="text-[10px] text-slate-400 text-right">{form.description.length}/500</div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-bold text-slate-700">Board</label>
          <Select
            value={form.board_slug}
            onValueChange={(v) => update('board_slug', v)}
          >
            <SelectTrigger data-testid="pin-edit-board">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {boards.map((b) => (
                <SelectItem key={b.slug} value={b.slug}>
                  {b.emoji} {b.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-xs font-bold text-slate-700">Alt text</label>
          <Input
            value={form.alt_text}
            onChange={(e) => update('alt_text', e.target.value.slice(0, 200))}
            maxLength={200}
            data-testid="pin-edit-alt"
          />
        </div>
      </div>
      <div>
        <label className="text-xs font-bold text-slate-700">Image URL</label>
        <Input
          value={form.image_url}
          onChange={(e) => update('image_url', e.target.value)}
          className="font-mono text-xs"
          data-testid="pin-edit-image"
        />
      </div>
      <div>
        <label className="text-xs font-bold text-slate-700">Link URL</label>
        <Input
          value={form.link_url}
          onChange={(e) => update('link_url', e.target.value)}
          className="font-mono text-xs"
          data-testid="pin-edit-link"
        />
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          onClick={() => onSave(form)}
          className="bg-emerald-600 hover:bg-emerald-700 text-white"
          data-testid="pin-edit-save"
        >
          <Check className="w-4 h-4 mr-1" /> Save changes
        </Button>
      </DialogFooter>
    </div>
  );
};

const PerformanceTab = ({ headers }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [repinning, setRepinning] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(
        `${API_URL}/api/admin/pinterest/visual/performance`,
        headers,
      );
      setData(r.data);
    } catch (e) {
      // Non-fatal
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => {
    load();
  }, [load]);

  const sync = async () => {
    setSyncing(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/pinterest/visual/performance/sync`,
        {},
        headers,
      );
      if (r.data.reason === 'integration_not_connected') {
        toast.error('Pinterest not connected yet — sync skipped');
      } else {
        toast.success(`Synced ${r.data.synced || 0} pins`);
      }
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const repin = async () => {
    setRepinning(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/pinterest/visual/repin/run`,
        {},
        headers,
      );
      if (r.data.reason) {
        toast.error(`Repin: ${r.data.reason}`);
      } else {
        toast.success(`Scheduled ${r.data.repinned || 0} repins`);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Repin failed');
    } finally {
      setRepinning(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-8 text-center text-slate-500">
        <Loader2 className="w-5 h-5 animate-spin inline" /> Loading performance…
      </Card>
    );
  }

  const top = data?.top_pins || [];
  const boardScores = data?.board_scores || {};

  return (
    <div className="space-y-4" data-testid="pin-performance-tab">
      <div className="flex gap-2 flex-wrap">
        <Button size="sm" onClick={sync} disabled={syncing} data-testid="pin-perf-sync">
          {syncing ? (
            <Loader2 className="w-4 h-4 animate-spin mr-1" />
          ) : (
            <RefreshCw className="w-4 h-4 mr-1" />
          )}
          Sync from Pinterest
        </Button>
        <Button size="sm" variant="outline" onClick={repin} disabled={repinning} data-testid="pin-perf-repin">
          {repinning ? (
            <Loader2 className="w-4 h-4 animate-spin mr-1" />
          ) : (
            <RotateCw className="w-4 h-4 mr-1" />
          )}
          Run repin scheduler
        </Button>
      </div>

      {top.length === 0 && Object.keys(boardScores).length === 0 ? (
        <Card className="p-8 text-center text-slate-500">
          <p className="text-sm font-semibold">No performance data yet</p>
          <p className="text-xs mt-1">
            This dashboard populates after Pinterest is connected and the daily 04:15 BST sync
            runs. You can also click <strong>Sync from Pinterest</strong> above to trigger it
            manually.
          </p>
        </Card>
      ) : (
        <>
          {Object.keys(boardScores).length > 0 && (
            <div>
              <h3 className="text-sm font-bold text-slate-700 mb-2">
                Board engagement (clicks per pin, last 30d)
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {Object.entries(boardScores)
                  .sort(([, a], [, b]) => b - a)
                  .map(([slug, score]) => (
                    <Card key={slug} className="p-3" data-testid={`board-score-${slug}`}>
                      <div className="text-xs font-semibold text-slate-700 truncate">
                        {slug}
                      </div>
                      <div className="text-xl font-bold font-mono text-emerald-700">
                        {score.toFixed(1)}
                      </div>
                      <div className="text-[10px] text-slate-500">avg clicks/pin</div>
                    </Card>
                  ))}
              </div>
            </div>
          )}

          {top.length > 0 && (
            <div>
              <h3 className="text-sm font-bold text-slate-700 mb-2">
                Top performing pins
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {top.map((p) => (
                  <Card key={p.id} className="overflow-hidden" data-testid={`top-pin-${p.id}`}>
                    <div className="aspect-[3/4] bg-slate-100">
                      <img
                        src={p.image_url}
                        alt={p.title}
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                    </div>
                    <div className="p-3 space-y-1">
                      <div className="font-bold text-sm line-clamp-2">{p.title}</div>
                      <div className="text-[10px] text-slate-500">{p.board_name}</div>
                      <div className="grid grid-cols-3 gap-1 text-center mt-2 text-xs">
                        <div className="bg-emerald-50 rounded px-1 py-1">
                          <div className="font-bold text-emerald-900">
                            {p.performance?.clicks || 0}
                          </div>
                          <div className="text-[9px] text-emerald-700">clicks</div>
                        </div>
                        <div className="bg-pink-50 rounded px-1 py-1">
                          <div className="font-bold text-pink-900">
                            {p.performance?.saves || 0}
                          </div>
                          <div className="text-[9px] text-pink-700">saves</div>
                        </div>
                        <div className="bg-slate-100 rounded px-1 py-1">
                          <div className="font-bold text-slate-700">
                            {p.performance?.impressions || 0}
                          </div>
                          <div className="text-[9px] text-slate-500">imps</div>
                        </div>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

const LifestyleRendersTab = ({ headers }) => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(
        `${API_URL}/api/admin/pinterest/visual/lifestyle-renders?limit=60`,
        headers,
      );
      setRows(r.data.rows || []);
    } catch (e) {
      // Non-fatal
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => {
    load();
  }, [load]);

  const runBatch = async () => {
    setRunning(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/pinterest/visual/lifestyle-renders/run-batch?batch_size=3`,
        {},
        headers,
      );
      if (r.data.reason) {
        toast.error(`Render: ${r.data.reason}`);
      } else {
        toast.success(
          `Rendered ${r.data.rendered || 0} (${r.data.failed || 0} failed)`,
        );
      }
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Batch failed');
    } finally {
      setRunning(false);
    }
  };

  const counts = rows.reduce(
    (acc, r) => ({ ...acc, [r.status]: (acc[r.status] || 0) + 1 }),
    {},
  );

  return (
    <div className="space-y-3" data-testid="pin-lifestyle-tab">
      <p className="text-sm text-slate-600">
        Tier-2 fallback: when a product has no real lifestyle photo, we ask Nano Banana to render
        one. Renders run automatically every 3h in batches of 3 (~£0.04 each). Click below to run a
        batch on demand.
      </p>
      <div className="flex flex-wrap gap-2 items-center">
        <Button size="sm" onClick={runBatch} disabled={running} data-testid="pin-lifestyle-run-batch">
          {running ? (
            <Loader2 className="w-4 h-4 animate-spin mr-1" />
          ) : (
            <Zap className="w-4 h-4 mr-1" />
          )}
          Run batch (3 renders)
        </Button>
        <span className="text-xs text-slate-500">
          {Object.entries(counts)
            .map(([k, v]) => `${v} ${k}`)
            .join(' · ') || 'No renders yet'}
        </span>
      </div>
      {loading ? (
        <Card className="p-8 text-center text-slate-500">
          <Loader2 className="w-5 h-5 animate-spin inline" /> Loading…
        </Card>
      ) : rows.length === 0 ? (
        <Card className="p-8 text-center text-slate-500">
          <p className="text-sm">No lifestyle renders yet.</p>
          <p className="text-xs mt-1">
            Renders are queued automatically when the candidate generator finds a product with
            only a cutout image.
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {rows.map((r) => (
            <Card key={r.id} className="overflow-hidden">
              <div className="aspect-[3/4] bg-slate-100 overflow-hidden">
                {r.image_url ? (
                  <img
                    src={r.image_url}
                    alt={r.product_name}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-400 text-xs">
                    {r.status}
                  </div>
                )}
              </div>
              <div className="p-2 space-y-0.5">
                <div className="text-xs font-bold truncate">{r.product_name}</div>
                <div className="text-[10px] text-slate-500 truncate">
                  {r.status} · {r.product_slug}
                </div>
                {r.error && (
                  <div className="text-[10px] text-rose-700 line-clamp-2">{r.error}</div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default PinterestQueuePage;
