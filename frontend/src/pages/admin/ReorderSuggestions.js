import React, { useState, useEffect, useRef } from 'react';
import { Package, AlertTriangle, TrendingDown, ArrowRight, Search, Camera, X, Scan } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ReorderSuggestions = () => {
  const [suggestions, setSuggestions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [daysLookback, setDaysLookback] = useState(30);
  const [stockThreshold, setStockThreshold] = useState(14);

  useEffect(() => {
    fetchSuggestions();
  }, [daysLookback, stockThreshold]);

  const fetchSuggestions = async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `${API_URL}/api/reorder-suggestions/analyze?days_lookback=${daysLookback}&stock_days_threshold=${stockThreshold}&limit=50`
      );
      if (res.ok) {
        const data = await res.json();
        setSuggestions(data.suggestions || []);
        setSummary(data.summary);
      }
    } catch (e) {
      console.error('Error:', e);
    } finally {
      setLoading(false);
    }
  };

  const getUrgencyColor = (urgency) => {
    switch (urgency) {
      case 'critical': return 'bg-red-100 text-red-700 border-red-200';
      case 'high': return 'bg-orange-100 text-orange-700 border-orange-200';
      case 'medium': return 'bg-yellow-100 text-yellow-700 border-yellow-200';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  return (
    <div className="space-y-6" data-testid="reorder-suggestions">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Smart Reorder Suggestions</h2>
          <p className="text-gray-500">AI-powered inventory recommendations based on sales velocity</p>
        </div>
        <div className="flex gap-3">
          <select
            value={daysLookback}
            onChange={(e) => setDaysLookback(parseInt(e.target.value))}
            className="border rounded-lg px-3 py-2"
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={60}>Last 60 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <select
            value={stockThreshold}
            onChange={(e) => setStockThreshold(parseInt(e.target.value))}
            className="border rounded-lg px-3 py-2"
          >
            <option value={7}>7 days threshold</option>
            <option value={14}>14 days threshold</option>
            <option value={21}>21 days threshold</option>
            <option value={30}>30 days threshold</option>
          </select>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="border-l-4 border-l-blue-500">
            <CardContent className="p-4">
              <p className="text-sm text-gray-500">Products Analyzed</p>
              <p className="text-2xl font-bold">{summary.total_products_analyzed}</p>
            </CardContent>
          </Card>
          <Card className="border-l-4 border-l-red-500">
            <CardContent className="p-4">
              <p className="text-sm text-gray-500">Critical Items</p>
              <p className="text-2xl font-bold text-red-600">{summary.critical_items}</p>
            </CardContent>
          </Card>
          <Card className="border-l-4 border-l-orange-500">
            <CardContent className="p-4">
              <p className="text-sm text-gray-500">High Priority</p>
              <p className="text-2xl font-bold text-orange-600">{summary.high_priority_items}</p>
            </CardContent>
          </Card>
          <Card className="border-l-4 border-l-green-500">
            <CardContent className="p-4">
              <p className="text-sm text-gray-500">Est. Order Value</p>
              <p className="text-2xl font-bold">£{summary.estimated_total_order_value?.toLocaleString()}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Suggestions List */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent"></div>
        </div>
      ) : suggestions.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Package className="h-12 w-12 text-green-500 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900">All stock levels healthy!</h3>
            <p className="text-gray-500">No products need reordering at this time.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {suggestions.map((item, idx) => (
            <Card key={idx} className={`border-l-4 ${
              item.urgency === 'critical' ? 'border-l-red-500' :
              item.urgency === 'high' ? 'border-l-orange-500' : 'border-l-yellow-500'
            }`}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${getUrgencyColor(item.urgency)}`}>
                        {item.urgency.toUpperCase()}
                      </span>
                      <h3 className="font-medium text-gray-900">{item.name}</h3>
                      <span className="text-sm text-gray-500">SKU: {item.sku}</span>
                    </div>
                    <p className="text-sm text-gray-600 mt-1">{item.reason}</p>
                    <div className="flex gap-6 mt-2 text-sm">
                      <span>Current Stock: <strong>{item.current_stock}</strong></span>
                      <span>Avg Daily Sales: <strong>{item.avg_daily_sales}</strong></span>
                      <span>Days Remaining: <strong className={item.days_of_stock_remaining <= 3 ? 'text-red-600' : ''}>
                        {item.days_of_stock_remaining}
                      </strong></span>
                    </div>
                  </div>
                  <div className="text-right ml-4">
                    <p className="text-sm text-gray-500">Suggested Order</p>
                    <p className="text-2xl font-bold text-blue-600">{item.suggested_order_qty}</p>
                    {item.estimated_order_value && (
                      <p className="text-sm text-gray-500">~£{item.estimated_order_value}</p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default ReorderSuggestions;
