import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { Loader2, Search, Image, ExternalLink, CheckCircle, XCircle, Info, Zap, RefreshCw, Download, Database, Link, Package } from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const SUPPORTED_SUPPLIERS = [
  { name: 'Tile Rite', value: 'Tile Rite', website: 'https://www.tilerite.co.uk' },
  { name: 'Trimline', value: 'Trimline', website: 'https://shop.trimlinegroup.com' },
  { name: 'Ultra Tile', value: 'Ultra Tile', website: 'https://www.instarmac.co.uk/products/ultratile/' },
];

export default function ImageScraper() {
  const [supplier, setSupplier] = useState('');
  const [sku, setSku] = useState('');
  const [productName, setProductName] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  
  // Bulk scrape state
  const [bulkSupplier, setBulkSupplier] = useState('');
  const [bulkLimit, setBulkLimit] = useState(50);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkJobId, setBulkJobId] = useState(null);
  const [bulkStatus, setBulkStatus] = useState(null);
  
  // Scrape all state
  const [scrapeAllLoading, setScrapeAllLoading] = useState(false);
  const [scrapeAllJobId, setScrapeAllJobId] = useState(null);
  const [scrapeAllStatus, setScrapeAllStatus] = useState(null);
  
  // Product stats state
  const [productStats, setProductStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(false);
  
  // Download and Link state
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [productSearch, setProductSearch] = useState(null);
  const [linkSuccess, setLinkSuccess] = useState(null);
  
  // Fetch product stats on mount
  useEffect(() => {
    fetchProductStats();
  }, []);
  
  const fetchProductStats = async () => {
    setStatsLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/scraper/products-status`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setProductStats(data);
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    } finally {
      setStatsLoading(false);
    }
  };

  const handleScrape = async () => {
    if (!supplier || !sku) {
      toast.error('Please select a supplier and enter a SKU');
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/scraper/single`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          supplier_name: supplier,
          sku: sku,
          product_name: productName
        })
      });

      if (!response.ok) {
        throw new Error('Failed to scrape product');
      }

      const data = await response.json();
      setResult(data);
      
      if (data.success) {
        toast.success(`Found ${data.images.length} images for ${sku}`);
      } else {
        toast.warning(data.error || 'No images found');
      }
    } catch (error) {
      toast.error('Failed to scrape: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  // Poll for bulk job status
  const checkBulkJobStatus = useCallback(async (jobId) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/scraper/job/${jobId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (!response.ok) throw new Error('Failed to get job status');
      
      const data = await response.json();
      setBulkStatus(data);
      
      if (data.status === 'completed') {
        setBulkLoading(false);
        toast.success(`Bulk scrape complete! ${data.successful}/${data.total} products updated`);
      } else if (data.status === 'failed') {
        setBulkLoading(false);
        toast.error('Bulk scrape failed');
      }
      
      return data.status;
    } catch (error) {
      console.error('Error checking job status:', error);
      return null;
    }
  }, []);

  // Start bulk scrape
  const handleBulkScrape = async () => {
    if (!bulkSupplier) {
      toast.error('Please select a supplier');
      return;
    }

    setBulkLoading(true);
    setBulkStatus(null);
    setBulkJobId(null);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/scraper/scrape-by-supplier/${encodeURIComponent(bulkSupplier)}?limit=${bulkLimit}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to start bulk scrape');
      }

      const data = await response.json();
      
      if (data.message && data.message.includes('No products found')) {
        toast.info(data.message);
        setBulkLoading(false);
        return;
      }
      
      setBulkJobId(data.job_id);
      toast.success(`Started scraping ${data.products_found} products from ${bulkSupplier}`);
    } catch (error) {
      toast.error('Failed to start bulk scrape: ' + error.message);
      setBulkLoading(false);
    }
  };

  // Handle Scrape All Products
  const handleScrapeAll = async () => {
    setScrapeAllLoading(true);
    setScrapeAllStatus(null);
    setScrapeAllJobId(null);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/scraper/scrape-all?limit=500`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to start scrape all');
      }

      const data = await response.json();
      
      if (data.message && data.message.includes('No products found')) {
        toast.info(data.message);
        setScrapeAllLoading(false);
        return;
      }
      
      setScrapeAllJobId(data.job_id);
      toast.success(`Started scraping ${data.products_to_scrape} products (${data.products_skipped} skipped)`);
    } catch (error) {
      toast.error('Failed to start scrape: ' + error.message);
      setScrapeAllLoading(false);
    }
  };

  // Check scrape all job status
  const checkScrapeAllJobStatus = useCallback(async (jobId) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/scraper/job/${jobId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (!response.ok) throw new Error('Failed to get job status');
      
      const data = await response.json();
      setScrapeAllStatus(data);
      
      if (data.status === 'completed') {
        setScrapeAllLoading(false);
        toast.success(`Scrape all complete! ${data.successful}/${data.total} products updated`);
        fetchProductStats(); // Refresh stats
      } else if (data.status === 'failed') {
        setScrapeAllLoading(false);
        toast.error('Scrape all failed');
      }
      
      return data.status;
    } catch (error) {
      console.error('Error checking job status:', error);
      return null;
    }
  }, []);

  // Poll scrape all job status
  useEffect(() => {
    if (!scrapeAllJobId || !scrapeAllLoading) return;
    
    const interval = setInterval(async () => {
      const status = await checkScrapeAllJobStatus(scrapeAllJobId);
      if (status === 'completed' || status === 'failed') {
        clearInterval(interval);
      }
    }, 2000);

    checkScrapeAllJobStatus(scrapeAllJobId);

    return () => clearInterval(interval);
  }, [scrapeAllJobId, scrapeAllLoading, checkScrapeAllJobStatus]);

  // Export products
  const handleExport = async (format) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/products/export/${format}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (!response.ok) throw new Error('Export failed');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `products_backup.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success(`Products exported as ${format.toUpperCase()}`);
    } catch (error) {
      toast.error('Export failed: ' + error.message);
    }
  };

  // Poll job status when we have a job ID
  useEffect(() => {
    if (!bulkJobId || !bulkLoading) return;
    
    const interval = setInterval(async () => {
      const status = await checkBulkJobStatus(bulkJobId);
      if (status === 'completed' || status === 'failed') {
        clearInterval(interval);
      }
    }, 2000);

    // Initial check
    checkBulkJobStatus(bulkJobId);

    return () => clearInterval(interval);
  }, [bulkJobId, bulkLoading, checkBulkJobStatus]);

  // Find product by SKU when scrape result changes
  useEffect(() => {
    const findProduct = async () => {
      if (!result?.success || !result?.sku) {
        setProductSearch(null);
        setLinkSuccess(null);
        return;
      }
      
      try {
        const token = localStorage.getItem('token');
        const response = await fetch(`${API_URL}/api/scraper/find-product/${encodeURIComponent(result.sku)}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
          const data = await response.json();
          setProductSearch(data);
        }
      } catch (error) {
        console.error('Error finding product:', error);
        setProductSearch({ found: false, message: 'Error searching for product' });
      }
    };
    
    findProduct();
  }, [result]);

  // Download images and link to product
  const handleDownloadAndLink = async () => {
    if (!result?.success || !result?.images?.length) {
      toast.error('No images to download');
      return;
    }
    
    if (!productSearch?.found) {
      toast.error('No product found to link images to');
      return;
    }
    
    setDownloadLoading(true);
    setLinkSuccess(null);
    
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/scraper/download-and-link`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          sku: result.sku,
          image_urls: result.images,
          product_id: productSearch.product?.id
        })
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to download and link images');
      }
      
      const data = await response.json();
      setLinkSuccess(data);
      toast.success(`${data.downloaded_images?.length || 0} images downloaded and linked to "${data.product_name}"`);
      
      // Refresh product stats
      fetchProductStats();
    } catch (error) {
      toast.error('Failed to download and link: ' + error.message);
    } finally {
      setDownloadLoading(false);
    }
  };

  return (
    <div className="container mx-auto py-6 space-y-6" data-testid="image-scraper-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Image Scraper & Backup</h1>
          <p className="text-muted-foreground">
            Scrape product images and export your product data
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => handleExport('csv')} data-testid="export-csv-btn">
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
          <Button variant="outline" onClick={() => handleExport('json')} data-testid="export-json-btn">
            <Download className="mr-2 h-4 w-4" />
            Export JSON
          </Button>
        </div>
      </div>

      {/* Product Stats Card */}
      <Card className="bg-gradient-to-r from-slate-50 to-slate-100 border-slate-200">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Database className="h-5 w-5 text-slate-600" />
            Product Overview
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={fetchProductStats}
              disabled={statsLoading}
            >
              <RefreshCw className={`h-4 w-4 ${statsLoading ? 'animate-spin' : ''}`} />
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {productStats ? (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="text-center p-3 bg-white rounded-lg border">
                <div className="text-2xl font-bold text-slate-800">{productStats.total_products}</div>
                <div className="text-xs text-muted-foreground">Total Products</div>
              </div>
              <div className="text-center p-3 bg-white rounded-lg border">
                <div className="text-2xl font-bold text-green-600">{productStats.with_images}</div>
                <div className="text-xs text-muted-foreground">With Images</div>
              </div>
              <div className="text-center p-3 bg-white rounded-lg border">
                <div className="text-2xl font-bold text-amber-600">{productStats.without_images}</div>
                <div className="text-xs text-muted-foreground">Without Images</div>
              </div>
              <div className="text-center p-3 bg-white rounded-lg border">
                <div className="text-2xl font-bold text-blue-600">{productStats.scrapable}</div>
                <div className="text-xs text-muted-foreground">Scrapable</div>
              </div>
              <div className="text-center p-3 bg-white rounded-lg border">
                <div className="text-2xl font-bold text-red-600">{productStats.not_scrapable}</div>
                <div className="text-xs text-muted-foreground">Not Scrapable</div>
              </div>
            </div>
          ) : (
            <div className="text-center py-4 text-muted-foreground">
              {statsLoading ? 'Loading stats...' : 'Failed to load stats'}
            </div>
          )}
          
          {productStats?.scrapable_by_supplier && productStats.scrapable_by_supplier.length > 0 && (
            <div className="mt-4 pt-4 border-t">
              <p className="text-sm font-medium mb-2">Scrapable by Supplier:</p>
              <div className="flex flex-wrap gap-2">
                {productStats.scrapable_by_supplier.map((s, idx) => (
                  <Badge key={idx} variant="secondary">
                    {s.supplier}: {s.count}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Scrape ALL Products Card */}
      {productStats?.scrapable > 0 && (
        <Card className="border-green-200 bg-green-50/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-green-600" />
              Scrape All Products Without Images
            </CardTitle>
            <CardDescription>
              Automatically scrape images for all {productStats.scrapable} products that don't have images.
              Supplier is auto-detected from SKU patterns.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button 
              onClick={handleScrapeAll} 
              disabled={scrapeAllLoading}
              className="bg-green-600 hover:bg-green-700"
              data-testid="scrape-all-button"
            >
              {scrapeAllLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Scraping All Products...
                </>
              ) : (
                <>
                  <Zap className="mr-2 h-4 w-4" />
                  Scrape All {productStats.scrapable} Products
                </>
              )}
            </Button>

            {/* Scrape All Progress */}
            {scrapeAllStatus && (
              <div className="mt-4 p-4 bg-white rounded-lg border space-y-3" data-testid="scrape-all-status">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {scrapeAllStatus.status === 'running' && (
                      <RefreshCw className="h-4 w-4 animate-spin text-green-600" />
                    )}
                    {scrapeAllStatus.status === 'completed' && (
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    )}
                    {scrapeAllStatus.status === 'failed' && (
                      <XCircle className="h-4 w-4 text-red-600" />
                    )}
                    <span className="font-medium capitalize">{scrapeAllStatus.status}</span>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {scrapeAllStatus.processed} / {scrapeAllStatus.total} processed
                  </div>
                </div>
                
                <Progress 
                  value={(scrapeAllStatus.processed / scrapeAllStatus.total) * 100} 
                  className="h-2"
                />
                
                <div className="flex gap-4 text-sm">
                  <span className="text-green-600 flex items-center gap-1">
                    <CheckCircle className="h-3 w-3" />
                    {scrapeAllStatus.successful} successful
                  </span>
                  <span className="text-red-600 flex items-center gap-1">
                    <XCircle className="h-3 w-3" />
                    {scrapeAllStatus.failed} failed
                  </span>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Info Card */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="flex items-start gap-3 pt-4">
          <Info className="h-5 w-5 text-blue-600 mt-0.5" />
          <div className="text-sm text-blue-800">
            <p className="font-medium mb-1">Supported Suppliers</p>
            <p>
              This tool can scrape product images from Tile Rite, Trimline, and Ultra Tile (Instarmac) websites.
              Enter the product SKU as it appears on the supplier's website for best results.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Scrape Form */}
      <Card>
        <CardHeader>
          <CardTitle>Scrape Product Images</CardTitle>
          <CardDescription>
            Enter product details to scrape images from supplier website
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="supplier">Supplier</Label>
              <Select value={supplier} onValueChange={setSupplier}>
                <SelectTrigger id="supplier" data-testid="supplier-select">
                  <SelectValue placeholder="Select supplier" />
                </SelectTrigger>
                <SelectContent>
                  {SUPPORTED_SUPPLIERS.map(s => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="sku">Product SKU / Code</Label>
              <Input
                id="sku"
                value={sku}
                onChange={(e) => setSku(e.target.value)}
                placeholder="e.g., BGL596"
                data-testid="sku-input"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="productName">Product Name (optional)</Label>
              <Input
                id="productName"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                placeholder="e.g., 12MM LSHAPE BRIGHT GOLD"
                data-testid="product-name-input"
              />
            </div>
          </div>

          <div className="flex items-center gap-4">
            <Button 
              onClick={handleScrape} 
              disabled={loading || !supplier || !sku}
              data-testid="scrape-button"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Scraping...
                </>
              ) : (
                <>
                  <Search className="mr-2 h-4 w-4" />
                  Scrape Images
                </>
              )}
            </Button>

            {supplier && (
              <a 
                href={SUPPORTED_SUPPLIERS.find(s => s.value === supplier)?.website}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-blue-600 hover:underline flex items-center gap-1"
              >
                Open {supplier} website <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {result && (
        <Card data-testid="scrape-results">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                Results for {result.sku}
                {result.success ? (
                  <Badge variant="default" className="bg-green-600">
                    <CheckCircle className="h-3 w-3 mr-1" /> Success
                  </Badge>
                ) : (
                  <Badge variant="destructive">
                    <XCircle className="h-3 w-3 mr-1" /> Not Found
                  </Badge>
                )}
              </CardTitle>
            </div>
            <CardDescription>
              {result.success 
                ? `Found ${result.images.length} image(s) from ${result.supplier}`
                : result.error || 'No images found'
              }
            </CardDescription>
          </CardHeader>
          {result.images && result.images.length > 0 && (
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {result.images.map((url, idx) => (
                  <div key={idx} className="relative group">
                    <div className="aspect-square bg-gray-100 rounded-lg overflow-hidden">
                      <img
                        src={url}
                        alt={`${result.sku} - ${idx + 1}`}
                        className="w-full h-full object-contain"
                        onError={(e) => {
                          e.target.src = '/placeholder-image.png';
                        }}
                      />
                    </div>
                    <div className="mt-2">
                      <a 
                        href={url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:underline break-all"
                      >
                        {url.length > 60 ? url.substring(0, 60) + '...' : url}
                      </a>
                    </div>
                  </div>
                ))}
              </div>

              {result.product_url && (
                <div className="pt-4 border-t">
                  <Label className="text-sm text-muted-foreground">Product Page:</Label>
                  <a 
                    href={result.product_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:underline flex items-center gap-1 mt-1"
                  >
                    {result.product_url} <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}

              {/* Download & Link to Product Section */}
              <div className="pt-4 border-t">
                <div className="flex items-center gap-2 mb-3">
                  <Package className="h-5 w-5 text-blue-600" />
                  <span className="font-medium">Link to Existing Product</span>
                </div>
                
                {productSearch === null ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Searching for product...
                  </div>
                ) : productSearch?.found ? (
                  <div className="space-y-3">
                    <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                      <div className="flex items-center gap-2 text-green-700 mb-1">
                        <CheckCircle className="h-4 w-4" />
                        <span className="font-medium">Product Found</span>
                      </div>
                      <div className="text-sm text-green-600">
                        <p><strong>Name:</strong> {productSearch.product?.name}</p>
                        <p><strong>SKU:</strong> {productSearch.product?.sku}</p>
                        <p><strong>Current Images:</strong> {productSearch.product?.existing_images || 0}</p>
                      </div>
                    </div>
                    
                    {linkSuccess ? (
                      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                        <div className="flex items-center gap-2 text-blue-700 mb-1">
                          <CheckCircle className="h-4 w-4" />
                          <span className="font-medium">Images Linked Successfully!</span>
                        </div>
                        <div className="text-sm text-blue-600">
                          <p>{linkSuccess.downloaded_images?.length || 0} images downloaded and linked</p>
                          <p>Total images on product: {linkSuccess.total_images}</p>
                        </div>
                      </div>
                    ) : (
                      <Button
                        onClick={handleDownloadAndLink}
                        disabled={downloadLoading}
                        className="w-full bg-blue-600 hover:bg-blue-700"
                        data-testid="download-link-btn"
                      >
                        {downloadLoading ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Downloading & Linking...
                          </>
                        ) : (
                          <>
                            <Link className="mr-2 h-4 w-4" />
                            Download & Link to "{productSearch.product?.name}"
                          </>
                        )}
                      </Button>
                    )}
                  </div>
                ) : (
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                    <div className="flex items-center gap-2 text-amber-700 mb-1">
                      <Info className="h-4 w-4" />
                      <span className="font-medium">Product Not Found</span>
                    </div>
                    <p className="text-sm text-amber-600">
                      No product found with SKU "{result.sku}". Please add the product first, then scrape images again.
                    </p>
                  </div>
                )}
              </div>
            </CardContent>
          )}
        </Card>
      )}

      {/* Bulk Scrape Card */}
      <Card className="border-orange-200 bg-orange-50/30">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-orange-600" />
            Bulk Scrape Products
          </CardTitle>
          <CardDescription>
            Automatically scrape images for all products from a supplier that don't have images yet
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="bulkSupplier">Supplier</Label>
              <Select value={bulkSupplier} onValueChange={setBulkSupplier}>
                <SelectTrigger id="bulkSupplier" data-testid="bulk-supplier-select">
                  <SelectValue placeholder="Select supplier" />
                </SelectTrigger>
                <SelectContent>
                  {SUPPORTED_SUPPLIERS.map(s => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="bulkLimit">Max Products to Scrape</Label>
              <Select value={bulkLimit.toString()} onValueChange={(v) => setBulkLimit(parseInt(v))}>
                <SelectTrigger id="bulkLimit" data-testid="bulk-limit-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10 products</SelectItem>
                  <SelectItem value="25">25 products</SelectItem>
                  <SelectItem value="50">50 products</SelectItem>
                  <SelectItem value="100">100 products</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2 flex items-end">
              <Button 
                onClick={handleBulkScrape} 
                disabled={bulkLoading || !bulkSupplier}
                className="w-full bg-orange-600 hover:bg-orange-700"
                data-testid="bulk-scrape-button"
              >
                {bulkLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Scraping...
                  </>
                ) : (
                  <>
                    <Zap className="mr-2 h-4 w-4" />
                    Start Bulk Scrape
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Bulk Scrape Progress */}
          {bulkStatus && (
            <div className="mt-4 p-4 bg-white rounded-lg border space-y-3" data-testid="bulk-scrape-status">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {bulkStatus.status === 'running' && (
                    <RefreshCw className="h-4 w-4 animate-spin text-orange-600" />
                  )}
                  {bulkStatus.status === 'completed' && (
                    <CheckCircle className="h-4 w-4 text-green-600" />
                  )}
                  {bulkStatus.status === 'failed' && (
                    <XCircle className="h-4 w-4 text-red-600" />
                  )}
                  <span className="font-medium capitalize">{bulkStatus.status}</span>
                </div>
                <div className="text-sm text-muted-foreground">
                  {bulkStatus.processed} / {bulkStatus.total} processed
                </div>
              </div>
              
              <Progress 
                value={(bulkStatus.processed / bulkStatus.total) * 100} 
                className="h-2"
              />
              
              <div className="flex gap-4 text-sm">
                <span className="text-green-600 flex items-center gap-1">
                  <CheckCircle className="h-3 w-3" />
                  {bulkStatus.successful} successful
                </span>
                <span className="text-red-600 flex items-center gap-1">
                  <XCircle className="h-3 w-3" />
                  {bulkStatus.failed} failed
                </span>
              </div>

              {bulkStatus.status === 'completed' && bulkStatus.results && bulkStatus.results.length > 0 && (
                <div className="mt-2 pt-2 border-t">
                  <p className="text-sm font-medium mb-2">Recent Results:</p>
                  <div className="max-h-40 overflow-y-auto space-y-1">
                    {bulkStatus.results.slice(0, 10).map((r, idx) => (
                      <div key={idx} className="text-xs flex items-center gap-2">
                        {r.success ? (
                          <CheckCircle className="h-3 w-3 text-green-600 flex-shrink-0" />
                        ) : (
                          <XCircle className="h-3 w-3 text-red-600 flex-shrink-0" />
                        )}
                        <span className="font-mono">{r.sku}</span>
                        {r.success && <span className="text-muted-foreground">({r.images?.length || 0} images)</span>}
                        {!r.success && <span className="text-red-500 truncate">{r.error}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Supported Suppliers List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Image className="h-5 w-5" />
            Supported Suppliers
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {SUPPORTED_SUPPLIERS.map(s => (
              <div key={s.value} className="p-4 border rounded-lg">
                <h3 className="font-medium">{s.name}</h3>
                <a 
                  href={s.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:underline flex items-center gap-1 mt-1"
                >
                  {s.website.replace('https://', '').replace('www.', '')}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
