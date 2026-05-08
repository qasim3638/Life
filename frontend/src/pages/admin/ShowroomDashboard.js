import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { 
  Package, AlertTriangle, ShoppingCart, PoundSterling, TrendingUp, 
  Building2, Trophy, Star, Users, Target, Download, Bell,
  ArrowUp, ArrowDown, Calendar, Filter, RefreshCw, Store
} from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, LineChart, Line, Legend 
} from 'recharts';
import { useAuth } from '../../contexts/AuthContext';

const COLORS = ['#f97316', '#3b82f6', '#22c55e', '#a855f7', '#ef4444', '#06b6d4', '#ec4899', '#14b8a6'];

export const ShowroomDashboard = () => {
  const { user } = useAuth();
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [showrooms, setStores] = useState([]);
  const [selectedStore, setSelectedStore] = useState('all');
  const [period, setPeriod] = useState('today');
  const [analytics, setAnalytics] = useState(null);
  const [bestSellers, setBestSellers] = useState(null);
  const [staffPerformance, setStaffPerformance] = useState([]);
  const [lowStockProducts, setLowStockProducts] = useState([]);
  const [alerts, setAlerts] = useState([]);
  
  // Sales Target State (loaded from localStorage - set on main Dashboard)
  const [monthlyTarget, setMonthlyTarget] = useState(0);
  const [weeklyTarget, setWeeklyTarget] = useState(0);
  const [dailyTarget, setDailyTarget] = useState(0);
  
  // Bonus Target State (loaded from localStorage - set on main Dashboard)
  const [monthlyBonusTarget, setMonthlyBonusTarget] = useState(0);
  const [weeklyBonusTarget, setWeeklyBonusTarget] = useState(0);
  const [dailyBonusTarget, setDailyBonusTarget] = useState(0);
  
  const isSuperAdmin = user?.role === 'super_admin';
  const isManager = user?.role === 'manager';
  const userStoreId = user?.showroom_id;

  // Refetch data on navigation or page focus
  useEffect(() => {
    fetchInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, location.key]);

  // Data sync listeners
  useEffect(() => {
    const handleFocus = () => {
      fetchDashboardData();
    };
    
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchDashboardData();
      }
    };
    
    const handleDataSync = () => {
      console.log('[ShowroomDashboard] Data sync event received');
      fetchDashboardData();
    };
    
    const handleStorageChange = (e) => {
      if (e.key === 'dataSync') {
        fetchDashboardData();
      }
    };
    
    window.addEventListener('focus', handleFocus);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('dataSync', handleDataSync);
    window.addEventListener('storage', handleStorageChange);
    
    return () => {
      window.removeEventListener('focus', handleFocus);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('dataSync', handleDataSync);
      window.removeEventListener('storage', handleStorageChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedStore, period, showrooms]);

  useEffect(() => {
    if (showrooms.length > 0) {
      fetchDashboardData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedStore, period, showrooms]);

  const fetchInitialData = async () => {
    try {
      const showroomsRes = await api.getStores();
      setStores(showroomsRes.data || []);
      
      // Set default showroom based on user role
      if (!isSuperAdmin && userStoreId) {
        setSelectedStore(userStoreId);
      }
      
      // Load saved targets from DATABASE
      try {
        const targetsRes = await api.getAllTargetTypes();
        const targets = targetsRes.data;
        
        // Sales Target
        if (targets.sales) {
          setMonthlyTarget(targets.sales.monthly || 0);
          setWeeklyTarget(targets.sales.weekly || 0);
          setDailyTarget(targets.sales.daily || 0);
        }
        
        // Bonus Target
        if (targets.bonus) {
          setMonthlyBonusTarget(targets.bonus.monthly || 0);
          setWeeklyBonusTarget(targets.bonus.weekly || 0);
          setDailyBonusTarget(targets.bonus.daily || 0);
        }
      } catch (targetError) {
        console.log('Failed to load targets from DB, using localStorage fallback');
        // Fallback to localStorage if API fails
        const savedMonthlyTarget = localStorage.getItem('monthlyTarget');
        if (savedMonthlyTarget) {
          const monthly = parseFloat(savedMonthlyTarget);
          setMonthlyTarget(monthly);
          setWeeklyTarget(Math.round(monthly / 4));
          setDailyTarget(Math.round(monthly / 30));
        }
        
        const savedMonthlyBonusTarget = localStorage.getItem('monthlyBonusTarget');
        if (savedMonthlyBonusTarget) {
          const monthlyBonus = parseFloat(savedMonthlyBonusTarget);
          setMonthlyBonusTarget(monthlyBonus);
          setWeeklyBonusTarget(Math.round(monthlyBonus / 4));
          setDailyBonusTarget(Math.round(monthlyBonus / 30));
        }
      }
    } catch (error) {
      console.error('Failed to load showrooms:', error);
    }
  };

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [analyticsRes, bestSellersRes, productsRes] = await Promise.all([
        api.getStoreAnalytics({ period, showroom_id: selectedStore !== 'all' ? selectedStore : undefined }),
        api.getBestSellers({ period, limit: 10 }),
        api.getProducts({ low_stock: true })
      ]);
      
      setAnalytics(analyticsRes.data);
      setBestSellers(bestSellersRes.data);
      setLowStockProducts(productsRes.data?.slice(0, 10) || []);
      
      // Extract staff performance from analytics
      if (analyticsRes.data?.staff_performance) {
        setStaffPerformance(analyticsRes.data.staff_performance);
      }
      
      // Generate alerts
      generateAlerts(analyticsRes.data, productsRes.data);
      
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
      toast.error('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const generateAlerts = (analyticsData, products) => {
    const newAlerts = [];
    
    // Low stock alerts
    const criticalStock = products?.filter(p => p.stock <= 5) || [];
    if (criticalStock.length > 0) {
      newAlerts.push({
        type: 'warning',
        message: `${criticalStock.length} products critically low on stock`,
        icon: AlertTriangle
      });
    }
    
    // Revenue target alert
    const todayRevenue = analyticsData?.total_revenue || 0;
    if (period === 'today' && todayRevenue < dailyTarget * 0.5) {
      newAlerts.push({
        type: 'info',
        message: "Today's revenue is below 50% of daily target",
        icon: Target
      });
    }
    
    setAlerts(newAlerts);
  };

  const exportReport = () => {
    const reportData = {
      period,
      showroom: selectedStore === 'all' ? 'All Stores' : showrooms.find(s => s.id === selectedStore)?.name,
      generated: new Date().toISOString(),
      revenue: analytics?.total_revenue,
      invoices: analytics?.total_invoices,
      bestSellers: bestSellers?.top_by_revenue
    };
    
    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `showroom-report-${period}-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    toast.success('Report exported');
  };

  const formatCurrency = (value) => `£${(value || 0).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const getPercentageChange = (current, previous) => {
    if (!previous || previous === 0) return 0;
    return ((current - previous) / previous * 100).toFixed(1);
  };

  // Calculate current showroom data
  const currentStoreData = selectedStore === 'all' 
    ? analytics 
    : analytics?.showroom_analytics?.find(s => s.showroom_id === selectedStore);

  const todayRevenue = currentStoreData?.total_revenue || analytics?.total_revenue || 0;

  // Leaderboard data
  const leaderboardData = (analytics?.showroom_analytics || [])
    .sort((a, b) => b.total_revenue - a.total_revenue)
    .map((s, i) => ({ ...s, rank: i + 1 }));

  // Daily trend data
  const dailyTrendData = analytics?.daily_breakdown?.map(d => ({
    date: new Date(d.date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }),
    revenue: d.revenue,
    invoices: d.count
  })) || [];

  if (loading && !analytics) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="showroom-dashboard">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-heading font-bold tracking-tight">Store Dashboard</h1>
          <p className="text-muted-foreground">
            {selectedStore === 'all' ? 'All Stores Overview' : showrooms.find(s => s.id === selectedStore)?.name}
          </p>
        </div>
        
        <div className="flex flex-wrap items-center gap-2">
          {/* Period Filter */}
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="px-3 py-2 border rounded-md text-sm"
          >
            <option value="today">Today</option>
            <option value="week">This Week</option>
            <option value="month">This Month</option>
            <option value="quarter">This Quarter</option>
            <option value="year">This Year</option>
          </select>
          
          {/* Store Filter - Only for Super Admin */}
          {isSuperAdmin && (
            <select
              value={selectedStore}
              onChange={(e) => setSelectedStore(e.target.value)}
              className="px-3 py-2 border rounded-md text-sm"
            >
              <option value="all">All Stores</option>
              {showrooms.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          )}
          
          <Button variant="outline" size="sm" onClick={fetchDashboardData}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          
          <Button variant="outline" size="sm" onClick={exportReport}>
            <Download className="h-4 w-4 mr-1" />
            Export
          </Button>
        </div>
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((alert, i) => (
            <div 
              key={i} 
              className={`flex items-center gap-2 p-3 rounded-lg ${
                alert.type === 'warning' ? 'bg-amber-50 text-amber-800 border border-amber-200' :
                alert.type === 'error' ? 'bg-red-50 text-red-800 border border-red-200' :
                'bg-blue-50 text-blue-800 border border-blue-200'
              }`}
            >
              <alert.icon className="h-4 w-4" />
              <span className="text-sm">{alert.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* SALES TARGET & BONUS TARGET SECTION (Display Only - Set on main Dashboard by Super Admin) */}
      {(monthlyTarget > 0 || monthlyBonusTarget > 0) && (
        <Card className="p-4 border-2 border-primary/20 bg-gradient-to-r from-primary/5 to-transparent" data-testid="store-targets-section">
          
          {/* SALES TARGET SECTION */}
          {monthlyTarget > 0 && (
            <Card className="p-4 mb-4 bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200">
              <div className="flex items-center gap-2 mb-4">
                <Target className="h-5 w-5 text-blue-600" />
                <h3 className="font-semibold text-blue-800">Sales Target</h3>
                <span className="text-xs text-blue-500 ml-auto">(Set by Super Admin)</span>
              </div>
              
              {/* Daily, Weekly, Monthly Target Bars */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Daily Target */}
                <div className="p-3 bg-white rounded-lg border border-blue-100">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-blue-700">Daily</span>
                    <span className="text-xs text-blue-600">Target: £{dailyTarget.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-bold text-gray-900">{formatCurrency(todayRevenue)}</span>
                  </div>
                  <div className="h-3 bg-blue-100 rounded-full overflow-hidden">
                    <div 
                      className={`h-full transition-all duration-500 ${
                        dailyTarget > 0 && (todayRevenue / dailyTarget * 100) >= 100 ? 'bg-green-500' : 
                        dailyTarget > 0 && (todayRevenue / dailyTarget * 100) >= 50 ? 'bg-amber-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${Math.min(dailyTarget > 0 ? (todayRevenue / dailyTarget * 100) : 0, 100)}%` }}
                    />
                  </div>
                  <p className="text-xs text-blue-600 text-center mt-1">
                    {dailyTarget > 0 ? `${(todayRevenue / dailyTarget * 100).toFixed(1)}%` : '0%'}
                  </p>
                </div>
                
                {/* Weekly Target */}
                <div className="p-3 bg-white rounded-lg border border-blue-100">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-blue-700">Weekly</span>
                    <span className="text-xs text-blue-600">Target: £{weeklyTarget.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-bold text-gray-900">{formatCurrency(analytics?.week_revenue || todayRevenue * 5)}</span>
                  </div>
                  <div className="h-3 bg-blue-100 rounded-full overflow-hidden">
                    <div 
                      className={`h-full transition-all duration-500 ${
                        weeklyTarget > 0 && ((analytics?.week_revenue || todayRevenue * 5) / weeklyTarget * 100) >= 100 ? 'bg-green-500' : 
                        weeklyTarget > 0 && ((analytics?.week_revenue || todayRevenue * 5) / weeklyTarget * 100) >= 50 ? 'bg-amber-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${Math.min(weeklyTarget > 0 ? ((analytics?.week_revenue || todayRevenue * 5) / weeklyTarget * 100) : 0, 100)}%` }}
                    />
                  </div>
                  <p className="text-xs text-blue-600 text-center mt-1">
                    {weeklyTarget > 0 ? `${((analytics?.week_revenue || todayRevenue * 5) / weeklyTarget * 100).toFixed(1)}%` : '0%'}
                  </p>
                </div>
                
                {/* Monthly Target */}
                <div className="p-3 bg-white rounded-lg border border-blue-100">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-blue-700">Monthly</span>
                    <span className="text-xs text-blue-600">Target: £{monthlyTarget.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-bold text-gray-900">{formatCurrency(analytics?.total_revenue || 0)}</span>
                  </div>
                  <div className="h-3 bg-blue-100 rounded-full overflow-hidden">
                    <div 
                      className={`h-full transition-all duration-500 ${
                        monthlyTarget > 0 && ((analytics?.total_revenue || 0) / monthlyTarget * 100) >= 100 ? 'bg-green-500' : 
                        monthlyTarget > 0 && ((analytics?.total_revenue || 0) / monthlyTarget * 100) >= 50 ? 'bg-amber-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${Math.min(monthlyTarget > 0 ? ((analytics?.total_revenue || 0) / monthlyTarget * 100) : 0, 100)}%` }}
                    />
                  </div>
                  <p className="text-xs text-blue-600 text-center mt-1">
                    {monthlyTarget > 0 ? `${((analytics?.total_revenue || 0) / monthlyTarget * 100).toFixed(1)}%` : '0%'}
                  </p>
                </div>
              </div>
            </Card>
          )}

          {/* BONUS TARGET SECTION */}
          {monthlyBonusTarget > 0 && (
            <Card className="p-4 bg-gradient-to-r from-purple-50 to-pink-50 border-purple-200">
              <div className="flex items-center gap-2 mb-4">
                <Trophy className="h-5 w-5 text-purple-600" />
                <h3 className="font-semibold text-purple-800">Bonus Target</h3>
                <span className="text-xs text-purple-500 ml-auto">(Set by Super Admin)</span>
              </div>
              
              {/* Daily, Weekly, Monthly Bonus Target Bars */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Daily Bonus Target */}
                <div className="p-3 bg-white rounded-lg border border-purple-100">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-purple-700">Daily</span>
                    <span className="text-xs text-purple-600">Target: £{dailyBonusTarget.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-bold text-gray-900">{formatCurrency(todayRevenue)}</span>
                  </div>
                  <div className="h-3 bg-purple-100 rounded-full overflow-hidden">
                    <div 
                      className={`h-full transition-all duration-500 ${
                        dailyBonusTarget > 0 && (todayRevenue / dailyBonusTarget * 100) >= 100 ? 'bg-green-500' : 
                        dailyBonusTarget > 0 && (todayRevenue / dailyBonusTarget * 100) >= 50 ? 'bg-amber-500' : 'bg-purple-500'
                      }`}
                      style={{ width: `${Math.min(dailyBonusTarget > 0 ? (todayRevenue / dailyBonusTarget * 100) : 0, 100)}%` }}
                    />
                  </div>
                  <p className="text-xs text-purple-600 text-center mt-1">
                    {dailyBonusTarget > 0 ? `${(todayRevenue / dailyBonusTarget * 100).toFixed(1)}%` : '0%'}
                  </p>
                </div>
                
                {/* Weekly Bonus Target */}
                <div className="p-3 bg-white rounded-lg border border-purple-100">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-purple-700">Weekly</span>
                    <span className="text-xs text-purple-600">Target: £{weeklyBonusTarget.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-bold text-gray-900">{formatCurrency(analytics?.week_revenue || todayRevenue * 5)}</span>
                  </div>
                  <div className="h-3 bg-purple-100 rounded-full overflow-hidden">
                    <div 
                      className={`h-full transition-all duration-500 ${
                        weeklyBonusTarget > 0 && ((analytics?.week_revenue || todayRevenue * 5) / weeklyBonusTarget * 100) >= 100 ? 'bg-green-500' : 
                        weeklyBonusTarget > 0 && ((analytics?.week_revenue || todayRevenue * 5) / weeklyBonusTarget * 100) >= 50 ? 'bg-amber-500' : 'bg-purple-500'
                      }`}
                      style={{ width: `${Math.min(weeklyBonusTarget > 0 ? ((analytics?.week_revenue || todayRevenue * 5) / weeklyBonusTarget * 100) : 0, 100)}%` }}
                    />
                  </div>
                  <p className="text-xs text-purple-600 text-center mt-1">
                    {weeklyBonusTarget > 0 ? `${((analytics?.week_revenue || todayRevenue * 5) / weeklyBonusTarget * 100).toFixed(1)}%` : '0%'}
                  </p>
                </div>
                
                {/* Monthly Bonus Target */}
                <div className="p-3 bg-white rounded-lg border border-purple-100">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-purple-700">Monthly</span>
                    <span className="text-xs text-purple-600">Target: £{monthlyBonusTarget.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-bold text-gray-900">{formatCurrency(analytics?.total_revenue || 0)}</span>
                  </div>
                  <div className="h-3 bg-purple-100 rounded-full overflow-hidden">
                    <div 
                      className={`h-full transition-all duration-500 ${
                        monthlyBonusTarget > 0 && ((analytics?.total_revenue || 0) / monthlyBonusTarget * 100) >= 100 ? 'bg-green-500' : 
                        monthlyBonusTarget > 0 && ((analytics?.total_revenue || 0) / monthlyBonusTarget * 100) >= 50 ? 'bg-amber-500' : 'bg-purple-500'
                      }`}
                      style={{ width: `${Math.min(monthlyBonusTarget > 0 ? ((analytics?.total_revenue || 0) / monthlyBonusTarget * 100) : 0, 100)}%` }}
                    />
                  </div>
                  <p className="text-xs text-purple-600 text-center mt-1">
                    {monthlyBonusTarget > 0 ? `${((analytics?.total_revenue || 0) / monthlyBonusTarget * 100).toFixed(1)}%` : '0%'}
                  </p>
                </div>
              </div>
            </Card>
          )}
        </Card>
      )}

      {/* No Targets Set Message */}
      {monthlyTarget === 0 && monthlyBonusTarget === 0 && (
        <Card className="p-4 bg-gray-50 border-dashed border-2 border-gray-300">
          <div className="flex items-center gap-2 text-gray-500">
            <Target className="h-5 w-5" />
            <span className="text-sm">No targets set. Super Admin can set Sales and Bonus targets from the main Dashboard.</span>
          </div>
        </Card>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Products</p>
              <p className="text-2xl font-bold">{analytics?.total_products || bestSellers?.total_products || 0}</p>
            </div>
            <Package className="h-8 w-8 text-blue-600" />
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Low Stock Items</p>
              <p className="text-2xl font-bold">{analytics?.low_stock_count || 0}</p>
            </div>
            <AlertTriangle className="h-8 w-8 text-amber-600" />
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Orders</p>
              <p className="text-2xl font-bold">{analytics?.total_invoices || 0}</p>
            </div>
            <ShoppingCart className="h-8 w-8 text-emerald-600" />
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Revenue</p>
              <p className="text-2xl font-bold">{formatCurrency(analytics?.total_revenue)}</p>
            </div>
            <PoundSterling className="h-8 w-8 text-purple-600" />
          </div>
        </Card>
      </div>

      {/* Profit Stats - Super Admin Only */}
      {isSuperAdmin && bestSellers?.show_profit && (
        <div className="grid grid-cols-3 gap-4">
          <Card className="p-4 bg-green-50 border-green-200">
            <p className="text-sm text-green-700">Total Revenue</p>
            <p className="text-xl font-bold text-green-800">{formatCurrency(bestSellers?.total_revenue)}</p>
          </Card>
          <Card className="p-4 bg-red-50 border-red-200">
            <p className="text-sm text-red-700">Total Cost</p>
            <p className="text-xl font-bold text-red-800">{formatCurrency(bestSellers?.total_cost)}</p>
          </Card>
          <Card className="p-4 bg-blue-50 border-blue-200">
            <p className="text-sm text-blue-700">Total Profit</p>
            <p className="text-xl font-bold text-blue-800">{formatCurrency(bestSellers?.total_profit)}</p>
            <p className="text-xs text-blue-600">Margin: {bestSellers?.overall_margin}%</p>
          </Card>
        </div>
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Store Leaderboard - Super Admin Only */}
        {isSuperAdmin && selectedStore === 'all' && (
          <Card className="p-4">
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <Trophy className="h-5 w-5 text-amber-500" />
              Store Leaderboard
            </h3>
            <div className="space-y-3">
              {leaderboardData.map((showroom, i) => (
                <div 
                  key={showroom.showroom_id}
                  className={`flex items-center justify-between p-3 rounded-lg ${
                    i === 0 ? 'bg-amber-50 border border-amber-200' :
                    i === 1 ? 'bg-gray-100 border border-gray-200' :
                    i === 2 ? 'bg-orange-50 border border-orange-200' :
                    'bg-gray-50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className={`text-lg font-bold ${
                      i === 0 ? 'text-amber-600' : i === 1 ? 'text-gray-600' : i === 2 ? 'text-orange-600' : 'text-gray-500'
                    }`}>
                      #{showroom.rank}
                    </span>
                    {i === 0 && <Trophy className="h-5 w-5 text-amber-500" />}
                    <div>
                      <p className="font-medium">{showroom.showroom_name}</p>
                      <p className="text-xs text-muted-foreground">{showroom.invoice_count} invoices</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-bold">{formatCurrency(showroom.total_revenue)}</p>
                    <p className="text-xs text-muted-foreground">{showroom.percentage_of_total?.toFixed(1)}%</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Revenue Chart */}
        <Card className="p-4">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-blue-600" />
            Revenue Trend
          </h3>
          {dailyTrendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={dailyTrendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip formatter={(value) => formatCurrency(value)} />
                <Line type="monotone" dataKey="revenue" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-muted-foreground">
              No data available
            </div>
          )}
        </Card>

        {/* Best Sellers */}
        <Card className="p-4">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <Star className="h-5 w-5 text-amber-500" />
            Top Selling Products
          </h3>
          <div className="space-y-2">
            {bestSellers?.top_by_revenue?.slice(0, 5).map((product, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-muted-foreground">#{i + 1}</span>
                  <div>
                    <p className="text-sm font-medium truncate max-w-[200px]">{product.name}</p>
                    <p className="text-xs text-muted-foreground">{product.quantity} sold</p>
                  </div>
                </div>
                <p className="font-semibold text-green-600">{formatCurrency(product.revenue)}</p>
              </div>
            )) || (
              <p className="text-sm text-muted-foreground text-center py-4">No sales data</p>
            )}
          </div>
        </Card>

        {/* Low Stock Alerts */}
        <Card className="p-4">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            Low Stock Alerts
          </h3>
          <div className="space-y-2 max-h-[250px] overflow-y-auto">
            {lowStockProducts.length > 0 ? lowStockProducts.map((product, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-red-50 rounded-lg border border-red-200">
                <div>
                  <p className="text-sm font-medium truncate max-w-[200px]">{product.name}</p>
                  <p className="text-xs text-muted-foreground">{product.sku}</p>
                </div>
                <div className="text-right">
                  <p className={`text-sm font-bold ${product.stock <= 5 ? 'text-red-600' : 'text-amber-600'}`}>
                    {product.stock} left
                  </p>
                  <p className="text-xs text-muted-foreground">Reorder: {product.reorder_level}</p>
                </div>
              </div>
            )) : (
              <p className="text-sm text-green-600 text-center py-4">✓ All products well stocked</p>
            )}
          </div>
        </Card>

        {/* Store Comparison Pie Chart - Super Admin */}
        {isSuperAdmin && selectedStore === 'all' && (
          <Card className="p-4">
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <Building2 className="h-5 w-5 text-purple-600" />
              Revenue Distribution
            </h3>
            {leaderboardData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={leaderboardData}
                    dataKey="total_revenue"
                    nameKey="showroom_name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ showroom_name, percentage_of_total }) => 
                      `${showroom_name?.split(' ')[0]}: ${percentage_of_total?.toFixed(0)}%`
                    }
                  >
                    {leaderboardData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => formatCurrency(value)} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                No data available
              </div>
            )}
          </Card>
        )}

        {/* Staff Performance - If available */}
        {staffPerformance.length > 0 && (
          <Card className="p-4">
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <Users className="h-5 w-5 text-blue-600" />
              Staff Performance
            </h3>
            <div className="space-y-2">
              {staffPerformance.slice(0, 5).map((staff, i) => (
                <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-muted-foreground">#{i + 1}</span>
                    <p className="text-sm font-medium">{staff.name}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold">{formatCurrency(staff.revenue)}</p>
                    <p className="text-xs text-muted-foreground">{staff.invoices} invoices</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>

    </div>
  );
};

export default ShowroomDashboard;
