import React, { useState } from 'react';
import { Target, Check, X } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Progress } from '../ui/progress';
import { toast } from 'sonner';

export const SalesTargetCard = ({ 
  salesTarget, 
  formatCurrency,
  onTargetSaved,
  api
}) => {
  const [editingTarget, setEditingTarget] = useState(false);
  const [newMonthlyTarget, setNewMonthlyTarget] = useState('');
  const [savingTarget, setSavingTarget] = useState(false);

  const getProgressColor = (progress) => {
    if (progress >= 100) return 'bg-green-500';
    if (progress >= 75) return 'bg-blue-500';
    if (progress >= 50) return 'bg-amber-500';
    return 'bg-red-500';
  };

  const handleSaveTarget = async () => {
    const target = parseFloat(newMonthlyTarget);
    if (!target || target <= 0) {
      toast.error('Please enter a valid target amount');
      return;
    }

    setSavingTarget(true);
    try {
      const now = new Date();
      await api.setSalesTarget({
        year: now.getFullYear(),
        month: now.getMonth() + 1,
        monthly_target: target
      });
      toast.success('Sales target updated successfully');
      setEditingTarget(false);
      setNewMonthlyTarget('');
      if (onTargetSaved) onTargetSaved();
    } catch (error) {
      toast.error('Failed to save target');
    } finally {
      setSavingTarget(false);
    }
  };

  // Extract values from salesTarget safely
  const monthlyTarget = salesTarget?.targets?.monthly || 0;
  const monthlyActual = salesTarget?.actual?.monthly || 0;
  const monthlyProgress = salesTarget?.progress?.monthly || 0;
  const dailyTarget = salesTarget?.targets?.daily || 0;
  const weeklyTarget = salesTarget?.targets?.weekly || 0;
  const hasTarget = salesTarget?.has_target;

  return (
    <Card className="border-purple-200 bg-purple-50/30">
      <CardHeader className="pb-2">
        <div className="flex justify-between items-start">
          <div>
            <CardDescription className="flex items-center gap-2 text-purple-700">
              <Target className="h-4 w-4" />
              Monthly Sales Target
            </CardDescription>
            {hasTarget ? (
              <CardTitle className="text-2xl text-purple-600">
                {formatCurrency(monthlyTarget)}
              </CardTitle>
            ) : (
              <CardTitle className="text-lg text-muted-foreground">No target set</CardTitle>
            )}
          </div>
          {editingTarget ? (
            <div className="flex gap-2">
              <Button 
                size="sm" 
                variant="outline" 
                onClick={() => setEditingTarget(false)}
                className="h-8"
              >
                <X className="h-4 w-4" />
              </Button>
              <Button 
                size="sm" 
                onClick={handleSaveTarget}
                disabled={savingTarget}
                className="h-8 bg-purple-600 hover:bg-purple-700"
              >
                <Check className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <Button 
              size="sm" 
              variant="outline" 
              onClick={() => {
                setEditingTarget(true);
                setNewMonthlyTarget(monthlyTarget?.toString() || '');
              }}
              className="text-purple-700 border-purple-300"
            >
              {hasTarget ? 'Edit' : 'Set Target'}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {editingTarget ? (
          <div className="space-y-2">
            <label className="text-xs font-medium">Monthly Target (£)</label>
            <Input
              type="number"
              value={newMonthlyTarget}
              onChange={(e) => setNewMonthlyTarget(e.target.value)}
              placeholder="Enter monthly target"
              className="h-9"
            />
            <p className="text-xs text-muted-foreground">
              Daily: {formatCurrency(parseFloat(newMonthlyTarget || 0) / 30)} | 
              Weekly: {formatCurrency(parseFloat(newMonthlyTarget || 0) / 4.33)}
            </p>
          </div>
        ) : hasTarget ? (
          <div className="space-y-3">
            <div className="flex justify-between text-xs">
              <span>Progress: {formatCurrency(monthlyActual)} / {formatCurrency(monthlyTarget)}</span>
              <span className="font-medium">{monthlyProgress.toFixed(1)}%</span>
            </div>
            <Progress 
              value={Math.min(monthlyProgress, 100)} 
              className="h-2"
              indicatorClassName={getProgressColor(monthlyProgress)}
            />
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-white rounded p-2">
                <p className="text-muted-foreground">Daily Target</p>
                <p className="font-medium">{formatCurrency(dailyTarget)}</p>
              </div>
              <div className="bg-white rounded p-2">
                <p className="text-muted-foreground">Weekly Target</p>
                <p className="font-medium">{formatCurrency(weeklyTarget)}</p>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            Set a monthly sales target to track your progress
          </p>
        )}
      </CardContent>
    </Card>
  );
};
