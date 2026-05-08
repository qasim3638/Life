import React, { useState, useEffect } from 'react';
import { Eye, ExternalLink, Monitor, Tablet, Smartphone, RefreshCw, Home, ShoppingBag, Calculator, Building2, FileText, Upload, Package, Globe, ChevronDown, ChevronUp, CheckCircle, AlertCircle, Rocket, Clock, Trash2, EyeOff, Loader2 } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const WebsitePreview = () => {
  const [device, setDevice] = useState('desktop');
  const [currentPage, setCurrentPage] = useState('/tiles');
  const [refreshKey, setRefreshKey] = useState(0);
  const [showPublishPanel, setShowPublishPanel] = useState(false);
  const [supplierStats, setSupplierStats] = useState([]);
  const [websiteTiles, setWebsiteTiles] = useState({ total: 0, by_supplier: {} });
  const [publishing, setPublishing] = useState(false);
  const [loadingStats, setLoadingStats] = useState(false);
  
  // Design changes state
  const [pendingChanges, setPendingChanges] = useState({ has_pending: false, total_changes: 0, changes: [] });
  const [publishingDesign, setPublishingDesign] = useState(false);
  const [unpublishing, setUnpublishing] = useState(false);

  // Get the base URL - in production this would be the actual domain
  const baseUrl = window.location.origin;

  const pages = [
    { path: '/tiles', label: 'Homepage', icon: Home },
    { path: '/tiles', label: 'All Products', icon: ShoppingBag },
    { path: '/shop/calculator', label: 'Tile Calculator', icon: Calculator },
    { path: '/shop/trade', label: 'Trade Signup', icon: Building2 },
    { path: '/shop/sample-service', label: 'Sample Service', icon: FileText },
  ];

  const deviceSizes = {
    desktop: { width: '100%', height: '100%', label: 'Desktop' },
    tablet: { width: '768px', height: '100%', label: 'Tablet' },
    mobile: { width: '375px', height: '100%', label: 'Mobile' },
  };

  useEffect(() => {
    fetchPendingChanges();
  }, []);

  useEffect(() => {
    if (showPublishPanel) {
      fetchStats();
    }
  }, [showPublishPanel]);

  const fetchPendingChanges = async () => {
    try {
      const response = await fetch(`${API_URL}/api/website-admin/pending-changes`);
      if (response.ok) {
        const data = await response.json();
        setPendingChanges(data);
      }
    } catch (error) {
      console.error('Error fetching pending changes:', error);
    }
  };

  const fetchStats = async () => {
    setLoadingStats(true);
    try {
      const [suppliersRes, tilesRes] = await Promise.all([
        fetch(`${API_URL}/api/supplier-sync/staging/stats`),
        fetch(`${API_URL}/api/supplier-sync/website-tiles-count`)
      ]);
      
      if (suppliersRes.ok) {
        const data = await suppliersRes.json();
        setSupplierStats(data.by_supplier || []);
      }
      if (tilesRes.ok) {
        const data = await tilesRes.json();
        setWebsiteTiles(data);
      }
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoadingStats(false);
    }
  };

  const handlePublish = async (supplier = null) => {
    setPublishing(true);
    try {
      let url = `${API_URL}/api/supplier-sync/publish-to-website?with_price_only=false`;
      if (supplier) {
        url += `&supplier=${encodeURIComponent(supplier)}`;
      }
      
      const response = await fetch(url, { method: 'POST' });
      const result = await response.json();
      
      if (response.ok) {
        toast.success(`Published ${result.total_processed} products to website`);
        fetchStats();
        handleRefresh(); // Refresh the preview
      } else {
        toast.error(result.detail || 'Publish failed');
      }
    } catch (error) {
      toast.error('Publish failed');
    } finally {
      setPublishing(false);
    }
  };

  const handleUnpublish = async (supplier = null) => {
    const confirmMsg = supplier 
      ? `Are you sure you want to unpublish all ${supplier} products from the website?`
      : 'Are you sure you want to unpublish ALL products from the website?';
    
    if (!window.confirm(confirmMsg)) return;
    
    setUnpublishing(true);
    try {
      let url = `${API_URL}/api/supplier-sync/unpublish-from-website`;
      if (supplier) {
        url += `?supplier=${encodeURIComponent(supplier)}`;
      }
      
      const response = await fetch(url, { method: 'DELETE' });
      const result = await response.json();
      
      if (response.ok) {
        toast.success(`Unpublished ${result.deleted_count} products from website`);
        fetchStats();
        handleRefresh();
      } else {
        toast.error(result.detail || 'Unpublish failed');
      }
    } catch (error) {
      toast.error('Unpublish failed');
    } finally {
      setUnpublishing(false);
    }
  };

  const handlePublishDesignChanges = async () => {
    setPublishingDesign(true);
    try {
      const response = await fetch(`${API_URL}/api/website-admin/publish-changes`, { method: 'POST' });
      const result = await response.json();
      
      if (response.ok) {
        toast.success(result.message || 'Changes published successfully');
        fetchPendingChanges();
        handleRefresh();
      } else {
        toast.error(result.detail || 'Publish failed');
      }
    } catch (error) {
      toast.error('Publish failed');
    } finally {
      setPublishingDesign(false);
    }
  };

  const handleDiscardChanges = async () => {
    if (!confirm('Are you sure you want to discard all pending changes?')) return;
    
    try {
      const response = await fetch(`${API_URL}/api/website-admin/discard-changes`, { method: 'DELETE' });
      const result = await response.json();
      
      if (response.ok) {
        toast.success('Changes discarded');
        fetchPendingChanges();
      } else {
        toast.error('Failed to discard changes');
      }
    } catch (error) {
      toast.error('Failed to discard changes');
    }
  };

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1);
  };

  const openInNewTab = () => {
    window.open(`${baseUrl}${currentPage}`, '_blank');
  };

  // Get unique suppliers
  const allSuppliers = [...new Set([
    ...supplierStats.map(s => s._id).filter(Boolean),
    ...Object.keys(websiteTiles.by_supplier || {}).filter(s => s !== 'Unknown')
  ])].sort();

  const getSupplierCount = (supplier) => supplierStats.find(s => s._id === supplier)?.count || 0;
  const getPublishedCount = (supplier) => websiteTiles.by_supplier?.[supplier] || 0;

  return (
    <div className="h-full flex flex-col" data-testid="website-preview">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
              <Eye className="w-5 h-5 text-emerald-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">Website Preview</h1>
              <p className="text-sm text-slate-500">Preview your shop as customers see it</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Publish Design Changes Button */}
            <Button 
              variant={pendingChanges.has_pending ? "default" : "outline"}
              size="sm" 
              onClick={handlePublishDesignChanges}
              disabled={publishingDesign || !pendingChanges.has_pending}
              className={pendingChanges.has_pending ? "bg-orange-500 hover:bg-orange-600" : ""}
              data-testid="publish-changes-btn"
            >
              {publishingDesign ? (
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Rocket className="w-4 h-4 mr-2" />
              )}
              Publish Changes
              {pendingChanges.total_changes > 0 && (
                <span className="ml-1.5 bg-white/20 px-1.5 py-0.5 rounded text-xs">
                  {pendingChanges.total_changes}
                </span>
              )}
            </Button>
            
            {/* Discard Changes Button - only show if there are pending changes */}
            {pendingChanges.has_pending && (
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={handleDiscardChanges}
                className="text-red-500 hover:text-red-600 hover:bg-red-50"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            )}
            
            <div className="w-px h-6 bg-slate-200 mx-1" />
            
            <Button 
              variant={showPublishPanel ? "default" : "outline"} 
              size="sm" 
              onClick={() => setShowPublishPanel(!showPublishPanel)}
              className={showPublishPanel ? "bg-emerald-600 hover:bg-emerald-700" : ""}
            >
              <Upload className="w-4 h-4 mr-2" />
              Publish Products
              {showPublishPanel ? <ChevronUp className="w-4 h-4 ml-1" /> : <ChevronDown className="w-4 h-4 ml-1" />}
            </Button>
            <Button variant="outline" size="sm" onClick={handleRefresh}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
            <Button variant="outline" size="sm" onClick={openInNewTab}>
              <ExternalLink className="w-4 h-4 mr-2" />
              Open in New Tab
            </Button>
          </div>
        </div>

        {/* Pending Changes Info Bar */}
        {pendingChanges.has_pending && (
          <div className="mb-4 p-3 bg-orange-50 border border-orange-200 rounded-lg flex items-center justify-between">
            <div className="flex items-center gap-2 text-orange-700">
              <Clock className="w-4 h-4" />
              <span className="text-sm font-medium">
                {pendingChanges.total_changes} unpublished change{pendingChanges.total_changes !== 1 ? 's' : ''} waiting
              </span>
              <span className="text-xs text-orange-500">
                (Changes will only appear on website after clicking "Publish Changes")
              </span>
            </div>
          </div>
        )}

        {/* Publish Panel */}
        {showPublishPanel && (
          <div className="mb-4 p-4 bg-slate-50 rounded-lg border">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <Package className="w-4 h-4 text-blue-500" />
                  <span className="text-sm">In Database: <strong>{supplierStats.reduce((sum, s) => sum + (s.count || 0), 0)}</strong></span>
                </div>
                <div className="flex items-center gap-2">
                  <Globe className="w-4 h-4 text-green-500" />
                  <span className="text-sm">Published: <strong className="text-green-600">{websiteTiles.total_tiles}</strong></span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button 
                  size="sm" 
                  onClick={() => handlePublish(null)}
                  disabled={publishing || unpublishing}
                  className="bg-green-600 hover:bg-green-700"
                >
                  {publishing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
                  Publish All
                </Button>
                {websiteTiles.total_tiles > 0 && (
                  <Button 
                    size="sm" 
                    variant="outline"
                    onClick={() => handleUnpublish(null)}
                    disabled={publishing || unpublishing}
                    className="border-red-300 text-red-600 hover:bg-red-50"
                  >
                    {unpublishing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <EyeOff className="w-4 h-4 mr-2" />}
                    Unpublish All
                  </Button>
                )}
              </div>
            </div>
            
            {loadingStats ? (
              <div className="text-center py-2 text-sm text-slate-500">Loading suppliers...</div>
            ) : allSuppliers.length > 0 ? (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                {allSuppliers.map(supplier => {
                  const inDb = getSupplierCount(supplier);
                  const published = getPublishedCount(supplier);
                  const isPending = inDb > published;
                  
                  return (
                    <div key={supplier} className="flex items-center justify-between p-2 bg-white rounded border text-xs">
                      <div className="flex-1 min-w-0 mr-2">
                        <div className="font-medium truncate" title={supplier}>{supplier}</div>
                        <div className="text-slate-500">
                          <span className="text-green-600">{published}</span>/{inDb} published
                          {isPending && <span className="text-orange-500 ml-1">(+{inDb - published} pending)</span>}
                        </div>
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {inDb > 0 && published < inDb && (
                          <Button 
                            size="sm" 
                            variant="ghost" 
                            className="h-6 px-2 text-xs text-green-600 hover:bg-green-50"
                            onClick={() => handlePublish(supplier)}
                            disabled={publishing || unpublishing}
                          >
                            <Upload className="w-3 h-3 mr-1" />
                            Publish
                          </Button>
                        )}
                        {published > 0 && (
                          <Button 
                            size="sm" 
                            variant="ghost" 
                            className="h-6 px-2 text-xs text-red-500 hover:bg-red-50"
                            onClick={() => handleUnpublish(supplier)}
                            disabled={publishing || unpublishing}
                          >
                            <EyeOff className="w-3 h-3 mr-1" />
                            Unpublish
                          </Button>
                        )}
                        {published === inDb && inDb > 0 && (
                          <CheckCircle className="w-4 h-4 text-green-500" />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-2 text-sm text-slate-500">
                <AlertCircle className="w-4 h-4 inline mr-1" />
                No supplier products found. Sync products first.
              </div>
            )}
          </div>
        )}

        {/* Controls */}
        <div className="flex items-center justify-between">
          {/* Page Selector */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-500 mr-2">Page:</span>
            {pages.map((page) => (
              <Button
                key={page.path}
                variant={currentPage === page.path ? 'default' : 'outline'}
                size="sm"
                onClick={() => setCurrentPage(page.path)}
                className={currentPage === page.path ? 'bg-slate-900' : ''}
              >
                <page.icon className="w-4 h-4 mr-1" />
                {page.label}
              </Button>
            ))}
          </div>

          {/* Device Selector */}
          <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
            <button
              onClick={() => setDevice('desktop')}
              className={`p-2 rounded-md transition-colors ${device === 'desktop' ? 'bg-white shadow-sm' : 'hover:bg-slate-200'}`}
              title="Desktop"
            >
              <Monitor className={`w-5 h-5 ${device === 'desktop' ? 'text-slate-900' : 'text-slate-500'}`} />
            </button>
            <button
              onClick={() => setDevice('tablet')}
              className={`p-2 rounded-md transition-colors ${device === 'tablet' ? 'bg-white shadow-sm' : 'hover:bg-slate-200'}`}
              title="Tablet"
            >
              <Tablet className={`w-5 h-5 ${device === 'tablet' ? 'text-slate-900' : 'text-slate-500'}`} />
            </button>
            <button
              onClick={() => setDevice('mobile')}
              className={`p-2 rounded-md transition-colors ${device === 'mobile' ? 'bg-white shadow-sm' : 'hover:bg-slate-200'}`}
              title="Mobile"
            >
              <Smartphone className={`w-5 h-5 ${device === 'mobile' ? 'text-slate-900' : 'text-slate-500'}`} />
            </button>
          </div>
        </div>
      </div>

      {/* Preview Area */}
      <div className="flex-1 bg-slate-100 p-4 overflow-hidden">
        <div 
          className="h-full mx-auto bg-white rounded-lg shadow-lg overflow-hidden transition-all duration-300"
          style={{ 
            width: deviceSizes[device].width,
            maxWidth: '100%'
          }}
        >
          {/* Browser Chrome */}
          <div className="bg-slate-200 px-4 py-2 flex items-center gap-2">
            <div className="flex gap-1.5">
              <div className="w-3 h-3 rounded-full bg-red-400" />
              <div className="w-3 h-3 rounded-full bg-yellow-400" />
              <div className="w-3 h-3 rounded-full bg-green-400" />
            </div>
            <div className="flex-1 bg-white rounded-md px-3 py-1 text-sm text-slate-500 truncate">
              {baseUrl}{currentPage}
            </div>
          </div>

          {/* iframe */}
          <iframe
            key={refreshKey}
            src={`${baseUrl}${currentPage}`}
            className="w-full border-0"
            style={{ height: 'calc(100vh - 240px)' }}
            title="Website Preview"
          />
        </div>
      </div>

      {/* Footer Info */}
      <div className="bg-white border-t px-6 py-3">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">
            Viewing: <span className="font-medium text-slate-900">{pages.find(p => p.path === currentPage)?.label}</span>
          </span>
          <span className="text-slate-500">
            Device: <span className="font-medium text-slate-900">{deviceSizes[device].label}</span>
            {device !== 'desktop' && <span className="ml-1 text-slate-400">({deviceSizes[device].width})</span>}
          </span>
        </div>
      </div>
    </div>
  );
};

export default WebsitePreview;
