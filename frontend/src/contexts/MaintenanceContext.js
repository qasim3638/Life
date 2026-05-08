import React, { createContext, useContext, useState, useEffect } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const DEFAULT_SITE = {
  enabled: false,
  headline: "We'll be back shortly",
  message: "Sorry for the inconvenience — we're making some quick improvements to the website. We'll be back online soon. Thanks for your patience.",
};

const MaintenanceContext = createContext({
  disabledRoutes: [],
  site: DEFAULT_SITE,
  loading: true,
  refresh: () => {},
});

export function MaintenanceProvider({ children }) {
  const [disabledRoutes, setDisabledRoutes] = useState([]);
  const [site, setSite] = useState(DEFAULT_SITE);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try {
      const [pagesRes, siteRes] = await Promise.all([
        fetch(`${API_URL}/api/website-admin/maintenance-pages/public`).then(r => r.ok ? r.json() : { pages: [] }).catch(() => ({ pages: [] })),
        fetch(`${API_URL}/api/website-admin/site-maintenance/public`).then(r => r.ok ? r.json() : DEFAULT_SITE).catch(() => DEFAULT_SITE),
      ]);
      setDisabledRoutes(pagesRes.pages?.map(p => p.route) || []);
      setSite({
        enabled: !!siteRes?.enabled,
        headline: siteRes?.headline || DEFAULT_SITE.headline,
        message: siteRes?.message || DEFAULT_SITE.message,
        scheduled_start: siteRes?.scheduled_start || null,
        scheduled_end: siteRes?.scheduled_end || null,
        auto_enabled: !!siteRes?.auto_enabled,
      });
    } catch (e) {
      console.error('Failed to fetch maintenance config:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  return (
    <MaintenanceContext.Provider value={{ disabledRoutes, site, loading, refresh }}>
      {children}
    </MaintenanceContext.Provider>
  );
}

export function useMaintenanceCheck() {
  return useContext(MaintenanceContext);
}

/**
 * Returns countdown state for the checkout/cart "Place Order" CTA when a
 * scheduled maintenance window is imminent (≤15 minutes away).
 *
 * Tiers:
 *   - >15 min away  → idle  (no UI)
 *   - 3-15 min away → warning (amber, CTA still active)
 *   - 0-2 min away  → blocking (rose, CTA replaced + disabled)
 *
 * Recomputes every 15s while the hook is mounted so the countdown stays fresh
 * without re-rendering the whole storefront.
 */
const WARNING_MS = 15 * 60 * 1000;
const BLOCKING_MS = 2 * 60 * 1000;

export function useCheckoutMaintenanceCountdown() {
  const { site } = useMaintenanceCheck();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 15_000);
    return () => clearInterval(id);
  }, []);

  const start = site?.scheduled_start ? new Date(site.scheduled_start).getTime() : null;
  const end = site?.scheduled_end ? new Date(site.scheduled_end).getTime() : null;

  if (!start || !end) return { active: false, blocking: false, minutes: null, severity: 'idle' };
  if (site?.enabled) return { active: false, blocking: false, minutes: null, severity: 'idle' };
  if (now >= end) return { active: false, blocking: false, minutes: null, severity: 'idle' };

  const msToStart = start - now;
  if (msToStart > WARNING_MS) {
    return { active: false, blocking: false, minutes: null, severity: 'idle' };
  }

  // Use Math.ceil so a 14m45s countdown still reads "15 mins" rather than skipping
  // straight to "14" — feels more honest to a customer mid-checkout.
  const minutes = Math.max(0, Math.ceil(msToStart / 60_000));
  const blocking = msToStart <= BLOCKING_MS;
  return {
    active: true,
    blocking,
    minutes,
    severity: blocking ? 'blocking' : 'warning',
    scheduledStart: site.scheduled_start,
    scheduledEnd: site.scheduled_end,
  };
}
