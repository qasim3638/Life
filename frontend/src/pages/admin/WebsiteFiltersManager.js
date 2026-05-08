import React, { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Save, X, Filter, ChevronDown, ChevronRight, GripVertical, Layers, FileText, Settings, RefreshCw, CheckSquare, Sliders, ToggleLeft, Eye, Monitor } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Switch } from '../../components/ui/switch';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Checkbox } from '../../components/ui/checkbox';
import { Slider } from '../../components/ui/slider';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const WebsiteFiltersManager = () => {
  const [activeTab, setActiveTab] = useState('types');
  const [filters, setFilters] = useState([]);
  const [filterGroups, setFilterGroups] = useState([]);
  const [pageSettings, setPageSettings] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingFilter, setEditingFilter] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [expandedFilters, setExpandedFilters] = useState({});
  const [newOption, setNewOption] = useState({ name: '', value: '' });

  // Group dialog state
  const [showGroupDialog, setShowGroupDialog] = useState(false);
  const [editingGroup, setEditingGroup] = useState(null);
  const [groupForm, setGroupForm] = useState({
    name: '', slug: '', description: '', category_slugs: [], filter_ids: [], is_active: true, display_order: 0
  });

  const emptyForm = {
    name: '',
    slug: '',
    filter_type: 'checkbox',
    display_order: 0,
    is_active: true,
    options: [],
    auto_populate: false,
    auto_populate_field: ''
  };

  const [formData, setFormData] = useState(emptyForm);

  useEffect(() => {
    fetchAllData();
  }, []);

  const fetchAllData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const [filtersRes, groupsRes, settingsRes, catsRes] = await Promise.all([
        fetch(`${API_URL}/api/filters/types`),  // Use new filters endpoint
        fetch(`${API_URL}/api/filters/groups`),
        fetch(`${API_URL}/api/filters/page-settings`),
        fetch(`${API_URL}/api/website-admin/categories`)
      ]);
      
      if (filtersRes.ok) {
        const data = await filtersRes.json();
        setFilters(data);
        const expanded = {};
        data.forEach(f => { expanded[f.id] = true; });
        setExpandedFilters(expanded);
      }
      if (groupsRes.ok) setFilterGroups(await groupsRes.json());
      if (settingsRes.ok) setPageSettings(await settingsRes.json());
      if (catsRes.ok) setCategories(await catsRes.json());
    } catch (e) {
      toast.error('Failed to load filters data');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => {
      const updated = { ...prev, [field]: value };
      if (field === 'name' && !editingFilter) {
        updated.slug = value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
      }
      return updated;
    });
  };

  const handleAddOption = () => {
    if (!newOption.name || !newOption.value) {
      toast.error('Option name and value are required');
      return;
    }
    
    setFormData(prev => ({
      ...prev,
      options: [...prev.options, { ...newOption, display_order: prev.options.length, is_active: true }]
    }));
    setNewOption({ name: '', value: '' });
  };

  const handleRemoveOption = (index) => {
    setFormData(prev => ({
      ...prev,
      options: prev.options.filter((_, i) => i !== index)
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const token = localStorage.getItem('token');

    try {
      const url = editingFilter 
        ? `${API_URL}/api/filters/types/${editingFilter.id}`
        : `${API_URL}/api/filters/types`;
      
      const res = await fetch(url, {
        method: editingFilter ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          name: formData.name,
          slug: formData.slug,
          input_type: formData.filter_type,
          description: '',
          values: formData.options.map(o => ({ value: o.value, label: o.name, display_order: o.display_order || 0, is_active: o.is_active !== false })),
          is_active: formData.is_active,
          auto_populate: formData.auto_populate || false,
          auto_populate_field: formData.auto_populate_field || ''
        })
      });

      if (res.ok) {
        toast.success(editingFilter ? 'Filter updated' : 'Filter created');
        setShowForm(false);
        setEditingFilter(null);
        setFormData(emptyForm);
        fetchAllData();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to save filter');
      }
    } catch (e) {
      toast.error('Failed to save filter');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this filter?')) return;
    
    const token = localStorage.getItem('token');
    try {
      const res = await fetch(`${API_URL}/api/filters/types/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.ok) {
        toast.success('Filter deleted');
        fetchAllData();
      }
    } catch (e) {
      toast.error('Failed to delete filter');
    }
  };

  const handleEdit = (filter) => {
    setEditingFilter(filter);
    setFormData({
      name: filter.name,
      slug: filter.slug,
      filter_type: filter.input_type || 'checkbox',
      display_order: filter.display_order || 0,
      is_active: filter.is_active !== false,
      options: (filter.values || []).map(v => ({ name: v.label || v.value, value: v.value, display_order: v.display_order || 0, is_active: v.is_active !== false })),
      auto_populate: filter.auto_populate || false,
      auto_populate_field: filter.auto_populate_field || ''
    });
    setShowForm(true);
  };

  const toggleExpanded = (id) => {
    setExpandedFilters(prev => ({ ...prev, [id]: !prev[id] }));
  };

  // Group handlers
  const handleSaveGroup = async () => {
    try {
      const url = editingGroup 
        ? `${API_URL}/api/filters/groups/${editingGroup.id}`
        : `${API_URL}/api/filters/groups`;
      
      const res = await fetch(url, {
        method: editingGroup ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(groupForm)
      });
      
      if (res.ok) {
        toast.success(editingGroup ? 'Group updated' : 'Group created');
        setShowGroupDialog(false);
        setEditingGroup(null);
        setGroupForm({ name: '', slug: '', description: '', category_slugs: [], filter_ids: [], is_active: true, display_order: 0 });
        fetchAllData();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to save group');
      }
    } catch (e) {
      toast.error('Failed to save group');
    }
  };

  const handleDeleteGroup = async (groupId) => {
    if (!window.confirm('Delete this filter group?')) return;
    try {
      const res = await fetch(`${API_URL}/api/filters/groups/${groupId}`, { method: 'DELETE' });
      if (res.ok) {
        toast.success('Group deleted');
        fetchAllData();
      }
    } catch (e) {
      toast.error('Failed to delete group');
    }
  };

  const openEditGroup = (group) => {
    setEditingGroup(group);
    setGroupForm({
      name: group.name,
      slug: group.slug,
      description: group.description || '',
      category_slugs: group.category_slugs || [],
      filter_ids: group.filter_ids || [],
      is_active: group.is_active !== false,
      display_order: group.display_order || 0
    });
    setShowGroupDialog(true);
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
        toast.success('Settings saved');
        fetchAllData();
      }
    } catch (e) {
      toast.error('Failed to save settings');
    }
  };

  const seedDefaults = async () => {
    try {
      const res = await fetch(`${API_URL}/api/filters/seed-defaults`, { method: 'POST' });
      const data = await res.json();
      if (data.skipped) {
        toast.info('Default filters already exist');
      } else {
        toast.success(`Created ${data.filter_types} filters`);
        fetchAllData();
      }
    } catch (e) {
      toast.error('Failed to seed defaults');
    }
  };

  const generateSlug = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');

  const filterTypes = [
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
    { value: 'rooms', label: 'Rooms' },
    { value: 'styles', label: 'Styles' }
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
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Filter className="w-6 h-6" />
            Product Filters
          </h1>
          <p className="text-gray-500 text-sm">Manage filters for different product categories</p>
        </div>
        <Button variant="outline" onClick={seedDefaults}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Seed Defaults
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="types" className="flex items-center gap-2">
            <Filter className="w-4 h-4" />
            Filter Types ({filters.length})
          </TabsTrigger>
          <TabsTrigger value="groups" className="flex items-center gap-2">
            <Layers className="w-4 h-4" />
            Filter Groups ({filterGroups.length})
          </TabsTrigger>
          <TabsTrigger value="pages" className="flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Page Settings
          </TabsTrigger>
          <TabsTrigger value="preview" className="flex items-center gap-2">
            <Eye className="w-4 h-4" />
            Preview
          </TabsTrigger>
        </TabsList>

        {/* Filter Types Tab */}
        <TabsContent value="types">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between py-4">
              <CardTitle className="text-lg">Filter Types</CardTitle>
              <Button size="sm" onClick={() => { setEditingFilter(null); setFormData(emptyForm); setShowForm(true); }}>
                <Plus className="w-4 h-4 mr-2" />
                Add Filter
              </Button>
            </CardHeader>
            <CardContent>
              {showForm && (
                <form onSubmit={handleSubmit} className="bg-gray-50 p-4 rounded-lg mb-4 border">
                  <h3 className="font-medium mb-3">{editingFilter ? 'Edit Filter' : 'New Filter'}</h3>
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <Label>Name</Label>
                      <Input
                        value={formData.name}
                        onChange={(e) => handleInputChange('name', e.target.value)}
                        placeholder="e.g., Size, Color"
                        required
                      />
                    </div>
                    <div>
                      <Label>Slug</Label>
                      <Input
                        value={formData.slug}
                        onChange={(e) => handleInputChange('slug', e.target.value)}
                        placeholder="e.g., size"
                        required
                      />
                    </div>
                    <div>
                      <Label>Type</Label>
                      <Select value={formData.filter_type} onValueChange={(v) => handleInputChange('filter_type', v)}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {filterTypes.map(t => (
                            <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Display Order</Label>
                      <Input
                        type="number"
                        value={formData.display_order}
                        onChange={(e) => handleInputChange('display_order', parseInt(e.target.value) || 0)}
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-4 mb-4">
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={formData.is_active}
                        onCheckedChange={(v) => handleInputChange('is_active', v)}
                      />
                      <Label>Active</Label>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={formData.auto_populate}
                        onCheckedChange={(v) => handleInputChange('auto_populate', v)}
                      />
                      <Label>Auto-populate from products</Label>
                    </div>
                    {formData.auto_populate && (
                      <Select value={formData.auto_populate_field} onValueChange={(v) => handleInputChange('auto_populate_field', v)}>
                        <SelectTrigger className="w-40"><SelectValue placeholder="Field" /></SelectTrigger>
                        <SelectContent>
                          {productFields.map(f => (
                            <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>

                  {/* Options */}
                  <div className="mb-4">
                    <Label>Filter Options</Label>
                    <div className="flex gap-2 mt-1 mb-2">
                      <Input
                        placeholder="Display name"
                        value={newOption.name}
                        onChange={(e) => setNewOption({ ...newOption, name: e.target.value })}
                        className="flex-1"
                      />
                      <Input
                        placeholder="Value"
                        value={newOption.value}
                        onChange={(e) => setNewOption({ ...newOption, value: e.target.value })}
                        className="flex-1"
                      />
                      <Button type="button" variant="outline" onClick={handleAddOption}>
                        <Plus className="w-4 h-4" />
                      </Button>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {formData.options.map((opt, i) => (
                        <Badge key={i} variant="secondary" className="pl-2 pr-1 py-1 flex items-center gap-1">
                          {opt.name}
                          <button type="button" onClick={() => handleRemoveOption(i)} className="ml-1 hover:text-red-500">
                            <X className="w-3 h-3" />
                          </button>
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Button type="submit"><Save className="w-4 h-4 mr-2" />Save</Button>
                    <Button type="button" variant="outline" onClick={() => { setShowForm(false); setEditingFilter(null); }}>
                      Cancel
                    </Button>
                  </div>
                </form>
              )}

              <div className="space-y-2">
                {filters.map((filter) => (
                  <div key={filter.id} className="border rounded-lg overflow-hidden">
                    <div 
                      className="flex items-center justify-between p-3 bg-white hover:bg-gray-50 cursor-pointer"
                      onClick={() => toggleExpanded(filter.id)}
                    >
                      <div className="flex items-center gap-3">
                        <GripVertical className="w-4 h-4 text-gray-400" />
                        {expandedFilters[filter.id] ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        <span className="font-medium">{filter.name}</span>
                        <Badge variant="outline" className="text-xs">{filter.input_type || filter.filter_type}</Badge>
                        {!filter.is_active && <Badge variant="secondary">Inactive</Badge>}
                        {filter.auto_populate && <Badge variant="outline" className="text-xs bg-blue-50">Auto</Badge>}
                      </div>
                      <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                        <Button variant="ghost" size="sm" onClick={() => handleEdit(filter)}>
                          <Edit2 className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(filter.id)}>
                          <Trash2 className="w-4 h-4 text-red-500" />
                        </Button>
                      </div>
                    </div>
                    {expandedFilters[filter.id] && (filter.values?.length > 0 || filter.options?.length > 0) && (
                      <div className="px-4 py-2 bg-gray-50 border-t">
                        <div className="flex flex-wrap gap-1">
                          {(filter.values || filter.options || []).map((opt, i) => (
                            <Badge key={i} variant="outline" className="text-xs">
                              {opt.label || opt.name || opt.value}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Filter Groups Tab */}
        <TabsContent value="groups">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between py-4">
              <div>
                <CardTitle className="text-lg">Filter Groups</CardTitle>
                <p className="text-sm text-gray-500">Assign filters to product categories</p>
              </div>
              <Button size="sm" onClick={() => { 
                setEditingGroup(null); 
                setGroupForm({ name: '', slug: '', description: '', category_slugs: [], filter_ids: [], is_active: true, display_order: 0 }); 
                setShowGroupDialog(true); 
              }}>
                <Plus className="w-4 h-4 mr-2" />
                Add Group
              </Button>
            </CardHeader>
            <CardContent>
              {filterGroups.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Layers className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>No filter groups yet.</p>
                  <p className="text-sm">Click "Seed Defaults" to create tiles filters.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {filterGroups.map((group) => (
                    <div key={group.id} className="border rounded-lg p-4 hover:bg-gray-50">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="font-semibold">{group.name}</h3>
                            <Badge variant={group.is_active ? "default" : "secondary"}>
                              {group.is_active ? "Active" : "Inactive"}
                            </Badge>
                          </div>
                          <p className="text-sm text-gray-500 mb-2">{group.description}</p>
                          <div className="flex flex-wrap gap-1 mb-2">
                            <span className="text-xs text-gray-400 mr-1">Categories:</span>
                            {group.category_slugs?.length > 0 ? (
                              group.category_slugs.map(cat => (
                                <Badge key={cat} variant="outline" className="text-xs">{cat}</Badge>
                              ))
                            ) : (
                              <Badge variant="outline" className="text-xs">All</Badge>
                            )}
                          </div>
                          <p className="text-xs text-gray-400">{group.filter_ids?.length || 0} filters assigned</p>
                        </div>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="sm" onClick={() => openEditGroup(group)}>
                            <Edit2 className="w-4 h-4" />
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

        {/* Page Settings Tab */}
        <TabsContent value="pages">
          <Card>
            <CardHeader className="py-4">
              <CardTitle className="text-lg">Page Filter Settings</CardTitle>
              <p className="text-sm text-gray-500">Configure which filters appear on each page</p>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {pages.map((page) => {
                  const settings = pageSettings.find(s => s.page_slug === page.slug) || {
                    page_slug: page.slug, enabled_filter_groups: [], auto_detect: true, display_style: 'sidebar'
                  };
                  
                  return (
                    <div key={page.slug} className="border rounded-lg p-4">
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <h3 className="font-semibold">{page.name}</h3>
                          <p className="text-xs text-gray-400">{page.path}</p>
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label className="text-xs">Display Style</Label>
                          <Select 
                            value={settings.display_style || 'sidebar'}
                            onValueChange={(value) => handleSavePageSettings(page.slug, { ...settings, display_style: value })}
                          >
                            <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="sidebar">Sidebar</SelectItem>
                              <SelectItem value="drawer">Collapsible Drawer</SelectItem>
                              <SelectItem value="topbar">Top Bar Dropdowns</SelectItem>
                              <SelectItem value="modal">Filter Modal</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        
                        <div>
                          <Label className="text-xs">Enabled Filter Groups</Label>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {filterGroups.map(group => {
                              const isEnabled = settings.enabled_filter_groups?.includes(group.slug);
                              return (
                                <Badge 
                                  key={group.slug}
                                  variant={isEnabled ? "default" : "outline"}
                                  className="cursor-pointer text-xs"
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
                        <Label className="text-sm">Auto-detect filters based on products</Label>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Preview Tab */}
        <TabsContent value="preview">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Filter Sidebar Preview */}
            <Card>
              <CardHeader className="py-4">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Monitor className="w-5 h-5" />
                  Filter Sidebar Preview
                </CardTitle>
                <p className="text-sm text-gray-500">How filters will appear on the shop page</p>
              </CardHeader>
              <CardContent>
                <div className="bg-gray-50 rounded-lg p-4 border max-w-[280px]">
                  {/* Preview Header */}
                  <div className="flex items-center justify-between mb-4 pb-2 border-b">
                    <h3 className="font-semibold flex items-center gap-2 text-sm">
                      <Filter className="w-4 h-4" />
                      Filters
                    </h3>
                    <button className="text-xs text-gray-500 hover:text-gray-700">Clear all</button>
                  </div>
                  
                  {/* Preview Filter Sections */}
                  {filters.filter(f => f.is_active).slice(0, 5).map((filter) => (
                    <div key={filter.id} className="mb-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-sm">{filter.name}</span>
                        <ChevronDown className="w-4 h-4 text-gray-400" />
                      </div>
                      
                      {filter.input_type === 'checkbox' && (
                        <div className="space-y-2 pl-1">
                          {(filter.values || []).slice(0, 4).map((val, i) => (
                            <div key={i} className="flex items-center gap-2">
                              <Checkbox id={`preview-${filter.slug}-${i}`} disabled />
                              <Label htmlFor={`preview-${filter.slug}-${i}`} className="text-sm text-gray-600 cursor-pointer">
                                {val.label || val.name || val.value}
                              </Label>
                            </div>
                          ))}
                          {(filter.values || []).length > 4 && (
                            <p className="text-xs text-blue-600 pl-5">+{filter.values.length - 4} more</p>
                          )}
                        </div>
                      )}
                      
                      {filter.input_type === 'range' && (
                        <div className="px-2 py-2">
                          <Slider defaultValue={[0, 100]} max={100} step={1} disabled className="mb-2" />
                          <div className="flex justify-between text-xs text-gray-500">
                            <span>£0/m²</span>
                            <span>£100/m²</span>
                          </div>
                        </div>
                      )}
                      
                      {filter.input_type === 'toggle' && (
                        <div className="flex items-center gap-2 pl-1">
                          <Checkbox disabled />
                          <Label className="text-sm text-gray-600">{filter.description || 'Enable'}</Label>
                        </div>
                      )}
                      
                      {filter.input_type === 'dropdown' && (
                        <select className="w-full text-sm border rounded p-2 bg-white" disabled>
                          <option>All {filter.name}</option>
                          {(filter.values || []).slice(0, 3).map((val, i) => (
                            <option key={i}>{val.label || val.name || val.value}</option>
                          ))}
                        </select>
                      )}
                    </div>
                  ))}
                  
                  {filters.filter(f => f.is_active).length === 0 && (
                    <p className="text-gray-400 text-sm text-center py-4">No active filters to preview</p>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Shop Page Mockup */}
            <Card>
              <CardHeader className="py-4">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Eye className="w-5 h-5" />
                  Shop Page Layout
                </CardTitle>
                <p className="text-sm text-gray-500">How the filter sidebar appears in context</p>
              </CardHeader>
              <CardContent>
                <div className="border rounded-lg overflow-hidden bg-white">
                  {/* Mockup Header */}
                  <div className="bg-gray-900 text-white p-3 text-center text-sm font-medium">
                    TILE STATION
                  </div>
                  
                  {/* Mockup Navigation */}
                  <div className="border-b p-2 flex gap-4 text-xs text-gray-600 justify-center">
                    <span className="border-b-2 border-gray-900 pb-1">ALL</span>
                    <span>WALL TILES</span>
                    <span>FLOOR TILES</span>
                    <span>OUTDOOR</span>
                  </div>
                  
                  {/* Mockup Content */}
                  <div className="flex p-3 gap-3" style={{ minHeight: '200px' }}>
                    {/* Filter Sidebar */}
                    <div className="w-1/4 bg-gray-50 rounded p-2 text-xs">
                      <div className="font-semibold mb-2 flex items-center gap-1">
                        <Filter className="w-3 h-3" />
                        Filters
                      </div>
                      {filters.filter(f => f.is_active).slice(0, 3).map((f) => (
                        <div key={f.id} className="mb-2">
                          <div className="font-medium text-gray-700">{f.name}</div>
                          <div className="text-gray-400 text-[10px]">
                            {(f.values || []).slice(0, 2).map(v => v.label || v.value).join(', ')}
                            {(f.values || []).length > 2 && '...'}
                          </div>
                        </div>
                      ))}
                    </div>
                    
                    {/* Product Grid */}
                    <div className="flex-1">
                      <div className="grid grid-cols-3 gap-2">
                        {[1,2,3,4,5,6].map((i) => (
                          <div key={i} className="bg-gray-100 rounded aspect-square flex items-center justify-center">
                            <div className="text-gray-300 text-[10px]">Product</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
                
                <p className="text-xs text-gray-400 mt-3 text-center">
                  * This is a simplified preview. Visit the actual shop page to see the full experience.
                </p>
              </CardContent>
            </Card>
          </div>
          
          {/* Filter Statistics */}
          <Card className="mt-6">
            <CardHeader className="py-4">
              <CardTitle className="text-lg">Filter Statistics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 bg-blue-50 rounded-lg">
                  <div className="text-3xl font-bold text-blue-600">{filters.length}</div>
                  <div className="text-sm text-gray-600">Total Filters</div>
                </div>
                <div className="text-center p-4 bg-green-50 rounded-lg">
                  <div className="text-3xl font-bold text-green-600">{filters.filter(f => f.is_active).length}</div>
                  <div className="text-sm text-gray-600">Active Filters</div>
                </div>
                <div className="text-center p-4 bg-purple-50 rounded-lg">
                  <div className="text-3xl font-bold text-purple-600">{filterGroups.length}</div>
                  <div className="text-sm text-gray-600">Filter Groups</div>
                </div>
                <div className="text-center p-4 bg-orange-50 rounded-lg">
                  <div className="text-3xl font-bold text-orange-600">
                    {filters.reduce((acc, f) => acc + (f.values?.length || 0), 0)}
                  </div>
                  <div className="text-sm text-gray-600">Total Options</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Group Dialog */}
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
                  onChange={(e) => setGroupForm({ 
                    ...groupForm, 
                    name: e.target.value,
                    slug: editingGroup ? groupForm.slug : generateSlug(e.target.value)
                  })}
                  placeholder="e.g., Tiles, Adhesives"
                />
              </div>
              <div>
                <Label>Slug</Label>
                <Input 
                  value={groupForm.slug}
                  onChange={(e) => setGroupForm({ ...groupForm, slug: e.target.value })}
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
              <Label>Applies to Categories</Label>
              <div className="flex flex-wrap gap-1 mt-1 p-2 border rounded min-h-[50px]">
                {categories.map(cat => {
                  const isSelected = groupForm.category_slugs?.includes(cat.slug);
                  return (
                    <Badge 
                      key={cat.slug}
                      variant={isSelected ? "default" : "outline"}
                      className="cursor-pointer text-xs"
                      onClick={() => setGroupForm({
                        ...groupForm,
                        category_slugs: isSelected
                          ? groupForm.category_slugs.filter(s => s !== cat.slug)
                          : [...(groupForm.category_slugs || []), cat.slug]
                      })}
                    >
                      {cat.name}
                    </Badge>
                  );
                })}
              </div>
              <p className="text-xs text-gray-400 mt-1">Leave empty to apply to all</p>
            </div>
            
            <div>
              <Label>Filters in this Group</Label>
              <div className="flex flex-wrap gap-1 mt-1 p-2 border rounded min-h-[50px]">
                {filters.map(filter => {
                  const isSelected = groupForm.filter_ids?.includes(filter.id);
                  return (
                    <Badge 
                      key={filter.id}
                      variant={isSelected ? "default" : "outline"}
                      className="cursor-pointer text-xs"
                      onClick={() => setGroupForm({
                        ...groupForm,
                        filter_ids: isSelected
                          ? groupForm.filter_ids.filter(id => id !== filter.id)
                          : [...(groupForm.filter_ids || []), filter.id]
                      })}
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
            <Button onClick={handleSaveGroup}><Save className="w-4 h-4 mr-2" />Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default WebsiteFiltersManager;
