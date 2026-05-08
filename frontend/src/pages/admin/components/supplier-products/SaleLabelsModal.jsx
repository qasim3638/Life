/**
 * SaleLabelsModal - Modal for managing sale and labels on single product
 * Extracted from SupplierProducts.js for better maintainability
 */

import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../../../components/ui/dialog';
import { Button } from '../../../../components/ui/button';
import { Input } from '../../../../components/ui/input';
import {
  Tag,
  Eye,
  Package,
  BadgePercent,
  Percent,
  Zap,
  AlertCircle,
  Star,
  Plus,
  X,
  RefreshCw,
  Save,
} from 'lucide-react';

const PRESET_LABELS = ['Sale', 'Clearance', 'New Arrival', 'Limited Stock', 'Best Seller'];

const SaleLabelsModal = ({
  open,
  onOpenChange,
  product,
  form,
  setForm,
  loading,
  onSave,
  onTogglePresetLabel,
  onAddCustomLabel,
  onRemoveCustomLabel,
  onWasMarkupChange,
  onWasPriceChange,
  calculateSavings,
  calculateProfit,
  dbLabels = [],
  getLabelStyle,
}) => {
  if (!product) return null;

  const labelNames = dbLabels.length > 0 ? dbLabels.map(l => l.name) : PRESET_LABELS;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Tag className="w-5 h-5 text-rose-600" />
            Sale & Labels
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-6">
          {/* LIVE PREVIEW - How product will look */}
          <div className="bg-gradient-to-r from-slate-50 to-slate-100 p-4 rounded-xl border-2 border-dashed border-slate-300">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-1">
              <Eye className="w-3 h-3" /> Live Preview
            </p>
            <div className="bg-white rounded-lg p-4 shadow-sm">
              {/* Product Name with Labels */}
              <div className="flex items-start gap-3">
                <div className="w-16 h-16 bg-gray-200 rounded-lg flex items-center justify-center text-gray-400">
                  <Package className="w-8 h-8" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center flex-wrap gap-1.5 mb-1">
                    <span className="font-semibold text-gray-900">{product.product_name || product.name}</span>
                    {/* Show selected labels as badges */}
                    {form.sale_active && form.discount_percentage && (
                      <span className="inline-flex items-center gap-1 bg-red-500 text-white text-xs px-2 py-0.5 rounded-full font-bold animate-pulse">
                        <BadgePercent className="w-3 h-3" />
                        {form.discount_percentage}% OFF
                      </span>
                    )}
                    {form.labels.map((label, idx) => {
                      const style = getLabelStyle ? getLabelStyle(label) : { bg: '#f3f4f6', text: '#374151' };
                      return (
                        <span key={idx} className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium"
                          style={{ backgroundColor: style.bg, color: style.text }}>
                          {label}
                        </span>
                      );
                    })}
                    {form.custom_labels.map((label, idx) => {
                      const style = getLabelStyle ? getLabelStyle(label) : { bg: '#eef2ff', text: '#4338ca' };
                      return (
                        <span key={`c-${idx}`} className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium"
                          style={{ backgroundColor: style.bg, color: style.text }}>
                          {label}
                        </span>
                      );
                    })}
                  </div>
                  <p className="text-sm text-gray-500">SKU: {product.sku}</p>
                  
                  {/* Price Display */}
                  <div className="mt-2">
                    {form.sale_active && form.now_price ? (
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-400 line-through">
                          WAS £{Number(form.was_price || product.price).toFixed(2)}
                        </span>
                        <span className="text-lg font-bold text-red-600">
                          NOW £{Number(form.now_price).toFixed(2)}
                        </span>
                        <span className="text-xs bg-red-100 text-red-600 px-1.5 py-0.5 rounded font-medium">
                          SAVE £{(Number(form.was_price || product.price) - Number(form.now_price)).toFixed(2)}
                        </span>
                      </div>
                    ) : (
                      <span className="text-lg font-semibold text-green-600">
                        £{Number(product.price || 0).toFixed(2)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Labels */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Labels</label>
            <div className="flex flex-wrap gap-2">
              {labelNames.map(label => {
                const style = getLabelStyle ? getLabelStyle(label) : { bg: '#f3f4f6', text: '#374151', color: '#6b7280' };
                const isActive = form.labels.includes(label);
                return (
                  <button
                    key={label}
                    onClick={() => onTogglePresetLabel(label)}
                    className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                      isActive ? 'ring-2 ring-offset-1 text-white' : 'hover:opacity-80'
                    }`}
                    style={isActive
                      ? { backgroundColor: style.color, color: 'white', ringColor: style.color }
                      : { backgroundColor: style.bg, color: style.text }
                    }
                    data-testid={`label-${label.toLowerCase().replace(/\s+/g, '-')}`}
                  >
                    <Tag className="w-3 h-3" />
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Custom Labels (for per-product one-offs) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Custom Labels (per product)</label>
            <div className="flex gap-2 mb-2">
              <Input
                value={form.newCustomLabel}
                onChange={(e) => setForm(prev => ({ ...prev, newCustomLabel: e.target.value }))}
                placeholder="Add custom label..."
                className="flex-1"
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), onAddCustomLabel())}
                data-testid="custom-label-input"
              />
              <Button onClick={onAddCustomLabel} variant="outline" size="sm">
                <Plus className="w-4 h-4" />
              </Button>
            </div>
            {form.custom_labels.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {form.custom_labels.map((label, idx) => (
                  <span key={idx} className="inline-flex items-center gap-1 bg-indigo-100 text-indigo-700 px-2 py-1 rounded-full text-sm">
                    {label}
                    <button onClick={() => onRemoveCustomLabel(label)} className="hover:text-indigo-900">
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Sale Pricing Section */}
          <div className="border-t pt-4">
            <div className="flex items-center gap-2 mb-4">
              <input
                type="checkbox"
                id="sale-active"
                checked={form.sale_active}
                onChange={(e) => setForm(prev => ({ ...prev, sale_active: e.target.checked }))}
                className="w-4 h-4 rounded border-gray-300 text-red-600 focus:ring-red-500"
                data-testid="sale-active-checkbox"
              />
              <label htmlFor="sale-active" className="text-sm font-medium text-gray-700">
                Enable WAS/NOW Sale Display
              </label>
            </div>

            {form.sale_active && (
              <div className="space-y-4">
                {/* Current List Price (NOW - read only) */}
                <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm text-green-700 font-medium">NOW Price (List Price)</span>
                      <p className="text-xs text-green-600">Your actual selling price - cannot be changed here</p>
                    </div>
                    <div className="text-2xl font-bold text-green-700">
                      £{parseFloat(form.list_price || 0).toFixed(2)}
                    </div>
                  </div>
                </div>

                {/* WAS Price Settings */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      WAS Markup (%)
                    </label>
                    <Input
                      type="number"
                      step="1"
                      value={form.was_markup_percent}
                      onChange={(e) => onWasMarkupChange(e.target.value)}
                      placeholder="e.g., 30"
                      data-testid="was-markup-input"
                    />
                    <p className="text-xs text-gray-500 mt-1">Add % on top of list price</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      OR Enter WAS Price (£)
                    </label>
                    <Input
                      type="number"
                      step="0.01"
                      value={form.was_price}
                      onChange={(e) => onWasPriceChange(e.target.value)}
                      placeholder="e.g., 39.99"
                      data-testid="was-price-input"
                    />
                    <p className="text-xs text-gray-500 mt-1">Direct WAS price entry</p>
                  </div>
                </div>

                {/* Preview Display */}
                {form.was_price && parseFloat(form.was_price) > parseFloat(form.list_price) && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <h4 className="text-sm font-semibold text-red-800 mb-2">Preview - How it will display:</h4>
                    <div className="flex items-center gap-4">
                      <div>
                        <span className="text-gray-400 line-through text-lg">
                          WAS £{parseFloat(form.was_price).toFixed(2)}
                        </span>
                      </div>
                      <div>
                        <span className="text-red-600 font-bold text-2xl">
                          NOW £{parseFloat(form.list_price).toFixed(2)}
                        </span>
                      </div>
                      <div className="bg-red-600 text-white px-2 py-1 rounded text-sm font-bold">
                        SAVE £{calculateSavings()?.savings} ({calculateSavings()?.percent}% OFF)
                      </div>
                    </div>
                  </div>
                )}

                {/* Profit Info */}
                {calculateProfit() && (
                  <div className="bg-blue-50 border border-blue-200 p-3 rounded-lg">
                    <p className="text-sm text-blue-800">
                      <span className="font-medium">Your Profit:</span> £{calculateProfit().profit} 
                      <span className="text-gray-500 ml-2">({calculateProfit().margin}% margin)</span>
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      Based on cost price: £{product?.cost_price?.toFixed(2) || '0.00'}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={onSave}
            disabled={loading}
            className="bg-rose-600 hover:bg-rose-700"
            data-testid="save-sale-labels-btn"
          >
            {loading ? (
              <><RefreshCw className="w-4 h-4 mr-2 animate-spin" /> Saving...</>
            ) : (
              <><Save className="w-4 h-4 mr-2" /> Save</>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SaleLabelsModal;
