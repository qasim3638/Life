import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, Edit2, Trash2, GripVertical, Save, X, Link2, ChevronDown, ChevronRight, Eye, EyeOff, Star } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Switch } from '../../components/ui/switch';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const NavigationMenuEditor = () => {
  const [searchParams] = useSearchParams();
  const menuType = searchParams.get('type') || 'main';
  
  const [menuItems, setMenuItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [draggedItem, setDraggedItem] = useState(null);

  const menuTypeLabels = {
    main: 'Main Navigation',
    shop: 'Shop Page Navigation',
    footer: 'Footer Navigation'
  };

  const emptyForm = {
    label: '',
    link_type: 'custom',
    link_url: '',
    category_id: null,
    page_slug: '',
    is_active: true,
    highlight: false,
    highlight_color: '#ef4444',
    children: []
  };

  const [formData, setFormData] = useState(emptyForm);

  useEffect(() => {
    fetchMenu();
    fetchCategories();
  }, [menuType]);

  const fetchMenu = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/navigation/${menuType}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      setMenuItems(data || []);
    } catch (e) {
      toast.error('Failed to load navigation menu');
    } finally {
      setLoading(false);
    }
  };

  const fetchCategories = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/categories`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      setCategories(data || []);
    } catch (e) {
      console.error('Failed to load categories');
    }
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSaveMenu = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/navigation/${menuType}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(menuItems)
      });

      if (!res.ok) throw new Error('Failed to save');

      toast.success(`${menuTypeLabels[menuType] || 'Navigation'} saved!`);
    } catch (e) {
      toast.error('Failed to save menu');
    } finally {
      setSaving(false);
    }
  };

  const handleAddItem = () => {
    if (!formData.label) {
      toast.error('Label is required');
      return;
    }

    const newItem = {
      ...formData,
      id: Date.now().toString(),
      display_order: menuItems.length
    };

    // Build link URL based on type
    if (formData.link_type === 'category' && formData.category_id) {
      const cat = categories.find(c => c.id === formData.category_id);
      newItem.link_url = `/tiles?category=${cat?.slug || formData.category_id}`;
    } else if (formData.link_type === 'page' && formData.page_slug) {
      newItem.link_url = `/${formData.page_slug}`;
    }

    if (editingItem) {
      setMenuItems(prev => prev.map(item => 
        item.id === editingItem.id ? { ...newItem, id: editingItem.id } : item
      ));
    } else {
      setMenuItems(prev => [...prev, newItem]);
    }

    setShowForm(false);
    setEditingItem(null);
    setFormData(emptyForm);
  };

  const handleEditItem = (item) => {
    setEditingItem(item);
    setFormData({
      label: item.label || '',
      link_type: item.link_type || 'custom',
      link_url: item.link_url || '',
      category_id: item.category_id || null,
      page_slug: item.page_slug || '',
      is_active: item.is_active !== false,
      highlight: item.highlight || false,
      highlight_color: item.highlight_color || '#ef4444',
      children: item.children || []
    });
    setShowForm(true);
  };

  const handleDeleteItem = (itemId) => {
    if (!window.confirm('Delete this menu item?')) return;
    setMenuItems(prev => prev.filter(item => item.id !== itemId));
  };

  const handleToggleActive = (itemId) => {
    setMenuItems(prev => prev.map(item =>
      item.id === itemId ? { ...item, is_active: !item.is_active } : item
    ));
  };

  const handleDragStart = (e, item) => {
    setDraggedItem(item);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e, item) => {
    e.preventDefault();
    if (!draggedItem || draggedItem.id === item.id) return;
    
    const items = [...menuItems];
    const draggedIndex = items.findIndex(i => i.id === draggedItem.id);
    const targetIndex = items.findIndex(i => i.id === item.id);
    
    items.splice(draggedIndex, 1);
    items.splice(targetIndex, 0, draggedItem);
    
    // Update display orders
    items.forEach((item, index) => {
      item.display_order = index;
    });
    
    setMenuItems(items);
  };

  const handleDragEnd = () => {
    setDraggedItem(null);
  };

  // Predefined page options
  const pageOptions = [
    { slug: 'shop/sample-service', label: 'Sample Service' },
    { slug: 'shop/contact', label: 'Contact & Stores' },
    { slug: 'shop/tile-login', label: 'Login Page' },
    { slug: 'shop/tile-register', label: 'Register Page' },
    { slug: 'tiles', label: 'Homepage' }
  ];

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-spin w-8 h-8 border-4 border-gray-400 border-t-transparent rounded-full mx-auto"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <div className="bg-white shadow-sm border-b sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">{menuTypeLabels[menuType] || 'Navigation Menu'}</h1>
            <p className="text-sm text-gray-500">
              {menuType === 'shop' 
                ? 'Customize the tabs shown on the shop/collections page' 
                : "Customize your website's main navigation"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => window.open(menuType === 'shop' ? '/tiles' : '/tiles', '_blank')}>
              <Eye className="h-4 w-4 mr-2" />
              Preview
            </Button>
            <Button onClick={handleSaveMenu} disabled={saving} className="bg-amber-500 hover:bg-amber-600">
              <Save className="h-4 w-4 mr-2" />
              {saving ? 'Saving...' : 'Save Menu'}
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Menu Items List */}
          <div className={`${showForm ? 'lg:col-span-2' : 'lg:col-span-3'}`}>
            <div className="bg-white rounded-lg shadow-sm">
              <div className="p-4 border-b flex items-center justify-between">
                <span className="font-medium">{menuItems.length} Menu Items</span>
                <Button size="sm" onClick={() => { setShowForm(true); setEditingItem(null); setFormData(emptyForm); }}>
                  <Plus className="h-4 w-4 mr-1" />
                  Add Item
                </Button>
              </div>

              {/* Preview Bar */}
              <div className="bg-[#333333] p-3 overflow-x-auto">
                <div className="flex items-center gap-4 min-w-max">
                  {menuItems.filter(item => item.is_active).map(item => (
                    <span 
                      key={item.id}
                      className={`text-sm font-medium whitespace-nowrap ${
                        item.highlight 
                          ? 'text-red-400' 
                          : 'text-gray-300'
                      }`}
                      style={item.highlight && item.highlight_color ? { color: item.highlight_color } : {}}
                    >
                      {item.label}
                    </span>
                  ))}
                </div>
              </div>

              {/* Drag and Drop List */}
              <div className="divide-y">
                {menuItems.length === 0 ? (
                  <div className="p-8 text-center text-gray-500">
                    <Link2 className="h-12 w-12 mx-auto text-gray-300 mb-3" />
                    <p>No menu items yet. Add your first item!</p>
                  </div>
                ) : (
                  menuItems.map((item, index) => (
                    <div
                      key={item.id}
                      draggable
                      onDragStart={(e) => handleDragStart(e, item)}
                      onDragOver={(e) => handleDragOver(e, item)}
                      onDragEnd={handleDragEnd}
                      className={`flex items-center gap-3 p-4 hover:bg-gray-50 cursor-move ${
                        draggedItem?.id === item.id ? 'opacity-50 bg-gray-100' : ''
                      } ${!item.is_active ? 'opacity-60' : ''}`}
                    >
                      <GripVertical className="h-5 w-5 text-gray-400 flex-shrink-0" />
                      
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{item.label}</span>
                          {item.highlight && (
                            <Star className="h-4 w-4 text-red-500 fill-current" />
                          )}
                        </div>
                        <div className="text-sm text-gray-500 truncate">
                          {item.link_url || 'No link'}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 text-xs rounded ${
                          item.link_type === 'category' ? 'bg-blue-100 text-blue-700' :
                          item.link_type === 'page' ? 'bg-purple-100 text-purple-700' :
                          'bg-gray-100 text-gray-600'
                        }`}>
                          {item.link_type}
                        </span>
                        
                        <button
                          onClick={() => handleToggleActive(item.id)}
                          className={`p-1.5 rounded ${item.is_active ? 'text-green-500' : 'text-gray-300'}`}
                        >
                          {item.is_active ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                        </button>
                        
                        <Button variant="ghost" size="sm" onClick={() => handleEditItem(item)}>
                          <Edit2 className="h-4 w-4" />
                        </Button>
                        
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          onClick={() => handleDeleteItem(item.id)}
                          className="text-red-500 hover:text-red-700"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="p-4 border-t bg-gray-50 text-sm text-gray-500">
                Drag items to reorder. Changes are saved when you click "Save Menu".
              </div>
            </div>
          </div>

          {/* Form Panel */}
          {showForm && (
            <div className="lg:col-span-1">
              <div className="bg-white rounded-lg shadow-sm sticky top-24">
                <div className="p-4 border-b flex items-center justify-between">
                  <span className="font-medium">{editingItem ? 'Edit Item' : 'Add Item'}</span>
                  <Button variant="ghost" size="sm" onClick={() => { setShowForm(false); setEditingItem(null); }}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>

                <div className="p-4 space-y-4">
                  <div>
                    <Label>Label *</Label>
                    <Input
                      value={formData.label}
                      onChange={(e) => handleInputChange('label', e.target.value)}
                      placeholder="e.g., WALL TILES"
                    />
                  </div>

                  <div>
                    <Label>Link Type</Label>
                    <select
                      value={formData.link_type}
                      onChange={(e) => handleInputChange('link_type', e.target.value)}
                      className="w-full border rounded-md p-2"
                    >
                      <option value="custom">Custom URL</option>
                      <option value="category">Category</option>
                      <option value="page">Page</option>
                    </select>
                  </div>

                  {formData.link_type === 'custom' && (
                    <div>
                      <Label>URL</Label>
                      <Input
                        value={formData.link_url}
                        onChange={(e) => handleInputChange('link_url', e.target.value)}
                        placeholder="/tiles?finish=matt"
                      />
                    </div>
                  )}

                  {formData.link_type === 'category' && (
                    <div>
                      <Label>Select Category</Label>
                      <select
                        value={formData.category_id || ''}
                        onChange={(e) => handleInputChange('category_id', e.target.value)}
                        className="w-full border rounded-md p-2"
                      >
                        <option value="">Select a category</option>
                        {categories.map(cat => (
                          <option key={cat.id} value={cat.id}>{cat.name}</option>
                        ))}
                      </select>
                      {categories.length === 0 && (
                        <p className="text-xs text-gray-500 mt-1">No categories available. Create categories first.</p>
                      )}
                    </div>
                  )}

                  {formData.link_type === 'page' && (
                    <div>
                      <Label>Select Page</Label>
                      <select
                        value={formData.page_slug || ''}
                        onChange={(e) => handleInputChange('page_slug', e.target.value)}
                        className="w-full border rounded-md p-2"
                      >
                        <option value="">Select a page</option>
                        {pageOptions.map(page => (
                          <option key={page.slug} value={page.slug}>{page.label}</option>
                        ))}
                      </select>
                    </div>
                  )}

                  <div className="flex items-center justify-between">
                    <Label>Active</Label>
                    <Switch
                      checked={formData.is_active}
                      onCheckedChange={(v) => handleInputChange('is_active', v)}
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <Label>Highlight (e.g., SALE)</Label>
                    <Switch
                      checked={formData.highlight}
                      onCheckedChange={(v) => handleInputChange('highlight', v)}
                    />
                  </div>

                  {formData.highlight && (
                    <div>
                      <Label>Highlight Color</Label>
                      <div className="flex gap-2 mt-1">
                        <Input
                          value={formData.highlight_color}
                          onChange={(e) => handleInputChange('highlight_color', e.target.value)}
                          placeholder="#ef4444"
                          className="flex-1"
                        />
                        <input
                          type="color"
                          value={formData.highlight_color}
                          onChange={(e) => handleInputChange('highlight_color', e.target.value)}
                          className="w-10 h-10 rounded cursor-pointer"
                        />
                      </div>
                    </div>
                  )}

                  <div className="flex gap-2 pt-4">
                    <Button 
                      type="button" 
                      variant="outline" 
                      className="flex-1" 
                      onClick={() => { setShowForm(false); setEditingItem(null); }}
                    >
                      Cancel
                    </Button>
                    <Button 
                      onClick={handleAddItem}
                      className="flex-1 bg-amber-500 hover:bg-amber-600"
                    >
                      {editingItem ? 'Update' : 'Add'}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Quick Add Common Items */}
        <div className="mt-6 bg-white rounded-lg shadow-sm p-4">
          <h3 className="font-medium mb-3">Quick Add Common Items</h3>
          <div className="flex flex-wrap gap-2">
            {[
              { label: 'NEW COLLECTION', url: '/tiles?collection=new' },
              { label: 'ALL TILES', url: '/tiles' },
              { label: 'WALL TILES', url: '/tiles?type=wall' },
              { label: 'FLOOR TILES', url: '/tiles?type=floor' },
              { label: 'POLISHED', url: '/tiles?finish=polished' },
              { label: 'MATT', url: '/tiles?finish=matt' },
              { label: 'OUTDOOR', url: '/tiles?usage=outdoor' },
              { label: 'BATHROOM', url: '/tiles?room=bathroom' },
              { label: 'KITCHEN', url: '/tiles?room=kitchen' },
              { label: 'SALE', url: '/tiles?sale=true', highlight: true }
            ].filter(item => !menuItems.find(m => m.label === item.label)).map(item => (
              <Button
                key={item.label}
                variant="outline"
                size="sm"
                onClick={() => {
                  const newItem = {
                    id: Date.now().toString(),
                    label: item.label,
                    link_type: 'custom',
                    link_url: item.url,
                    is_active: true,
                    highlight: item.highlight || false,
                    highlight_color: item.highlight ? '#ef4444' : null,
                    display_order: menuItems.length,
                    children: []
                  };
                  setMenuItems(prev => [...prev, newItem]);
                }}
              >
                <Plus className="h-3 w-3 mr-1" />
                {item.label}
              </Button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default NavigationMenuEditor;
