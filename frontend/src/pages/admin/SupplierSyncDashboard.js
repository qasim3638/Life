import React, { useState, useEffect } from 'react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { RefreshCw, Search, Download, Package, TrendingUp, Clock, CheckCircle } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function SupplierSyncDashboard() {
  const [products, setProducts] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalProducts, setTotalProducts] = useState(0);
  const productsPerPage = 50;

  useEffect(() => {
    fetchStats();
    fetchProducts();
  }, [currentPage, searchTerm]);

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/supplier-sync/verona/status`);
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const skip = (currentPage - 1) * productsPerPage;
      const url = `${API_URL}/api/supplier-sync/verona/products?skip=${skip}&limit=${productsPerPage}${searchTerm ? `&search=${encodeURIComponent(searchTerm)}` : ''}`;
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        setProducts(data.products || []);
        setTotalProducts(data.total || 0);
      }
    } catch (error) {
      console.error('Error fetching products:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e) => {
    setSearchTerm(e.target.value);
    setCurrentPage(1);
  };

  const exportCSV = () => {
    const headers = ['Name', 'SKU/Code', 'Price (£/m²)', 'Stock (units)', 'Stock (m²)', 'In Stock', 'Last Synced'];
    const rows = products.map(p => [
      p.name || '',
      p.sku || '',
      p.price || '',
      p.stock_quantity || '',
      p.stock_m2 || '',
      p.in_stock ? 'Yes' : 'No',
      p.synced_at || ''
    ]);
    
    const csvContent = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `verona-products-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  const totalPages = Math.ceil(totalProducts / productsPerPage);

  return (
    <div className="p-6 space-y-6" data-testid="supplier-sync-dashboard">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Supplier Sync Dashboard</h1>
          <p className="text-gray-500">Verona Group product sync status and data</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => { fetchStats(); fetchProducts(); }}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={exportCSV} disabled={products.length === 0}>
            <Download className="w-4 h-4 mr-2" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Total Products</p>
                <p className="text-3xl font-bold text-gray-900">{stats?.total_products || 0}</p>
              </div>
              <Package className="w-10 h-10 text-blue-500 opacity-50" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Last Sync</p>
                <p className="text-lg font-semibold text-gray-900">
                  {stats?.last_sync ? new Date(stats.last_sync).toLocaleString('en-GB') : 'Never'}
                </p>
              </div>
              <Clock className="w-10 h-10 text-green-500 opacity-50" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Last Batch</p>
                <p className="text-3xl font-bold text-gray-900">{stats?.last_sync_count || 0}</p>
                <p className="text-xs text-gray-400">products synced</p>
              </div>
              <TrendingUp className="w-10 h-10 text-purple-500 opacity-50" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">With Stock Data</p>
                <p className="text-3xl font-bold text-gray-900">
                  {products.filter(p => p.stock_quantity || p.price).length}
                </p>
                <p className="text-xs text-gray-400">of {products.length} on page</p>
              </div>
              <CheckCircle className="w-10 h-10 text-emerald-500 opacity-50" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Synced Products</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <Input
                placeholder="Search by name or SKU..."
                value={searchTerm}
                onChange={handleSearch}
                className="pl-10"
              />
            </div>
          </div>

          {loading ? (
            <div className="text-center py-10">
              <RefreshCw className="w-8 h-8 animate-spin mx-auto text-gray-400" />
              <p className="text-gray-500 mt-2">Loading products...</p>
            </div>
          ) : products.length === 0 ? (
            <div className="text-center py-10 bg-gray-50 rounded-lg">
              <Package className="w-12 h-12 mx-auto text-gray-300" />
              <p className="text-gray-500 mt-2">No products synced yet</p>
              <p className="text-sm text-gray-400">Use the browser extension to sync products from Verona</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b bg-gray-50">
                      <th className="text-left py-3 px-4 font-medium text-gray-600">Product</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-600">Code</th>
                      <th className="text-right py-3 px-4 font-medium text-gray-600">Price/m²</th>
                      <th className="text-right py-3 px-4 font-medium text-gray-600">Stock</th>
                      <th className="text-center py-3 px-4 font-medium text-gray-600">Status</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-600">Last Synced</th>
                    </tr>
                  </thead>
                  <tbody>
                    {products.map((product, idx) => (
                      <tr key={idx} className="border-b hover:bg-gray-50">
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-3">
                            {product.image && (
                              <img 
                                src={product.image} 
                                alt={product.name}
                                className="w-12 h-12 object-cover rounded"
                                onError={(e) => e.target.style.display = 'none'}
                              />
                            )}
                            <div>
                              <p className="font-medium text-gray-900 line-clamp-1">{product.name}</p>
                              {product.url && (
                                <a 
                                  href={product.url} 
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                  className="text-xs text-blue-500 hover:underline"
                                >
                                  View on Verona
                                </a>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-mono text-sm text-gray-600">{product.sku || '-'}</span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          {product.price ? (
                            <span className="font-semibold text-gray-900">£{product.price.toFixed(2)}</span>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {product.stock_quantity ? (
                            <div>
                              <span className="font-semibold text-gray-900">{product.stock_quantity.toLocaleString()}</span>
                              {product.stock_m2 && (
                                <span className="text-xs text-gray-500 block">{product.stock_m2}m²</span>
                              )}
                            </div>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center">
                          {product.in_stock === true ? (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">
                              In Stock
                            </span>
                          ) : product.in_stock === false ? (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
                              Out of Stock
                            </span>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-sm text-gray-500">
                          {product.synced_at ? new Date(product.synced_at).toLocaleString('en-GB') : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="flex items-center justify-between mt-4 pt-4 border-t">
                <p className="text-sm text-gray-500">
                  Showing {((currentPage - 1) * productsPerPage) + 1} - {Math.min(currentPage * productsPerPage, totalProducts)} of {totalProducts} products
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                  >
                    Previous
                  </Button>
                  <span className="px-3 py-1 text-sm text-gray-600">
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
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
