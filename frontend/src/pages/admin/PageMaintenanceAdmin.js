import React, { useState, useEffect } from 'react';
import { Wrench, Loader2, Save, ToggleLeft, ToggleRight, Globe, ExternalLink, Power, AlertTriangle } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const MANAGEABLE_PAGES = [
  { route: '/', label: 'Homepage', description: 'Main shop homepage' },
  { route: '/tiles', label: 'All Tiles', description: 'Product collections & listing page' },
  { route: '/new-collection', label: 'New Collections', description: 'New arrivals page' },
  { route: '/tiles?group=flooring', label: 'Flooring', description: 'Flooring products page' },
  { route: '/shop/bathroom', label: 'Bathroom', description: 'Bathroom landing page & catalogue' },
  { route: '/tiles?group=underfloor-heating', label: 'Underfloor Heating', description: 'Underfloor heating products page' },
  { route: '/tiles?group=materials', label: 'Materials', description: 'Materials, adhesives & grout page' },
  { route: '/tiles?group=tools-accessories', label: 'Tools & Accessories', description: 'Tools, equipment, trims & accessories page' },
  { route: '/clearance', label: 'Clearance / Sale', description: 'Clearance & sale products' },
  { route: '/shop/contact', label: 'Contact Us', description: 'Contact page & showroom locations' },
];

