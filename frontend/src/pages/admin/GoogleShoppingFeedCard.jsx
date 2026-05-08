/**
 * GoogleShoppingFeedCard
 * ──────────────────────
 * Surfaces the public Google Shopping feed URL so the admin can
 * paste it into Google Merchant Center. Also displays a live count
 * of products in the feed and a "Test feed" button that pings the
 * feed and reports back.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { ShoppingBag, Copy, ExternalLink, Loader2, CheckCircle } from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';

const FRONTEND_BASE = 'https://tilestation.co.uk';
const API_URL = process.env.REACT_APP_BACKEND_URL;

const GoogleShoppingFeedCard = () => {
  const [productCount, setProductCount] = useState(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  // Dev/preview hits the current backend; admin still sees the
  // production URL to copy/paste into Merchant Center.
  const feedUrl = `${API_URL}/api/feeds/google-shopping.xml`;
  const productionFeedUrl = `${FRONTEND_BASE}/api/feeds/google-shopping.xml`;

  const testFeed = useCallback(async () => {
    setLoading(true);
    try {
      // Hit the local feed (same backend) so we see the count from the
      // X-Product-Count response header — preview env, not prod.
      const r = await fetch(`${API_URL}/api/feeds/google-shopping.xml`, {
        method: 'HEAD',
      });
      const cnt = parseInt(r.headers.get('X-Product-Count') || '0', 10);
      setProductCount(cnt);
      if (cnt > 0) {
        toast.success(`Feed has ${cnt} products ready for Google`);
      } else {
        toast.error('Feed returned 0 products — check filtering');
      }
    } catch (e) {
      toast.error('Could not test feed: ' + (e.message || ''));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open && productCount === null) testFeed();
  }, [open, productCount, testFeed]);

  const copyUrl = () => {
    navigator.clipboard.writeText(productionFeedUrl);
    toast.success('Feed URL copied — paste it into Google Merchant Center');
  };

  if (!open) {
    return (
      <Card className="p-4 bg-blue-50/40 border-blue-200" data-testid="google-shopping-collapsed">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2 min-w-0">
            <ShoppingBag className="w-5 h-5 text-blue-700" />
            <div className="min-w-0">
              <div className="font-bold text-blue-950">Google Shopping (free listings)</div>
              <div className="text-xs text-blue-900/70">
                Get all 777 products into Google's free Shopping tab — 5 min one-off setup.
              </div>
            </div>
          </div>
          <Button
            size="sm"
            onClick={() => setOpen(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white"
            data-testid="google-shopping-open"
          >
            Setup
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden border-blue-200" data-testid="google-shopping-card">
      <div className="bg-gradient-to-br from-blue-700 to-indigo-800 text-white px-6 py-4">
        <div className="text-[10px] uppercase tracking-widest text-blue-200 font-semibold">
          Google Shopping — free product listings
        </div>
        <h3 className="text-xl font-bold mt-0.5 flex items-center gap-2">
          <ShoppingBag className="w-5 h-5" /> Merchant Center feed
        </h3>
      </div>
      <div className="p-5 space-y-4 text-sm text-slate-700">
        <div>
          <div className="text-xs font-bold text-slate-700 mb-1">Your feed URL</div>
          <div className="flex gap-2 items-stretch">
            <code className="flex-1 bg-slate-100 px-3 py-2 rounded text-xs font-mono break-all text-slate-900">
              {productionFeedUrl}
            </code>
            <Button
              size="sm"
              variant="outline"
              onClick={copyUrl}
              data-testid="google-shopping-copy"
            >
              <Copy className="w-4 h-4 mr-1" /> Copy
            </Button>
          </div>
        </div>

        <div>
          <div className="text-xs font-bold text-slate-700 mb-1">Feed health</div>
          {loading ? (
            <div className="flex items-center gap-2 text-slate-500">
              <Loader2 className="w-4 h-4 animate-spin" /> Counting products…
            </div>
          ) : productCount !== null ? (
            <div
              className={`flex items-center gap-2 font-bold ${
                productCount > 0 ? 'text-emerald-700' : 'text-amber-700'
              }`}
              data-testid="google-shopping-count"
            >
              <CheckCircle className="w-4 h-4" />
              {productCount} products ready for submission
            </div>
          ) : (
            <Button size="sm" variant="outline" onClick={testFeed}>
              Test feed
            </Button>
          )}
        </div>

        <div className="bg-blue-50 border-l-4 border-blue-300 pl-4 py-3 text-xs text-blue-900 space-y-1.5">
          <div className="font-bold">5-step setup at Google Merchant Center:</div>
          <ol className="list-decimal list-inside space-y-1">
            <li>
              Go to{' '}
              <a
                href="https://merchants.google.com"
                target="_blank"
                rel="noopener noreferrer"
                className="underline font-semibold"
              >
                merchants.google.com
              </a>
              {' '}— sign up free with your Google account
            </li>
            <li>
              Verify ownership of <code className="bg-white px-1 rounded">tilestation.co.uk</code>{' '}
              (DNS TXT record or HTML tag)
            </li>
            <li>Settings → Feeds → Add primary feed → "Scheduled fetch"</li>
            <li>
              Feed URL: paste the URL above. Frequency: Daily 04:00 UK time. Country: United
              Kingdom. Language: English
            </li>
            <li>Click "Fetch now" once — products go live in 24–72h after Google reviews</li>
          </ol>
        </div>

        <a
          href="https://merchants.google.com"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-sm text-blue-700 hover:underline font-semibold"
          data-testid="google-shopping-merchant-link"
        >
          Open Merchant Center <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </Card>
  );
};

export default GoogleShoppingFeedCard;
