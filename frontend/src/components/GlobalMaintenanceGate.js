import React from 'react';
import { useLocation } from 'react-router-dom';
import { useMaintenanceCheck } from '../contexts/MaintenanceContext';
import MaintenancePage from '../pages/shop/MaintenancePage';
import MaintenanceAdvanceBanner from './MaintenanceAdvanceBanner';

// Paths that must remain reachable when whole-site maintenance is enabled,
// otherwise admins lose the ability to flip the switch back off.
const BYPASS_PREFIXES = [
  '/admin',
  '/staff-register',
  '/forgot-password',
  '/reset-password',
];

function isAdminPath(path) {
  return BYPASS_PREFIXES.some(p => path === p || path.startsWith(p + '/') || path.startsWith(p + '?'))
    || path === '/register';
}

/**
 * Wraps <Routes> at the app root. When whole-site maintenance is on, every
 * customer-facing path renders <MaintenancePage>. Admin / auth paths bypass
 * so the toggle can always be reversed.
 *
 * Also injects the advance-notice banner above customer-facing pages when a
 * future maintenance window is within 24h.
 */
export default function GlobalMaintenanceGate({ children }) {
  const { site, loading } = useMaintenanceCheck();
  const location = useLocation();
  const path = location.pathname || '/';
  const onAdmin = isAdminPath(path);

  if (loading) return children; // first paint — don't flash maintenance
  if (site?.enabled && !onAdmin) {
    return <MaintenancePage headline={site.headline} message={site.message} />;
  }

  return (
    <>
      {!onAdmin && <MaintenanceAdvanceBanner />}
      {children}
    </>
  );
}
