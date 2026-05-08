import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import {
  Mail, Users, Store, Send, Plus, Trash2, BarChart3, CheckCircle, Clock,
  QrCode, Gift, ClipboardList, Search as SearchIcon, FileEdit,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card } from '../../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../../components/ui/dialog';
import { MarketingExtensions } from '../../components/admin/MarketingExtensions';

// Valid tabs for Marketing page
const VALID_TABS = ['campaigns', 'showrooms', 'customers', 'qr', 'referrals', 'leads', 'seo', 'seo-drafts'];

export const Marketing = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Get initial tab from URL
  const getInitialTab = useCallback(() => {
    const urlTab = searchParams.get('tab');
    if (urlTab && VALID_TABS.includes(urlTab)) {
      return urlTab;
    }
    return 'campaigns';
  }, [searchParams]);

  const [campaigns, setCampaigns] = useState([]);
  const [showrooms, setStores] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(getInitialTab);
  
  // Handle tab change with URL update
  const handleTabChange = useCallback((newTab) => {
    setActiveTab(newTab);
    setSearchParams({ tab: newTab }, { replace: true });
  }, [setSearchParams]);

  // Sync tab with URL on mount
  useEffect(() => {
    const urlTab = searchParams.get('tab');
    if (!urlTab) {
      setSearchParams({ tab: activeTab }, { replace: true });
    }
  }, [searchParams, activeTab, setSearchParams]);
  
  // Campaign form
  const [campaignDialogOpen, setCampaignDialogOpen] = useState(false);
  const [campaignForm, setCampaignForm] = useState({
    name: '',
    subject: '',
    content: '',
    campaign_type: 'promotional',
    target_audience: 'all',
    target_showroom_id: ''
  });
  
  // Store form
  const [showroomDialogOpen, setStoreDialogOpen] = useState(false);
  const [showroomForm, setStoreForm] = useState({
    name: '',
    address: '',
    phone: '',
    email: ''
  });
  const [editingStore, setEditingStore] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [campaignsRes, showroomsRes, customersRes, statsRes] = await Promise.all([
        api.getCampaigns(),
        api.getStores(),
        api.getCustomers(),
        api.getMarketingStats()
      ]);
      setCampaigns(campaignsRes.data);
      setStores(showroomsRes.data);
      setCustomers(customersRes.data);
      setStats(statsRes.data);
    } catch (error) {
      toast.error('Failed to load marketing data');
    } finally {
      setLoading(false);
    }
  };

  // Campaign functions
  const handleCreateCampaign = async (e) => {
    e.preventDefault();
    try {
      await api.createCampaign(campaignForm);
      toast.success('Campaign created');
      setCampaignDialogOpen(false);
      setCampaignForm({
        name: '',
        subject: '',
        content: '',
        campaign_type: 'promotional',
        target_audience: 'all',
        target_showroom_id: ''
      });
      fetchData();
    } catch (error) {
      toast.error('Failed to create campaign');
    }
  };

  const handleSendCampaign = async (id) => {
    if (!window.confirm('Are you sure you want to send this campaign? This cannot be undone.')) return;
    
    try {
      const response = await api.sendCampaign(id);
      toast.success(`Campaign sent to ${response.data.sent_count} recipients`);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to send campaign');
    }
  };

  const handleDeleteCampaign = async (id) => {
    if (!window.confirm('Are you sure you want to delete this campaign?')) return;
    
    try {
      await api.deleteCampaign(id);
      toast.success('Campaign deleted');
      fetchData();
    } catch (error) {
      toast.error('Failed to delete campaign');
    }
  };

  // Store functions
  const handleCreateStore = async (e) => {
    e.preventDefault();
    try {
      if (editingStore) {
        await api.updateStore(editingStore.id, showroomForm);
        toast.success('Store updated');
      } else {
        await api.createStore(showroomForm);
        toast.success('Store created');
      }
      setStoreDialogOpen(false);
      setStoreForm({ name: '', address: '', phone: '', email: '' });
      setEditingStore(null);
      fetchData();
    } catch (error) {
      toast.error('Failed to save showroom');
    }
  };

  const handleEditStore = (showroom) => {
    setEditingStore(showroom);
    setStoreForm({
      name: showroom.name,
      address: showroom.address || '',
      phone: showroom.phone || '',
      email: showroom.email || ''
    });
    setStoreDialogOpen(true);
  };

  const handleDeleteStore = async (id) => {
    if (!window.confirm('Are you sure you want to delete this showroom?')) return;
    
    try {
      await api.deleteStore(id);
      toast.success('Store deleted');
      fetchData();
    } catch (error) {
      toast.error('Failed to delete showroom');
    }
  };

  // Customer showroom assignment
  const handleAssignStore = async (email, showroomId) => {
    try {
      await api.assignCustomerStore(email, showroomId || null);
      toast.success('Customer showroom updated');
      fetchData();
    } catch (error) {
      toast.error('Failed to update customer');
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>;
  }

  return (
    <div className="space-y-6" data-testid="marketing-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-tightest mb-2">Marketing</h1>
          <p className="text-muted-foreground">Manage showrooms and send marketing campaigns</p>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <Users className="h-8 w-8 text-blue-600" />
            <div>
              <p className="text-2xl font-bold">{stats?.total_customers || 0}</p>
              <p className="text-sm text-muted-foreground">Total Customers</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <CheckCircle className="h-8 w-8 text-green-600" />
            <div>
              <p className="text-2xl font-bold">{stats?.opted_in_customers || 0}</p>
              <p className="text-sm text-muted-foreground">Opted In</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <Store className="h-8 w-8 text-purple-600" />
            <div>
              <p className="text-2xl font-bold">{showrooms.length}</p>
              <p className="text-sm text-muted-foreground">Stores</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <Mail className="h-8 w-8 text-accent" />
            <div>
              <p className="text-2xl font-bold">{stats?.sent_campaigns || 0}</p>
              <p className="text-sm text-muted-foreground">Campaigns Sent</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b flex-wrap" data-testid="marketing-tabs-nav">
        <button
          onClick={() => handleTabChange('campaigns')}
          className={`px-4 py-2 font-medium ${activeTab === 'campaigns' ? 'border-b-2 border-accent text-accent' : 'text-muted-foreground'}`}
        >
          <Mail className="h-4 w-4 inline mr-2" />
          Campaigns
        </button>
        <button
          onClick={() => handleTabChange('showrooms')}
          className={`px-4 py-2 font-medium ${activeTab === 'showrooms' ? 'border-b-2 border-accent text-accent' : 'text-muted-foreground'}`}
        >
          <Store className="h-4 w-4 inline mr-2" />
          Stores
        </button>
        <button
          onClick={() => handleTabChange('customers')}
          className={`px-4 py-2 font-medium ${activeTab === 'customers' ? 'border-b-2 border-accent text-accent' : 'text-muted-foreground'}`}
        >
          <Users className="h-4 w-4 inline mr-2" />
          Customers
        </button>
        <button
          onClick={() => handleTabChange('qr')}
          className={`px-4 py-2 font-medium ${activeTab === 'qr' ? 'border-b-2 border-accent text-accent' : 'text-muted-foreground'}`}
          data-testid="marketing-tab-qr"
        >
          <QrCode className="h-4 w-4 inline mr-2" />
          Trade QR
        </button>
        <button
          onClick={() => handleTabChange('referrals')}
          className={`px-4 py-2 font-medium ${activeTab === 'referrals' ? 'border-b-2 border-accent text-accent' : 'text-muted-foreground'}`}
          data-testid="marketing-tab-referrals"
        >
          <Gift className="h-4 w-4 inline mr-2" />
          Referrals
        </button>
        <button
          onClick={() => handleTabChange('leads')}
          className={`px-4 py-2 font-medium ${activeTab === 'leads' ? 'border-b-2 border-accent text-accent' : 'text-muted-foreground'}`}
          data-testid="marketing-tab-leads"
        >
          <ClipboardList className="h-4 w-4 inline mr-2" />
          Lead Capture
        </button>
        <button
          onClick={() => handleTabChange('seo')}
          className={`px-4 py-2 font-medium ${activeTab === 'seo' ? 'border-b-2 border-accent text-accent' : 'text-muted-foreground'}`}
          data-testid="marketing-tab-seo"
        >
          <SearchIcon className="h-4 w-4 inline mr-2" />
          SEO
        </button>
        <button
          onClick={() => handleTabChange('seo-drafts')}
          className={`px-4 py-2 font-medium ${activeTab === 'seo-drafts' ? 'border-b-2 border-accent text-accent' : 'text-muted-foreground'}`}
          data-testid="marketing-tab-seo-drafts"
        >
          <FileEdit className="h-4 w-4 inline mr-2" />
          SEO Drafts
        </button>
      </div>

      {/* New: Trade QR / Referrals / Lead Capture / SEO panels */}
      <MarketingExtensions activeTab={activeTab} />

      {/* Campaigns Tab */}
      {activeTab === 'campaigns' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Dialog open={campaignDialogOpen} onOpenChange={setCampaignDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-accent hover:bg-accent/90">
                  <Plus className="h-4 w-4 mr-2" />
                  Create Campaign
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-lg">
                <DialogHeader>
                  <DialogTitle>Create Email Campaign</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleCreateCampaign} className="space-y-4">
                  <div className="space-y-2">
                    <Label>Campaign Name</Label>
                    <Input
                      value={campaignForm.name}
                      onChange={(e) => setCampaignForm({ ...campaignForm, name: e.target.value })}
                      placeholder="Summer Sale 2026"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Email Subject</Label>
                    <Input
                      value={campaignForm.subject}
                      onChange={(e) => setCampaignForm({ ...campaignForm, subject: e.target.value })}
                      placeholder="Exclusive Summer Discounts at Tile Station!"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Campaign Type</Label>
                    <select
                      className="w-full px-3 py-2 border rounded-md"
                      value={campaignForm.campaign_type}
                      onChange={(e) => setCampaignForm({ ...campaignForm, campaign_type: e.target.value })}
                    >
                      <option value="promotional">Promotional</option>
                      <option value="newsletter">Newsletter</option>
                      <option value="custom">Custom</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label>Target Audience</Label>
                    <select
                      className="w-full px-3 py-2 border rounded-md"
                      value={campaignForm.target_audience}
                      onChange={(e) => setCampaignForm({ ...campaignForm, target_audience: e.target.value })}
                    >
                      <option value="all">All Customers</option>
                      <option value="opted_in">Opted-In Only</option>
                      <option value="store">By Store</option>
                    </select>
                  </div>
                  {campaignForm.target_audience === 'store' && (
                    <div className="space-y-2">
                      <Label>Select Store</Label>
                      <select
                        className="w-full px-3 py-2 border rounded-md"
                        value={campaignForm.target_showroom_id}
                        onChange={(e) => setCampaignForm({ ...campaignForm, target_showroom_id: e.target.value })}
                        required
                      >
                        <option value="">Select showroom...</option>
                        {showrooms.map(s => (
                          <option key={s.id} value={s.id}>{s.name}</option>
                        ))}
                      </select>
                    </div>
                  )}
                  <div className="space-y-2">
                    <Label>Email Content (HTML supported)</Label>
                    <textarea
                      className="w-full px-3 py-2 border rounded-md min-h-[150px]"
                      value={campaignForm.content}
                      onChange={(e) => setCampaignForm({ ...campaignForm, content: e.target.value })}
                      placeholder="<h2>Summer Sale!</h2><p>Get 20% off all floor tiles this month...</p>"
                      required
                    />
                  </div>
                  <Button type="submit" className="w-full bg-accent hover:bg-accent/90">
                    Create Campaign
                  </Button>
                </form>
              </DialogContent>
            </Dialog>
          </div>

          <Card>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-muted">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-medium">Campaign</th>
                    <th className="px-4 py-3 text-left text-sm font-medium">Type</th>
                    <th className="px-4 py-3 text-left text-sm font-medium">Target</th>
                    <th className="px-4 py-3 text-left text-sm font-medium">Status</th>
                    <th className="px-4 py-3 text-left text-sm font-medium">Sent</th>
                    <th className="px-4 py-3 text-right text-sm font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {campaigns.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                        No campaigns yet. Create your first campaign!
                      </td>
                    </tr>
                  ) : (
                    campaigns.map(campaign => (
                      <tr key={campaign.id}>
                        <td className="px-4 py-3">
                          <p className="font-medium">{campaign.name}</p>
                          <p className="text-sm text-muted-foreground">{campaign.subject}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-700 capitalize">
                            {campaign.campaign_type}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm capitalize">{campaign.target_audience}</td>
                        <td className="px-4 py-3">
                          {campaign.status === 'sent' ? (
                            <span className="flex items-center gap-1 text-green-600">
                              <CheckCircle className="h-4 w-4" /> Sent
                            </span>
                          ) : (
                            <span className="flex items-center gap-1 text-yellow-600">
                              <Clock className="h-4 w-4" /> Draft
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm">{campaign.sent_count || 0}</td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex justify-end gap-2">
                            {campaign.status !== 'sent' && (
                              <Button
                                size="sm"
                                onClick={() => handleSendCampaign(campaign.id)}
                                className="bg-green-600 hover:bg-green-700"
                              >
                                <Send className="h-4 w-4 mr-1" /> Send
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleDeleteCampaign(campaign.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* Stores Tab */}
      {activeTab === 'showrooms' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Dialog open={showroomDialogOpen} onOpenChange={(open) => {
              setStoreDialogOpen(open);
              if (!open) {
                setEditingStore(null);
                setStoreForm({ name: '', address: '', phone: '', email: '' });
              }
            }}>
              <DialogTrigger asChild>
                <Button className="bg-accent hover:bg-accent/90">
                  <Plus className="h-4 w-4 mr-2" />
                  Add Store
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{editingStore ? 'Edit Store' : 'Add Store'}</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleCreateStore} className="space-y-4">
                  <div className="space-y-2">
                    <Label>Store Name</Label>
                    <Input
                      value={showroomForm.name}
                      onChange={(e) => setStoreForm({ ...showroomForm, name: e.target.value })}
                      placeholder="London Store"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Address</Label>
                    <Input
                      value={showroomForm.address}
                      onChange={(e) => setStoreForm({ ...showroomForm, address: e.target.value })}
                      placeholder="123 High Street, London"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Phone</Label>
                    <Input
                      value={showroomForm.phone}
                      onChange={(e) => setStoreForm({ ...showroomForm, phone: e.target.value })}
                      placeholder="020 1234 5678"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Email</Label>
                    <Input
                      type="email"
                      value={showroomForm.email}
                      onChange={(e) => setStoreForm({ ...showroomForm, email: e.target.value })}
                      placeholder="london@tilestation.co.uk"
                    />
                  </div>
                  <Button type="submit" className="w-full bg-accent hover:bg-accent/90">
                    {editingStore ? 'Update Store' : 'Add Store'}
                  </Button>
                </form>
              </DialogContent>
            </Dialog>
          </div>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {showrooms.length === 0 ? (
              <Card className="col-span-full p-8 text-center text-muted-foreground">
                No showrooms yet. Add your first showroom!
              </Card>
            ) : (
              showrooms.map(showroom => {
                const customerCount = stats?.showroom_stats?.find(s => s.showroom_id === showroom.id)?.customer_count || 0;
                return (
                  <Card key={showroom.id} className="p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Store className="h-5 w-5 text-purple-600" />
                        <h3 className="font-semibold">{showroom.name}</h3>
                      </div>
                      <div className="flex gap-1">
                        <Button size="sm" variant="ghost" onClick={() => handleEditStore(showroom)}>
                          Edit
                        </Button>
                        <Button size="sm" variant="ghost" className="text-red-600" onClick={() => handleDeleteStore(showroom.id)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                    {showroom.address && (
                      <p className="text-sm text-muted-foreground mb-1">{showroom.address}</p>
                    )}
                    {showroom.phone && (
                      <p className="text-sm text-muted-foreground mb-1">📞 {showroom.phone}</p>
                    )}
                    {showroom.email && (
                      <p className="text-sm text-muted-foreground mb-1">✉️ {showroom.email}</p>
                    )}
                    <div className="mt-3 pt-3 border-t">
                      <p className="text-sm">
                        <Users className="h-4 w-4 inline mr-1" />
                        <span className="font-medium">{customerCount}</span> customers
                      </p>
                    </div>
                  </Card>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Customers Tab */}
      {activeTab === 'customers' && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium">Customer</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Company</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Store</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Marketing</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {customers.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                      No customers yet.
                    </td>
                  </tr>
                ) : (
                  customers.map(customer => (
                    <tr key={customer.email}>
                      <td className="px-4 py-3">
                        <p className="font-medium">{customer.name}</p>
                        <p className="text-sm text-muted-foreground">{customer.email}</p>
                      </td>
                      <td className="px-4 py-3 text-sm">{customer.company_name || '-'}</td>
                      <td className="px-4 py-3">
                        <select
                          className="px-2 py-1 border rounded text-sm"
                          value={customer.showroom_id || ''}
                          onChange={(e) => handleAssignStore(customer.email, e.target.value)}
                        >
                          <option value="">No showroom</option>
                          {showrooms.map(s => (
                            <option key={s.id} value={s.id}>{s.name}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        {customer.marketing_opt_in !== false ? (
                          <span className="text-green-600 text-sm">✓ Opted In</span>
                        ) : (
                          <span className="text-red-600 text-sm">✗ Opted Out</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
};

export default Marketing;
