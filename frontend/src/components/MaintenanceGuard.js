import React from 'react';
import { useLocation } from 'react-router-dom';
import { useMaintenanceCheck } from '../contexts/MaintenanceContext';
import MaintenancePage from '../pages/shop/MaintenancePage';

export default function MaintenanceGuard({ children }) {
  const { disabledRoutes, site } = useMaintenanceCheck();
  const location = useLocation();

  // Whole-site override beats per-page rules.
  if (site?.enabled) {
    return <MaintenancePage headline={site.headline} message={site.message} />;
  }

  const currentPath = location.pathname;
  const currentSearch = location.search;

  const isDisabled = disabledRoutes.some(route => {
    const hasQuery = route.includes('?');
    const [routePath, routeQuery] = route.split('?');

    if (currentPath !== routePath) return false;

    if (hasQuery) {
      // Route has query params — check they all match
      const currentParams = new URLSearchParams(currentSearch);
      const routeParams = new URLSearchParams(routeQuery);
      for (const [key, value] of routeParams.entries()) {
        if (currentParams.get(key) !== value) return false;
      }
      return true;
    } else {
      // Route has no query params — only match if current URL also has no group param
      // This prevents "/tiles" from blocking "/tiles?group=flooring"
      const currentParams = new URLSearchParams(currentSearch);
      if (routePath === '/tiles' && currentParams.get('group')) return false;
      return true;
    }
  });

  if (isDisabled) return <MaintenancePage />;
  return children;
}
