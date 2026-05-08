import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { 
  Globe, Copy, Search, ExternalLink, ChevronDown, ChevronRight,
  Home, Layers, ShoppingBag, FileText, Grid3X3, Loader2, Check,
  Plus, Navigation, LayoutGrid, Menu, ArrowRight, X, AlertTriangle,
  List, Columns3, GripVertical, CheckSquare, Square, Link2, Unlink,
  FolderTree, Eye, PanelRightOpen, PanelRightClose, Wrench
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import CollectionOrganizerView from './components/CollectionOrganizerView';
import LivePreviewPanel from './components/LivePreviewPanel';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const SITE_URL = window.location.origin;

const TYPE_CONFIG = {
  shop: { label: 'Shop Pages', icon: Home, color: 'bg-blue-100 text-blue-700', dot: 'bg-blue-500' },
  collection: { label: 'Collections', icon: Layers, color: 'bg-purple-100 text-purple-700', dot: 'bg-purple-500' },
  product: { label: 'Products', icon: ShoppingBag, color: 'bg-amber-100 text-amber-700', dot: 'bg-amber-500' },
  info: { label: 'Info Pages', icon: FileText, color: 'bg-green-100 text-green-700', dot: 'bg-green-500' },
  category: { label: 'Categories', icon: Grid3X3, color: 'bg-rose-100 text-rose-700', dot: 'bg-rose-500' },
};

const DESTINATIONS = [
  { id: 'main_nav', label: 'Main Navigation', icon: Navigation, color: 'border-blue-300 bg-blue-50' },
  { id: 'footer', label: 'Footer Links', icon: ArrowRight, color: 'border-green-300 bg-green-50' },
  { id: 'homepage', label: 'Homepage', icon: LayoutGrid, color: 'border-amber-300 bg-amber-50' },
];

// ============ MAIN COMPONENT ============
export default function SiteMapManager() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeType, setActiveType] = useState('all');
  const [expandedGroups, setExpandedGroups] = useState({ shop: true, collection: true, info: true, category: true, product: false });
  const [copiedUrl, setCopiedUrl] = useState(null);
  const [addingToNav, setAddingToNav] = useState(null);
  const [selectedPages, setSelectedPages] = useState(new Set());
  const [viewMode, setViewMode] = useState('list');
  const [bulkAction, setBulkAction] = useState(null);
  const [hoveredPage, setHoveredPage] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [previewUrl, setPreviewUrl] = useState('/tiles');
  const [previewDevice, setPreviewDevice] = useState('desktop');
  const [previewKey, setPreviewKey] = useState(0);
  const iframeRef = useRef(null);
  // One-shot legacy URL migrator state — see runHyphenMigrator below.
  const [migrating, setMigrating] = useState(false);

  useEffect(() => { fetchSitemap(); }, []);

  // Auto-fix admin-saved URLs that were typed/pasted in the old hyphen
  // format (e.g. /shop/collection/Ardesia-Slate). Backend rewrites only
  // those that resolve to a real collection; bogus typos are returned in
  // `needs_review` and surfaced verbatim in the toast for manual fix.
  const runHyphenMigrator = async () => {
    if (!window.confirm(
      'This will auto-correct any saved category links that use the old hyphen format ' +
      '(e.g. /Ardesia-Slate → /Ardesia%20Slate), but ONLY when the result points to a real collection. ' +
      'Typos or dead routes will be flagged for you to fix manually.\n\nProceed?'
    )) return;
    setMigrating(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/sitemap/migrate-hyphenated-urls`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Request failed');
      const data = await res.json();
      const fixed = data.rewritten_count || 0;
      const flagged = data.needs_review_count || 0;
      const summary = `Scanned ${data.scanned} link${data.scanned === 1 ? '' : 's'} · ` +
                      `Auto-fixed ${fixed} · Needs review: ${flagged}`;
      if (fixed > 0 || flagged > 0) {
        toast.success(summary, {
          description: flagged > 0
            ? `Couldn't auto-fix: ${(data.needs_review || []).slice(0, 3).map(r => r.where).join(' · ')}${flagged > 3 ? ' …' : ''}`
            : 'Click Refresh to see the updated map.',
          duration: 9000,
        });
      } else {
        toast.success('All your saved links are already in the correct format.');
      }
      await fetchSitemap();
    } catch {
      toast.error('Failed to run migrator');
    } finally {
      setMigrating(false);
    }
  };

  const fetchSitemap = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/sitemap`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const json = await res.json();
        setData(json);
        setSelectedPages(new Set());
        setPreviewKey(k => k + 1);
      } else {
        toast.error('Failed to load site map');
      }
    } catch (error) {
      toast.error('Failed to load site map');
    } finally {
      setLoading(false);
    }
  };

  const unlinkedCount = useMemo(() => {
    if (!data) return 0;
    return data.pages.filter(p => !p.linked_from || p.linked_from.length === 0).length;
  }, [data]);

  const filteredPages = useMemo(() => {
    if (!data) return [];
    let pages = data.pages;
    if (activeType === 'unlinked') {
      pages = pages.filter(p => !p.linked_from || p.linked_from.length === 0);
    } else if (activeType !== 'all') {
      pages = pages.filter(p => p.type === activeType);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      pages = pages.filter(p => p.name.toLowerCase().includes(q) || p.url.toLowerCase().includes(q));
    }
    return pages;
  }, [data, activeType, search]);

  const groupedPages = useMemo(() => {
    const groups = {};
    for (const page of filteredPages) {
      if (!groups[page.type]) groups[page.type] = [];
      groups[page.type].push(page);
    }
    return groups;
  }, [filteredPages]);

  const copyUrl = (url) => {
    const fullUrl = `${SITE_URL}${url}`;
    navigator.clipboard.writeText(fullUrl);
    setCopiedUrl(url);
    toast.success('URL copied to clipboard');
    setTimeout(() => setCopiedUrl(null), 2000);
  };

  const addToNavigation = useCallback(async (page, menuType = 'main') => {
    setAddingToNav(page.url);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/navigation/${menuType}/item`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ label: page.name, link_type: 'custom', link_url: page.url, is_active: true, highlight: false, children: [] })
      });
      if (res.ok) {
        toast.success(`Added "${page.name}" to Main Navigation`);
        fetchSitemap();
      } else toast.error('Failed to add to navigation');
    } catch { toast.error('Failed to add to navigation'); }
    finally { setAddingToNav(null); }
  }, []);

  const addToHomepage = useCallback(async (page) => {
    if (page.type === 'category') {
      try {
        const token = localStorage.getItem('token');
        const slug = page.url.split('category=')[1];
        const catRes = await fetch(`${API_URL}/api/website-admin/categories`, { headers: { 'Authorization': `Bearer ${token}` } });
        if (catRes.ok) {
          const cats = await catRes.json();
          const cat = cats.find(c => c.slug === slug);
          if (cat) {
            await fetch(`${API_URL}/api/website-admin/categories/${cat._id || cat.id}`, {
              method: 'PUT',
              headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
              body: JSON.stringify({ ...cat, show_on_homepage: true })
            });
            toast.success(`Added "${page.name}" to homepage`);
            fetchSitemap();
          }
        }
      } catch { toast.error('Failed to add to homepage'); }
    } else {
      toast.info('Only categories can be added to the homepage from here');
    }
  }, []);

  const addToFooter = useCallback(async (page) => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/footer-settings`);
      if (res.ok) {
        const { settings } = await res.json();
        const quickLinks = settings.quickLinks || [];
        if (quickLinks.some(l => l.url === page.url)) { toast.info(`"${page.name}" is already in the footer`); return; }
        quickLinks.push({ label: page.name, url: page.url });
        await fetch(`${API_URL}/api/website-admin/footer-settings`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ settings: { ...settings, quickLinks } })
        });
        toast.success(`Added "${page.name}" to footer`);
        fetchSitemap();
      }
    } catch { toast.error('Failed to add to footer'); }
  }, []);

  const unlinkPage = useCallback(async (linkRef) => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/sitemap/unlink`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(linkRef)
      });
      if (res.ok) {
        toast.success('Link removed');
        fetchSitemap();
      } else {
        toast.error('Failed to remove link');
      }
    } catch { toast.error('Failed to remove link'); }
  }, []);

  // ---- Bulk Operations ----
  const toggleSelect = (pageUrl) => {
    setSelectedPages(prev => {
      const next = new Set(prev);
      if (next.has(pageUrl)) next.delete(pageUrl);
      else next.add(pageUrl);
      return next;
    });
  };

  const selectAllVisible = () => {
    if (selectedPages.size === filteredPages.length) {
      setSelectedPages(new Set());
    } else {
      setSelectedPages(new Set(filteredPages.map(p => p.url)));
    }
  };

  const executeBulkAction = async (destination) => {
    const selected = filteredPages.filter(p => selectedPages.has(p.url));
    if (selected.length === 0) return;
    setBulkAction(destination);
    let success = 0;
    const token = localStorage.getItem('token');

    for (const page of selected) {
      try {
        if (destination === 'main_nav') {
          const res = await fetch(`${API_URL}/api/website-admin/navigation/main/item`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ label: page.name, link_type: 'custom', link_url: page.url, is_active: true, highlight: false, children: [] })
          });
          if (res.ok) success++;
        } else if (destination === 'footer') {
          const res = await fetch(`${API_URL}/api/website-admin/footer-settings`);
          if (res.ok) {
            const { settings } = await res.json();
            const quickLinks = settings.quickLinks || [];
            if (!quickLinks.some(l => l.url === page.url)) {
              quickLinks.push({ label: page.name, url: page.url });
              const saveRes = await fetch(`${API_URL}/api/website-admin/footer-settings`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ settings: { ...settings, quickLinks } })
              });
              if (saveRes.ok) success++;
            }
          }
        } else if (destination === 'homepage' && page.type === 'category') {
          const slug = page.url.split('category=')[1];
          const catRes = await fetch(`${API_URL}/api/website-admin/categories`, { headers: { 'Authorization': `Bearer ${token}` } });
          if (catRes.ok) {
            const cats = await catRes.json();
            const cat = cats.find(c => c.slug === slug);
            if (cat) {
              const r = await fetch(`${API_URL}/api/website-admin/categories/${cat._id || cat.id}`, {
                method: 'PUT',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...cat, show_on_homepage: true })
              });
              if (r.ok) success++;
            }
          }
        }
      } catch {}
    }

    const destLabel = DESTINATIONS.find(d => d.id === destination)?.label || destination;
    toast.success(`Added ${success} of ${selected.length} pages to ${destLabel}`);
    setSelectedPages(new Set());
    setBulkAction(null);
    fetchSitemap();
  };

  // ---- Board View Drop Handler ----
  const onDragEnd = async (result) => {
    if (!result.destination) return;
    const destId = result.destination.droppableId;
    if (destId === 'page-source') return;
    const pageUrl = result.draggableId;
    const page = filteredPages.find(p => p.url === pageUrl);
    if (!page) return;

    if (destId === 'main_nav') await addToNavigation(page, 'main');
    else if (destId === 'footer') await addToFooter(page);
    else if (destId === 'homepage') await addToHomepage(page);
  };

  const toggleGroup = (type) => {
    setExpandedGroups(prev => ({ ...prev, [type]: !prev[type] }));
  };

  const selectForPreview = useCallback((url) => {
    setPreviewUrl(url);
    if (!showPreview) setShowPreview(true);
  }, [showPreview]);

  const refreshPreview = useCallback(() => {
    setPreviewKey(k => k + 1);
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center h-[60vh]"><Loader2 className="w-8 h-8 animate-spin text-gray-400" /></div>;
  }

  return (
    <div className="h-full flex flex-col min-h-0" data-testid="sitemap-manager">
      {/* ========== HEADER ========== */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center flex-shrink-0">
              <Globe className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">Site Map & Link Manager</h1>
              <p className="text-sm text-gray-500">All your pages in one place — copy URLs and link them anywhere</p>
            </div>
          </div>
        </div>

        {/* Controls row: alert + view toggle + refresh */}
        <div className="flex items-center gap-2 mt-3 flex-wrap">
          {/* Unlinked Alert */}
          {unlinkedCount > 0 && (
            <button
              onClick={() => setActiveType(activeType === 'unlinked' ? 'all' : 'unlinked')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                activeType === 'unlinked'
                  ? 'bg-red-600 text-white'
                  : 'bg-red-50 text-red-700 hover:bg-red-100 border border-red-200'
              }`}
              data-testid="unlinked-alert"
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              {unlinkedCount} unlinked
            </button>
          )}
          {/* View Toggle */}
          <div className="flex items-center bg-gray-100 rounded-lg p-0.5" data-testid="view-toggle">
            <button
              onClick={() => setViewMode('list')}
              className={`p-1.5 rounded-md transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}
              title="List View"
              data-testid="view-list"
            >
              <List className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('board')}
              className={`p-1.5 rounded-md transition-colors ${viewMode === 'board' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}
              title="Board View (Drag & Drop)"
              data-testid="view-board"
            >
              <Columns3 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('collections')}
              className={`p-1.5 rounded-md transition-colors ${viewMode === 'collections' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}
              title="Collection Organizer"
              data-testid="view-collections"
            >
              <FolderTree className="w-4 h-4" />
            </button>
          </div>
          <Button variant="outline" size="sm" onClick={fetchSitemap} data-testid="refresh-sitemap">
            <Globe className="w-4 h-4 mr-1" /> Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={runHyphenMigrator}
            disabled={migrating}
            title="One-shot fix for category links saved with hyphens (e.g. /Ardesia-Slate) before today's URL fix landed. Auto-corrects only links that point to real collections; flags typos for manual review."
            data-testid="migrate-hyphen-urls"
            className="border-amber-300 bg-amber-50 hover:bg-amber-100 text-amber-800"
          >
            {migrating ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Wrench className="w-4 h-4 mr-1" />}
            Fix legacy hyphen links
          </Button>

          {/* Preview Toggle */}
          <div className="ml-auto">
            <button
              onClick={() => setShowPreview(prev => !prev)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                showPreview
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200 border border-gray-200'
              }`}
              data-testid="toggle-preview"
            >
              {showPreview ? <PanelRightClose className="w-3.5 h-3.5" /> : <PanelRightOpen className="w-3.5 h-3.5" />}
              {showPreview ? 'Hide Preview' : 'Live Preview'}
            </button>
          </div>
        </div>

        {/* Summary pills */}
        {data && viewMode !== 'collections' && (
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            <button
              onClick={() => setActiveType('all')}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${activeType === 'all' ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              data-testid="filter-all"
            >
              All ({data.pages.length})
            </button>
            {Object.entries(TYPE_CONFIG).map(([type, config]) => {
              const count = data.summary[type] || 0;
              if (count === 0) return null;
              return (
                <button key={type} onClick={() => setActiveType(activeType === type ? 'all' : type)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors flex items-center gap-1.5 ${activeType === type ? 'bg-gray-900 text-white' : `${config.color} hover:opacity-80`}`}
                  data-testid={`filter-${type}`}
                >
                  <div className={`w-2 h-2 rounded-full ${activeType === type ? 'bg-white' : config.dot}`} />
                  {config.label} ({count})
                  {type === 'product' && count < data.total_products && <span className="text-[10px] opacity-60">of {data.total_products}</span>}
                </button>
              );
            })}
          </div>
        )}

        {/* Search */}
        {viewMode !== 'collections' && (
        <div className="mt-3 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Search pages by name or URL..." className="pl-9 bg-gray-50" data-testid="search-pages" />
          {search && <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2"><X className="w-4 h-4 text-gray-400 hover:text-gray-600" /></button>}
        </div>
        )}
      </div>

      {/* ========== CONTENT + PREVIEW ========== */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* Main Content */}
        <div className={`flex-1 flex flex-col min-h-0 min-w-0 transition-all duration-300 ${showPreview ? 'max-w-[55%]' : ''}`}>
          {viewMode === 'list' ? (
            <ListView
              groupedPages={groupedPages} filteredPages={filteredPages} expandedGroups={expandedGroups}
              toggleGroup={toggleGroup} copiedUrl={copiedUrl} addingToNav={addingToNav}
              selectedPages={selectedPages} hoveredPage={hoveredPage}
              onCopy={copyUrl} onAddToNav={addToNavigation} onAddToHomepage={addToHomepage}
              onAddToFooter={addToFooter} onToggleSelect={toggleSelect} onSelectAll={selectAllVisible}
              onSetHovered={setHoveredPage} onUnlink={unlinkPage} onSelectForPreview={selectForPreview}
              previewUrl={previewUrl} showPreview={showPreview}
            />
          ) : viewMode === 'board' ? (
            <BoardView
              filteredPages={filteredPages} data={data} onDragEnd={onDragEnd}
              search={search} activeType={activeType} onUnlink={unlinkPage}
              onSelectForPreview={selectForPreview} previewUrl={previewUrl} showPreview={showPreview}
            />
          ) : (
            <CollectionOrganizerView />
          )}
        </div>

        {/* Live Preview Panel */}
        {showPreview && (
          <LivePreviewPanel
            previewUrl={previewUrl}
            previewDevice={previewDevice}
            setPreviewDevice={setPreviewDevice}
            previewKey={previewKey}
            onRefresh={refreshPreview}
            onClose={() => setShowPreview(false)}
            iframeRef={iframeRef}
          />
        )}
      </div>

      {/* ========== BULK ACTION BAR (fixed at bottom) ========== */}
      {selectedPages.size > 0 && viewMode === 'list' && (
        <div className="sticky bottom-0 bg-gray-900 text-white px-6 py-3 flex items-center justify-between shadow-2xl z-40" data-testid="bulk-action-bar">
          <div className="flex items-center gap-3">
            <CheckSquare className="w-4 h-4 text-indigo-400" />
            <span className="text-sm font-medium">{selectedPages.size} page{selectedPages.size !== 1 ? 's' : ''} selected</span>
            <button onClick={() => setSelectedPages(new Set())} className="text-xs text-gray-400 hover:text-white underline">Clear</button>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {DESTINATIONS.map(dest => (
              <Button key={dest.id} size="sm" variant="secondary"
                onClick={() => executeBulkAction(dest.id)}
                disabled={bulkAction !== null}
                className="text-xs h-8"
                data-testid={`bulk-add-${dest.id}`}
              >
                {bulkAction === dest.id ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <dest.icon className="w-3 h-3 mr-1" />}
                {dest.label}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ============ LIST VIEW ============
function ListView({ groupedPages, filteredPages, expandedGroups, toggleGroup, copiedUrl, addingToNav,
  selectedPages, hoveredPage, onCopy, onAddToNav, onAddToHomepage, onAddToFooter, onToggleSelect, onSelectAll, onSetHovered, onUnlink,
  onSelectForPreview, previewUrl, showPreview }) {
  
  const allSelected = filteredPages.length > 0 && selectedPages.size === filteredPages.length;

  return (
    <div className="flex-1 overflow-auto bg-gray-50 p-6">
      <div className="max-w-5xl mx-auto space-y-4">
        {/* Select all toggle */}
        {filteredPages.length > 0 && (
          <div className="flex items-center gap-2 px-1">
            <button onClick={onSelectAll} className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-700" data-testid="select-all">
              {allSelected ? <CheckSquare className="w-4 h-4 text-indigo-500" /> : <Square className="w-4 h-4" />}
              {allSelected ? 'Deselect all' : `Select all ${filteredPages.length} pages`}
            </button>
          </div>
        )}

        {Object.entries(groupedPages).length === 0 && (
          <div className="text-center py-12 text-gray-500">No pages found matching your search.</div>
        )}

        {['shop', 'category', 'collection', 'info', 'product'].map(type => {
          const pages = groupedPages[type];
          if (!pages || pages.length === 0) return null;
          const config = TYPE_CONFIG[type];
          const Icon = config.icon;
          const isExpanded = expandedGroups[type] !== false;

          return (
            <div key={type} className="bg-white rounded-xl border shadow-sm overflow-hidden" data-testid={`group-${type}`}>
              <button onClick={() => toggleGroup(type)}
                className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-gray-50 transition-colors"
                data-testid={`toggle-group-${type}`}>
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${config.color}`}><Icon className="w-4 h-4" /></div>
                  <span className="font-semibold text-gray-900">{config.label}</span>
                  <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">{pages.length}</span>
                </div>
                {isExpanded ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
              </button>
              {isExpanded && (
                <div className="border-t divide-y">
                  {pages.map((page, idx) => (
                    <PageRow key={`${page.type}-${idx}`} page={page} copiedUrl={copiedUrl} addingToNav={addingToNav}
                      isSelected={selectedPages.has(page.url)} isHovered={hoveredPage === page.url}
                      onCopy={onCopy} onAddToNav={onAddToNav} onAddToHomepage={onAddToHomepage}
                      onAddToFooter={onAddToFooter} onToggleSelect={onToggleSelect} onSetHovered={onSetHovered} onUnlink={onUnlink}
                      onSelectForPreview={onSelectForPreview} isPreviewActive={showPreview && previewUrl === page.url} />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============ PAGE ROW (with checkbox, hover preview) ============
function PageRow({ page, copiedUrl, addingToNav, isSelected, onCopy, onAddToNav, onAddToHomepage, onAddToFooter, onToggleSelect, onSetHovered, onUnlink,
  onSelectForPreview, isPreviewActive }) {
  const [showActions, setShowActions] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const isCopied = copiedUrl === page.url;
  const hasLinks = page.linked_from && page.linked_from.length > 0;

  // Helper to get label from linked_from (supports both old string format and new object format)
  const getLabel = (ref) => typeof ref === 'string' ? ref : ref.label;
  const isRemovable = (ref) => typeof ref === 'object' && ref.removable;

  return (
    <div
      className={`group flex items-center gap-3 px-5 py-2.5 transition-colors cursor-pointer ${
        isPreviewActive ? 'bg-indigo-50 border-l-2 border-l-indigo-500' :
        isSelected ? 'bg-indigo-50/50' : 'hover:bg-gray-50/80'
      }`}
      data-testid={`page-row-${page.type}-${page.name.toLowerCase().replace(/\s+/g, '-').slice(0, 30)}`}
      onMouseEnter={() => onSetHovered(page.url)}
      onMouseLeave={() => onSetHovered(null)}
      onClick={() => onSelectForPreview && onSelectForPreview(page.url)}
    >
      {/* Checkbox */}
      <button onClick={(e) => { e.stopPropagation(); onToggleSelect(page.url); }} className="flex-shrink-0" data-testid={`select-${page.name.toLowerCase().replace(/\s+/g, '-').slice(0, 20)}`}>
        {isSelected
          ? <CheckSquare className="w-4 h-4 text-indigo-500" />
          : <Square className="w-4 h-4 text-gray-300 group-hover:text-gray-400" />}
      </button>

      {/* Page info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-gray-900 truncate text-sm">{page.name}</span>
          {page.product_count && <span className="text-xs text-gray-400 flex-shrink-0">{page.product_count} products</span>}
        </div>
        <code className="text-xs text-gray-400 truncate block max-w-md">{page.url}</code>
      </div>

      {/* Linked from badges with hover preview */}
      <div className="relative flex items-center gap-1 flex-shrink-0">
        {hasLinks ? (
          <button
            className="flex items-center gap-1"
            onMouseEnter={() => setShowPreview(true)}
            onMouseLeave={() => setShowPreview(false)}
          >
            <Link2 className="w-3 h-3 text-emerald-500" />
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 whitespace-nowrap">
              {page.linked_from.length} link{page.linked_from.length !== 1 ? 's' : ''}
            </span>
          </button>
        ) : (
          <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-red-50 text-red-400 whitespace-nowrap">
            <Unlink className="w-3 h-3" /> Not linked
          </span>
        )}

        {/* Hover Preview Tooltip with Unlink buttons */}
        {showPreview && hasLinks && (
          <div 
            className="absolute right-0 bottom-full mb-2 w-72 bg-gray-900 text-white rounded-lg shadow-xl p-3 z-30" 
            data-testid="link-preview-tooltip"
            onMouseEnter={() => setShowPreview(true)}
            onMouseLeave={() => setShowPreview(false)}
          >
            <p className="text-[10px] text-gray-400 uppercase tracking-wide mb-2 font-semibold">Linked from</p>
            <div className="space-y-1">
              {page.linked_from.map((ref, i) => {
                const label = getLabel(ref);
                const parts = label.split(':');
                const source = parts[0]?.trim();
                const detail = parts.slice(1).join(':').trim();
                let icon = <Globe className="w-3 h-3" />;
                let color = 'text-gray-400';
                if (source === 'Nav') { icon = <Navigation className="w-3 h-3" />; color = 'text-blue-400'; }
                else if (source === 'Footer') { icon = <ArrowRight className="w-3 h-3" />; color = 'text-green-400'; }
                else if (source === 'Homepage') { icon = <LayoutGrid className="w-3 h-3" />; color = 'text-amber-400'; }
                return (
                  <div key={i} className="flex items-center justify-between gap-2 group/ref">
                    <div className="flex items-start gap-2 min-w-0">
                      <span className={`mt-0.5 flex-shrink-0 ${color}`}>{icon}</span>
                      <div className="min-w-0">
                        <span className="text-xs font-medium text-white">{source}</span>
                        {detail && <span className="text-xs text-gray-300 ml-1 truncate">{detail}</span>}
                      </div>
                    </div>
                    {isRemovable(ref) && (
                      <button
                        onClick={(e) => { e.stopPropagation(); onUnlink(ref); setShowPreview(false); }}
                        className="flex-shrink-0 p-1 rounded hover:bg-red-500/30 text-gray-500 hover:text-red-400 transition-colors opacity-0 group-hover/ref:opacity-100"
                        title="Remove this link"
                        data-testid={`unlink-${i}`}
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-0.5 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
        {/* Preview eye */}
        <button onClick={() => onSelectForPreview && onSelectForPreview(page.url)}
          className={`p-1.5 rounded-md transition-colors ${isPreviewActive ? 'bg-indigo-100 text-indigo-600' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'}`}
          title="Preview this page" data-testid={`preview-${page.name.toLowerCase().replace(/\s+/g, '-').slice(0, 20)}`}>
          <Eye className="w-3.5 h-3.5" />
        </button>
        <button onClick={() => onCopy(page.url)}
          className={`p-1.5 rounded-md transition-colors ${isCopied ? 'bg-green-100 text-green-600' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'}`}
          title="Copy full URL" data-testid={`copy-url-${page.name.toLowerCase().replace(/\s+/g, '-').slice(0, 20)}`}>
          {isCopied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
        <a href={page.url} target="_blank" rel="noopener noreferrer"
          className="p-1.5 rounded-md text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors" title="Open page">
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
        <div className="relative">
          <button onClick={() => setShowActions(!showActions)}
            className={`p-1.5 rounded-md transition-colors ${showActions ? 'bg-indigo-100 text-indigo-600' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'}`}
            title="Link this page" data-testid={`link-actions-${page.name.toLowerCase().replace(/\s+/g, '-').slice(0, 20)}`}>
            <Plus className="w-3.5 h-3.5" />
          </button>
          {showActions && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowActions(false)} />
              <div className="absolute right-0 top-full mt-1 w-48 bg-white rounded-lg shadow-lg border z-20 py-1">
                <button onClick={() => { onAddToNav(page, 'main'); setShowActions(false); }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  data-testid="add-to-main-nav"><Navigation className="w-3.5 h-3.5 text-blue-400" />Main Nav</button>
                {page.type === 'category' && (
                  <button onClick={() => { onAddToHomepage(page); setShowActions(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                    data-testid="add-to-homepage"><LayoutGrid className="w-3.5 h-3.5 text-amber-400" />Homepage</button>
                )}
                <button onClick={() => { onAddToFooter(page); setShowActions(false); }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  data-testid="add-to-footer"><ArrowRight className="w-3.5 h-3.5 text-green-400" />Footer</button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ============ BOARD VIEW (Drag & Drop) ============
function BoardView({ filteredPages, data, onDragEnd, search, activeType, onUnlink, onSelectForPreview, previewUrl, showPreview }) {
  // Compute what's currently in each destination
  const destinationContents = useMemo(() => {
    if (!data) return {};
    const contents = { main_nav: [], footer: [], homepage: [] };
    for (const page of data.pages) {
      for (const ref of (page.linked_from || [])) {
        const label = typeof ref === 'string' ? ref : ref.label;
        if (label.startsWith('Nav: main')) contents.main_nav.push({ ...page, _linkRef: ref });
        else if (label.startsWith('Footer:')) contents.footer.push({ ...page, _linkRef: ref });
        else if (label.startsWith('Homepage:')) contents.homepage.push({ ...page, _linkRef: ref });
      }
    }
    // Dedupe
    for (const key of Object.keys(contents)) {
      const seen = new Set();
      contents[key] = contents[key].filter(p => { if (seen.has(p.url)) return false; seen.add(p.url); return true; });
    }
    return contents;
  }, [data]);

  // Pages available to drag (not yet linked anywhere for the filtered set)
  const sourcePages = useMemo(() => {
    return filteredPages.slice(0, 60); // Cap for performance
  }, [filteredPages]);

  return (
    <DragDropContext onDragEnd={onDragEnd}>
      <div className="flex-1 overflow-auto bg-gray-50 p-4">
        <div className="flex gap-4 h-full min-h-[500px]">
          {/* SOURCE: Pages to drag */}
          <div className="w-80 flex-shrink-0 flex flex-col">
            <div className="bg-white rounded-xl border shadow-sm flex flex-col h-full">
              <div className="px-4 py-3 border-b">
                <h3 className="font-semibold text-gray-900 text-sm">Pages</h3>
                <p className="text-xs text-gray-400 mt-0.5">Drag pages to a destination</p>
              </div>
              <Droppable droppableId="page-source">
                {(provided) => (
                  <div ref={provided.innerRef} {...provided.droppableProps}
                    className="flex-1 overflow-auto p-2 space-y-1">
                    {sourcePages.map((page, index) => (
                      <Draggable key={page.url} draggableId={page.url} index={index}>
                        {(provided, snapshot) => (
                          <div ref={provided.innerRef} {...provided.draggableProps} {...provided.dragHandleProps}
                            onClick={() => onSelectForPreview && onSelectForPreview(page.url)}
                            className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors cursor-pointer ${
                              snapshot.isDragging ? 'bg-indigo-50 border-indigo-300 shadow-lg' :
                              (showPreview && previewUrl === page.url) ? 'bg-indigo-50 border-indigo-300 ring-1 ring-indigo-200' :
                              'bg-white border-gray-200 hover:border-gray-300'
                            }`}>
                            <GripVertical className="w-3.5 h-3.5 text-gray-300 flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                              <span className="font-medium text-gray-800 text-xs truncate block">{page.name}</span>
                              <code className="text-[10px] text-gray-400 truncate block">{page.url}</code>
                            </div>
                            {page.linked_from && page.linked_from.length > 0 ? (
                              <Link2 className="w-3 h-3 text-emerald-400 flex-shrink-0" />
                            ) : (
                              <Unlink className="w-3 h-3 text-red-300 flex-shrink-0" />
                            )}
                          </div>
                        )}
                      </Draggable>
                    ))}
                    {provided.placeholder}
                    {sourcePages.length === 0 && (
                      <div className="text-center py-8 text-gray-400 text-xs">No pages match your filters</div>
                    )}
                    {filteredPages.length > 60 && (
                      <div className="text-center py-2 text-gray-400 text-[10px]">
                        Showing 60 of {filteredPages.length} — use search to find specific pages
                      </div>
                    )}
                  </div>
                )}
              </Droppable>
            </div>
          </div>

          {/* DESTINATIONS */}
          <div className="flex-1 grid grid-cols-2 gap-4">
            {DESTINATIONS.map(dest => (
              <DestinationColumn key={dest.id} dest={dest} contents={destinationContents[dest.id] || []} onUnlink={onUnlink} />
            ))}
          </div>
        </div>
      </div>
    </DragDropContext>
  );
}

// ============ DESTINATION COLUMN ============
function DestinationColumn({ dest, contents, onUnlink }) {
  const Icon = dest.icon;
  return (
    <Droppable droppableId={dest.id}>
      {(provided, snapshot) => (
        <div ref={provided.innerRef} {...provided.droppableProps}
          className={`rounded-xl border-2 border-dashed flex flex-col transition-colors ${
            snapshot.isDraggingOver ? 'border-indigo-400 bg-indigo-50/50' : dest.color
          }`}>
          <div className="px-4 py-3 flex items-center gap-2 border-b border-gray-200/50">
            <Icon className="w-4 h-4 text-gray-600" />
            <span className="font-semibold text-gray-800 text-sm">{dest.label}</span>
            <span className="text-xs text-gray-400 bg-white/70 px-1.5 py-0.5 rounded-full">{contents.length}</span>
          </div>
          <div className="flex-1 overflow-auto p-2 space-y-1 min-h-[120px]">
            {contents.map((page, idx) => (
              <div key={`${dest.id}-${page.url}-${idx}`}
                className="group flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-white/80 border border-gray-200 text-xs hover:border-gray-300 transition-colors">
                <Link2 className="w-3 h-3 text-emerald-500 flex-shrink-0" />
                <span className="font-medium text-gray-700 truncate flex-1">{page.name}</span>
                <button
                  onClick={() => onUnlink(page._linkRef)}
                  className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-100 hover:text-red-500 text-gray-400 transition-all"
                  title={`Remove ${page.name} from ${dest.label}`}
                  data-testid={`unlink-board-${dest.id}-${idx}`}
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
            {contents.length === 0 && !snapshot.isDraggingOver && (
              <div className="flex items-center justify-center h-full text-gray-400 text-xs py-8">
                Drop pages here
              </div>
            )}
            {snapshot.isDraggingOver && (
              <div className="flex items-center justify-center py-3 text-indigo-500 text-xs font-medium animate-pulse">
                Release to link here
              </div>
            )}
            {provided.placeholder}
          </div>
        </div>
      )}
    </Droppable>
  );
}
