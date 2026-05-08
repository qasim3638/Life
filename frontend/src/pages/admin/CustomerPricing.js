import React, { useEffect, useState, useRef } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { Users, Plus, Trash2, Tag, Upload, Download, FileSpreadsheet, CheckCircle2, XCircle, AlertCircle, FileDown } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card } from '../../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../../components/ui/dialog';

export const CustomerPricing = () => {
  const [customers, setCustomers] = useState([]);
  const [products, setProducts] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState('');
  const [selectedProduct, setSelectedProduct] = useState('');
  const [customPrice, setCustomPrice] = useState('');
  const [customerPricing, setCustomerPricing] = useState([]);
  const [open, setOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [exporting, setExporting] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [productsRes] = await Promise.all([
        api.getProducts(),
      ]);
      setProducts(productsRes.data);
      
      // Fetch all customers who have placed orders
      const ordersRes = await api.getOrders();
      const uniqueCustomers = [...new Set(ordersRes.data.map(o => o.customer_email))];
      setCustomers(uniqueCustomers.map(email => ({ email, name: ordersRes.data.find(o => o.customer_email === email)?.customer_name || email })));
    } catch (error) {
      toast.error('Failed to load data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchCustomerPricing = async (email) => {
    try {
      const response = await api.getCustomerPricing(email);
      setCustomerPricing(response.data);
    } catch (error) {
      console.error('Failed to load customer pricing', error);
      setCustomerPricing([]);
    }
  };

  const handleCustomerChange = (email) => {
    setSelectedCustomer(email);
    if (email) {
      fetchCustomerPricing(email);
    } else {
      setCustomerPricing([]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedCustomer || !selectedProduct || !customPrice) {
      toast.error('Please fill all fields');
      return;
    }

    try {
      await api.createCustomerPricing({
        customer_email: selectedCustomer,
        product_id: selectedProduct,
        custom_price: parseFloat(customPrice)
      });
      toast.success('Custom pricing set successfully');
      setSelectedProduct('');
      setCustomPrice('');
      setOpen(false);
      fetchCustomerPricing(selectedCustomer);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to set custom pricing');
    }
  };

  const handleDelete = async (pricingId) => {
    if (!window.confirm('Remove this custom pricing?')) return;
    
    try {
      await api.deleteCustomerPricing(pricingId);
      toast.success('Custom pricing removed');
      fetchCustomerPricing(selectedCustomer);
    } catch (error) {
      toast.error('Failed to remove custom pricing');
    }
  };

  const downloadTemplate = () => {
    // Create CSV template with product IDs
    const headers = ['customer_email', 'product_id', 'custom_price'];
    const exampleRows = products.slice(0, 3).map(p => 
      `customer@example.com,${p.id},${(p.price * 0.9).toFixed(2)}`
    );
    
    const csvContent = [
      headers.join(','),
      '# Example rows below (remove these and add your own):',
      ...exampleRows,
      '',
      '# Available Product IDs:',
      ...products.map(p => `# ${p.id} - ${p.name} (SKU: ${p.sku}) - Regular Price: £${p.price.toFixed(2)}`)
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'customer_pricing_template.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    toast.success('Template downloaded!');
  };

  const parseCSV = (text) => {
    const lines = text.split('\n').filter(line => line.trim() && !line.trim().startsWith('#'));
    const items = [];
    
    // Skip header row
    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(',').map(v => v.trim());
      if (values.length >= 3) {
        items.push({
          customer_email: values[0],
          product_id: values[1],
          custom_price: parseFloat(values[2])
        });
      }
    }
    
    return items;
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImporting(true);
    setImportResult(null);

    try {
      const text = await file.text();
      const items = parseCSV(text);

      if (items.length === 0) {
        toast.error('No valid data found in CSV file');
        setImporting(false);
        return;
      }

      const response = await api.bulkImportPricing(items);
      setImportResult(response.data);
      
      if (response.data.successful > 0) {
        toast.success(`Successfully imported ${response.data.successful} pricing entries`);
        // Refresh current customer pricing if one is selected
        if (selectedCustomer) {
          fetchCustomerPricing(selectedCustomer);
        }
      }
      
      if (response.data.failed > 0) {
        toast.error(`${response.data.failed} entries failed to import`);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to import pricing');
      setImportResult(null);
    } finally {
      setImporting(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleExportCsv = async () => {
    setExporting(true);
    try {
      const response = await api.exportCustomerPricingCsv();
      const blob = new Blob([response.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `customer_pricing_export_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success('Customer pricing exported successfully!');
    } catch (error) {
      toast.error('Failed to export customer pricing');
      console.error(error);
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>;
  }

  return (
    <div className="space-y-6" data-testid="customer-pricing-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-tightest mb-2">Customer Pricing</h1>
          <p className="text-muted-foreground">Set custom prices for individual customers</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button 
            variant="outline" 
            onClick={handleExportCsv}
            disabled={exporting}
            data-testid="export-pricing-btn"
          >
            <FileDown className="mr-2 h-4 w-4" />
            {exporting ? 'Exporting...' : 'Export CSV'}
          </Button>
          <Dialog open={bulkOpen} onOpenChange={setBulkOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" data-testid="bulk-import-btn">
                <Upload className="mr-2 h-4 w-4" /> Bulk Import
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg" data-testid="bulk-import-dialog">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <FileSpreadsheet className="h-5 w-5" />
                  Bulk Import Pricing
                </DialogTitle>
              </DialogHeader>
              
              <div className="space-y-4">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h4 className="font-medium text-blue-800 mb-2">CSV Format</h4>
                  <p className="text-sm text-blue-700 mb-2">
                    Your CSV file should have these columns:
                  </p>
                  <code className="block bg-blue-100 p-2 rounded text-xs font-mono text-blue-900">
                    customer_email,product_id,custom_price
                  </code>
                </div>

                <Button 
                  variant="outline" 
                  onClick={downloadTemplate}
                  className="w-full"
                  data-testid="download-template-btn"
                >
                  <Download className="mr-2 h-4 w-4" />
                  Download Template with Product IDs
                </Button>

                <div className="border-2 border-dashed border-border rounded-lg p-6 text-center">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv"
                    onChange={handleFileUpload}
                    className="hidden"
                    id="csv-upload"
                    data-testid="csv-file-input"
                  />
                  <label 
                    htmlFor="csv-upload" 
                    className="cursor-pointer"
                  >
                    <Upload className="h-10 w-10 mx-auto mb-3 text-muted-foreground" />
                    <p className="font-medium mb-1">
                      {importing ? 'Importing...' : 'Click to upload CSV'}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      or drag and drop your file here
                    </p>
                  </label>
                </div>

                {importResult && (
                  <div className="space-y-3" data-testid="import-result">
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div className="bg-secondary rounded-lg p-3">
                        <p className="text-2xl font-bold">{importResult.total}</p>
                        <p className="text-xs text-muted-foreground">Total</p>
                      </div>
                      <div className="bg-green-50 rounded-lg p-3">
                        <p className="text-2xl font-bold text-green-600">{importResult.successful}</p>
                        <p className="text-xs text-green-600">Success</p>
                      </div>
                      <div className="bg-red-50 rounded-lg p-3">
                        <p className="text-2xl font-bold text-red-600">{importResult.failed}</p>
                        <p className="text-xs text-red-600">Failed</p>
                      </div>
                    </div>

                    {importResult.errors.length > 0 && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-3 max-h-40 overflow-y-auto">
                        <h5 className="font-medium text-red-800 mb-2 flex items-center gap-1">
                          <AlertCircle className="h-4 w-4" />
                          Errors
                        </h5>
                        <ul className="text-xs text-red-700 space-y-1">
                          {importResult.errors.map((error, idx) => (
                            <li key={idx}>• {error}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {importResult.successful > 0 && importResult.failed === 0 && (
                      <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-center gap-2">
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                        <p className="text-sm text-green-700">All entries imported successfully!</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </DialogContent>
          </Dialog>

          {selectedCustomer && (
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button data-testid="add-pricing-btn" className="bg-accent hover:bg-accent/90">
                  <Plus className="mr-2 h-4 w-4" /> Add Custom Price
                </Button>
              </DialogTrigger>
              <DialogContent data-testid="pricing-dialog">
                <DialogHeader>
                  <DialogTitle>Set Custom Price</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="product" data-testid="product-label">Product *</Label>
                    <select
                      id="product"
                      data-testid="product-select"
                      value={selectedProduct}
                      onChange={(e) => setSelectedProduct(e.target.value)}
                      required
                      className="flex h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <option value="">Select a product</option>
                      {products.map(product => (
                        <option key={product.id} value={product.id}>
                          {product.name} (SKU: {product.sku}) - £{product.price.toFixed(2)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="custom-price" data-testid="custom-price-label">Custom Price (£) *</Label>
                    <Input
                      id="custom-price"
                      data-testid="custom-price-input"
                      type="number"
                      step="0.01"
                      value={customPrice}
                      onChange={(e) => setCustomPrice(e.target.value)}
                      required
                      placeholder="Enter custom price"
                      min="0"
                    />
                  </div>
                  <Button type="submit" data-testid="submit-pricing" className="w-full bg-accent hover:bg-accent/90">
                    Set Custom Price
                  </Button>
                </form>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      <Card className="p-6">
        <div className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="customer-select" data-testid="customer-select-label">Select Customer</Label>
            <select
              id="customer-select"
              data-testid="customer-select"
              value={selectedCustomer}
              onChange={(e) => handleCustomerChange(e.target.value)}
              className="flex h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="">Choose a customer...</option>
              {customers.map(customer => (
                <option key={customer.email} value={customer.email}>
                  {customer.name} ({customer.email})
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              Only customers who have placed orders are shown. Use bulk import to add pricing for new customers.
            </p>
          </div>

          {selectedCustomer && (
            <div className="border-t border-border pt-6">
              <h2 className="text-xl font-heading font-bold tracking-tightest mb-4">Custom Prices for {selectedCustomer}</h2>
              {customerPricing.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Tag className="h-12 w-12 mx-auto mb-3 opacity-20" />
                  <p>No custom pricing set for this customer</p>
                  <p className="text-sm mt-2">Click &ldquo;Add Custom Price&rdquo; to set special pricing</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {customerPricing.map(pricing => {
                    const product = products.find(p => p.id === pricing.product_id);
                    return (
                      <div key={pricing.id} className="flex items-center justify-between p-4 bg-secondary rounded-md" data-testid={`pricing-${pricing.id}`}>
                        <div className="flex-1">
                          <p className="font-medium">{product?.name || 'Unknown Product'}</p>
                          <p className="text-sm text-muted-foreground font-mono">SKU: {product?.sku}</p>
                          <div className="flex items-center gap-3 mt-1">
                            <span className="text-xs text-muted-foreground line-through">
                              Regular: £{(product?.price || 0).toFixed(2)}
                            </span>
                            <span className="text-sm font-bold text-accent">
                              Custom: £{pricing.custom_price.toFixed(2)}
                            </span>
                          </div>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDelete(pricing.id)}
                          data-testid={`delete-pricing-${pricing.id}`}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* Quick Help Card */}
      <Card className="p-6 bg-blue-50/50 border-blue-200">
        <h3 className="font-heading font-bold text-lg mb-3 flex items-center gap-2">
          <FileSpreadsheet className="h-5 w-5 text-blue-600" />
          Bulk Import Guide
        </h3>
        <div className="grid md:grid-cols-2 gap-4 text-sm">
          <div>
            <h4 className="font-medium mb-2">Steps:</h4>
            <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
              <li>Click &ldquo;Bulk Import&rdquo; button</li>
              <li>Download the template CSV</li>
              <li>Fill in customer emails, product IDs, and prices</li>
              <li>Upload the completed CSV file</li>
            </ol>
          </div>
          <div>
            <h4 className="font-medium mb-2">Tips:</h4>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground">
              <li>Product IDs are included in the template</li>
              <li>Existing prices will be updated</li>
              <li>Invalid rows will be skipped with error messages</li>
              <li>Use any spreadsheet app to edit the CSV</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
};
