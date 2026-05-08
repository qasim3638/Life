import React from 'react';
import { TrendingUp, Award, Star } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';

export const TopProductsTable = ({ 
  products, 
  showProfit, 
  formatCurrency 
}) => {
  if (!products || products.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Award className="h-5 w-5 text-amber-500" />
          Top Selling Products
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {products.slice(0, 10).map((product, index) => (
            <div key={index} className="flex justify-between items-center p-2 bg-muted/50 rounded">
              <div className="flex items-center gap-3">
                <span className={`w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold ${
                  index === 0 ? 'bg-amber-500 text-white' :
                  index === 1 ? 'bg-gray-400 text-white' :
                  index === 2 ? 'bg-amber-700 text-white' :
                  'bg-gray-200'
                }`}>
                  {index + 1}
                </span>
                <div>
                  <p className="font-medium text-sm">{product.name}</p>
                  <p className="text-xs text-muted-foreground">
                    Qty: {product.quantity} | {product.showroom}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="font-medium">{formatCurrency(product.revenue)}</p>
                {showProfit && (
                  <p className="text-xs text-emerald-600">
                    Profit: {formatCurrency(product.profit)}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

export const StoreStatsTable = ({ 
  showroomAnalytics, 
  showProfit, 
  formatCurrency 
}) => {
  if (!showroomAnalytics || showroomAnalytics.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Star className="h-5 w-5 text-blue-500" />
          Store Statistics
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2">Store</th>
                <th className="text-right py-2">Orders</th>
                <th className="text-right py-2">Revenue</th>
                {showProfit && <th className="text-right py-2">Profit</th>}
                <th className="text-right py-2">Items</th>
              </tr>
            </thead>
            <tbody>
              {showroomAnalytics.map((showroom, index) => (
                <tr key={index} className="border-b">
                  <td className="py-2 font-medium">{showroom.showroom_name}</td>
                  <td className="py-2 text-right">{showroom.order_count}</td>
                  <td className="py-2 text-right text-green-600">{formatCurrency(showroom.gross_revenue)}</td>
                  {showProfit && (
                    <td className="py-2 text-right text-emerald-600">{formatCurrency(showroom.profit)}</td>
                  )}
                  <td className="py-2 text-right">{showroom.items_sold}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
};
