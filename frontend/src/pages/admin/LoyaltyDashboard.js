import React, { useState, useEffect } from 'react';
import { Gift, Star, Trophy, TrendingUp, Users, Coins, Award, ChevronRight, Search } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const TIER_ICONS = {
  bronze: '🥉',
  silver: '🥈',
  gold: '🥇',
  platinum: '💎'
};

const LoyaltyDashboard = () => {
  const [stats, setStats] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResult, setSearchResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [enrolling, setEnrolling] = useState(false);
  const [enrollForm, setEnrollForm] = useState({ customer_id: '', email: '', name: '' });
  const [recentTransactions, setRecentTransactions] = useState([]);

  useEffect(() => {
    fetchStats();
    fetchRecentTransactions();
  }, []);

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/loyalty/stats`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (e) {
      console.error('Error fetching loyalty stats:', e);
    } finally {
      setLoading(false);
    }
  };

  const fetchRecentTransactions = async () => {
    try {
      // Get all recent transactions across all customers
      const res = await fetch(`${API_URL}/api/loyalty/recent-activity?limit=10`);
      if (res.ok) {
        const data = await res.json();
        setRecentTransactions(data.transactions || []);
      }
    } catch (e) {
      console.log('Recent transactions not available');
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    try {
      const res = await fetch(`${API_URL}/api/loyalty/account/${encodeURIComponent(searchQuery)}`);
      if (res.ok) {
        const data = await res.json();
        setSearchResult(data);
      }
    } catch (e) {
      toast.error('Error searching customer');
    }
  };

  const handleEnroll = async (e) => {
    e.preventDefault();
    if (!enrollForm.customer_id || !enrollForm.email || !enrollForm.name) {
      toast.error('Please fill all fields');
      return;
    }

    setEnrolling(true);
    try {
      const res = await fetch(`${API_URL}/api/loyalty/enroll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(enrollForm)
      });

      if (res.ok) {
        toast.success('Customer enrolled successfully!');
        setEnrollForm({ customer_id: '', email: '', name: '' });
        fetchStats();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to enroll customer');
      }
    } catch (e) {
      toast.error('Failed to enroll customer');
    } finally {
      setEnrolling(false);
    }
  };

  const formatNumber = (num) => {
    return new Intl.NumberFormat('en-GB').format(num);
  };

  if (loading) {
    return (
      <div className="p-6 animate-pulse">
        <div className="h-8 bg-gray-200 rounded w-64 mb-6"></div>
        <div className="grid grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <div key={i} className="h-32 bg-gray-200 rounded"></div>)}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 bg-gray-50 min-h-screen" data-testid="loyalty-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Gift className="h-7 w-7 text-amber-500" />
            Loyalty Program
          </h1>
          <p className="text-gray-500 mt-1">Reward your customers for their loyalty</p>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card className="bg-gradient-to-br from-purple-500 to-purple-600 text-white">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-purple-100">Total Members</p>
                  <p className="text-3xl font-bold">{formatNumber(stats.total_enrolled)}</p>
                </div>
                <Users className="h-10 w-10 text-purple-200" />
              </div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-blue-500 to-blue-600 text-white">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-blue-100">Active (30d)</p>
                  <p className="text-3xl font-bold">{formatNumber(stats.active_members)}</p>
                </div>
                <TrendingUp className="h-10 w-10 text-blue-200" />
              </div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-amber-500 to-amber-600 text-white">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-amber-100">Points in Circulation</p>
                  <p className="text-3xl font-bold">{formatNumber(stats.points.total_in_circulation)}</p>
                </div>
                <Coins className="h-10 w-10 text-amber-200" />
              </div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-green-500 to-green-600 text-white">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-green-100">Points Redeemed</p>
                  <p className="text-3xl font-bold">{formatNumber(stats.points.total_redeemed)}</p>
                </div>
                <Award className="h-10 w-10 text-green-200" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Tier Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Trophy className="h-5 w-5 text-amber-500" />
              Tier Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.tier_distribution?.map((tier) => (
              <div key={tier.tier} className="flex items-center justify-between py-3 border-b last:border-0">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{TIER_ICONS[tier.tier]}</span>
                  <div>
                    <p className="font-medium" style={{ color: tier.color }}>{tier.name}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-bold text-gray-900">{tier.count}</p>
                  <p className="text-xs text-gray-500">members</p>
                </div>
              </div>
            ))}

            {/* Program Info */}
            <div className="mt-4 pt-4 border-t bg-gray-50 rounded-lg p-3">
              <p className="text-sm text-gray-600 mb-2">
                <strong>Earn:</strong> {stats?.points_per_pound || 10} points per £1 spent
              </p>
              <p className="text-sm text-gray-600">
                <strong>Redeem:</strong> {stats?.redemption_rate || 100} points = £1 discount
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Search Customer */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="h-5 w-5 text-blue-500" />
              Look Up Customer
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSearch} className="mb-4">
              <div className="flex gap-2">
                <Input
                  placeholder="Enter customer ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <Button type="submit">Search</Button>
              </div>
            </form>

            {searchResult && (
              <div className="border rounded-lg p-4 bg-gray-50">
                {searchResult.enrolled ? (
                  <>
                    <div className="flex items-center gap-3 mb-4">
                      <span className="text-3xl">{TIER_ICONS[searchResult.tier?.tier_id]}</span>
                      <div>
                        <p className="font-bold text-lg" style={{ color: searchResult.tier?.color }}>
                          {searchResult.tier?.name} Member
                        </p>
                        <p className="text-sm text-gray-500">ID: {searchResult.customer_id}</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-white rounded p-3">
                        <p className="text-xs text-gray-500">Current Points</p>
                        <p className="text-xl font-bold text-amber-600">{formatNumber(searchResult.current_points)}</p>
                      </div>
                      <div className="bg-white rounded p-3">
                        <p className="text-xs text-gray-500">Lifetime Points</p>
                        <p className="text-xl font-bold text-purple-600">{formatNumber(searchResult.lifetime_points)}</p>
                      </div>
                    </div>
                    {searchResult.next_tier?.next_tier && (
                      <div className="mt-3 text-sm text-gray-600">
                        <strong>{formatNumber(searchResult.next_tier.points_needed)}</strong> points to {searchResult.next_tier.next_tier}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-center py-4">
                    <p className="text-gray-500 mb-2">Not enrolled in loyalty program</p>
                    <Button 
                      size="sm" 
                      onClick={() => setEnrollForm({ ...enrollForm, customer_id: searchQuery })}
                    >
                      Enroll Now
                    </Button>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Enroll New Customer */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Star className="h-5 w-5 text-green-500" />
              Enroll Customer
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleEnroll} className="space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-700">Customer ID *</label>
                <Input
                  value={enrollForm.customer_id}
                  onChange={(e) => setEnrollForm({ ...enrollForm, customer_id: e.target.value })}
                  placeholder="Enter customer ID"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">Name *</label>
                <Input
                  value={enrollForm.name}
                  onChange={(e) => setEnrollForm({ ...enrollForm, name: e.target.value })}
                  placeholder="Customer name"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">Email *</label>
                <Input
                  type="email"
                  value={enrollForm.email}
                  onChange={(e) => setEnrollForm({ ...enrollForm, email: e.target.value })}
                  placeholder="customer@email.com"
                />
              </div>
              <Button type="submit" className="w-full" disabled={enrolling}>
                {enrolling ? 'Enrolling...' : 'Enroll in Loyalty Program'}
              </Button>
            </form>

            <div className="mt-4 pt-4 border-t">
              <h4 className="font-medium text-gray-900 mb-2">Tier Benefits</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">🥉 Bronze</span>
                  <span>0% discount</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">🥈 Silver (5K pts)</span>
                  <span>5% discount</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">🥇 Gold (15K pts)</span>
                  <span>10% discount</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">💎 Platinum (50K pts)</span>
                  <span>15% discount</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      {recentTransactions.length > 0 && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-green-500" />
              Recent Points Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {recentTransactions.map((tx, idx) => (
                <div key={idx} className="flex items-center justify-between py-2 border-b last:border-0">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                      tx.type === 'earn' ? 'bg-green-100 text-green-600' : 'bg-amber-100 text-amber-600'
                    }`}>
                      {tx.type === 'earn' ? '+' : '-'}
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">{tx.customer_id}</p>
                      <p className="text-sm text-gray-500">
                        {tx.invoice_no ? `Invoice #${tx.invoice_no}` : tx.type === 'redeem' ? 'Points Redeemed' : 'Points Earned'}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className={`font-bold ${tx.type === 'earn' ? 'text-green-600' : 'text-amber-600'}`}>
                      {tx.type === 'earn' ? '+' : ''}{formatNumber(tx.points)} pts
                    </p>
                    {tx.amount && (
                      <p className="text-xs text-gray-500">£{tx.amount.toFixed(2)} spent</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default LoyaltyDashboard;
