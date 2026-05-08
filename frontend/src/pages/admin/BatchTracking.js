import React, { useState, useEffect } from 'react';
import { Package, Plus, AlertTriangle, RotateCcw, FileText, Clock } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const BatchTracking = () => {
  const [batches, setBatches] = useState([]);
  const [expiringBatches, setExpiringBatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showMovementDialog, setShowMovementDialog] = useState(false);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [statusFilter, setStatusFilter] = useState('active');
  
  // Form state
  const [formData, setFormData] = useState({
    product_id: '',
    batch_number: '',
    quantity: 1,
    manufacturing_date: '',
    expiry_date: '',
    supplier: '',
    cost_price: '',
    notes: ''
  });
  
  // Movement form
  const [movementData, setMovementData] = useState({
    quantity: 1,
    movement_type: 'sale',
    reference: '',
    notes: ''
  });

  const [productSearch, setProductSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);

  useEffect(() => {
    fetchBatches();
    fetchExpiringBatches();
  }, [statusFilter]);

  const fetchBatches = async () => {
    setLoading(true);
    try {
      const url = statusFilter 
        ? `${API_URL}/api/batch-tracking/batches?status=${statusFilter}`
        : `${API_URL}/api/batch-tracking/batches`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setBatches(data.batches || []);
      }
    } catch (e) {
      console.error('Error:', e);
    } finally {
      setLoading(false);
    }
  };

  const fetchExpiringBatches = async () => {
    try {
      const res = await fetch(`${API_URL}/api/batch-tracking/expiring?days=30`);
      if (res.ok) {
        const data = await res.json();
        setExpiringBatches(data.expiring_batches || []);
      }
    } catch (e) {
      console.error('Error:', e);
    }
  };

  const searchProducts = async (query) => {
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }
    try {
      const res = await fetch(`${API_URL}/api/barcode/search?q=${encodeURIComponent(query)}&limit=10`);
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.results || []);
      }
    } catch (e) {
      console.error('Search error:', e);
    }
  };

  const handleCreateBatch = async () => {
    if (!formData.product_id || !formData.batch_number || !formData.quantity) {
      toast.error('Please fill required fields');
      return;
    }
    
    try {
      const res = await fetch(`${API_URL}/api/batch-tracking/batches/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          quantity: parseInt(formData.quantity),
          cost_price: formData.cost_price ? parseFloat(formData.cost_price) : null
        })
      });
      
      if (res.ok) {
        toast.success('Batch created successfully');
        setShowCreateDialog(false);
        fetchBatches();
        resetForm();
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Failed to create batch');
      }
    } catch (e) {
      console.error('Error:', e);
      toast.error('Failed to create batch');
    }
  };

  const handleRecordMovement = async () => {
    if (!selectedBatch || !movementData.quantity) return;
    
    try {
      const res = await fetch(`${API_URL}/api/batch-tracking/batches/${selectedBatch.id}/movement`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...movementData,
          quantity: parseInt(movementData.quantity)
        })
      });
      
      if (res.ok) {
        toast.success('Movement recorded');
        setShowMovementDialog(false);
        fetchBatches();
        setMovementData({ quantity: 1, movement_type: 'sale', reference: '', notes: '' });
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Failed to record movement');
      }
    } catch (e) {
      toast.error('Failed to record movement');
    }
  };

  const handleRecall = async (batchId, reason) => {
    try {
      const res = await fetch(`${API_URL}/api/batch-tracking/batches/${batchId}/recall`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason })
      });
      
      if (res.ok) {
        toast.success('Batch recalled');
        fetchBatches();
      }
    } catch (e) {
      toast.error('Failed to recall batch');
    }
  };

  const resetForm = () => {
    setFormData({
      product_id: '',
      batch_number: '',
      quantity: 1,
      manufacturing_date: '',
      expiry_date: '',
      supplier: '',
      cost_price: '',
      notes: ''
    });
    setProductSearch('');
  };

  const getStatusBadge = (status) => {
    const styles = {
      active: 'bg-green-100 text-green-700',
      depleted: 'bg-gray-100 text-gray-700',
      recalled: 'bg-red-100 text-red-700',
      expired: 'bg-orange-100 text-orange-700'
    };
    return <span className={`px-2 py-1 rounded text-xs font-medium ${styles[status] || 'bg-gray-100'}`}>
      {status?.toUpperCase()}
    </span>;
  };

  return (
    <div className="space-y-6" data-testid="batch-tracking">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Batch/Lot Tracking</h2>
          <p className="text-gray-500">Track products by batch number for quality control</p>
        </div>
        <div className="flex gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border rounded-lg px-3 py-2"
          >
            <option value="active">Active</option>
            <option value="">All</option>
            <option value="depleted">Depleted</option>
            <option value="recalled">Recalled</option>
          </select>
          <Button onClick={() => setShowCreateDialog(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Batch
          </Button>
        </div>
      </div>

      {/* Expiring Soon Alert */}
      {expiringBatches.length > 0 && (
        <Card className="border-orange-200 bg-orange-50">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-5 w-5 text-orange-600" />
              <div>
                <h3 className="font-medium text-orange-900">Batches Expiring Soon</h3>
                <p className="text-sm text-orange-700">
                  {expiringBatches.length} batch(es) expiring within 30 days
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Batches List */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent"></div>
        </div>
      ) : batches.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Package className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900">No batches found</h3>
            <p className="text-gray-500">Start tracking batches by adding your first one.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {batches.map((batch) => (
            <Card key={batch.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-3">
                      <span className="font-mono font-bold text-lg">{batch.batch_number}</span>
                      {getStatusBadge(batch.status)}
                    </div>
                    <p className="text-sm font-medium text-gray-900 mt-1">{batch.product_name}</p>
                    <p className="text-xs text-gray-500">SKU: {batch.sku}</p>
                    <div className="flex gap-4 mt-2 text-sm text-gray-600">
                      <span>Initial: {batch.initial_quantity}</span>
                      <span>Current: <strong>{batch.current_quantity}</strong></span>
                      {batch.expiry_date && (
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          Expires: {new Date(batch.expiry_date).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {batch.status === 'active' && (
                      <>
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => {
                            setSelectedBatch(batch);
                            setShowMovementDialog(true);
                          }}
                        >
                          <RotateCcw className="h-4 w-4 mr-1" />
                          Record Movement
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline"
                          className="text-red-600 border-red-200 hover:bg-red-50"
                          onClick={() => {
                            const reason = prompt('Enter recall reason:');
                            if (reason) handleRecall(batch.id, reason);
                          }}
                        >
                          Recall
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Batch Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Add New Batch</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Product *</label>
              <div className="relative mt-1">
                <Input
                  placeholder="Search product..."
                  value={productSearch}
                  onChange={(e) => {
                    setProductSearch(e.target.value);
                    searchProducts(e.target.value);
                  }}
                />
                {searchResults.length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-40 overflow-auto">
                    {searchResults.map((product, idx) => (
                      <button
                        key={idx}
                        className="w-full px-3 py-2 text-left hover:bg-gray-50 text-sm"
                        onClick={() => {
                          setFormData({...formData, product_id: product.id});
                          setProductSearch(product.name);
                          setSearchResults([]);
                        }}
                      >
                        {product.name} ({product.sku})
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">Batch Number *</label>
                <Input
                  value={formData.batch_number}
                  onChange={(e) => setFormData({...formData, batch_number: e.target.value})}
                  placeholder="e.g., LOT-2026-001"
                  className="mt-1"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Quantity *</label>
                <Input
                  type="number"
                  min="1"
                  value={formData.quantity}
                  onChange={(e) => setFormData({...formData, quantity: e.target.value})}
                  className="mt-1"
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">Manufacturing Date</label>
                <Input
                  type="date"
                  value={formData.manufacturing_date}
                  onChange={(e) => setFormData({...formData, manufacturing_date: e.target.value})}
                  className="mt-1"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Expiry Date</label>
                <Input
                  type="date"
                  value={formData.expiry_date}
                  onChange={(e) => setFormData({...formData, expiry_date: e.target.value})}
                  className="mt-1"
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">Supplier</label>
                <Input
                  value={formData.supplier}
                  onChange={(e) => setFormData({...formData, supplier: e.target.value})}
                  className="mt-1"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Cost Price</label>
                <Input
                  type="number"
                  step="0.01"
                  value={formData.cost_price}
                  onChange={(e) => setFormData({...formData, cost_price: e.target.value})}
                  className="mt-1"
                />
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium">Notes</label>
              <Input
                value={formData.notes}
                onChange={(e) => setFormData({...formData, notes: e.target.value})}
                className="mt-1"
              />
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCreateDialog(false)}>Cancel</Button>
              <Button onClick={handleCreateBatch}>Create Batch</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Movement Dialog */}
      <Dialog open={showMovementDialog} onOpenChange={setShowMovementDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Record Movement - {selectedBatch?.batch_number}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Movement Type</label>
              <select
                value={movementData.movement_type}
                onChange={(e) => setMovementData({...movementData, movement_type: e.target.value})}
                className="w-full border rounded-lg px-3 py-2 mt-1"
              >
                <option value="sale">Sale</option>
                <option value="transfer">Transfer</option>
                <option value="return">Return</option>
                <option value="adjustment">Adjustment</option>
                <option value="writeoff">Write-off</option>
              </select>
            </div>
            
            <div>
              <label className="text-sm font-medium">Quantity</label>
              <Input
                type="number"
                min="1"
                max={selectedBatch?.current_quantity}
                value={movementData.quantity}
                onChange={(e) => setMovementData({...movementData, quantity: e.target.value})}
                className="mt-1"
              />
              <p className="text-xs text-gray-500 mt-1">
                Available: {selectedBatch?.current_quantity}
              </p>
            </div>
            
            <div>
              <label className="text-sm font-medium">Reference (Invoice/Transfer #)</label>
              <Input
                value={movementData.reference}
                onChange={(e) => setMovementData({...movementData, reference: e.target.value})}
                placeholder="Optional reference"
                className="mt-1"
              />
            </div>
            
            <div>
              <label className="text-sm font-medium">Notes</label>
              <Input
                value={movementData.notes}
                onChange={(e) => setMovementData({...movementData, notes: e.target.value})}
                className="mt-1"
              />
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowMovementDialog(false)}>Cancel</Button>
              <Button onClick={handleRecordMovement}>Record</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default BatchTracking;
