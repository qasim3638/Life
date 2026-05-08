import React, { useState, useMemo } from 'react';
import { 
  Globe, Settings2, RefreshCw, Check, FileText, Settings, Flag, Tag, Sparkles, X, 
  ChevronDown, ChevronUp, AlertCircle, Wand2, Eye, ExternalLink, Loader2, Plus,
  Trash2, Save, Box, Calculator, DollarSign, Percent, Star, ImageIcon, Package,
  Building2, CheckCircle, Palette, Grid3X3, Layers
} from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../../components/ui/dialog';
import { Button } from '../../../../components/ui/button';
import { Input } from '../../../../components/ui/input';
import { toast } from 'sonner';
import ManageOptionsModal from './ManageOptionsModal';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const BulkCategoryEditorModal = ({
  open,
  onOpenChange,
  showOptionsManager,
  setShowOptionsManager,
  selectedProducts,
  products,
  bulkCategorySelections,
  setBulkCategorySelections,
  setBulkSingleValue,
  bulkCategoryLoading,
  bulkShowOnWebsite,
  setBulkShowOnWebsite,
  bulkDescriptionSettings,
  setBulkDescriptionSettings,
  bulkDescriptionSaving,
  handleBulkGenerateDescription,
  bulkSaleSettings,
  setBulkSaleSettings,
  bulkSaleSaving,
  bulkTilesPerBoxSettings,
  setBulkTilesPerBoxSettings,
  bulkTilesPerBoxSaving,
  bulkEditTemplates,
  productOptions,
  optionsLoading,
  pricingSizeFilter,
  setPricingSizeFilter,
  tilesPerBoxSizeFilter,
  setTilesPerBoxSizeFilter,
  tierPricingConfig,
  setTierPricingConfig,
  showWebsitePreviewCard,
  setShowWebsitePreviewCard,
  expandedProductInGrid,
  setExpandedProductInGrid,
  getSelectedProductsForPreview,
  getWebsitePreviewUrl,
  getProductsFilteredBySize,
  getSelectedProductsPricing,
  getTierPricingFromProducts,
  getUniqueSizesFromSelected,
  publishSelectedToWebsite,
  publishingToWebsite,
  openOnWebsite,
  applyTemplate,
  deleteTemplate,
  clearPersistedState,
  onApplyClick,
  setShowPricingUnitModal,
  setShowQuoteSettingsModal,
  setShowTierPricingModal,
  CATEGORY_OPTIONS
}) => {
  const [showAllPreviews, setShowAllPreviews] = useState(false);

  // Get selected products list
  const selectedProductsList = useMemo(() => {
    return products.filter(p => selectedProducts.has(`${p.supplier}|||${p.sku}`));
  }, [products, selectedProducts]);

  // Count products with various attributes
  const withDescription = selectedProductsList.filter(p => p.description && p.description.trim()).length;
  const withMaterial = selectedProductsList.filter(p => p.material && p.material.trim()).length;
  const withFinish = selectedProductsList.filter(p => p.finish && p.finish.trim()).length;
  const withEdge = selectedProductsList.filter(p => p.edge && p.edge.trim()).length;
  const withMadeIn = selectedProductsList.filter(p => p.made_in && p.made_in.trim()).length;
  const withSaleLabels = selectedProductsList.filter(p => p.sale_labels && p.sale_labels.length > 0).length;
  const withRooms = selectedProductsList.filter(p => p.rooms && p.rooms.length > 0).length;
  const withStyles = selectedProductsList.filter(p => p.styles && p.styles.length > 0).length;
  const withColors = selectedProductsList.filter(p => p.colors && p.colors.length > 0).length;
  const total = selectedProducts.size;

  // Default countries for made_in
  const defaultCountries = [
    { id: 'Italy', label: '🇮🇹 Italy' },
    { id: 'Spain', label: '🇪🇸 Spain' },
    { id: 'Europe', label: '🇪🇺 Europe' },
    { id: 'Poland', label: '🇵🇱 Poland' },
    { id: 'India', label: '🇮🇳 India' },
    { id: 'China', label: '🇨🇳 China' },
    { id: 'Turkey', label: '🇹🇷 Turkey' },
    { id: 'Portugal', label: '🇵🇹 Portugal' },
    { id: 'UK', label: '🇬🇧 UK' },
    { id: 'Morocco', label: '🇲🇦 Morocco' },
    { id: 'Vietnam', label: '🇻🇳 Vietnam' },
    { id: 'Brazil', label: '🇧🇷 Brazil' }
  ];

  // Get countries from productOptions or use defaults
  // Handle both string arrays and object arrays with {id, label, color} format  
  const rawCountries = productOptions?.countries || [];
  const countries = rawCountries.length > 0 
    ? rawCountries.map(c => {
        if (typeof c === 'string') return { id: c, label: c };
        if (c && typeof c === 'object') return { id: c.id || c.label || String(c), label: c.label || c.id || String(c) };
        return { id: String(c), label: String(c) };
      })
    : defaultCountries;

  // Finishes from productOptions or defaults
  const rawFinishes = productOptions?.finishes || ['Matt', 'Gloss', 'Polished', 'Satin', 'Lappato', 'Natural', 'Honed', 'Textured', 'Structured', 'Anti-slip'];
  const finishes = rawFinishes.map(f => {
    if (typeof f === 'string') return f;
    if (f && typeof f === 'object') return f.label || f.id || String(f);
    return String(f);
  });

  // Colors from productOptions or defaults
  const defaultColors = ['White', 'Black', 'Grey', 'Beige', 'Brown', 'Blue', 'Green', 'Cream', 'Taupe', 'Charcoal', 'Multi'];
  // Handle both string arrays and object arrays with {id, label, color} format
  const rawColors = productOptions?.colors || defaultColors;
  const colors = rawColors.map(c => {
    if (typeof c === 'string') return c;
    if (c && typeof c === 'object') return c.label || c.id || String(c);
    return String(c);
  });

  // Preview products for website display
  const previewProducts = getSelectedProductsForPreview ? getSelectedProductsForPreview() : [];
  const firstProduct = previewProducts[0];

  return (
    <>
      <Dialog 
        open={open} 
        onOpenChange={onOpenChange}
        modal={!showOptionsManager}
      >
        <DialogContent 
          className="max-w-3xl max-h-[90vh] flex flex-col overflow-hidden" 
          style={{ pointerEvents: showOptionsManager ? 'none' : 'auto' }}
          onPointerDownOutside={(e) => {
            if (showOptionsManager) {
              e.preventDefault();
            }
          }} 
          onInteractOutside={(e) => {
            if (showOptionsManager) {
              e.preventDefault();
            }
          }}
        >
          <DialogHeader className="flex-shrink-0" style={{ pointerEvents: showOptionsManager ? 'none' : 'auto' }}>
            <DialogTitle className="flex items-center justify-between w-full">
              <span className="flex items-center gap-2 text-purple-700">
                <Globe className="w-5 h-5" />
                Bulk Category Editor
              </span>
              <button
                type="button"
                onClick={() => setShowOptionsManager(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-amber-100 text-amber-700 rounded-lg hover:bg-amber-200 transition-colors"
                title="Add, edit or delete attribute options"
                style={{ pointerEvents: 'auto' }}
              >
                <Settings2 className="w-4 h-4" />
                Manage Options
              </button>
            </DialogTitle>
          </DialogHeader>
          
          <div className="flex-1 overflow-y-auto py-4 space-y-6" style={{ pointerEvents: showOptionsManager ? 'none' : 'auto' }}>
            {/* Header Info */}
            <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg">
              <p className="text-purple-800 font-medium">
                Editing categories for {selectedProducts.size} selected products
              </p>
              <p className="text-sm text-purple-600 mt-1">
                Select categories below to assign them to all selected products.
              </p>
            </div>

            {/* Website Preview Panel */}
            {firstProduct && (
              <div className="p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-bold text-blue-800 flex items-center gap-2">
                    <Eye className="w-4 h-4" />
                    Website Preview
                    {!firstProduct.show_on_website && (
                      <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full ml-2">
                        Not Published
                      </span>
                    )}
                    {firstProduct.show_on_website && (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full ml-2">
                        Live
                      </span>
                    )}
                  </h3>
                  <div className="flex items-center gap-2">
                    {!firstProduct.show_on_website && publishSelectedToWebsite && (
                      <button
                        type="button"
                        onClick={publishSelectedToWebsite}
                        disabled={publishingToWebsite}
                        className="text-xs px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-1.5 disabled:opacity-50"
                      >
                        {publishingToWebsite ? (
                          <>
                            <Loader2 className="w-3 h-3 animate-spin" />
                            Publishing...
                          </>
                        ) : (
                          <>
                            <Globe className="w-3 h-3" />
                            Publish to Website
                          </>
                        )}
                      </button>
                    )}
                    {firstProduct.show_on_website && openOnWebsite && (
                      <button
                        type="button"
                        onClick={() => openOnWebsite(firstProduct)}
                        className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-1.5"
                      >
                        <ExternalLink className="w-3 h-3" />
                        View on Website
                      </button>
                    )}
                  </div>
                </div>
                
                {/* Preview Card */}
                <div className="bg-white rounded-lg p-3 shadow-sm">
                  <div className="flex gap-3">
                    {firstProduct.images?.[0] && (
                      <img 
                        src={firstProduct.images[0]} 
                        alt={firstProduct.display_name || firstProduct.product_name}
                        className="w-20 h-20 object-cover rounded"
                      />
                    )}
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 text-sm">
                        {firstProduct.display_name || firstProduct.product_name}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        {firstProduct.sku}
                      </p>
                      {firstProduct.price && (
                        <p className="text-sm font-semibold text-green-600 mt-1">
                          £{Number(firstProduct.price).toFixed(2)}/m²
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Category Selection */}
            <div className="space-y-4">
              {/* Material */}
              <div className="border rounded-lg p-3">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Material
                  <span className="text-xs text-gray-400 ml-2">({withMaterial}/{total} have material)</span>
                </label>
                <select
                  value={bulkCategorySelections?.material || ''}
                  onChange={(e) => setBulkSingleValue('material', e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                >
                  <option value="">-- Select Material --</option>
                  {(CATEGORY_OPTIONS?.material || ['Porcelain', 'Ceramic', 'Natural Stone', 'Glass', 'Metal', 'Wood', 'Vinyl', 'Laminate']).map(opt => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              </div>

              {/* Finish */}
              <div className="border rounded-lg p-3">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Finish
                  <span className="text-xs text-gray-400 ml-2">({withFinish}/{total} have finish)</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {finishes.map(finish => (
                    <button
                      key={finish}
                      type="button"
                      onClick={() => setBulkSingleValue('finish', bulkCategorySelections?.finish === finish ? '' : finish)}
                      className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                        bulkCategorySelections?.finish === finish
                          ? 'bg-purple-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      {finish}
                    </button>
                  ))}
                </div>
              </div>

              {/* Country of Origin */}
              <div className="border rounded-lg p-3">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Country of Origin
                  <span className="text-xs text-gray-400 ml-2">({withMadeIn}/{total} have origin)</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {countries.map(country => (
                    <button
                      key={country.id}
                      type="button"
                      onClick={() => setBulkSingleValue('made_in', bulkCategorySelections?.made_in === country.id ? '' : country.id)}
                      className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                        bulkCategorySelections?.made_in === country.id
                          ? 'bg-purple-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      {country.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Rooms */}
              <div className="border rounded-lg p-3">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Layers className="w-4 h-4 inline mr-1" />
                  Suitable Rooms
                  <span className="text-xs text-gray-400 ml-2">({withRooms}/{total} have rooms)</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {(CATEGORY_OPTIONS?.rooms || ['Kitchen', 'Bathroom', 'Living Room', 'Bedroom', 'Hallway', 'Outdoor', 'Commercial']).map(room => (
                    <button
                      key={room}
                      type="button"
                      onClick={() => {
                        const currentRooms = bulkCategorySelections?.rooms || [];
                        const newRooms = currentRooms.includes(room)
                          ? currentRooms.filter(r => r !== room)
                          : [...currentRooms, room];
                        setBulkCategorySelections(prev => ({ ...prev, rooms: newRooms }));
                      }}
                      className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                        (bulkCategorySelections?.rooms || []).includes(room)
                          ? 'bg-purple-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      {(bulkCategorySelections?.rooms || []).includes(room) && <Check className="w-3 h-3 inline mr-1" />}
                      {room}
                    </button>
                  ))}
                </div>
              </div>

              {/* Styles */}
              <div className="border rounded-lg p-3">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Palette className="w-4 h-4 inline mr-1" />
                  Styles
                  <span className="text-xs text-gray-400 ml-2">({withStyles}/{total} have styles)</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {(CATEGORY_OPTIONS?.styles || ['Modern', 'Traditional', 'Contemporary', 'Rustic', 'Industrial', 'Minimalist', 'Mediterranean', 'Victorian']).map(style => (
                    <button
                      key={style}
                      type="button"
                      onClick={() => {
                        const currentStyles = bulkCategorySelections?.styles || [];
                        const newStyles = currentStyles.includes(style)
                          ? currentStyles.filter(s => s !== style)
                          : [...currentStyles, style];
                        setBulkCategorySelections(prev => ({ ...prev, styles: newStyles }));
                      }}
                      className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                        (bulkCategorySelections?.styles || []).includes(style)
                          ? 'bg-purple-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      {(bulkCategorySelections?.styles || []).includes(style) && <Check className="w-3 h-3 inline mr-1" />}
                      {style}
                    </button>
                  ))}
                </div>
              </div>

              {/* Colors */}
              <div className="border rounded-lg p-3">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Grid3X3 className="w-4 h-4 inline mr-1" />
                  Colors
                  <span className="text-xs text-gray-400 ml-2">({withColors}/{total} have colors)</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {colors.map(color => (
                    <button
                      key={color}
                      type="button"
                      onClick={() => {
                        const currentColors = bulkCategorySelections?.colors || [];
                        const newColors = currentColors.includes(color)
                          ? currentColors.filter(c => c !== color)
                          : [...currentColors, color];
                        setBulkCategorySelections(prev => ({ ...prev, colors: newColors }));
                      }}
                      className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                        (bulkCategorySelections?.colors || []).includes(color)
                          ? 'bg-purple-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      {(bulkCategorySelections?.colors || []).includes(color) && <Check className="w-3 h-3 inline mr-1" />}
                      {color}
                    </button>
                  ))}
                </div>
              </div>

              {/* Sale Labels */}
              <div className="border rounded-lg p-3 bg-rose-50">
                <label className="block text-sm font-medium text-rose-700 mb-2">
                  <Tag className="w-4 h-4 inline mr-1" />
                  Sale & Labels
                  <span className="text-xs text-rose-400 ml-2">({withSaleLabels}/{total} have labels)</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {['SALE', 'NEW', 'BESTSELLER', 'LIMITED', 'CLEARANCE'].map(label => (
                    <button
                      key={label}
                      type="button"
                      onClick={() => {
                        const currentLabels = bulkCategorySelections?.sale_labels || [];
                        const newLabels = currentLabels.includes(label)
                          ? currentLabels.filter(l => l !== label)
                          : [...currentLabels, label];
                        setBulkCategorySelections(prev => ({ ...prev, sale_labels: newLabels }));
                      }}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                        (bulkCategorySelections?.sale_labels || []).includes(label)
                          ? 'bg-rose-600 text-white shadow-sm'
                          : 'bg-white text-rose-700 border border-rose-200 hover:bg-rose-100'
                      }`}
                    >
                      {(bulkCategorySelections?.sale_labels || []).includes(label) && <Check className="w-3 h-3 inline mr-1" />}
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {/* AI Description */}
              <div className="border rounded-lg p-3 bg-gradient-to-r from-indigo-50 to-purple-50">
                <label className="block text-sm font-medium text-indigo-700 mb-2">
                  <Sparkles className="w-4 h-4 inline mr-1" />
                  AI Description Generator
                  <span className="text-xs text-indigo-400 ml-2">({withDescription}/{total} have descriptions)</span>
                </label>
                
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="generate-descriptions"
                      checked={bulkDescriptionSettings?.enabled || false}
                      onChange={(e) => setBulkDescriptionSettings(prev => ({ ...prev, enabled: e.target.checked }))}
                      className="rounded border-indigo-300 text-indigo-600 focus:ring-indigo-500"
                    />
                    <label htmlFor="generate-descriptions" className="text-sm text-indigo-700">
                      Generate AI descriptions for selected products
                    </label>
                  </div>
                  
                  {bulkDescriptionSettings?.enabled && (
                    <div className="pl-6 space-y-2">
                      <select
                        value={bulkDescriptionSettings?.mode || 'empty_only'}
                        onChange={(e) => setBulkDescriptionSettings(prev => ({ ...prev, mode: e.target.value }))}
                        className="w-full border rounded-lg px-3 py-2 text-sm"
                      >
                        <option value="empty_only">Only products without descriptions ({total - withDescription} products)</option>
                        <option value="all">Regenerate for all selected ({total} products)</option>
                      </select>
                      
                      <Button
                        type="button"
                        onClick={handleBulkGenerateDescription}
                        disabled={bulkDescriptionSaving}
                        className="w-full bg-indigo-600 hover:bg-indigo-700"
                      >
                        {bulkDescriptionSaving ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Generating...
                          </>
                        ) : (
                          <>
                            <Wand2 className="w-4 h-4 mr-2" />
                            Generate Descriptions
                          </>
                        )}
                      </Button>
                    </div>
                  )}
                </div>
              </div>

              {/* Pricing Section */}
              <div className="border rounded-lg p-3">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <DollarSign className="w-4 h-4 inline mr-1" />
                  Pricing
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Cost Price (£/m²)</label>
                    <Input
                      type="number"
                      step="0.01"
                      value={bulkCategorySelections?.cost_price || ''}
                      onChange={(e) => setBulkSingleValue('cost_price', e.target.value)}
                      placeholder="0.00"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">List Price (£/m²)</label>
                    <Input
                      type="number"
                      step="0.01"
                      value={bulkCategorySelections?.list_price || ''}
                      onChange={(e) => setBulkSingleValue('list_price', e.target.value)}
                      placeholder="0.00"
                    />
                  </div>
                </div>
                
                {/* Quick Actions */}
                <div className="flex flex-wrap gap-2 mt-3">
                  {setShowTierPricingModal && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setShowTierPricingModal(true)}
                    >
                      <Percent className="w-4 h-4 mr-1" />
                      Set Tier Discounts
                    </Button>
                  )}
                </div>
              </div>

              {/* Templates Section */}
              {bulkEditTemplates && bulkEditTemplates.length > 0 && (
                <div className="border rounded-lg p-3 bg-amber-50">
                  <label className="block text-sm font-medium text-amber-700 mb-2">
                    <FileText className="w-4 h-4 inline mr-1" />
                    Saved Templates
                  </label>
                  <div className="space-y-2">
                    {bulkEditTemplates.map((template, idx) => (
                      <div 
                        key={idx}
                        className="flex items-center justify-between bg-white rounded-lg px-3 py-2 border border-amber-200"
                      >
                        <span className="text-sm font-medium text-amber-800">{template.name}</span>
                        <div className="flex items-center gap-2">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => applyTemplate(template)}
                          >
                            Apply
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => deleteTemplate(template.name)}
                            className="text-red-600 hover:text-red-700"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Summary of what will be applied */}
              <div className="border rounded-lg p-3 bg-gray-50">
                <p className="text-xs font-semibold text-purple-700 mb-2">ATTRIBUTES TO BE APPLIED:</p>
                <div className="flex flex-wrap gap-2">
                  {bulkCategorySelections?.material && (
                    <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs">
                      Material: {bulkCategorySelections.material}
                    </span>
                  )}
                  {bulkCategorySelections?.finish && (
                    <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs">
                      Finish: {bulkCategorySelections.finish}
                    </span>
                  )}
                  {bulkCategorySelections?.made_in && (
                    <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs">
                      Origin: {bulkCategorySelections.made_in}
                    </span>
                  )}
                  {(bulkCategorySelections?.rooms || []).length > 0 && (
                    <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs">
                      Rooms: {bulkCategorySelections.rooms.join(', ')}
                    </span>
                  )}
                  {(bulkCategorySelections?.styles || []).length > 0 && (
                    <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs">
                      Styles: {bulkCategorySelections.styles.join(', ')}
                    </span>
                  )}
                  {(bulkCategorySelections?.colors || []).length > 0 && (
                    <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs">
                      Colors: {bulkCategorySelections.colors.join(', ')}
                    </span>
                  )}
                  {(bulkCategorySelections?.sale_labels || []).length > 0 && (
                    <span className="px-2 py-1 bg-rose-100 text-rose-700 rounded text-xs">
                      Labels: {bulkCategorySelections.sale_labels.join(', ')}
                    </span>
                  )}
                  {bulkCategorySelections?.cost_price && (
                    <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs">
                      Cost: £{bulkCategorySelections.cost_price}
                    </span>
                  )}
                  {bulkCategorySelections?.list_price && (
                    <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs">
                      Price: £{bulkCategorySelections.list_price}
                    </span>
                  )}
                  {Object.keys(bulkCategorySelections || {}).filter(k => 
                    bulkCategorySelections[k] && 
                    !['material', 'finish', 'made_in', 'rooms', 'styles', 'colors', 'sale_labels', 'cost_price', 'list_price'].includes(k) &&
                    (typeof bulkCategorySelections[k] !== 'object' || (Array.isArray(bulkCategorySelections[k]) && bulkCategorySelections[k].length > 0))
                  ).length === 0 && !bulkCategorySelections?.material && !bulkCategorySelections?.finish && !bulkCategorySelections?.made_in && (
                    <span className="text-xs text-gray-500 italic">No attributes selected yet</span>
                  )}
                </div>
              </div>
            </div>
          </div>
          
          <DialogFooter className="flex-shrink-0 border-t pt-4">
            <Button 
              variant="outline" 
              onClick={() => {
                onOpenChange(false);
                setBulkCategorySelections({
                  material: '', finish: '', type: '', edge: '', slip_rating: '', suitability: '',
                  cost_price: '', list_price: '',
                  rooms: [], styles: [], colors: [], features: []
                });
                setBulkShowOnWebsite(false);
                if (clearPersistedState) clearPersistedState();
              }}
            >
              Cancel
            </Button>
            <Button 
              onClick={onApplyClick}
              disabled={bulkCategoryLoading}
              className="bg-purple-600 hover:bg-purple-700"
            >
              {bulkCategoryLoading ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Updating...
                </>
              ) : (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  Apply to {selectedProducts.size} Products
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Options Manager Modal */}
      <ManageOptionsModal
        isOpen={showOptionsManager}
        onClose={() => setShowOptionsManager(false)}
        productOptions={productOptions}
        optionsLoading={optionsLoading}
      />
    </>
  );
};

export default BulkCategoryEditorModal;
