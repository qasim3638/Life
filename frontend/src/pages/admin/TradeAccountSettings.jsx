import React, { useState, useEffect } from 'react';
import { 
  Save, Plus, Trash2, Edit2, GripVertical, RefreshCw, Eye,
  Percent, Gift, Award, Truck, Headphones, Shield, ChevronUp, ChevronDown,
  Building2, Loader2, TrendingUp
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Switch } from '../../components/ui/switch';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Default settings
const DEFAULT_SETTINGS = {
  // Announcement bar (top of shop)
  announcement_bar: {
    enabled: true,
    items: [
      { text: 'Pay in 3 ways with Klarna', link: '/tiles', enabled: true },
      { text: 'Free samples with free delivery', link: '/shop/sample-service', enabled: true },
      { text: 'Free delivery on orders over £300', link: '/shop/delivery', enabled: true },
    ]
  },
  // Homepage Banner
  banner: {
    enabled: true,
    badge_text: 'For Trade Professionals',
    headline: 'Open a Trade Account &',
    headline_highlight: 'Save More',
    description: 'Join thousands of builders, tilers, and contractors who enjoy exclusive trade pricing, credit back rewards on every purchase, and priority service.',
    cta_primary_text: 'Open Trade Account',
    cta_primary_link: '/shop/trade/register',
    cta_secondary_text: 'Already have an account? Sign In',
    cta_secondary_link: '/shop/login',
  },
  // Benefits shown on both homepage and registration page
  benefits: [
    { id: '1', icon: 'Percent', title: 'Exclusive Trade Discounts', description: 'Access special pricing not available to retail customers', enabled: true },
    { id: '2', icon: 'Gift', title: 'Credit Back Rewards', description: 'Earn credit back on every purchase - up to 5% based on your tier', enabled: true },
    { id: '3', icon: 'Award', title: 'Tier Rewards Program', description: 'Bronze → Silver → Gold → Platinum - the more you spend, the more you save', enabled: true },
    { id: '4', icon: 'Truck', title: 'Priority Delivery', description: 'Trade customers get priority on deliveries and collections', enabled: true },
    { id: '5', icon: 'Headphones', title: 'Extended Support Hours', description: 'Dedicated trade support line with extended hours', enabled: true },
    { id: '6', icon: 'Shield', title: 'Trade Guarantee', description: 'Extended warranty and hassle-free returns for trade purchases', enabled: true },
  ],
  // Discount tiers
  // Trade pricing (homepage right-side card)
  tiers_enabled: true,
  trade_pricing: {
    sale_discount: 20,
    standard_discount: 40,
    sale_credit_back: 3,
    standard_credit_back: 5,
    tagline: 'On Every Single Purchase',
  },
  tiers: [
    { id: 'bronze', name: 'Bronze', discount: 1, min_spend: 0, color: '#B45309' },
    { id: 'silver', name: 'Silver', discount: 2, min_spend: 5000, color: '#9CA3AF' },
    { id: 'gold', name: 'Gold', discount: 3, min_spend: 15000, color: '#FBBF24' },
    { id: 'platinum', name: 'Platinum', discount: 5, min_spend: 50000, color: '#D1D5DB' },
  ],
  // Short benefits for homepage banner
  banner_benefits: [
    { id: '1', icon: 'Percent', text: 'Exclusive Discounts', enabled: true },
    { id: '2', icon: 'Gift', text: 'Up to 5% Credit Back', enabled: true },
    { id: '3', icon: 'Truck', text: 'Priority Delivery', enabled: true },
    { id: '4', icon: 'Headphones', text: 'Dedicated Support', enabled: true },
  ],
  // Trade Dashboard (Account Portal) settings
  dashboard: {
    // Visibility toggles for main sections
    show_tier_card: true,
    show_progress_bar: true,
    // Stats cards
    stats: [
      { id: 'credit', label: 'Discount Balance', icon: 'Wallet', color: 'green', enabled: true },
      { id: 'orders', label: 'Total Orders', icon: 'ShoppingBag', color: 'blue', enabled: true },
      { id: 'spent', label: 'Total Spent', icon: 'TrendingUp', color: 'purple', enabled: true },
    ],
    // Quick actions
    quick_actions: [
      { id: 'shop', title: 'Shop Products', description: 'Browse our trade catalogue', link: '/tiles', icon: 'ShoppingBag', enabled: true },
      { id: 'samples', title: 'Order Samples', description: 'Request product samples', link: '/shop/sample-service', icon: 'Package', enabled: true },
    ],
    // Credit back explanation steps
    credit_steps: [
      { id: '1', title: 'Make a Purchase', description: 'Shop any products from our trade catalogue' },
      { id: '2', title: 'Earn Discount', description: 'Get a discount on every order based on your tier' },
      { id: '3', title: 'Use on Future Orders', description: 'Apply your credit balance at checkout to save more' },
    ],
    // Misc text
    tier_progress_text: 'Spend £{remaining} more to reach {next_tier}',
    account_type_label: 'Proforma / Cash Account',
  }
};

const ICON_OPTIONS = [
  { value: 'Percent', label: 'Percent', icon: Percent },
  { value: 'Gift', label: 'Gift', icon: Gift },
  { value: 'Award', label: 'Award', icon: Award },
  { value: 'Truck', label: 'Truck', icon: Truck },
  { value: 'Headphones', label: 'Headphones', icon: Headphones },
  { value: 'Shield', label: 'Shield', icon: Shield },
  { value: 'Building2', label: 'Building', icon: Building2 },
];

const getIconComponent = (iconName) => {
  const found = ICON_OPTIONS.find(i => i.value === iconName);
  return found ? found.icon : Percent;
};

