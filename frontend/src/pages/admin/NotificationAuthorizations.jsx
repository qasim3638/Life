/**
 * Notification authorisations — Super-Admin only.
 *
 * Default: deny. No admin receives any of the 6 automated emails until
 * a super-admin toggles them on here. Useful for:
 *   - Onboarding a junior staff member without exposing P&L
 *   - Multi-shop scaling where each owner only wants their own deck
 *   - Audit trail (every change is stamped with the super-admin's email)
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Loader2, ShieldAlert, ShieldCheck, Crown, Mail, Save,
  AlertCircle,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Checkbox } from '../../components/ui/checkbox';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL || ''}/api`;

export default function NotificationAuthorizations() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [savingFor, setSavingFor] = useState(null); // email currently saving
  const [channels, setChannels] = useState([]);
  const [admins, setAdmins] = useState([]);

  const isSuperAdmin = user?.role === 'super_admin';

  const headers = useMemo(() => (token ? { Authorization: `Bearer ${token}` } : {}), [token]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [cRes, aRes] = await Promise.all([
        fetch(`${API}/admin/notification-prefs/channels`, { headers }),
        fetch(`${API}/admin/notification-prefs/admins`, { headers }),
      ]);
      if (!cRes.ok || !aRes.ok) throw new Error('Failed to load notification prefs');
      const cJson = await cRes.json();
      const aJson = await aRes.json();
      setChannels(cJson.channels || []);
      setAdmins(aJson.admins || []);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => { load(); }, [load]);

  const toggleChannel = async (email, channelId, nextValue) => {
    if (!isSuperAdmin) {
      toast.error('Only super-admins can change notification authorisations.');
      return;
    }
    // Optimistic update
    const prevAdmins = admins;
    const updated = admins.map((a) =>
      a.email === email
        ? { ...a, channels: { ...a.channels, [channelId]: nextValue } }
        : a
    );
    setAdmins(updated);
    setSavingFor(email);

    try {
      const target = updated.find((a) => a.email === email);
      const res = await fetch(`${API}/admin/notification-prefs/admin/${encodeURIComponent(email)}`, {
        method: 'PUT',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ channels: target.channels }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Save failed');
      // Refresh just this row's metadata (updated_by/updated_at)
      setAdmins((curr) => curr.map((a) =>
        a.email === email
          ? { ...a, updated_by: json.updated_by, updated_at: json.updated_at }
          : a
      ));
    } catch (e) {
      toast.error(e.message);
      setAdmins(prevAdmins); // rollback
    } finally {
      setSavingFor(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!isSuperAdmin) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <div className="max-w-3xl mx-auto">
          <Card className="border-amber-200 bg-amber-50">
            <CardContent className="p-6 flex items-start gap-3">
              <ShieldAlert className="w-6 h-6 text-amber-600 mt-0.5" />
              <div>
                <p className="font-semibold text-amber-900">Super-admin access required</p>
                <p className="text-sm text-amber-800 mt-1">
                  Notification authorisations contain board-level financial channels and are
                  restricted to super-admins. Ask a super-admin to grant or revoke access.
                </p>
                <Button className="mt-3" variant="outline" onClick={() => navigate('/admin/dashboard')}>
                  Back to dashboard
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-10">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate(-1)} className="p-2 hover:bg-slate-100 rounded-lg" data-testid="notif-perms-back-btn">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <div className="bg-purple-100 p-2 rounded-lg">
                <ShieldCheck className="w-6 h-6 text-purple-600" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">Notification authorisations</h1>
                <p className="text-sm text-slate-500">
                  Super-admin only · Default = deny · Toggle to opt admins in to specific email channels.
                </p>
              </div>
            </div>
          </div>
          <Badge className="bg-purple-100 text-purple-700 border-purple-200">
            <Crown className="w-3 h-3 mr-1" /> Super-admin
          </Badge>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6 space-y-6">

        <Card className="border-slate-200 bg-slate-50">
          <CardContent className="p-4 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-slate-600 mt-0.5" />
            <div className="text-sm text-slate-700">
              <p className="font-semibold mb-1">How this works</p>
              <p>
                <strong>Policy:</strong> super-admins (👑) receive every channel by default — they can opt out individually if needed.
                Everyone else receives <strong>nothing</strong> until you tick a box. Changes save automatically; the timestamp + your
                email are stamped for audit.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Mail className="w-5 h-5 text-blue-600" />
              Per-admin channel access
            </CardTitle>
            <CardDescription>{admins.length} admin{admins.length === 1 ? '' : 's'} · {channels.length} channels</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-slate-500 border-b">
                    <th className="pb-3 font-medium pr-4">Admin</th>
                    {channels.map((c) => (
                      <th key={c.id} className="pb-3 font-medium px-2 text-center min-w-[120px]" title={c.description}>
                        <div className="leading-tight">
                          <div className="font-semibold text-slate-700">{c.label}</div>
                          <div className="text-[10px] text-slate-400 font-normal mt-0.5">{c.cadence}</div>
                        </div>
                      </th>
                    ))}
                    <th className="pb-3 font-medium pl-2 text-right text-[10px]">Last changed</th>
                  </tr>
                </thead>
                <tbody>
                  {admins.map((a) => (
                    <tr key={a.email} className="border-b last:border-0 hover:bg-slate-50/50" data-testid={`notif-perms-row-${a.email}`}>
                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-2">
                          {a.role === 'super_admin' && <Crown className="w-3.5 h-3.5 text-purple-500 flex-shrink-0" />}
                          <div className="min-w-0">
                            <p className="font-medium text-slate-900 text-sm truncate">{a.name || a.email}</p>
                            <p className="text-xs text-slate-500 truncate">{a.email}</p>
                          </div>
                        </div>
                      </td>
                      {channels.map((c) => (
                        <td key={c.id} className="py-3 px-2 text-center">
                          <div className="flex justify-center">
                            <Checkbox
                              checked={!!a.channels?.[c.id]}
                              onCheckedChange={(v) => toggleChannel(a.email, c.id, !!v)}
                              disabled={savingFor === a.email}
                              data-testid={`notif-perms-toggle-${a.email}-${c.id}`}
                            />
                          </div>
                        </td>
                      ))}
                      <td className="py-3 pl-2 text-right text-[10px] text-slate-400 whitespace-nowrap">
                        {savingFor === a.email && (
                          <span className="inline-flex items-center gap-1 text-blue-600">
                            <Loader2 className="w-3 h-3 animate-spin" /> saving
                          </span>
                        )}
                        {savingFor !== a.email && a.updated_at && (
                          <>
                            {new Date(a.updated_at).toLocaleDateString('en-GB')}<br />
                            <span className="text-slate-300">by {(a.updated_by || '').split('@')[0]}</span>
                          </>
                        )}
                        {savingFor !== a.email && !a.updated_at && <span className="text-slate-300 italic">never</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
