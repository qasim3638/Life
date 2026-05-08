import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { 
  Building2, Plus, Search, Edit, Trash2, 
  RefreshCw, Phone, Mail, Globe, Calendar,
  Package, X, Check, ChevronDown, ChevronUp,
  AlertCircle
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Textarea } from '../../components/ui/textarea';

const Suppliers = () => {
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [stats, setStats] = useState(null);
  
  // Dialog states
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [selectedSupplier, setSelectedSupplier] = useState(null);
  
  // Form state
  const [formData, setFormData] = useState({
    name: '',
    code: '',
    contact_name: '',
    email: '',
    phone: '',
    address: '',
    website: '',
    payment_terms: '',
    lead_time_days: '',
    notes: '',
    is_active: true
  });
  
  const [saving, setSaving] = useState(false);

  const loadSuppliers = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (searchTerm) params.append('search', searchTerm);
      if (!showInactive) params.append('is_active', 'true');
      
      const res = await api.get(`/suppliers?${params.toString()}`);
      setSuppliers(res.data || []);
    } catch (error) {
      console.error('Error loading suppliers:', error);
      toast.error('Failed to load suppliers');
    } finally {
      setLoading(false);
    }
  }, [searchTerm, showInactive]);

  const loadStats = async () => {
    try {
      const res = await api.get('/suppliers/stats/summary');
      setStats(res.data);
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  };

  useEffect(() => {
    loadSuppliers();
    loadStats();
  }, [loadSuppliers]);

  // Debounce search
  const [debouncedSearch, setDebouncedSearch] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchTerm), 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  useEffect(() => {
    if (debouncedSearch !== undefined) loadSuppliers();
  }, [debouncedSearch, loadSuppliers]);

  const resetForm = () => {
    setFormData({
      name: '',
      code: '',
      contact_name: '',
      email: '',
      phone: '',
      address: '',
      website: '',
      payment_terms: '',
      lead_time_days: '',
      notes: '',
      is_active: true
    });
  };

  const handleAdd = () => {
    resetForm();
    setShowAddDialog(true);
  };

  const handleEdit = (supplier) => {
    setSelectedSupplier(supplier);
    setFormData({
      name: supplier.name || '',
      code: supplier.code || '',
      contact_name: supplier.contact_name || '',
      email: supplier.email || '',
      phone: supplier.phone || '',
      address: supplier.address || '',
      website: supplier.website || '',
      payment_terms: supplier.payment_terms || '',
      lead_time_days: supplier.lead_time_days || '',
      notes: supplier.notes || '',
      is_active: supplier.is_active !== false
    });
    setShowEditDialog(true);
  };

  const handleDelete = (supplier) => {
    setSelectedSupplier(supplier);
    setShowDeleteDialog(true);
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      toast.error('Supplier name is required');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        ...formData,
        lead_time_days: formData.lead_time_days ? parseInt(formData.lead_time_days) : null
      };

      if (showEditDialog && selectedSupplier) {
        await api.put(`/suppliers/${selectedSupplier.id}`, payload);
        toast.success('Supplier updated');
      } else {
        await api.post('/suppliers', payload);
        toast.success('Supplier created');
      }
      
      setShowAddDialog(false);
      setShowEditDialog(false);
      resetForm();
      loadSuppliers();
      loadStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save supplier');
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!selectedSupplier) return;
    
    try {
      await api.delete(`/suppliers/${selectedSupplier.id}`);
      toast.success('Supplier removed');
      setShowDeleteDialog(false);
      setSelectedSupplier(null);
      loadSuppliers();
      loadStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete supplier');
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric'
    });
  };

  return (
    <div className="space-y-6" data-testid="suppliers-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-heading font-bold tracking-tight">Suppliers</h1>
          <p className="text-muted-foreground">Manage your product suppliers</p>
        </div>
        <Button onClick={handleAdd} data-testid="add-supplier-btn">
          <Plus className="h-4 w-4 mr-2" />
          Add Supplier
        </Button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold">{stats.total_suppliers}</div>
              <div className="text-sm text-muted-foreground">Total Suppliers</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-green-600">{stats.active_suppliers}</div>
              <div className="text-sm text-muted-foreground">Active</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-amber-600">{stats.inactive_suppliers}</div>
              <div className="text-sm text-muted-foreground">Inactive</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold">
                {stats.products_by_supplier?.reduce((sum, s) => sum + s.product_count, 0) || 0}
              </div>
              <div className="text-sm text-muted-foreground">Total Products</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search suppliers..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
                data-testid="search-input"
              />
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={showInactive}
                  onChange={(e) => setShowInactive(e.target.checked)}
                  className="rounded"
                />
                Show inactive
              </label>
              <Button variant="outline" size="sm" onClick={() => { loadSuppliers(); loadStats(); }}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Suppliers List */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : suppliers.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Building2 className="h-12 w-12 text-muted-foreground/30 mb-3" />
              <p className="text-muted-foreground">No suppliers found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full" data-testid="suppliers-table">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="text-left py-3 px-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">Supplier</th>
                    <th className="text-left py-3 px-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">Contact</th>
                    <th className="text-left py-3 px-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">Products</th>
                    <th className="text-left py-3 px-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">Lead Time</th>
                    <th className="text-left py-3 px-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">Status</th>
                    <th className="text-right py-3 px-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {suppliers.map(supplier => (
                    <tr 
                      key={supplier.id} 
                      className="border-b hover:bg-muted/30"
                      data-testid={`supplier-row-${supplier.id}`}
                    >
                      <td className="py-3 px-4">
                        <div className="font-medium">{supplier.name}</div>
                        {supplier.code && (
                          <div className="text-xs text-muted-foreground font-mono">{supplier.code}</div>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <div className="text-sm">{supplier.contact_name || '-'}</div>
                        {supplier.email && (
                          <div className="text-xs text-muted-foreground flex items-center gap-1">
                            <Mail className="h-3 w-3" /> {supplier.email}
                          </div>
                        )}
                        {supplier.phone && (
                          <div className="text-xs text-muted-foreground flex items-center gap-1">
                            <Phone className="h-3 w-3" /> {supplier.phone}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1">
                          <Package className="h-4 w-4 text-muted-foreground" />
                          <span className="font-medium">{supplier.product_count || 0}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-sm">
                        {supplier.lead_time_days ? `${supplier.lead_time_days} days` : '-'}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          supplier.is_active !== false
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}>
                          {supplier.is_active !== false ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEdit(supplier)}
                            data-testid={`edit-btn-${supplier.id}`}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(supplier)}
                            className="text-red-600 hover:text-red-700"
                            data-testid={`delete-btn-${supplier.id}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add/Edit Dialog */}
      <Dialog open={showAddDialog || showEditDialog} onOpenChange={(open) => {
        if (!open) {
          setShowAddDialog(false);
          setShowEditDialog(false);
        }
      }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {showEditDialog ? 'Edit Supplier' : 'Add New Supplier'}
            </DialogTitle>
          </DialogHeader>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-4">
            <div className="md:col-span-2">
              <label className="text-sm font-medium mb-1 block">Supplier Name *</label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                placeholder="e.g., Tile Rite"
                data-testid="supplier-name-input"
              />
            </div>
            
            <div>
              <label className="text-sm font-medium mb-1 block">Code</label>
              <Input
                value={formData.code}
                onChange={(e) => setFormData({...formData, code: e.target.value.toUpperCase()})}
                placeholder="e.g., TIL"
                maxLength={10}
              />
            </div>
            
            <div>
              <label className="text-sm font-medium mb-1 block">Contact Name</label>
              <Input
                value={formData.contact_name}
                onChange={(e) => setFormData({...formData, contact_name: e.target.value})}
                placeholder="Primary contact"
              />
            </div>
            
            <div>
              <label className="text-sm font-medium mb-1 block">Email</label>
              <Input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({...formData, email: e.target.value})}
                placeholder="orders@supplier.com"
              />
            </div>
            
            <div>
              <label className="text-sm font-medium mb-1 block">Phone</label>
              <Input
                value={formData.phone}
                onChange={(e) => setFormData({...formData, phone: e.target.value})}
                placeholder="01onal 234 5678"
              />
            </div>
            
            <div>
              <label className="text-sm font-medium mb-1 block">Website</label>
              <Input
                value={formData.website}
                onChange={(e) => setFormData({...formData, website: e.target.value})}
                placeholder="https://supplier.com"
              />
            </div>
            
            <div>
              <label className="text-sm font-medium mb-1 block">Lead Time (days)</label>
              <Input
                type="number"
                value={formData.lead_time_days}
                onChange={(e) => setFormData({...formData, lead_time_days: e.target.value})}
                placeholder="3"
                min="0"
              />
            </div>
            
            <div className="md:col-span-2">
              <label className="text-sm font-medium mb-1 block">Address</label>
              <Textarea
                value={formData.address}
                onChange={(e) => setFormData({...formData, address: e.target.value})}
                placeholder="Full address"
                rows={2}
              />
            </div>
            
            <div>
              <label className="text-sm font-medium mb-1 block">Payment Terms</label>
              <Input
                value={formData.payment_terms}
                onChange={(e) => setFormData({...formData, payment_terms: e.target.value})}
                placeholder="e.g., Net 30"
              />
            </div>
            
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_active"
                checked={formData.is_active}
                onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                className="rounded"
              />
              <label htmlFor="is_active" className="text-sm">Active supplier</label>
            </div>
            
            <div className="md:col-span-2">
              <label className="text-sm font-medium mb-1 block">Notes</label>
              <Textarea
                value={formData.notes}
                onChange={(e) => setFormData({...formData, notes: e.target.value})}
                placeholder="Additional notes..."
                rows={3}
              />
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowAddDialog(false);
              setShowEditDialog(false);
            }}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : null}
              {showEditDialog ? 'Save Changes' : 'Add Supplier'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Supplier</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-6 w-6 text-amber-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Are you sure you want to delete "{selectedSupplier?.name}"?</p>
                {selectedSupplier?.product_count > 0 && (
                  <p className="text-sm text-muted-foreground mt-2">
                    This supplier has <strong>{selectedSupplier.product_count}</strong> associated products. 
                    The supplier will be marked as inactive instead of deleted.
                  </p>
                )}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              {selectedSupplier?.product_count > 0 ? 'Deactivate' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Suppliers;
