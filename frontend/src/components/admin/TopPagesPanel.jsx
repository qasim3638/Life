/**
 * Top Pages Panel — leaderboard of most-visited storefront pages.
 * Excludes home / auth / admin / account / checkout / basket so what's
 * left is the real signal: which products & collections pull traffic.
 *
 * Mounted on /admin/live-visitors.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import {
  TrendingUp, RefreshCw, Loader2, ExternalLink, Eye, Users, Trophy,
} from 'lucide-react';
import { Button } from '../ui/button';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const RANGE_OPTIONS = [
  { label: '24h', days: 1 },
  { label: '7d',  days: 7 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
];

// Strip the host so /shop/x renders the same whether logged from
// preview / prod / a localhost session.
function shortPath(url) {
  if (!url) return '';
  try {
    const u = url.match(/^https?:\/\//) ? new URL(url) : null;
    return u ? u.pathname : url;
  } catch {
    return url;
  }
}

function rankColour(idx) {
  if (idx === 0) return 'text-amber-500';   // gold
  if (idx === 1) return 'text-gray-400';     // silver
  if (idx === 2) return 'text-orange-600';   // bronze
  return 'text-gray-300';
}

export default function TopPagesPanel() {
  const [data, setData] = useState({ pages: [], max_views: 0 });
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/website/top-pages`, {
        params: { days, limit: 15 },
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      setData(r.data || { pages: [], max_views: 0 });
    } catch {
      // silent
    } finally { setLoading(false); }
  }, [days]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const pages = data.pages || [];
  const max = Math.max(1, data.max_views || 1);

  return (
    <div
      className="bg-white border border-gray-200 rounded-xl overflow-hidden"
      data-testid="top-pages-panel"
    >
      <div className="px-5 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-600" />
          <h3 className="text-sm font-semibold text-gray-900">Top visited pages</h3>
          <span className="text-[10px] text-gray-400 font-normal">
            (excludes home, auth, admin, basket)
          </span>
        </div>
        <div className="flex items-center gap-1">
          <div className="flex items-center bg-white border border-gray-200 rounded-md p-0.5" data-testid="top-pages-range">
            {RANGE_OPTIONS.map(opt => (
              <button
                key={opt.days}
                type="button"
                onClick={() => setDays(opt.days)}
                className={`text-[11px] font-medium px-2 py-1 rounded transition-colors ${
                  days === opt.days ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <Button
            onClick={fetchData}
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            data-testid="top-pages-refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      <div data-testid="top-pages-list">
        {loading && pages.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-gray-400">
            <Loader2 className="w-4 h-4 animate-spin inline mr-1.5" /> Loading…
          </div>
        ) : pages.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-gray-500">
            No traffic data in the selected period.
          </div>
        ) : (
          <ol className="divide-y divide-gray-100">
            {pages.map((p, idx) => {
              const path = shortPath(p.url);
              const pct = (p.views / max) * 100;
              return (
                <li
                  key={`${p.url}-${idx}`}
                  className="px-4 py-2.5 hover:bg-gray-50 transition-colors"
                  data-testid={`top-pages-row-${idx}`}
                >
                  <div className="flex items-center gap-3">
                    <span className={`flex-shrink-0 inline-flex items-center justify-center w-6 ${rankColour(idx)}`}>
                      {idx < 3 ? <Trophy className="w-4 h-4" /> : (
                        <span className="text-xs font-semibold text-gray-400">{idx + 1}</span>
                      )}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <code className="font-mono text-[12px] text-gray-900 font-medium truncate">{path}</code>
                        <a
                          href={path}
                          target="_blank"
                          rel="noreferrer"
                          className="text-gray-300 hover:text-gray-600 flex-shrink-0"
                          onClick={(e) => e.stopPropagation()}
                          title="Open page"
                        >
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                      {p.title && p.title !== path && (
                        <p className="text-[10px] text-gray-500 truncate">{p.title}</p>
                      )}
                      {/* mini bar */}
                      <div className="mt-1.5 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-emerald-400 rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                    <div className="flex-shrink-0 text-right">
                      <div className="flex items-center gap-3 text-[11px] font-mono">
                        <span className="inline-flex items-center gap-1 text-gray-700" title="Views">
                          <Eye className="w-3 h-3" />
                          {p.views}
                        </span>
                        <span className="inline-flex items-center gap-1 text-gray-500" title="Unique visitors">
                          <Users className="w-3 h-3" />
                          {p.unique_visitors}
                        </span>
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </div>
  );
}
