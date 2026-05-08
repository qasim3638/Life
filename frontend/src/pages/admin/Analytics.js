import React, { useState, useEffect } from 'react';
import { BarChart3, Loader2, FileDown } from 'lucide-react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { Button } from '../../components/ui/button';
import {
  AnalyticsSummaryCards,
  AnalyticsVATBreakdown,
  SalesTargetCard,
  StoreBarChart,
  StorePieChart,
  DailyTrendChart,
  TopProductsTable,
  StoreStatsTable,
  AnalyticsPeriodSelector
} from '../../components/analytics';

export const Analytics = () => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [period, setPeriod] = useState('month');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [showCustomDates, setShowCustomDates] = useState(false);
  const [chartMetric, setChartMetric] = useState('revenue');
  const [salesTarget, setSalesTarget] = useState(null);

  // Fetch analytics data
  const fetchAnalytics = async (customDates = null) => {
    setLoading(true);
    try {
      const params = { period };
      if (customDates) {
        params.start_date = customDates.start;
        params.end_date = customDates.end;
      }
      const response = await api.getStoreAnalytics(params);
      setAnalytics(response.data);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch sales target
  const fetchSalesTarget = async () => {
    try {
      const response = await api.getCurrentSalesTarget();
      setSalesTarget(response.data);
    } catch (error) {
      console.error('Failed to fetch sales target:', error);
    }
  };

  useEffect(() => {
    fetchAnalytics();
    fetchSalesTarget();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

  // Handle period change
  const handlePeriodChange = (newPeriod) => {
    setPeriod(newPeriod);
  };

  // Handle custom date apply
  const handleCustomDateApply = () => {
    if (customStart && customEnd) {
      fetchAnalytics({ start: customStart, end: customEnd });
    }
  };

  // Handle profit report export
  const handleExportProfitReport = async () => {
    setExporting(true);
    try {
      const params = { period };
      if (customStart && customEnd) {
        params.start_date = customStart;
        params.end_date = customEnd;
      }
      
      const response = await api.exportProfitReportCsv(params);
      const blob = new Blob([response.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `profit_report_${period}_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success('Profit report exported successfully!');
    } catch (error) {
      if (error.response?.status === 403) {
        toast.error('Super Admin access required to export profit reports');
      } else {
        toast.error('Failed to export profit report');
      }
      console.error(error);
    } finally {
      setExporting(false);
    }
  };

  // Format currency helper
  const formatCurrency = (value) => 
    `£${value?.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}`;

  // Check if profit should be shown
  const showProfit = analytics?.show_profit === true;

  // Loading state
  if (loading && !analytics) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Prepare chart data
  const pieData = analytics?.showroom_analytics?.map((s, i) => ({
    name: s.showroom_name,
    value: s.gross_revenue,
    color: ['#f97316', '#3b82f6', '#22c55e', '#a855f7', '#ef4444', '#06b6d4'][i % 6]
  })) || [];

  const barData = analytics?.showroom_analytics?.map(s => ({
    name: s.showroom_name,
    revenue: s.gross_revenue,
    orders: s.order_count,
    profit: s.profit || 0
  })) || [];

  const dailyTrendData = analytics?.daily_trends?.map(d => ({
    date: d.date,
    revenue: d.revenue
  })) || [];

  // Prepare top products data
  const allTopProducts = showProfit 
    ? analytics?.showroom_analytics?.flatMap(s => 
        s.top_products?.map(p => ({
          ...p,
          showroom: s.showroom_name
        })) || []
      ).sort((a, b) => b.revenue - a.revenue) || []
    : analytics?.showroom_analytics?.flatMap(s => 
        s.top_products?.map(p => ({
          ...p,
          showroom: s.showroom_name
        })) || []
      ).sort((a, b) => b.revenue - a.revenue) || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BarChart3 className="h-6 w-6" />
            Analytics Dashboard
          </h1>
          <p className="text-muted-foreground text-sm">
            Track sales performance across showrooms
          </p>
        </div>
        
        <div className="flex flex-wrap items-center gap-2">
          {showProfit && (
            <Button 
              variant="outline" 
              onClick={handleExportProfitReport}
              disabled={exporting}
              data-testid="export-profit-report-btn"
            >
              <FileDown className="mr-2 h-4 w-4" />
              {exporting ? 'Exporting...' : 'Export Profit Report'}
            </Button>
          )}
          <AnalyticsPeriodSelector
            period={period}
            onPeriodChange={handlePeriodChange}
            customStart={customStart}
            setCustomStart={setCustomStart}
            customEnd={customEnd}
            setCustomEnd={setCustomEnd}
            showCustomDates={showCustomDates}
            setShowCustomDates={setShowCustomDates}
            onCustomDateApply={handleCustomDateApply}
            onRefresh={() => fetchAnalytics()}
            loading={loading}
          />
        </div>
      </div>

      {/* Summary Cards */}
      <AnalyticsSummaryCards 
        analytics={analytics} 
        showProfit={showProfit} 
        formatCurrency={formatCurrency} 
      />

      {/* Sales Target & VAT Breakdown Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SalesTargetCard 
          salesTarget={salesTarget} 
          formatCurrency={formatCurrency}
          onTargetSaved={fetchSalesTarget}
          api={api}
        />
        <AnalyticsVATBreakdown 
          analytics={analytics} 
          formatCurrency={formatCurrency} 
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <StoreBarChart
          data={barData}
          chartMetric={chartMetric}
          onChartMetricChange={setChartMetric}
          showProfit={showProfit}
          formatCurrency={formatCurrency}
        />
        <StorePieChart 
          data={pieData} 
          formatCurrency={formatCurrency} 
        />
      </div>

      {/* Daily Trend Chart */}
      {dailyTrendData.length > 0 && (
        <DailyTrendChart 
          data={dailyTrendData} 
          formatCurrency={formatCurrency} 
        />
      )}

      {/* Tables Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TopProductsTable
          products={allTopProducts}
          showProfit={showProfit}
          formatCurrency={formatCurrency}
        />
        <StoreStatsTable
          showroomAnalytics={analytics?.showroom_analytics}
          showProfit={showProfit}
          formatCurrency={formatCurrency}
        />
      </div>
    </div>
  );
};