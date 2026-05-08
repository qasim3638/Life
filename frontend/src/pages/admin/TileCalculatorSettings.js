import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Calculator, ArrowLeft, Save, RefreshCw, Eye, EyeOff, 
  Bath, Home, Square, Grid3X3, Info, Check, X, Settings,
  Move, DoorOpen, Percent, Ruler, Package
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Switch } from '../../components/ui/switch';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Default calculator configuration
const DEFAULT_CONFIG = {
  enabled: true,
  defaultWastage: 10,
  maxWastage: 30,
  calculatorTypes: {
    bathroom: {
      enabled: true,
      name: 'Bathroom',
      description: 'Floor + Walls with window/door subtraction',
      defaultWallHeight: 2.4,
      showSubtractions: true
    },
    floor: {
      enabled: true,
      name: 'Floor Only',
      description: 'Kitchen, Living Room, Garden, etc.',
      showSubtractions: false
    },
    singleWall: {
      enabled: true,
      name: 'Single Wall',
      description: 'Splash backs, Feature walls, Fireplace',
      showSubtractions: true
    },
    custom: {
      enabled: true,
      name: 'Custom Areas',
      description: 'Multiple small or complicated sections',
      showSubtractions: false
    }
  },
  defaultSubtractions: {
    window: { width: 1.2, height: 1.0 },
    door: { width: 0.9, height: 2.0 }
  },
  presetRooms: {
    bathroom: ['Small Bathroom', 'Medium Bathroom', 'Large Bathroom', 'Wet Room', 'En-Suite'],
    floor: ['Kitchen', 'Living Room', 'Hallway', 'Garden Patio', 'Conservatory', 'Utility Room'],
    singleWall: ['Kitchen Splashback', 'Feature Wall', 'Fireplace Wall', 'Accent Wall', 'Shower Wall'],
    custom: ['Complex Layout', 'Multiple Areas', 'L-Shaped Room', 'Alcoves']
  },
  showBoxCalculation: true,
  showPriceEstimate: true,
  infoMessage: 'We recommend ordering 10% extra for cuts and wastage. Always order from the same batch.'
};

