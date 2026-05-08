import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { 
  Package, Search, Save, RefreshCw, Building2, 
  AlertTriangle, Check, ChevronDown, ChevronUp,
  Filter, X, Plus, Minus, Settings2
} from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';

export const BulkStockEdit = () => {
  const [products, setProducts] = useState([]);
  const [showrooms, setShowrooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [supplierFilter, setSupplierFilter] = useState('');
  const [changes, setChanges] = useState({}); // { productId: { showroomId: { value, operation } } }
  const [expandedRows, setExpandedRows] = useState(new Set());
  const [selectedShowroom, setSelectedShowroom] = useState('all');
  
  // Edit mode: 'set' (exact value) or 'adjust' (add/subtract)
  const [editMode, setEditMode] = useState('set');
  
  // Pagination
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const pageSize = 50;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get('/bulk-stock/products-with-stock', {
        params: {
          search: searchTerm || undefined,
          supplier_name: supplierFilter || undefined,
          limit: pageSize,
          offset: page * pageSize
        }
      });
      
      setProducts(response.data.products || []);
      setShowrooms(response.data.showrooms || []);
      setTotal(response.data.total || 0);
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error('Failed to load products');
    } finally {
      setLoading(false);
    }
  }, [searchTerm, supplierFilter, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Debounce search
  const [debouncedSearch, setDebouncedSearch] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(0); // Reset to first page on search
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  useEffect(() => {
    if (debouncedSearch !== undefined) {
      fetchData();
    }
  }, [debouncedSearch, fetchData]);

  const getStockForShowroom = (product, showroomId) => {
    const allocation = product.showroom_allocations?.find(a => a.showroom_id === showroomId);
    return allocation?.quantity || 0;
  };

  const getCurrentValue = (productId, showroomId, originalValue) => {
    if (changes[productId] && changes[productId][showroomId] !== undefined) {
      const change = changes[productId][showroomId];
      if (editMode === 'adjust') {
        // In adjust mode, show the adjustment value (not the result)
        return change.value || 0;
      }
      return change.value;
    }
    return editMode === 'adjust' ? 0 : originalValue;
  };

  const getResultValue = (productId, showroomId, originalValue) => {
    if (changes[productId] && changes[productId][showroomId] !== undefined) {
      const change = changes[productId][showroomId];
      if (change.operation === 'add') {
        return originalValue + change.value;
      } else if (change.operation === 'subtract') {
        return Math.max(0, originalValue - change.value);
      }
      return change.value; // 'set' operation
    }
    return originalValue;
  };

  const handleStockChange = (productId, showroomId, value, operation = null) => {
    const numValue = Math.max(0, parseInt(value) || 0);
    const op = operation || (editMode === 'adjust' ? 'add' : 'set');
    
    setChanges(prev => ({
      ...prev,
      [productId]: {
        ...prev[productId],
        [showroomId]: { value: numValue, operation: op }
      }
    }));
  };

  const handleQuickAdjust = (productId, showroomId, originalValue, delta) => {
    const currentChange = changes[productId]?.[showroomId];
    let newValue;
    
    if (currentChange) {
      if (currentChange.operation === 'add') {
        newValue = Math.max(0, currentChange.value + delta);
      } else if (currentChange.operation === 'subtract') {
        newValue = Math.max(0, currentChange.value - delta);
      } else {
        newValue = Math.max(0, currentChange.value + delta);
      }
    } else {
      newValue = Math.max(0, delta);
    }
    
    const operation = newValue >= 0 ? 'add' : 'subtract';
    handleStockChange(productId, showroomId, Math.abs(newValue), operation);
  };

  const toggleRow = (productId) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(productId)) {
        next.delete(productId);
      } else {
        next.add(productId);
      }
      return next;
    });
  };

  const expandAll = () => {
    setExpandedRows(new Set(products.map(p => p.id)));
  };

  const collapseAll = () => {
    setExpandedRows(new Set());
  };

  const hasChanges = Object.keys(changes).length > 0;
  
  const changesCount = useMemo(() => {
    let count = 0;
    Object.values(changes).forEach(productChanges => {
      Object.keys(productChanges).forEach(() => count++);
    });
    return count;
  }, [changes]);

  const clearChanges = () => {
    setChanges({});
    toast.info('All changes cleared');
  };

  const switchEditMode = (newMode) => {
    if (hasChanges) {
      if (!window.confirm('Switching modes will clear all pending changes. Continue?')) {
        return;
      }
      setChanges({});
    }
    setEditMode(newMode);
    toast.info(newMode === 'adjust' ? 'Quick Adjust mode: Enter +/- quantities' : 'Set Value mode: Enter exact stock values');
  };

  const saveChanges = async (dryRun = false) => {
    if (!hasChanges) {
      toast.warning('No changes to save');
      return;
    }

    setSaving(true);
    try {
      // Build updates array
      const updates = [];
      
      Object.entries(changes).forEach(([productId, showroomChanges]) => {
        Object.entries(showroomChanges).forEach(([showroomId, change]) => {
          updates.push({
            product_id: productId,
            showroom_id: showroomId,
            quantity: change.value,
            operation: change.operation
          });
        });
      });

      const response = await api.post('/bulk-stock/update', {
        updates,
        dry_run: dryRun
      });

      if (dryRun) {
        toast.info(`Preview: ${response.data.preview?.length || 0} changes would be applied`);
        console.log('Preview:', response.data.preview);
      } else {
        toast.success(`Successfully updated ${response.data.updated_count} products`);
        if (response.data.errors?.length > 0) {
          toast.warning(`${response.data.errors.length} errors occurred`);
          console.error('Errors:', response.data.errors);
        }
        setChanges({});
        fetchData();
      }
    } catch (error) {
      console.error('Failed to save:', error);
      toast.error(error.response?.data?.detail || 'Failed to save changes');
    } finally {
      setSaving(false);
    }
  };

  // Get unique suppliers for filter
  const suppliers = useMemo(() => {
    const uniqueSuppliers = new Set(products.map(p => p.supplier_name).filter(Boolean));
    return Array.from(uniqueSuppliers).sort();
  }, [products]);

  const totalPages = Math.ceil(total / pageSize);

  if (loading && products.length === 0) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="bulk-stock-loading">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="bulk-stock-edit-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-heading font-bold tracking-tight">Bulk Stock Edit</h1>
          <p className="text-muted-foreground">Edit stock levels for multiple products at once</p>
        </div>
        <div className="flex gap-2">
          {/* Edit Mode Toggle */}
          <div className="flex rounded-lg border border-input overflow-hidden" data-testid="edit-mode-toggle">
            <button
              onClick={() => switchEditMode('set')}
              className={`px-3 py-2 text-sm font-medium transition-colors ${
                editMode === 'set' 
                  ? 'bg-primary text-primary-foreground' 
                  : 'bg-background hover:bg-muted'
              }`}
              data-testid="mode-set-btn"
            >
              <Settings2 className="h-4 w-4 inline mr-1" />
              Set Value
            </button>
            <button
              onClick={() => switchEditMode('adjust')}
              className={`px-3 py-2 text-sm font-medium transition-colors ${
                editMode === 'adjust' 
                  ? 'bg-green-600 text-white' 
                  : 'bg-background hover:bg-muted'
              }`}
              data-testid="mode-adjust-btn"
            >
              <Plus className="h-4 w-4 inline" />
              <Minus className="h-4 w-4 inline mr-1" />
              Quick Adjust
            </button>
          </div>
          <Button variant="outline" onClick={fetchData} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Changes Summary Bar */}
      {hasChanges && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3" data-testid="changes-bar">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-600" />
            <span className="font-medium text-amber-800">
              {changesCount} unsaved change{changesCount !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={clearChanges}
              data-testid="clear-changes-btn"
            >
              <X className="h-4 w-4 mr-2" />
              Clear All
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => saveChanges(true)}
              disabled={saving}
              data-testid="preview-btn"
            >
              Preview Changes
            </Button>
            <Button
              size="sm"
              onClick={() => saveChanges(false)}
              disabled={saving}
              className="bg-green-600 hover:bg-green-700"
              data-testid="save-changes-btn"
            >
              {saving ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              Save Changes
            </Button>
          </div>
        </div>
      )}

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-col lg:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search by product name or SKU..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
              data-testid="search-input"
            />
          </div>
          
          <div className="flex flex-wrap gap-2">
            <select
              value={supplierFilter}
              onChange={(e) => {
                setSupplierFilter(e.target.value);
                setPage(0);
              }}
              className="px-3 py-2 rounded-md border border-input bg-background text-sm"
              data-testid="supplier-filter"
            >
              <option value="">All Suppliers</option>
              {suppliers.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            
            <select
              value={selectedShowroom}
              onChange={(e) => setSelectedShowroom(e.target.value)}
              className="px-3 py-2 rounded-md border border-input bg-background text-sm"
              data-testid="showroom-filter"
            >
              <option value="all">All Showrooms</option>
              {showrooms.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            
            <Button variant="outline" size="sm" onClick={expandAll}>
              <ChevronDown className="h-4 w-4 mr-1" />
              Expand All
            </Button>
            <Button variant="outline" size="sm" onClick={collapseAll}>
              <ChevronUp className="h-4 w-4 mr-1" />
              Collapse All
            </Button>
          </div>
        </div>
        
        <div className="mt-3 text-sm text-muted-foreground">
          Showing {products.length} of {total} products
          {hasChanges && (
            <span className="ml-2 text-amber-600">
              ({changesCount} pending change{changesCount !== 1 ? 's' : ''})
            </span>
          )}
        </div>
      </Card>

      {/* Products Table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full" data-testid="bulk-stock-table">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left py-3 px-4 text-xs font-mono uppercase tracking-widest text-muted-foreground w-10">
                  
                </th>
                <th className="text-left py-3 px-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                  Product
                </th>
                <th className="text-left py-3 px-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                  SKU
                </th>
                <th className="text-left py-3 px-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                  Supplier
                </th>
                <th className="text-right py-3 px-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                  Total Stock
                </th>
                {selectedShowroom !== 'all' && (
                  <th className="text-right py-3 px-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                    {showrooms.find(s => s.id === selectedShowroom)?.name || 'Showroom'} Stock
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {products.length === 0 ? (
                <tr>
                  <td colSpan={selectedShowroom !== 'all' ? 6 : 5} className="text-center py-12 text-muted-foreground">
                    <Package className="h-12 w-12 mx-auto mb-3 opacity-20" />
                    <p>No products found</p>
                  </td>
                </tr>
              ) : (
                products.map(product => {
                  const isExpanded = expandedRows.has(product.id);
                  const hasProductChanges = changes[product.id] && Object.keys(changes[product.id]).length > 0;
                  
                  // Calculate new total if there are changes
                  let displayTotal = product.total_stock;
                  if (hasProductChanges) {
                    let totalAdjustment = 0;
                    Object.entries(changes[product.id]).forEach(([showroomId, change]) => {
                      const originalQty = getStockForShowroom(product, showroomId);
                      if (change.operation === 'add') {
                        totalAdjustment += change.value;
                      } else if (change.operation === 'subtract') {
                        totalAdjustment -= Math.min(change.value, originalQty);
                      } else {
                        // 'set' operation - calculate difference
                        totalAdjustment += (change.value - originalQty);
                      }
                    });
                    displayTotal = Math.max(0, product.total_stock + totalAdjustment);
                  }
                  
                  return (
                    <React.Fragment key={product.id}>
                      <tr 
                        className={`border-b border-border hover:bg-muted/30 cursor-pointer ${hasProductChanges ? 'bg-amber-50/50' : ''}`}
                        onClick={() => toggleRow(product.id)}
                        data-testid={`product-row-${product.id}`}
                      >
                        <td className="py-3 px-4">
                          <button className="p-1 hover:bg-muted rounded">
                            {isExpanded ? (
                              <ChevronUp className="h-4 w-4 text-muted-foreground" />
                            ) : (
                              <ChevronDown className="h-4 w-4 text-muted-foreground" />
                            )}
                          </button>
                        </td>
                        <td className="py-3 px-4">
                          <div className="font-medium">{product.name}</div>
                          {hasProductChanges && (
                            <span className="text-xs text-amber-600">Modified</span>
                          )}
                        </td>
                        <td className="py-3 px-4 font-mono text-sm">{product.sku || '-'}</td>
                        <td className="py-3 px-4 text-sm">{product.supplier_name || '-'}</td>
                        <td className="py-3 px-4 text-right tabular-nums font-medium">
                          {hasProductChanges ? (
                            <span className="text-amber-600">{displayTotal}</span>
                          ) : (
                            product.total_stock
                          )}
                        </td>
                        {selectedShowroom !== 'all' && (
                          <td className="py-3 px-4 text-right" onClick={e => e.stopPropagation()}>
                            {editMode === 'adjust' ? (
                              <div className="flex items-center justify-end gap-1">
                                <span className="text-xs text-muted-foreground mr-2">
                                  {getStockForShowroom(product, selectedShowroom)}
                                </span>
                                <button
                                  onClick={() => handleQuickAdjust(product.id, selectedShowroom, getStockForShowroom(product, selectedShowroom), -1)}
                                  className="w-7 h-7 rounded bg-red-100 hover:bg-red-200 text-red-700 flex items-center justify-center"
                                >
                                  <Minus className="h-3 w-3" />
                                </button>
                                <Input
                                  type="number"
                                  value={getCurrentValue(product.id, selectedShowroom, getStockForShowroom(product, selectedShowroom))}
                                  onChange={(e) => handleStockChange(product.id, selectedShowroom, e.target.value)}
                                  className="w-16 text-center"
                                  data-testid={`stock-input-${product.id}-${selectedShowroom}`}
                                />
                                <button
                                  onClick={() => handleQuickAdjust(product.id, selectedShowroom, getStockForShowroom(product, selectedShowroom), 1)}
                                  className="w-7 h-7 rounded bg-green-100 hover:bg-green-200 text-green-700 flex items-center justify-center"
                                >
                                  <Plus className="h-3 w-3" />
                                </button>
                              </div>
                            ) : (
                              <Input
                                type="number"
                                min="0"
                                value={getCurrentValue(
                                  product.id,
                                  selectedShowroom,
                                  getStockForShowroom(product, selectedShowroom)
                                )}
                                onChange={(e) => handleStockChange(product.id, selectedShowroom, e.target.value)}
                                className="w-24 text-right ml-auto"
                                data-testid={`stock-input-${product.id}-${selectedShowroom}`}
                              />
                            )}
                          </td>
                        )}
                      </tr>
                      
                      {/* Expanded Row - All Showrooms */}
                      {isExpanded && (
                        <tr className="bg-muted/20">
                          <td colSpan={selectedShowroom !== 'all' ? 6 : 5} className="px-4 py-3">
                            <div className="pl-8">
                              <div className="flex items-center gap-2 mb-3">
                                <Building2 className="h-4 w-4 text-muted-foreground" />
                                <span className="text-sm font-medium">Showroom Stock Allocation</span>
                                {editMode === 'adjust' && (
                                  <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">
                                    Quick Adjust Mode: +/- values
                                  </span>
                                )}
                              </div>
                              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                                {showrooms.map(showroom => {
                                  const originalQty = getStockForShowroom(product, showroom.id);
                                  const currentQty = getCurrentValue(product.id, showroom.id, originalQty);
                                  const resultQty = getResultValue(product.id, showroom.id, originalQty);
                                  const isChanged = changes[product.id]?.[showroom.id] !== undefined;
                                  const change = changes[product.id]?.[showroom.id];
                                  
                                  return (
                                    <div 
                                      key={showroom.id} 
                                      className={`p-2 rounded border ${isChanged ? 'border-amber-300 bg-amber-50' : 'border-border bg-background'}`}
                                    >
                                      <div className="flex items-center justify-between mb-1">
                                        <span className="text-sm font-medium truncate">{showroom.name}</span>
                                        {editMode === 'adjust' && (
                                          <span className="text-xs text-muted-foreground">
                                            Current: {originalQty}
                                          </span>
                                        )}
                                      </div>
                                      
                                      {editMode === 'adjust' ? (
                                        <div className="flex items-center gap-1">
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              handleQuickAdjust(product.id, showroom.id, originalQty, -1);
                                            }}
                                            className="w-8 h-8 rounded bg-red-100 hover:bg-red-200 text-red-700 flex items-center justify-center"
                                          >
                                            <Minus className="h-4 w-4" />
                                          </button>
                                          <div className="flex-1 text-center">
                                            <Input
                                              type="number"
                                              value={currentQty}
                                              onChange={(e) => handleStockChange(product.id, showroom.id, e.target.value)}
                                              onClick={(e) => e.stopPropagation()}
                                              className="w-full text-center"
                                              data-testid={`stock-input-expanded-${product.id}-${showroom.id}`}
                                            />
                                          </div>
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              handleQuickAdjust(product.id, showroom.id, originalQty, 1);
                                            }}
                                            className="w-8 h-8 rounded bg-green-100 hover:bg-green-200 text-green-700 flex items-center justify-center"
                                          >
                                            <Plus className="h-4 w-4" />
                                          </button>
                                        </div>
                                      ) : (
                                        <Input
                                          type="number"
                                          min="0"
                                          value={currentQty}
                                          onChange={(e) => handleStockChange(product.id, showroom.id, e.target.value)}
                                          onClick={(e) => e.stopPropagation()}
                                          className="w-full text-right"
                                          data-testid={`stock-input-expanded-${product.id}-${showroom.id}`}
                                        />
                                      )}
                                      
                                      {isChanged && editMode === 'adjust' && (
                                        <div className="text-xs mt-1 text-center">
                                          <span className={change?.operation === 'add' ? 'text-green-600' : 'text-red-600'}>
                                            {change?.operation === 'add' ? '+' : '-'}{change?.value}
                                          </span>
                                          <span className="text-muted-foreground mx-1">=</span>
                                          <span className="font-medium">{resultQty}</span>
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        
        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t bg-muted/30">
            <div className="text-sm text-muted-foreground">
              Page {page + 1} of {totalPages}
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Floating Save Button for mobile */}
      {hasChanges && (
        <div className="fixed bottom-6 right-6 sm:hidden">
          <Button
            onClick={() => saveChanges(false)}
            disabled={saving}
            className="bg-green-600 hover:bg-green-700 shadow-lg rounded-full h-14 w-14 p-0"
            data-testid="floating-save-btn"
          >
            {saving ? (
              <RefreshCw className="h-6 w-6 animate-spin" />
            ) : (
              <Save className="h-6 w-6" />
            )}
          </Button>
        </div>
      )}
    </div>
  );
};

export default BulkStockEdit;
