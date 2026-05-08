/**
 * PinterestVisualEngineCard
 * ─────────────────────────
 * Compact summary card for /admin/seo with at-a-glance stats and a
 * link to the full /admin/pinterest-queue page.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { Sparkles, ChevronRight, Loader2, Zap, AlertTriangle } from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const token = () =>
  localStorage.getItem('token') || localStorage.getItem('access_token') || '';

const PinterestVisualEngineCard = () => {
  const nav = useNavigate();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(
        `${API_URL}/api/admin/pinterest/visual/queue/summary`,
        { headers: { Authorization: `Bearer ${token()}` } },
      );
      setSummary(r.data);
    } catch (e) {
      // Non-fatal
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <Card className="p-4 flex items-center gap-2 text-slate-500" data-testid="pin-engine-loading">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading visual engine…
      </Card>
    );
  }

  const pending = summary?.pending || 0;
  const approved = summary?.approved || 0;
  const posted = summary?.posted || 0;

  return (
    <Card
      className="overflow-hidden border-rose-200 hover:shadow-lg transition cursor-pointer"
      onClick={() => nav('/admin/pinterest-queue')}
      data-testid="pin-engine-card"
    >
      <div className="bg-gradient-to-br from-rose-700 via-rose-800 to-pink-900 text-white px-5 py-4">
        <div className="flex items-start justify-between flex-wrap gap-2">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-rose-200 font-semibold">
              Pinterest visual marketing engine
            </div>
            <h3 className="text-xl font-bold mt-0.5 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-yellow-300" /> Pin Queue
            </h3>
          </div>
          <Button
            size="sm"
            variant="ghost"
            className="text-white hover:bg-white/10"
            data-testid="pin-engine-open-queue"
          >
            Manage <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-px bg-rose-100">
        <Mini label="Pending review" value={pending} tone="amber" testid="pin-mini-pending" />
        <Mini label="Approved · queued" value={approved} tone="blue" testid="pin-mini-approved" />
        <Mini label="Posted live" value={posted} tone="emerald" testid="pin-mini-posted" />
      </div>

      <div className="p-4 text-xs text-slate-700 bg-rose-50/40">
        {pending > 0 ? (
          <div className="flex items-start gap-2 text-amber-900 font-semibold">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>
              <strong className="font-mono">{pending}</strong> Pin{pending !== 1 && 's'} waiting for
              your review. Tap <strong>Manage</strong> above to approve, edit or skip.
            </span>
          </div>
        ) : approved > 0 ? (
          <div className="flex items-start gap-2 text-blue-900">
            <Zap className="w-4 h-4 mt-0.5 shrink-0" />
            <span>
              <strong className="font-mono">{approved}</strong> Pin{approved !== 1 && 's'} drip-feeding
              to Pinterest at 90-min intervals. Nothing for you to do.
            </span>
          </div>
        ) : (
          <div className="flex items-start gap-2 text-slate-700">
            <Sparkles className="w-4 h-4 mt-0.5 shrink-0" />
            <span>
              Engine is ready. The first batch generates automatically tomorrow at 5am, or click{' '}
              <strong>Manage → Generate now</strong> to start immediately.
            </span>
          </div>
        )}
      </div>
    </Card>
  );
};

const Mini = ({ label, value, tone, testid }) => {
  const tones = {
    amber: 'bg-amber-50 text-amber-900',
    blue: 'bg-blue-50 text-blue-900',
    emerald: 'bg-emerald-50 text-emerald-900',
  };
  return (
    <div className={`p-3 ${tones[tone]}`} data-testid={testid}>
      <div className="text-[10px] uppercase tracking-wide font-semibold opacity-80">{label}</div>
      <div className="text-xl font-bold font-mono mt-0.5">{value}</div>
    </div>
  );
};

export default PinterestVisualEngineCard;
