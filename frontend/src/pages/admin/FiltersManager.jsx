import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Switch } from '../../components/ui/switch';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { 
  Filter, Plus, Pencil, Trash2, GripVertical, Settings, Layers, 
  FileText, CheckSquare, Sliders, ToggleLeft, ChevronDown, ChevronUp,
  RefreshCw, Save, X, Eye, EyeOff
} from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const FiltersManager = () => {
  const [activeTab, setActiveTab] = useState('groups');
  const [filterGroups, setFilterGroups] = useState([]);
  const [filterTypes, setFilterTypes] = useState([]);
  const [pageSettings, setPageSettings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState([]);
  const [productGroups, setProductGroups] = useState([]);
  
  // Dialogs
  const [showGroupDialog, setShowGroupDialog] = useState(false);
  const [showFilterDialog, setShowFilterDialog] = useState(false);
  const [showValueDialog, setShowValueDialog] = useState(false);
  const [editingGroup, setEditingGroup] = useState(null);
  const [editingFilter, setEditingFilter] = useState(null);
  const [editingValue, setEditingValue] = useState(null);
  const [selectedFilterForValues, setSelectedFilterForValues] = useState(null);

  // Form states
  const [groupForm, setGroupForm] = useState({
    name: '', slug: '', description: '', category_slugs: [], group_slugs: [], filter_ids: [], is_active: true, display_order: 0
  });
  const [filterForm, setFilterForm] = useState({
    name: '', slug: '', input_type: 'checkbox', description: '', values: [], is_active: true, auto_populate: false, auto_populate_field: ''
  });
  const [valueForm, setValueForm] = useState({ value: '', label: '', display_order: 0, is_active: true });

  // Fetch data
  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [groupsRes, typesRes, settingsRes, catsRes, prodGroupsRes] = await Promise.all([
        fetch(`${API_URL}/api/filters/groups`),
        fetch(`${API_URL}/api/filters/types`),
        fetch(`${API_URL}/api/filters/page-settings`),
        fetch(`${API_URL}/api/website-admin/categories`),
        fetch(`${API_URL}/api/website-admin/category-groups`)
      ]);
      
      if (groupsRes.ok) setFilterGroups(await groupsRes.json());
      if (typesRes.ok) setFilterTypes(await typesRes.json());
      if (settingsRes.ok) setPageSettings(await settingsRes.json());
      if (catsRes.ok) setCategories(await catsRes.json());
      if (prodGroupsRes.ok) setProductGroups(await prodGroupsRes.json());
    } catch (error) {
      toast.error('Failed to load filters data');
    }
    setLoading(false);
  };

  const seedDefaults = async () => {
    try {
      const res = await fetch(`${API_URL}/api/filters/seed-defaults`, { method: 'POST' });
      const data = await res.json();
      if (data.skipped) {
        toast.info('Default filters already exist');
      } else {
        toast.success(`Created ${data.filter_types} filter types and ${data.filter_groups} groups`);
        fetchData();
      }
    } catch (error) {
      toast.error('Failed to seed defaults');
    }
  };

  // Filter Group handlers
  const handleSaveGroup = async () => {
    try {
      const url = editingGroup 
        ? `${API_URL}/api/filters/groups/${editingGroup.id}`
        : `${API_URL}/api/filters/groups`;
      const method = editingGroup ? 'PUT' : 'POST';
      
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(groupForm)
      });
      
      if (res.ok) {
        toast.success(editingGroup ? 'Filter group updated' : 'Filter group created');
        setShowGroupDialog(false);
        setEditingGroup(null);
        resetGroupForm();
        fetchData();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to save group');
      }
    } catch (error) {
      toast.error('Failed to save group');
    }
  };

  const handleDeleteGroup = async (groupId) => {
    if (!window.confirm('Delete this filter group?')) return;
    try {
      const res = await fetch(`${API_URL}/api/filters/groups/${groupId}`, { method: 'DELETE' });
      if (res.ok) {
        toast.success('Filter group deleted');
        fetchData();
      }
    } catch (error) {
      toast.error('Failed to delete group');
    }
  };

  // Filter Type handlers
  const handleSaveFilter = async () => {
    try {
      const url = editingFilter 
        ? `${API_URL}/api/filters/types/${editingFilter.id}`
        : `${API_URL}/api/filters/types`;
      const method = editingFilter ? 'PUT' : 'POST';
      
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(filterForm)
      });
      
      if (res.ok) {
        toast.success(editingFilter ? 'Filter updated' : 'Filter created');
        setShowFilterDialog(false);
        setEditingFilter(null);
        resetFilterForm();
        fetchData();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to save filter');
      }
    } catch (error) {
      toast.error('Failed to save filter');
    }
  };

  const handleDeleteFilter = async (filterId) => {
    if (!window.confirm('Delete this filter type?')) return;
    try {
      const res = await fetch(`${API_URL}/api/filters/types/${filterId}`, { method: 'DELETE' });
      if (res.ok) {
        toast.success('Filter type deleted');
        fetchData();
      }
    } catch (error) {
      toast.error('Failed to delete filter');
    }
  };

  // Value handlers
  const handleAddValue = async () => {
    if (!selectedFilterForValues) return;
    try {
      const res = await fetch(`${API_URL}/api/filters/types/${selectedFilterForValues.id}/values`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(valueForm)
      });
      
      if (res.ok) {
        toast.success('Value added');
        setShowValueDialog(false);
        resetValueForm();
        fetchData();
      }
    } catch (error) {
      toast.error('Failed to add value');
    }
  };

  // Page settings handler
  const handleSavePageSettings = async (pageSlug, settings) => {
    try {
      const res = await fetch(`${API_URL}/api/filters/page-settings/${pageSlug}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      
      if (res.ok) {
        toast.success('Page settings updated');
        fetchData();
      }
    } catch (error) {
      toast.error('Failed to update page settings');
    }
  };

  const resetGroupForm = () => setGroupForm({ name: '', slug: '', description: '', category_slugs: [], filter_ids: [], is_active: true, display_order: 0 });
  const resetFilterForm = () => setFilterForm({ name: '', slug: '', input_type: 'checkbox', description: '', values: [], is_active: true, auto_populate: false, auto_populate_field: '' });
  const resetValueForm = () => setValueForm({ value: '', label: '', display_order: 0, is_active: true });

  const openEditGroup = (group) => {
    setEditingGroup(group);
    setGroupForm({
      name: group.name,
      slug: group.slug,
      description: group.description || '',
      category_slugs: group.category_slugs || [],
      group_slugs: group.group_slugs || [],
      filter_ids: group.filter_ids || [],
      is_active: group.is_active !== false,
      display_order: group.display_order || 0
    });
    setShowGroupDialog(true);
  };

  const openEditFilter = (filter) => {
    setEditingFilter(filter);
    setFilterForm({
      name: filter.name,
      slug: filter.slug,
      input_type: filter.input_type || 'checkbox',
      description: filter.description || '',
      values: filter.values || [],
      is_active: filter.is_active !== false,
      auto_populate: filter.auto_populate || false,
      auto_populate_field: filter.auto_populate_field || ''
    });
    setShowFilterDialog(true);
  };

  const generateSlug = (name) => {
    return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  };

  const inputTypes = [
    { value: 'checkbox', label: 'Checkboxes', icon: CheckSquare },
    { value: 'dropdown', label: 'Dropdown', icon: ChevronDown },
    { value: 'range', label: 'Range Slider', icon: Sliders },
    { value: 'toggle', label: 'Toggle', icon: ToggleLeft }
  ];

  const productFields = [
    { value: 'size', label: 'Size' },
    { value: 'colour', label: 'Color' },
    { value: 'finish', label: 'Finish' },
    { value: 'material', label: 'Material' },
    { value: 'category', label: 'Category' },
    { value: 'rooms', label: 'Room Suitability' },
    { value: 'styles', label: 'Style' }
  ];

  const pages = [
    { slug: 'collections', name: 'Collections Page', path: '/tiles' },
    { slug: 'collection-detail', name: 'Collection Detail', path: '/shop/collection/:name' },
    { slug: 'all-tiles', name: 'All Tiles', path: '/shop/all-tiles' },
    { slug: 'search', name: 'Search Results', path: '/shop/search' }
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Filter className="w-6 h-6" />
            Product Filters
          </h1>
          <p className="text-gray-500">Manage filter types, groups, and page settings</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={seedDefaults}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Seed Defaults
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="groups" className="flex items-center gap-2">
            <Layers className="w-4 h-4" />
            Filter Groups ({filterGroups.length})
          </TabsTrigger>
          <TabsTrigger value="types" className="flex items-center gap-2">
            <Filter className="w-4 h-4" />
            Filter Types ({filterTypes.length})
          </TabsTrigger>
          <TabsTrigger value="pages" className="flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Page Settings
          </TabsTrigger>
        </TabsList>

        {/* Filter Groups Tab */}
        <TabsContent value="groups">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Filter Groups</CardTitle>
              <Button onClick={() => { resetGroupForm(); setEditingGroup(null); setShowGroupDialog(true); }}>
                <Plus className="w-4 h-4 mr-2" />
                Add Group
              </Button>
            </CardHeader>
            <CardContent>
              {filterGroups.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Layers className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>No filter groups yet. Click "Seed Defaults" to create tiles filters.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {filterGroups.map((group) => (
                    <div key={group.id} className="border rounded-lg p-4 hover:bg-gray-50 transition-colors">
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-3">
                          <GripVertical className="w-5 h-5 text-gray-400 mt-1 cursor-grab" />
                          <div>
                            <div className="flex items-center gap-2">
                              <h3 className="font-semibold">{group.name}</h3>
                              <Badge variant={group.is_active ? "default" : "secondary"}>
                                {group.is_active ? "Active" : "Inactive"}
                              </Badge>
                            </div>
                            <p className="text-sm text-gray-500">{group.description}</p>
                            <div className="flex flex-wrap gap-1 mt-2">
                              {group.group_slugs?.map(gs => (
                                <Badge key={gs} variant="default" className="text-xs bg-blue-600">{gs}</Badge>
                              ))}
                              {group.category_slugs?.map(cat => (
                                <Badge key={cat} variant="outline" className="text-xs">{cat}</Badge>
                              ))}
                            </div>
                            <p className="text-xs text-gray-400 mt-1">
                              {group.filter_ids?.length || 0} filters assigned
                            </p>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button variant="ghost" size="sm" onClick={() => openEditGroup(group)}>
                            <Pencil className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDeleteGroup(group.id)}>
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Filter Types Tab */}
        <TabsContent value="types">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Filter Types</CardTitle>
              <Button onClick={() => { resetFilterForm(); setEditingFilter(null); setShowFilterDialog(true); }}>
                <Plus className="w-4 h-4 mr-2" />
                Add Filter
              </Button>
            </CardHeader>
            <CardContent>
              {filterTypes.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Filter className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>No filter types yet. Click "Seed Defaults" to create default filters.</p>
                </div>
              ) : (
                <div className="grid gap-3">
                  {filterTypes.map((filter) => {
                    const TypeIcon = inputTypes.find(t => t.value === filter.input_type)?.icon || Filter;
                    return (
                      <div key={filter.id} className="border rounded-lg p-4 hover:bg-gray-50 transition-colors">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-3">
                            <div className="p-2 bg-gray-100 rounded-lg">
                              <TypeIcon className="w-5 h-5 text-gray-600" />
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <h3 className="font-semibold">{filter.name}</h3>
                                <Badge variant="outline" className="text-xs">{filter.input_type}</Badge>
                                {filter.auto_populate && (
                                  <Badge variant="secondary" className="text-xs">Auto-populate</Badge>
                                )}
                                <Badge variant={filter.is_active ? "default" : "secondary"}>
                                  {filter.is_active ? "Active" : "Inactive"}
                                </Badge>
                              </div>
                              <p className="text-sm text-gray-500">{filter.description}</p>
                              {filter.values?.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-2">
                                  {filter.values.slice(0, 8).map((v, i) => (
                                    <Badge key={i} variant="outline" className="text-xs">
                                      {v.label}
                                    </Badge>
                                  ))}
                                  {filter.values.length > 8 && (
                                    <Badge variant="outline" className="text-xs">
                                      +{filter.values.length - 8} more
                                    </Badge>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Button 
                              variant="ghost" 
                              size="sm" 
                              onClick={() => { setSelectedFilterForValues(filter); setShowValueDialog(true); }}
                              title="Add Value"
                            >
                              <Plus className="w-4 h-4" />
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => openEditFilter(filter)}>
                              <Pencil className="w-4 h-4" />
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => handleDeleteFilter(filter.id)}>
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Page Settings Tab */}
        <TabsContent value="pages">
          <Card>
            <CardHeader>
              <CardTitle>Page Filter Settings</CardTitle>
              <p className="text-sm text-gray-500">Configure which filters appear on each page</p>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {pages.map((page) => {
                  const settings = pageSettings.find(s => s.page_slug === page.slug) || {
                    page_slug: page.slug,
                    enabled_filter_groups: [],
                    auto_detect: true,
                    display_style: 'sidebar'
                  };
                  
                  return (
                    <div key={page.slug} className="border rounded-lg p-4">
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <h3 className="font-semibold">{page.name}</h3>
                          <p className="text-xs text-gray-400">{page.path}</p>
                        </div>
                        <Badge variant={settings.auto_detect ? "default" : "secondary"}>
                          {settings.auto_detect ? "Auto-detect" : "Manual"}
                        </Badge>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label className="text-xs">Display Style</Label>
                          <Select 
                            value={settings.display_style || 'sidebar'}
                            onValueChange={(value) => handleSavePageSettings(page.slug, { ...settings, display_style: value })}
                          >
                            <SelectTrigger className="mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="sidebar">Sidebar</SelectItem>
                              <SelectItem value="drawer">Collapsible Drawer</SelectItem>
                              <SelectItem value="topbar">Top Bar</SelectItem>
                              <SelectItem value="modal">Modal</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        
                        <div>
                          <Label className="text-xs">Filter Groups</Label>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {filterGroups.map(group => {
                              const isEnabled = settings.enabled_filter_groups?.includes(group.slug);
                              return (
                                <Badge 
                                  key={group.slug}
                                  variant={isEnabled ? "default" : "outline"}
                                  className="cursor-pointer"
                                  onClick={() => {
                                    const newGroups = isEnabled
                                      ? settings.enabled_filter_groups.filter(g => g !== group.slug)
                                      : [...(settings.enabled_filter_groups || []), group.slug];
                                    handleSavePageSettings(page.slug, { ...settings, enabled_filter_groups: newGroups });
                                  }}
                                >
                                  {group.name}
                                </Badge>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2 mt-3 pt-3 border-t">
                        <Switch 
                          checked={settings.auto_detect}
                          onCheckedChange={(checked) => handleSavePageSettings(page.slug, { ...settings, auto_detect: checked })}
                        />
                        <Label className="text-sm">Auto-detect filters based on products shown</Label>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Filter Group Dialog */}
      <Dialog open={showGroupDialog} onOpenChange={setShowGroupDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingGroup ? 'Edit Filter Group' : 'Create Filter Group'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Name</Label>
                <Input 
                  value={groupForm.name}
                  onChange={(e) => {
                    setGroupForm({ 
                      ...groupForm, 
                      name: e.target.value,
                      slug: editingGroup ? groupForm.slug : generateSlug(e.target.value)
                    });
                  }}
                  placeholder="e.g., Tiles, Adhesives"
                />
              </div>
              <div>
                <Label>Slug</Label>
                <Input 
                  value={groupForm.slug}
                  onChange={(e) => setGroupForm({ ...groupForm, slug: e.target.value })}
                  placeholder="e.g., tiles"
                />
              </div>
            </div>
            
            <div>
              <Label>Description</Label>
              <Input 
                value={groupForm.description}
                onChange={(e) => setGroupForm({ ...groupForm, description: e.target.value })}
                placeholder="Filters for tile products"
              />
            </div>
            
            <div>
              <Label>Applies to Product Groups</Label>
              <p className="text-xs text-gray-400 mb-1">All categories in selected groups will automatically inherit these filters</p>
              <div className="flex flex-wrap gap-1 p-2 border rounded-lg min-h-[40px]">
                {productGroups.map(pg => {
                  const isSelected = groupForm.group_slugs.includes(pg.slug);
                  return (
                    <Badge 
                      key={pg.slug}
                      variant={isSelected ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => {
                        setGroupForm({
                          ...groupForm,
                          group_slugs: isSelected
                            ? groupForm.group_slugs.filter(s => s !== pg.slug)
                            : [...groupForm.group_slugs, pg.slug]
                        });
                      }}
                    >
                      {pg.name}
                    </Badge>
                  );
                })}
              </div>
            </div>

            <div>
              <Label>Applies to Categories (Legacy - optional)</Label>
              <div className="flex flex-wrap gap-1 mt-1 p-2 border rounded-lg min-h-[60px]">
                {categories.map(cat => {
                  const isSelected = groupForm.category_slugs.includes(cat.slug);
                  return (
                    <Badge 
                      key={cat.slug}
                      variant={isSelected ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => {
                        setGroupForm({
                          ...groupForm,
                          category_slugs: isSelected
                            ? groupForm.category_slugs.filter(s => s !== cat.slug)
                            : [...groupForm.category_slugs, cat.slug]
                        });
                      }}
                    >
                      {cat.name}
                    </Badge>
                  );
                })}
              </div>
              <p className="text-xs text-gray-400 mt-1">Leave empty to apply to all categories</p>
            </div>
            
            <div>
              <Label>Filters in this Group</Label>
              <div className="flex flex-wrap gap-1 mt-1 p-2 border rounded-lg min-h-[60px]">
                {filterTypes.map(filter => {
                  const isSelected = groupForm.filter_ids.includes(filter.id);
                  return (
                    <Badge 
                      key={filter.id}
                      variant={isSelected ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => {
                        setGroupForm({
                          ...groupForm,
                          filter_ids: isSelected
                            ? groupForm.filter_ids.filter(id => id !== filter.id)
                            : [...groupForm.filter_ids, filter.id]
                        });
                      }}
                    >
                      {filter.name}
                    </Badge>
                  );
                })}
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Switch 
                checked={groupForm.is_active}
                onCheckedChange={(checked) => setGroupForm({ ...groupForm, is_active: checked })}
              />
              <Label>Active</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowGroupDialog(false)}>Cancel</Button>
            <Button onClick={handleSaveGroup}>
              <Save className="w-4 h-4 mr-2" />
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Filter Type Dialog */}
      <Dialog open={showFilterDialog} onOpenChange={setShowFilterDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingFilter ? 'Edit Filter' : 'Create Filter'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Name</Label>
                <Input 
                  value={filterForm.name}
                  onChange={(e) => {
                    setFilterForm({ 
                      ...filterForm, 
                      name: e.target.value,
                      slug: editingFilter ? filterForm.slug : generateSlug(e.target.value)
                    });
                  }}
                  placeholder="e.g., Size, Color"
                />
              </div>
              <div>
                <Label>Slug</Label>
                <Input 
                  value={filterForm.slug}
                  onChange={(e) => setFilterForm({ ...filterForm, slug: e.target.value })}
                />
              </div>
            </div>
            
            <div>
              <Label>Input Type</Label>
              <Select 
                value={filterForm.input_type}
                onValueChange={(value) => setFilterForm({ ...filterForm, input_type: value })}
              >
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {inputTypes.map(type => (
                    <SelectItem key={type.value} value={type.value}>
                      <div className="flex items-center gap-2">
                        <type.icon className="w-4 h-4" />
                        {type.label}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <Label>Description</Label>
              <Input 
                value={filterForm.description}
                onChange={(e) => setFilterForm({ ...filterForm, description: e.target.value })}
                placeholder="Filter by tile dimensions"
              />
            </div>
            
            <div className="border-t pt-4">
              <div className="flex items-center gap-2 mb-3">
                <Switch 
                  checked={filterForm.auto_populate}
                  onCheckedChange={(checked) => setFilterForm({ ...filterForm, auto_populate: checked })}
                />
                <Label>Auto-populate values from products</Label>
              </div>
              
              {filterForm.auto_populate && (
                <div>
                  <Label>Product Field</Label>
                  <Select 
                    value={filterForm.auto_populate_field}
                    onValueChange={(value) => setFilterForm({ ...filterForm, auto_populate_field: value })}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="Select field" />
                    </SelectTrigger>
                    <SelectContent>
                      {productFields.map(field => (
                        <SelectItem key={field.value} value={field.value}>{field.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
            
            <div className="flex items-center gap-2">
              <Switch 
                checked={filterForm.is_active}
                onCheckedChange={(checked) => setFilterForm({ ...filterForm, is_active: checked })}
              />
              <Label>Active</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowFilterDialog(false)}>Cancel</Button>
            <Button onClick={handleSaveFilter}>
              <Save className="w-4 h-4 mr-2" />
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Value Dialog */}
      <Dialog open={showValueDialog} onOpenChange={setShowValueDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add Filter Value</DialogTitle>
            {selectedFilterForValues && (
              <p className="text-sm text-gray-500">Adding value to: {selectedFilterForValues.name}</p>
            )}
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Value (internal)</Label>
              <Input 
                value={valueForm.value}
                onChange={(e) => setValueForm({ ...valueForm, value: e.target.value })}
                placeholder="e.g., 60x60"
              />
            </div>
            <div>
              <Label>Label (display)</Label>
              <Input 
                value={valueForm.label}
                onChange={(e) => setValueForm({ ...valueForm, label: e.target.value })}
                placeholder="e.g., 60x60cm"
              />
            </div>
            <div>
              <Label>Display Order</Label>
              <Input 
                type="number"
                value={valueForm.display_order}
                onChange={(e) => setValueForm({ ...valueForm, display_order: parseInt(e.target.value) || 0 })}
              />
            </div>
            <div className="flex items-center gap-2">
              <Switch 
                checked={valueForm.is_active}
                onCheckedChange={(checked) => setValueForm({ ...valueForm, is_active: checked })}
              />
              <Label>Active</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowValueDialog(false); resetValueForm(); }}>Cancel</Button>
            <Button onClick={handleAddValue}>
              <Plus className="w-4 h-4 mr-2" />
              Add Value
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default FiltersManager;
