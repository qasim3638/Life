import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { TrendingUp, TrendingDown, DollarSign, Calendar, Building2, BarChart3, ChevronDown, ChevronUp } from 'lucide-react';
import { api } from '../../lib/api';

// Moved outside component to fix ESLint react/no-unstable-nested-components
const ChangeIndicator = ({ change }) => {
  const isPositive = change >= 0;
  
  return (
    <div className={`flex items-center gap-1 text-sm ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
      {isPositive ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
      <span>{isPositive ? '+' : ''}{change.toFixed(1)}%</span>
    </div>
  );
};

/**
 * Sales Comparison Component for Main Dashboard
 * Shows historical vs current sales comparison by store
 */
export const SalesComparison = ({ className = '' }) => {
  const [comparisons, setComparisons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedStore, setExpandedStore] = useState(null);

  useEffect(() => {
    fetchComparisons();
  }, []);

  const fetchComparisons = async () => {
    try {
      const response = await api.get('/historical-sales/comparison');
      setComparisons(response.data || []);
    } catch (error) {
      console.error('Failed to fetch sales comparison:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: 'GBP',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  const calculateChange = (current, previous) => {
    if (previous === 0) return current > 0 ? 100 : 0;
    return ((current - previous) / previous) * 100;
  };

  if (loading) {
    return (
      <Card className={className}>
        <CardContent className="p-6">
          <div className="animate-pulse space-y-4">
            <div className="h-6 bg-gray-200 rounded w-1/3"></div>
            <div className="h-20 bg-gray-200 rounded"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Filter stores with historical data
  const storesWithData = comparisons.filter(c => c.has_data);

  if (storesWithData.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Sales Comparison
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-sm">
            No historical sales data available. Import sales records to see comparisons.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className} data-testid="sales-comparison-card">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <BarChart3 className="h-5 w-5 text-blue-600" />
          Store Sales Comparison
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {storesWithData.map((store) => (
          <div 
            key={store.showroom_id} 
            className="border rounded-lg p-4 bg-gradient-to-r from-slate-50 to-white"
            data-testid={`store-comparison-${store.showroom_id}`}
          >
            {/* Store Header */}
            <div 
              className="flex items-center justify-between cursor-pointer"
              onClick={() => setExpandedStore(expandedStore === store.showroom_id ? null : store.showroom_id)}
            >
              <div className="flex items-center gap-2">
                <Building2 className="h-5 w-5 text-slate-600" />
                <span className="font-semibold text-lg">{store.showroom_name}</span>
              </div>
              <Button variant="ghost" size="sm">
                {expandedStore === store.showroom_id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </Button>
            </div>

            {/* Summary Grid - Always Visible */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
              {/* This Month */}
              <div className="bg-white p-3 rounded-lg border shadow-sm">
                <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                  <Calendar className="h-3 w-3" />
                  This Month
                </div>
                <div className="text-xl font-bold text-blue-600">
                  {formatCurrency(store.this_month)}
                </div>
                <ChangeIndicator change={calculateChange(store.this_month, store.last_month)} />
              </div>

              {/* Last Month */}
              <div className="bg-white p-3 rounded-lg border shadow-sm">
                <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                  <Calendar className="h-3 w-3" />
                  Last Month
                </div>
                <div className="text-xl font-bold text-slate-700">
                  {formatCurrency(store.last_month)}
                </div>
              </div>

              {/* This Year */}
              <div className="bg-white p-3 rounded-lg border shadow-sm">
                <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                  <DollarSign className="h-3 w-3" />
                  This Year
                </div>
                <div className="text-xl font-bold text-green-600">
                  {formatCurrency(store.this_year)}
                </div>
                <ChangeIndicator change={calculateChange(store.this_year, store.last_year)} />
              </div>

              {/* Last Year */}
              <div className="bg-white p-3 rounded-lg border shadow-sm">
                <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                  <DollarSign className="h-3 w-3" />
                  Last Year
                </div>
                <div className="text-xl font-bold text-slate-700">
                  {formatCurrency(store.last_year)}
                </div>
              </div>
            </div>

            {/* Expanded Monthly Breakdown */}
            {expandedStore === store.showroom_id && store.monthly_data?.length > 0 && (
              <div className="mt-4 pt-4 border-t">
                <h4 className="text-sm font-medium mb-3">Monthly Breakdown (Last 6 Months)</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-2 px-2">Month</th>
                        <th className="text-right py-2 px-2">Cash</th>
                        <th className="text-right py-2 px-2">Card</th>
                        <th className="text-right py-2 px-2">Bank</th>
                        <th className="text-right py-2 px-2">Refunds</th>
                        <th className="text-right py-2 px-2 font-semibold">Total</th>
                        <th className="text-right py-2 px-2">Daily Avg</th>
                      </tr>
                    </thead>
                    <tbody>
                      {store.monthly_data.slice(0, 6).map((month, idx) => (
                        <tr key={idx} className="border-b hover:bg-gray-50">
                          <td className="py-2 px-2 font-medium">
                            {month.month_name} {month.year}
                          </td>
                          <td className="text-right py-2 px-2 text-green-600">
                            {formatCurrency(month.cash)}
                          </td>
                          <td className="text-right py-2 px-2 text-blue-600">
                            {formatCurrency(month.card)}
                          </td>
                          <td className="text-right py-2 px-2 text-purple-600">
                            {formatCurrency(month.bank)}
                          </td>
                          <td className="text-right py-2 px-2 text-red-500">
                            -{formatCurrency(month.refunds)}
                          </td>
                          <td className="text-right py-2 px-2 font-bold">
                            {formatCurrency(month.total)}
                          </td>
                          <td className="text-right py-2 px-2 text-muted-foreground">
                            {formatCurrency(month.daily_avg)}/day
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
};

export default SalesComparison;
