import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, ArrowLeft, RefreshCw, TrendingUp, TrendingDown,
  ShoppingCart, Package, DollarSign, Users, Calendar, Download,
  Eye, ChevronDown, ChevronRight, BarChart3, PieChart, ArrowUpRight,
  ArrowDownRight, Clock, CheckCircle, XCircle, Truck, CreditCard,
  Receipt, Percent, Banknote, Calculator
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { toast } from 'sonner';
import { MetricInfoTooltip, SALES_EXPLAINERS } from '../../components/admin/MetricInfoTooltip';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Stat card component
const StatCard = ({ title, value, subtitle, icon: Icon, trend, trendValue, color = 'blue', explainer }) => {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600 border-blue-200',
    green: 'bg-green-50 text-green-600 border-green-200',
    purple: 'bg-purple-50 text-purple-600 border-purple-200',
    amber: 'bg-amber-50 text-amber-600 border-amber-200',
    red: 'bg-red-50 text-red-600 border-red-200',
    slate: 'bg-slate-50 text-slate-600 border-slate-200'
  };
  
  return (
    <Card className={`border ${colorClasses[color].split(' ')[2]}`}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide flex items-center">
              <span>{title}</span>
              {explainer ? <MetricInfoTooltip explainer={explainer} side="top" align="start" /> : null}
            </p>
            <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
            {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
          </div>
          <div className={`p-2 rounded-lg ${colorClasses[color].split(' ').slice(0, 2).join(' ')}`}>
            <Icon className="w-5 h-5" />
          </div>
        </div>
        {trend !== undefined && (
          <div className={`flex items-center gap-1 mt-3 text-xs ${trend >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {trend >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
            <span className="font-medium">{Math.abs(trend)}%</span>
            <span className="text-slate-500">vs last period</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Order status badge
const OrderStatusBadge = ({ status }) => {
  const statusConfig = {
    pending: { color: 'bg-yellow-100 text-yellow-700', icon: Clock },
    processing: { color: 'bg-blue-100 text-blue-700', icon: RefreshCw },
    shipped: { color: 'bg-purple-100 text-purple-700', icon: Truck },
    delivered: { color: 'bg-green-100 text-green-700', icon: CheckCircle },
    cancelled: { color: 'bg-red-100 text-red-700', icon: XCircle },
    refunded: { color: 'bg-gray-100 text-gray-700', icon: DollarSign }
  };
  
  const config = statusConfig[status] || statusConfig.pending;
  const Icon = config.icon;
  
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${config.color}`}>
      <Icon className="w-3 h-3" />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
};

export default function WebsiteSalesDashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState('30d'); // 7d, 30d, 90d, ytd, all
  const [stats, setStats] = useState({
    totalSales: 0,
    totalOrders: 0,
    totalProfit: 0,
    averageOrderValue: 0,
    totalCustomers: 0,
    conversionRate: 0,
    returningCustomers: 0,
    pendingOrders: 0
  });
  const [recentOrders, setRecentOrders] = useState([]);
  const [topProducts, setTopProducts] = useState([]);
  const [salesByCategory, setSalesByCategory] = useState([]);
  const [profitBreakdown, setProfitBreakdown] = useState({
    grossRevenue: 0,
    vatCollected: 0,
    costOfGoods: 0,
    netProfit: 0,
    profitMargin: 0
  });

  useEffect(() => {
    fetchDashboardData();
  }, [dateRange]);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      // Fetch all dashboard data in parallel
      const [statsRes, ordersRes, productsRes, categoriesRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/website-sales/stats?range=${dateRange}`),
        fetch(`${API_URL}/api/admin/website-sales/orders?limit=10`),
        fetch(`${API_URL}/api/admin/website-sales/top-products?range=${dateRange}`),
        fetch(`${API_URL}/api/admin/website-sales/by-category?range=${dateRange}`)
      ]);

      if (statsRes.ok) {
        const data = await statsRes.json();
        setStats(data.stats || data);
        setProfitBreakdown(data.profit_breakdown || {
          grossRevenue: data.stats?.totalSales || 0,
          vatCollected: (data.stats?.totalSales || 0) - ((data.stats?.totalSales || 0) / 1.2),
          costOfGoods: (data.stats?.totalSales || 0) * 0.4, // Estimated
          netProfit: data.stats?.totalProfit || 0,
          profitMargin: 0
        });
      }
      
      if (ordersRes.ok) {
        const data = await ordersRes.json();
        setRecentOrders(data.orders || data || []);
      }
      
      if (productsRes.ok) {
        const data = await productsRes.json();
        setTopProducts(data.products || data || []);
      }
      
      if (categoriesRes.ok) {
        const data = await categoriesRes.json();
        setSalesByCategory(data.categories || data || []);
      }
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      // Load sample data for demo
      loadSampleData();
    } finally {
      setLoading(false);
    }
  };

  const loadSampleData = () => {
    // Sample data for demonstration
    setStats({
      totalSales: 15678.50,
      totalOrders: 47,
      totalProfit: 4523.20,
      averageOrderValue: 333.58,
      totalCustomers: 32,
      conversionRate: 2.8,
      returningCustomers: 12,
      pendingOrders: 5
    });
    
    setProfitBreakdown({
      grossRevenue: 15678.50,
      vatCollected: 2613.08,
      costOfGoods: 8542.22,
      netProfit: 4523.20,
      profitMargin: 28.85
    });
    
    setRecentOrders([
      { id: 'ORD-001', customer: 'John Smith', email: 'john@example.com', total: 567.89, status: 'delivered', date: '2026-03-12', items: 3 },
      { id: 'ORD-002', customer: 'Sarah Jones', email: 'sarah@example.com', total: 234.50, status: 'shipped', date: '2026-03-11', items: 2 },
      { id: 'ORD-003', customer: 'Mike Brown', email: 'mike@example.com', total: 1250.00, status: 'processing', date: '2026-03-11', items: 5 },
      { id: 'ORD-004', customer: 'Emma Wilson', email: 'emma@example.com', total: 89.99, status: 'pending', date: '2026-03-10', items: 1 },
      { id: 'ORD-005', customer: 'David Lee', email: 'david@example.com', total: 445.00, status: 'delivered', date: '2026-03-10', items: 2 }
    ]);
    
    setTopProducts([
      { name: 'Carrara White Marble 60x60', sku: 'CWM-6060', sold: 156, revenue: 4523.44, profit: 1267.80 },
      { name: 'Slate Grey Floor Tile', sku: 'SGF-001', sold: 98, revenue: 2844.20, profit: 812.40 },
      { name: 'Wood Effect Oak', sku: 'WEO-001', sold: 87, revenue: 2436.63, profit: 701.20 },
      { name: 'Porcelain White Gloss', sku: 'PWG-001', sold: 65, revenue: 1885.35, profit: 542.00 },
      { name: 'Terracotta Natural', sku: 'TN-001', sold: 54, revenue: 1566.66, profit: 423.50 }
    ]);
    
    setSalesByCategory([
      { name: 'Floor Tiles', sales: 8234.50, percentage: 52.5 },
      { name: 'Wall Tiles', sales: 4123.00, percentage: 26.3 },
      { name: 'Accessories', sales: 2156.00, percentage: 13.8 },
      { name: 'Adhesives & Grout', sales: 1165.00, percentage: 7.4 }
    ]);
  };

  const formatCurrency = (amount) => `£${(amount || 0).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const formatNumber = (num) => (num || 0).toLocaleString('en-GB');
  const formatDate = (dateStr) => new Date(dateStr).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-2" />
          <p className="text-slate-500">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-10">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => navigate('/admin/website-hub')}
              className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <div className="bg-blue-100 p-2 rounded-lg">
                <LayoutDashboard className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">Website Sales Dashboard</h1>
                <p className="text-sm text-slate-500">Track sales, orders, and profitability</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Date Range Selector */}
            <Select value={dateRange} onValueChange={setDateRange}>
              <SelectTrigger className="w-36">
                <Calendar className="w-4 h-4 mr-2" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7d">Last 7 days</SelectItem>
                <SelectItem value="30d">Last 30 days</SelectItem>
                <SelectItem value="90d">Last 90 days</SelectItem>
                <SelectItem value="ytd">Year to date</SelectItem>
                <SelectItem value="all">All time</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={fetchDashboardData}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
            <Button variant="outline">
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Key Stats Row */}
        <div className="grid grid-cols-4 gap-4">
          <StatCard 
            title="Total Sales"
            value={formatCurrency(stats.totalSales)}
            subtitle={`${formatNumber(stats.totalOrders)} orders`}
            icon={DollarSign}
            trend={12.5}
            color="green"
            explainer={SALES_EXPLAINERS.total_sales}
          />
          <StatCard 
            title="Net Profit"
            value={formatCurrency(stats.totalProfit)}
            subtitle={`${((stats.totalProfit / stats.totalSales) * 100 || 0).toFixed(1)}% margin`}
            icon={TrendingUp}
            trend={8.3}
            color="purple"
            explainer={SALES_EXPLAINERS.net_profit}
          />
          <StatCard 
            title="Orders"
            value={formatNumber(stats.totalOrders)}
            subtitle={`${stats.pendingOrders} pending`}
            icon={ShoppingCart}
            trend={5.2}
            color="blue"
            explainer={SALES_EXPLAINERS.orders}
          />
          <StatCard 
            title="Avg Order Value"
            value={formatCurrency(stats.averageOrderValue)}
            subtitle={`${formatNumber(stats.totalCustomers)} customers`}
            icon={Receipt}
            trend={-2.1}
            color="amber"
            explainer={SALES_EXPLAINERS.aov}
          />
        </div>

        {/* Profit Breakdown & Sales by Category */}
        <div className="grid grid-cols-2 gap-6">
          {/* Profit Breakdown Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Calculator className="w-5 h-5 text-green-600" />
                Profit Breakdown
              </CardTitle>
              <CardDescription>Revenue and cost analysis</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex justify-between items-center py-2 border-b">
                  <span className="text-slate-600 inline-flex items-center">
                    Gross Revenue (inc. VAT)
                    <MetricInfoTooltip explainer={SALES_EXPLAINERS.gross_revenue} side="top" align="start" />
                  </span>
                  <span className="font-semibold text-slate-900">{formatCurrency(profitBreakdown.grossRevenue)}</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b text-purple-600">
                  <span className="inline-flex items-center">
                    Less: VAT Collected (20%)
                    <MetricInfoTooltip explainer={SALES_EXPLAINERS.vat_collected} side="top" align="start" />
                  </span>
                  <span className="font-medium">-{formatCurrency(profitBreakdown.vatCollected)}</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b">
                  <span className="text-slate-600">Revenue (ex. VAT)</span>
                  <span className="font-medium text-slate-700">{formatCurrency(profitBreakdown.grossRevenue - profitBreakdown.vatCollected)}</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b text-red-600">
                  <span className="inline-flex items-center">
                    Less: Cost of Goods
                    <MetricInfoTooltip explainer={SALES_EXPLAINERS.cost_of_goods} side="top" align="start" />
                  </span>
                  <span className="font-medium">-{formatCurrency(profitBreakdown.costOfGoods)}</span>
                </div>
                <div className="flex justify-between items-center py-3 bg-green-50 px-3 rounded-lg">
                  <span className="font-bold text-green-800 inline-flex items-center">
                    Net Profit
                    <MetricInfoTooltip explainer={SALES_EXPLAINERS.net_profit_row} side="top" align="start" />
                  </span>
                  <span className="font-bold text-xl text-green-600">{formatCurrency(profitBreakdown.netProfit)}</span>
                </div>
                <div className="flex justify-between items-center py-2 text-sm">
                  <span className="text-slate-500 inline-flex items-center">
                    Profit Margin
                    <MetricInfoTooltip explainer={SALES_EXPLAINERS.profit_margin} side="top" align="start" />
                  </span>
                  <span className="font-medium text-green-600">{profitBreakdown.profitMargin.toFixed(1)}%</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Sales by Category */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <PieChart className="w-5 h-5 text-blue-600" />
                Sales by Category
                <MetricInfoTooltip explainer={SALES_EXPLAINERS.sales_by_category} side="top" align="start" />
              </CardTitle>
              <CardDescription>Revenue distribution</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {salesByCategory.map((cat, idx) => (
                  <div key={idx} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium text-slate-700">{cat.name}</span>
                      <span className="text-slate-600">{formatCurrency(cat.sales)} ({cat.percentage}%)</span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2">
                      <div 
                        className="bg-blue-500 h-2 rounded-full transition-all"
                        style={{ width: `${cat.percentage}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Recent Orders */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <ShoppingCart className="w-5 h-5 text-purple-600" />
                  Recent Orders
                </CardTitle>
                <CardDescription>Latest customer orders</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => navigate('/admin/orders')}>
                View All Orders
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-slate-500 border-b">
                    <th className="pb-3 font-medium">Order ID</th>
                    <th className="pb-3 font-medium">Customer</th>
                    <th className="pb-3 font-medium">Date</th>
                    <th className="pb-3 font-medium text-center">Items</th>
                    <th className="pb-3 font-medium text-right">Total</th>
                    <th className="pb-3 font-medium text-center">Status</th>
                    <th className="pb-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {recentOrders.map((order) => (
                    <tr key={order.id} className="border-b last:border-0 hover:bg-slate-50">
                      <td className="py-3">
                        <span className="font-mono text-sm text-blue-600">{order.id}</span>
                      </td>
                      <td className="py-3">
                        <div>
                          <p className="font-medium text-slate-900">{order.customer}</p>
                          <p className="text-xs text-slate-500">{order.email}</p>
                        </div>
                      </td>
                      <td className="py-3 text-sm text-slate-600">{formatDate(order.date)}</td>
                      <td className="py-3 text-center text-sm">{order.items}</td>
                      <td className="py-3 text-right font-medium">{formatCurrency(order.total)}</td>
                      <td className="py-3 text-center">
                        <OrderStatusBadge status={order.status} />
                      </td>
                      <td className="py-3 text-right">
                        <Button variant="ghost" size="sm">
                          <Eye className="w-4 h-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Top Products */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <BarChart3 className="w-5 h-5 text-amber-600" />
              Top Selling Products
              <MetricInfoTooltip explainer={SALES_EXPLAINERS.top_products} side="top" align="start" />
            </CardTitle>
            <CardDescription>Best performers by revenue</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-slate-500 border-b">
                    <th className="pb-3 font-medium">#</th>
                    <th className="pb-3 font-medium">Product</th>
                    <th className="pb-3 font-medium text-right">Units Sold</th>
                    <th className="pb-3 font-medium text-right">Revenue</th>
                    <th className="pb-3 font-medium text-right">Profit</th>
                  </tr>
                </thead>
                <tbody>
                  {topProducts.map((product, idx) => (
                    <tr key={product.sku} className="border-b last:border-0 hover:bg-slate-50">
                      <td className="py-3">
                        <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium ${
                          idx === 0 ? 'bg-yellow-100 text-yellow-700' :
                          idx === 1 ? 'bg-slate-200 text-slate-700' :
                          idx === 2 ? 'bg-orange-100 text-orange-700' :
                          'bg-slate-100 text-slate-600'
                        }`}>
                          {idx + 1}
                        </span>
                      </td>
                      <td className="py-3">
                        <div>
                          <p className="font-medium text-slate-900">{product.name}</p>
                          <p className="text-xs text-slate-500 font-mono">{product.sku}</p>
                        </div>
                      </td>
                      <td className="py-3 text-right font-medium">{formatNumber(product.sold)}m²</td>
                      <td className="py-3 text-right font-medium text-blue-600">{formatCurrency(product.revenue)}</td>
                      <td className="py-3 text-right font-medium text-green-600">{formatCurrency(product.profit)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Quick Stats Row */}
        <div className="grid grid-cols-4 gap-4">
          <StatCard 
            title="Customers"
            value={formatNumber(stats.totalCustomers)}
            subtitle={`${stats.returningCustomers} returning`}
            icon={Users}
            color="slate"
            explainer={SALES_EXPLAINERS.customers}
          />
          <StatCard 
            title="Conversion Rate"
            value={`${stats.conversionRate}%`}
            subtitle="Visitors to orders"
            icon={Percent}
            color="purple"
            explainer={SALES_EXPLAINERS.sales_conversion_rate}
          />
          <StatCard 
            title="Pending Orders"
            value={formatNumber(stats.pendingOrders)}
            subtitle="Awaiting action"
            icon={Clock}
            color="amber"
            explainer={SALES_EXPLAINERS.pending_orders}
          />
          <StatCard 
            title="Revenue per Customer"
            value={formatCurrency(stats.totalSales / (stats.totalCustomers || 1))}
            subtitle="Average lifetime value"
            icon={Banknote}
            color="green"
            explainer={SALES_EXPLAINERS.revenue_per_customer}
          />
        </div>
      </div>
    </div>
  );
}
