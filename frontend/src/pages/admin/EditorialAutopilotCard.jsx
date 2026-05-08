/**
 * EditorialAutopilotCard
 *
 * Drop-in card for /admin/seo. Shows the autopilot status, lets the
 * admin pause/unpause + adjust monthly cap, and exposes a "Run now"
 * button (forces a run even when paused, e.g. for testing).
 *
 * Below the controls, lists the 10 most-recently-published articles
 * with their source competitor, primary keyword, and a delete
 * button. Each title links to the public /blog/<slug> page.
 *
 * Designed to be self-contained — fetches its own data, does not
 * leak any state to the parent.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Switch } from '../../components/ui/switch';
import {
  BookOpen, Sparkles, Loader2, RefreshCw, Trash2, ExternalLink,
  PauseCircle, PlayCircle, DollarSign, AlertTriangle,
  CheckCircle2, Clock,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const tok = () => `Bearer ${localStorage.getItem('token') || localStorage.getItem('access_token') || ''}`;


const STATUS_COPY = {
  never: { label: 'Never run', tone: 'amber' },
  ok: { label: 'Running cleanly', tone: 'emerald' },
  skipped_paused: { label: 'Skipped (paused)', tone: 'slate' },
  skipped_cap_reached: { label: 'Skipped (monthly cap reached)', tone: 'amber' },
  failed_harvest: { label: 'Failed at harvest', tone: 'red' },
  no_candidates: { label: 'No new topics found this run', tone: 'slate' },
  all_drafts_failed: { label: 'All drafts failed', tone: 'red' },
};


const EditorialAutopilotCard = () => {
  const [status, setStatus] = useState(null);
  const [articles, setArticles] = useState(null);
  const [busy, setBusy] = useState(false);
  const [running, setRunning] = useState(false);
  const [editingCap, setEditingCap] = useState(false);
  const [capDraft, setCapDraft] = useState('');

  const load = async () => {
    try {
      const [s, a] = await Promise.all([
        axios.get(`${API_URL}/api/admin/editorial-autopilot/status`, { headers: { Authorization: tok() } }),
        axios.get(`${API_URL}/api/admin/editorial-autopilot/articles?limit=10`, { headers: { Authorization: tok() } }),
      ]);
      setStatus(s.data);
      setArticles(a.data?.articles || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not load Editorial Autopilot');
    }
  };

  useEffect(() => { load(); }, []);

  const setPaused = async (paused) => {
    setBusy(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/editorial-autopilot/settings`,
        { paused },
        { headers: { Authorization: tok() } },
      );
      setStatus((prev) => ({ ...(prev || {}), ...r.data }));
      toast.success(paused ? 'Editorial Autopilot paused' : 'Editorial Autopilot resumed');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not update settings');
    } finally {
      setBusy(false);
    }
  };

  const saveCap = async () => {
    const n = parseFloat(capDraft);
    if (!Number.isFinite(n) || n < 1 || n > 1000) {
      toast.error('Cap must be between $1 and $1000');
      return;
    }
    setBusy(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/editorial-autopilot/settings`,
        { monthly_cap_usd: n },
        { headers: { Authorization: tok() } },
      );
      setStatus((prev) => ({ ...(prev || {}), ...r.data }));
      setEditingCap(false);
      toast.success(`Monthly cap set to $${n.toFixed(2)}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not update cap');
    } finally {
      setBusy(false);
    }
  };

  const runNow = async () => {
    if (!window.confirm(
      'Run the Editorial Autopilot right now?\n\n'
      + 'Will fetch competitor wins, draft up to ~3 articles via Claude, '
      + 'auto-publish them to /blog/, and email you a summary. '
      + 'Spend ~$0.60 per article from your Emergent LLM key. '
      + 'Takes 60-180 seconds — runs in the background, you can navigate away.\n\n'
      + 'You\'re overriding the schedule — manual runs work even while paused.',
    )) return;
    setRunning(true);
    try {
      // Kick — backend returns immediately, run continues in background.
      await axios.post(
        `${API_URL}/api/admin/editorial-autopilot/run-now`,
        {},
        { headers: { Authorization: tok() } },
      );
      toast.info('Run started — drafting articles in the background. This card will update when done.');
      // Poll /status until last_run_at advances past the timestamp we
      // captured before kicking the run. Cap at 4 minutes.
      const baselineLastRun = status?.last_run_at || null;
      const startTime = Date.now();
      while (Date.now() - startTime < 240_000) {
        await new Promise((res) => setTimeout(res, 6000));
        try {
          const s = await axios.get(`${API_URL}/api/admin/editorial-autopilot/status`, {
            headers: { Authorization: tok() },
          });
          if (s.data?.last_run_at && s.data.last_run_at !== baselineLastRun) {
            await load();
            const d = s.data;
            if (d.last_run_status === 'ok') {
              toast.success(`Published ${d.last_run_published || 0} new article${d.last_run_published === 1 ? '' : 's'} · spent $${d.spent_this_month_usd?.toFixed(2) || '0.00'}`);
            } else if (d.last_run_status === 'no_candidates') {
              toast.info('No new topics worth replicating this run — competitors had nothing fresh in the tile space.');
            } else if (d.last_run_status === 'all_drafts_failed') {
              toast.error('All Claude drafts failed validation — see error below the list');
            } else if (d.last_run_status === 'failed_harvest') {
              toast.error('Failed to fetch competitor data from Ahrefs — check API key');
            } else {
              toast.success('Run complete');
            }
            return;
          }
        } catch (_e) { /* keep polling */ }
      }
      toast.warning('Run is taking longer than expected — check back in a minute.');
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not start run');
    } finally {
      setRunning(false);
    }
  };

  const removeArticle = async (slug) => {
    if (!window.confirm(`Delete this article?\n\n"${slug}"\n\nIt'll disappear from /blog/ within seconds.`)) return;
    try {
      await axios.delete(
        `${API_URL}/api/admin/editorial-autopilot/articles/${slug}`,
        { headers: { Authorization: tok() } },
      );
      setArticles((prev) => (prev || []).filter((a) => a.slug !== slug));
      toast.success('Deleted');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Delete failed');
    }
  };

  if (!status) {
    return (
      <Card className="p-6 flex items-center gap-2 text-slate-500" data-testid="editorial-autopilot-loading">
        <Loader2 className="w-5 h-5 animate-spin" /> Loading Editorial Autopilot…
      </Card>
    );
  }

  const lastStatusMeta = STATUS_COPY[status.last_run_status] || { label: status.last_run_status, tone: 'slate' };
  const lastRunAt = status.last_run_at ? new Date(status.last_run_at) : null;
  const cap = status.monthly_cap_usd || 0;
  const spent = status.spent_this_month_usd || 0;
  const pct = cap > 0 ? Math.min(100, Math.round((spent / cap) * 100)) : 0;

  return (
    <Card className="overflow-hidden border-2 border-amber-300" data-testid="editorial-autopilot-card">
      <div className="bg-gradient-to-r from-amber-700 to-orange-800 text-white px-5 py-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <BookOpen className="w-6 h-6 text-yellow-200" />
            <div>
              <div className="text-xs uppercase tracking-widest opacity-80 font-semibold">Editorial Autopilot</div>
              <div className="text-lg font-bold">Competitor-driven blog articles · runs every Monday 07:00 BST</div>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Button
              size="sm"
              onClick={runNow}
              disabled={running}
              className="bg-yellow-400 hover:bg-yellow-300 text-amber-900 font-bold"
              data-testid="editorial-run-now-btn"
            >
              {running ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1.5" />}
              {running ? 'Running…' : 'Run now'}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={load}
              disabled={running}
              className="text-white hover:bg-white/10"
              data-testid="editorial-refresh-btn"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="p-5 space-y-5">
        {/* Top status row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-slate-50 rounded-lg p-3 border border-slate-200" data-testid="editorial-stat-status">
            <div className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Status</div>
            <div className={`text-sm font-bold mt-1 ${
              lastStatusMeta.tone === 'emerald' ? 'text-emerald-700' :
              lastStatusMeta.tone === 'red' ? 'text-red-700' :
              lastStatusMeta.tone === 'amber' ? 'text-amber-700' : 'text-slate-700'
            }`}>
              {lastStatusMeta.label}
            </div>
          </div>
          <div className="bg-slate-50 rounded-lg p-3 border border-slate-200" data-testid="editorial-stat-last-run">
            <div className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Last run</div>
            <div className="text-sm font-bold mt-1 text-slate-900">
              {lastRunAt ? lastRunAt.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : '—'}
              {lastRunAt && (
                <span className="text-xs text-slate-500 ml-1.5">
                  {lastRunAt.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </div>
          </div>
          <div className="bg-slate-50 rounded-lg p-3 border border-slate-200" data-testid="editorial-stat-published">
            <div className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Last run published</div>
            <div className="text-sm font-bold mt-1 text-slate-900">{status.last_run_published || 0}</div>
          </div>
          <div className="bg-slate-50 rounded-lg p-3 border border-slate-200" data-testid="editorial-stat-spend">
            <div className="text-[10px] uppercase tracking-widest text-slate-500 font-bold flex items-center gap-1">
              <DollarSign className="w-3 h-3" /> This month
            </div>
            <div className="text-sm font-bold mt-1 text-slate-900">
              ${spent.toFixed(2)} / ${cap.toFixed(2)}
            </div>
            <div className="h-1 bg-slate-200 rounded-full mt-1.5 overflow-hidden">
              <div
                className={`h-full transition-all ${pct >= 100 ? 'bg-red-600' : pct >= 80 ? 'bg-amber-500' : 'bg-emerald-500'}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        </div>

        {/* Pause + cap controls */}
        <div className="flex items-center justify-between gap-4 flex-wrap p-3 rounded-lg bg-slate-50 border border-slate-200">
          <label className="flex items-center gap-2 cursor-pointer">
            <Switch
              checked={!status.paused}
              onCheckedChange={(v) => setPaused(!v)}
              disabled={busy}
              data-testid="editorial-paused-toggle"
            />
            <span className="text-sm font-semibold text-slate-900">
              {status.paused ? (
                <span className="flex items-center gap-1 text-slate-600">
                  <PauseCircle className="w-4 h-4" /> Autopilot is PAUSED — will not auto-publish
                </span>
              ) : (
                <span className="flex items-center gap-1 text-emerald-700">
                  <PlayCircle className="w-4 h-4" /> Autopilot is ACTIVE — runs Monday 07:00 BST
                </span>
              )}
            </span>
          </label>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-600 font-semibold uppercase tracking-wider">Monthly cap</span>
            {editingCap ? (
              <>
                <span className="text-sm text-slate-500">$</span>
                <Input
                  type="number"
                  step="1"
                  min="1"
                  max="1000"
                  className="w-24 h-8 text-sm"
                  value={capDraft}
                  onChange={(e) => setCapDraft(e.target.value)}
                  data-testid="editorial-cap-input"
                />
                <Button size="sm" onClick={saveCap} disabled={busy} className="h-8" data-testid="editorial-cap-save">Save</Button>
                <Button size="sm" variant="ghost" onClick={() => setEditingCap(false)} className="h-8">Cancel</Button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => { setCapDraft(String(cap)); setEditingCap(true); }}
                className="text-sm font-bold text-amber-700 hover:text-amber-900 underline"
                data-testid="editorial-cap-edit"
              >
                ${cap.toFixed(0)}
              </button>
            )}
          </div>
        </div>

        {/* Recent articles */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" /> Recently published ({articles?.length || 0})
            </h3>
            {articles && articles.length > 0 && (
              <a
                href="/blog"
                target="_blank"
                rel="noreferrer"
                className="text-xs text-amber-700 hover:text-amber-900 font-semibold inline-flex items-center gap-1"
                data-testid="editorial-view-blog-link"
              >
                See public blog <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
          {(!articles || articles.length === 0) ? (
            <div
              className="text-center text-slate-500 text-sm border-2 border-dashed border-slate-200 rounded-lg p-8"
              data-testid="editorial-empty-state"
            >
              <Clock className="w-8 h-8 text-slate-300 mx-auto mb-2" />
              No articles published yet — the next scheduled run is Monday 07:00 BST, or click <strong>Run now</strong> above.
            </div>
          ) : (
            <ul className="divide-y divide-slate-100 border border-slate-200 rounded-lg" data-testid="editorial-articles-list">
              {articles.map((a) => (
                <li
                  key={a.slug}
                  className="flex items-start gap-3 p-3 hover:bg-slate-50"
                  data-testid={`editorial-article-${a.slug}`}
                >
                  <div className="flex-1 min-w-0">
                    <a
                      href={`/blog/${a.slug}`}
                      target="_blank"
                      rel="noreferrer"
                      className="font-semibold text-slate-900 hover:text-amber-700 truncate inline-flex items-center gap-1"
                    >
                      {a.title}
                      <ExternalLink className="w-3 h-3 text-slate-400" />
                    </a>
                    <div className="text-xs text-slate-500 mt-1 flex items-center gap-3 flex-wrap">
                      <span className="font-mono">/{a.slug}</span>
                      {a.primary_keyword && <span>· keyword: <em>{a.primary_keyword}</em></span>}
                      {a.source_competitor && (
                        <span>· beating <strong className="text-slate-700">{a.source_competitor}</strong></span>
                      )}
                      {a.published_at && (
                        <span>· {new Date(a.published_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}</span>
                      )}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeArticle(a.slug)}
                    className="p-1.5 text-slate-400 hover:text-red-600 rounded-md hover:bg-red-50"
                    title="Delete article"
                    data-testid={`editorial-delete-${a.slug}`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {status.last_run_error && (
          <div
            className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2 flex items-start gap-2"
            data-testid="editorial-last-error"
          >
            <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-bold">Last run error</div>
              <div className="font-mono">{status.last_run_error}</div>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};

export default EditorialAutopilotCard;
