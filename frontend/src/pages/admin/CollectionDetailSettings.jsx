import React, { useState, useEffect, useCallback } from 'react';
import { 
  Settings, 
  Save, 
  Loader2, 
  Eye, 
  EyeOff,
  Truck, 
  Clock, 
  Share2, 
  ShoppingCart, 
  Image, 
  FileText,
  Tag,
  Percent,
  Shield,
  Scissors,
  Check,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Smartphone,
  Monitor,
  Facebook,
  Mail,
  Copy,
  Play,
  Maximize2,
  Home,
  Layers,
  Package,
  Wrench,
  Droplet,
  Ruler,
  Info,
  Palette,
  AlertCircle
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Default settings for Collection Detail Page
const DEFAULT_SETTINGS = {
  // Trust Badges
  trustBadges: {
    enabled: true,
    badges: [
      { id: 'delivery', enabled: true, title: 'Free Delivery', subtitle: 'Over £299', icon: 'truck', color: 'amber' },
      { id: 'samples', enabled: true, title: 'Free Samples', subtitle: 'Try before you buy', icon: 'scissors', color: 'green' },
      { id: 'quality', enabled: true, title: 'Quality Guaranteed', subtitle: 'Premium tiles only', icon: 'shield', color: 'blue' },
      { id: 'secure', enabled: true, title: 'Secure Payment', subtitle: '100% protected', icon: 'check', color: 'purple' },
    ]
  },
  
  // Delivery Estimate
  deliveryEstimate: {
    enabled: true,
    showCountdown: true,
    cutoffHour: 14, // 2PM
    freeDeliveryThreshold: 299,
    standardDays: '2-3',
    expressDays: 'Next day',
    showPalletDelivery: true,
    showUKMainland: true,
  },

  // Next Day Delivery - supplier-based
  nextDayDelivery: {
    enabled: false,
    suppliers: [],
  },
  
  // Share Buttons
  shareButtons: {
    enabled: true,
    platforms: {
      facebook: true,
      twitter: true,
      whatsapp: true,
      pinterest: true,
      email: true,
      copyLink: true,
    }
  },
  
  // Frequently Bought Together
  frequentlyBoughtTogether: {
    enabled: true,
    title: 'Frequently Bought Together',
    subtitle: 'Complete your project with these essential accessories',
    showBundleTotal: true,
    accessories: [
      { id: 'adhesive', name: 'Tile Adhesive', description: '20kg bag', price: 24.99, enabled: true },
      { id: 'grout', name: 'Tile Grout', description: 'Grey - 5kg', price: 12.99, enabled: true },
      { id: 'spacers', name: 'Tile Spacers', description: '3mm - 200pcs', price: 4.99, enabled: true },
    ]
  },
  
  // Accordion Sections
  accordionSections: {
    enabled: true,
    sections: {
      specifications: { enabled: true, defaultOpen: true, title: 'Technical Specifications' },
      installation: { enabled: true, defaultOpen: false, title: 'Installation Guide' },
      maintenance: { enabled: true, defaultOpen: false, title: 'Maintenance Tips' },
    }
  },
  
  // Sticky Mobile Cart
  stickyMobileCart: {
    enabled: true,
    showPrice: true,
    showTotal: true,
  },
  
  // Image Gallery
  imageGallery: {
    lightboxEnabled: true,
    viewInRoomEnabled: true,
    videoSupport: true,
    showMobileNavDots: true,
    showNavigationArrows: true,
    zoomOnHover: true,
  },
  
  // Pricing Display
  pricingDisplay: {
    saleBadgeStyle: 'ribbon', // 'ribbon', 'pill', 'tag'
    showWasPrice: true,
    showSavingsPercent: true,
    showSavingsAmount: true,
    tierPricingEnabled: true,
    showTierPricingBeforeSelection: true,
  },
  
  // Sale Badge
  saleBadge: {
    style: 'ribbon', // 'ribbon', 'pill', 'corner'
    showStar: true,
    text: 'Sale',
    position: 'top-right',
  }
};

// Settings Section Component
const SettingsSection = ({ title, icon: Icon, children, defaultOpen = true }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  
  return (
    <div className="border rounded-lg overflow-hidden bg-white shadow-sm">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Icon className="w-5 h-5 text-amber-600" />
          <span className="font-semibold text-gray-900">{title}</span>
        </div>
        {isOpen ? (
          <ChevronDown className="w-5 h-5 text-gray-500" />
        ) : (
          <ChevronRight className="w-5 h-5 text-gray-500" />
        )}
      </button>
      {isOpen && (
        <div className="p-4 space-y-4 border-t">
          {children}
        </div>
      )}
    </div>
  );
};

// Toggle Switch Component
const ToggleSwitch = ({ enabled, onChange, label, description }) => (
  <div className="flex items-center justify-between py-2">
    <div>
      <p className="font-medium text-gray-900">{label}</p>
      {description && <p className="text-sm text-gray-500">{description}</p>}
    </div>
    <button
      onClick={() => onChange(!enabled)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
        enabled ? 'bg-amber-500' : 'bg-gray-300'
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
          enabled ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  </div>
);

export default function CollectionDetailSettings({ embedded = false }) {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [allSuppliers, setAllSuppliers] = useState([]);
  const [supplierSearch, setSupplierSearch] = useState('');

  // Deep merge helper function
  const deepMerge = (target, source) => {
    const result = { ...target };
    for (const key in source) {
      if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
        result[key] = deepMerge(target[key] || {}, source[key]);
      } else {
        result[key] = source[key];
      }
    }
    return result;
  };

  // Fetch settings from backend
  const fetchSettings = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/collection-detail-settings`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        if (data.settings && Object.keys(data.settings).length > 0) {
          // Deep merge to preserve nested arrays like badges and accessories
          setSettings(prev => deepMerge(DEFAULT_SETTINGS, data.settings));
        }
      }
    } catch (error) {
      console.error('Error fetching settings:', error);
      // Use defaults if fetch fails
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
    // Fetch supplier list for next day delivery
    const fetchSuppliers = async () => {
      try {
        const token = localStorage.getItem('token');
        const res = await fetch(`${API_URL}/api/website-admin/suppliers-list`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setAllSuppliers(data.suppliers || []);
        }
      } catch (error) {
        console.error('Error fetching suppliers:', error);
      }
    };
    fetchSuppliers();
  }, [fetchSettings]);

  // Update a nested setting
  const updateSetting = (section, key, value) => {
    setSettings(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value
      }
    }));
    setHasChanges(true);
  };

  // Update deeply nested setting
  const updateNestedSetting = (section, subsection, key, value) => {
    setSettings(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [subsection]: {
          ...prev[section][subsection],
          [key]: value
        }
      }
    }));
    setHasChanges(true);
  };

  // Update trust badge
  const updateTrustBadge = (badgeId, key, value) => {
    setSettings(prev => ({
      ...prev,
      trustBadges: {
        ...prev.trustBadges,
        badges: (prev.trustBadges.badges || []).map(badge =>
          badge.id === badgeId ? { ...badge, [key]: value } : badge
        )
      }
    }));
    setHasChanges(true);
  };

  // Update accessory
  const updateAccessory = (accessoryId, key, value) => {
    setSettings(prev => ({
      ...prev,
      frequentlyBoughtTogether: {
        ...prev.frequentlyBoughtTogether,
        accessories: (prev.frequentlyBoughtTogether.accessories || []).map(acc =>
          acc.id === accessoryId ? { ...acc, [key]: value } : acc
        )
      }
    }));
    setHasChanges(true);
  };

  // Save settings
  const saveSettings = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/collection-detail-settings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ settings })
      });
      
      if (res.ok) {
        toast.success('Settings saved successfully!');
        setHasChanges(false);
      } else {
        throw new Error('Failed to save');
      }
    } catch (error) {
      console.error('Error saving settings:', error);
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  // Reset to defaults
  const resetToDefaults = () => {
    if (window.confirm('Are you sure you want to reset all settings to defaults?')) {
      setSettings(DEFAULT_SETTINGS);
      setHasChanges(true);
      toast.info('Settings reset to defaults. Click Save to apply.');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 p-6 flex items-center justify-center">
        <div className="flex items-center gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
          <span className="text-gray-600">Loading settings...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={embedded ? 'bg-gray-100' : 'min-h-screen bg-gray-100'}>
      {/* Header */}
      {!embedded ? (
        <div className="bg-white border-b sticky top-0 z-10">
          <div className="max-w-6xl mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
                  <Settings className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-gray-900">Collection Detail Page Settings</h1>
                  <p className="text-sm text-gray-500">Customize how your product collection pages look and function</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Button
                  variant="outline"
                  onClick={resetToDefaults}
                  className="flex items-center gap-2"
                >
                  <RefreshCw className="w-4 h-4" />
                  Reset to Defaults
                </Button>
                <Button
                  onClick={saveSettings}
                  disabled={saving || !hasChanges}
                  className={`flex items-center gap-2 ${hasChanges ? 'bg-amber-500 hover:bg-amber-600' : 'bg-gray-300'}`}
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  {saving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </div>
            {hasChanges && (
              <div className="mt-2 flex items-center gap-2 text-amber-600 text-sm">
                <AlertCircle className="w-4 h-4" />
                You have unsaved changes
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="px-4 py-3 bg-white border-b flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              onClick={resetToDefaults}
              className="flex items-center gap-2"
              size="sm"
            >
              <RefreshCw className="w-4 h-4" />
              Reset to Defaults
            </Button>
            <Button
              onClick={saveSettings}
              disabled={saving || !hasChanges}
              size="sm"
              className={`flex items-center gap-2 ${hasChanges ? 'bg-amber-500 hover:bg-amber-600' : 'bg-gray-300'}`}
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
          {hasChanges && (
            <div className="flex items-center gap-2 text-amber-600 text-sm">
              <AlertCircle className="w-4 h-4" />
              Unsaved changes
            </div>
          )}
        </div>
      )}

      {/* Settings Content */}
      <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">
        {/* Trust Badges Section */}
        <SettingsSection title="Trust Badges Strip" icon={Shield}>
          <ToggleSwitch
            enabled={settings.trustBadges.enabled}
            onChange={(v) => updateSetting('trustBadges', 'enabled', v)}
            label="Enable Trust Badges"
            description="Show trust badges below header (Free Delivery, Free Samples, etc.)"
          />
          
          {settings.trustBadges.enabled && (
            <div className="mt-4 space-y-3">
              <p className="text-sm font-medium text-gray-700">Configure Badges:</p>
              {(settings.trustBadges.badges || []).map((badge) => (
                <div key={badge.id} className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg">
                  <input
                    type="checkbox"
                    checked={badge.enabled}
                    onChange={(e) => updateTrustBadge(badge.id, 'enabled', e.target.checked)}
                    className="w-4 h-4 text-amber-500 rounded"
                  />
                  <div className="flex-1 grid grid-cols-2 gap-3">
                    <Input
                      value={badge.title}
                      onChange={(e) => updateTrustBadge(badge.id, 'title', e.target.value)}
                      placeholder="Title"
                      className="text-sm"
                    />
                    <Input
                      value={badge.subtitle}
                      onChange={(e) => updateTrustBadge(badge.id, 'subtitle', e.target.value)}
                      placeholder="Subtitle"
                      className="text-sm"
                    />
                  </div>
                  <select
                    value={badge.color}
                    onChange={(e) => updateTrustBadge(badge.id, 'color', e.target.value)}
                    className="text-sm border rounded px-2 py-1"
                  >
                    <option value="amber">Amber</option>
                    <option value="green">Green</option>
                    <option value="blue">Blue</option>
                    <option value="purple">Purple</option>
                    <option value="red">Red</option>
                  </select>
                </div>
              ))}
            </div>
          )}
        </SettingsSection>

        {/* Delivery Estimate Section */}
        <SettingsSection title="Delivery Estimate & Countdown" icon={Truck}>
          <ToggleSwitch
            enabled={settings.deliveryEstimate.enabled}
            onChange={(v) => updateSetting('deliveryEstimate', 'enabled', v)}
            label="Enable Delivery Estimate Section"
            description="Show delivery information with countdown timer"
          />
          
          {settings.deliveryEstimate.enabled && (
            <div className="mt-4 space-y-4">
              <ToggleSwitch
                enabled={settings.deliveryEstimate.showCountdown}
                onChange={(v) => updateSetting('deliveryEstimate', 'showCountdown', v)}
                label="Show Countdown Timer"
                description="Display live countdown to order cutoff time"
              />
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Cutoff Hour (24h format)</label>
                  <Input
                    type="number"
                    min="0"
                    max="23"
                    value={settings.deliveryEstimate.cutoffHour}
                    onChange={(e) => updateSetting('deliveryEstimate', 'cutoffHour', parseInt(e.target.value))}
                  />
                  <p className="text-xs text-gray-500 mt-1">Orders before this hour qualify for next-day dispatch</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Free Delivery Threshold (£)</label>
                  <Input
                    type="number"
                    value={settings.deliveryEstimate.freeDeliveryThreshold}
                    onChange={(e) => updateSetting('deliveryEstimate', 'freeDeliveryThreshold', parseInt(e.target.value))}
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Standard Delivery</label>
                  <Input
                    value={settings.deliveryEstimate.standardDays}
                    onChange={(e) => updateSetting('deliveryEstimate', 'standardDays', e.target.value)}
                    placeholder="e.g., 2-3 days"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Express Delivery</label>
                  <Input
                    value={settings.deliveryEstimate.expressDays}
                    onChange={(e) => updateSetting('deliveryEstimate', 'expressDays', e.target.value)}
                    placeholder="e.g., Next day"
                  />
                </div>
              </div>
            </div>
          )}
        </SettingsSection>

        {/* Next Day Delivery Section */}
        <SettingsSection title="Next Day Delivery" icon={Clock} defaultOpen={false}>
          <ToggleSwitch
            enabled={settings.nextDayDelivery?.enabled}
            onChange={(v) => updateSetting('nextDayDelivery', 'enabled', v)}
            label="Enable Next Day Delivery"
            description="Show 'Next Day Delivery Available' badge on eligible product pages"
          />
          
          {settings.nextDayDelivery?.enabled && (
            <div className="mt-4 space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select suppliers that offer next day delivery
                </label>
                <p className="text-xs text-gray-500 mb-3">
                  Products from checked suppliers will show the next day delivery badge on product pages. ({settings.nextDayDelivery?.suppliers?.length || 0} of {allSuppliers.length} selected)
                </p>
                
                {/* Search + Select All */}
                <div className="flex items-center gap-2 mb-3">
                  <Input
                    placeholder="Search suppliers..."
                    value={supplierSearch}
                    onChange={(e) => setSupplierSearch(e.target.value)}
                    className="flex-1"
                    data-testid="supplier-search-input"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const filtered = allSuppliers.filter(s => 
                        s.toLowerCase().includes(supplierSearch.toLowerCase())
                      );
                      const allChecked = filtered.every(s => settings.nextDayDelivery?.suppliers?.includes(s));
                      const newSuppliers = allChecked
                        ? (settings.nextDayDelivery?.suppliers || []).filter(s => !filtered.includes(s))
                        : [...new Set([...(settings.nextDayDelivery?.suppliers || []), ...filtered])];
                      updateSetting('nextDayDelivery', 'suppliers', newSuppliers);
                    }}
                    data-testid="toggle-all-suppliers"
                  >
                    {allSuppliers.filter(s => s.toLowerCase().includes(supplierSearch.toLowerCase())).every(s => settings.nextDayDelivery?.suppliers?.includes(s))
                      ? 'Deselect All' : 'Select All'}
                  </Button>
                </div>

                {/* Supplier Checklist */}
                <div className="border rounded-lg max-h-64 overflow-y-auto divide-y" data-testid="supplier-checklist">
                  {allSuppliers.length === 0 && (
                    <div className="p-4 text-center text-sm text-gray-500">No suppliers found</div>
                  )}
                  {allSuppliers
                    .filter(s => s.toLowerCase().includes(supplierSearch.toLowerCase()))
                    .map(supplier => (
                      <label
                        key={supplier}
                        className="flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 cursor-pointer transition-colors"
                      >
                        <input
                          type="checkbox"
                          checked={settings.nextDayDelivery?.suppliers?.includes(supplier) || false}
                          onChange={(e) => {
                            const current = settings.nextDayDelivery?.suppliers || [];
                            const newSuppliers = e.target.checked
                              ? [...current, supplier]
                              : current.filter(s => s !== supplier);
                            updateSetting('nextDayDelivery', 'suppliers', newSuppliers);
                          }}
                          className="w-4 h-4 text-amber-500 rounded border-gray-300"
                          data-testid={`supplier-checkbox-${supplier.replace(/\s+/g, '-').toLowerCase()}`}
                        />
                        <span className="text-sm text-gray-700">{supplier}</span>
                        {settings.nextDayDelivery?.suppliers?.includes(supplier) && (
                          <span className="ml-auto text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                            Next Day
                          </span>
                        )}
                      </label>
                    ))
                  }
                </div>
              </div>
            </div>
          )}
        </SettingsSection>

        {/* Share Buttons Section */}
        <SettingsSection title="Share Buttons" icon={Share2}>
          <ToggleSwitch
            enabled={settings.shareButtons.enabled}
            onChange={(v) => updateSetting('shareButtons', 'enabled', v)}
            label="Enable Share Buttons"
            description="Allow customers to share products on social media"
          />
          
          {settings.shareButtons.enabled && (
            <div className="mt-4 grid grid-cols-2 md:grid-cols-3 gap-3">
              {Object.entries(settings.shareButtons.platforms).map(([platform, enabled]) => (
                <label key={platform} className="flex items-center gap-2 p-2 bg-gray-50 rounded cursor-pointer hover:bg-gray-100">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(e) => updateNestedSetting('shareButtons', 'platforms', platform, e.target.checked)}
                    className="w-4 h-4 text-amber-500 rounded"
                  />
                  <span className="text-sm capitalize">{platform === 'copyLink' ? 'Copy Link' : platform}</span>
                </label>
              ))}
            </div>
          )}
        </SettingsSection>

        {/* Frequently Bought Together Section */}
        <SettingsSection title="Frequently Bought Together" icon={Package}>
          <ToggleSwitch
            enabled={settings.frequentlyBoughtTogether.enabled}
            onChange={(v) => updateSetting('frequentlyBoughtTogether', 'enabled', v)}
            label="Enable Frequently Bought Together"
            description="Show complementary products section"
          />
          
          {settings.frequentlyBoughtTogether.enabled && (
            <div className="mt-4 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Section Title</label>
                  <Input
                    value={settings.frequentlyBoughtTogether.title}
                    onChange={(e) => updateSetting('frequentlyBoughtTogether', 'title', e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Subtitle</label>
                  <Input
                    value={settings.frequentlyBoughtTogether.subtitle}
                    onChange={(e) => updateSetting('frequentlyBoughtTogether', 'subtitle', e.target.value)}
                  />
                </div>
              </div>
              
              <ToggleSwitch
                enabled={settings.frequentlyBoughtTogether.showBundleTotal}
                onChange={(v) => updateSetting('frequentlyBoughtTogether', 'showBundleTotal', v)}
                label="Show Bundle Total"
                description="Display combined price of all selected items"
              />
              
              <div className="space-y-2">
                <p className="text-sm font-medium text-gray-700">Accessories:</p>
                {(settings.frequentlyBoughtTogether.accessories || []).map((acc) => (
                  <div key={acc.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                    <input
                      type="checkbox"
                      checked={acc.enabled}
                      onChange={(e) => updateAccessory(acc.id, 'enabled', e.target.checked)}
                      className="w-4 h-4 text-amber-500 rounded"
                    />
                    <Input
                      value={acc.name}
                      onChange={(e) => updateAccessory(acc.id, 'name', e.target.value)}
                      placeholder="Name"
                      className="flex-1 text-sm"
                    />
                    <Input
                      value={acc.description}
                      onChange={(e) => updateAccessory(acc.id, 'description', e.target.value)}
                      placeholder="Description"
                      className="flex-1 text-sm"
                    />
                    <div className="flex items-center gap-1">
                      <span className="text-sm text-gray-500">£</span>
                      <Input
                        type="number"
                        step="0.01"
                        value={acc.price}
                        onChange={(e) => updateAccessory(acc.id, 'price', parseFloat(e.target.value))}
                        className="w-24 text-sm"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </SettingsSection>

        {/* Accordion Sections */}
        <SettingsSection title="Information Accordion" icon={Layers}>
          <ToggleSwitch
            enabled={settings.accordionSections.enabled}
            onChange={(v) => updateSetting('accordionSections', 'enabled', v)}
            label="Enable Information Accordion"
            description="Show expandable sections for specs, installation, maintenance"
          />
          
          {settings.accordionSections.enabled && (
            <div className="mt-4 space-y-3">
              {Object.entries(settings.accordionSections.sections).map(([key, section]) => (
                <div key={key} className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg">
                  <input
                    type="checkbox"
                    checked={section.enabled}
                    onChange={(e) => updateNestedSetting('accordionSections', 'sections', key, { ...section, enabled: e.target.checked })}
                    className="w-4 h-4 text-amber-500 rounded"
                  />
                  <Input
                    value={section.title}
                    onChange={(e) => updateNestedSetting('accordionSections', 'sections', key, { ...section, title: e.target.value })}
                    className="flex-1 text-sm"
                  />
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={section.defaultOpen}
                      onChange={(e) => updateNestedSetting('accordionSections', 'sections', key, { ...section, defaultOpen: e.target.checked })}
                      className="w-4 h-4 text-amber-500 rounded"
                    />
                    Open by default
                  </label>
                </div>
              ))}
            </div>
          )}
        </SettingsSection>

        {/* Sticky Mobile Cart */}
        <SettingsSection title="Sticky Mobile Add-to-Cart" icon={Smartphone}>
          <ToggleSwitch
            enabled={settings.stickyMobileCart.enabled}
            onChange={(v) => updateSetting('stickyMobileCart', 'enabled', v)}
            label="Enable Sticky Mobile Cart"
            description="Show fixed Add to Cart bar at bottom on mobile devices"
          />
          
          {settings.stickyMobileCart.enabled && (
            <div className="mt-4 space-y-2">
              <ToggleSwitch
                enabled={settings.stickyMobileCart.showPrice}
                onChange={(v) => updateSetting('stickyMobileCart', 'showPrice', v)}
                label="Show Price"
              />
              <ToggleSwitch
                enabled={settings.stickyMobileCart.showTotal}
                onChange={(v) => updateSetting('stickyMobileCart', 'showTotal', v)}
                label="Show Total"
              />
            </div>
          )}
        </SettingsSection>

        {/* Image Gallery */}
        <SettingsSection title="Image Gallery" icon={Image}>
          <div className="space-y-2">
            <ToggleSwitch
              enabled={settings.imageGallery.lightboxEnabled}
              onChange={(v) => updateSetting('imageGallery', 'lightboxEnabled', v)}
              label="Fullscreen Lightbox"
              description="Allow clicking images to view fullscreen"
            />
            <ToggleSwitch
              enabled={settings.imageGallery.viewInRoomEnabled}
              onChange={(v) => updateSetting('imageGallery', 'viewInRoomEnabled', v)}
              label="View in Room Button"
              description="Show lifestyle images modal"
            />
            <ToggleSwitch
              enabled={settings.imageGallery.videoSupport}
              onChange={(v) => updateSetting('imageGallery', 'videoSupport', v)}
              label="Video Support"
              description="Allow video files in product gallery"
            />
            <ToggleSwitch
              enabled={settings.imageGallery.showMobileNavDots}
              onChange={(v) => updateSetting('imageGallery', 'showMobileNavDots', v)}
              label="Mobile Navigation Dots"
              description="Show dot indicators on mobile"
            />
            <ToggleSwitch
              enabled={settings.imageGallery.showNavigationArrows}
              onChange={(v) => updateSetting('imageGallery', 'showNavigationArrows', v)}
              label="Navigation Arrows"
              description="Show left/right arrows for image navigation"
            />
            <ToggleSwitch
              enabled={settings.imageGallery.zoomOnHover}
              onChange={(v) => updateSetting('imageGallery', 'zoomOnHover', v)}
              label="Zoom on Hover"
              description="Enable image zoom when hovering"
            />
          </div>
        </SettingsSection>

        {/* Pricing Display */}
        <SettingsSection title="Pricing Display" icon={Tag}>
          <div className="space-y-4">
            <ToggleSwitch
              enabled={settings.pricingDisplay.showWasPrice}
              onChange={(v) => updateSetting('pricingDisplay', 'showWasPrice', v)}
              label="Show 'Was' Price"
              description="Display original price for sale items"
            />
            <ToggleSwitch
              enabled={settings.pricingDisplay.showSavingsPercent}
              onChange={(v) => updateSetting('pricingDisplay', 'showSavingsPercent', v)}
              label="Show Savings Percentage"
              description="Display 'Save X%' badge"
            />
            <ToggleSwitch
              enabled={settings.pricingDisplay.showSavingsAmount}
              onChange={(v) => updateSetting('pricingDisplay', 'showSavingsAmount', v)}
              label="Show Savings Amount"
              description="Display 'You save £X.XX'"
            />
            <ToggleSwitch
              enabled={settings.pricingDisplay.tierPricingEnabled}
              onChange={(v) => updateSetting('pricingDisplay', 'tierPricingEnabled', v)}
              label="Enable Tier Pricing"
              description="Show volume pricing table"
            />
            <ToggleSwitch
              enabled={settings.pricingDisplay.showTierPricingBeforeSelection}
              onChange={(v) => updateSetting('pricingDisplay', 'showTierPricingBeforeSelection', v)}
              label="Show Tier Pricing Before Selection"
              description="Display tier pricing even before customer selects options"
            />
          </div>
        </SettingsSection>

        {/* Sale Badge */}
        <SettingsSection title="Sale Badge Appearance" icon={Percent}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Badge Style</label>
              <div className="flex gap-3">
                {['ribbon', 'pill', 'corner'].map((style) => (
                  <button
                    key={style}
                    onClick={() => updateSetting('saleBadge', 'style', style)}
                    className={`px-4 py-2 rounded-lg border-2 transition-colors capitalize ${
                      settings.saleBadge.style === style
                        ? 'border-amber-500 bg-amber-50 text-amber-700'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    {style}
                  </button>
                ))}
              </div>
            </div>
            
            <ToggleSwitch
              enabled={settings.saleBadge.showStar}
              onChange={(v) => updateSetting('saleBadge', 'showStar', v)}
              label="Show Star Icon"
              description="Display star decoration on sale badge"
            />
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Badge Text</label>
              <Input
                value={settings.saleBadge.text}
                onChange={(e) => updateSetting('saleBadge', 'text', e.target.value)}
                placeholder="Sale"
                className="w-32"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Position</label>
              <div className="flex gap-3">
                {['top-left', 'top-right'].map((pos) => (
                  <button
                    key={pos}
                    onClick={() => updateSetting('saleBadge', 'position', pos)}
                    className={`px-4 py-2 rounded-lg border-2 transition-colors capitalize ${
                      settings.saleBadge.position === pos
                        ? 'border-amber-500 bg-amber-50 text-amber-700'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    {pos.replace('-', ' ')}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </SettingsSection>

        {/* Preview Section */}
        <div className="bg-white rounded-lg border p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <Eye className="w-5 h-5 text-amber-600" />
              Preview Changes
            </h3>
            <a
              href="/shop/collection/Bluestone"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-amber-600 hover:text-amber-700 flex items-center gap-1"
            >
              <Monitor className="w-4 h-4" />
              View Live Page
            </a>
          </div>
          <p className="text-sm text-gray-500">
            Changes will be reflected on the Collection Detail Pages after saving. 
            Visit any collection page to see your customizations in action.
          </p>
        </div>
      </div>
    </div>
  );
}
