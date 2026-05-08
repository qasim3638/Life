import React, { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { 
  Settings2, X, Plus, Edit2, Trash2, Loader2, Layers, FolderOpen, 
  RefreshCw, Link2, ExternalLink, Filter, Tag, Sliders, Check,
  Grid3X3, ChevronDown, ChevronRight, Lock, Eye, CheckSquare, Square
} from 'lucide-react';
import { Button } from '../../../../components/ui/button';
import { Input } from '../../../../components/ui/input';
import { Badge } from '../../../../components/ui/badge';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ManageOptionsModal = ({
  isOpen,
  onClose,
  refreshOptions,
  categoryGroups = [],
  selectedProductGroup = 'tiles',
  setSelectedProductGroup = () => {},
  userRole = 'staff' // Pass user role to control permissions
}) => {
  // Check if user is admin (super_admin or admin can edit, others are read-only)
  const isAdmin = ['super_admin', 'admin', 'SUPER_ADMIN', 'ADMIN'].includes(userRole);
  
  // Main tab: Categories, Filters, Specifications (matching Navigation & Structure)
  const [activeTab, setActiveTab] = useState('categories');
  const [loading, setLoading] = useState(false);
  
  // Data from Navigation & Structure APIs
  const [categories, setCategories] = useState([]);
  const [categoriesByGroup, setCategoriesByGroup] = useState({});
  const [filters, setFilters] = useState([]);
  const [specifications, setSpecifications] = useState([]);
  const [specGroups, setSpecGroups] = useState([]);
  
  // Edit state
  const [editingItem, setEditingItem] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [newItemName, setNewItemName] = useState('');
  const [newFilterName, setNewFilterName] = useState('');
  const [expandedGroups, setExpandedGroups] = useState({});
  
  // Bulk scope state
  const [bulkSelectMode, setBulkSelectMode] = useState(false);
  const [selectedSpecIds, setSelectedSpecIds] = useState(new Set());
  const [selectedFilterIds, setSelectedFilterIds] = useState(new Set());
  const [bulkTargetGroup, setBulkTargetGroup] = useState('');
  const [bulkAssigning, setBulkAssigning] = useState(false);

  // Fetch all data from Navigation & Structure APIs
  const fetchAllData = useCallback(async () => {
    if (!isOpen) return;
    
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const headers = { Authorization: `Bearer ${token}` };
      
      const [catsRes, catsByGroupRes, filtersRes, specsRes, specGroupsRes] = await Promise.all([
        fetch(`${API_URL}/api/website-admin/categories`, { headers }),
        fetch(`${API_URL}/api/website-admin/categories/by-group`, { headers }),
        fetch(`${API_URL}/api/filters/types`),
        fetch(`${API_URL}/api/specifications/types/by-group`),
        fetch(`${API_URL}/api/specifications/groups`)
      ]);
      
      if (catsRes.ok) setCategories(await catsRes.json());
      
      // Handle categories by group - returns list of groups with categories inside
      if (catsByGroupRes.ok) {
        const groupsWithCats = await catsByGroupRes.json();
        // Convert to dictionary format: { groupSlug: [categories] }
        const grouped = {};
        for (const group of groupsWithCats) {
          if (group.slug && group.categories) {
            grouped[group.slug] = group.categories;
          }
        }
        setCategoriesByGroup(grouped);
      }
      
      if (filtersRes.ok) setFilters(await filtersRes.json());
      
      // Handle specifications - returns list of spec groups with specs nested inside
      if (specsRes.ok) {
        const specsByGroup = await specsRes.json();
        // Convert to dictionary: { groupName: [specs] }
        const grouped = {};
        if (Array.isArray(specsByGroup)) {
          for (const group of specsByGroup) {
            const groupName = group.name || 'Other';
            const specs = group.specifications || [];
            if (specs.length > 0) {
              grouped[groupName] = specs;
            } else {
              // Group exists but no specs inside it yet
              grouped[groupName] = [];
            }
          }
        }
        setSpecifications(grouped);
      }
      
      if (specGroupsRes.ok) setSpecGroups(await specGroupsRes.json());
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [isOpen]);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  // Filter data by selected product group
  const getFilteredCategories = () => {
    if (selectedProductGroup === 'all') return categoriesByGroup;
    return { [selectedProductGroup]: categoriesByGroup[selectedProductGroup] || [] };
  };

  const getFilteredFilters = () => {
    if (selectedProductGroup === 'all') return filters;
    return filters.filter(f => {
      // Hide filters explicitly hidden from this group
      const hiddenGroups = f.hidden_groups || [];
      if (hiddenGroups.includes(selectedProductGroup)) return false;
      // Show if no group restrictions or if group matches
      return !f.auto_populate_groups?.length || 
        f.auto_populate_groups.includes(selectedProductGroup);
    });
  };

  const getFilteredSpecifications = () => {
    if (selectedProductGroup === 'all') return specifications;
    const result = {};
    Object.entries(specifications).forEach(([groupName, specs]) => {
      const filteredSpecs = specs.filter(s => {
        // Check hidden_groups
        const hiddenGroups = s.hidden_groups || [];
        if (hiddenGroups.includes(selectedProductGroup)) return false;
        // Strict product_groups scoping on the TYPE level
        const productGroups = s.product_groups || [];
        if (productGroups.length > 0 && !productGroups.includes(selectedProductGroup)) return false;
        return true;
      });
      if (filteredSpecs.length > 0) {
        result[groupName] = filteredSpecs;
      }
    });
    return result;
  };

  // CRUD handlers for Categories
  const handleAddCategory = async () => {
    if (!newItemName.trim()) return;
    
    try {
      const token = localStorage.getItem('token');
      const slug = newItemName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      
      const res = await fetch(`${API_URL}/api/website-admin/categories`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          name: newItemName.trim(),
          slug: slug,
          group_slug: selectedProductGroup !== 'all' ? selectedProductGroup : 'tiles',
          is_active: true,
          show_on_homepage: false
        })
      });
      
      if (res.ok) {
        toast.success(`Category "${newItemName}" created`);
        setNewItemName('');
        fetchAllData();
        if (refreshOptions) refreshOptions();
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Failed to create category');
      }
    } catch (error) {
      toast.error('Failed to create category');
    }
  };

  const handleDeleteCategory = async (categoryId, categoryName) => {
    if (!window.confirm(`Delete category "${categoryName}"?`)) return;
    
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/categories/${categoryId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.ok) {
        toast.success(`Category "${categoryName}" deleted`);
        fetchAllData();
        if (refreshOptions) refreshOptions();
      } else {
        toast.error('Failed to delete category');
      }
    } catch (error) {
      toast.error('Failed to delete category');
    }
  };

  // Toggle a product group on a filter TYPE
  const handleToggleFilterTypeGroup = async (filterId, group, currentGroups) => {
    const action = currentGroups.includes(group) ? 'remove' : 'add';
    try {
      const res = await fetch(`${API_URL}/api/filters/types/${filterId}/toggle-group`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_group: group, action })
      });
      if (res.ok) {
        toast.success(`Filter ${action === 'add' ? 'added to' : 'removed from'} ${group}`);
        fetchAllData();
        if (refreshOptions) refreshOptions();
      } else {
        toast.error('Failed to update filter group');
      }
    } catch (error) {
      toast.error('Failed to update filter group');
    }
  };

  // CRUD handlers for Filters
  const handleAddFilter = async () => {
    if (!newFilterName.trim()) return;
    
    try {
      const slug = newFilterName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      
      const res = await fetch(`${API_URL}/api/filters/types`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newFilterName.trim(),
          slug: slug,
          input_type: 'checkbox',
          is_active: true,
          show_in_shop_filter: true,
          show_in_bulk_editor: true,
          auto_populate_groups: selectedProductGroup !== 'all' ? [selectedProductGroup] : []
        })
      });
      
      if (res.ok) {
        toast.success(`Filter "${newFilterName}" created`);
        setNewFilterName('');
        fetchAllData();
        if (refreshOptions) refreshOptions();
      } else {
        let errorMsg = 'Failed to create filter';
        try {
          const error = await res.json();
          errorMsg = error.detail || errorMsg;
        } catch (e) {
          errorMsg = `Failed to create filter (${res.status})`;
        }
        toast.error(errorMsg);
      }
    } catch (error) {
      toast.error('Failed to create filter: ' + (error.message || 'Unknown error'));
    }
  };

  const handleAddFilterValue = async (filterSlug, value) => {
    if (!value.trim()) return;
    
    try {
      const valueSlug = value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      
      const body = {
        value: valueSlug,
        label: value.trim(),
        is_active: true
      };
      // Auto-scope value to current product group
      if (selectedProductGroup && selectedProductGroup !== 'all') {
        body.product_groups = [selectedProductGroup];
      }
      
      const res = await fetch(`${API_URL}/api/filters/types/${filterSlug}/add-value`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      
      if (res.ok) {
        toast.success(`Added "${value}" to filter`);
        fetchAllData();
        if (refreshOptions) refreshOptions();
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Failed to add value');
      }
    } catch (error) {
      toast.error('Failed to add value');
    }
  };

  const handleDeleteFilterValue = async (filterSlug, valueSlug, valueLabel, filterId) => {
    // If viewing a specific product group, hide from that group only (not global delete)
    if (selectedProductGroup && selectedProductGroup !== 'all') {
      if (!window.confirm(`Remove "${valueLabel}" from ${selectedProductGroup}? (It will remain available in other groups)`)) return;
      
      try {
        const res = await fetch(`${API_URL}/api/filters/types/${filterId}/values/${valueSlug}/toggle-group`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ product_group: selectedProductGroup, action: 'remove' })
        });
        
        if (res.ok) {
          toast.success(`"${valueLabel}" hidden from ${selectedProductGroup}`);
          fetchAllData();
          if (refreshOptions) refreshOptions();
        } else {
          let errorMsg = 'Failed to remove value from group';
          try { const error = await res.json(); errorMsg = error.detail || errorMsg; } catch(e) {}
          toast.error(errorMsg);
        }
      } catch (error) {
        toast.error('Failed to remove value');
      }
    } else {
      // Global delete when viewing "All"
      if (!window.confirm(`Delete "${valueLabel}" from ALL groups? This cannot be undone.`)) return;
      
      try {
        const res = await fetch(`${API_URL}/api/filters/types/by-slug/${filterSlug}/values/${valueSlug}`, {
          method: 'DELETE'
        });
        
        if (res.ok) {
          toast.success(`Deleted "${valueLabel}" from all groups`);
          fetchAllData();
          if (refreshOptions) refreshOptions();
        } else {
          toast.error('Failed to delete value');
        }
      } catch (error) {
        toast.error('Failed to delete value');
      }
    }
  };

  // CRUD handlers for Specification Values
  const handleAddSpecValue = async (specId, value) => {
    if (!value.trim()) return;
    
    try {
      const valueSlug = value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      
      const body = {
        value: valueSlug,
        label: value.trim(),
        is_active: true
      };
      // Auto-scope value to current product group
      if (selectedProductGroup && selectedProductGroup !== 'all') {
        body.product_groups = [selectedProductGroup];
      }
      
      const res = await fetch(`${API_URL}/api/specifications/types/${specId}/values`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      
      if (res.ok) {
        toast.success(`Added "${value}" to specification`);
        fetchAllData();
        if (refreshOptions) refreshOptions();
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Failed to add value');
      }
    } catch (error) {
      toast.error('Failed to add value');
    }
  };

  // Toggle a product group on a spec TYPE
  const handleToggleSpecTypeGroup = async (specId, group, currentGroups) => {
    const action = currentGroups.includes(group) ? 'remove' : 'add';
    try {
      const res = await fetch(`${API_URL}/api/specifications/types/${specId}/toggle-group`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_group: group, action })
      });
      if (res.ok) {
        toast.success(`Spec ${action === 'add' ? 'added to' : 'removed from'} ${group}`);
        fetchAllData();
        if (refreshOptions) refreshOptions();
      } else {
        toast.error('Failed to update spec group');
      }
    } catch (error) {
      toast.error('Failed to update spec group');
    }
  };

  // Bulk scope helpers
  const toggleSpecSelect = (specId) => {
    setSelectedSpecIds(prev => {
      const next = new Set(prev);
      next.has(specId) ? next.delete(specId) : next.add(specId);
      return next;
    });
  };
  const toggleFilterSelect = (filterId) => {
    setSelectedFilterIds(prev => {
      const next = new Set(prev);
      next.has(filterId) ? next.delete(filterId) : next.add(filterId);
      return next;
    });
  };
  const selectAllSpecs = () => {
    const allIds = Object.values(specifications).flat().map(s => s.id || s._id);
    setSelectedSpecIds(new Set(allIds));
  };
  const selectAllFilters = () => {
    setSelectedFilterIds(new Set(filters.map(f => f.id)));
  };
  const clearBulkSelection = () => {
    setSelectedSpecIds(new Set());
    setSelectedFilterIds(new Set());
    setBulkTargetGroup('');
  };
  const exitBulkMode = () => {
    setBulkSelectMode(false);
    clearBulkSelection();
  };

  const handleBulkAssign = async (action = 'add') => {
    if (!bulkTargetGroup) {
      toast.error('Select a target group first');
      return;
    }
    const totalSelected = selectedSpecIds.size + selectedFilterIds.size;
    if (totalSelected === 0) {
      toast.error('Select at least one spec or filter');
      return;
    }

    setBulkAssigning(true);
    let specUpdated = 0, filterUpdated = 0;

    try {
      if (selectedSpecIds.size > 0) {
        const res = await fetch(`${API_URL}/api/specifications/types/bulk-assign-group`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type_ids: [...selectedSpecIds],
            product_group: bulkTargetGroup,
            action
          })
        });
        if (res.ok) {
          const d = await res.json();
          specUpdated = d.updated || 0;
        }
      }

      if (selectedFilterIds.size > 0) {
        const res = await fetch(`${API_URL}/api/filters/types/bulk-assign-group`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type_ids: [...selectedFilterIds],
            product_group: bulkTargetGroup,
            action
          })
        });
        if (res.ok) {
          const d = await res.json();
          filterUpdated = d.updated || 0;
        }
      }

      const verb = action === 'add' ? 'assigned to' : 'removed from';
      const groupLabel = categoryGroups.find(g => g.slug === bulkTargetGroup)?.name || bulkTargetGroup;
      toast.success(`${specUpdated + filterUpdated} items ${verb} ${groupLabel}`);
      clearBulkSelection();
      fetchAllData();
      if (refreshOptions) refreshOptions();
    } catch (error) {
      toast.error('Bulk assign failed');
    } finally {
      setBulkAssigning(false);
    }
  };

  const handleDeleteSpecValue = async (specId, valueSlug, valueLabel) => {
    // If viewing a specific product group, hide from that group only
    if (selectedProductGroup && selectedProductGroup !== 'all') {
      if (!window.confirm(`Remove "${valueLabel}" from ${selectedProductGroup}? (It will remain in other groups)`)) return;
      
      try {
        const res = await fetch(`${API_URL}/api/specifications/types/${specId}/values/${valueSlug}/toggle-group`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ product_group: selectedProductGroup, action: 'remove' })
        });
        
        if (res.ok) {
          toast.success(`"${valueLabel}" hidden from ${selectedProductGroup}`);
          fetchAllData();
          if (refreshOptions) refreshOptions();
        } else {
          let errorMsg = 'Failed to remove value from group';
          try { const error = await res.json(); errorMsg = error.detail || errorMsg; } catch(e) {}
          toast.error(errorMsg);
        }
      } catch (error) {
        toast.error('Failed to remove value');
      }
    } else {
      // Global delete when viewing "All"
      if (!window.confirm(`Delete "${valueLabel}" from ALL groups? This cannot be undone.`)) return;
      
      try {
        const res = await fetch(`${API_URL}/api/specifications/types/${specId}/values/${valueSlug}`, {
          method: 'DELETE'
        });
        
        if (res.ok) {
          toast.success(`Deleted "${valueLabel}" from all groups`);
          fetchAllData();
          if (refreshOptions) refreshOptions();
        } else {
          toast.error('Failed to delete value');
        }
      } catch (error) {
        toast.error('Failed to delete value');
      }
    }
  };

  // Toggle group expansion
  const toggleGroup = (groupKey) => {
    setExpandedGroups(prev => ({
      ...prev,
      [groupKey]: !prev[groupKey]
    }));
  };

  // Filter values by current product group (group isolation)
  const getVisibleValues = (values) => {
    if (!values) return [];
    if (!selectedProductGroup || selectedProductGroup === 'all') return values;
    
    return values.filter(val => {
      const groups = val.product_groups;
      // No product_groups = visible everywhere (backward compatible)
      if (!groups || groups.length === 0) return true;
      return groups.includes(selectedProductGroup);
    });
  };

  if (!isOpen) return null;

  const filteredCategories = getFilteredCategories();
  const filteredFilters = getFilteredFilters();
  const filteredSpecifications = getFilteredSpecifications();

  return createPortal(
    <div
      className="fixed inset-0 flex items-center justify-center p-4"
      style={{ pointerEvents: 'auto', zIndex: 9999 }}
      data-testid="options-manager-modal"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />

      {/* Modal Content */}
      <div
        className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col relative z-10"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-t-xl">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              {isAdmin ? <Settings2 className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              {isAdmin ? 'Manage Product Options' : 'View Product Options'}
            </h3>
            {isAdmin ? (
              <div className="flex items-center gap-1.5 px-2.5 py-1 bg-white/20 backdrop-blur-sm rounded-full text-xs font-medium">
                <RefreshCw className="w-3 h-3" />
                <span>Synced with Navigation & Structure</span>
                <Link2 className="w-3 h-3" />
              </div>
            ) : (
              <div className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-500/30 backdrop-blur-sm rounded-full text-xs font-medium">
                <Lock className="w-3 h-3" />
                <span>Read-Only Mode</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {isAdmin && selectedProductGroup === 'all' && (
              <button
                onClick={() => bulkSelectMode ? exitBulkMode() : setBulkSelectMode(true)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  bulkSelectMode
                    ? 'bg-white text-indigo-700 shadow-md'
                    : 'bg-white/20 text-white hover:bg-white/30'
                }`}
                data-testid="bulk-scope-toggle-btn"
              >
                <CheckSquare className="w-3.5 h-3.5" />
                {bulkSelectMode ? 'Exit Bulk Scope' : 'Bulk Scope'}
              </button>
            )}
            <button onClick={onClose} className="text-white/80 hover:text-white">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Read-only notice for non-admins */}
        {!isAdmin && (
          <div className="px-4 py-2 bg-amber-50 border-b border-amber-200 text-amber-800 text-sm flex items-center gap-2">
            <Lock className="w-4 h-4" />
            <span>View-only access. Contact an admin to make changes to product options.</span>
          </div>
        )}

        {/* Product Group Selector */}
        <div className="p-3 bg-gradient-to-r from-slate-50 to-gray-50 border-b">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <FolderOpen className="w-4 h-4 text-indigo-600" />
              <span className="text-sm font-medium text-gray-700">Working on:</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setSelectedProductGroup('all')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  selectedProductGroup === 'all'
                    ? 'bg-indigo-600 text-white shadow-md'
                    : 'bg-white text-gray-700 hover:bg-indigo-50 border border-gray-200'
                }`}
              >
                <Layers className="w-3.5 h-3.5 inline mr-1" />
                All Groups
              </button>
              {categoryGroups.map(group => (
                <button
                  key={group.slug}
                  onClick={() => setSelectedProductGroup(group.slug)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    selectedProductGroup === group.slug
                      ? 'bg-indigo-600 text-white shadow-md'
                      : 'bg-white text-gray-700 hover:bg-indigo-50 border border-gray-200'
                  }`}
                >
                  {group.name}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Main Tabs - Matching Navigation & Structure */}
        <div className="flex border-b bg-gray-50">
          <button
            onClick={() => setActiveTab('categories')}
            className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-all border-b-2 ${
              activeTab === 'categories'
                ? 'border-green-500 text-green-700 bg-white'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Tag className="w-4 h-4" />
            Categories
            <Badge variant="secondary" className="ml-1 text-xs">
              {Object.values(filteredCategories).flat().length}
            </Badge>
          </button>
          <button
            onClick={() => setActiveTab('filters')}
            className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-all border-b-2 ${
              activeTab === 'filters'
                ? 'border-blue-500 text-blue-700 bg-white'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Filter className="w-4 h-4" />
            Filters
            <Badge variant="secondary" className="ml-1 text-xs">
              {filteredFilters.length}
            </Badge>
          </button>
          <button
            onClick={() => setActiveTab('specifications')}
            className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-all border-b-2 ${
              activeTab === 'specifications'
                ? 'border-purple-500 text-purple-700 bg-white'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Sliders className="w-4 h-4" />
            Specifications
            <Badge variant="secondary" className="ml-1 text-xs">
              {Object.values(filteredSpecifications).flat().length}
            </Badge>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
              <span className="ml-2 text-gray-500">Loading...</span>
            </div>
          ) : (
            <>
              {/* Categories Tab */}
              {activeTab === 'categories' && (
                <div className="space-y-4">
                  {/* Add New Category - Only for admins */}
                  {isAdmin && (
                    <div className="flex gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                      <Input
                        value={newItemName}
                        onChange={(e) => setNewItemName(e.target.value)}
                        placeholder="Add new category..."
                        className="flex-1"
                        onKeyDown={(e) => e.key === 'Enter' && handleAddCategory()}
                      />
                      <Button onClick={handleAddCategory} disabled={!newItemName.trim()} className="bg-green-600 hover:bg-green-700">
                        <Plus className="w-4 h-4 mr-1" />
                        Add Category
                      </Button>
                    </div>
                  )}

                  {/* Categories List by Group */}
                  {Object.entries(filteredCategories).map(([groupSlug, groupCats]) => {
                    const group = categoryGroups.find(g => g.slug === groupSlug);
                    const isExpanded = expandedGroups[groupSlug] !== false;
                    
                    return (
                      <div key={groupSlug} className="border rounded-lg overflow-hidden">
                        <button
                          onClick={() => toggleGroup(groupSlug)}
                          className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 transition-colors"
                        >
                          <div className="flex items-center gap-2">
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                            <Grid3X3 className="w-4 h-4 text-green-600" />
                            <span className="font-medium">{group?.name || groupSlug}</span>
                            <Badge variant="secondary">{groupCats?.length || 0} categories</Badge>
                          </div>
                        </button>
                        
                        {isExpanded && (
                          <div className="divide-y">
                            {(groupCats || []).map(cat => (
                              <div key={cat.id || cat._id || cat.slug} className="flex items-center justify-between p-3 hover:bg-gray-50">
                                <div className="flex items-center gap-2">
                                  <span>{cat.name}</span>
                                  {cat.is_active && <Badge className="bg-green-100 text-green-700 text-xs">Active</Badge>}
                                  {cat.show_on_homepage && <Badge className="bg-blue-100 text-blue-700 text-xs">Homepage</Badge>}
                                </div>
                                {isAdmin && (
                                  <div className="flex items-center gap-1">
                                    <button
                                      onClick={() => handleDeleteCategory(cat.id || cat._id, cat.name)}
                                      className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                                    >
                                      <Trash2 className="w-4 h-4" />
                                    </button>
                                  </div>
                                )}
                              </div>
                            ))}
                            {(!groupCats || groupCats.length === 0) && (
                              <p className="p-3 text-sm text-gray-500 italic">No categories in this group</p>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Filters Tab */}
              {activeTab === 'filters' && (
                <div className="space-y-4">
                  {/* Add New Filter - Only for admins */}
                  {isAdmin && (
                    <div className="flex gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                      <Input
                        value={newFilterName}
                        onChange={(e) => setNewFilterName(e.target.value)}
                        placeholder="Add new filter (e.g. Thickness, Material)..."
                        className="flex-1"
                        onKeyDown={(e) => e.key === 'Enter' && handleAddFilter()}
                      />
                      <Button onClick={handleAddFilter} disabled={!newFilterName.trim()} className="bg-blue-600 hover:bg-blue-700">
                        <Plus className="w-4 h-4 mr-1" />
                        Add Filter
                      </Button>
                    </div>
                  )}

                  {filteredFilters.map(filter => {
                    const isExpanded = expandedGroups[`filter-${filter.slug}`] !== false;
                    
                    return (
                      <div key={filter.id || filter.slug} className="border rounded-lg overflow-hidden">
                        <div className="flex items-center bg-blue-50 hover:bg-blue-100 transition-colors">
                          {bulkSelectMode && (
                            <button
                              onClick={() => toggleFilterSelect(filter.id)}
                              className="flex-shrink-0 pl-3"
                              data-testid={`bulk-select-filter-${filter.slug}`}
                            >
                              {selectedFilterIds.has(filter.id)
                                ? <CheckSquare className="w-4 h-4 text-blue-600" />
                                : <Square className="w-4 h-4 text-gray-400" />}
                            </button>
                          )}
                          <button
                            onClick={() => toggleGroup(`filter-${filter.slug}`)}
                            className="w-full flex items-center justify-between p-3"
                          >
                            <div className="flex items-center gap-2">
                              {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                              <Filter className="w-4 h-4 text-blue-600" />
                              <span className="font-medium">{filter.name}</span>
                              <Badge variant="secondary">{getVisibleValues(filter.values).length} values</Badge>
                              {filter.is_active && <Badge className="bg-green-100 text-green-700 text-xs">Active</Badge>}
                            </div>
                          </button>
                        </div>
                        
                        {isExpanded && (
                          <div className="p-3 space-y-3">
                            {/* Group scoping badges for filter type */}
                            {isAdmin && selectedProductGroup === 'all' && categoryGroups.length > 0 && (
                              <div className="flex items-center gap-1.5 flex-wrap pb-2 border-b">
                                <span className="text-xs text-gray-500 mr-1">Groups:</span>
                                {categoryGroups.map(grp => {
                                  const filterGroups = filter.auto_populate_groups || [];
                                  const isAssigned = filterGroups.includes(grp.slug);
                                  const isUnscoped = filterGroups.length === 0;
                                  return (
                                    <button
                                      key={grp.slug}
                                      onClick={() => handleToggleFilterTypeGroup(
                                        filter.id,
                                        grp.slug,
                                        filterGroups
                                      )}
                                      className={`px-2 py-0.5 rounded text-xs font-medium transition-all border ${
                                        isAssigned
                                          ? 'bg-blue-100 text-blue-700 border-blue-300'
                                          : isUnscoped
                                            ? 'bg-amber-50 text-amber-600 border-amber-200'
                                            : 'bg-gray-50 text-gray-400 border-gray-200 hover:bg-gray-100'
                                      }`}
                                      title={isUnscoped ? `${grp.name} (unscoped)` : isAssigned ? `Remove from ${grp.name}` : `Add to ${grp.name}`}
                                      data-testid={`filter-group-toggle-${filter.slug}-${grp.slug}`}
                                    >
                                      {isAssigned && <Check className="w-3 h-3 inline mr-0.5" />}
                                      {grp.name}
                                    </button>
                                  );
                                })}
                                {(filter.auto_populate_groups || []).length === 0 && (
                                  <span className="text-xs text-amber-500 italic ml-1">unscoped — visible in all groups</span>
                                )}
                              </div>
                            )}
                            {/* Add value input - Only for admins */}
                            {isAdmin && (
                              <div className="flex gap-2">
                                <Input
                                  placeholder={`Add new ${filter.name.toLowerCase()}...`}
                                  className="flex-1 h-8 text-sm"
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter' && e.target.value.trim()) {
                                      handleAddFilterValue(filter.slug, e.target.value);
                                      e.target.value = '';
                                    }
                                  }}
                                />
                                <Button 
                                  size="sm" 
                                  className="bg-blue-600 hover:bg-blue-700 h-8"
                                  onClick={(e) => {
                                    const input = e.target.closest('.flex').querySelector('input');
                                    if (input.value.trim()) {
                                      handleAddFilterValue(filter.slug, input.value);
                                      input.value = '';
                                    }
                                  }}
                                >
                                  <Plus className="w-3 h-3" />
                                </Button>
                              </div>
                            )}
                            
                            {/* Values list */}
                            <div className="flex flex-wrap gap-2">
                              {getVisibleValues(filter.values).map(val => (
                                <div 
                                  key={val.value}
                                  className="group flex items-center gap-1 px-2 py-1 bg-gray-100 rounded text-sm hover:bg-gray-200"
                                >
                                  <span>{val.label}</span>
                                  {isAdmin && (
                                    <button
                                      onClick={() => handleDeleteFilterValue(filter.slug, val.value, val.label, filter.id)}
                                      className="opacity-0 group-hover:opacity-100 p-0.5 text-gray-400 hover:text-red-600 transition-opacity"
                                    >
                                      <X className="w-3 h-3" />
                                    </button>
                                  )}
                                </div>
                              ))}
                              {getVisibleValues(filter.values).length === 0 && (
                                <p className="text-sm text-gray-500 italic">No values in this group</p>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                  
                  {filteredFilters.length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      <Filter className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                      <p>No filters found for this group</p>
                    </div>
                  )}
                </div>
              )}

              {/* Specifications Tab */}
              {activeTab === 'specifications' && (
                <div className="space-y-4">
                  {Object.entries(filteredSpecifications).map(([groupName, specs]) => {
                    const isExpanded = expandedGroups[`spec-${groupName}`] !== false;
                    
                    return (
                      <div key={groupName} className="border rounded-lg overflow-hidden">
                        <button
                          onClick={() => toggleGroup(`spec-${groupName}`)}
                          className="w-full flex items-center justify-between p-3 bg-purple-50 hover:bg-purple-100 transition-colors"
                        >
                          <div className="flex items-center gap-2">
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                            <Sliders className="w-4 h-4 text-purple-600" />
                            <span className="font-medium">{groupName}</span>
                            <Badge variant="secondary">{specs.length} specs</Badge>
                          </div>
                        </button>
                        
                        {isExpanded && (
                          <div className="divide-y">
                            {specs.map(spec => (
                              <div key={spec.id || spec._id || spec.slug} className="p-3 space-y-2">
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center gap-2">
                                    {bulkSelectMode && (
                                      <button
                                        onClick={() => toggleSpecSelect(spec.id || spec._id)}
                                        className="flex-shrink-0"
                                        data-testid={`bulk-select-spec-${spec.slug}`}
                                      >
                                        {selectedSpecIds.has(spec.id || spec._id)
                                          ? <CheckSquare className="w-4 h-4 text-purple-600" />
                                          : <Square className="w-4 h-4 text-gray-400" />}
                                      </button>
                                    )}
                                    <span className="font-medium">{spec.name}</span>
                                    {spec.is_active && <Badge className="bg-green-100 text-green-700 text-xs">Active</Badge>}
                                    <Badge variant="outline" className="text-xs">{getVisibleValues(spec.values).length} values</Badge>
                                  </div>
                                </div>
                                
                                {/* Group scoping badges - show which groups this spec belongs to */}
                                {isAdmin && selectedProductGroup === 'all' && categoryGroups.length > 0 && (
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <span className="text-xs text-gray-500 mr-1">Groups:</span>
                                    {categoryGroups.map(grp => {
                                      const specGroups = spec.product_groups || [];
                                      const isAssigned = specGroups.includes(grp.slug);
                                      const isUnscoped = specGroups.length === 0;
                                      return (
                                        <button
                                          key={grp.slug}
                                          onClick={() => handleToggleSpecTypeGroup(
                                            spec.id || spec._id,
                                            grp.slug,
                                            specGroups
                                          )}
                                          className={`px-2 py-0.5 rounded text-xs font-medium transition-all border ${
                                            isAssigned
                                              ? 'bg-purple-100 text-purple-700 border-purple-300'
                                              : isUnscoped
                                                ? 'bg-amber-50 text-amber-600 border-amber-200'
                                                : 'bg-gray-50 text-gray-400 border-gray-200 hover:bg-gray-100'
                                          }`}
                                          title={isUnscoped ? `${grp.name} (unscoped — shows everywhere)` : isAssigned ? `Remove from ${grp.name}` : `Add to ${grp.name}`}
                                          data-testid={`spec-group-toggle-${spec.slug}-${grp.slug}`}
                                        >
                                          {isAssigned && <Check className="w-3 h-3 inline mr-0.5" />}
                                          {grp.name}
                                        </button>
                                      );
                                    })}
                                    {(spec.product_groups || []).length === 0 && (
                                      <span className="text-xs text-amber-500 italic ml-1">unscoped — visible in all groups</span>
                                    )}
                                  </div>
                                )}
                                
                                {/* Add value input - Only for admins */}
                                {isAdmin && (
                                  <div className="flex gap-2">
                                    <Input
                                      placeholder={`Add new ${spec.name.toLowerCase()} value...`}
                                      className="flex-1 h-8 text-sm"
                                      onKeyDown={(e) => {
                                        if (e.key === 'Enter' && e.target.value.trim()) {
                                          handleAddSpecValue(spec.id || spec._id, e.target.value);
                                          e.target.value = '';
                                        }
                                      }}
                                    />
                                    <Button 
                                      size="sm" 
                                      className="bg-purple-600 hover:bg-purple-700 h-8"
                                      onClick={(e) => {
                                        const input = e.target.closest('.flex').querySelector('input');
                                        if (input.value.trim()) {
                                          handleAddSpecValue(spec.id || spec._id, input.value);
                                          input.value = '';
                                        }
                                      }}
                                    >
                                      <Plus className="w-3 h-3" />
                                    </Button>
                                  </div>
                                )}
                                
                                {/* Values list */}
                                <div className="flex flex-wrap gap-1">
                                  {getVisibleValues(spec.values).map(val => (
                                    <div 
                                      key={val.value}
                                      className="group flex items-center gap-1 px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs hover:bg-purple-200"
                                    >
                                      <span>{val.label}</span>
                                      {isAdmin && (
                                        <button
                                          onClick={() => handleDeleteSpecValue(spec.id || spec._id, val.value, val.label)}
                                          className="opacity-0 group-hover:opacity-100 p-0.5 text-purple-400 hover:text-red-600 transition-opacity"
                                        >
                                          <X className="w-3 h-3" />
                                        </button>
                                      )}
                                    </div>
                                  ))}
                                  {getVisibleValues(spec.values).length === 0 && (
                                    <p className="text-sm text-gray-500 italic">No values in this group — add some above</p>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  
                  {Object.keys(filteredSpecifications).length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      <Sliders className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                      <p>No specifications found for this group</p>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Bulk Scope Action Bar */}
        {bulkSelectMode && (selectedSpecIds.size > 0 || selectedFilterIds.size > 0) && (
          <div className="p-3 border-t bg-gradient-to-r from-indigo-50 to-purple-50 flex items-center gap-3 flex-wrap" data-testid="bulk-scope-action-bar">
            <div className="flex items-center gap-2">
              <CheckSquare className="w-4 h-4 text-indigo-600" />
              <span className="text-sm font-semibold text-indigo-800">
                {selectedSpecIds.size + selectedFilterIds.size} selected
              </span>
              {selectedSpecIds.size > 0 && (
                <Badge className="bg-purple-100 text-purple-700 text-xs">{selectedSpecIds.size} specs</Badge>
              )}
              {selectedFilterIds.size > 0 && (
                <Badge className="bg-blue-100 text-blue-700 text-xs">{selectedFilterIds.size} filters</Badge>
              )}
            </div>
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-xs text-gray-600">Assign to:</span>
              <select
                value={bulkTargetGroup}
                onChange={(e) => setBulkTargetGroup(e.target.value)}
                className="h-8 px-2 rounded border border-gray-300 text-sm bg-white focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400"
                data-testid="bulk-scope-group-select"
              >
                <option value="">Select group...</option>
                {categoryGroups.map(g => (
                  <option key={g.slug} value={g.slug}>{g.name}</option>
                ))}
              </select>
              <Button
                size="sm"
                disabled={!bulkTargetGroup || bulkAssigning}
                onClick={() => handleBulkAssign('add')}
                className="bg-indigo-600 hover:bg-indigo-700 h-8 text-xs"
                data-testid="bulk-scope-assign-btn"
              >
                {bulkAssigning ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Check className="w-3 h-3 mr-1" />}
                Assign
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!bulkTargetGroup || bulkAssigning}
                onClick={() => handleBulkAssign('remove')}
                className="h-8 text-xs text-red-600 border-red-200 hover:bg-red-50"
                data-testid="bulk-scope-remove-btn"
              >
                Remove
              </Button>
              <button onClick={clearBulkSelection} className="text-xs text-gray-500 hover:text-gray-700 underline ml-1">
                Clear
              </button>
            </div>
          </div>
        )}

        {/* Bulk mode — Select All helpers */}
        {bulkSelectMode && selectedSpecIds.size === 0 && selectedFilterIds.size === 0 && (
          <div className="p-2 border-t bg-indigo-50/50 flex items-center gap-3 text-xs text-indigo-600" data-testid="bulk-scope-hint-bar">
            <CheckSquare className="w-3.5 h-3.5" />
            <span>Click items to select, or:</span>
            {(activeTab === 'specifications' || activeTab === 'filters') && (
              <>
                {activeTab === 'specifications' && (
                  <button onClick={selectAllSpecs} className="underline font-medium hover:text-indigo-800">Select all specs</button>
                )}
                {activeTab === 'filters' && (
                  <button onClick={selectAllFilters} className="underline font-medium hover:text-indigo-800">Select all filters</button>
                )}
              </>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="p-3 border-t bg-gradient-to-r from-green-50 to-emerald-50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-green-700">
              <RefreshCw className="w-4 h-4" />
              <span className="text-sm font-medium">Live Sync Enabled</span>
              <span className="text-xs text-green-600">• Changes sync with Navigation & Structure</span>
            </div>
            <a 
              href="/admin/navigation-structure" 
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs text-green-700 hover:text-green-800 font-medium px-3 py-1.5 bg-white rounded border border-green-200 hover:bg-green-50"
            >
              <ExternalLink className="w-3 h-3" />
              Open Navigation & Structure
            </a>
          </div>
        </div>
      </div>
    </div>,
    document.getElementById('modal-portal-root') || document.body
  );
};

export default ManageOptionsModal;
