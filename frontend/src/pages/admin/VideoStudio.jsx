/**
 * VideoStudio — Sora 2 video generation for social-media promos.
 *
 * Split out from MarketingStudio.jsx to keep the banner page light.
 * Pre-existing "AI Banners" flow on /admin/marketing-studio is untouched.
 *
 * Flow:
 *   1. Admin picks model/size/duration, writes a prompt
 *   2. Frontend fetches a live cost estimate via POST /cost-estimate
 *   3. POST /generate enqueues an async job (backend returns immediately)
 *   4. Jobs-in-progress strip polls /jobs?status=queued,running every 5s
 *   5. When a job flips to succeeded, the completed-videos grid refreshes
 *   6. Clicking a video opens a lightbox with inline playback + download
 */
import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Link, useSearchParams } from 'react-router-dom';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Textarea } from '../../components/ui/textarea';
import {
  Video, Sparkles, Film, Play, Download, X, Loader2, Trash2,
  Clock, Coins, DollarSign, AlertTriangle, ArrowLeft, Copy,
  CheckCircle2, XCircle, PauseCircle,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const tokenHdr = () => ({
  Authorization: `Bearer ${localStorage.getItem('token') || localStorage.getItem('access_token') || ''}`,
});

const DEFAULT_PROMPT = 'Slow 4-second landscape camera push-in across a luxurious bathroom with backlit Calacatta marble feature wall, soft morning light through linen curtains, subtle steam rising. Cinematic depth-of-field, magazine-quality colour grade. No text overlay.';


// ---------- Stats strip ----------

const StatTile = ({ icon, label, value, testid }) => (
  <Card className="p-4" data-testid={testid}>
    <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-slate-500 font-semibold">
      {icon} {label}
    </div>
    <div className="mt-1 text-2xl font-bold text-slate-900">{value}</div>
  </Card>
);


// ---------- Job progress card (in-flight) ----------

const STATUS_META = {
  queued:    { color: 'text-slate-600',   bg: 'bg-slate-50',   border: 'border-slate-200',   icon: Clock,        label: 'Queued' },
  running:   { color: 'text-indigo-700',  bg: 'bg-indigo-50',  border: 'border-indigo-200',  icon: Loader2,      label: 'Generating' },
  succeeded: { color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', icon: CheckCircle2, label: 'Ready' },
  failed:    { color: 'text-red-700',     bg: 'bg-red-50',     border: 'border-red-200',     icon: XCircle,      label: 'Failed' },
  cancelled: { color: 'text-slate-500',   bg: 'bg-slate-50',   border: 'border-slate-200',   icon: PauseCircle,  label: 'Cancelled' },
};

const JobRow = ({ job, onCancel }) => {
  const meta = STATUS_META[job.status] || STATUS_META.queued;
  const Icon = meta.icon;
  const spinning = job.status === 'running';
  return (
    <div
      className={`flex items-center gap-3 p-3 rounded-lg border ${meta.bg} ${meta.border}`}
      data-testid={`video-job-row-${job.id}`}
    >
      <div className={`${meta.color} flex-shrink-0`}>
        <Icon className={`w-5 h-5 ${spinning ? 'animate-spin' : ''}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-[10px] font-bold uppercase tracking-widest ${meta.color}`}>{meta.label}</span>
          <span className="text-[11px] text-slate-500 font-mono">{job.model} · {job.size} · {job.duration}s</span>
          <span className="text-[11px] text-slate-500">· est ${job.estimated_cost_usd?.toFixed(2)}</span>
        </div>
        <div className="text-sm text-slate-700 mt-0.5 truncate" title={job.prompt}>
          {job.prompt}
        </div>
        {job.status === 'failed' && job.error && (
          <div className="text-xs text-red-700 mt-1 font-mono truncate" title={job.error}>
            {job.error}
          </div>
        )}
        {spinning && (
          <div className="mt-2 h-1.5 bg-white rounded-full overflow-hidden border border-indigo-100">
            <div
              className="h-full bg-indigo-600 transition-all"
              style={{ width: `${Math.max(5, Math.min(100, job.progress || 0))}%` }}
            />
          </div>
        )}
        <div className="text-[11px] text-slate-500 mt-1">{job.status_message}</div>
      </div>
      {job.status === 'queued' && (
        <button
          type="button"
          onClick={() => onCancel(job.id)}
          className="text-xs text-slate-500 hover:text-red-700 font-semibold"
          data-testid={`video-job-cancel-${job.id}`}
        >
          Cancel
        </button>
      )}
    </div>
  );
};


// ---------- Video lightbox ----------

const VideoLightbox = ({ video, onClose }) => {
  if (!video) return null;
  const src = `${API}${video.video_url}`;
  const downloadVideo = async () => {
    const sep = src.includes('?') ? '&' : '?';
    const dlUrl = `${src}${sep}download=1`;
    try {
      const r = await fetch(dlUrl, { cache: 'no-store' });
      if (!r.ok) {
        toast.error(`Video missing from storage (HTTP ${r.status})`);
        return;
      }
      const blob = await r.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = `tilestation-video-${video.id}.mp4`;
      a.rel = 'noopener';
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 2000);
      toast.success('Download started');
    } catch (_e) {
      // Fallback — direct navigation
      window.location.href = dlUrl;
    }
  };
  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(video.prompt || '');
      toast.success('Prompt copied');
    } catch (_e) { toast.error('Copy failed'); }
  };
  return (
    <div
      className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
      data-testid="video-lightbox"
    >
      <div
        className="relative max-w-5xl w-full max-h-[92vh] flex flex-col bg-slate-950 rounded-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-slate-800">
          <div className="text-white text-sm font-semibold truncate flex-1">
            {video.model} · {video.size} · {video.duration_seconds}s · ${video.cost_usd?.toFixed(2) || '—'}
          </div>
          <button
            onClick={copyPrompt}
            className="text-slate-300 hover:text-white text-xs flex items-center gap-1 px-2 py-1 rounded hover:bg-slate-800"
            data-testid="video-lightbox-copy-prompt"
          >
            <Copy className="w-3 h-3" /> Copy prompt
          </button>
          <button
            onClick={downloadVideo}
            className="text-slate-300 hover:text-white text-xs flex items-center gap-1 px-2 py-1 rounded hover:bg-slate-800"
            data-testid="video-lightbox-download"
          >
            <Download className="w-3 h-3" /> Download
          </button>
          <button onClick={onClose} className="text-slate-300 hover:text-white p-1" data-testid="video-lightbox-close">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center bg-black overflow-hidden">
          <video
            src={src}
            controls
            autoPlay
            loop
            className="max-w-full max-h-[70vh]"
            data-testid="video-lightbox-player"
          />
        </div>
        {video.prompt && (
          <div className="px-4 py-3 text-xs text-slate-300 border-t border-slate-800 max-h-24 overflow-y-auto">
            <span className="text-slate-500 font-semibold uppercase tracking-wider mr-2">Prompt:</span>
            {video.prompt}
          </div>
        )}
      </div>
    </div>
  );
};