export default function PageMaintenanceAdmin() {
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Whole-site maintenance switch (overrides per-page rules when on)
  const [site, setSite] = useState({
    enabled: false, headline: '', message: '',
    scheduled_start: null, scheduled_end: null, auto_enabled: false,
  });
  const [siteSaving, setSiteSaving] = useState(false);
  const [siteDirty, setSiteDirty] = useState(false);
  // Schedule fields kept in `<input type="datetime-local">` format (no tz suffix).
  // Empty string means "no schedule".
  const [scheduleDirty, setScheduleDirty] = useState(false);
  const [schedStart, setSchedStart] = useState('');
  const [schedEnd, setSchedEnd] = useState('');
  const [schedSaving, setSchedSaving] = useState(false);

  useEffect(() => {
    fetchSettings();
    fetchSiteMaintenance();
  }, []);

  const fetchSiteMaintenance = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/site-maintenance`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSite({
          enabled: !!data.enabled,
          headline: data.headline || '',
          message: data.message || '',
          scheduled_start: data.scheduled_start || null,
          scheduled_end: data.scheduled_end || null,
          auto_enabled: !!data.auto_enabled,
        });
        // Hydrate datetime-local fields (which expect "YYYY-MM-DDTHH:mm" in local time)
        setSchedStart(isoToLocal(data.scheduled_start));
        setSchedEnd(isoToLocal(data.scheduled_end));
        setScheduleDirty(false);
      }
    } catch (e) {
      console.error('Error fetching site maintenance:', e);
    }
  };

  // Convert ISO 8601 (UTC) → "YYYY-MM-DDTHH:mm" in the browser's local tz
  // for binding to <input type="datetime-local">.
  function isoToLocal(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }
  // Convert "YYYY-MM-DDTHH:mm" (local time, tz-naive) → ISO 8601 UTC string.
  function localToIso(local) {
    if (!local) return null;
    const d = new Date(local);
    if (Number.isNaN(d.getTime())) return null;
    return d.toISOString();
  }

  const saveSiteMaintenance = async () => {
    if (site.enabled && (!site.headline.trim() || !site.message.trim())) {
      toast.error('Headline and message are required when enabling');
      return;
    }
    setSiteSaving(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/site-maintenance`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(site),
      });
      if (res.ok) {
        const data = await res.json();
        setSite({
          enabled: !!data.enabled,
          headline: data.headline || '',
          message: data.message || '',
          scheduled_start: data.scheduled_start || null,
          scheduled_end: data.scheduled_end || null,
          auto_enabled: !!data.auto_enabled,
        });
        setSiteDirty(false);
        toast.success(site.enabled ? 'Storefront is now in maintenance mode' : 'Storefront is back online');
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || 'Failed to save');
      }
    } catch {
      toast.error('Failed to save');
    } finally {
      setSiteSaving(false);
    }
  };

  const saveSchedule = async () => {
    const startIso = localToIso(schedStart);
    const endIso = localToIso(schedEnd);
    if (!startIso || !endIso) {
      toast.error('Pick a start AND end time');
      return;
    }
    if (new Date(endIso).getTime() <= new Date(startIso).getTime()) {
      toast.error('End must be after start');
      return;
    }
    setSchedSaving(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/site-maintenance`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ scheduled_start: startIso, scheduled_end: endIso }),
      });
      if (res.ok) {
        await fetchSiteMaintenance();
        toast.success('Maintenance window scheduled');
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || 'Failed to schedule');
      }
    } catch {
      toast.error('Failed to schedule');
    } finally {
      setSchedSaving(false);
    }
  };

  const clearSchedule = async () => {
    setSchedSaving(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/site-maintenance`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ scheduled_start: null, scheduled_end: null }),
      });
      if (res.ok) {
        setSchedStart(''); setSchedEnd(''); setScheduleDirty(false);
        await fetchSiteMaintenance();
        toast.success('Schedule cleared');
      } else {
        toast.error('Failed to clear');
      }
    } catch {
      toast.error('Failed to clear');
    } finally {
      setSchedSaving(false);
    }
  };

  const fetchSettings = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/maintenance-pages`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        const savedPages = data.pages || [];

        // Merge saved state with the full list
        const merged = MANAGEABLE_PAGES.map(page => {
          const saved = savedPages.find(s => s.route === page.route);
          return {
            ...page,
            disabled: saved?.disabled || false
          };
        });
        setPages(merged);
      }
    } catch (error) {
      console.error('Error fetching maintenance settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const togglePage = (route) => {
    setPages(prev => prev.map(p =>
      p.route === route ? { ...p, disabled: !p.disabled } : p
    ));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/maintenance-pages`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ pages })
      });
      if (res.ok) {
        toast.success('Maintenance settings saved');
      } else {
        toast.error('Failed to save');
      }
    } catch (error) {
      toast.error('Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const disabledCount = pages.filter(p => p.disabled).length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6" data-testid="page-maintenance-admin">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center">
            <Wrench className="w-6 h-6 text-amber-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Page Maintenance</h1>
            <p className="text-gray-500">Temporarily disable pages to show an Under Maintenance notice</p>
          </div>
        </div>
        <Button onClick={handleSave} disabled={saving} data-testid="save-maintenance-btn">
          {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
          Save Changes
        </Button>
      </div>

      {/* Whole-site maintenance switch */}
      <div
        className={`mb-8 rounded-xl border-2 p-5 transition-colors ${
          site.enabled ? 'bg-red-50 border-red-300' : 'bg-white border-gray-200'
        }`}
        data-testid="site-maintenance-panel"
      >
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-start gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              site.enabled ? 'bg-red-100' : 'bg-gray-100'
            }`}>
              <Power className={`w-5 h-5 ${site.enabled ? 'text-red-600' : 'text-gray-500'}`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-semibold text-gray-900">Whole-site maintenance</h2>
                {site.enabled && (
                  <span className="text-[10px] font-bold uppercase tracking-wider bg-red-600 text-white px-2 py-0.5 rounded">
                    LIVE NOW
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500 mt-0.5">
                Show every storefront visitor an &ldquo;Under Maintenance&rdquo; page. Admin access is unaffected.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => { setSite(s => ({ ...s, enabled: !s.enabled })); setSiteDirty(true); }}
            className="focus:outline-none shrink-0"
            data-testid="site-maintenance-toggle"
            aria-label={site.enabled ? 'Disable site maintenance' : 'Enable site maintenance'}
          >
            {site.enabled ? (
              <ToggleRight className="w-12 h-12 text-red-500 hover:text-red-600 transition-colors" />
            ) : (
              <ToggleLeft className="w-12 h-12 text-gray-400 hover:text-gray-500 transition-colors" />
            )}
          </button>
        </div>

        <div className="grid gap-4 md:grid-cols-1">
          <label className="text-sm">
            <span className="font-medium text-gray-700">Headline</span>
            <input
              type="text"
              value={site.headline}
              onChange={(e) => { setSite(s => ({ ...s, headline: e.target.value })); setSiteDirty(true); }}
              placeholder="We'll be back shortly"
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-amber-500 focus:ring-1 focus:ring-amber-500"
              maxLength={120}
              data-testid="site-maintenance-headline-input"
            />
          </label>
          <label className="text-sm">
            <span className="font-medium text-gray-700">Polite message</span>
            <textarea
              rows={4}
              value={site.message}
              onChange={(e) => { setSite(s => ({ ...s, message: e.target.value })); setSiteDirty(true); }}
              placeholder="Sorry for the inconvenience — we're making some quick improvements..."
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-amber-500 focus:ring-1 focus:ring-amber-500 resize-y"
              maxLength={1000}
              data-testid="site-maintenance-message-input"
            />
            <span className="block mt-1 text-xs text-gray-400">{site.message.length}/1000 characters</span>
          </label>
        </div>

        {site.enabled && (
          <div className="mt-3 flex items-start gap-2 text-xs text-red-700 bg-red-100/60 rounded-md p-2.5">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              When you save with the switch on, the public storefront will immediately show this message to every visitor. Admin pages remain accessible.
            </span>
          </div>
        )}

        <div className="mt-4 flex items-center justify-end gap-2">
          <a
            href="/?_preview_maintenance=1"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-gray-500 hover:text-gray-800 underline-offset-2 hover:underline"
          >
            Open homepage in new tab
          </a>
          <Button
            onClick={saveSiteMaintenance}
            disabled={siteSaving || !siteDirty}
            data-testid="site-maintenance-save-btn"
          >
            {siteSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
            Save site maintenance
          </Button>
        </div>

        {/* Scheduled window */}
        <div className="mt-5 pt-5 border-t border-gray-200">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium text-gray-900 text-sm">Schedule a maintenance window</h3>
            {site.scheduled_start && site.scheduled_end && (
              site.auto_enabled
                ? <span className="text-[10px] font-bold uppercase tracking-wider bg-red-600 text-white px-2 py-0.5 rounded">IN WINDOW</span>
                : <span className="text-[10px] font-bold uppercase tracking-wider bg-amber-500 text-white px-2 py-0.5 rounded">SCHEDULED</span>
            )}
          </div>
          <p className="text-xs text-gray-500 mb-3">
            We&apos;ll automatically flip the storefront into maintenance at the start time and back online at the end. Useful for planned overnight deploys.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm">
              <span className="text-xs font-medium text-gray-700">Start (your local time)</span>
              <input
                type="datetime-local"
                value={schedStart}
                onChange={(e) => { setSchedStart(e.target.value); setScheduleDirty(true); }}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-amber-500 focus:ring-1 focus:ring-amber-500"
                data-testid="site-maintenance-schedule-start"
              />
            </label>
            <label className="text-sm">
              <span className="text-xs font-medium text-gray-700">End (your local time)</span>
              <input
                type="datetime-local"
                value={schedEnd}
                onChange={(e) => { setSchedEnd(e.target.value); setScheduleDirty(true); }}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-amber-500 focus:ring-1 focus:ring-amber-500"
                data-testid="site-maintenance-schedule-end"
              />
            </label>
          </div>
          {site.scheduled_start && site.scheduled_end && (
            <p className="mt-2 text-[11px] text-gray-500">
              Currently set: {new Date(site.scheduled_start).toLocaleString()} → {new Date(site.scheduled_end).toLocaleString()}
            </p>
          )}
          <div className="mt-3 flex items-center justify-end gap-2">
            {(site.scheduled_start || site.scheduled_end) && (
              <Button
                type="button"
                variant="ghost"
                onClick={clearSchedule}
                disabled={schedSaving}
                className="text-gray-500"
                data-testid="site-maintenance-schedule-clear"
              >
                Clear schedule
              </Button>
            )}
            <Button
              type="button"
              onClick={saveSchedule}
              disabled={schedSaving || !scheduleDirty || !schedStart || !schedEnd}
              data-testid="site-maintenance-schedule-save"
            >
              {schedSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
              Save schedule
            </Button>
          </div>
        </div>
      </div>

      {/* Status Banner */}
      {disabledCount > 0 && (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center gap-3" data-testid="maintenance-warning">
          <Wrench className="w-5 h-5 text-amber-600 flex-shrink-0" />
          <p className="text-amber-800">
            <strong>{disabledCount} page{disabledCount !== 1 ? 's' : ''}</strong> currently showing Under Maintenance to visitors.
          </p>
        </div>
      )}

      {/* Pages List */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden divide-y divide-gray-100">
        {pages.map((page) => (
          <div
            key={page.route}
            className={`flex items-center justify-between p-5 transition-colors ${
              page.disabled ? 'bg-red-50/50' : ''
            }`}
            data-testid={`maintenance-row-${page.route.replace(/\//g, '-').replace(/^-/, '')}`}
          >
            <div className="flex items-center gap-4">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                page.disabled ? 'bg-red-100' : 'bg-green-100'
              }`}>
                <Globe className={`w-5 h-5 ${page.disabled ? 'text-red-600' : 'text-green-600'}`} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-semibold text-gray-900">{page.label}</p>
                  {page.disabled && (
                    <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium">
                      Under Maintenance
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-500">{page.description}</p>
                <p className="text-xs text-gray-400 mt-0.5 font-mono">{page.route}</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <a
                href={page.route}
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-400 hover:text-gray-600 transition-colors"
                title="Open page"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
              <button
                onClick={() => togglePage(page.route)}
                className="focus:outline-none"
                data-testid={`toggle-${page.route.replace(/\//g, '-').replace(/^-/, '')}`}
              >
                {page.disabled ? (
                  <ToggleRight className="w-10 h-10 text-red-500 hover:text-red-600 transition-colors" />
                ) : (
                  <ToggleLeft className="w-10 h-10 text-green-500 hover:text-green-600 transition-colors" />
                )}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Help Text */}
      <p className="text-sm text-gray-400 mt-4 text-center">
        Disabled pages will show a friendly "Under Maintenance" message to visitors. Admin access is not affected.
      </p>
    </div>
  );
}
