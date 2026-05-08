/**
 * Google Business Profile — admin connect + reviews + insights panel.
 *
 * Mirrors the SEO Command Centre's "Google Search Console" panel UX:
 *   - Disconnected → green "Connect Google Business Profile" button
 *   - Connected    → list locations, pick one, show reviews + insights
 *
 * IMPORTANT: GBP API requires Google to allowlist the GCP project
 * before any read endpoints work (typically 3-14 days). The backend
 * surfaces a friendly 503 when that's the case; we render a banner.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, RefreshCw, Star, Phone, MapPin, ExternalLink, MessageSquare,
  TrendingUp, MousePointerClick, Globe, Eye, AlertCircle, CheckCircle2,
  Building2, Loader2, Unlink,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import { MetricInfoTooltip } from '../../components/admin/MetricInfoTooltip';

const API = process.env.REACT_APP_BACKEND_URL || '';

const GBP_EXPLAINERS = {
  reviews: {
    title: 'Google reviews',
    what: 'Customer-submitted star ratings and comments tied to your Google Business Profile. Visible on Google Search and Maps the moment they\'re posted.',
    why: 'Reviews are the highest-trust signal in local search. A profile with 50+ reviews and a 4.5+ average wins clicks against competitors with fewer or lower-rated reviews — even when the competitor ranks higher.',
    good: '4.5★ or above with steady fresh reviews each month. A 5.0★ with only 3 reviews looks fake; a 4.6★ with 200 looks credible.',
  },
  rating_avg: {
    title: 'Average rating',
    what: 'The mean star rating across every review, exactly as Google displays it next to your business name.',
    why: 'Below 4.0★ Google often de-prioritises a business in the local 3-pack. Each 0.1★ improvement raises CTR by an estimated 2-5% in competitive local categories.',
  },
  calls: {
    title: 'Calls (from Google)',
    what: 'Times someone tapped the phone number on your Business Profile in Google Search or Maps in the window. These are people actively looking to talk to a human.',
    why: 'Phone calls have the highest intent-to-buy of any digital signal — typically converting at 30-50% to a sale on tile/stone.',
  },
  direction_requests: {
    title: 'Direction requests',
    what: 'Times someone tapped "Directions" to your shop on Google Maps. These are visitors who decided to drive in.',
    why: 'A leading indicator of in-shop revenue. Track week-on-week — if directions rise but footfall doesn\'t, your front-of-shop messaging is leaking sales.',
  },
  website_clicks: {
    title: 'Website clicks',
    what: 'Times someone clicked the website link on your Google Business Profile.',
    why: 'These are pre-qualified visitors — they searched for you, saw your profile, AND chose your site over a phone call or directions. Conversion rate on this segment is typically 2-3× site average.',
  },
  impressions: {
    title: 'Profile impressions',
    what: 'How many times your profile appeared in Google Search or Maps — both for branded searches ("Tile Station Maidstone") and discovery searches ("tile shops near me").',
    why: 'Tracks the size of your local audience. A flat impression count + rising clicks means your profile is converting better; falling impressions means a competitor is out-ranking you.',
  },
};

const StarRow = ({ rating }) => {
  const filled = Math.round(rating || 0);
  return (
    <div className="inline-flex items-center gap-0.5" data-testid="gbp-star-row">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          className={`w-4 h-4 ${i <= filled ? 'text-amber-400 fill-amber-400' : 'text-slate-300'}`}
        />
      ))}
    </div>
  );
};

const InsightCard = ({ title, value, icon: Icon, color, explainerKey }) => (
  <Card className="border-slate-200">
    <CardContent className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide flex items-center">
            <span>{title}</span>
            <MetricInfoTooltip explainer={GBP_EXPLAINERS[explainerKey]} side="top" align="start" />
          </p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
        </div>
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </CardContent>
  </Card>
);

export default function GoogleBusinessProfile() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [statusLoading, setStatusLoading] = useState(true);
  const [status, setStatus] = useState({ connected: false, configured: false });
  const [locations, setLocations] = useState([]);
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [reviews, setReviews] = useState(null);
  const [insights, setInsights] = useState(null);
  const [busy, setBusy] = useState(false);
  const [allowlistError, setAllowlistError] = useState(null);

  // Read auth token (we use the same key the rest of the admin uses).
  const token = useMemo(() => localStorage.getItem('token') || '', []);

  const authedFetch = useCallback(async (path, opts = {}) => {
    const res = await fetch(`${API}${path}`, {
      ...opts,
      headers: {
        'Content-Type': 'application/json',
        ...(opts.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    return res;
  }, [token]);

  const fetchStatus = useCallback(async () => {
    setStatusLoading(true);
    try {
      const res = await authedFetch('/api/admin/gbp/status');
      const data = await res.json();
      setStatus(data);
      if (data.connected) {
        await fetchLocations();
      }
    } catch (e) {
      console.error('GBP status error', e);
    } finally {
      setStatusLoading(false);
    }
  }, [authedFetch]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchLocations = useCallback(async () => {
    setBusy(true);
    setAllowlistError(null);
    try {
      const res = await authedFetch('/api/admin/gbp/locations');
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 503 && (data?.detail || '').toLowerCase().includes('allowlist') ||
            res.status === 503 && (data?.detail || '').toLowerCase().includes('approved')) {
          setAllowlistError(data.detail);
        } else {
          toast.error(data.detail || 'Could not load locations');
        }
        setLocations([]);
        return;
      }
      setLocations(data.locations || []);
      if ((data.locations || []).length && !selectedLocation) {
        setSelectedLocation(data.locations[0]);
      }
    } catch (e) {
      toast.error(e.message || 'Locations request failed');
    } finally {
      setBusy(false);
    }
  }, [authedFetch, selectedLocation]);

  const fetchReviewsAndInsights = useCallback(async (loc) => {
    if (!loc?.id) return;
    setBusy(true);
    try {
      const [rRes, iRes] = await Promise.all([
        authedFetch(`/api/admin/gbp/reviews?location_id=${encodeURIComponent(loc.id)}&page_size=20`),
        authedFetch(`/api/admin/gbp/insights?location_id=${encodeURIComponent(loc.id)}&days=30`),
      ]);
      if (rRes.ok) setReviews(await rRes.json()); else setReviews(null);
      if (iRes.ok) setInsights(await iRes.json()); else setInsights(null);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }, [authedFetch]);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  useEffect(() => {
    if (selectedLocation) fetchReviewsAndInsights(selectedLocation);
  }, [selectedLocation, fetchReviewsAndInsights]);

  // Pick up callback flags (?gbp=connected&email=xxx) from the OAuth roundtrip.
  useEffect(() => {
    const flag = searchParams.get('gbp');
    if (flag === 'connected') {
      toast.success('Google Business Profile connected!');
      const next = new URLSearchParams(searchParams);
      next.delete('gbp'); next.delete('email');
      setSearchParams(next, { replace: true });
      fetchStatus();
    } else if (flag === 'error') {
      toast.error(`Google connect failed: ${searchParams.get('reason') || 'unknown'}`);
      const next = new URLSearchParams(searchParams);
      next.delete('gbp'); next.delete('reason');
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams, fetchStatus]);

  const handleConnect = async () => {
    try {
      const res = await authedFetch('/api/admin/gbp/connect?return_to=/admin/gbp');
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not start connect flow');
      window.location.href = data.authorization_url;
    } catch (e) {
      toast.error(e.message);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('Disconnect Google Business Profile? You\'ll need to re-authorise to see reviews + insights again.')) return;
    try {
      const res = await authedFetch('/api/admin/gbp/disconnect', { method: 'POST' });
      if (res.ok) {
        toast.success('Disconnected');
        setStatus({ connected: false, configured: status.configured });
        setLocations([]); setReviews(null); setInsights(null); setSelectedLocation(null);
      }
    } catch (e) {
      toast.error(e.message);
    }
  };

  if (statusLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-2" />
          <p className="text-slate-500">Loading Google Business Profile…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-10">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/admin/seo')}
              className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
              data-testid="gbp-back-btn"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <div className="bg-blue-100 p-2 rounded-lg">
                <Building2 className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">Google Business Profile</h1>
                <p className="text-sm text-slate-500">
                  Reviews, ratings & local-search performance — straight from Google.
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {status.connected && (
              <Button variant="outline" onClick={() => fetchReviewsAndInsights(selectedLocation)} disabled={busy} data-testid="gbp-refresh-btn">
                <RefreshCw className={`w-4 h-4 mr-2 ${busy ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            )}
            {status.connected && (
              <Button variant="outline" onClick={handleDisconnect} data-testid="gbp-disconnect-btn">
                <Unlink className="w-4 h-4 mr-2" />
                Disconnect
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6 space-y-6">

        {!status.configured && (
          <Card className="border-amber-300 bg-amber-50">
            <CardContent className="p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5" />
              <div className="text-sm">
                <p className="font-semibold text-amber-900">Backend not configured.</p>
                <p className="text-amber-800">Set GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET + GBP_OAUTH_REDIRECT_URI in the backend env to enable Business Profile access. (You can reuse the same OAuth client as Google Search Console.)</p>
              </div>
            </CardContent>
          </Card>
        )}

        {!status.connected && status.configured && (
          <Card className="border-blue-200 bg-gradient-to-br from-blue-50 to-white">
            <CardContent className="p-8 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-100 mb-4">
                <Building2 className="w-8 h-8 text-blue-600" />
              </div>
              <h2 className="text-2xl font-bold text-slate-900">Connect your Google Business Profile</h2>
              <p className="mt-2 text-slate-600 max-w-xl mx-auto">
                Pull live reviews, ratings, profile views, calls, direction requests and website clicks
                directly from Google — no copy-pasting, no third-party trackers.
              </p>
              <Button
                onClick={handleConnect}
                size="lg"
                className="mt-6 bg-blue-600 hover:bg-blue-700"
                data-testid="gbp-connect-btn"
              >
                <Building2 className="w-5 h-5 mr-2" />
                Connect Google Business Profile
              </Button>
              <p className="mt-4 text-xs text-slate-500">
                ⓘ The Google Business Profile API requires your Google Cloud project to be approved.{' '}
                <a className="underline" href="https://support.google.com/business/contact/api_default" target="_blank" rel="noreferrer">
                  Apply here
                </a>{' '}
                if you haven't already — approval typically takes 3-14 days.
              </p>
            </CardContent>
          </Card>
        )}

        {status.connected && (
          <Card className="border-emerald-200 bg-emerald-50">
            <CardContent className="p-4 flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 mt-0.5" />
              <div className="text-sm">
                <p className="font-semibold text-emerald-900">
                  Connected as <span className="font-mono">{status.google_account_email || 'Google account'}</span>
                </p>
                <p className="text-emerald-800">
                  Last refreshed {status.last_refreshed_at ? new Date(status.last_refreshed_at).toLocaleString('en-GB') : '—'}.
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {allowlistError && (
          <Card className="border-amber-300 bg-amber-50" data-testid="gbp-allowlist-banner">
            <CardContent className="p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5" />
              <div className="text-sm">
                <p className="font-semibold text-amber-900">Awaiting Google approval</p>
                <p className="text-amber-800">{allowlistError}</p>
              </div>
            </CardContent>
          </Card>
        )}

        {status.connected && locations.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <MapPin className="w-5 h-5 text-blue-600" /> Locations
              </CardTitle>
              <CardDescription>Pick a location to see its reviews + last-30-day performance.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {locations.map((loc) => (
                  <button
                    key={loc.id}
                    onClick={() => setSelectedLocation(loc)}
                    className={`text-left border rounded-xl p-4 transition-all ${
                      selectedLocation?.id === loc.id
                        ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200'
                        : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                    }`}
                    data-testid={`gbp-location-${loc.id}`}
                  >
                    <p className="font-semibold text-slate-900">{loc.title || '(unnamed)'}</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {(loc.address_lines || []).join(', ')}{loc.locality ? `, ${loc.locality}` : ''}{loc.postal_code ? ` ${loc.postal_code}` : ''}
                    </p>
                    <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
                      {loc.primary_phone && <span className="inline-flex items-center gap-1"><Phone className="w-3 h-3" /> {loc.primary_phone}</span>}
                      {loc.website_uri && <span className="inline-flex items-center gap-1"><Globe className="w-3 h-3" /> website</span>}
                    </div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {status.connected && selectedLocation && insights && (
          <div>
            <h2 className="text-lg font-semibold text-slate-900 mb-3 flex items-center gap-2">
              Last 30 days — {selectedLocation.title}
              <span className="text-xs text-slate-500 font-normal">({insights.start_date} → {insights.end_date})</span>
            </h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <InsightCard title="Profile views" value={insights.totals.impressions_total.toLocaleString('en-GB')} icon={Eye} color="bg-blue-100 text-blue-600" explainerKey="impressions" />
              <InsightCard title="Calls" value={insights.totals.calls.toLocaleString('en-GB')} icon={Phone} color="bg-emerald-100 text-emerald-600" explainerKey="calls" />
              <InsightCard title="Directions" value={insights.totals.direction_requests.toLocaleString('en-GB')} icon={MapPin} color="bg-purple-100 text-purple-600" explainerKey="direction_requests" />
              <InsightCard title="Website clicks" value={insights.totals.website_clicks.toLocaleString('en-GB')} icon={MousePointerClick} color="bg-amber-100 text-amber-600" explainerKey="website_clicks" />
            </div>
          </div>
        )}

        {status.connected && selectedLocation && reviews && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-lg flex items-center gap-2">
                  <MessageSquare className="w-5 h-5 text-amber-500" />
                  Reviews
                  <MetricInfoTooltip explainer={GBP_EXPLAINERS.reviews} side="top" align="start" />
                </CardTitle>
                <CardDescription>
                  {reviews.total_count?.toLocaleString('en-GB') || 0} total reviews
                  {reviews.average_rating ? ` · ${(+reviews.average_rating).toFixed(1)}★ average` : ''}
                </CardDescription>
              </div>
              <a
                href={selectedLocation.place_uri || '#'}
                target="_blank"
                rel="noreferrer"
                className={`text-sm inline-flex items-center gap-1 ${selectedLocation.place_uri ? 'text-blue-600 hover:underline' : 'text-slate-400 pointer-events-none'}`}
              >
                Reply on Google <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </CardHeader>
            <CardContent>
              {(reviews.reviews || []).length === 0 ? (
                <p className="text-sm text-slate-500 italic py-6 text-center">No reviews yet on this location.</p>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {(reviews.reviews || []).map((rv) => (
                    <li key={rv.id} className="py-4 flex gap-3" data-testid={`gbp-review-${rv.id}`}>
                      <div className="flex-shrink-0">
                        <div className="w-9 h-9 rounded-full bg-slate-200 flex items-center justify-center text-sm font-semibold text-slate-700">
                          {(rv.reviewer_name || '?').charAt(0).toUpperCase()}
                        </div>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <p className="font-semibold text-slate-900">{rv.reviewer_name}</p>
                          <span className="text-xs text-slate-500">{rv.created_at ? new Date(rv.created_at).toLocaleDateString('en-GB') : ''}</span>
                        </div>
                        <StarRow rating={rv.rating} />
                        {rv.comment && <p className="text-sm text-slate-700 mt-1 whitespace-pre-line">{rv.comment}</p>}
                        {rv.has_reply && (
                          <div className="mt-2 ml-2 pl-3 border-l-2 border-emerald-300 bg-emerald-50/50 py-1.5 px-2 rounded-r">
                            <p className="text-xs font-semibold text-emerald-700">Your reply</p>
                            <p className="text-sm text-slate-700 whitespace-pre-line">{rv.reply_text}</p>
                          </div>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        )}

      </div>
    </div>
  );
}
