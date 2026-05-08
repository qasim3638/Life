import React, { useMemo } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../../components/ui/dialog';
import { Button } from '../../../../components/ui/button';
import { ArrowRight, Check, AlertTriangle, Eye, Pencil } from 'lucide-react';

const formatFieldName = (key) => {
  return key
    .replace(/^(cat_|filter_|spec_)/, '')
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
};

// Map dry run field names back to editor section IDs
const getFieldSectionId = (field, type) => {
  const lower = field.toLowerCase();
  if (type === 'pricing') return 'editor-section-pricing';
  if (type === 'categories') return 'editor-section-categories';
  if (type === 'filter') return 'editor-section-filters';
  if (type === 'spec') return 'editor-section-specifications';
  if (['material', 'finish', 'type', 'edge', 'slip rating', 'suitability', 'thickness', 'underfloor heating'].includes(lower)) return 'editor-section-specifications';
  if (['rooms', 'styles', 'colors', 'features', 'materials', 'sub categories'].includes(lower)) return 'editor-section-filters';
  if (lower === 'made in') return 'editor-section-made-in';
  return null;
};

const DryRunPreview = ({
  open,
  onClose,
  onConfirm,
  onEditField,
  bulkCategorySelections,
  products,
  selectedProducts,
  bulkFieldBreakdowns,
  bulkCategoryMode,
  loading,
}) => {
  const changes = useMemo(() => {
    if (!open) return [];
    const result = [];
    const selectedList = products.filter(p => {
      const key = `${p.supplier || 'unknown'}|||${p.sku || p.supplier_code || p._id}`;
      return selectedProducts.has(key);
    });
    const total = selectedList.length;

    // Scalar fields
    const scalarFields = [
      'material', 'finish', 'type', 'edge', 'slip_rating',
      'suitability', 'thickness', 'underfloor_heating', 'made_in',
    ];
    for (const field of scalarFields) {
      const newVal = bulkCategorySelections[field];
      if (!newVal || newVal === '__CLEAR__') {
        if (newVal === '__CLEAR__') {
          const breakdown = bulkFieldBreakdowns[field] || {};
          const haveValue = Object.entries(breakdown).reduce((sum, [, c]) => sum + c, 0);
          if (haveValue > 0) {
            result.push({ field: formatFieldName(field), type: 'clear', currentBreakdown: breakdown, affected: haveValue, total, rawKey: field });
          }
        }
        continue;
      }
      const breakdown = bulkFieldBreakdowns[field] || {};
      const alreadySet = breakdown[newVal] || 0;
      const willChange = total - alreadySet;
      result.push({
        field: formatFieldName(field), type: 'scalar', newValue: newVal,
        alreadyCorrect: alreadySet, willChange, currentBreakdown: breakdown, total, rawKey: field,
      });
    }

    // Array fields
    const arrayFields = [
      { key: 'rooms', label: 'Rooms' },
      { key: 'styles', label: 'Styles' },
      { key: 'colors', label: 'Colors' },
      { key: 'features', label: 'Features' },
      { key: 'materials', label: 'Materials' },
      { key: 'sub_categories', label: 'Sub Categories' },
    ];
    for (const { key, label } of arrayFields) {
      const newVals = bulkCategorySelections[key];
      if (!newVals || newVals.length === 0) continue;
      const breakdown = bulkFieldBreakdowns[`_array_${key}`] || {};
      result.push({
        field: label, type: 'array', newValues: newVals,
        mode: bulkCategoryMode, currentBreakdown: breakdown, total, rawKey: key,
      });
    }

    // Category selections (cat_*)
    const catKeys = Object.keys(bulkCategorySelections).filter(k => k.startsWith('cat_') && bulkCategorySelections[k]);
    if (catKeys.length > 0) {
      result.push({
        field: 'Categories', type: 'categories',
        categories: catKeys.map(k => formatFieldName(k)), total, rawKey: 'categories',
      });
    }

    // Filter selections (filter_*)
    const filterKeys = Object.keys(bulkCategorySelections).filter(k => k.startsWith('filter_') && bulkCategorySelections[k]);
    for (const key of filterKeys) {
      const vals = bulkCategorySelections[key];
      if (!vals || (Array.isArray(vals) && vals.length === 0)) continue;
      result.push({
        field: formatFieldName(key), type: 'filter',
        newValues: Array.isArray(vals) ? vals : [vals], total, rawKey: key,
      });
    }

    // Spec selections (spec_*)
    const specKeys = Object.keys(bulkCategorySelections).filter(k => k.startsWith('spec_') && bulkCategorySelections[k]);
    for (const key of specKeys) {
      const val = bulkCategorySelections[key];
      if (!val || (Array.isArray(val) && val.length === 0)) continue;
      result.push({
        field: formatFieldName(key), type: 'spec',
        newValue: Array.isArray(val) ? val.join(', ') : val, total, rawKey: key,
      });
    }

    // Pricing
    if (bulkCategorySelections.cost_price) {
      result.push({ field: 'Cost Price', type: 'pricing', newValue: `£${bulkCategorySelections.cost_price}`, total, rawKey: 'cost_price' });
    }
    if (bulkCategorySelections.list_price) {
      result.push({ field: 'List Price', type: 'pricing', newValue: `£${bulkCategorySelections.list_price}`, total, rawKey: 'list_price' });
    }

    return result;
  }, [open, bulkCategorySelections, products, selectedProducts, bulkFieldBreakdowns, bulkCategoryMode]);

  const handleEditClick = (change) => {
    const sectionId = getFieldSectionId(change.field, change.type);
    if (onEditField) {
      onEditField(sectionId, change.rawKey);
    }
  };

  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[80vh] flex flex-col" data-testid="dry-run-dialog">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <Eye className="w-5 h-5 text-blue-600" />
            Preview Changes (Dry Run)
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-2 py-2 min-h-0">
          {changes.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-amber-400" />
              <p className="font-medium">No changes detected</p>
              <p className="text-sm">Select attributes in the editor first</p>
            </div>
          ) : (
            <>
              <p className="text-xs text-gray-500 px-1">
                {changes.length} attribute{changes.length !== 1 ? 's' : ''} will be modified across {changes[0]?.total || 0} products.
                Click any row to edit.
              </p>
              {changes.map((change, i) => (
                <div
                  key={i}
                  className="border rounded-lg p-3 bg-gray-50 cursor-pointer hover:bg-blue-50 hover:border-blue-300 transition-colors group"
                  data-testid={`dry-run-change-${i}`}
                  onClick={() => handleEditClick(change)}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-sm text-gray-800 flex items-center gap-1.5">
                      {change.field}
                      <Pencil className="w-3 h-3 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </span>
                    <span className="text-xs text-gray-500">
                      {change.total} product{change.total !== 1 ? 's' : ''}
                    </span>
                  </div>

                  {change.type === 'scalar' && (
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-gray-500">
                          {Object.keys(change.currentBreakdown).length > 0
                            ? Object.entries(change.currentBreakdown)
                                .map(([v, c]) => `${v} (${c})`)
                                .join(', ')
                            : '(empty)'}
                        </span>
                        <ArrowRight className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                        <span className="font-medium text-blue-700">{change.newValue}</span>
                      </div>
                      {change.alreadyCorrect > 0 && (
                        <p className="text-xs text-green-600 flex items-center gap-1">
                          <Check className="w-3 h-3" />
                          {change.alreadyCorrect} already set to {change.newValue}
                        </p>
                      )}
                      {change.willChange > 0 && (
                        <p className="text-xs text-amber-600">
                          {change.willChange} will be changed
                        </p>
                      )}
                    </div>
                  )}

                  {change.type === 'clear' && (
                    <div className="text-sm text-red-600">
                      Will clear value from {change.affected} products
                    </div>
                  )}

                  {change.type === 'array' && (
                    <div className="space-y-1">
                      <div className="flex flex-wrap gap-1">
                        {change.newValues.map(v => (
                          <span key={v} className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                            {v}
                          </span>
                        ))}
                      </div>
                      <p className="text-xs text-gray-500">
                        Mode: {change.mode === 'replace' ? 'Replace existing' : 'Append to existing'}
                      </p>
                    </div>
                  )}

                  {change.type === 'categories' && (
                    <div className="flex flex-wrap gap-1">
                      {change.categories.map(c => (
                        <span key={c} className="px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">
                          {c}
                        </span>
                      ))}
                    </div>
                  )}

                  {change.type === 'filter' && (
                    <div className="flex flex-wrap gap-1">
                      {change.newValues.map(v => (
                        <span key={v} className="px-1.5 py-0.5 bg-teal-100 text-teal-700 rounded text-xs">
                          {v}
                        </span>
                      ))}
                    </div>
                  )}

                  {(change.type === 'spec' || change.type === 'pricing') && (
                    <div className="text-sm">
                      <ArrowRight className="w-3.5 h-3.5 text-blue-500 inline mr-1" />
                      <span className="font-medium text-blue-700">{change.newValue}</span>
                    </div>
                  )}
                </div>
              ))}
            </>
          )}
        </div>

        <DialogFooter className="flex-shrink-0 border-t pt-3">
          <Button variant="outline" onClick={onClose}>
            Go Back
          </Button>
          <Button
            onClick={onConfirm}
            disabled={changes.length === 0 || loading}
            className="bg-green-600 hover:bg-green-700"
            data-testid="dry-run-confirm-btn"
          >
            <Check className="w-4 h-4 mr-2" />
            Confirm & Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default DryRunPreview;
