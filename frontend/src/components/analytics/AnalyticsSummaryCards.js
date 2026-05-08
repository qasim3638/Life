import React from 'react';
import { TrendingUp, TrendingDown, Target, Calendar, Percent } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';

export const AnalyticsSummaryCards = ({ 
  analytics, 
  showProfit, 
  formatCurrency 
}) => {
  if (!analytics) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Total Revenue */}
      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            Total Revenue (Gross)
          </CardDescription>
          <CardTitle className="text-2xl text-green-600">
            {formatCurrency(analytics.total_gross)}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">
            Net: {formatCurrency(analytics.total_net)} | VAT: {formatCurrency(analytics.total_vat)}
          </p>
        </CardContent>
      </Card>

      {/* Total Orders */}
      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            Total Orders
          </CardDescription>
          <CardTitle className="text-2xl text-blue-600">
            {analytics.total_orders}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">
            Avg Order: {formatCurrency(analytics.average_order_value)}
          </p>
        </CardContent>
      </Card>

      {/* Profit Card - Only shown to admins */}
      {showProfit && (
        <Card className="border-emerald-200 bg-emerald-50/30">
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-2 text-emerald-700">
              <TrendingUp className="h-4 w-4" />
              Total Profit (Ex-VAT)
            </CardDescription>
            <CardTitle className="text-2xl text-emerald-600">
              {formatCurrency(analytics.total_profit)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-emerald-700">
              Margin: {analytics.profit_margin?.toFixed(1)}% | Per m²: {formatCurrency(analytics.profit_per_m2)}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Items Sold */}
      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="flex items-center gap-2">
            <Target className="h-4 w-4" />
            Items Sold
          </CardDescription>
          <CardTitle className="text-2xl text-purple-600">
            {analytics.total_items_sold?.toLocaleString() || 0}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">
            Total m²: {analytics.total_m2_sold?.toFixed(2) || 0}
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export const AnalyticsVATBreakdown = ({ analytics, formatCurrency }) => {
  if (!analytics) return null;

  return (
    <Card className="border-blue-200 bg-blue-50/30">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Percent className="h-4 w-4 text-blue-600" />
          VAT Breakdown
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-xs text-muted-foreground">Gross (Inc VAT)</p>
            <p className="text-lg font-bold text-blue-700">{formatCurrency(analytics.total_gross)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Net (Ex VAT)</p>
            <p className="text-lg font-bold text-green-700">{formatCurrency(analytics.total_net)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">VAT (20%)</p>
            <p className="text-lg font-bold text-amber-700">{formatCurrency(analytics.total_vat)}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
