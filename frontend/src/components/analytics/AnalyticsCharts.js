import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';

const COLORS = ['#f97316', '#3b82f6', '#22c55e', '#a855f7', '#ef4444', '#06b6d4'];

export const StoreBarChart = ({ 
  data, 
  chartMetric, 
  onChartMetricChange, 
  showProfit, 
  formatCurrency 
}) => {
  if (!data || data.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-center">
          <CardTitle className="text-lg">Store Performance</CardTitle>
          <div className="flex gap-2">
            <button
              onClick={() => onChartMetricChange('revenue')}
              className={`px-3 py-1 text-xs rounded-full ${chartMetric === 'revenue' ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}
            >
              Revenue
            </button>
            <button
              onClick={() => onChartMetricChange('orders')}
              className={`px-3 py-1 text-xs rounded-full ${chartMetric === 'orders' ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}
            >
              Orders
            </button>
            {showProfit && (
              <button
                onClick={() => onChartMetricChange('profit')}
                className={`px-3 py-1 text-xs rounded-full ${chartMetric === 'profit' ? 'bg-emerald-600 text-white' : 'bg-gray-100'}`}
              >
                Profit
              </button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis tickFormatter={(v) => chartMetric === 'orders' ? v : `£${v.toLocaleString()}`} />
            <Tooltip 
              formatter={(value, name) => [
                chartMetric === 'orders' ? value : formatCurrency(value), 
                name
              ]} 
            />
            <Legend />
            {chartMetric === 'revenue' && <Bar dataKey="revenue" fill="#3b82f6" name="Revenue" />}
            {chartMetric === 'orders' && <Bar dataKey="orders" fill="#f97316" name="Orders" />}
            {chartMetric === 'profit' && <Bar dataKey="profit" fill="#22c55e" name="Profit" />}
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

export const StorePieChart = ({ data, formatCurrency }) => {
  if (!data || data.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Revenue Distribution</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
              outerRadius={100}
              fill="#8884d8"
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(value) => formatCurrency(value)} />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

export const DailyTrendChart = ({ data, formatCurrency }) => {
  if (!data || data.length === 0) return null;

  return (
    <Card className="col-span-2">
      <CardHeader>
        <CardTitle className="text-lg">Daily Sales Trend</CardTitle>
        <CardDescription>Revenue over time</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis 
              dataKey="date" 
              tickFormatter={(d) => {
                const [day, month] = d.split('/');
                return `${day}/${month}`;
              }}
            />
            <YAxis tickFormatter={(v) => `£${v.toLocaleString()}`} />
            <Tooltip formatter={(value) => formatCurrency(value)} />
            <Legend />
            <Line type="monotone" dataKey="revenue" stroke="#3b82f6" name="Revenue" />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};
