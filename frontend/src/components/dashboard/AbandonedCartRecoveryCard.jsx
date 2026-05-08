import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '../ui/card';
import { Sparkles, ArrowRight } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Tiny dashboard widget showing how much revenue the abandoned-cart
 * email sequence recovered THIS calendar month — at a glance.
 */
export default function AbandonedCartRecoveryCard() {
  const { token, user } = useAuth();
  const [data, setData] = useState(null);

  const isAdminish = ['super_admin', 'admin', 'manager'].includes(user?.role);

  useEffect(() => {
    if (!token || !isAdminish) return;
    let cancelled = false;
    axios.get(`${API}/abandoned-carts/stats`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(res => { if (!cancelled) setData(res.data?.recovered_this_month || null); })
      .catch(() => { /* silent — non-essential widget */ });
    return () => { cancelled = true; };
  }, [token, isAdminish]);

  if (!isAdminish || !data) return null;

  const value = Number(data.value || 0);
  const codes = Number(data.codes_used || 0);
  const count = Number(data.count || 0);

  return (
    <Card
      className="bg-gradient-to-br from-emerald-50 to-emerald-100/60 border-emerald-200 hover:shadow-md transition-shadow"
      data-testid="dashboard-abandoned-recovery-card"
    >
      <CardContent className="p-4">
        <Link to="/admin/abandoned-baskets" className="block group">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-md bg-emerald-600/10 flex items-center justify-center">
                  <Sparkles className="w-4 h-4 text-emerald-700" />
                </div>
                <p className="text-[11px] uppercase tracking-wider text-emerald-800/70">
                  Recovered • {data.month}
                </p>
              </div>
              <p className="text-2xl font-bold text-emerald-900 mt-2 tabular-nums">
                £{value.toFixed(2)}
              </p>
              <p className="text-xs text-emerald-700 mt-0.5">
                {count} basket{count === 1 ? '' : 's'}
                {codes > 0 && (
                  <span className="text-emerald-700/80"> &nbsp;•&nbsp; {codes} code{codes === 1 ? '' : 's'} used</span>
                )}
              </p>
            </div>
            <ArrowRight className="w-4 h-4 text-emerald-700 mt-1 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </Link>
      </CardContent>
    </Card>
  );
}
