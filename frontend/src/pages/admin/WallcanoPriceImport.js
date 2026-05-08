import React, { useState, useEffect, useRef } from 'react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { 
  Upload, 
  Download, 
  FileSpreadsheet, 
  CheckCircle, 
  XCircle, 
  AlertCircle,
  RefreshCw,
  DollarSign,
  Package,
  Search
} from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function WallcanoPriceImport() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [priceSummary, setPriceSummary] = useState(null);
  const [filter, setFilter] = useState('all'); // all, with_price, without_price
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchProducts();
  }, [filter, currentPage]);

  const fetchProducts = async () => {
    setLoading(true);
    try {
      let url = `${API_URL}/api/supplier-sync/wallcano/products?page=${currentPage}&per_page=50`;
      if (filter === 'with_price') {
        url += '&has_price=true';
      } else if (filter === 'without_price') {
        url += '&has_price=false';
      }
      
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        setProducts(data.products || []);
        setPriceSummary(data.price_summary);
        setTotalPages(data.total_pages || 1);
      }
    } catch (error) {
      console.error('Error fetching products:', error);
      toast.error('Failed to fetch products');
    } finally {
      setLoading(false);
    }
  };

  const handleExportCSV = async () => {
    try {
      const response = await fetch(`${API_URL}/api/supplier-sync/wallcano/export-for-pricing`);
      if (response.ok) {
        const data = await response.json();
        
        // Create and download CSV file
        const blob = new Blob([data.csv_content], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `wallcano_products_for_pricing_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        toast.success(`Exported ${data.total_products} products`);
      } else {
        toast.error('Failed to export products');
      }
    } catch (error) {
      console.error('Error exporting:', error);
      toast.error('Export failed');
    }
  };

  const handleFileSelect = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file type
    const validTypes = ['.csv', '.xlsx', '.xls'];
    const fileExt = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    if (!validTypes.includes(fileExt)) {
      toast.error('Please upload a CSV or Excel file (.csv, .xlsx, .xls)');
      return;
    }

    setUploading(true);
    setImportResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${API_URL}/api/supplier-sync/wallcano/import-prices`, {
        method: 'POST',
        body: formData
      });

      const result = await response.json();

      if (response.ok) {
        setImportResult(result);
        toast.success(`Updated prices for ${result.updated} products`);
        fetchProducts(); // Refresh the list
      } else {
        toast.error(result.detail || 'Import failed');
        setImportResult({ error: result.detail });
      }
    } catch (error) {
      console.error('Error importing:', error);
      toast.error('Import failed');
      setImportResult({ error: error.message });
    } finally {
      setUploading(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const filteredProducts = products.filter(p => 
    !searchTerm || 
    p.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.sku?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6" data-testid="wallcano-price-import">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Wallcano Price Import</h1>
          <p className="text-muted-foreground">Import cost prices for Wallcano products from CSV or Excel</p>
        </div>
        <Button onClick={fetchProducts} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Products</p>
                <p className="text-2xl font-bold">{(priceSummary?.with_price || 0) + (priceSummary?.without_price || 0)}</p>
              </div>
              <Package className="h-8 w-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">With Price</p>
                <p className="text-2xl font-bold text-green-600">{priceSummary?.with_price || 0}</p>
              </div>
              <CheckCircle className="h-8 w-8 text-green-500" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Without Price</p>
                <p className="text-2xl font-bold text-orange-600">{priceSummary?.without_price || 0}</p>
              </div>
              <AlertCircle className="h-8 w-8 text-orange-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Import/Export Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5" />
            Price Import
          </CardTitle>
          <CardDescription>
            Export products to CSV, add prices in Excel/Google Sheets, then import back
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Step 1: Export */}
            <div className="flex-1 p-4 border rounded-lg bg-muted/30">
              <div className="flex items-center gap-2 mb-2">
                <span className="bg-primary text-primary-foreground rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium">1</span>
                <h3 className="font-medium">Export Products</h3>
              </div>
              <p className="text-sm text-muted-foreground mb-3">
                Download CSV with all Wallcano products. Fill in the "Cost Price" column.
              </p>
              <Button onClick={handleExportCSV} variant="outline" className="w-full">
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            </div>

            {/* Step 2: Import */}
            <div className="flex-1 p-4 border rounded-lg bg-muted/30">
              <div className="flex items-center gap-2 mb-2">
                <span className="bg-primary text-primary-foreground rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium">2</span>
                <h3 className="font-medium">Import Prices</h3>
              </div>
              <p className="text-sm text-muted-foreground mb-3">
                Upload the CSV/Excel file with filled prices to update products.
              </p>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept=".csv,.xlsx,.xls"
                className="hidden"
                data-testid="file-input"
              />
              <Button 
                onClick={() => fileInputRef.current?.click()} 
                disabled={uploading}
                className="w-full"
              >
                {uploading ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    Importing...
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4 mr-2" />
                    Import Prices
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Import Result */}
          {importResult && (
            <div className={`p-4 rounded-lg ${importResult.error ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'} border`}>
              {importResult.error ? (
                <div className="flex items-center gap-2 text-red-700">
                  <XCircle className="h-5 w-5" />
                  <span>{importResult.error}</span>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-green-700">
                    <CheckCircle className="h-5 w-5" />
                    <span className="font-medium">Import Complete</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">Updated:</span>
                      <span className="ml-1 font-medium text-green-600">{importResult.updated}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Skipped:</span>
                      <span className="ml-1 font-medium">{importResult.skipped}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Not Found:</span>
                      <span className="ml-1 font-medium text-orange-600">{importResult.not_found}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Errors:</span>
                      <span className="ml-1 font-medium text-red-600">{importResult.errors?.length || 0}</span>
                    </div>
                  </div>
                  {importResult.not_found_items?.length > 0 && (
                    <div className="text-sm text-orange-600">
                      Not found: {importResult.not_found_items.join(', ')}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Products Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row justify-between gap-4">
            <CardTitle>Products</CardTitle>
            <div className="flex gap-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search products..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-8 w-[200px]"
                />
              </div>
              <select
                value={filter}
                onChange={(e) => { setFilter(e.target.value); setCurrentPage(1); }}
                className="border rounded-md px-3 py-2 text-sm"
              >
                <option value="all">All Products</option>
                <option value="with_price">With Price</option>
                <option value="without_price">Without Price</option>
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : filteredProducts.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No products found
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-3 px-2 font-medium">SKU</th>
                      <th className="text-left py-3 px-2 font-medium">Name</th>
                      <th className="text-left py-3 px-2 font-medium">Category</th>
                      <th className="text-left py-3 px-2 font-medium">Size</th>
                      <th className="text-right py-3 px-2 font-medium">Stock (m²)</th>
                      <th className="text-right py-3 px-2 font-medium">Cost Price</th>
                      <th className="text-right py-3 px-2 font-medium">List Price</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredProducts.map((product, idx) => (
                      <tr key={product.sku || idx} className="border-b hover:bg-muted/50">
                        <td className="py-3 px-2 font-mono text-xs">{product.sku}</td>
                        <td className="py-3 px-2">{product.name}</td>
                        <td className="py-3 px-2 text-muted-foreground">{product.category}</td>
                        <td className="py-3 px-2">{product.size}</td>
                        <td className="py-3 px-2 text-right">{product.stock_m2?.toFixed(2) || '0.00'}</td>
                        <td className="py-3 px-2 text-right">
                          {product.cost_price ? (
                            <span className="text-green-600 font-medium">£{product.cost_price.toFixed(2)}</span>
                          ) : (
                            <span className="text-orange-500">-</span>
                          )}
                        </td>
                        <td className="py-3 px-2 text-right">
                          {product.price ? (
                            <span className="font-medium">£{product.price.toFixed(2)}</span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex justify-center gap-2 mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                  >
                    Previous
                  </Button>
                  <span className="flex items-center px-3 text-sm text-muted-foreground">
                    Page {currentPage} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                    disabled={currentPage === totalPages}
                  >
                    Next
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
