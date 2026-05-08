import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Camera, ImagePlus, ChevronRight, Loader2, Flame } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Photography backlog audit. Lists installation-essential SKUs missing
 * product images, prioritising the ones currently surfaced in the FBT
 * cache (those embarrass us most — they show up as "No image" on real
 * customer-facing PDPs).
 */
export default function EssentialsNeedingPhotosCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
    axios.get(`${API_URL}/api/recommendations/admin/essentials-needing-photos?limit=20`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(res => { if (!cancelled) setData(res.data); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const items = data?.items || [];
  const totalMissing = data?.total_missing || 0;
  const inCacheMissing = data?.in_cache_missing || 0;
  const visible = expanded ? items : items.slice(0, 5);

  if (loading) {
    return (
      <Card className="border-orange-100 bg-orange-50/30">
        <CardContent className="p-5 flex items-center gap-2 text-sm text-gray-500">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading photography backlog…
        </CardContent>
      </Card>
    );
  }

  if (!data || totalMissing === 0) {
    return (
      <Card className="border-emerald-100 bg-emerald-50/40">
        <CardContent className="p-5 flex items-center gap-2 text-sm text-emerald-700" data-testid="essentials-photos-empty">
          <Camera className="w-4 h-4" /> All installation essentials have product photos. Nothing in the backlog right now.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-orange-200" data-testid="essentials-photos-card">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-start gap-3">
            <div className="p-2 bg-orange-100 rounded-lg">
              <Camera className="w-5 h-5 text-orange-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Essentials needing photos</h3>
              <p className="text-xs text-gray-500 mt-0.5">
                {totalMissing} essential{totalMissing === 1 ? '' : 's'} without a product image
                {inCacheMissing > 0 && (
                  <>
                    {' · '}
                    <span className="text-orange-700 font-medium" data-testid="essentials-photos-in-cache-count">
                      {inCacheMissing} surfaced on PDPs right now
                    </span>
                  </>
                )}
              </p>
            </div>
          </div>
        </div>

        <ul className="rounded-md border border-gray-200 divide-y divide-gray-100 bg-gray-50/40 mb-2" data-testid="essentials-photos-list">
          {visible.map((it) => (
            <li
              key={it.id}
              className="flex items-center justify-between gap-2 px-3 py-2 text-[13px] hover:bg-gray-50"
              data-testid={`essential-row-${it.id}`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <ImagePlus className="w-4 h-4 text-gray-400 shrink-0" />
                <div className="min-w-0">
                  <p className="font-medium text-gray-800 truncate">{it.display_name}</p>
                  <p className="text-[11px] text-gray-400 truncate">
                    {it.sku ? `SKU ${it.sku} · ` : ''}£{Number(it.price || 0).toFixed(2)}
                    {it.view_count > 0 && ` · ${it.view_count} view${it.view_count === 1 ? '' : 's'}`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                {it.in_fbt_cache && (
                  <span
                    className="inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded"
                    title="Currently appears in Frequently Bought Together on customer PDPs"
                    data-testid={`essential-badge-fbt-${it.id}`}
                  >
                    <Flame className="w-3 h-3" />
                    On PDPs
                  </span>
                )}
                <Link
                  to={`/admin/products/edit/${it.id}`}
                  className="inline-flex items-center gap-1 text-xs text-gray-700 hover:text-orange-700 px-1.5 py-0.5 rounded hover:bg-orange-50"
                  data-testid={`essential-edit-link-${it.id}`}
                >
                  Edit <ChevronRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </li>
          ))}
        </ul>

        {items.length > 5 && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setExpanded(v => !v)}
            className="text-xs text-gray-600 hover:text-gray-900 h-7"
            data-testid="essentials-photos-toggle"
          >
            {expanded ? 'Show fewer' : `Show all ${items.length}`}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
