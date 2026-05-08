/**
 * My subscriptions — read-only personal view.
 *
 * Mirrors the super-admin notification panel but scoped to the
 * current user. Purely informational: tells admins exactly which
 * automated emails they'll receive (or won't), with cadence + a
 * pointer to ask a super-admin if they need a change.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Loader2, BellRing, BellOff, ShieldCheck, Mail, Info,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL || ''}/api`;

export default function MySubscriptions() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  const headers = useMemo(() => (token ? { Authorization: `Bearer ${token}` } : {}), [token]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/admin/notification-prefs/me`, { headers });
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed to load');
      setData(await res.json());
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <p className="text-slate-500">Could not load subscriptions.</p>
      </div>
    );
  }

  const { channels = [], subscribed_count = 0, total_channels = 0, last_changed_at, last_changed_by } = data;
  const isSuperAdmin = user?.role === 'super_admin';

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-10">
        <div className="flex items-center justify-between max-w-4xl mx-auto">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate(-1)} className="p-2 hover:bg-slate-100 rounded-lg" data-testid="my-subs-back-btn">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <div className="bg-blue-100 p-2 rounded-lg">
                <BellRing className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">My subscriptions</h1>
                <p className="text-sm text-slate-500">Automated emails you'll receive — read-only.</p>
              </div>
            </div>
          </div>
          <Badge className="bg-slate-100 text-slate-700 border-slate-200">
            {subscribed_count} of {total_channels} active
          </Badge>
        </div>
      </div>

      <div className="max-w-4xl mx-auto p-6 space-y-6">

        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="p-4 flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-blue-900">
              <p className="font-semibold mb-1">Read-only view</p>
              <p>
                Notification subscriptions are managed centrally by super-admins to keep board-level financial
                emails on a tight need-to-know basis. If you'd like a change, ping a super-admin —
                {isSuperAdmin
                  ? <> you can also <button className="underline font-semibold ml-1" onClick={() => navigate('/admin/notification-permissions')} data-testid="my-subs-jump-admin-btn">manage these for the whole team →</button></>
                  : ' they can update it in seconds.'}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Mail className="w-5 h-5 text-slate-600" />
              {data.email}
            </CardTitle>
            <CardDescription>
              {last_changed_at ? (
                <>Last updated {new Date(last_changed_at).toLocaleDateString('en-GB')}{last_changed_by ? ` by ${last_changed_by}` : ''}</>
              ) : 'No changes yet — using deny-by-default.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="divide-y divide-slate-100" data-testid="my-subs-list">
              {channels.map((c) => (
                <li
                  key={c.id}
                  className="py-4 flex items-start gap-4"
                  data-testid={`my-subs-row-${c.id}`}
                >
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                      c.subscribed ? 'bg-emerald-100 text-emerald-600' : 'bg-slate-100 text-slate-400'
                    }`}
                  >
                    {c.subscribed ? <BellRing className="w-5 h-5" /> : <BellOff className="w-5 h-5" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold text-slate-900">{c.label}</p>
                      {c.subscribed ? (
                        <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200" data-testid={`my-subs-status-${c.id}`}>
                          Subscribed
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-slate-500 border-slate-300" data-testid={`my-subs-status-${c.id}`}>
                          Not subscribed
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-slate-600 mt-1">{c.description}</p>
                    <p className="text-xs text-slate-400 mt-1.5">⏱ {c.cadence}</p>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
