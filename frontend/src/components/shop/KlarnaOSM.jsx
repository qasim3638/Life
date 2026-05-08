/**
 * KlarnaOSM — Klarna On-Site Messaging widget
 *
 * Shows "From £X/mo with Klarna" on a product card or product detail page.
 * Fetches the admin's Klarna Client ID + enable flag from the public
 * checkout-settings endpoint and only renders when BOTH conditions are true:
 *   1. Admin has toggled klarna_osm_enabled = true in the admin panel
 *   2. klarna_client_id is non-empty
 *
 * Uses Klarna's free OSM library — no customer data is sent, only the
 * product price (in pence/gbp) and the Client ID.
 *
 * Docs: https://docs.klarna.com/on-site-messaging/
 *
 * Usage:
 *   <KlarnaOSM price={29.99} placement="credit-promotion-badge" />   // product card
 *   <KlarnaOSM price={29.99} placement="credit-promotion-standard" /> // PDP
 */
import { useEffect, useState } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Cache the fetched config across re-renders (the admin settings rarely change)
let _cachedConfig = null;
let _inflightPromise = null;

async function fetchKlarnaConfig() {
  if (_cachedConfig) return _cachedConfig;
  if (_inflightPromise) return _inflightPromise;
  _inflightPromise = (async () => {
    try {
      const res = await fetch(`${API_URL}/api/website-admin/public/checkout-settings`);
      if (!res.ok) return { enabled: false };
      const { settings } = await res.json();
      const p = settings?.payments || {};
      _cachedConfig = {
        enabled: !!p.klarna_osm_enabled && !!p.klarna_client_id,
        clientId: p.klarna_client_id || '',
      };
      return _cachedConfig;
    } catch {
      _cachedConfig = { enabled: false };
      return _cachedConfig;
    } finally {
      _inflightPromise = null;
    }
  })();
  return _inflightPromise;
}

// Script loader (loads the Klarna OSM library once per client ID)
const _loadedClientIds = new Set();
function loadKlarnaLib(clientId) {
  if (_loadedClientIds.has(clientId)) return Promise.resolve();
  _loadedClientIds.add(clientId);
  return new Promise((resolve) => {
    const s = document.createElement('script');
    s.async = true;
    s.src = `https://eu-library.klarnaservices.com/lib.js`;
    s.setAttribute('data-client-id', clientId);
    s.onload = () => resolve();
    s.onerror = () => resolve(); // silent — widget just won't render
    document.head.appendChild(s);
  });
}

export default function KlarnaOSM({
  price,
  placement = 'credit-promotion-badge',
  purchaseCountry = 'GB',
  locale = 'en-GB',
  className = '',
}) {
  const [ready, setReady] = useState(false);
  const [config, setConfig] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchKlarnaConfig().then(async (cfg) => {
      if (cancelled || !cfg.enabled) return;
      setConfig(cfg);
      await loadKlarnaLib(cfg.clientId);
      if (!cancelled) setReady(true);
    });
    return () => { cancelled = true; };
  }, []);

  // Re-evaluate the placement whenever price or readiness changes
  useEffect(() => {
    if (!ready || !window.Klarna || !window.Klarna.OnsiteMessaging) return;
    try {
      window.Klarna.OnsiteMessaging.refresh();
    } catch {
      /* noop */
    }
  }, [ready, price]);

  // Guards — render absolutely nothing if not configured or price invalid
  if (!config || !config.enabled) return null;
  const amountPence = Math.round(Number(price) * 100);
  if (!amountPence || amountPence < 100) return null;

  return (
    <klarna-placement
      data-testid={`klarna-osm-${placement}`}
      data-key={placement}
      data-locale={locale}
      data-purchase-country={purchaseCountry}
      data-purchase-amount={String(amountPence)}
      className={className}
    />
  );
}

// Test helper — lets unit tests / the admin preview refetch the config after saving
export function resetKlarnaOSMCache() {
  _cachedConfig = null;
  _inflightPromise = null;
}
