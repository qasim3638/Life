import React, { useState, useEffect } from 'react';
import { Card } from '../ui/card';
import { TrendingUp, TrendingDown, FileText, Receipt, ArrowRight, AlertCircle } from 'lucide-react';
import { Button } from '../ui/button';
import { Link } from 'react-router-dom';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export const QuoteConversionWidget = ({ showroomId }) => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const token = localStorage.getItem('token');
        const url = showroomId 
          ? `${API_URL}/api/conversion-analytics/quote-to-invoice?days=30&showroom_id=${showroomId}`
          : `${API_URL}/api/conversion-analytics/quote-to-invoice?days=30`;
        
        const res = await fetch(url, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!res.ok) throw new Error('Failed to fetch conversion stats');
        const data = await res.json();
        setStats(data);
      } catch (e) {
        console.error('Error fetching conversion stats:', e);
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, [showroomId]);

  if (loading) {
    return (
      <Card className="p-6 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/2 mb-4"></div>
        <div className="h-20 bg-gray-200 rounded"></div>
      </Card>
    );
  }

  if (error || !stats) {
    return (
      <Card className="p-6">
        <div className="text-center text-gray-500">
          <AlertCircle className="h-8 w-8 mx-auto mb-2" />
          <p>Unable to load conversion stats</p>
        </div>
      </Card>
    );
  }

  const isGoodRate = stats.conversion_rate >= 30;
  const trend = stats.weekly_trend?.[3]?.rate > stats.weekly_trend?.[0]?.rate;

  return (
    <Card className="p-6" data-testid="quote-conversion-widget">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
          <FileText className="h-5 w-5 text-blue-500" />
          Quote Conversion
        </h3>
        <span className="text-xs text-gray-500">Last 30 days</span>
      </div>

      {/* Main Conversion Rate */}
      <div className="text-center py-4 mb-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg">
        <div className="flex items-center justify-center gap-2">
          <span className={`text-4xl font-bold ${isGoodRate ? 'text-green-600' : 'text-amber-600'}`}>
            {stats.conversion_rate}%
          </span>
          {trend ? (
            <TrendingUp className="h-6 w-6 text-green-500" />
          ) : (
            <TrendingDown className="h-6 w-6 text-red-500" />
          )}
        </div>
        <p className="text-sm text-gray-600 mt-1">Conversion Rate</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center justify-center gap-1 text-blue-600">
            <FileText className="h-4 w-4" />
            <span className="text-xl font-semibold">{stats.total_quotations}</span>
          </div>
          <p className="text-xs text-gray-500">Quotations</p>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center justify-center gap-1 text-green-600">
            <Receipt className="h-4 w-4" />
            <span className="text-xl font-semibold">{stats.converted_quotations}</span>
          </div>
          <p className="text-xs text-gray-500">Converted</p>
        </div>
      </div>

      {/* Value Stats */}
      <div className="space-y-2 mb-4">
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Quoted Value</span>
          <span className="font-medium">£{stats.total_quotation_value?.toLocaleString()}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Converted Value</span>
          <span className="font-medium text-green-600">£{stats.converted_value?.toLocaleString()}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Lost Opportunity</span>
          <span className="font-medium text-red-500">£{stats.lost_opportunity?.toLocaleString()}</span>
        </div>
      </div>

      {/* Weekly Trend Mini Chart */}
      {stats.weekly_trend && stats.weekly_trend.length > 0 && (
        <div className="mb-4">
          <p className="text-xs text-gray-500 mb-2">Weekly Trend</p>
          <div className="flex items-end gap-1 h-12">
            {stats.weekly_trend.map((week, idx) => (
              <div 
                key={idx} 
                className="flex-1 bg-blue-200 rounded-t transition-all hover:bg-blue-300"
                style={{ height: `${Math.max(week.rate, 5)}%` }}
                title={`${week.week}: ${week.rate}%`}
              />
            ))}
          </div>
          <div className="flex justify-between text-[10px] text-gray-400 mt-1">
            {stats.weekly_trend.map((week, idx) => (
              <span key={idx}>{week.rate}%</span>
            ))}
          </div>
        </div>
      )}

      <Link to="/admin/reports?tab=conversion">
        <Button variant="outline" size="sm" className="w-full">
          View Details
          <ArrowRight className="h-4 w-4 ml-2" />
        </Button>
      </Link>
    </Card>
  );
};

export default QuoteConversionWidget;
