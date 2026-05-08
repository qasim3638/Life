import React, { useState, useEffect } from 'react';
import { Users, TrendingUp, Award, Target, Calendar, ChevronDown, Crown, Medal, ArrowUp, ArrowDown } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const StaffPerformanceDashboard = () => {
  const [overview, setOverview] = useState(null);
  const [leaderboard, setLeaderboard] = useState(null);
  const [selectedStaff, setSelectedStaff] = useState(null);
  const [staffDetail, setStaffDetail] = useState(null);
  const [days, setDays] = useState(30);
  const [period, setPeriod] = useState('month');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, [days, period]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [overviewRes, leaderboardRes] = await Promise.all([
        fetch(`${API_URL}/api/staff-performance/overview?days=${days}`),
        fetch(`${API_URL}/api/staff-performance/leaderboard?period=${period}&metric=revenue`)
      ]);

      if (overviewRes.ok) {
        const data = await overviewRes.json();
        setOverview(data);
      }
      if (leaderboardRes.ok) {
        const data = await leaderboardRes.json();
        setLeaderboard(data);
      }
    } catch (e) {
      console.error('Error fetching performance data:', e);
    } finally {
      setLoading(false);
    }
  };

  const fetchStaffDetail = async (staffName) => {
    try {
      const res = await fetch(`${API_URL}/api/staff-performance/individual/${encodeURIComponent(staffName)}?days=${days}`);
      if (res.ok) {
        const data = await res.json();
        setStaffDetail(data);
        setSelectedStaff(staffName);
      }
    } catch (e) {
      console.error('Error fetching staff detail:', e);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(amount);
  };

  if (loading && !overview) {
    return (
      <div className="p-6 animate-pulse">
        <div className="h-8 bg-gray-200 rounded w-64 mb-6"></div>
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[1,2,3,4].map(i => <div key={i} className="h-32 bg-gray-200 rounded"></div>)}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 bg-gray-50 min-h-screen" data-testid="staff-performance-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Users className="h-7 w-7 text-amber-500" />
            Staff Performance Dashboard
          </h1>
          <p className="text-gray-500 mt-1">Track sales, conversions, and achievements</p>
        </div>
        <div className="flex gap-2">
          <select
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value))}
            className="border rounded-lg px-3 py-2 text-sm"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={365}>Last year</option>
          </select>
        </div>
      </div>

      {/* Summary Cards */}
      {overview && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Total Revenue</p>
                  <p className="text-2xl font-bold text-gray-900">{formatCurrency(overview.totals.total_revenue)}</p>
                </div>
                <div className="p-3 bg-green-100 rounded-full">
                  <TrendingUp className="h-6 w-6 text-green-600" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Total Invoices</p>
                  <p className="text-2xl font-bold text-gray-900">{overview.totals.total_invoices}</p>
                </div>
                <div className="p-3 bg-blue-100 rounded-full">
                  <Calendar className="h-6 w-6 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Active Staff</p>
                  <p className="text-2xl font-bold text-gray-900">{overview.totals.total_staff}</p>
                </div>
                <div className="p-3 bg-purple-100 rounded-full">
                  <Users className="h-6 w-6 text-purple-600" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Avg per Staff</p>
                  <p className="text-2xl font-bold text-gray-900">{formatCurrency(overview.totals.avg_per_staff)}</p>
                </div>
                <div className="p-3 bg-amber-100 rounded-full">
                  <Target className="h-6 w-6 text-amber-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Leaderboard */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Award className="h-5 w-5 text-amber-500" />
                Leaderboard
              </CardTitle>
              <select
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                className="text-sm border rounded px-2 py-1"
              >
                <option value="day">Today</option>
                <option value="week">This Week</option>
                <option value="month">This Month</option>
                <option value="year">This Year</option>
              </select>
            </div>
          </CardHeader>
          <CardContent>
            {leaderboard?.leaderboard?.map((staff, idx) => (
              <div
                key={staff.staff_name}
                onClick={() => fetchStaffDetail(staff.staff_name)}
                className={`flex items-center justify-between p-3 rounded-lg mb-2 cursor-pointer transition ${
                  selectedStaff === staff.staff_name 
                    ? 'bg-amber-100 border border-amber-300' 
                    : 'bg-gray-50 hover:bg-gray-100'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{staff.badge || `#${staff.rank}`}</span>
                  <div>
                    <p className="font-medium text-gray-900">{staff.staff_name}</p>
                    <p className="text-sm text-gray-500">{staff.invoices} invoices</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-bold text-gray-900">{formatCurrency(staff.revenue)}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Staff Table */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Performance Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full" data-testid="staff-performance-table">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-2 font-medium text-gray-500">Staff</th>
                    <th className="text-right py-3 px-2 font-medium text-gray-500">Revenue</th>
                    <th className="text-right py-3 px-2 font-medium text-gray-500">Invoices</th>
                    <th className="text-right py-3 px-2 font-medium text-gray-500">Avg Value</th>
                    <th className="text-right py-3 px-2 font-medium text-gray-500">Quotes</th>
                    <th className="text-right py-3 px-2 font-medium text-gray-500">Conversion</th>
                  </tr>
                </thead>
                <tbody>
                  {overview?.staff?.map((staff) => (
                    <tr 
                      key={staff.staff_name} 
                      className="border-b hover:bg-gray-50 cursor-pointer"
                      onClick={() => fetchStaffDetail(staff.staff_name)}
                    >
                      <td className="py-3 px-2 font-medium">{staff.staff_name}</td>
                      <td className="text-right py-3 px-2">{formatCurrency(staff.total_revenue)}</td>
                      <td className="text-right py-3 px-2">{staff.total_invoices}</td>
                      <td className="text-right py-3 px-2">{formatCurrency(staff.avg_invoice_value)}</td>
                      <td className="text-right py-3 px-2">{staff.total_quotations}</td>
                      <td className="text-right py-3 px-2">
                        <span className={`px-2 py-1 rounded text-sm ${
                          staff.conversion_rate >= 50 ? 'bg-green-100 text-green-700' :
                          staff.conversion_rate >= 30 ? 'bg-amber-100 text-amber-700' :
                          'bg-red-100 text-red-700'
                        }`}>
                          {staff.conversion_rate}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Staff Detail Modal/Panel */}
      {staffDetail && selectedStaff && (
        <Card className="mt-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Crown className="h-5 w-5 text-amber-500" />
                {selectedStaff} - Detailed Performance
              </CardTitle>
              <Button variant="ghost" size="sm" onClick={() => { setSelectedStaff(null); setStaffDetail(null); }}>
                Close
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-blue-50 rounded-lg p-4">
                <p className="text-sm text-blue-600">Total Revenue</p>
                <p className="text-2xl font-bold text-blue-900">{formatCurrency(staffDetail.summary.total_revenue)}</p>
              </div>
              <div className="bg-green-50 rounded-lg p-4">
                <p className="text-sm text-green-600">Total Invoices</p>
                <p className="text-2xl font-bold text-green-900">{staffDetail.summary.total_invoices}</p>
              </div>
              <div className="bg-purple-50 rounded-lg p-4">
                <p className="text-sm text-purple-600">Best Day</p>
                <p className="text-xl font-bold text-purple-900">{staffDetail.summary.best_day?.date || 'N/A'}</p>
                <p className="text-sm text-purple-700">{formatCurrency(staffDetail.summary.best_day?.revenue || 0)}</p>
              </div>
              <div className="bg-amber-50 rounded-lg p-4">
                <p className="text-sm text-amber-600">Avg Daily</p>
                <p className="text-2xl font-bold text-amber-900">{formatCurrency(staffDetail.summary.avg_daily_revenue)}</p>
              </div>
            </div>

            {/* Top Products */}
            <div className="mb-6">
              <h3 className="font-medium text-gray-900 mb-3">Top Products Sold</h3>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                {staffDetail.top_products.slice(0, 5).map((product, idx) => (
                  <div key={idx} className="bg-gray-50 rounded-lg p-3 text-center">
                    <p className="text-sm text-gray-700 truncate" title={product.name}>{product.name}</p>
                    <p className="font-bold text-gray-900">{formatCurrency(product.revenue)}</p>
                    <p className="text-xs text-gray-500">{product.quantity} units</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Recent Invoices */}
            <div>
              <h3 className="font-medium text-gray-900 mb-3">Recent Invoices</h3>
              <div className="space-y-2">
                {staffDetail.recent_invoices.slice(0, 5).map((inv) => (
                  <div key={inv.id} className="flex items-center justify-between bg-gray-50 rounded-lg p-3">
                    <div>
                      <p className="font-medium text-gray-900">#{inv.invoice_no}</p>
                      <p className="text-sm text-gray-500">{inv.customer_name || 'Walk-in'}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-bold text-gray-900">{formatCurrency(inv.total)}</p>
                      <p className="text-xs text-gray-500">{new Date(inv.created_at).toLocaleDateString()}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default StaffPerformanceDashboard;
