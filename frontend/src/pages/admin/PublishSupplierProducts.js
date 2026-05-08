import React, { useState, useEffect } from 'react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { 
  Upload, 
  CheckCircle, 
  XCircle, 
  AlertCircle,
  RefreshCw,
  Package,
  Globe,
  ArrowRight,
  Database
} from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function PublishSupplierProducts() {
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [supplierStats, setSupplierStats] = useState([]);
  const [websiteTiles, setWebsiteTiles] = useState({ total: 0, by_supplier: {} });
  const [publishResult, setPublishResult] = useState(null);
  const [selectedSupplier, setSelectedSupplier] = useState('all');

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    setLoading(true);
    try {
      // Get supplier products stats
      const suppliersRes = await fetch(`${API_URL}/api/supplier-sync/staging/stats`);
      if (suppliersRes.ok) {
        const data = await suppliersRes.json();
        setSupplierStats(data.by_supplier || []);
      }

      // Get website tiles count
      const tilesRes = await fetch(`${API_URL}/api/supplier-sync/website-tiles-count`);
      if (tilesRes.ok) {
        const data = await tilesRes.json();
        setWebsiteTiles(data);
      }
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePublish = async (supplier = null, withPriceOnly = false) => {
    setPublishing(true);
    setPublishResult(null);

    try {
      let url = `${API_URL}/api/supplier-sync/publish-to-website?with_price_only=${withPriceOnly}`;
      if (supplier && supplier !== 'all') {
        url += `&supplier=${encodeURIComponent(supplier)}`;
      }

      const response = await fetch(url, { method: 'POST' });
      const result = await response.json();

      if (response.ok) {
        setPublishResult(result);
        toast.success(`Published ${result.total_processed} products to website`);
        fetchStats(); // Refresh stats
      } else {
        toast.error(result.detail || 'Publish failed');
        setPublishResult({ error: result.detail });
      }
    } catch (error) {
      console.error('Error publishing:', error);
      toast.error('Publish failed');
      setPublishResult({ error: error.message });
    } finally {
      setPublishing(false);
    }
  };

  // Get unique suppliers from both sources
  const allSuppliers = [...new Set([
    ...supplierStats.map(s => s._id).filter(Boolean),
    ...Object.keys(websiteTiles.by_supplier || {}).filter(s => s !== 'Unknown')
  ])].sort();

  const getSupplierProductCount = (supplier) => {
    const stat = supplierStats.find(s => s._id === supplier);
    return stat?.count || 0;
  };

  const getPublishedCount = (supplier) => {
    return websiteTiles.by_supplier?.[supplier] || 0;
  };

  return (
    <div className="space-y-6" data-testid="publish-supplier-products">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Publish Supplier Products</h1>
          <p className="text-muted-foreground">Publish synced supplier products to the public website</p>
        </div>
        <Button onClick={fetchStats} variant="outline" size="sm" disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Supplier Products</p>
                <p className="text-2xl font-bold">
                  {supplierStats.reduce((sum, s) => sum + (s.count || 0), 0)}
                </p>
                <p className="text-xs text-muted-foreground">In database</p>
              </div>
              <Database className="h-8 w-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Published to Website</p>
                <p className="text-2xl font-bold text-green-600">{websiteTiles.total}</p>
                <p className="text-xs text-muted-foreground">Visible on website</p>
              </div>
              <Globe className="h-8 w-8 text-green-500" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Suppliers</p>
                <p className="text-2xl font-bold">{allSuppliers.length}</p>
                <p className="text-xs text-muted-foreground">Active suppliers</p>
              </div>
              <Package className="h-8 w-8 text-purple-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Publish Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Quick Publish
          </CardTitle>
          <CardDescription>
            Publish all supplier products to the website with one click
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <Button 
              onClick={() => handlePublish('all', false)} 
              disabled={publishing}
              className="flex-1"
            >
              {publishing ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Upload className="h-4 w-4 mr-2" />
              )}
              Publish All Products
            </Button>
            <Button 
              onClick={() => handlePublish('all', true)} 
              disabled={publishing}
              variant="outline"
              className="flex-1"
            >
              Publish Only Products with Prices
            </Button>
          </div>

          {/* Publish Result */}
          {publishResult && (
            <div className={`p-4 rounded-lg ${publishResult.error ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'} border`}>
              {publishResult.error ? (
                <div className="flex items-center gap-2 text-red-700">
                  <XCircle className="h-5 w-5" />
                  <span>{publishResult.error}</span>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-green-700">
                    <CheckCircle className="h-5 w-5" />
                    <span className="font-medium">{publishResult.message}</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">New:</span>
                      <span className="ml-1 font-medium text-green-600">{publishResult.published}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Updated:</span>
                      <span className="ml-1 font-medium">{publishResult.updated}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Skipped:</span>
                      <span className="ml-1 font-medium">{publishResult.skipped}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Total:</span>
                      <span className="ml-1 font-medium">{publishResult.total_processed}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Supplier Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle>Suppliers</CardTitle>
          <CardDescription>
            View and publish products by supplier
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : allSuppliers.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Package className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>No supplier products found</p>
              <p className="text-sm">Sync products from suppliers first</p>
            </div>
          ) : (
            <div className="space-y-3">
              {allSuppliers.map((supplier) => {
                const inDb = getSupplierProductCount(supplier);
                const published = getPublishedCount(supplier);
                const unpublished = inDb - published;
                
                return (
                  <div 
                    key={supplier} 
                    className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                        <Package className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <h3 className="font-medium">{supplier}</h3>
                        <div className="flex gap-4 text-sm text-muted-foreground">
                          <span>In DB: <span className="font-medium text-foreground">{inDb}</span></span>
                          <span>Published: <span className="font-medium text-green-600">{published}</span></span>
                          {unpublished > 0 && (
                            <span>Pending: <span className="font-medium text-orange-600">{unpublished}</span></span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {published === inDb && inDb > 0 ? (
                        <span className="text-sm text-green-600 flex items-center gap-1">
                          <CheckCircle className="h-4 w-4" />
                          All Published
                        </span>
                      ) : (
                        <Button 
                          size="sm"
                          variant="outline"
                          onClick={() => handlePublish(supplier, false)}
                          disabled={publishing || inDb === 0}
                        >
                          Publish
                          <ArrowRight className="h-4 w-4 ml-1" />
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Instructions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            How it works
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-3 gap-6 text-sm">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="bg-blue-100 text-blue-700 rounded-full w-6 h-6 flex items-center justify-center font-medium">1</span>
                <h4 className="font-medium">Sync Products</h4>
              </div>
              <p className="text-muted-foreground pl-8">
                Products are synced from suppliers (Wallcano, Splendour, Verona, etc.) and stored in the database.
              </p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="bg-green-100 text-green-700 rounded-full w-6 h-6 flex items-center justify-center font-medium">2</span>
                <h4 className="font-medium">Publish to Website</h4>
              </div>
              <p className="text-muted-foreground pl-8">
                Use this page to publish products to the public website. Products without prices show as "Out of Stock".
              </p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="bg-purple-100 text-purple-700 rounded-full w-6 h-6 flex items-center justify-center font-medium">3</span>
                <h4 className="font-medium">Set Prices</h4>
              </div>
              <p className="text-muted-foreground pl-8">
                Import prices using the price import feature (for Wallcano) or via bulk edit to make products available for purchase.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
