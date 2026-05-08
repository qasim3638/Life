/**
 * Precise Location helper — two paths for replacing the (often 100-mile-off)
 * IP geolocation with something accurate:
 *
 *   1. requestBrowserGeolocation()  → GPS, requires user consent
 *   2. tagPostcodeFromForm(postcode) → form input, validated UK postcode
 *
 * Both POST to /api/live-analytics/precise-location with both possible
 * session_ids (visitor beacon + page tracking) so admins see the precise
 * label everywhere — Live Visitors AND Visitor History.
 */
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const BEACON_SESSION_KEY = 'tilestation_visitor_session';
const PAGE_TRACKING_SESSION_KEY = 'analytics_session_id';

const UK_POSTCODE_RE = /^([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})$/i;

function readSessionIds() {
  try {
    return {
      session_id: sessionStorage.getItem(BEACON_SESSION_KEY) || sessionStorage.getItem(PAGE_TRACKING_SESSION_KEY) || null,
      page_tracking_session_id: sessionStorage.getItem(PAGE_TRACKING_SESSION_KEY) || null,
    };
  } catch {
    return { session_id: null, page_tracking_session_id: null };
  }
}

/** Returns the canonical "AB1 2CD" form, or null if not a UK postcode. */
export function normalisePostcode(raw) {
  if (!raw) return null;
  const m = String(raw).trim().match(UK_POSTCODE_RE);
  if (!m) return null;
  return `${m[1].toUpperCase()} ${m[2].toUpperCase()}`;
}

// Per-session de-dupe so we don't spam the backend if a user retypes a postcode
// or returns from a previously-tagged device.
const _postedPostcodes = new Set();

const PERSISTED_LOCATION_KEY = 'tilestation_precise_location_v1';
const PERSISTED_TTL_MS = 90 * 24 * 60 * 60 * 1000; // 90 days
let _restoreInFlight = false;

async function postPreciseLocation(body) {
  const ids = readSessionIds();
  if (!ids.session_id) return { ok: false, reason: 'no_session' };
  try {
    const r = await axios.post(`${API_URL}/api/live-analytics/precise-location`, {
      session_id: ids.session_id,
      page_tracking_session_id: ids.page_tracking_session_id,
      ...body,
    });
    const data = (r && r.data) || { ok: false };
    // Persist successful tags so we can re-tag this same device on its next
    // visit without re-prompting / re-typing. 90 day expiry keeps data fresh.
    if (data && data.ok && data.postcode) {
      try {
        localStorage.setItem(
          PERSISTED_LOCATION_KEY,
          JSON.stringify({
            postcode: data.postcode,
            town: data.town,
            source: data.source,
            saved_at: Date.now(),
          }),
        );
      } catch {
        // Storage full / private mode — non-fatal.
      }
    }
    return data;
  } catch {
    return { ok: false, reason: 'network' };
  }
}

/**
 * On every fresh visit, if we previously tagged this device's location,
 * re-apply it to the new session_id so the admin Live Visitors panel shows
 * a precise badge for returning customers — no consent prompt, no typing.
 *
 * Privacy-clean because the data the visitor previously provided is
 * being reused for the same purpose (analytics tagging) on the same device.
 *
 * Returns null if there's nothing to restore, otherwise the API result.
 */
export async function restorePersistedLocation() {
  if (_restoreInFlight) return null;
  let saved = null;
  try {
    const raw = localStorage.getItem(PERSISTED_LOCATION_KEY);
    if (!raw) return null;
    saved = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!saved || !saved.postcode) return null;
  if (saved.saved_at && Date.now() - saved.saved_at > PERSISTED_TTL_MS) {
    try { localStorage.removeItem(PERSISTED_LOCATION_KEY); } catch (_e) { /* non-fatal */ }
    return null;
  }
  // Don't re-fire if we've already posted this postcode in the current
  // session (prevents double tagging when a returning visitor also types
  // a postcode into a form).
  if (_postedPostcodes.has(saved.postcode)) return null;
  _restoreInFlight = true;
  _postedPostcodes.add(saved.postcode);
  try {
    return await postPreciseLocation({ source: 'form', postcode: saved.postcode });
  } finally {
    _restoreInFlight = false;
  }
}

/**
 * Browser GPS opt-in. Returns a promise resolving to:
 *   { ok: true, town, postcode } on success
 *   { ok: false, reason } on permission denied / no UK match / network
 *
 * Caller is responsible for the UI button + toast.
 */
export function requestBrowserGeolocation() {
  return new Promise((resolve) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      resolve({ ok: false, reason: 'unsupported' });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude: lat, longitude: lon, accuracy: accuracy_m } = pos.coords;
        const data = await postPreciseLocation({
          source: 'browser',
          lat,
          lon,
          accuracy_m: Number.isFinite(accuracy_m) ? Math.round(accuracy_m) : null,
        });
        resolve(data);
      },
      (err) => {
        // PERMISSION_DENIED=1 / POSITION_UNAVAILABLE=2 / TIMEOUT=3
        const map = { 1: 'permission_denied', 2: 'unavailable', 3: 'timeout' };
        resolve({ ok: false, reason: map[err && err.code] || 'gps_error' });
      },
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 60_000 },
    );
  });
}

/**
 * Quietly tags the current visitor session with a postcode the user typed
 * into ANY form field on the site. No-op if not a valid UK postcode or
 * already posted this session.
 */
export async function tagPostcodeFromForm(raw) {
  const pc = normalisePostcode(raw);
  if (!pc) return null;
  if (_postedPostcodes.has(pc)) return null;
  _postedPostcodes.add(pc);
  return await postPreciseLocation({ source: 'form', postcode: pc });
}

/**
 * Tags the current session using a logged-in customer's stored address.
 * Privacy-clean: the customer already provided the postcode for orders/
 * delivery, so reusing it for analytics on their own session is covered
 * by the same legitimate-interest basis as their account record.
 *
 * Accepts the same shape `customer.address.postcode` as the shop API.
 */
export async function tagFromCustomerProfile(customer) {
  if (!customer) return null;
  const pc =
    customer.postcode
    || (customer.address && customer.address.postcode)
    || null;
  return await tagPostcodeFromForm(pc);
}