const TradeAccountSettings = () => {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('banner');
  const [editingBenefit, setEditingBenefit] = useState(null);
  const [editingTier, setEditingTier] = useState(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/trade-account-settings`, {
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
      const res = await fetch(`${API_URL}/api/website-admin/trade-account-settings`, {
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

  const updateBanner = (field, value) => {
    setSettings(prev => ({
      ...prev,
      banner: { ...prev.banner, [field]: value }
    }));
  };

  const updateBenefit = (id, field, value) => {
    setSettings(prev => ({
      ...prev,
      benefits: prev.benefits.map(b => b.id === id ? { ...b, [field]: value } : b)
    }));
  };

  const addBenefit = () => {
    const newBenefit = {
      id: `benefit_${Date.now()}`,
      icon: 'Percent',
      title: 'New Benefit',
      description: 'Description here',
      enabled: true
    };
    setSettings(prev => ({
      ...prev,
      benefits: [...prev.benefits, newBenefit]
    }));
    setEditingBenefit(newBenefit.id);
  };

  const deleteBenefit = (id) => {
    if (!window.confirm('Delete this benefit?')) return;
    setSettings(prev => ({
      ...prev,
      benefits: prev.benefits.filter(b => b.id !== id)
    }));
  };

  const updateTier = (id, field, value) => {
    setSettings(prev => ({
      ...prev,
      tiers: prev.tiers.map(t => t.id === id ? { ...t, [field]: value } : t)
    }));
  };

  const updateBannerBenefit = (id, field, value) => {
    setSettings(prev => ({
      ...prev,
      banner_benefits: prev.banner_benefits.map(b => b.id === id ? { ...b, [field]: value } : b)
    }));
  };

  const addTier = () => {
    const newTier = {
      id: `tier_${Date.now()}`,
      name: 'New Tier',
      discount: 0,
      min_spend: 0,
      color: '#6B7280'
    };
    setSettings(prev => ({
      ...prev,
      tiers: [...prev.tiers, newTier]
    }));
    setEditingTier(newTier.id);
  };

  const deleteTier = (id) => {
    if (settings.tiers.length <= 1) {
      toast.error('You must have at least one tier');
      return;
    }
    if (!window.confirm('Delete this tier?')) return;
    setSettings(prev => ({
      ...prev,
      tiers: prev.tiers.filter(t => t.id !== id)
    }));
  };

  const updateAnnouncementBar = (field, value) => {
    setSettings(prev => ({
      ...prev,
      announcement_bar: { ...(prev.announcement_bar || {}), [field]: value }
    }));
  };

  const updateAnnouncementItem = (index, field, value) => {
    setSettings(prev => {
      const items = [...(prev.announcement_bar?.items || [])];
      items[index] = { ...items[index], [field]: value };
      return { ...prev, announcement_bar: { ...(prev.announcement_bar || {}), items } };
    });
  };

  const addAnnouncementItem = () => {
    setSettings(prev => {
      const items = [...(prev.announcement_bar?.items || [])];
      items.push({ text: 'New announcement', link: '/tiles', enabled: true });
      return { ...prev, announcement_bar: { ...(prev.announcement_bar || {}), items } };
    });
  };

  const removeAnnouncementItem = (index) => {
    setSettings(prev => {
      const items = [...(prev.announcement_bar?.items || [])];
      items.splice(index, 1);
      return { ...prev, announcement_bar: { ...(prev.announcement_bar || {}), items } };
    });
  };

  const tabs = [
    { id: 'banner', label: 'Homepage Banner' },
    { id: 'benefits', label: 'Benefits List' },
    { id: 'pricing', label: 'Trade Pricing' },
    { id: 'tiers', label: 'Account Tiers' },
    { id: 'dashboard', label: 'Account Dashboard' },
    { id: 'preview', label: 'Full Preview' },
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
          <h1 className="text-2xl font-bold text-gray-900">Trade Account Settings</h1>
          <p className="text-gray-500">Manage trade account banner, benefits, and tier settings</p>
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

      {/* Master visibility switch — promoted to the top so it's not buried
          inside a tab. Hides ALL discount-tier visuals across the entire shop
          in one click (registration page Discount Tiers panel, login page tier
          messaging, account dashboard tier indicators, homepage trade pricing
          card, plus any benefit cards mentioning Bronze/Silver/Gold/Platinum). */}
      <div
        className={`rounded-xl border p-5 mb-6 flex items-start justify-between gap-4 ${
          settings.tiers_enabled !== false
            ? 'bg-emerald-50 border-emerald-200'
            : 'bg-amber-50 border-amber-200'
        }`}
        data-testid="master-tiers-visibility-card"
      >
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-base font-bold text-gray-900">Show discount tier amounts (Bronze / Silver / Gold / Platinum)</h2>
            <span className="inline-flex items-center text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-gray-900 text-white">
              Master switch
            </span>
          </div>
          <p className="text-sm text-gray-600 mb-2">
            Single switch controlling whether tier discount % values are visible across the entire shop. When OFF, customers see your trade benefits but not the specific discount percentages.
          </p>
          <details className="text-xs text-gray-500">
            <summary className="cursor-pointer hover:text-gray-700">Affected pages (5)</summary>
            <ul className="mt-2 ml-4 list-disc space-y-0.5">
              <li>Trade registration page — "Discount Tiers" panel (Bronze 5% / Silver 10% / Gold 15% / Platinum 20%)</li>
              <li>Trade registration page — auto-hides any benefit card mentioning Bronze / Silver / Gold / Platinum / "Tier"</li>
              <li>Trade login page — tier-based messaging</li>
              <li>Trade account dashboard — tier indicators on the customer's account</li>
              <li>Homepage — right-side "Trade Pricing Card" with the discount table</li>
            </ul>
          </details>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span className={`text-sm font-semibold ${settings.tiers_enabled !== false ? 'text-emerald-700' : 'text-amber-700'}`}>
            {settings.tiers_enabled !== false ? 'Visible' : 'Hidden'}
          </span>
          <button
            type="button"
            onClick={() => setSettings(prev => ({ ...prev, tiers_enabled: prev.tiers_enabled === false ? true : false }))}
            className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${
              settings.tiers_enabled !== false ? 'bg-emerald-500' : 'bg-gray-300'
            }`}
            data-testid="master-tiers-visibility-toggle"
            aria-label="Toggle tier amount visibility across the entire shop"
          >
            <span
              className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
                settings.tiers_enabled !== false ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
          <span className="text-[10px] text-gray-500">Save to apply</span>
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

      {/* Banner Settings */}
      {activeTab === 'banner' && (
        <div className="space-y-6">
          {/* Enable/Disable Banner */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-bold text-gray-900">Homepage Trade Banner</h2>
                <p className="text-sm text-gray-500">The promotional banner shown on the homepage</p>
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.banner.enabled}
                  onChange={(e) => updateBanner('enabled', e.target.checked)}
                  className="w-5 h-5 text-amber-500 rounded"
                />
                <span className="font-medium">Show on Homepage</span>
              </label>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <Label>Badge Text</Label>
                <Input
                  value={settings.banner.badge_text}
                  onChange={(e) => updateBanner('badge_text', e.target.value)}
                  placeholder="For Trade Professionals"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>Headline Highlight (Yellow text)</Label>
                <Input
                  value={settings.banner.headline_highlight}
                  onChange={(e) => updateBanner('headline_highlight', e.target.value)}
                  placeholder="Save More"
                  className="mt-1"
                />
              </div>
              <div className="md:col-span-2">
                <Label>Main Headline</Label>
                <Input
                  value={settings.banner.headline}
                  onChange={(e) => updateBanner('headline', e.target.value)}
                  placeholder="Open a Trade Account &"
                  className="mt-1"
                />
              </div>
              <div className="md:col-span-2">
                <Label>Description</Label>
                <textarea
                  value={settings.banner.description}
                  onChange={(e) => updateBanner('description', e.target.value)}
                  className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-md min-h-[80px]"
                  placeholder="Join thousands of builders..."
                />
              </div>
              <div>
                <Label>Primary Button Text</Label>
                <Input
                  value={settings.banner.cta_primary_text}
                  onChange={(e) => updateBanner('cta_primary_text', e.target.value)}
                  placeholder="Open Trade Account"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>Primary Button Link</Label>
                <Input
                  value={settings.banner.cta_primary_link}
                  onChange={(e) => updateBanner('cta_primary_link', e.target.value)}
                  placeholder="/shop/trade/register"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>Secondary Button Text</Label>
                <Input
                  value={settings.banner.cta_secondary_text}
                  onChange={(e) => updateBanner('cta_secondary_text', e.target.value)}
                  placeholder="Already have an account?"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>Secondary Button Link</Label>
                <Input
                  value={settings.banner.cta_secondary_link}
                  onChange={(e) => updateBanner('cta_secondary_link', e.target.value)}
                  placeholder="/shop/login"
                  className="mt-1"
                />
              </div>
            </div>
          </div>

          {/* Banner Quick Benefits */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="font-bold text-gray-900 mb-4">Banner Quick Benefits (4 items shown on homepage)</h3>
            <div className="grid md:grid-cols-2 gap-4">
              {settings.banner_benefits.map((benefit, idx) => (
                <div key={benefit.id} className="flex items-center gap-3 p-3 border rounded-lg">
                  <select
                    value={benefit.icon}
                    onChange={(e) => updateBannerBenefit(benefit.id, 'icon', e.target.value)}
                    className="w-24 px-2 py-1 border rounded text-sm"
                  >
                    {ICON_OPTIONS.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                  <Input
                    value={benefit.text}
                    onChange={(e) => updateBannerBenefit(benefit.id, 'text', e.target.value)}
                    className="flex-1"
                    placeholder="Benefit text"
                  />
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={benefit.enabled}
                      onChange={(e) => updateBannerBenefit(benefit.id, 'enabled', e.target.checked)}
                      className="w-4 h-4 text-amber-500 rounded"
                    />
                  </label>
                </div>
              ))}
            </div>
          </div>

          {/* Preview */}
          <div className="bg-gray-100 rounded-xl p-6">
            <h3 className="font-bold text-gray-700 mb-4 flex items-center gap-2">
              <Eye className="w-5 h-5" /> Banner Preview
            </h3>
            <div className="bg-[#333333] rounded-xl p-6 text-white">
              <div className="inline-flex items-center gap-2 bg-[#F7EA1C] text-[#333] px-3 py-1 rounded-full text-sm font-semibold mb-4">
                {settings.banner.badge_text}
              </div>
              <h2 className="text-2xl font-bold mb-2">
                {settings.banner.headline} <span className="text-[#F7EA1C]">{settings.banner.headline_highlight}</span>
              </h2>
              <p className="text-gray-300 text-sm mb-4">{settings.banner.description}</p>
              <div className="flex flex-wrap gap-4 mb-4">
                {settings.banner_benefits.filter(b => b.enabled).map(benefit => {
                  const IconComponent = getIconComponent(benefit.icon);
                  return (
                    <div key={benefit.id} className="flex items-center gap-2 text-sm">
                      <IconComponent className="w-4 h-4 text-[#F7EA1C]" />
                      <span>{benefit.text}</span>
                    </div>
                  );
                })}
              </div>
              <div className="flex gap-3">
                <span className="bg-[#F7EA1C] text-[#333] px-4 py-2 rounded-lg text-sm font-bold">
                  {settings.banner.cta_primary_text}
                </span>
                <span className="border border-white/30 px-4 py-2 rounded-lg text-sm">
                  {settings.banner.cta_secondary_text}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Benefits Settings */}
      {activeTab === 'benefits' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-bold text-gray-900">Trade Account Benefits</h2>
                <p className="text-sm text-gray-500">Benefits shown on the trade registration page sidebar</p>
              </div>
              <Button onClick={addBenefit} className="bg-amber-500 hover:bg-amber-600">
                <Plus className="w-4 h-4 mr-1" /> Add Benefit
              </Button>
            </div>

            <div className="space-y-3">
              {settings.benefits.map((benefit, idx) => {
                const IconComponent = getIconComponent(benefit.icon);
                const isEditing = editingBenefit === benefit.id;
                
                return (
                  <div 
                    key={benefit.id}
                    className={`border rounded-lg p-4 ${isEditing ? 'border-amber-400 bg-amber-50' : 'hover:border-gray-300'}`}
                  >
                    {isEditing ? (
                      <div className="space-y-3">
                        <div className="grid grid-cols-3 gap-3">
                          <div>
                            <Label>Icon</Label>
                            <select
                              value={benefit.icon}
                              onChange={(e) => updateBenefit(benefit.id, 'icon', e.target.value)}
                              className="w-full mt-1 px-3 py-2 border rounded-md"
                            >
                              {ICON_OPTIONS.map(opt => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                              ))}
                            </select>
                          </div>
                          <div className="col-span-2">
                            <Label>Title</Label>
                            <Input
                              value={benefit.title}
                              onChange={(e) => updateBenefit(benefit.id, 'title', e.target.value)}
                              className="mt-1"
                            />
                          </div>
                        </div>
                        <div>
                          <Label>Description</Label>
                          <Input
                            value={benefit.description}
                            onChange={(e) => updateBenefit(benefit.id, 'description', e.target.value)}
                            className="mt-1"
                          />
                        </div>
                        <div className="flex items-center justify-between">
                          <label className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={benefit.enabled}
                              onChange={(e) => updateBenefit(benefit.id, 'enabled', e.target.checked)}
                              className="w-4 h-4 text-amber-500 rounded"
                            />
                            <span className="text-sm">Enabled</span>
                          </label>
                          <Button variant="outline" size="sm" onClick={() => setEditingBenefit(null)}>
                            Done
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 bg-[#F7EA1C]/20 rounded-lg flex items-center justify-center">
                          <IconComponent className="w-5 h-5 text-[#333]" />
                        </div>
                        <div className="flex-1">
                          <h3 className={`font-semibold ${benefit.enabled ? 'text-gray-900' : 'text-gray-400'}`}>
                            {benefit.title}
                          </h3>
                          <p className="text-sm text-gray-500">{benefit.description}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs px-2 py-1 rounded ${benefit.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                            {benefit.enabled ? 'Enabled' : 'Disabled'}
                          </span>
                          <Button variant="ghost" size="sm" onClick={() => setEditingBenefit(benefit.id)}>
                            <Edit2 className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" className="text-red-600" onClick={() => deleteBenefit(benefit.id)}>
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Trade Pricing Settings (Homepage right-side card) */}
      {activeTab === 'pricing' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-bold text-gray-900">Trade Pricing Card</h2>
                <p className="text-sm text-gray-500">These values appear on the homepage trade banner (right-side card). Visibility is controlled by the master switch at the top of this page.</p>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span className={`inline-flex items-center gap-1 px-2 py-1 rounded font-medium ${settings.tiers_enabled !== false ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700 border border-amber-200'}`}>
                  {settings.tiers_enabled !== false ? 'Visible' : 'Hidden'} (master)
                </span>
              </div>
            </div>

            {settings.tiers_enabled === false && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-6 text-sm text-amber-700">
                The pricing card is currently hidden from the homepage. Toggle on to show it.
              </div>
            )}

            <div className={`space-y-8 ${settings.tiers_enabled === false ? 'opacity-50 pointer-events-none' : ''}`}>
              {/* Trade Discounts */}
              <div>
                <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Percent className="w-5 h-5 text-[#F7EA1C]" />
                  Trade Discounts
                </h3>
                <div className="grid grid-cols-2 gap-6">
                  <div className="border rounded-lg p-4">
                    <Label className="text-sm font-medium text-red-600">Sale Price Discount</Label>
                    <p className="text-xs text-gray-500 mb-2">Extra % off on top of sale prices</p>
                    <div className="relative">
                      <Input
                        type="number"
                        min="0"
                        max="100"
                        value={settings.trade_pricing?.sale_discount ?? 20}
                        onChange={(e) => setSettings(prev => ({
                          ...prev,
                          trade_pricing: { ...prev.trade_pricing, sale_discount: parseFloat(e.target.value) || 0 }
                        }))}
                        className="text-2xl font-bold pr-10"
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 text-lg font-bold">%</span>
                    </div>
                  </div>
                  <div className="border rounded-lg p-4">
                    <Label className="text-sm font-medium text-amber-600">Standard Price Discount</Label>
                    <p className="text-xs text-gray-500 mb-2">% off on standard / retail prices</p>
                    <div className="relative">
                      <Input
                        type="number"
                        min="0"
                        max="100"
                        value={settings.trade_pricing?.standard_discount ?? 40}
                        onChange={(e) => setSettings(prev => ({
                          ...prev,
                          trade_pricing: { ...prev.trade_pricing, standard_discount: parseFloat(e.target.value) || 0 }
                        }))}
                        className="text-2xl font-bold pr-10"
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 text-lg font-bold">%</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Credit Back */}
              <div>
                <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Gift className="w-5 h-5 text-green-500" />
                  Credit Back Rewards
                </h3>
                <div className="grid grid-cols-2 gap-6">
                  <div className="border rounded-lg p-4">
                    <Label className="text-sm font-medium text-green-600">From Sale Products</Label>
                    <p className="text-xs text-gray-500 mb-2">Credit back % on sale items</p>
                    <div className="relative">
                      <Input
                        type="number"
                        min="0"
                        max="10"
                        step="0.5"
                        value={settings.trade_pricing?.sale_credit_back ?? 3}
                        onChange={(e) => setSettings(prev => ({
                          ...prev,
                          trade_pricing: { ...prev.trade_pricing, sale_credit_back: parseFloat(e.target.value) || 0 }
                        }))}
                        className="text-2xl font-bold pr-10"
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 text-lg font-bold">%</span>
                    </div>
                  </div>
                  <div className="border rounded-lg p-4">
                    <Label className="text-sm font-medium text-emerald-600">From Standard Products</Label>
                    <p className="text-xs text-gray-500 mb-2">Credit back % on standard items</p>
                    <div className="relative">
                      <Input
                        type="number"
                        min="0"
                        max="10"
                        step="0.5"
                        value={settings.trade_pricing?.standard_credit_back ?? 5}
                        onChange={(e) => setSettings(prev => ({
                          ...prev,
                          trade_pricing: { ...prev.trade_pricing, standard_credit_back: parseFloat(e.target.value) || 0 }
                        }))}
                        className="text-2xl font-bold pr-10"
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 text-lg font-bold">%</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Tagline */}
              <div>
                <h3 className="font-semibold text-gray-900 mb-4">Bottom Tagline</h3>
                <Input
                  value={settings.trade_pricing?.tagline ?? 'On Every Single Purchase'}
                  onChange={(e) => setSettings(prev => ({
                    ...prev,
                    trade_pricing: { ...prev.trade_pricing, tagline: e.target.value }
                  }))}
                  placeholder="e.g. On Every Single Purchase"
                  className="font-bold"
                />
              </div>
            </div>
          </div>

          {/* Live Preview */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="font-bold text-gray-900 mb-4">Live Preview</h3>
            <div className="bg-[#333333] rounded-xl p-6 max-w-md mx-auto">
              <div className="space-y-3">
                <div className="bg-white/10 backdrop-blur rounded-xl p-4 border border-white/10">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-6 h-6 bg-[#F7EA1C] rounded flex items-center justify-center">
                      <Percent className="w-3 h-3 text-[#333]" />
                    </div>
                    <span className="text-white font-bold text-xs tracking-wide uppercase">Trade Discounts</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-red-500/20 rounded-lg p-3 border border-red-500/20 text-center">
                      <p className="text-red-300 text-[10px] uppercase tracking-wider">Sale Prices</p>
                      <p className="text-white text-2xl font-black"><span className="text-[9px] font-semibold">Up to </span>{settings.trade_pricing?.sale_discount ?? 20}<span className="text-sm">%</span></p>
                      <p className="text-red-300 text-[10px]">extra off</p>
                    </div>
                    <div className="bg-[#F7EA1C]/20 rounded-lg p-3 border border-[#F7EA1C]/20 text-center">
                      <p className="text-[#F7EA1C]/80 text-[10px] uppercase tracking-wider">Standard</p>
                      <p className="text-white text-2xl font-black"><span className="text-[9px] font-semibold">Up to </span>{settings.trade_pricing?.standard_discount ?? 40}<span className="text-sm">%</span></p>
                      <p className="text-[#F7EA1C]/80 text-[10px]">off retail</p>
                    </div>
                  </div>
                </div>
                <div className="bg-white/10 backdrop-blur rounded-xl p-4 border border-white/10">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-6 h-6 bg-green-500 rounded flex items-center justify-center">
                      <Gift className="w-3 h-3 text-white" />
                    </div>
                    <span className="text-white font-bold text-xs tracking-wide uppercase">Credit Back Rewards</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-green-500/20 rounded-lg p-3 border border-green-500/20 text-center">
                      <p className="text-green-300 text-[10px] uppercase tracking-wider">From Sale</p>
                      <p className="text-white text-2xl font-black"><span className="text-[9px] font-semibold">Up to </span>{settings.trade_pricing?.sale_credit_back ?? 3}<span className="text-sm">%</span></p>
                      <p className="text-green-300 text-[10px]">credit back</p>
                    </div>
                    <div className="bg-emerald-500/20 rounded-lg p-3 border border-emerald-500/20 text-center">
                      <p className="text-emerald-300 text-[10px] uppercase tracking-wider">Standard</p>
                      <p className="text-white text-2xl font-black"><span className="text-[9px] font-semibold">Up to </span>{settings.trade_pricing?.standard_credit_back ?? 5}<span className="text-sm">%</span></p>
                      <p className="text-emerald-300 text-[10px]">credit back</p>
                    </div>
                  </div>
                </div>
                <div className="bg-[#F7EA1C] rounded-lg py-2 text-center">
                  <p className="text-[#333] font-black text-xs tracking-wide uppercase">
                    {settings.trade_pricing?.tagline || 'On Every Single Purchase'}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tiers Settings */}
      {activeTab === 'tiers' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-bold text-gray-900">Discount Tiers</h2>
                <p className="text-sm text-gray-500">Configure the tier levels, discounts, and spend thresholds</p>
              </div>
              <div className="flex items-center gap-3">
                <Button variant="outline" onClick={addTier} size="sm">
                  <Plus className="w-4 h-4 mr-1" /> Add Tier
                </Button>
                <span className="text-sm text-gray-500">{settings.tiers_enabled !== false ? 'Visible' : 'Hidden'}</span>
                <button
                  onClick={() => setSettings(prev => ({ ...prev, tiers_enabled: prev.tiers_enabled === false ? true : false }))}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${settings.tiers_enabled !== false ? 'bg-green-500' : 'bg-gray-300'}`}
                  data-testid="tiers-enabled-toggle"
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${settings.tiers_enabled !== false ? 'translate-x-6' : 'translate-x-1'}`} />
                </button>
              </div>
            </div>

            {settings.tiers_enabled === false && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 text-sm text-amber-700">
                Discount tiers are currently hidden from the website. Toggle on to make them visible again.
              </div>
            )}

            <div className="space-y-4">
              {settings.tiers.map((tier, idx) => (
                <div key={tier.id} className={`border rounded-lg p-4 ${settings.tiers_enabled === false ? 'opacity-50' : ''}`}>
                  <div className="flex items-center gap-4">
                    <div 
                      className="w-4 h-4 rounded-full flex-shrink-0"
                      style={{ backgroundColor: tier.color }}
                    />
                    <div className="flex-1 grid grid-cols-4 gap-4 items-center">
                      <div>
                        <Label className="text-xs text-gray-500">Tier Name</Label>
                        <Input
                          value={tier.name}
                          onChange={(e) => updateTier(tier.id, 'name', e.target.value)}
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <Label className="text-xs text-gray-500">Discount %</Label>
                        <div className="relative mt-1">
                          <Input
                            type="number"
                            min="0"
                            max="50"
                            step="0.5"
                            value={tier.discount}
                            onChange={(e) => {
                              const val = parseFloat(e.target.value) || 0;
                              updateTier(tier.id, 'discount', val);
                            }}
                            className="pr-8"
                          />
                          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">%</span>
                        </div>
                      </div>
                      <div>
                        <Label className="text-xs text-gray-500">Min. Spend (£)</Label>
                        <div className="relative mt-1">
                          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">£</span>
                          <Input
                            type="number"
                            value={tier.min_spend}
                            onChange={(e) => updateTier(tier.id, 'min_spend', parseInt(e.target.value) || 0)}
                            className="pl-8"
                          />
                        </div>
                      </div>
                      <div>
                        <Label className="text-xs text-gray-500">Color</Label>
                        <div className="flex gap-2 mt-1">
                          <input
                            type="color"
                            value={tier.color}
                            onChange={(e) => updateTier(tier.id, 'color', e.target.value)}
                            className="w-10 h-10 rounded border cursor-pointer"
                          />
                          <button
                            type="button"
                            onClick={() => deleteTier(tier.id)}
                            className="p-2 text-red-400 hover:text-red-600 hover:bg-red-50 rounded"
                            title="Delete tier"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Tier Preview */}
          <div className="bg-gray-100 rounded-xl p-6">
            <h3 className="font-bold text-gray-700 mb-4 flex items-center gap-2">
              <Eye className="w-5 h-5" /> Tier Preview (as shown on registration page)
            </h3>
            <div className="bg-[#333333] rounded-xl p-6 max-w-md">
              <h3 className="text-white font-bold mb-4">Discount Tiers</h3>
              <div className="space-y-2">
                {settings.tiers.map(tier => (
                  <div key={tier.id} className="flex items-center justify-between bg-white/5 rounded-lg px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div 
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: tier.color }}
                      />
                      <span className="text-white font-medium">{tier.name}</span>
                    </div>
                    <div className="text-right">
                      <span className="text-[#F7EA1C] font-bold">{tier.discount}%</span>
                      <span className="text-gray-400 text-sm ml-2">
                        (£{tier.min_spend.toLocaleString()}+)
                      </span>
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-gray-400 text-xs mt-4 text-center">
                The more you spend, the bigger your discount!
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Dashboard Settings Tab */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          {/* Tier Card & Progress Visibility */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Tier Card & Progress</h2>
            <p className="text-sm text-gray-500 mb-4">Control visibility of the trade tier card and progress bar on the customer's account page</p>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gray-800 text-white rounded-lg flex items-center justify-center">
                    <Award className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">Trade Tier Card</p>
                    <p className="text-xs text-gray-500">Shows current tier name (Bronze/Silver/Gold) and discount rate</p>
                  </div>
                </div>
                <Switch
                  checked={settings.dashboard?.show_tier_card !== false}
                  onCheckedChange={(v) => setSettings(prev => ({
                    ...prev, dashboard: { ...prev.dashboard, show_tier_card: v }
                  }))}
                  data-testid="show-tier-card-toggle"
                />
              </div>
              <div className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">Progress to Next Tier</p>
                    <p className="text-xs text-gray-500">Shows spending progress bar towards the next tier level</p>
                  </div>
                </div>
                <Switch
                  checked={settings.dashboard?.show_progress_bar !== false}
                  onCheckedChange={(v) => setSettings(prev => ({
                    ...prev, dashboard: { ...prev.dashboard, show_progress_bar: v }
                  }))}
                  data-testid="show-progress-bar-toggle"
                />
              </div>
            </div>
          </div>

          {/* Stats Cards */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Dashboard Stats Cards</h2>
            <p className="text-sm text-gray-500 mb-4">Configure which stats appear on the trade account dashboard</p>
            <div className="space-y-3">
              {settings.dashboard?.stats?.map((stat, idx) => (
                <div key={stat.id} className="flex items-center gap-4 p-3 border rounded-lg">
                  <div className={`w-10 h-10 bg-${stat.color}-100 rounded-lg flex items-center justify-center`}>
                    <span className="text-sm font-bold">{idx + 1}</span>
                  </div>
                  <Input
                    value={stat.label}
                    onChange={(e) => {
                      const newStats = [...settings.dashboard.stats];
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
                      const newStats = [...settings.dashboard.stats];
                      newStats[idx] = { ...stat, color: e.target.value };
                      setSettings(prev => ({
                        ...prev,
                        dashboard: { ...prev.dashboard, stats: newStats }
                      }));
                    }}
                    className="px-3 py-2 border rounded-md"
                  >
                    <option value="green">Green</option>
                    <option value="blue">Blue</option>
                    <option value="purple">Purple</option>
                    <option value="amber">Amber</option>
                    <option value="pink">Pink</option>
                  </select>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={stat.enabled}
                      onChange={(e) => {
                        const newStats = [...settings.dashboard.stats];
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
                          const newActions = [...settings.dashboard.quick_actions];
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
                          const newActions = [...settings.dashboard.quick_actions];
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
                          const newActions = [...settings.dashboard.quick_actions];
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
                          const newActions = [...settings.dashboard.quick_actions];
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

          {/* Credit Back Steps */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">"How Discount Tiers Work" Steps</h2>
            <div className="space-y-3">
              {settings.dashboard?.credit_steps?.map((step, idx) => (
                <div key={step.id} className="flex items-start gap-4 p-3 border rounded-lg">
                  <div className="w-8 h-8 bg-[#F7EA1C] rounded-full flex items-center justify-center font-bold text-[#333] flex-shrink-0">
                    {idx + 1}
                  </div>
                  <div className="flex-1 grid grid-cols-2 gap-3">
                    <div>
                      <Label>Title</Label>
                      <Input
                        value={step.title}
                        onChange={(e) => {
                          const newSteps = [...settings.dashboard.credit_steps];
                          newSteps[idx] = { ...step, title: e.target.value };
                          setSettings(prev => ({
                            ...prev,
                            dashboard: { ...prev.dashboard, credit_steps: newSteps }
                          }));
                        }}
                        className="mt-1"
                      />
                    </div>
                    <div>
                      <Label>Description</Label>
                      <Input
                        value={step.description}
                        onChange={(e) => {
                          const newSteps = [...settings.dashboard.credit_steps];
                          newSteps[idx] = { ...step, description: e.target.value };
                          setSettings(prev => ({
                            ...prev,
                            dashboard: { ...prev.dashboard, credit_steps: newSteps }
                          }));
                        }}
                        className="mt-1"
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Misc Settings */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Other Text</h2>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <Label>Tier Progress Text</Label>
                <Input
                  value={settings.dashboard?.tier_progress_text || ''}
                  onChange={(e) => setSettings(prev => ({
                    ...prev,
                    dashboard: { ...prev.dashboard, tier_progress_text: e.target.value }
                  }))}
                  className="mt-1"
                  placeholder="Spend £{remaining} more to reach {next_tier}"
                />
                <p className="text-xs text-gray-500 mt-1">Use {'{remaining}'} and {'{next_tier}'} as placeholders</p>
              </div>
              <div>
                <Label>Account Type Label</Label>
                <Input
                  value={settings.dashboard?.account_type_label || ''}
                  onChange={(e) => setSettings(prev => ({
                    ...prev,
                    dashboard: { ...prev.dashboard, account_type_label: e.target.value }
                  }))}
                  className="mt-1"
                  placeholder="Proforma / Cash Account"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Full Preview Tab */}
      {activeTab === 'preview' && (
        <div className="space-y-6">
          {/* Quick Links */}
          <div className="flex gap-4 mb-4">
            <a 
              href="/shop/trade/register" 
              target="_blank" 
              rel="noopener noreferrer"
              className="flex items-center gap-2 bg-amber-500 text-white px-4 py-2 rounded-lg hover:bg-amber-600"
            >
              <Eye className="w-4 h-4" /> View Trade Registration Page
            </a>
            <a 
              href="/shop/trade/account" 
              target="_blank" 
              rel="noopener noreferrer"
              className="flex items-center gap-2 bg-gray-700 text-white px-4 py-2 rounded-lg hover:bg-gray-800"
            >
              <Eye className="w-4 h-4" /> View Trade Account Portal
            </a>
          </div>

          {/* Homepage Banner Preview */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="font-bold text-gray-900 mb-4">Homepage Trade Banner Preview</h3>
            <div className="bg-[#333333] rounded-xl p-8 text-white relative overflow-hidden">
              <div className="absolute inset-0 opacity-10">
                <div className="absolute inset-0" style={{
                  backgroundImage: 'url("data:image/svg+xml,%3Csvg width=\'60\' height=\'60\' viewBox=\'0 0 60 60\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cg fill=\'none\' fill-rule=\'evenodd\'%3E%3Cg fill=\'%23F7EA1C\' fill-opacity=\'0.4\'%3E%3Cpath d=\'M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z\'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")',
                }} />
              </div>
              <div className="relative z-10 grid md:grid-cols-2 gap-8 items-center">
                <div>
                  <div className="inline-flex items-center gap-2 bg-[#F7EA1C] text-[#333] px-3 py-1 rounded-full text-sm font-semibold mb-4">
                    <Award className="w-4 h-4" />
                    {settings.banner.badge_text}
                  </div>
                  <h2 className="text-3xl font-bold mb-4">
                    {settings.banner.headline} <span className="text-[#F7EA1C]">{settings.banner.headline_highlight}</span>
                  </h2>
                  <p className="text-gray-300 mb-6">{settings.banner.description}</p>
                  <div className="grid grid-cols-2 gap-4 mb-6">
                    {settings.banner_benefits.filter(b => b.enabled).map(benefit => {
                      const IconComponent = getIconComponent(benefit.icon);
                      return (
                        <div key={benefit.id} className="flex items-center gap-2">
                          <div className="w-8 h-8 bg-[#F7EA1C]/20 rounded-lg flex items-center justify-center">
                            <IconComponent className="w-4 h-4 text-[#F7EA1C]" />
                          </div>
                          <span className="text-sm">{benefit.text}</span>
                        </div>
                      );
                    })}
                  </div>
                  <div className="flex flex-col sm:flex-row gap-3">
                    <span className="inline-flex items-center justify-center gap-2 bg-[#F7EA1C] text-[#333] font-bold px-6 py-3 rounded-lg">
                      <Building2 className="w-5 h-5" />
                      {settings.banner.cta_primary_text}
                    </span>
                    <span className="inline-flex items-center justify-center gap-2 border-2 border-white/30 text-white font-semibold px-6 py-3 rounded-lg">
                      {settings.banner.cta_secondary_text}
                    </span>
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="bg-white/10 backdrop-blur rounded-xl p-4 border border-white/10">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-6 h-6 bg-[#F7EA1C] rounded flex items-center justify-center">
                        <Percent className="w-3 h-3 text-[#333]" />
                      </div>
                      <span className="text-white font-bold text-xs tracking-wide uppercase">Trade Discounts</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-red-500/20 rounded-lg p-3 border border-red-500/20 text-center">
                        <p className="text-red-300 text-[10px] uppercase">Sale Prices</p>
                        <p className="text-white text-2xl font-black"><span className="text-[9px] font-semibold">Up to </span>{settings.trade_pricing?.sale_discount ?? 20}<span className="text-sm">%</span></p>
                        <p className="text-red-300 text-[10px]">extra off</p>
                      </div>
                      <div className="bg-[#F7EA1C]/20 rounded-lg p-3 border border-[#F7EA1C]/20 text-center">
                        <p className="text-[#F7EA1C]/80 text-[10px] uppercase">Standard</p>
                        <p className="text-white text-2xl font-black"><span className="text-[9px] font-semibold">Up to </span>{settings.trade_pricing?.standard_discount ?? 40}<span className="text-sm">%</span></p>
                        <p className="text-[#F7EA1C]/80 text-[10px]">off retail</p>
                      </div>
                    </div>
                  </div>
                  <div className="bg-white/10 backdrop-blur rounded-xl p-4 border border-white/10">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-6 h-6 bg-green-500 rounded flex items-center justify-center">
                        <Gift className="w-3 h-3 text-white" />
                      </div>
                      <span className="text-white font-bold text-xs tracking-wide uppercase">Credit Back</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-green-500/20 rounded-lg p-3 border border-green-500/20 text-center">
                        <p className="text-green-300 text-[10px] uppercase">From Sale</p>
                        <p className="text-white text-2xl font-black"><span className="text-[9px] font-semibold">Up to </span>{settings.trade_pricing?.sale_credit_back ?? 3}<span className="text-sm">%</span></p>
                        <p className="text-green-300 text-[10px]">credit back</p>
                      </div>
                      <div className="bg-emerald-500/20 rounded-lg p-3 border border-emerald-500/20 text-center">
                        <p className="text-emerald-300 text-[10px] uppercase">Standard</p>
                        <p className="text-white text-2xl font-black"><span className="text-[9px] font-semibold">Up to </span>{settings.trade_pricing?.standard_credit_back ?? 5}<span className="text-sm">%</span></p>
                        <p className="text-emerald-300 text-[10px]">credit back</p>
                      </div>
                    </div>
                  </div>
                  <div className="bg-[#F7EA1C] rounded-lg py-2 text-center">
                    <p className="text-[#333] font-black text-xs tracking-wide uppercase">
                      {settings.trade_pricing?.tagline || 'On Every Single Purchase'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Registration Page Sidebar Preview */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="font-bold text-gray-900 mb-4">Registration Page Benefits Sidebar Preview</h3>
            <div className="max-w-md">
              <div className="bg-[#333333] text-white rounded-2xl p-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-12 h-12 bg-[#F7EA1C] rounded-xl flex items-center justify-center">
                    <Building2 className="w-6 h-6 text-[#333333]" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold">Trade Account Benefits</h2>
                    <p className="text-gray-400 text-sm">Why join our trade program?</p>
                  </div>
                </div>

                <div className="space-y-4 mb-8">
                  {settings.benefits.filter(b => b.enabled).map((benefit) => {
                    const IconComponent = getIconComponent(benefit.icon);
                    return (
                      <div key={benefit.id} className="flex gap-3">
                        <div className="w-10 h-10 bg-[#F7EA1C]/10 rounded-lg flex items-center justify-center flex-shrink-0">
                          <IconComponent className="w-5 h-5 text-[#F7EA1C]" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-white">{benefit.title}</h3>
                          <p className="text-gray-400 text-sm">{benefit.description}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="border-t border-gray-700 pt-6">
                  <div className="space-y-2">
                    <div className="bg-white/10 rounded-lg p-3 border border-white/10">
                      <div className="flex items-center gap-2 mb-2">
                        <Percent className="w-4 h-4 text-[#F7EA1C]" />
                        <span className="text-white font-bold text-xs uppercase">Trade Discounts</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="bg-red-500/20 rounded p-2 text-center">
                          <p className="text-red-300 text-[9px] uppercase">Sale</p>
                          <p className="text-white text-lg font-black">Up to {settings.trade_pricing?.sale_discount ?? 20}%</p>
                        </div>
                        <div className="bg-[#F7EA1C]/20 rounded p-2 text-center">
                          <p className="text-[#F7EA1C]/80 text-[9px] uppercase">Standard</p>
                          <p className="text-white text-lg font-black">Up to {settings.trade_pricing?.standard_discount ?? 40}%</p>
                        </div>
                      </div>
                    </div>
                    <div className="bg-white/10 rounded-lg p-3 border border-white/10">
                      <div className="flex items-center gap-2 mb-2">
                        <Gift className="w-4 h-4 text-green-400" />
                        <span className="text-white font-bold text-xs uppercase">Credit Back</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="bg-green-500/20 rounded p-2 text-center">
                          <p className="text-green-300 text-[9px] uppercase">Sale</p>
                          <p className="text-white text-lg font-black">Up to {settings.trade_pricing?.sale_credit_back ?? 3}%</p>
                        </div>
                        <div className="bg-emerald-500/20 rounded p-2 text-center">
                          <p className="text-emerald-300 text-[9px] uppercase">Standard</p>
                          <p className="text-white text-lg font-black">Up to {settings.trade_pricing?.standard_credit_back ?? 5}%</p>
                        </div>
                      </div>
                    </div>
                    <div className="bg-[#F7EA1C] rounded py-1.5 text-center">
                      <p className="text-[#333] font-black text-[10px] uppercase">{settings.trade_pricing?.tagline || 'On Every Single Purchase'}</p>
                    </div>
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

export default TradeAccountSettings;
