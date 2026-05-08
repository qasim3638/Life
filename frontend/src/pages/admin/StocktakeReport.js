import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { 
  ClipboardList, Download, RefreshCw, Building2, 
  Package, PoundSterling, Filter, ChevronDown, ChevronUp,
  FileSpreadsheet
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';

const StocktakeReport = () => {
  const [loading, setLoading] = useState(true);
  const [stockData, setStockData] = useState(null);
  const [showrooms, setShowrooms] = useState([]);
  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);
  
  // Filters
  const [supplierFilter, setSupplierFilter] = useState('');
  const [showroomFilter, setShowroomFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  
  // Expanded sections
  const [expandedSuppliers, setExpandedSuppliers] = useState(new Set());

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [stockRes, showroomsRes, categoriesRes, productsRes] = await Promise.all([
        api.get('/reports/stock-value'),
        api.get('/showrooms'),
        api.get('/categories'),
        api.get('/products?limit=5000')
      ]);
      
      setStockData(stockRes.data);
      setShowrooms(showroomsRes.data || []);
      setCategories(categoriesRes.data || []);
      
      const prods = productsRes.data?.products || productsRes.data || [];
      setProducts(prods);
    } catch (error) {
      console.error('Error loading data:', error);
      toast.error('Failed to load stock data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Filter products
  const filteredProducts = products.filter(p => {
    if (supplierFilter && !p.supplier_name?.toLowerCase().includes(supplierFilter.toLowerCase())) {
      return false;
    }
    if (categoryFilter && p.category_id !== categoryFilter) {
      return false;
    }
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      if (!p.name?.toLowerCase().includes(search) && !p.sku?.toLowerCase().includes(search)) {
        return false;
      }
    }
    if (showroomFilter) {
      const showroomStock = p.showroom_stock || {};
      let stockInShowroom = 0;
      if (Array.isArray(showroomStock)) {
        const found = showroomStock.find(s => s.showroom_id === showroomFilter);
        stockInShowroom = found?.quantity || 0;
      } else {
        stockInShowroom = showroomStock[showroomFilter] || 0;
      }
      if (stockInShowroom <= 0) return false;
    }
    return true;
  });

  // Group by supplier
  const groupedBySupplier = filteredProducts.reduce((acc, p) => {
    const supplier = p.supplier_name || 'Unknown';
    if (!acc[supplier]) {
      acc[supplier] = { items: [], totalStock: 0, totalCostValue: 0, totalRetailValue: 0 };
    }
    acc[supplier].items.push(p);
    acc[supplier].totalStock += p.stock || 0;
    acc[supplier].totalCostValue += (p.stock || 0) * (p.cost_price || 0);
    acc[supplier].totalRetailValue += (p.stock || 0) * (p.price || 0);
    return acc;
  }, {});

  // Calculate totals
  const totals = {
    products: filteredProducts.length,
    stock: filteredProducts.reduce((sum, p) => sum + (p.stock || 0), 0),
    costValue: filteredProducts.reduce((sum, p) => sum + ((p.stock || 0) * (p.cost_price || 0)), 0),
    retailValue: filteredProducts.reduce((sum, p) => sum + ((p.stock || 0) * (p.price || 0)), 0)
  };

  const toggleSupplier = (supplier) => {
    setExpandedSuppliers(prev => {
      const next = new Set(prev);
      if (next.has(supplier)) {
        next.delete(supplier);
      } else {
        next.add(supplier);
      }
      return next;
    });
  };

  const expandAll = () => {
    setExpandedSuppliers(new Set(Object.keys(groupedBySupplier)));
  };

  const collapseAll = () => {
    setExpandedSuppliers(new Set());
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(amount || 0);
  };

  const getShowroomStock = (product, showroomId) => {
    const stock = product.showroom_stock || {};
    if (Array.isArray(stock)) {
      const found = stock.find(s => s.showroom_id === showroomId);
      return found?.quantity || 0;
    }
    return stock[showroomId] || 0;
  };

  // Export to CSV
  const exportCSV = () => {
    const rows = [
      ['Supplier', 'SKU', 'Product Name', 'Category', 'Stock', 'Cost Price', 'Retail Price', 'Cost Value', 'Retail Value', ...showrooms.map(s => s.name)]
    ];
    
    filteredProducts.forEach(p => {
      const costValue = (p.stock || 0) * (p.cost_price || 0);
      const retailValue = (p.stock || 0) * (p.price || 0);
      const showroomStocks = showrooms.map(s => getShowroomStock(p, s.id));
      
      rows.push([
        p.supplier_name || 'Unknown',
        p.sku || '',
        p.name || '',
        p.category_name || '',
        p.stock || 0,
        p.cost_price || 0,
        p.price || 0,
        costValue.toFixed(2),
        retailValue.toFixed(2),
        ...showroomStocks
      ]);
    });
    
    // Add totals row
    rows.push([]);
    rows.push(['TOTALS', '', '', '', totals.stock, '', '', totals.costValue.toFixed(2), totals.retailValue.toFixed(2)]);
    
    const csvContent = rows.map(row => 
      row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')
    ).join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `stocktake_report_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    
    toast.success('Report exported');
  };

  // Unique suppliers for filter
  const uniqueSuppliers = [...new Set(products.map(p => p.supplier_name).filter(Boolean))].sort();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="stocktake-loading">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="stocktake-report-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-heading font-bold tracking-tight">Stocktake Report</h1>
          <p className="text-muted-foreground">Complete inventory overview by supplier, category, and showroom</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadData}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={exportCSV} data-testid="export-btn">
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground mb-1">
              <Package className="h-4 w-4" />
              <span className="text-sm">Products</span>
            </div>
            <div className="text-2xl font-bold">{totals.products.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground mb-1">
              <ClipboardList className="h-4 w-4" />
              <span className="text-sm">Total Stock</span>
            </div>
            <div className="text-2xl font-bold">{totals.stock.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground mb-1">
              <PoundSterling className="h-4 w-4" />
              <span className="text-sm">Cost Value</span>
            </div>
            <div className="text-2xl font-bold text-blue-600">{formatCurrency(totals.costValue)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground mb-1">
              <PoundSterling className="h-4 w-4" />
              <span className="text-sm">Retail Value</span>
            </div>
            <div className="text-2xl font-bold text-green-600">{formatCurrency(totals.retailValue)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="lg:col-span-2">
              <Input
                type="text"
                placeholder="Search by name or SKU..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                data-testid="search-input"
              />
            </div>
            <select
              value={supplierFilter}
              onChange={(e) => setSupplierFilter(e.target.value)}
              className="h-10 px-3 rounded-md border border-input bg-background text-sm"
              data-testid="supplier-filter"
            >
              <option value="">All Suppliers</option>
              {uniqueSuppliers.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="h-10 px-3 rounded-md border border-input bg-background text-sm"
              data-testid="category-filter"
            >
              <option value="">All Categories</option>
              {categories.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <select
              value={showroomFilter}
              onChange={(e) => setShowroomFilter(e.target.value)}
              className="h-10 px-3 rounded-md border border-input bg-background text-sm"
              data-testid="showroom-filter"
            >
              <option value="">All Showrooms</option>
              {showrooms.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center justify-between mt-4">
            <span className="text-sm text-muted-foreground">
              Showing {filteredProducts.length} of {products.length} products
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={expandAll}>
                <ChevronDown className="h-4 w-4 mr-1" /> Expand All
              </Button>
              <Button variant="outline" size="sm" onClick={collapseAll}>
                <ChevronUp className="h-4 w-4 mr-1" /> Collapse All
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stock by Supplier */}
      <div className="space-y-4">
        {Object.entries(groupedBySupplier)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([supplier, data]) => {
            const isExpanded = expandedSuppliers.has(supplier);
            
            return (
              <Card key={supplier} className="overflow-hidden">
                <div
                  className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-muted/50"
                  onClick={() => toggleSupplier(supplier)}
                  data-testid={`supplier-header-${supplier}`}
                >
                  <div className="flex items-center gap-3">
                    <Building2 className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <h3 className="font-semibold">{supplier}</h3>
                      <p className="text-sm text-muted-foreground">
                        {data.items.length} products | {data.totalStock.toLocaleString()} units
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <div className="text-sm text-muted-foreground">Cost Value</div>
                      <div className="font-semibold text-blue-600">{formatCurrency(data.totalCostValue)}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm text-muted-foreground">Retail Value</div>
                      <div className="font-semibold text-green-600">{formatCurrency(data.totalRetailValue)}</div>
                    </div>
                    {isExpanded ? (
                      <ChevronUp className="h-5 w-5 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-5 w-5 text-muted-foreground" />
                    )}
                  </div>
                </div>
                
                {isExpanded && (
                  <div className="border-t">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-muted/30">
                          <tr>
                            <th className="text-left py-2 px-3 font-medium">SKU</th>
                            <th className="text-left py-2 px-3 font-medium">Product</th>
                            <th className="text-right py-2 px-3 font-medium">Stock</th>
                            <th className="text-right py-2 px-3 font-medium">Cost</th>
                            <th className="text-right py-2 px-3 font-medium">Retail</th>
                            <th className="text-right py-2 px-3 font-medium">Cost Value</th>
                            {showrooms.map(s => (
                              <th key={s.id} className="text-right py-2 px-3 font-medium">{s.name}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {data.items.map(product => (
                            <tr key={product.id} className="border-b border-muted/30 hover:bg-muted/20">
                              <td className="py-2 px-3 font-mono text-xs">{product.sku}</td>
                              <td className="py-2 px-3">{product.name}</td>
                              <td className="py-2 px-3 text-right font-medium">{product.stock || 0}</td>
                              <td className="py-2 px-3 text-right">{formatCurrency(product.cost_price)}</td>
                              <td className="py-2 px-3 text-right">{formatCurrency(product.price)}</td>
                              <td className="py-2 px-3 text-right font-medium text-blue-600">
                                {formatCurrency((product.stock || 0) * (product.cost_price || 0))}
                              </td>
                              {showrooms.map(s => (
                                <td key={s.id} className="py-2 px-3 text-right">
                                  {getShowroomStock(product, s.id) || '-'}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
      </div>

      {filteredProducts.length === 0 && (
        <Card>
          <CardContent className="py-12">
            <div className="text-center text-muted-foreground">
              <Package className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p>No products match your filters</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default StocktakeReport;
