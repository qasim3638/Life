import React, { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { 
  FolderTree, Plus, Edit2, Trash2, RefreshCw, Search, 
  Eye, EyeOff, ArrowUpDown, Merge, Save, X, Package,
  GripVertical, ChevronDown, ChevronUp, Settings, DollarSign, Percent
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function ManageCategories() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('name'); // name, products, order
  const [sortDir, setSortDir] = useState('asc');
  
  // Modal states
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showMergeModal, setShowMergeModal] = useState(false);
  
  // Form states
  const [newCategoryName, setNewCategoryName] = useState('');
  const [editingCategory, setEditingCategory] = useState(null);
  const [editForm, setEditForm] = useState({ name: '', show_on_website: true, display_order: 999 });
  const [deletingCategory, setDeletingCategory] = useState(null);
  const [replacementCategory, setReplacementCategory] = useState('');
  const [selectedForMerge, setSelectedForMerge] = useState([]);
  const [mergeTarget, setMergeTarget] = useState('');
  
  const [actionLoading, setActionLoading] = useState(false);
  
  // Tier Pricing Settings
  const [showTierSettings, setShowTierSettings] = useState(false);
  const [tierConfig, setTierConfig] = useState({
    thresholds: [10, 50, 100],
    discounts: [0, 5, 10, 15],
    custom_quote_threshold: 150,
    trade_discount_default: 5,
    credit_back_default: 2
  });
  const [tierLoading, setTierLoading] = useState(false);

  // Fetch categories
  const fetchCategories = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/supplier-sync/categories/detailed`);
      if (response.ok) {
        const data = await response.json();
        setCategories(data.categories || []);
      } else {
        toast.error('Failed to fetch categories');
      }
    } catch (error) {
      console.error('Error:', error);
      toast.error('Failed to fetch categories');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCategories();
    fetchTierConfig();
  }, []);

  // Fetch tier pricing config
  const fetchTierConfig = async () => {
    try {
      const response = await fetch(`${API_URL}/api/tiles/pricing/tiers`);
      if (response.ok) {
        const data = await response.json();
        setTierConfig(data);
      }
    } catch (error) {
      console.error('Error fetching tier config:', error);
    }
  };

  // Save tier pricing config
  const saveTierConfig = async () => {
    setTierLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/tiles/pricing/tiers`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(tierConfig)
      });
      if (response.ok) {
        toast.success('Tier pricing settings saved!');
        setShowTierSettings(false);
      } else {
        toast.error('Failed to save tier settings');
      }
    } catch (error) {
      console.error('Error saving tier config:', error);
      toast.error('Failed to save tier settings');
    } finally {
      setTierLoading(false);
    }
  };

  // Filter and sort categories
  const filteredCategories = categories
    .filter(cat => cat.name.toLowerCase().includes(searchTerm.toLowerCase()))
    .sort((a, b) => {
      let compare = 0;
      if (sortBy === 'name') {
        compare = a.name.localeCompare(b.name);
      } else if (sortBy === 'products') {
        compare = b.total_count - a.total_count;
      } else if (sortBy === 'order') {
        compare = a.display_order - b.display_order;
      }
      return sortDir === 'asc' ? compare : -compare;
    });

  // Add category
  const handleAddCategory = async () => {
    if (!newCategoryName.trim()) {
      toast.error('Please enter a category name');
      return;
    }
    
    setActionLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/supplier-sync/categories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newCategoryName.trim() })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        toast.success(`Category "${newCategoryName}" created`);
        setShowAddModal(false);
        setNewCategoryName('');
        fetchCategories();
      } else {
        toast.error(data.detail || 'Failed to create category');
      }
    } catch (error) {
      toast.error('Failed to create category');
    } finally {
      setActionLoading(false);
    }
  };

  // Edit category
  const handleEditCategory = async () => {
    if (!editForm.name.trim()) {
      toast.error('Category name cannot be empty');
      return;
    }
    
    setActionLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/supplier-sync/categories/${encodeURIComponent(editingCategory.name)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm)
      });
      
      const data = await response.json();
      
      if (response.ok) {
        const msg = data.products_updated > 0 || data.supplier_products_updated > 0
          ? `Category updated. ${data.supplier_products_updated + data.products_updated} products updated.`
          : 'Category updated';
        toast.success(msg);
        setShowEditModal(false);
        setEditingCategory(null);
        fetchCategories();
      } else {
        toast.error(data.detail || 'Failed to update category');
      }
    } catch (error) {
      toast.error('Failed to update category');
    } finally {
      setActionLoading(false);
    }
  };

  // Delete category
  const handleDeleteCategory = async () => {
    setActionLoading(true);
    try {
      const url = new URL(`${API_URL}/api/supplier-sync/categories/${encodeURIComponent(deletingCategory.name)}`);
      if (replacementCategory) {
        url.searchParams.set('replacement', replacementCategory);
      }
      
      const response = await fetch(url, { method: 'DELETE' });
      const data = await response.json();
      
      if (response.ok) {
        const affected = data.supplier_products_affected + data.products_affected;
        toast.success(`Category deleted. ${affected} products ${data.action}.`);
        setShowDeleteModal(false);
        setDeletingCategory(null);
        setReplacementCategory('');
        fetchCategories();
      } else {
        toast.error(data.detail || 'Failed to delete category');
      }
    } catch (error) {
      toast.error('Failed to delete category');
    } finally {
      setActionLoading(false);
    }
  };

  // Merge categories
  const handleMergeCategories = async () => {
    if (selectedForMerge.length < 2) {
      toast.error('Select at least 2 categories to merge');
      return;
    }
    if (!mergeTarget) {
      toast.error('Select a target category');
      return;
    }
    
    setActionLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/supplier-sync/categories/merge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sources: selectedForMerge.filter(c => c !== mergeTarget),
          target: mergeTarget
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        toast.success(data.message);
        setShowMergeModal(false);
        setSelectedForMerge([]);
        setMergeTarget('');
        fetchCategories();
      } else {
        toast.error(data.detail || 'Failed to merge categories');
      }
    } catch (error) {
      toast.error('Failed to merge categories');
    } finally {
      setActionLoading(false);
    }
  };

  // Open edit modal
  const openEditModal = (category) => {
    setEditingCategory(category);
    setEditForm({
      name: category.name,
      show_on_website: category.show_on_website !== false,
      display_order: category.display_order || 999
    });
    setShowEditModal(true);
  };

  // Open delete modal
  const openDeleteModal = (category) => {
    setDeletingCategory(category);
    setReplacementCategory('');
    setShowDeleteModal(true);
  };

  // Toggle sort
  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDir('asc');
    }
  };

  // Toggle selection for merge
  const toggleMergeSelection = (categoryName) => {
    setSelectedForMerge(prev => 
      prev.includes(categoryName)
        ? prev.filter(c => c !== categoryName)
        : [...prev, categoryName]
    );
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FolderTree className="w-7 h-7 text-amber-600" />
            Manage Categories
          </h1>
          <p className="text-muted-foreground mt-1">
            Create, edit, and organize product categories
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={fetchCategories}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          {selectedForMerge.length >= 2 && (
            <Button
              variant="outline"
              onClick={() => setShowMergeModal(true)}
              className="text-purple-600 border-purple-300 hover:bg-purple-50"
            >
              <Merge className="w-4 h-4 mr-2" />
              Merge ({selectedForMerge.length})
            </Button>
          )}
          <Button
            onClick={() => setShowAddModal(true)}
            className="bg-amber-600 hover:bg-amber-700"
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Category
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="text-sm text-muted-foreground">Total Categories</div>
            <div className="text-2xl font-bold text-amber-600">{categories.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-sm text-muted-foreground">With Products</div>
            <div className="text-2xl font-bold text-green-600">
              {categories.filter(c => c.total_count > 0).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-sm text-muted-foreground">Empty Categories</div>
            <div className="text-2xl font-bold text-gray-400">
              {categories.filter(c => c.total_count === 0).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-sm text-muted-foreground">Hidden from Website</div>
            <div className="text-2xl font-bold text-red-500">
              {categories.filter(c => c.show_on_website === false).length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tier Pricing Settings */}
      <Card className="border-amber-200 bg-amber-50/30">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-amber-600" />
              Quantity Tier Pricing
            </CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowTierSettings(!showTierSettings)}
              className="border-amber-300 text-amber-700 hover:bg-amber-100"
            >
              <Settings className="w-4 h-4 mr-2" />
              {showTierSettings ? 'Hide Settings' : 'Configure'}
            </Button>
          </div>
        </CardHeader>
        
        {showTierSettings ? (
          <CardContent className="space-y-6">
            {/* Tier Thresholds */}
            <div>
              <h4 className="font-medium text-sm text-gray-700 mb-3">Quantity Thresholds (m²)</h4>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-gray-500">Tier 2 starts at</label>
                  <Input
                    type="number"
                    value={tierConfig.thresholds[0]}
                    onChange={(e) => setTierConfig(prev => ({
                      ...prev,
                      thresholds: [parseInt(e.target.value) || 0, prev.thresholds[1], prev.thresholds[2]]
                    }))}
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500">Tier 3 starts at</label>
                  <Input
                    type="number"
                    value={tierConfig.thresholds[1]}
                    onChange={(e) => setTierConfig(prev => ({
                      ...prev,
                      thresholds: [prev.thresholds[0], parseInt(e.target.value) || 0, prev.thresholds[2]]
                    }))}
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500">Tier 4 starts at</label>
                  <Input
                    type="number"
                    value={tierConfig.thresholds[2]}
                    onChange={(e) => setTierConfig(prev => ({
                      ...prev,
                      thresholds: [prev.thresholds[0], prev.thresholds[1], parseInt(e.target.value) || 0]
                    }))}
                    className="mt-1"
                  />
                </div>
              </div>
            </div>

            {/* Tier Discounts */}
            <div>
              <h4 className="font-medium text-sm text-gray-700 mb-3">Tier Discounts (%)</h4>
              <div className="grid grid-cols-4 gap-3">
                <div>
                  <label className="text-xs text-gray-500">Tier 1 (0-{tierConfig.thresholds[0]}m²)</label>
                  <div className="relative mt-1">
                    <Input
                      type="number"
                      value={tierConfig.discounts[0]}
                      onChange={(e) => setTierConfig(prev => ({
                        ...prev,
                        discounts: [parseInt(e.target.value) || 0, prev.discounts[1], prev.discounts[2], prev.discounts[3]]
                      }))}
                      className="pr-8"
                    />
                    <Percent className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  </div>
                </div>
                <div>
                  <label className="text-xs text-gray-500">Tier 2 ({tierConfig.thresholds[0]}-{tierConfig.thresholds[1]}m²)</label>
                  <div className="relative mt-1">
                    <Input
                      type="number"
                      value={tierConfig.discounts[1]}
                      onChange={(e) => setTierConfig(prev => ({
                        ...prev,
                        discounts: [prev.discounts[0], parseInt(e.target.value) || 0, prev.discounts[2], prev.discounts[3]]
                      }))}
                      className="pr-8"
                    />
                    <Percent className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  </div>
                </div>
                <div>
                  <label className="text-xs text-gray-500">Tier 3 ({tierConfig.thresholds[1]}-{tierConfig.thresholds[2]}m²)</label>
                  <div className="relative mt-1">
                    <Input
                      type="number"
                      value={tierConfig.discounts[2]}
                      onChange={(e) => setTierConfig(prev => ({
                        ...prev,
                        discounts: [prev.discounts[0], prev.discounts[1], parseInt(e.target.value) || 0, prev.discounts[3]]
                      }))}
                      className="pr-8"
                    />
                    <Percent className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  </div>
                </div>
                <div>
                  <label className="text-xs text-gray-500">Tier 4 ({tierConfig.thresholds[2]}m²+)</label>
                  <div className="relative mt-1">
                    <Input
                      type="number"
                      value={tierConfig.discounts[3]}
                      onChange={(e) => setTierConfig(prev => ({
                        ...prev,
                        discounts: [prev.discounts[0], prev.discounts[1], prev.discounts[2], parseInt(e.target.value) || 0]
                      }))}
                      className="pr-8"
                    />
                    <Percent className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  </div>
                </div>
              </div>
            </div>

            {/* Trade & Quote Settings */}
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="text-xs text-gray-500">Custom Quote Threshold (m²)</label>
                <Input
                  type="number"
                  value={tierConfig.custom_quote_threshold}
                  onChange={(e) => setTierConfig(prev => ({
                    ...prev,
                    custom_quote_threshold: parseInt(e.target.value) || 0
                  }))}
                  className="mt-1"
                />
                <p className="text-xs text-gray-400 mt-1">Show "Request Quote" above this quantity</p>
              </div>
              <div>
                <label className="text-xs text-gray-500">Default Trade Discount (%)</label>
                <div className="relative mt-1">
                  <Input
                    type="number"
                    value={tierConfig.trade_discount_default}
                    onChange={(e) => setTierConfig(prev => ({
                      ...prev,
                      trade_discount_default: parseInt(e.target.value) || 0
                    }))}
                    className="pr-8"
                  />
                  <Percent className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                </div>
                <p className="text-xs text-gray-400 mt-1">Extra % off for trade accounts</p>
              </div>
              <div>
                <label className="text-xs text-gray-500">Credit Back Rate (%)</label>
                <div className="relative mt-1">
                  <Input
                    type="number"
                    value={tierConfig.credit_back_default}
                    onChange={(e) => setTierConfig(prev => ({
                      ...prev,
                      credit_back_default: parseInt(e.target.value) || 0
                    }))}
                    className="pr-8"
                  />
                  <Percent className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                </div>
                <p className="text-xs text-gray-400 mt-1">% credited back on trade orders</p>
              </div>
            </div>

            {/* Preview */}
            <div className="bg-white p-4 rounded-lg border">
              <h4 className="font-medium text-sm text-gray-700 mb-3">Preview (Base Price: £50/m²)</h4>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 border-b">
                    <th className="text-left py-2">Tier</th>
                    <th className="text-left py-2">Quantity</th>
                    <th className="text-right py-2">Discount</th>
                    <th className="text-right py-2">Price/m²</th>
                    <th className="text-right py-2">Trade Price</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b">
                    <td className="py-2">Tier 1</td>
                    <td>0 - {tierConfig.thresholds[0]}m²</td>
                    <td className="text-right">{tierConfig.discounts[0]}%</td>
                    <td className="text-right font-medium">£{(50 * (1 - tierConfig.discounts[0]/100)).toFixed(2)}</td>
                    <td className="text-right text-green-600">£{(50 * (1 - tierConfig.discounts[0]/100) * (1 - tierConfig.trade_discount_default/100)).toFixed(2)}</td>
                  </tr>
                  <tr className="border-b">
                    <td className="py-2">Tier 2</td>
                    <td>{tierConfig.thresholds[0]} - {tierConfig.thresholds[1]}m²</td>
                    <td className="text-right">{tierConfig.discounts[1]}%</td>
                    <td className="text-right font-medium">£{(50 * (1 - tierConfig.discounts[1]/100)).toFixed(2)}</td>
                    <td className="text-right text-green-600">£{(50 * (1 - tierConfig.discounts[1]/100) * (1 - tierConfig.trade_discount_default/100)).toFixed(2)}</td>
                  </tr>
                  <tr className="border-b">
                    <td className="py-2">Tier 3</td>
                    <td>{tierConfig.thresholds[1]} - {tierConfig.thresholds[2]}m²</td>
                    <td className="text-right">{tierConfig.discounts[2]}%</td>
                    <td className="text-right font-medium">£{(50 * (1 - tierConfig.discounts[2]/100)).toFixed(2)}</td>
                    <td className="text-right text-green-600">£{(50 * (1 - tierConfig.discounts[2]/100) * (1 - tierConfig.trade_discount_default/100)).toFixed(2)}</td>
                  </tr>
                  <tr>
                    <td className="py-2">Tier 4</td>
                    <td>{tierConfig.thresholds[2]}m²+</td>
                    <td className="text-right">{tierConfig.discounts[3]}%</td>
                    <td className="text-right font-medium">£{(50 * (1 - tierConfig.discounts[3]/100)).toFixed(2)}</td>
                    <td className="text-right text-green-600">£{(50 * (1 - tierConfig.discounts[3]/100) * (1 - tierConfig.trade_discount_default/100)).toFixed(2)}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Save Button */}
            <div className="flex justify-end">
              <Button
                onClick={saveTierConfig}
                disabled={tierLoading}
                className="bg-amber-600 hover:bg-amber-700"
              >
                {tierLoading ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                Save Tier Settings
              </Button>
            </div>
          </CardContent>
        ) : (
          <CardContent>
            <div className="flex items-center justify-between text-sm">
              <div className="flex gap-6">
                <div>
                  <span className="text-gray-500">Thresholds:</span>
                  <span className="ml-2 font-medium">{tierConfig.thresholds.join(' / ')} m²</span>
                </div>
                <div>
                  <span className="text-gray-500">Discounts:</span>
                  <span className="ml-2 font-medium">{tierConfig.discounts.join('% / ')}%</span>
                </div>
                <div>
                  <span className="text-gray-500">Trade:</span>
                  <span className="ml-2 font-medium text-green-600">+{tierConfig.trade_discount_default}% off</span>
                </div>
              </div>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Search and Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search categories..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Sort by:</span>
              <Button
                variant={sortBy === 'name' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => toggleSort('name')}
              >
                Name {sortBy === 'name' && (sortDir === 'asc' ? <ChevronUp className="w-3 h-3 ml-1" /> : <ChevronDown className="w-3 h-3 ml-1" />)}
              </Button>
              <Button
                variant={sortBy === 'products' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => toggleSort('products')}
              >
                Products {sortBy === 'products' && (sortDir === 'asc' ? <ChevronUp className="w-3 h-3 ml-1" /> : <ChevronDown className="w-3 h-3 ml-1" />)}
              </Button>
              <Button
                variant={sortBy === 'order' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => toggleSort('order')}
              >
                Order {sortBy === 'order' && (sortDir === 'asc' ? <ChevronUp className="w-3 h-3 ml-1" /> : <ChevronDown className="w-3 h-3 ml-1" />)}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Categories Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 animate-spin text-amber-600" />
            </div>
          ) : filteredCategories.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              {searchTerm ? 'No categories match your search' : 'No categories found'}
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="w-12 px-4 py-3 text-left">
                    <input
                      type="checkbox"
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedForMerge(filteredCategories.map(c => c.name));
                        } else {
                          setSelectedForMerge([]);
                        }
                      }}
                      checked={selectedForMerge.length === filteredCategories.length && filteredCategories.length > 0}
                      className="w-4 h-4 rounded"
                    />
                  </th>
                  <th className="px-4 py-3 text-left font-medium">Category Name</th>
                  <th className="px-4 py-3 text-center font-medium">Supplier Products</th>
                  <th className="px-4 py-3 text-center font-medium">Main Products</th>
                  <th className="px-4 py-3 text-center font-medium">Website</th>
                  <th className="px-4 py-3 text-center font-medium">Order</th>
                  <th className="px-4 py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filteredCategories.map((category) => (
                  <tr 
                    key={category.name} 
                    className={`hover:bg-muted/30 ${selectedForMerge.includes(category.name) ? 'bg-purple-50' : ''}`}
                  >
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedForMerge.includes(category.name)}
                        onChange={() => toggleMergeSelection(category.name)}
                        className="w-4 h-4 rounded"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <FolderTree className="w-4 h-4 text-amber-500" />
                        <span className="font-medium">{category.name}</span>
                        {category.source === 'manual' && (
                          <span className="text-xs px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded">Manual</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-1 rounded ${category.supplier_products_count > 0 ? 'bg-green-100 text-green-700' : 'text-gray-400'}`}>
                        {category.supplier_products_count}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-1 rounded ${category.products_count > 0 ? 'bg-blue-100 text-blue-700' : 'text-gray-400'}`}>
                        {category.products_count}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {category.show_on_website !== false ? (
                        <Eye className="w-4 h-4 text-green-600 mx-auto" />
                      ) : (
                        <EyeOff className="w-4 h-4 text-gray-400 mx-auto" />
                      )}
                    </td>
                    <td className="px-4 py-3 text-center text-muted-foreground">
                      {category.display_order || '-'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditModal(category)}
                          title="Edit"
                        >
                          <Edit2 className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openDeleteModal(category)}
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {/* Add Category Modal */}
      <Dialog open={showAddModal} onOpenChange={setShowAddModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="w-5 h-5 text-amber-600" />
              Add New Category
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="block text-sm font-medium mb-1">Category Name</label>
              <Input
                value={newCategoryName}
                onChange={(e) => setNewCategoryName(e.target.value)}
                placeholder="e.g., Wall Tiles"
                autoFocus
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddModal(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleAddCategory}
              disabled={actionLoading}
              className="bg-amber-600 hover:bg-amber-700"
            >
              {actionLoading ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
              Add Category
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Category Modal */}
      <Dialog open={showEditModal} onOpenChange={setShowEditModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Edit2 className="w-5 h-5 text-amber-600" />
              Edit Category
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="block text-sm font-medium mb-1">Category Name</label>
              <Input
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              />
              {editingCategory && editForm.name !== editingCategory.name && (
                <p className="text-sm text-amber-600 mt-1">
                  Renaming will update {editingCategory.total_count} products
                </p>
              )}
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={editForm.show_on_website}
                  onChange={(e) => setEditForm({ ...editForm, show_on_website: e.target.checked })}
                  className="w-4 h-4 rounded"
                />
                <span className="text-sm">Show on Website</span>
              </label>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Display Order</label>
              <Input
                type="number"
                value={editForm.display_order}
                onChange={(e) => setEditForm({ ...editForm, display_order: parseInt(e.target.value) || 999 })}
                min={1}
              />
              <p className="text-xs text-muted-foreground mt-1">Lower numbers appear first</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditModal(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleEditCategory}
              disabled={actionLoading}
              className="bg-amber-600 hover:bg-amber-700"
            >
              {actionLoading ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Category Modal */}
      <Dialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <Trash2 className="w-5 h-5" />
              Delete Category
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <p>
              Are you sure you want to delete <strong>"{deletingCategory?.name}"</strong>?
            </p>
            {deletingCategory?.total_count > 0 && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <p className="text-sm text-amber-800">
                  <strong>{deletingCategory.total_count} products</strong> use this category.
                  Choose what to do with them:
                </p>
                <div className="mt-3 space-y-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="deleteAction"
                      checked={!replacementCategory}
                      onChange={() => setReplacementCategory('')}
                      className="w-4 h-4"
                    />
                    <span className="text-sm">Clear category from products</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="deleteAction"
                      checked={!!replacementCategory}
                      onChange={() => setReplacementCategory(categories[0]?.name || '')}
                      className="w-4 h-4"
                    />
                    <span className="text-sm">Replace with another category:</span>
                  </label>
                  {replacementCategory !== '' && (
                    <select
                      value={replacementCategory}
                      onChange={(e) => setReplacementCategory(e.target.value)}
                      className="ml-6 mt-1 px-3 py-2 border rounded-md text-sm w-full"
                    >
                      {categories
                        .filter(c => c.name !== deletingCategory?.name)
                        .map(c => (
                          <option key={c.name} value={c.name}>{c.name}</option>
                        ))
                      }
                    </select>
                  )}
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteModal(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleDeleteCategory}
              disabled={actionLoading}
              variant="destructive"
            >
              {actionLoading ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Trash2 className="w-4 h-4 mr-2" />}
              Delete Category
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Merge Categories Modal */}
      <Dialog open={showMergeModal} onOpenChange={setShowMergeModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-purple-600">
              <Merge className="w-5 h-5" />
              Merge Categories
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <p className="text-sm text-muted-foreground">
              Merge {selectedForMerge.length} categories into one. Select which category to keep:
            </p>
            <div className="space-y-2 max-h-60 overflow-auto">
              {selectedForMerge.map(catName => {
                const cat = categories.find(c => c.name === catName);
                return (
                  <label 
                    key={catName}
                    className={`flex items-center justify-between p-3 border rounded-lg cursor-pointer hover:bg-purple-50 ${mergeTarget === catName ? 'border-purple-500 bg-purple-50' : ''}`}
                  >
                    <div className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="mergeTarget"
                        checked={mergeTarget === catName}
                        onChange={() => setMergeTarget(catName)}
                        className="w-4 h-4 text-purple-600"
                      />
                      <span className="font-medium">{catName}</span>
                    </div>
                    <span className="text-sm text-muted-foreground">
                      {cat?.total_count || 0} products
                    </span>
                  </label>
                );
              })}
            </div>
            {mergeTarget && (
              <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg text-sm">
                <strong>Result:</strong> All products from {selectedForMerge.filter(c => c !== mergeTarget).length} categories 
                will be moved to "{mergeTarget}"
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowMergeModal(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleMergeCategories}
              disabled={actionLoading || !mergeTarget}
              className="bg-purple-600 hover:bg-purple-700"
            >
              {actionLoading ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Merge className="w-4 h-4 mr-2" />}
              Merge Categories
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