// ---------- Completed video card ----------

const VideoCard = ({ video, onDelete, onZoom }) => {
  const src = `${API}${video.video_url}`;
  return (
    <Card className="overflow-hidden group relative" data-testid={`video-card-${video.id}`}>
      <div
        className="relative bg-black cursor-zoom-in"
        onClick={() => onZoom(video)}
        data-testid={`video-card-zoom-${video.id}`}
      >
        <video
          src={src}
          className="w-full object-cover aspect-video bg-slate-900"
          muted
          preload="metadata"
        />
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition bg-black/30">
          <Play className="w-12 h-12 text-white" />
        </div>
      </div>
      <div className="p-3 space-y-1.5">
        <div className="text-xs text-slate-500 font-mono flex items-center gap-2">
          <span>{video.model}</span>
          <span>·</span>
          <span>{video.size}</span>
          <span>·</span>
          <span>{video.duration_seconds}s</span>
          {video.cost_usd != null && (
            <span className="ml-auto text-emerald-700 font-semibold">${video.cost_usd.toFixed(2)}</span>
          )}
        </div>
        <div className="text-xs text-slate-700 line-clamp-2 min-h-[2em]" title={video.prompt}>
          {video.prompt}
        </div>
        <div className="flex justify-between items-center gap-2 pt-1">
          <span className="text-[10px] text-slate-400">
            {video.created_at ? new Date(video.created_at).toLocaleDateString('en-GB') : ''}
          </span>
          <button
            type="button"
            onClick={() => onDelete(video)}
            className="text-xs text-slate-500 hover:text-red-700 flex items-center gap-0.5"
            data-testid={`video-card-delete-${video.id}`}
          >
            <Trash2 className="w-3 h-3" /> Delete
          </button>
        </div>
      </div>
    </Card>
  );
};


