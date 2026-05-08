/**
 * UseMyLocationButton — opt-in GPS button for visitors. Renders inside the
 * Showrooms page so the consent prompt has a clear, sales-team-friendly
 * justification ("Find my nearest showroom"). Side-effect: posts the GPS
 * fix to /api/live-analytics/precise-location which upgrades the admin
 * Live Visitors row from "approximate ISP city" → "precise town/postcode".
 */
import React, { useState } from 'react';
import { MapPin, Loader2, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '../ui/button';
import { requestBrowserGeolocation } from '../../lib/preciseLocation';

export default function UseMyLocationButton() {
  const [state, setState] = useState('idle'); // idle | loading | done
  const [result, setResult] = useState(null);  // { town, postcode } when ok

  const handleClick = async () => {
    if (state !== 'idle') return;
    setState('loading');
    const r = await requestBrowserGeolocation();
    if (r && r.ok) {
      setResult({ town: r.town, postcode: r.postcode });
      setState('done');
      toast.success(`Located you near ${r.town}${r.postcode ? ` · ${r.postcode}` : ''}`);
    } else {
      setState('idle');
      const reasonMap = {
        permission_denied: "Location permission denied. You can still browse — we'll just use a coarse IP location.",
        unavailable: 'Could not get a precise location right now.',
        timeout: 'Location lookup timed out — please try again.',
        no_uk_match: "We couldn't match those coordinates to a UK postcode.",
        unsupported: "Your browser doesn't support precise location.",
        no_session: 'Could not identify your session.',
      };
      toast.error(reasonMap[r && r.reason] || 'Could not pinpoint your location.');
    }
  };

  return (
    <div className="text-center mt-4" data-testid="use-my-location-wrapper">
      <Button
        type="button"
        onClick={handleClick}
        variant="outline"
        size="sm"
        className="text-sm"
        disabled={state !== 'idle'}
        data-testid="use-my-location-btn"
      >
        {state === 'loading' && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
        {state === 'done' && <CheckCircle2 className="w-4 h-4 mr-2 text-emerald-600" />}
        {state === 'idle' && <MapPin className="w-4 h-4 mr-2" />}
        {state === 'done'
          ? `Located near ${result?.town || 'you'}`
          : state === 'loading'
            ? 'Locating you…'
            : 'Find my nearest showroom'}
      </Button>
      <p className="text-xs text-slate-500 mt-2">
        Uses your browser's location with permission — far more accurate than IP lookup.
      </p>
    </div>
  );
}
