import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { 
  Download, RefreshCw, Package, AlertTriangle, 
  TrendingDown, Loader2, FileSpreadsheet, ChevronDown, ChevronUp
} from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const SUPPLIERS = [
  { value: 'all', label: 'All Suppliers' },
  { value: 'Tile Rite', label: 'Tile Rite' },
  { value: 'Ultra Tile', label: 'Ultra Tile' },
  { value: 'Trimline', label: 'Trimline' },
];

export default function ToOrderReport() {
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [selectedSupplier, setSelectedSupplier] = useState('all');
  const [expandedSuppliers, setExpandedSuppliers] = useState({});
  const [stockValueReport, setStockValueReport] = useState(null);

  useEffect(() => {
    const fetchReport = async () => {
      setLoading(true);
      try {
        const token = localStorage.getItem('token');
        const supplierParam = selectedSupplier !== 'all' ? `&supplier=${encodeURIComponent(selectedSupplier)}` : '';
        const response = await fetch(`${API_URL}/api/reports/to-order?include_zero_stock=true${supplierParam}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) throw new Error('Failed to fetch report');
        
        const data = await response.json();
        setReport(data);
        
        // Auto-expand all suppliers
        const expanded = {};
        data.reports?.forEach(r => { expanded[r.supplier] = true; });
        setExpandedSuppliers(expanded);
      } catch (error) {
        toast.error('Failed to load report: ' + error.message);
      } finally {
        setLoading(false);
      }
    };

    const fetchStockValue = async () => {
      try {
        const token = localStorage.getItem('token');
        const supplierParam = selectedSupplier !== 'all' ? `?supplier=${encodeURIComponent(selectedSupplier)}` : '';
        const response = await fetch(`${API_URL}/api/reports/stock-value${supplierParam}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
          const data = await response.json();
          setStockValueReport(data);
        }
      } catch (error) {
        console.error('Failed to fetch stock value:', error);
      }
    };

    fetchReport();
    fetchStockValue();
  }, [selectedSupplier]);

  const handleRefresh = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const supplierParam = selectedSupplier !== 'all' ? `&supplier=${encodeURIComponent(selectedSupplier)}` : '';
      const response = await fetch(`${API_URL}/api/reports/to-order?include_zero_stock=true${supplierParam}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (!response.ok) throw new Error('Failed to fetch report');
      
      const data = await response.json();
      setReport(data);
      
      const expanded = {};
      data.reports?.forEach(r => { expanded[r.supplier] = true; });
      setExpandedSuppliers(expanded);
      
      // Also refresh stock value
      const stockResponse = await fetch(`${API_URL}/api/reports/stock-value${selectedSupplier !== 'all' ? `?supplier=${encodeURIComponent(selectedSupplier)}` : ''}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (stockResponse.ok) {
        setStockValueReport(await stockResponse.json());
      }
    } catch (error) {
      toast.error('Failed to load report: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (format, supplier = null) => {
    try {
      const token = localStorage.getItem('token');
      const supplierParam = supplier ? `&supplier=${encodeURIComponent(supplier)}` : 
                           (selectedSupplier !== 'all' ? `&supplier=${encodeURIComponent(selectedSupplier)}` : '');
      
      const response = await fetch(`${API_URL}/api/reports/to-order/export?format=${format}${supplierParam}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (!response.ok) throw new Error('Export failed');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `to_order_${supplier || 'all'}_${new Date().toISOString().split('T')[0]}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success(`Report exported as ${format.toUpperCase()}`);
    } catch (error) {
      toast.error('Export failed: ' + error.message);
    }
  };

  const toggleSupplier = (supplier) => {
    setExpandedSuppliers(prev => ({
      ...prev,
      [supplier]: !prev[supplier]
    }));
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(value || 0);
  };

  return (
    <div className="container mx-auto py-6 space-y-6" data-testid="to-order-report-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Package className="h-8 w-8 text-orange-600" />
            Stock & Ordering Report
          </h1>
          <p className="text-muted-foreground">
            Products to order from Tile Rite, Ultra Tile, and Trimline
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={selectedSupplier} onValueChange={setSelectedSupplier}>
            <SelectTrigger className="w-[180px]" data-testid="supplier-filter">
              <SelectValue placeholder="Select supplier" />
            </SelectTrigger>
            <SelectContent>
              {SUPPLIERS.map(s => (
                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={handleRefresh} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button variant="outline" onClick={() => handleExport('csv')}>
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      {report && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Total Suppliers</p>
                  <p className="text-2xl font-bold">{report.total_suppliers}</p>
                </div>
                <Package className="h-8 w-8 text-blue-500" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Items to Order</p>
                  <p className="text-2xl font-bold text-orange-600">{report.total_items}</p>
                </div>
                <AlertTriangle className="h-8 w-8 text-orange-500" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Total Order Value</p>
                  <p className="text-2xl font-bold text-green-600">{formatCurrency(report.total_order_value)}</p>
                </div>
                <TrendingDown className="h-8 w-8 text-green-500" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Current Stock Value</p>
                  <p className="text-2xl font-bold">{formatCurrency(stockValueReport?.totals?.cost_value)}</p>
                </div>
                <FileSpreadsheet className="h-8 w-8 text-purple-500" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Content */}
      <Tabs defaultValue="to-order" className="space-y-4">
        <TabsList>
          <TabsTrigger value="to-order" className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            To Order
          </TabsTrigger>
          <TabsTrigger value="stock-value" className="flex items-center gap-2">
            <FileSpreadsheet className="h-4 w-4" />
            Stock Value
          </TabsTrigger>
        </TabsList>

        {/* To Order Tab */}
        <TabsContent value="to-order" className="space-y-4">
          {loading ? (
            <Card>
              <CardContent className="py-12 flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </CardContent>
            </Card>
          ) : report?.reports?.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Package className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-lg font-medium">No items need ordering</p>
                <p className="text-muted-foreground">All products are above their reorder levels</p>
              </CardContent>
            </Card>
          ) : (
            report?.reports?.map((supplierReport) => (
              <Card key={supplierReport.supplier} className="overflow-hidden">
                <CardHeader 
                  className="cursor-pointer hover:bg-muted/50 transition-colors"
                  onClick={() => toggleSupplier(supplierReport.supplier)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {expandedSuppliers[supplierReport.supplier] ? 
                        <ChevronUp className="h-5 w-5" /> : 
                        <ChevronDown className="h-5 w-5" />
                      }
                      <div>
                        <CardTitle className="text-xl">{supplierReport.supplier}</CardTitle>
                        <CardDescription>
                          {supplierReport.total_items} items • {formatCurrency(supplierReport.total_order_value)} estimated order value
                        </CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-lg px-3 py-1">
                        {supplierReport.total_items} items
                      </Badge>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleExport('csv', supplierReport.supplier);
                        }}
                      >
                        <Download className="h-4 w-4 mr-1" />
                        Export
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                
                {expandedSuppliers[supplierReport.supplier] && (
                  <CardContent className="p-0">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-muted/50">
                          <TableHead className="w-[120px]">SKU</TableHead>
                          <TableHead>Product Name</TableHead>
                          <TableHead className="text-center w-[100px]">Current Stock</TableHead>
                          <TableHead className="text-center w-[100px]">Reorder Level</TableHead>
                          <TableHead className="text-center w-[100px]">Qty to Order</TableHead>
                          <TableHead className="text-right w-[100px]">Cost</TableHead>
                          <TableHead className="text-right w-[120px]">Order Value</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {supplierReport.items.map((item) => (
                          <TableRow key={item.id} className={item.current_stock === 0 ? 'bg-red-50' : ''}>
                            <TableCell className="font-mono text-sm">{item.sku}</TableCell>
                            <TableCell>
                              <div className="max-w-[300px] truncate" title={item.name}>
                                {item.name}
                              </div>
                              {item.category_name && (
                                <span className="text-xs text-muted-foreground">{item.category_name}</span>
                              )}
                            </TableCell>
                            <TableCell className="text-center">
                              <Badge variant={item.current_stock === 0 ? 'destructive' : 'secondary'}>
                                {item.current_stock}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-center text-muted-foreground">
                              {item.reorder_level}
                            </TableCell>
                            <TableCell className="text-center">
                              <Badge className="bg-orange-600 hover:bg-orange-700">
                                {item.quantity_to_order}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right">
                              {formatCurrency(item.cost_price)}
                            </TableCell>
                            <TableCell className="text-right font-medium">
                              {formatCurrency(item.order_value)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    
                    {/* Supplier Total */}
                    <div className="p-4 bg-muted/30 border-t flex justify-between items-center">
                      <span className="font-medium">Supplier Total:</span>
                      <span className="text-xl font-bold text-green-600">
                        {formatCurrency(supplierReport.total_order_value)}
                      </span>
                    </div>
                  </CardContent>
                )}
              </Card>
            ))
          )}
        </TabsContent>

        {/* Stock Value Tab */}
        <TabsContent value="stock-value" className="space-y-4">
          {stockValueReport ? (
            <Card>
              <CardHeader>
                <CardTitle>Stock Value by Supplier</CardTitle>
                <CardDescription>Current inventory value at cost and retail prices</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Supplier</TableHead>
                      <TableHead className="text-right">Products</TableHead>
                      <TableHead className="text-right">Total Stock</TableHead>
                      <TableHead className="text-right">Cost Value</TableHead>
                      <TableHead className="text-right">Retail Value</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {stockValueReport.by_supplier?.map((row) => (
                      <TableRow key={row.supplier}>
                        <TableCell className="font-medium">{row.supplier}</TableCell>
                        <TableCell className="text-right">{row.total_products}</TableCell>
                        <TableCell className="text-right">{row.total_stock}</TableCell>
                        <TableCell className="text-right">{formatCurrency(row.cost_value)}</TableCell>
                        <TableCell className="text-right">{formatCurrency(row.retail_value)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                
                {/* Totals */}
                <div className="mt-4 p-4 bg-muted/30 rounded-lg">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                    <div>
                      <p className="text-sm text-muted-foreground">Total Products</p>
                      <p className="text-xl font-bold">{stockValueReport.totals?.total_products}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Total Stock Units</p>
                      <p className="text-xl font-bold">{stockValueReport.totals?.total_stock}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Total Cost Value</p>
                      <p className="text-xl font-bold text-blue-600">{formatCurrency(stockValueReport.totals?.total_cost_value)}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Total Retail Value</p>
                      <p className="text-xl font-bold text-green-600">{formatCurrency(stockValueReport.totals?.total_retail_value)}</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-12 flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