export default function TileCalculatorSettings() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState(DEFAULT_CONFIG);

  // Fetch current configuration
  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/calculator-config`);
      if (res.ok) {
        const data = await res.json();
        setConfig({ ...DEFAULT_CONFIG, ...data });
      }
    } catch (error) {
      console.error('Error fetching calculator config:', error);
      // Use defaults if fetch fails
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/calculator-config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      if (res.ok) {
        toast.success('Calculator settings saved successfully');
      } else {
        toast.error('Failed to save settings');
      }
    } catch (error) {
      console.error('Error saving config:', error);
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const updateCalculatorType = (type, field, value) => {
    setConfig(prev => ({
      ...prev,
      calculatorTypes: {
        ...prev.calculatorTypes,
        [type]: {
          ...prev.calculatorTypes[type],
          [field]: value
        }
      }
    }));
  };

  const updateDefaultSubtraction = (type, field, value) => {
    setConfig(prev => ({
      ...prev,
      defaultSubtractions: {
        ...prev.defaultSubtractions,
        [type]: {
          ...prev.defaultSubtractions[type],
          [field]: parseFloat(value) || 0
        }
      }
    }));
  };

  const resetToDefaults = () => {
    setConfig(DEFAULT_CONFIG);
    toast.info('Reset to default settings (not saved yet)');
  };

  const getIconForType = (type) => {
    switch (type) {
      case 'bathroom': return Bath;
      case 'floor': return Home;
      case 'singleWall': return Square;
      case 'custom': return Grid3X3;
      default: return Calculator;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-amber-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="flex items-center justify-between max-w-6xl mx-auto">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => navigate('/admin/website-hub')}
              className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <div className="bg-amber-100 p-2 rounded-lg">
                <Calculator className="w-6 h-6 text-amber-600" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">Tile Calculator Settings</h1>
                <p className="text-sm text-slate-500">Configure calculator options for product pages</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={resetToDefaults}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Reset Defaults
            </Button>
            <Button onClick={saveConfig} disabled={saving} className="bg-amber-500 hover:bg-amber-600">
              {saving ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
              Save Changes
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto p-6 space-y-6">
        {/* Global Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="w-5 h-5" />
              Global Settings
            </CardTitle>
            <CardDescription>Configure general calculator behavior</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Enable/Disable Calculator */}
            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
              <div>
                <Label className="text-base font-medium">Enable Tile Calculator</Label>
                <p className="text-sm text-slate-500">Show calculator on product pages</p>
              </div>
              <Switch
                checked={config.enabled}
                onCheckedChange={(checked) => setConfig(prev => ({ ...prev, enabled: checked }))}
              />
            </div>

            {/* Wastage Settings */}
            <div className="grid grid-cols-2 gap-6">
              <div>
                <Label className="flex items-center gap-2 mb-2">
                  <Percent className="w-4 h-4" />
                  Default Wastage (%)
                </Label>
                <Input
                  type="number"
                  min="0"
                  max="50"
                  value={config.defaultWastage}
                  onChange={(e) => setConfig(prev => ({ ...prev, defaultWastage: parseInt(e.target.value) || 10 }))}
                  className="w-32"
                />
                <p className="text-xs text-slate-500 mt-1">Recommended: 10%</p>
              </div>
              <div>
                <Label className="flex items-center gap-2 mb-2">
                  <Percent className="w-4 h-4" />
                  Maximum Wastage (%)
                </Label>
                <Input
                  type="number"
                  min="0"
                  max="100"
                  value={config.maxWastage}
                  onChange={(e) => setConfig(prev => ({ ...prev, maxWastage: parseInt(e.target.value) || 30 }))}
                  className="w-32"
                />
                <p className="text-xs text-slate-500 mt-1">Maximum user can select</p>
              </div>
            </div>

            {/* Display Options */}
            <div className="grid grid-cols-2 gap-6">
              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                <div>
                  <Label className="font-medium">Show Box Calculation</Label>
                  <p className="text-xs text-slate-500">Display boxes needed when product has box data</p>
                </div>
                <Switch
                  checked={config.showBoxCalculation}
                  onCheckedChange={(checked) => setConfig(prev => ({ ...prev, showBoxCalculation: checked }))}
                />
              </div>
              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                <div>
                  <Label className="font-medium">Show Price Estimate</Label>
                  <p className="text-xs text-slate-500">Display estimated total cost</p>
                </div>
                <Switch
                  checked={config.showPriceEstimate}
                  onCheckedChange={(checked) => setConfig(prev => ({ ...prev, showPriceEstimate: checked }))}
                />
              </div>
            </div>

            {/* Info Message */}
            <div>
              <Label className="flex items-center gap-2 mb-2">
                <Info className="w-4 h-4" />
                Info Message
              </Label>
              <Input
                type="text"
                value={config.infoMessage}
                onChange={(e) => setConfig(prev => ({ ...prev, infoMessage: e.target.value }))}
                placeholder="Helpful message shown below calculator"
              />
              <p className="text-xs text-slate-500 mt-1">Displayed at the bottom of the calculator</p>
            </div>
          </CardContent>
        </Card>

        {/* Calculator Types */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calculator className="w-5 h-5" />
              Calculator Types
            </CardTitle>
            <CardDescription>Enable/disable and customize each calculator mode</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              {Object.entries(config.calculatorTypes).map(([type, typeConfig]) => {
                const Icon = getIconForType(type);
                return (
                  <div 
                    key={type} 
                    className={`p-4 border rounded-lg transition-colors ${
                      typeConfig.enabled ? 'bg-amber-50 border-amber-200' : 'bg-slate-50 border-slate-200'
                    }`}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${typeConfig.enabled ? 'bg-amber-100' : 'bg-slate-200'}`}>
                          <Icon className={`w-5 h-5 ${typeConfig.enabled ? 'text-amber-600' : 'text-slate-400'}`} />
                        </div>
                        <div>
                          <h4 className="font-medium text-slate-900">{typeConfig.name}</h4>
                          <p className="text-xs text-slate-500">{typeConfig.description}</p>
                        </div>
                      </div>
                      <Switch
                        checked={typeConfig.enabled}
                        onCheckedChange={(checked) => updateCalculatorType(type, 'enabled', checked)}
                      />
                    </div>

                    {typeConfig.enabled && (
                      <div className="space-y-3 mt-4 pt-3 border-t border-amber-200">
                        {/* Editable Name */}
                        <div>
                          <Label className="text-xs">Display Name</Label>
                          <Input
                            type="text"
                            value={typeConfig.name}
                            onChange={(e) => updateCalculatorType(type, 'name', e.target.value)}
                            className="h-8 text-sm"
                          />
                        </div>
                        
                        {/* Editable Description */}
                        <div>
                          <Label className="text-xs">Description</Label>
                          <Input
                            type="text"
                            value={typeConfig.description}
                            onChange={(e) => updateCalculatorType(type, 'description', e.target.value)}
                            className="h-8 text-sm"
                          />
                        </div>

                        {/* Wall Height (for bathroom) */}
                        {type === 'bathroom' && (
                          <div>
                            <Label className="text-xs flex items-center gap-1">
                              <Ruler className="w-3 h-3" />
                              Default Wall Height (m)
                            </Label>
                            <Input
                              type="number"
                              step="0.1"
                              min="0"
                              value={typeConfig.defaultWallHeight || 2.4}
                              onChange={(e) => updateCalculatorType(type, 'defaultWallHeight', parseFloat(e.target.value) || 2.4)}
                              className="h-8 text-sm w-24"
                            />
                          </div>
                        )}

                        {/* Show Subtractions */}
                        {(type === 'bathroom' || type === 'singleWall') && (
                          <div className="flex items-center justify-between">
                            <Label className="text-xs">Allow Window/Door Subtraction</Label>
                            <Switch
                              checked={typeConfig.showSubtractions !== false}
                              onCheckedChange={(checked) => updateCalculatorType(type, 'showSubtractions', checked)}
                            />
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Default Subtraction Sizes */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DoorOpen className="w-5 h-5" />
              Default Subtraction Sizes
            </CardTitle>
            <CardDescription>Set default dimensions for windows and doors</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-6">
              {/* Window Defaults */}
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center gap-2 mb-3">
                  <Move className="w-5 h-5 text-blue-600" />
                  <h4 className="font-medium text-blue-900">Window Defaults</h4>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs text-blue-700">Width (m)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      min="0"
                      value={config.defaultSubtractions?.window?.width || 1.2}
                      onChange={(e) => updateDefaultSubtraction('window', 'width', e.target.value)}
                      className="h-8 text-sm"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-blue-700">Height (m)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      min="0"
                      value={config.defaultSubtractions?.window?.height || 1.0}
                      onChange={(e) => updateDefaultSubtraction('window', 'height', e.target.value)}
                      className="h-8 text-sm"
                    />
                  </div>
                </div>
                <p className="text-xs text-blue-600 mt-2">
                  Default: 1.2m × 1.0m = {((config.defaultSubtractions?.window?.width || 1.2) * (config.defaultSubtractions?.window?.height || 1.0)).toFixed(2)}m²
                </p>
              </div>

              {/* Door Defaults */}
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center gap-2 mb-3">
                  <DoorOpen className="w-5 h-5 text-green-600" />
                  <h4 className="font-medium text-green-900">Door Defaults</h4>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs text-green-700">Width (m)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      min="0"
                      value={config.defaultSubtractions?.door?.width || 0.9}
                      onChange={(e) => updateDefaultSubtraction('door', 'width', e.target.value)}
                      className="h-8 text-sm"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-green-700">Height (m)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      min="0"
                      value={config.defaultSubtractions?.door?.height || 2.0}
                      onChange={(e) => updateDefaultSubtraction('door', 'height', e.target.value)}
                      className="h-8 text-sm"
                    />
                  </div>
                </div>
                <p className="text-xs text-green-600 mt-2">
                  Default: {config.defaultSubtractions?.door?.width || 0.9}m × {config.defaultSubtractions?.door?.height || 2.0}m = {((config.defaultSubtractions?.door?.width || 0.9) * (config.defaultSubtractions?.door?.height || 2.0)).toFixed(2)}m²
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Preview Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Eye className="w-5 h-5" />
              Preview
            </CardTitle>
            <CardDescription>See how your calculator configuration will look</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <Calculator className="w-5 h-5 text-amber-600" />
                <span className="font-semibold text-slate-900">Tile Calculator</span>
              </div>
              
              {/* Tab Preview */}
              <div className="flex gap-1 mb-3 p-1 bg-amber-100 rounded-lg">
                {Object.entries(config.calculatorTypes)
                  .filter(([_, tc]) => tc.enabled)
                  .map(([type, tc], idx) => {
                    const Icon = getIconForType(type);
                    return (
                      <div 
                        key={type}
                        className={`flex-1 flex flex-col items-center gap-1 px-2 py-2 rounded-md text-xs ${
                          idx === 0 ? 'bg-amber-500 text-white' : 'text-amber-700'
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                        <span className="font-medium">{tc.name}</span>
                      </div>
                    );
                  })}
              </div>
              
              {/* Preview Description */}
              <p className="text-xs text-amber-700 bg-amber-100 px-2 py-1.5 rounded mb-3">
                {Object.values(config.calculatorTypes).find(t => t.enabled)?.description || 'No calculator types enabled'}
              </p>

              {/* Info Message Preview */}
              <p className="text-xs text-slate-500 flex items-start gap-1">
                <Info className="w-3 h-3 mt-0.5 flex-shrink-0" />
                {config.infoMessage}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
