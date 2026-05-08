import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';
import { 
  Truck, Package, Search, RefreshCw, Plus, Minus, 
  Check, X, Building2, ClipboardList, Calendar,
  FileText, Barcode, AlertCircle, History
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

export const DeliveryCheckIn = () => {
  const { user } = useAuth();
  const [products, setProducts] = useState([]);
  const [showrooms, setShowrooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedShowroom, setSelectedShowroom] = useState('');
  const [deliveryItems, setDeliveryItems] = useState([]);
  const [deliveryNote, setDeliveryNote] = useState('');
  const [supplierRef, setSupplierRef] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [recentDeliveries, setRecentDeliveries] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [productsRes, showroomsRes] = await Promise.all([
        api.getProducts(),
        api.getStores()
      ]);
      setProducts(productsRes.data || []);
      setShowrooms(showroomsRes.data || []);
      
      // Set default showroom based on user's assigned showroom
      if (user?.showroom_id && !selectedShowroom) {
        setSelectedShowroom(user.showroom_id);
      } else if (showroomsRes.data?.length > 0 && !selectedShowroom) {
        setSelectedShowroom(showroomsRes.data[0].id);
      }
      
      // Fetch recent deliveries
      try {
        const deliveriesRes = await api.get('/deliveries/recent');
        setRecentDeliveries(deliveriesRes.data || []);
      } catch (e) {
        // Deliveries endpoint may not exist yet
        console.log('Recent deliveries not available');
      }
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [user?.showroom_id, selectedShowroom]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const addProductToDelivery = (product) => {
    // Check if product already in delivery
    const existing = deliveryItems.find(item => item.product_id === product.id);
    if (existing) {
      setDeliveryItems(deliveryItems.map(item => 
        item.product_id === product.id 
          ? { ...item, quantity: item.quantity + 1 }
          : item
      ));
    } else {
      setDeliveryItems([...deliveryItems, {
        product_id: product.id,
        product_name: product.name,
        sku: product.sku,
        quantity: 1,
        cost: product.cost || 0
      }]);
    }
    toast.success(`Added ${product.name}`);
  };

  const updateItemQuantity = (productId, quantity) => {
    if (quantity <= 0) {
      removeItemFromDelivery(productId);
      return;
    }
    setDeliveryItems(deliveryItems.map(item =>
      item.product_id === productId
        ? { ...item, quantity: parseInt(quantity) || 0 }
        : item
    ));
  };

  const removeItemFromDelivery = (productId) => {
    setDeliveryItems(deliveryItems.filter(item => item.product_id !== productId));
  };

  const getTotalItems = () => {
    return deliveryItems.reduce((sum, item) => sum + item.quantity, 0);
  };

  const getTotalValue = () => {
    return deliveryItems.reduce((sum, item) => sum + (item.quantity * item.cost), 0);
  };

  const handleCheckIn = async () => {
    if (!selectedShowroom) {
      toast.error('Please select a showroom');
      return;
    }
    if (deliveryItems.length === 0) {
      toast.error('Please add items to the delivery');
      return;
    }
    
    setShowConfirmDialog(true);
  };

  const confirmCheckIn = async () => {
    setSubmitting(true);
    try {
      const deliveryData = {
        showroom_id: selectedShowroom,
        items: deliveryItems.map(item => ({
          product_id: item.product_id,
          quantity: item.quantity
        })),
        supplier_reference: supplierRef,
        notes: deliveryNote,
        checked_in_by: user?.name || user?.email
      };

      await api.post('/deliveries/check-in', deliveryData);
      
      toast.success(`Delivery checked in! ${getTotalItems()} items added to stock.`);
      
      // Clear form
      setDeliveryItems([]);
      setDeliveryNote('');
      setSupplierRef('');
      setShowConfirmDialog(false);
      
      // Refresh data
      fetchData();
    } catch (error) {
      console.error('Failed to check in delivery:', error);
      toast.error(error.response?.data?.detail || 'Failed to check in delivery');
    } finally {
      setSubmitting(false);
    }
  };

  const filteredProducts = products.filter(p =>
    p.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.sku?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const selectedShowroomName = showrooms.find(s => s.id === selectedShowroom)?.name || '';

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="delivery-checkin-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-heading font-bold tracking-tight flex items-center gap-3">
            <Truck className="h-8 w-8 text-primary" />
            Delivery Check-In
          </h1>
          <p className="text-muted-foreground">Receive stock deliveries and update inventory</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowHistory(true)}>
            <History className="h-4 w-4 mr-2" />
            History
          </Button>
          <Button variant="outline" onClick={fetchData}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Showroom Selection */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-muted-foreground" />
            <span className="font-medium">Receiving Store:</span>
          </div>
          <select
            value={selectedShowroom}
            onChange={(e) => setSelectedShowroom(e.target.value)}
            className="flex-1 max-w-xs px-3 py-2 border rounded-md bg-background"
            data-testid="showroom-select"
          >
            <option value="">Select store...</option>
            {showrooms.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          
          <div className="flex-1" />
          
          <div className="flex gap-2">
            <Input
              placeholder="Supplier/PO Reference"
              value={supplierRef}
              onChange={(e) => setSupplierRef(e.target.value)}
              className="w-48"
              data-testid="supplier-ref-input"
            />
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Product Search */}
        <div className="lg:col-span-1">
          <Card className="p-4">
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <Package className="h-4 w-4" />
              Find Products
            </h3>
            
            <div className="relative mb-3">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search by name or SKU..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
                data-testid="product-search"
              />
            </div>
            
            <div className="max-h-[500px] overflow-y-auto space-y-2">
              {filteredProducts.slice(0, 50).map(product => (
                <div
                  key={product.id}
                  className="p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors group"
                  onClick={() => addProductToDelivery(product)}
                  data-testid={`product-item-${product.sku}`}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">{product.name}</p>
                      <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <Barcode className="h-3 w-3" />
                        {product.sku}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        Stock: {product.stock || 0}
                      </span>
                      <Button 
                        size="sm" 
                        variant="ghost"
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Plus className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
              
              {filteredProducts.length === 0 && (
                <p className="text-center text-muted-foreground py-4">No products found</p>
              )}
              
              {filteredProducts.length > 50 && (
                <p className="text-center text-muted-foreground py-2 text-sm">
                  Showing first 50 results. Refine your search.
                </p>
              )}
            </div>
          </Card>
        </div>

        {/* Delivery Items */}
        <div className="lg:col-span-2">
          <Card className="p-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold flex items-center gap-2">
                <ClipboardList className="h-4 w-4" />
                Delivery Items
              </h3>
              {deliveryItems.length > 0 && (
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => setDeliveryItems([])}
                  className="text-red-600 hover:text-red-700"
                >
                  <X className="h-4 w-4 mr-1" />
                  Clear All
                </Button>
              )}
            </div>

            {deliveryItems.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Truck className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p className="font-medium">No items added yet</p>
                <p className="text-sm">Search and click products to add them to the delivery</p>
              </div>
            ) : (
              <>
                <div className="space-y-2 max-h-[350px] overflow-y-auto mb-4">
                  {deliveryItems.map(item => (
                    <div 
                      key={item.product_id}
                      className="flex items-center gap-4 p-3 border rounded-lg bg-gray-50"
                      data-testid={`delivery-item-${item.sku}`}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">{item.product_name}</p>
                        <p className="text-xs text-muted-foreground">{item.sku}</p>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => updateItemQuantity(item.product_id, item.quantity - 1)}
                        >
                          <Minus className="h-4 w-4" />
                        </Button>
                        <Input
                          type="number"
                          min="1"
                          value={item.quantity}
                          onChange={(e) => updateItemQuantity(item.product_id, e.target.value)}
                          className="w-20 text-center"
                        />
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => updateItemQuantity(item.product_id, item.quantity + 1)}
                        >
                          <Plus className="h-4 w-4" />
                        </Button>
                      </div>
                      
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => removeItemFromDelivery(item.product_id)}
                        className="text-red-600 hover:text-red-700"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>

                {/* Notes */}
                <div className="mb-4">
                  <label className="text-sm font-medium mb-1 block">Delivery Notes (optional)</label>
                  <Input
                    placeholder="Any notes about this delivery..."
                    value={deliveryNote}
                    onChange={(e) => setDeliveryNote(e.target.value)}
                    data-testid="delivery-notes"
                  />
                </div>

                {/* Summary */}
                <div className="border-t pt-4">
                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div className="text-center p-3 bg-blue-50 rounded-lg">
                      <p className="text-2xl font-bold text-blue-700">{deliveryItems.length}</p>
                      <p className="text-xs text-blue-600">Products</p>
                    </div>
                    <div className="text-center p-3 bg-green-50 rounded-lg">
                      <p className="text-2xl font-bold text-green-700">{getTotalItems()}</p>
                      <p className="text-xs text-green-600">Total Items</p>
                    </div>
                    <div className="text-center p-3 bg-purple-50 rounded-lg">
                      <p className="text-2xl font-bold text-purple-700">£{getTotalValue().toFixed(2)}</p>
                      <p className="text-xs text-purple-600">Est. Cost Value</p>
                    </div>
                  </div>

                  <Button
                    className="w-full"
                    size="lg"
                    onClick={handleCheckIn}
                    disabled={!selectedShowroom || deliveryItems.length === 0}
                    data-testid="check-in-button"
                  >
                    <Check className="h-5 w-5 mr-2" />
                    Check In Delivery to {selectedShowroomName || 'Store'}
                  </Button>
                </div>
              </>
            )}
          </Card>
        </div>
      </div>

      {/* Confirmation Dialog */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Truck className="h-5 w-5" />
              Confirm Delivery Check-In
            </DialogTitle>
            <DialogDescription>
              This will add stock to {selectedShowroomName}
            </DialogDescription>
          </DialogHeader>
          
          <div className="py-4">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 flex items-start gap-2">
              <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-amber-700">
                <p className="font-medium">Please verify before confirming:</p>
                <ul className="list-disc ml-4 mt-1">
                  <li>All items have been physically received</li>
                  <li>Quantities match the actual delivery</li>
                  <li>Products are undamaged</li>
                </ul>
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Store:</span>
                <span className="font-medium">{selectedShowroomName}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Products:</span>
                <span className="font-medium">{deliveryItems.length}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Total Items:</span>
                <span className="font-medium">{getTotalItems()}</span>
              </div>
              {supplierRef && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Reference:</span>
                  <span className="font-medium">{supplierRef}</span>
                </div>
              )}
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfirmDialog(false)}>
              Cancel
            </Button>
            <Button onClick={confirmCheckIn} disabled={submitting}>
              {submitting ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Check className="h-4 w-4 mr-2" />
              )}
              Confirm Check-In
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* History Dialog */}
      <Dialog open={showHistory} onOpenChange={setShowHistory}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <History className="h-5 w-5" />
              Recent Deliveries
            </DialogTitle>
          </DialogHeader>
          
          <div className="py-4 max-h-[400px] overflow-y-auto">
            {recentDeliveries.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">No recent deliveries</p>
            ) : (
              <div className="space-y-3">
                {recentDeliveries.map((delivery, idx) => (
                  <div key={idx} className="p-3 border rounded-lg">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <p className="font-medium">{delivery.showroom_name || 'Unknown Store'}</p>
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {new Date(delivery.created_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium">{delivery.total_items} items</p>
                        <p className="text-xs text-muted-foreground">
                          by {delivery.checked_in_by}
                        </p>
                      </div>
                    </div>
                    {delivery.supplier_reference && (
                      <p className="text-xs text-muted-foreground">
                        Ref: {delivery.supplier_reference}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowHistory(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default DeliveryCheckIn;
