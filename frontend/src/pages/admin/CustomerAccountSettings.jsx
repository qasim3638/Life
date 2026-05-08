import React, { useState, useEffect } from 'react';
import { 
  Save, Plus, Trash2, Edit2, RefreshCw, Eye,
  ShoppingBag, Heart, Truck, CheckCircle2, User, Building2,
  Loader2, Package, MapPin, Gift
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Default settings
const DEFAULT_SETTINGS = {
  // Registration page settings
  registration: {
    headline: 'Create Your Account',
    subheadline: 'Join Tile Station for a better shopping experience',
    show_trade_cta: true,
    trade_cta_title: 'Are you a Trade Professional?',
    trade_cta_description: 'Get exclusive discounts & credit back rewards',
    trade_cta_button: 'Open Trade Account',
  },
  // Benefits shown on registration page
  registration_benefits: [
    { id: '1', icon: 'ShoppingBag', text: 'Track your orders easily', enabled: true },
    { id: '2', icon: 'Heart', text: 'Save items to your wishlist', enabled: true },
    { id: '3', icon: 'Truck', text: 'Faster checkout experience', enabled: true },
    { id: '4', icon: 'CheckCircle2', text: 'Exclusive member offers', enabled: true },
  ],
  // Account portal settings
  portal: {
    welcome_message: 'Welcome back, {name}!',
    welcome_subtext: 'Manage your account, track orders, and save your favourites.',
    show_trade_upgrade: true,
    trade_upgrade_title: 'Trade Professional?',
    trade_upgrade_text: 'Get exclusive discounts & credit back rewards',
    trade_upgrade_button: 'Open Trade Account',
  },
  // Dashboard stats and quick actions
  dashboard: {
    stats: [
      { id: 'orders', label: 'Total Orders', icon: 'ShoppingBag', color: 'blue', enabled: true },
      { id: 'wishlist', label: 'Wishlist Items', icon: 'Heart', color: 'pink', enabled: true },
      { id: 'addresses', label: 'Saved Addresses', icon: 'MapPin', color: 'green', enabled: true },
    ],
    quick_actions: [
      { id: 'shop', title: 'Browse Tiles', description: 'Explore our collections', link: '/tiles', enabled: true },
      { id: 'samples', title: 'Order Samples', description: 'Try before you buy', link: '/shop/sample-service', enabled: true },
    ],
    sidebar_tabs: [
      { id: 'overview', label: 'Overview', enabled: true },
      { id: 'orders', label: 'Orders', enabled: true },
      { id: 'wishlist', label: 'Wishlist', enabled: true },
      { id: 'settings', label: 'Settings', enabled: true },
    ]
  }
};

const ICON_OPTIONS = [
  { value: 'ShoppingBag', label: 'Shopping Bag', icon: ShoppingBag },
  { value: 'Heart', label: 'Heart', icon: Heart },
  { value: 'Truck', label: 'Truck', icon: Truck },
  { value: 'CheckCircle2', label: 'Check', icon: CheckCircle2 },
  { value: 'Package', label: 'Package', icon: Package },
  { value: 'MapPin', label: 'Location', icon: MapPin },
  { value: 'Gift', label: 'Gift', icon: Gift },
  { value: 'User', label: 'User', icon: User },
];

const getIconComponent = (iconName) => {
  const found = ICON_OPTIONS.find(i => i.value === iconName);
  return found ? found.icon : ShoppingBag;
};

const CustomerAccountSettings = () => {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('registration');

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/customer-account-settings`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (res.ok) {
        const data = await res.json();
        if (data.settings && Object.keys(data.settings).length > 0) {
          setSettings({ ...DEFAULT_SETTINGS, ...data.settings });
        }
      }
    } catch (error) {
      console.error('Error fetching settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/customer-account-settings`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}` 
        },
        body: JSON.stringify({ settings })
      });
      
      if (res.ok) {
        toast.success('Settings saved successfully!');
      } else {
        throw new Error('Failed to save');
      }
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const updateRegistration = (field, value) => {
    setSettings(prev => ({
      ...prev,
      registration: { ...prev.registration, [field]: value }
    }));
  };

  const updatePortal = (field, value) => {
    setSettings(prev => ({
      ...prev,
      portal: { ...prev.portal, [field]: value }
    }));
  };

  const updateBenefit = (id, field, value) => {
    setSettings(prev => ({
      ...prev,
      registration_benefits: prev.registration_benefits.map(b => 
        b.id === id ? { ...b, [field]: value } : b
      )
    }));
  };

  const addBenefit = () => {
    const newBenefit = {
      id: `benefit_${Date.now()}`,
      icon: 'ShoppingBag',
      text: 'New benefit',
      enabled: true
    };
    setSettings(prev => ({
      ...prev,
      registration_benefits: [...prev.registration_benefits, newBenefit]
    }));
  };

  const deleteBenefit = (id) => {
    if (!window.confirm('Delete this benefit?')) return;
    setSettings(prev => ({
      ...prev,
      registration_benefits: prev.registration_benefits.filter(b => b.id !== id)
    }));
  };

  const tabs = [
    { id: 'registration', label: 'Registration Page' },
    { id: 'portal', label: 'Account Portal' },
    { id: 'dashboard', label: 'Dashboard Content' },
    { id: 'preview', label: 'Preview' },
  ];

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Customer Account Settings</h1>
          <p className="text-gray-500">Manage registration page and customer account portal</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchSettings}>
            <RefreshCw className="w-4 h-4 mr-1" /> Refresh
          </Button>
          <Button 
            onClick={handleSave} 
            disabled={saving}
            className="bg-amber-500 hover:bg-amber-600"
          >
            {saving ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Save className="w-4 h-4 mr-1" />}
            Save Changes
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-amber-500 text-amber-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Registration Page Settings */}
      {activeTab === 'registration' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-6">Registration Page Content</h2>
            
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <Label>Page Headline</Label>
                <Input
                  value={settings.registration.headline}
                  onChange={(e) => updateRegistration('headline', e.target.value)}
                  placeholder="Create Your Account"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>Subheadline</Label>
                <Input
                  value={settings.registration.subheadline}
                  onChange={(e) => updateRegistration('subheadline', e.target.value)}
                  placeholder="Join Tile Station for a better shopping experience"
                  className="mt-1"
                />
              </div>
            </div>
          </div>

          {/* Benefits */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-gray-900">Registration Benefits</h3>
              <Button onClick={addBenefit} size="sm" className="bg-amber-500 hover:bg-amber-600">
                <Plus className="w-4 h-4 mr-1" /> Add
              </Button>
            </div>
            <div className="space-y-3">
              {settings.registration_benefits.map(benefit => {
                const IconComponent = getIconComponent(benefit.icon);
                return (
                  <div key={benefit.id} className="flex items-center gap-3 p-3 border rounded-lg">
                    <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                      <IconComponent className="w-5 h-5 text-gray-600" />
                    </div>
                    <select
                      value={benefit.icon}
                      onChange={(e) => updateBenefit(benefit.id, 'icon', e.target.value)}
                      className="w-32 px-2 py-1 border rounded text-sm"
                    >
                      {ICON_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                    <Input
                      value={benefit.text}
                      onChange={(e) => updateBenefit(benefit.id, 'text', e.target.value)}
                      className="flex-1"
                    />
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={benefit.enabled}
                        onChange={(e) => updateBenefit(benefit.id, 'enabled', e.target.checked)}
                        className="w-4 h-4 text-amber-500 rounded"
                      />
                      <span className="text-sm text-gray-500">Show</span>
                    </label>
                    <Button variant="ghost" size="sm" className="text-red-600" onClick={() => deleteBenefit(benefit.id)}>
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Trade CTA */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-gray-900">Trade Account CTA (Sidebar)</h3>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={settings.registration.show_trade_cta}
                  onChange={(e) => updateRegistration('show_trade_cta', e.target.checked)}
                  className="w-4 h-4 text-amber-500 rounded"
                />
                <span className="text-sm">Show Trade CTA</span>
              </label>
            </div>
            {settings.registration.show_trade_cta && (
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label>Title</Label>
                  <Input
                    value={settings.registration.trade_cta_title}
                    onChange={(e) => updateRegistration('trade_cta_title', e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Button Text</Label>
                  <Input
                    value={settings.registration.trade_cta_button}
                    onChange={(e) => updateRegistration('trade_cta_button', e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div className="md:col-span-2">
                  <Label>Description</Label>
                  <Input
                    value={settings.registration.trade_cta_description}
                    onChange={(e) => updateRegistration('trade_cta_description', e.target.value)}
                    className="mt-1"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Account Portal Settings */}
      {activeTab === 'portal' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-6">Account Portal Content</h2>
            
            <div className="space-y-4">
              <div>
                <Label>Welcome Message</Label>
                <Input
                  value={settings.portal.welcome_message}
                  onChange={(e) => updatePortal('welcome_message', e.target.value)}
                  placeholder="Welcome back, {name}!"
                  className="mt-1"
                />
                <p className="text-xs text-gray-500 mt-1">Use {'{name}'} to show customer's first name</p>
              </div>
              <div>
                <Label>Welcome Subtext</Label>
                <Input
                  value={settings.portal.welcome_subtext}
                  onChange={(e) => updatePortal('welcome_subtext', e.target.value)}
                  className="mt-1"
                />
              </div>
            </div>
          </div>

          {/* Trade Upgrade CTA */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-gray-900">Trade Upgrade CTA (Sidebar)</h3>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={settings.portal.show_trade_upgrade}
                  onChange={(e) => updatePortal('show_trade_upgrade', e.target.checked)}
                  className="w-4 h-4 text-amber-500 rounded"
                />
                <span className="text-sm">Show Trade Upgrade CTA</span>
              </label>
            </div>
            {settings.portal.show_trade_upgrade && (
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label>Title</Label>
                  <Input
                    value={settings.portal.trade_upgrade_title}
                    onChange={(e) => updatePortal('trade_upgrade_title', e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Button Text</Label>
                  <Input
                    value={settings.portal.trade_upgrade_button}
                    onChange={(e) => updatePortal('trade_upgrade_button', e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div className="md:col-span-2">
                  <Label>Description</Label>
                  <Input
                    value={settings.portal.trade_upgrade_text}
                    onChange={(e) => updatePortal('trade_upgrade_text', e.target.value)}
                    className="mt-1"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Dashboard Content Tab */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          {/* Stats Cards */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Dashboard Stats Cards</h2>
            <p className="text-sm text-gray-500 mb-4">Configure which stats appear on the customer account dashboard</p>
            <div className="space-y-3">
              {settings.dashboard?.stats?.map((stat, idx) => (
                <div key={stat.id} className="flex items-center gap-4 p-3 border rounded-lg">
                  <div className={`w-10 h-10 bg-${stat.color}-100 rounded-lg flex items-center justify-center`}>
                    <span className="text-sm font-bold">{idx + 1}</span>
                  </div>
                  <Input
                    value={stat.label}
                    onChange={(e) => {
                      const newStats = [...(settings.dashboard?.stats || [])];
                      newStats[idx] = { ...stat, label: e.target.value };
                      setSettings(prev => ({
                        ...prev,
                        dashboard: { ...prev.dashboard, stats: newStats }
                      }));
                    }}
                    className="flex-1"
                    placeholder="Stat label"
                  />
                  <select
                    value={stat.color}
                    onChange={(e) => {
                      const newStats = [...(settings.dashboard?.stats || [])];
                      newStats[idx] = { ...stat, color: e.target.value };
                      setSettings(prev => ({
                        ...prev,
                        dashboard: { ...prev.dashboard, stats: newStats }
                      }));
                    }}
                    className="px-3 py-2 border rounded-md"
                  >
                    <option value="blue">Blue</option>
                    <option value="pink">Pink</option>
                    <option value="green">Green</option>
                    <option value="purple">Purple</option>
                    <option value="amber">Amber</option>
                  </select>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={stat.enabled}
                      onChange={(e) => {
                        const newStats = [...(settings.dashboard?.stats || [])];
                        newStats[idx] = { ...stat, enabled: e.target.checked };
                        setSettings(prev => ({
                          ...prev,
                          dashboard: { ...prev.dashboard, stats: newStats }
                        }));
                      }}
                      className="w-4 h-4 text-amber-500 rounded"
                    />
                    <span className="text-sm">Show</span>
                  </label>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Quick Action Buttons</h2>
            <div className="space-y-3">
              {settings.dashboard?.quick_actions?.map((action, idx) => (
                <div key={action.id} className="p-4 border rounded-lg space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label>Title</Label>
                      <Input
                        value={action.title}
                        onChange={(e) => {
                          const newActions = [...(settings.dashboard?.quick_actions || [])];
                          newActions[idx] = { ...action, title: e.target.value };
                          setSettings(prev => ({
                            ...prev,
                            dashboard: { ...prev.dashboard, quick_actions: newActions }
                          }));
                        }}
                        className="mt-1"
                      />
                    </div>
                    <div>
                      <Label>Link</Label>
                      <Input
                        value={action.link}
                        onChange={(e) => {
                          const newActions = [...(settings.dashboard?.quick_actions || [])];
                          newActions[idx] = { ...action, link: e.target.value };
                          setSettings(prev => ({
                            ...prev,
                            dashboard: { ...prev.dashboard, quick_actions: newActions }
                          }));
                        }}
                        className="mt-1"
                      />
                    </div>
                  </div>
                  <div className="flex gap-3 items-end">
                    <div className="flex-1">
                      <Label>Description</Label>
                      <Input
                        value={action.description}
                        onChange={(e) => {
                          const newActions = [...(settings.dashboard?.quick_actions || [])];
                          newActions[idx] = { ...action, description: e.target.value };
                          setSettings(prev => ({
                            ...prev,
                            dashboard: { ...prev.dashboard, quick_actions: newActions }
                          }));
                        }}
                        className="mt-1"
                      />
                    </div>
                    <label className="flex items-center gap-2 pb-2">
                      <input
                        type="checkbox"
                        checked={action.enabled}
                        onChange={(e) => {
                          const newActions = [...(settings.dashboard?.quick_actions || [])];
                          newActions[idx] = { ...action, enabled: e.target.checked };
                          setSettings(prev => ({
                            ...prev,
                            dashboard: { ...prev.dashboard, quick_actions: newActions }
                          }));
                        }}
                        className="w-4 h-4 text-amber-500 rounded"
                      />
                      <span className="text-sm">Show</span>
                    </label>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Sidebar Tabs */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Sidebar Navigation Tabs</h2>
            <p className="text-sm text-gray-500 mb-4">Enable or disable sections in the account sidebar</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {settings.dashboard?.sidebar_tabs?.map((tab, idx) => (
                <div key={tab.id} className="flex items-center gap-3 p-3 border rounded-lg">
                  <input
                    type="checkbox"
                    checked={tab.enabled}
                    onChange={(e) => {
                      const newTabs = [...(settings.dashboard?.sidebar_tabs || [])];
                      newTabs[idx] = { ...tab, enabled: e.target.checked };
                      setSettings(prev => ({
                        ...prev,
                        dashboard: { ...prev.dashboard, sidebar_tabs: newTabs }
                      }));
                    }}
                    className="w-4 h-4 text-amber-500 rounded"
                  />
                  <Input
                    value={tab.label}
                    onChange={(e) => {
                      const newTabs = [...(settings.dashboard?.sidebar_tabs || [])];
                      newTabs[idx] = { ...tab, label: e.target.value };
                      setSettings(prev => ({
                        ...prev,
                        dashboard: { ...prev.dashboard, sidebar_tabs: newTabs }
                      }));
                    }}
                    className="flex-1"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Preview Tab */}
      {activeTab === 'preview' && (
        <div className="space-y-6">
          {/* Quick Links */}
          <div className="flex gap-4 mb-4">
            <a 
              href="/shop/register" 
              target="_blank" 
              rel="noopener noreferrer"
              className="flex items-center gap-2 bg-amber-500 text-white px-4 py-2 rounded-lg hover:bg-amber-600"
            >
              <Eye className="w-4 h-4" /> View Registration Page
            </a>
            <a 
              href="/shop/account" 
              target="_blank" 
              rel="noopener noreferrer"
              className="flex items-center gap-2 bg-gray-700 text-white px-4 py-2 rounded-lg hover:bg-gray-800"
            >
              <Eye className="w-4 h-4" /> View Account Portal
            </a>
          </div>

          {/* Registration Preview */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="font-bold text-gray-900 mb-4">Registration Page Preview</h3>
            <div className="grid md:grid-cols-5 gap-6">
              {/* Form Side */}
              <div className="md:col-span-3 bg-white border rounded-xl p-6">
                <div className="text-center mb-6">
                  <h1 className="text-2xl font-bold text-gray-900">{settings.registration.headline}</h1>
                  <p className="text-gray-500 mt-1">{settings.registration.subheadline}</p>
                </div>
                <div className="space-y-4">
                  <div className="bg-gray-100 h-10 rounded-lg"></div>
                  <div className="bg-gray-100 h-10 rounded-lg"></div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-gray-100 h-10 rounded-lg"></div>
                    <div className="bg-gray-100 h-10 rounded-lg"></div>
                  </div>
                  <div className="bg-[#333] text-[#F7EA1C] text-center py-3 rounded-lg font-semibold">
                    Create Account
                  </div>
                </div>
              </div>
              
              {/* Benefits Sidebar */}
              <div className="md:col-span-2 bg-[#333333] text-white rounded-xl p-6">
                <h2 className="text-lg font-bold mb-4">Why Create an Account?</h2>
                <div className="space-y-3 mb-6">
                  {settings.registration_benefits.filter(b => b.enabled).map(benefit => {
                    const IconComponent = getIconComponent(benefit.icon);
                    return (
                      <div key={benefit.id} className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-[#F7EA1C]/10 rounded-lg flex items-center justify-center">
                          <IconComponent className="w-5 h-5 text-[#F7EA1C]" />
                        </div>
                        <span className="text-gray-200 text-sm">{benefit.text}</span>
                      </div>
                    );
                  })}
                </div>
                {settings.registration.show_trade_cta && (
                  <div className="border-t border-gray-700 pt-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Building2 className="w-5 h-5 text-[#F7EA1C]" />
                      <span className="font-semibold text-sm">{settings.registration.trade_cta_title}</span>
                    </div>
                    <p className="text-xs text-gray-400 mb-3">{settings.registration.trade_cta_description}</p>
                    <div className="bg-[#F7EA1C] text-[#333] text-center py-2 rounded-lg text-sm font-semibold">
                      {settings.registration.trade_cta_button}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Account Portal Preview */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="font-bold text-gray-900 mb-4">Account Portal Preview</h3>
            <div className="grid md:grid-cols-4 gap-6">
              {/* Sidebar */}
              <div className="bg-white border rounded-xl p-4">
                <div className="text-center mb-4 pb-4 border-b">
                  <div className="w-14 h-14 bg-[#333333] rounded-full flex items-center justify-center mx-auto mb-2">
                    <User className="w-7 h-7 text-[#F7EA1C]" />
                  </div>
                  <p className="font-bold text-gray-900">John Smith</p>
                  <p className="text-xs text-gray-500">john@example.com</p>
                </div>
                <div className="space-y-1 text-sm">
                  <div className="bg-[#333] text-[#F7EA1C] px-3 py-2 rounded">Overview</div>
                  <div className="px-3 py-2 text-gray-600">Orders</div>
                  <div className="px-3 py-2 text-gray-600">Wishlist</div>
                  <div className="px-3 py-2 text-gray-600">Settings</div>
                </div>
                {settings.portal.show_trade_upgrade && (
                  <div className="mt-4 pt-4 border-t">
                    <div className="bg-[#333333] rounded-lg p-3 text-white">
                      <div className="flex items-center gap-2 mb-1">
                        <Building2 className="w-4 h-4 text-[#F7EA1C]" />
                        <span className="font-semibold text-xs">{settings.portal.trade_upgrade_title}</span>
                      </div>
                      <p className="text-xs text-gray-400 mb-2">{settings.portal.trade_upgrade_text}</p>
                      <div className="bg-[#F7EA1C] text-[#333] text-center py-1 rounded text-xs font-semibold">
                        {settings.portal.trade_upgrade_button}
                      </div>
                    </div>
                  </div>
                )}
              </div>
              
              {/* Main Content */}
              <div className="md:col-span-3">
                <div className="bg-gradient-to-br from-[#333333] to-[#444444] rounded-xl p-6 text-white mb-4">
                  <h2 className="text-xl font-bold">
                    {settings.portal.welcome_message.replace('{name}', 'John')}
                  </h2>
                  <p className="text-gray-300 text-sm">{settings.portal.welcome_subtext}</p>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-white border rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-8 h-8 bg-blue-100 rounded flex items-center justify-center">
                        <ShoppingBag className="w-4 h-4 text-blue-600" />
                      </div>
                      <span className="text-xs text-gray-500">Total Orders</span>
                    </div>
                    <p className="text-xl font-bold">12</p>
                  </div>
                  <div className="bg-white border rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-8 h-8 bg-pink-100 rounded flex items-center justify-center">
                        <Heart className="w-4 h-4 text-pink-600" />
                      </div>
                      <span className="text-xs text-gray-500">Wishlist</span>
                    </div>
                    <p className="text-xl font-bold">5</p>
                  </div>
                  <div className="bg-white border rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-8 h-8 bg-green-100 rounded flex items-center justify-center">
                        <MapPin className="w-4 h-4 text-green-600" />
                      </div>
                      <span className="text-xs text-gray-500">Addresses</span>
                    </div>
                    <p className="text-xl font-bold">2</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CustomerAccountSettings;