// ---------- Main page ----------

const VideoStudio = () => {
  const [searchParams] = useSearchParams();
  // Accept ?prompt=... & preset=vertical|widescreen|hd & model=... from
  // "Remix to video" links on other pages. This lets the Banners page
  // push a one-click "make a Reels version of this" button.
  const remixPrompt = searchParams.get('prompt');
  const remixPreset = searchParams.get('preset');
  const remixModel = searchParams.get('model');
  const remixAssetId = searchParams.get('source_asset_id');

  const [prompt, setPrompt] = useState(remixPrompt || DEFAULT_PROMPT);
  const [model, setModel] = useState(remixModel || 'sora-2');
  const [sizePreset, setSizePreset] = useState(remixPreset || 'hd');
  const [duration, setDuration] = useState(4);
  const [submitting, setSubmitting] = useState(false);

  const [catalogue, setCatalogue] = useState(null);
  const [stats, setStats] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [videos, setVideos] = useState([]);
  const [lightboxVideo, setLightboxVideo] = useState(null);

  const selectedSize = useMemo(() => {
    const match = (catalogue?.sizes || []).find((s) => s.id === sizePreset);
    return match?.size || '1280x720';
  }, [sizePreset, catalogue]);

  // If the picked preset requires a specific model (vertical/widescreen
  // need sora-2-pro — sora-2 only does landscape HD today), auto-upgrade
  // the model so the admin doesn't hit a validation error at submit.
  // Also runs once when the catalogue first loads so any URL-injected
  // preset (from the "Remix to video" deep-link) can upgrade the model
  // on first render — not just on a later radio click.
  useEffect(() => {
    if (!catalogue?.sizes) return;
    const preset = catalogue.sizes.find((s) => s.id === sizePreset);
    if (preset?.requires_model && preset.requires_model !== model) {
      setModel(preset.requires_model);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sizePreset, catalogue]);

  const estCost = useMemo(() => {
    if (!catalogue?.pricing) return null;
    const perSec = catalogue.pricing[model]?.per_second_usd;
    if (perSec == null) return null;
    return Number((perSec * duration).toFixed(2));
  }, [catalogue, model, duration]);

  const load = async () => {
    try {
      const [c, s, j, v] = await Promise.all([
        axios.get(`${API}/api/admin/marketing-studio/videos/catalogue`, { headers: tokenHdr() }),
        axios.get(`${API}/api/admin/marketing-studio/videos/stats`, { headers: tokenHdr() }),
        axios.get(`${API}/api/admin/marketing-studio/videos/jobs?status=queued,running,failed`, { headers: tokenHdr() }),
        axios.get(`${API}/api/admin/marketing-studio/videos/assets?limit=60`, { headers: tokenHdr() }),
      ]);
      setCatalogue(c.data);
      setStats(s.data);
      setJobs(j.data?.jobs || []);
      setVideos(v.data?.videos || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not load Video Studio');
    }
  };

  useEffect(() => { load(); }, []);

  // Poll only while there are in-flight jobs — no point spamming the
  // backend when everything's quiet.
  useEffect(() => {
    const needPoll = (jobs || []).some((j) => j.status === 'queued' || j.status === 'running');
    if (!needPoll) return undefined;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs.length, jobs.filter((j) => j.status === 'running').length]);

  const submit = async () => {
    if (prompt.trim().length < 10) {
      toast.error('Prompt is too short — describe what the video should look like');
      return;
    }
    setSubmitting(true);
    try {
      const r = await axios.post(
        `${API}/api/admin/marketing-studio/videos/generate`,
        { prompt, model, size: selectedSize, duration, source_asset_id: remixAssetId || undefined },
        { headers: tokenHdr() },
      );
      setJobs((prev) => [r.data.job, ...prev]);
      toast.success('Queued — you can carry on, this takes 2-5 min');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Queue failed');
    } finally {
      setSubmitting(false);
    }
  };

  const cancelJob = async (jobId) => {
    try {
      await axios.post(
        `${API}/api/admin/marketing-studio/videos/jobs/${jobId}/cancel`,
        {},
        { headers: tokenHdr() },
      );
      toast.success('Cancelled');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Cancel failed');
    }
  };

  const deleteVideo = async (video) => {
    if (!window.confirm(`Delete this video? This also removes it from storage.`)) return;
    try {
      await axios.delete(
        `${API}/api/admin/marketing-studio/videos/${video.id}`,
        { headers: tokenHdr() },
      );
      setVideos((prev) => prev.filter((v) => v.id !== video.id));
      toast.success('Deleted');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Delete failed');
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6" data-testid="video-studio-page">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <Link
            to="/admin/marketing-studio"
            className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1 mb-1"
            data-testid="video-studio-back-link"
          >
            <ArrowLeft className="w-3 h-3" /> Back to Marketing Studio
          </Link>
          <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-2">
            <Video className="w-7 h-7 text-indigo-600" /> Video Studio
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            AI-generated short videos for Reels, Shorts, and Pinterest — powered by OpenAI Sora 2.
          </p>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatTile icon={<Film className="w-4 h-4 text-indigo-600" />} label="Videos" value={stats.total_videos} testid="video-stat-total" />
          <StatTile icon={<Loader2 className="w-4 h-4 text-amber-600" />} label="In flight" value={stats.running_jobs + stats.queued_jobs} testid="video-stat-inflight" />
          <StatTile icon={<DollarSign className="w-4 h-4 text-emerald-600" />} label="Lifetime spend" value={`$${stats.lifetime_spend_usd?.toFixed(2) || '0.00'}`} testid="video-stat-spend" />
          <StatTile icon={<Clock className="w-4 h-4 text-slate-600" />} label="Seconds rendered" value={stats.lifetime_seconds} testid="video-stat-seconds" />
        </div>
      )}

      {/* Generate form */}
      <Card className="p-5">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="w-5 h-5 text-amber-500" />
          <h2 className="text-lg font-bold text-slate-900">Generate a new video</h2>
        </div>
        <Textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={5}
          className="w-full font-mono text-sm"
          placeholder="Describe the video you want — camera movement, lighting, subject, style…"
          data-testid="video-prompt-input"
        />

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
          {/* Model */}
          <div>
            <label className="block text-xs uppercase tracking-wider font-bold text-slate-600 mb-2">Model</label>
            <div className="flex flex-col gap-1.5" data-testid="video-model-group">
              {(catalogue?.models || ['sora-2', 'sora-2-pro']).map((m) => {
                const perSec = catalogue?.pricing?.[m]?.per_second_usd;
                const preset = (catalogue?.sizes || []).find((s) => s.id === sizePreset);
                const disabledByPreset = !!preset?.requires_model && preset.requires_model !== m;
                return (
                  <label
                    key={m}
                    className={`flex items-center gap-2 text-sm ${disabledByPreset ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
                  >
                    <input
                      type="radio"
                      name="video-model"
                      value={m}
                      checked={model === m}
                      onChange={() => setModel(m)}
                      disabled={disabledByPreset}
                      data-testid={`video-model-${m}`}
                      className="text-indigo-600 focus:ring-indigo-500"
                    />
                    <span className="font-mono">{m}</span>
                    {perSec != null && <span className="text-slate-400 text-xs">${perSec.toFixed(2)}/s</span>}
                    {disabledByPreset && <span className="text-[10px] text-amber-700">(aspect needs sora-2-pro)</span>}
                  </label>
                );
              })}
            </div>
          </div>

          {/* Size */}
          <div>
            <label className="block text-xs uppercase tracking-wider font-bold text-slate-600 mb-2">Aspect</label>
            <div className="flex flex-col gap-1.5" data-testid="video-size-group">
              {(catalogue?.sizes || []).map((s) => (
                <label key={s.id} className="flex items-center gap-2 cursor-pointer text-sm">
                  <input
                    type="radio"
                    name="video-size"
                    value={s.id}
                    checked={sizePreset === s.id}
                    onChange={() => setSizePreset(s.id)}
                    data-testid={`video-size-${s.id}`}
                    className="text-indigo-600 focus:ring-indigo-500"
                  />
                  <span className="text-slate-800">{s.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Duration */}
          <div>
            <label className="block text-xs uppercase tracking-wider font-bold text-slate-600 mb-2">Duration</label>
            <div className="flex gap-2" data-testid="video-duration-group">
              {(catalogue?.durations || [4, 8, 12]).map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDuration(d)}
                  className={`flex-1 py-2 rounded border text-sm font-semibold transition ${
                    duration === d
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white text-slate-700 border-slate-300 hover:border-indigo-400'
                  }`}
                  data-testid={`video-duration-${d}`}
                >
                  {d}s
                </button>
              ))}
            </div>
            <div className="mt-3 text-xs text-slate-600 flex items-center gap-1.5" data-testid="video-cost-estimate">
              <Coins className="w-4 h-4 text-amber-600" />
              <span>Est. cost: <strong>${estCost?.toFixed(2) ?? '—'}</strong> · takes ~{model === 'sora-2-pro' ? '4-5' : '2-3'} min</span>
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between gap-3 flex-wrap">
          <div className="text-xs text-slate-500 flex items-center gap-1.5">
            <AlertTriangle className="w-3 h-3 text-amber-500" />
            <span>Costs are charged to your Emergent LLM key balance.</span>
          </div>
          <Button
            onClick={submit}
            disabled={submitting || prompt.trim().length < 10}
            className="bg-indigo-600 hover:bg-indigo-700 text-white"
            data-testid="video-generate-btn"
          >
            {submitting ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1.5" />}
            {submitting ? 'Queuing…' : `Generate · $${estCost?.toFixed(2) ?? ''}`}
          </Button>
        </div>
      </Card>

      {/* Jobs in flight */}
      {jobs.length > 0 && (
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Loader2 className="w-5 h-5 text-indigo-600" /> In flight
            </h2>
            <span className="text-xs text-slate-500">{jobs.length} job{jobs.length === 1 ? '' : 's'}</span>
          </div>
          <div className="space-y-2" data-testid="video-jobs-list">
            {jobs.map((j) => <JobRow key={j.id} job={j} onCancel={cancelJob} />)}
          </div>
        </Card>
      )}

      {/* Videos grid */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Film className="w-5 h-5 text-slate-700" /> Videos ({videos.length})
          </h2>
        </div>
        {videos.length === 0 ? (
          <Card className="p-12 text-center text-slate-500 border-dashed" data-testid="video-empty-state">
            <Video className="w-10 h-10 mx-auto text-slate-300 mb-2" />
            <div className="font-semibold">No videos yet</div>
            <div className="text-xs mt-1">Your first Sora 2 render will appear here when the job finishes.</div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="video-grid">
            {videos.map((v) => (
              <VideoCard key={v.id} video={v} onDelete={deleteVideo} onZoom={setLightboxVideo} />
            ))}
          </div>
        )}
      </div>

      <VideoLightbox video={lightboxVideo} onClose={() => setLightboxVideo(null)} />
    </div>
  );
};

export default VideoStudio;
