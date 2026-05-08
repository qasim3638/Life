/**
 * VisitorBeacon — invisible component that drives the live-visitor heartbeat
 * and the global postcode listener (auto-tags the current session whenever
 * a visitor types a UK postcode into any form field on the site).
 * Mounted once inside <BrowserRouter> so it can read the current pathname.
 */
import { useEffect } from 'react';
import useVisitorBeacon from '../hooks/useVisitorBeacon';
import { tagPostcodeFromForm, restorePersistedLocation } from '../lib/preciseLocation';

const VisitorBeacon = () => {
  useVisitorBeacon();

  // On mount, re-tag this session if we have a previously persisted location
  // (returning visitor → instant precise badge, no consent prompt).
  useEffect(() => {
    restorePersistedLocation().catch(() => { /* non-fatal */ });
  }, []);

  // Global postcode listener — fires when ANY input field on the site
  // either blurs OR is typed into and matches a UK postcode. We listen on
  // the document so we don't have to touch every form individually.
  useEffect(() => {
    const tryTag = (target) => {
      if (!target || target.tagName !== 'INPUT') return;
      const name = (target.name || target.id || '').toLowerCase();
      const placeholder = (target.placeholder || '').toLowerCase();
      const looksLikePostcode = name.includes('postcode') || name.includes('post_code') || placeholder.includes('postcode');
      if (!looksLikePostcode) return;
      tagPostcodeFromForm(target.value);
    };
    const onBlur = (e) => tryTag(e.target);
    document.addEventListener('blur', onBlur, true);
    return () => document.removeEventListener('blur', onBlur, true);
  }, []);

  return null;
};

export default VisitorBeacon;
