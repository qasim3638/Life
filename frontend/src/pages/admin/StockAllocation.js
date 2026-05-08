import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { 
  Package, Building2, ArrowRight, Search, RefreshCw, 
  Save, AlertTriangle, Check, ArrowLeftRight
} from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';

export const StockAllocation = () => {
  const [products, setProducts] = useState([]);
  const [showrooms, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [allocations, setAllocations] = useState({});
  const [saving, setSaving] = useState(false);
  
  // Transfer dialog state
  const [showTransferDialog, setShowTransferDialog] = useState(false);
  const [transferProduct, setTransferProduct] = useState(null);
  const [transferFrom, setTransferFrom] = useState('');
  const [transferTo, setTransferTo] = useState('');
  const [transferQty, setTransferQty] = useState(1);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [productsRes, showroomsRes] = await Promise.all([
        api.getProducts(),
        api.getStores()
      ]);
      setProducts(productsRes.data || []);
      setStores(showroomsRes.data || []);
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadProductAllocations = async (product) => {
    setSelectedProduct(product);
    try {
      const res = await api.getProductStoreStock(product.id);
      const allocationMap = {};
      (res.data.allocations || []).forEach(a => {
        allocationMap[a.showroom_id] = a.quantity;
      });
      setAllocations(allocationMap);
    } catch (error) {
      console.error('Failed to load allocations:', error);
      // Initialize with empty allocations
      setAllocations({});
    }
  };

  const updateAllocation = (showroomId, quantity) => {
    setAllocations(prev => ({
      ...prev,
      [showroomId]: Math.max(0, parseInt(quantity) || 0)
    }));
  };

  const getTotalAllocated = () => {
    return Object.values(allocations).reduce((sum, qty) => sum + qty, 0);
  };

  const getUnallocated = () => {
    return (selectedProduct?.stock || 0) - getTotalAllocated();
  };

  const saveAllocations = async () => {
    if (!selectedProduct) return;
    
    const unallocated = getUnallocated();
    if (unallocated < 0) {
      toast.error(`Over-allocated by ${Math.abs(unallocated)} units`);
      return;
    }
    
    setSaving(true);
    try {
      const allocationsList = Object.entries(allocations)
        .filter(([_, qty]) => qty > 0)
        .map(([showroom_id, quantity]) => ({ showroom_id, quantity }));
      
      await api.updateProductStoreStock(selectedProduct.id, allocationsList);
      toast.success('Stock allocation saved');
      
      // Update local product data
      setProducts(products.map(p => 
        p.id === selectedProduct.id 
          ? { ...p, showroom_stock: allocations }
          : p
      ));
    } catch (error) {
      console.error('Failed to save allocations:', error);
      toast.error(error.response?.data?.detail || 'Failed to save allocations');
    } finally {
      setSaving(false);
    }
  };

  const openTransferDialog = (product) => {
    setTransferProduct(product);
    setTransferFrom('');
    setTransferTo('');
    setTransferQty(1);
    setShowTransferDialog(true);
  };

  const executeTransfer = async () => {
    if (!transferProduct || !transferFrom || !transferTo || transferQty < 1) {
      toast.error('Please fill all transfer details');
      return;
    }
    
    if (transferFrom === transferTo) {
      toast.error('Source and destination must be different');
      return;
    }
    
    try {
      await api.transferStock(transferProduct.id, transferFrom, transferTo, transferQty);
      toast.success('Stock transferred successfully');
      setShowTransferDialog(false);
      
      // Reload allocations if this product is selected
      if (selectedProduct?.id === transferProduct.id) {
        loadProductAllocations(transferProduct);
      }
      
      // Refresh products
      fetchData();
    } catch (error) {
      console.error('Failed to transfer stock:', error);
      toast.error(error.response?.data?.detail || 'Failed to transfer stock');
    }
  };

  const filteredProducts = products.filter(p =>
    p.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.sku?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="stock-allocation-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-heading font-bold tracking-tight">Stock Allocation</h1>
          <p className="text-muted-foreground">Allocate product stock to individual showrooms</p>
        </div>
        <Button variant="outline" onClick={fetchData}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Product List */}
        <div className="lg:col-span-1">
          <Card className="p-4">
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <Package className="h-4 w-4" />
              Select Product
            </h3>
            
            <div className="relative mb-3">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search products..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
              />
            </div>
            
            <div className="max-h-[500px] overflow-y-auto space-y-2">
              {filteredProducts.map(product => {
                const totalStock = product.stock || 0;
                const m2Qty = product.m2_quantity;
                const m2PerPiece = product.tile_m2_per_piece;
                const allocatedStock = Object.values(product.showroom_stock || {}).reduce((s, q) => s + q, 0);
                const hasAllocation = allocatedStock > 0;
                
                return (
                  <div
                    key={product.id}
                    className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                      selectedProduct?.id === product.id
                        ? 'bg-primary/10 border-primary'
                        : 'hover:bg-gray-50'
                    }`}
                    onClick={() => loadProductAllocations(product)}
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">{product.name}</p>
                        <p className="text-xs text-muted-foreground">{product.sku}</p>
                        {product.description && (
                          <p className="text-xs text-blue-600 mt-1 truncate" title={product.description}>
                            {product.description}
                          </p>
                        )}
                      </div>
                      <div className="text-right">
                        {m2Qty ? (
                          <>
                            <p className={`text-sm font-bold ${m2Qty <= 10 ? 'text-red-600' : 'text-green-600'}`}>
                              {m2Qty} m²
                            </p>
                            {m2PerPiece && (
                              <p className="text-xs text-muted-foreground">
                                ({Math.round(m2Qty / m2PerPiece)} pcs)
                              </p>
                            )}
                          </>
                        ) : (
                          <p className={`text-sm font-bold ${totalStock <= 10 ? 'text-red-600' : 'text-green-600'}`}>
                            {totalStock} pcs
                          </p>
                        )}
                        {hasAllocation && (
                          <p className="text-xs text-blue-600">
                            {allocatedStock} allocated
                          </p>
                        )}
                      </div>
                    </div>
                    
                    {/* Quick action buttons */}
                    <div className="mt-2 flex gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          openTransferDialog(product);
                        }}
                        className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                      >
                        <ArrowLeftRight className="h-3 w-3 inline mr-1" />
                        Transfer
                      </button>
                    </div>
                  </div>
                );
              })}
              
              {filteredProducts.length === 0 && (
                <p className="text-center text-muted-foreground py-4">No products found</p>
              )}
            </div>
          </Card>
        </div>

        {/* Allocation Editor */}
        <div className="lg:col-span-2">
          {selectedProduct ? (
            <Card className="p-4">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="font-semibold text-lg">{selectedProduct.name}</h3>
                  <p className="text-sm text-muted-foreground">SKU: {selectedProduct.sku}</p>
                  {selectedProduct.description && (
                    <p className="text-sm text-blue-600 mt-1">{selectedProduct.description}</p>
                  )}
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold">{selectedProduct.stock || 0}</p>
                  <p className="text-xs text-muted-foreground">Total Stock</p>
                </div>
              </div>

              {/* Stock Summary */}
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="p-3 bg-gray-100 rounded-lg text-center">
                  <p className="text-xl font-bold">{selectedProduct.stock || 0}</p>
                  <p className="text-xs text-muted-foreground">Total Stock</p>
                </div>
                <div className="p-3 bg-blue-100 rounded-lg text-center">
                  <p className="text-xl font-bold text-blue-700">{getTotalAllocated()}</p>
                  <p className="text-xs text-blue-600">Allocated</p>
                </div>
                <div className={`p-3 rounded-lg text-center ${getUnallocated() < 0 ? 'bg-red-100' : 'bg-green-100'}`}>
                  <p className={`text-xl font-bold ${getUnallocated() < 0 ? 'text-red-700' : 'text-green-700'}`}>
                    {getUnallocated()}
                  </p>
                  <p className={`text-xs ${getUnallocated() < 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {getUnallocated() < 0 ? 'Over-allocated!' : 'Unallocated'}
                  </p>
                </div>
              </div>

              {/* Warning if over-allocated */}
              {getUnallocated() < 0 && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-red-600" />
                  <p className="text-sm text-red-700">
                    You have allocated more stock than available. Please reduce allocations.
                  </p>
                </div>
              )}

              {/* Store Allocations */}
              <h4 className="font-semibold mb-3 flex items-center gap-2">
                <Building2 className="h-4 w-4" />
                Allocate to Stores
              </h4>
              
              <div className="space-y-3">
                {showrooms.map(showroom => (
                  <div 
                    key={showroom.id}
                    className="flex items-center gap-4 p-3 border rounded-lg"
                  >
                    <div className="flex-1">
                      <p className="font-medium">{showroom.name}</p>
                      <p className="text-xs text-muted-foreground">{showroom.address}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => updateAllocation(showroom.id, (allocations[showroom.id] || 0) - 1)}
                        className="w-8 h-8 rounded bg-gray-200 hover:bg-gray-300 flex items-center justify-center"
                      >
                        -
                      </button>
                      <Input
                        type="number"
                        min="0"
                        value={allocations[showroom.id] || 0}
                        onChange={(e) => updateAllocation(showroom.id, e.target.value)}
                        className="w-20 text-center"
                      />
                      <button
                        onClick={() => updateAllocation(showroom.id, (allocations[showroom.id] || 0) + 1)}
                        className="w-8 h-8 rounded bg-gray-200 hover:bg-gray-300 flex items-center justify-center"
                      >
                        +
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Save Button */}
              <div className="mt-6 flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => openTransferDialog(selectedProduct)}
                >
                  <ArrowLeftRight className="h-4 w-4 mr-2" />
                  Transfer Between Stores
                </Button>
                <Button
                  onClick={saveAllocations}
                  disabled={saving || getUnallocated() < 0}
                >
                  {saving ? (
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4 mr-2" />
                  )}
                  Save Allocations
                </Button>
              </div>
            </Card>
          ) : (
            <Card className="p-8 text-center">
              <Package className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
              <h3 className="font-semibold text-lg mb-2">Select a Product</h3>
              <p className="text-muted-foreground">
                Choose a product from the list to allocate stock to showrooms
              </p>
            </Card>
          )}
        </div>
      </div>

      {/* Transfer Dialog */}
      <Dialog open={showTransferDialog} onOpenChange={setShowTransferDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Transfer Stock</DialogTitle>
            <DialogDescription>
              Transfer stock for {transferProduct?.name} between showrooms
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div>
              <label className="text-sm font-medium">From Store</label>
              <select
                value={transferFrom}
                onChange={(e) => setTransferFrom(e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
              >
                <option value="">Select source...</option>
                {showrooms.map(s => {
                  const qty = transferProduct?.showroom_stock?.[s.id] || 0;
                  return (
                    <option key={s.id} value={s.id} disabled={qty === 0}>
                      {s.name} ({qty} available)
                    </option>
                  );
                })}
              </select>
            </div>
            
            <div className="flex justify-center">
              <ArrowRight className="h-6 w-6 text-muted-foreground" />
            </div>
            
            <div>
              <label className="text-sm font-medium">To Store</label>
              <select
                value={transferTo}
                onChange={(e) => setTransferTo(e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
              >
                <option value="">Select destination...</option>
                {showrooms.map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="text-sm font-medium">Quantity to Transfer</label>
              <Input
                type="number"
                min="1"
                value={transferQty}
                onChange={(e) => setTransferQty(parseInt(e.target.value) || 1)}
              />
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowTransferDialog(false)}>
              Cancel
            </Button>
            <Button onClick={executeTransfer}>
              <Check className="h-4 w-4 mr-2" />
              Transfer Stock
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default StockAllocation;
