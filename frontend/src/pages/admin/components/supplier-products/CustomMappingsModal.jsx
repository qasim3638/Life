import React from 'react';
import { PenLine, RefreshCw, Check, X, Edit2, Trash2, Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../../components/ui/dialog';
import { Button } from '../../../../components/ui/button';
import { Input } from '../../../../components/ui/input';

const CustomMappingsModal = ({
  open,
  onOpenChange,
  customMappings,
  customMappingsLoading,
  customMappingsSearch,
  setCustomMappingsSearch,
  customMappingsFilter,
  setCustomMappingsFilter,
  customMappingsBySupplier,
  filteredCustomMappings,
  editingMapping,
  setEditingMapping,
  fetchCustomMappings,
  updateCustomMapping,
  deleteCustomMapping,
  SUPPLIERS
}) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <PenLine className="w-5 h-5 text-indigo-600" />
            Custom Name Mappings
          </DialogTitle>
          <p className="text-sm text-muted-foreground">
            Products with custom names that override auto-generated names during sync
          </p>
        </DialogHeader>
        
        <div className="flex-1 overflow-hidden flex flex-col">
          {/* Filters */}
          <div className="flex items-center gap-3 py-3 border-b">
            <div className="flex-1">
              <Input
                placeholder="Search by name or SKU..."
                value={customMappingsSearch}
                onChange={(e) => setCustomMappingsSearch(e.target.value)}
                className="max-w-xs"
              />
            </div>
            <select
              value={customMappingsFilter}
              onChange={(e) => setCustomMappingsFilter(e.target.value)}
              className="border rounded-lg px-3 py-2 text-sm"
            >
              <option value="all">All Suppliers ({customMappings.length})</option>
              {Object.entries(customMappingsBySupplier).sort((a, b) => a[0].localeCompare(b[0])).map(([supplier, count]) => (
                <option key={supplier} value={supplier}>{supplier} ({count})</option>
              ))}
            </select>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchCustomMappings}
              disabled={customMappingsLoading}
            >
              <RefreshCw className={`w-4 h-4 ${customMappingsLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
          
          {/* Mappings List */}
          <div className="flex-1 overflow-y-auto py-3">
            {customMappingsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
              </div>
            ) : filteredCustomMappings.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <PenLine className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p className="font-medium">No custom mappings found</p>
                <p className="text-sm mt-1">
                  {customMappings.length === 0 
                    ? "Custom mappings are created when you edit a product's display name via Quick Edit"
                    : "Try adjusting your search or filter"}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredCustomMappings.map((mapping, idx) => (
                  <div 
                    key={`${mapping.supplier}-${mapping.sku}-${idx}`}
                    className="border rounded-lg p-3 hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-start gap-3">
                      {/* Supplier Badge */}
                      <span className={`px-2 py-1 text-xs rounded-full font-medium shrink-0 ${
                        SUPPLIERS.find(s => s.id === mapping.supplier)?.color || 'bg-gray-500'
                      } text-white`}>
                        {mapping.supplier}
                      </span>
                      
                      {/* Name Info */}
                      <div className="flex-1 min-w-0">
                        {editingMapping === `${mapping.supplier}-${mapping.sku}` ? (
                          <div className="flex items-center gap-2">
                            <Input
                              defaultValue={mapping.custom_name}
                              id={`edit-${mapping.supplier}-${mapping.sku}`}
                              className="flex-1"
                              autoFocus
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  updateCustomMapping(mapping.supplier, mapping.sku, e.target.value);
                                } else if (e.key === 'Escape') {
                                  setEditingMapping(null);
                                }
                              }}
                            />
                            <Button
                              size="sm"
                              variant="default"
                              onClick={() => {
                                const input = document.getElementById(`edit-${mapping.supplier}-${mapping.sku}`);
                                if (input) updateCustomMapping(mapping.supplier, mapping.sku, input.value);
                              }}
                            >
                              <Check className="w-4 h-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setEditingMapping(null)}
                            >
                              <X className="w-4 h-4" />
                            </Button>
                          </div>
                        ) : (
                          <>
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-foreground">{mapping.custom_name}</span>
                              <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                                {mapping.sku}
                              </span>
                            </div>
                            <div className="text-sm text-muted-foreground mt-1 flex items-center gap-1">
                              <span className="line-through">{mapping.original_name || 'Unknown original'}</span>
                              <span className="text-xs">→</span>
                              <span className="text-indigo-600 font-medium">{mapping.custom_name}</span>
                            </div>
                            {mapping.updated_at && (
                              <div className="text-xs text-muted-foreground mt-1">
                                Last updated: {new Date(mapping.updated_at).toLocaleDateString()}
                                {mapping.updated_by && ` by ${mapping.updated_by}`}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                      
                      {/* Actions */}
                      {editingMapping !== `${mapping.supplier}-${mapping.sku}` && (
                        <div className="flex items-center gap-1 shrink-0">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setEditingMapping(`${mapping.supplier}-${mapping.sku}`)}
                          >
                            <Edit2 className="w-4 h-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            onClick={() => deleteCustomMapping(mapping.supplier, mapping.sku)}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          
          {/* Summary */}
          {customMappings.length > 0 && (
            <div className="border-t pt-3 text-sm text-muted-foreground">
              Showing {filteredCustomMappings.length} of {customMappings.length} custom mappings
              {Object.keys(customMappingsBySupplier).length > 0 && (
                <span className="ml-2">
                  ({Object.entries(customMappingsBySupplier).map(([s, c]) => `${s}: ${c}`).join(', ')})
                </span>
              )}
            </div>
          )}
        </div>
        
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default CustomMappingsModal;
