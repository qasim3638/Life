import { useState, useEffect } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Cache to avoid refetching on every page
let cachedSettings = null;
let cacheTimestamp = 0;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

const DEFAULT_BADGES = {
  delivery: { title: 'Free Delivery', subtitle: 'Over £499', enabled: true },
  samples: { title: 'Free Samples', subtitle: 'Try before you buy', enabled: true },
  quality: { title: 'Quality Guaranteed', subtitle: 'Premium tiles only', enabled: true },
  secure: { title: 'Secure Payment', subtitle: '100% protected', enabled: true },
};

export function useTrustBadges() {
  const [badges, setBadges] = useState(cachedSettings || DEFAULT_BADGES);
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    const now = Date.now();
    if (cachedSettings && (now - cacheTimestamp) < CACHE_TTL) {
      setBadges(cachedSettings);
      return;
    }

    const fetchSettings = async () => {
      try {
        const res = await fetch(`${API_URL}/api/website-admin/collection-detail-settings`);
        if (res.ok) {
          const data = await res.json();
          const settings = data.settings || data;
          const tb = settings.trustBadges || {};
          
          setEnabled(tb.enabled !== false);
          
          const badgeList = tb.badges || [];
          const merged = { ...DEFAULT_BADGES };
          
          for (const b of badgeList) {
            if (b.id && merged[b.id]) {
              merged[b.id] = {
                title: b.title || merged[b.id].title,
                subtitle: b.subtitle || merged[b.id].subtitle,
                enabled: b.enabled !== false,
              };
            }
          }
          
          // Also check freeDeliveryThreshold from delivery settings
          const threshold = settings.deliveryEstimate?.freeDeliveryThreshold;
          if (threshold && !badgeList.find(b => b.id === 'delivery')?.subtitle) {
            merged.delivery.subtitle = `Over £${threshold}`;
          }

          cachedSettings = merged;
          cacheTimestamp = Date.now();
          setBadges(merged);
        }
      } catch (e) {
        // Use defaults on error
      }
    };

    fetchSettings();
  }, []);

  return { badges, enabled };
}

// Helper to get a specific badge value
export function getBadgeText(badges, id, field = 'title') {
  return badges?.[id]?.[field] || DEFAULT_BADGES[id]?.[field] || '';
}
