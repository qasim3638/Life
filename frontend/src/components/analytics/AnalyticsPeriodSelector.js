import React from 'react';
import { Calendar, RefreshCw } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';

const PERIOD_OPTIONS = [
  { value: 'day', label: 'Today' },
  { value: 'week', label: 'This Week' },
  { value: 'month', label: 'This Month' },
  { value: 'quarter', label: 'This Quarter' },
  { value: 'year', label: 'This Year' },
  { value: 'custom', label: 'Custom Range' }
];

export const AnalyticsPeriodSelector = ({
  period,
  onPeriodChange,
  customStart,
  setCustomStart,
  customEnd,
  setCustomEnd,
  showCustomDates,
  setShowCustomDates,
  onCustomDateApply,
  onRefresh,
  loading
}) => {
  return (
    <div className="flex flex-wrap items-center gap-4">
      <Select 
        value={period} 
        onValueChange={(value) => {
          if (value === 'custom') {
            setShowCustomDates(true);
          } else {
            setShowCustomDates(false);
            onPeriodChange(value);
          }
        }}
      >
        <SelectTrigger className="w-[180px]">
          <SelectValue placeholder="Select period" />
        </SelectTrigger>
        <SelectContent>
          {PERIOD_OPTIONS.map(opt => (
            <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      {showCustomDates && (
        <div className="flex items-center gap-2">
          <Input
            type="date"
            value={customStart}
            onChange={(e) => setCustomStart(e.target.value)}
            className="w-[150px]"
          />
          <span className="text-muted-foreground">to</span>
          <Input
            type="date"
            value={customEnd}
            onChange={(e) => setCustomEnd(e.target.value)}
            className="w-[150px]"
          />
          <Button size="sm" onClick={onCustomDateApply}>
            Apply
          </Button>
        </div>
      )}

      <Button 
        variant="outline" 
        size="sm" 
        onClick={onRefresh}
        disabled={loading}
      >
        <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
        Refresh
      </Button>
    </div>
  );
};
