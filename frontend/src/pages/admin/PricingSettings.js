import React, { useState, useEffect } from 'react';
import { 
  Settings, Percent, DollarSign, RefreshCw, Save, AlertTriangle,
  Check, Building2, ChevronDown, ChevronUp, Calculator, Loader2
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const PricingSettings = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [config, setConfig] = useState(null);
  const [globalMarkup, setGlobalMarkup] = useState(130);
  const [vatPercentage, setVatPercentage] = useState(20);
  const [roundTo99, setRoundTo99] = useState(true);
  const [supplierMarkups, setSupplierMarkups] = useState({});
  const [expandedSuppliers, setExpandedSuppliers] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/supplier-sync/admin/pricing-config`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
        setGlobalMarkup(data.global_markup_percentage || 130);
        setVatPercentage(data.vat_percentage || 20);
        setRoundTo99(data.round_to_99 !== false);
        
        // Build supplier markups object
        const markups = {};
        data.suppliers?.forEach(s => {
          if (s.is_custom) {
            markups[s.name] = s.markup_percentage;
          }
        });
        setSupplierMarkups(markups);
      }
    } catch (error) {
      console.error('Error fetching pricing config:', error);
      toast.error('Failed to load pricing configuration');
    } finally {
      setLoading(false);
    }
  };

  const calculatePrice = (cost, markup) => {
    if (!cost || cost <= 0) return 0;
    const markupMult = 1 + (markup / 100);
    const vatMult = 1 + (vatPercentage / 100);
    const rawPrice = cost * markupMult * vatMult;
    if (roundTo99) {
      return Math.ceil(rawPrice) - 0.01;
    }
    return Math.round(rawPrice * 100) / 100;
  };

  const saveConfig = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/supplier-sync/admin/pricing-config`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          global_markup_percentage: globalMarkup,
          vat_percentage: vatPercentage,
          round_to_99: roundTo99,
          supplier_markups: supplierMarkups
        })
      });
      
      if (response.ok) {
        toast.success('Pricing configuration saved!');
        fetchConfig();
      } else {
        toast.error('Failed to save configuration');
      }
    } catch (error) {
      console.error('Error saving config:', error);
      toast.error('Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const recalculateAllPrices = async () => {
    if (!window.confirm('This will update prices for ALL products based on current settings. Continue?')) {
      return;
    }
    
    setRecalculating(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/supplier-sync/admin/recalculate-all-prices`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const result = await response.json();
        setLastUpdate(result);
        toast.success(`Updated ${result.supplier_products_updated} products and ${result.tiles_updated} tiles!`);
        fetchConfig();
      } else {
        toast.error('Failed to recalculate prices');
      }
    } catch (error) {
      console.error('Error recalculating:', error);
      toast.error('Failed to recalculate prices');
    } finally {
      setRecalculating(false);
    }
  };

  const setSupplierMarkup = (supplier, value) => {
    if (value === '' || value === null) {
      // Remove custom markup
      const newMarkups = { ...supplierMarkups };
      delete newMarkups[supplier];
      setSupplierMarkups(newMarkups);
    } else {
      setSupplierMarkups(prev => ({
        ...prev,
        [supplier]: parseFloat(value)
      }));
    }
  };

  const getSupplierMarkup = (supplier) => {
    return supplierMarkups[supplier] !== undefined ? supplierMarkups[supplier] : globalMarkup;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Settings className="w-6 h-6 text-purple-600" />
          Pricing Settings
        </h1>
        <p className="text-gray-600 mt-1">
          Configure markup percentages and update product prices
        </p>
      </div>

      {/* Global Settings Card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <Percent className="w-5 h-5 text-amber-600" />
          Global Pricing Formula
        </h2>
        
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
          <p className="text-amber-800 font-medium text-sm">
            List Price = Cost × (1 + Markup%) × (1 + VAT%) → Round to .99p
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Markup Percentage */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Global Markup %
            </label>
            <div className="relative">
              <Input
                type="number"
                value={globalMarkup}
                onChange={(e) => setGlobalMarkup(parseFloat(e.target.value) || 0)}
                className="pr-8"
                min="0"
                max="500"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">%</span>
            </div>
            <p className="text-xs text-gray-500 mt-1">Default for all suppliers</p>
          </div>

          {/* VAT Percentage */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              VAT %
            </label>
            <div className="relative">
              <Input
                type="number"
                value={vatPercentage}
                onChange={(e) => setVatPercentage(parseFloat(e.target.value) || 0)}
                className="pr-8"
                min="0"
                max="100"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">%</span>
            </div>
            <p className="text-xs text-gray-500 mt-1">UK VAT rate</p>
          </div>

          {/* Round to 99 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Price Rounding
            </label>
            <div className="flex items-center gap-3 h-10">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={roundTo99}
                  onChange={(e) => setRoundTo99(e.target.checked)}
                  className="w-5 h-5 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                />
                <span className="text-sm text-gray-700">Round to .99p</span>
              </label>
            </div>
            <p className="text-xs text-gray-500 mt-1">e.g., £27.80 → £27.99</p>
          </div>
        </div>

        {/* Price Calculator */}
        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
          <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
            <Calculator className="w-4 h-4" />
            Price Calculator Preview
          </h3>
          <div className="grid grid-cols-4 gap-4 text-center">
            {[5, 10, 15, 20, 25, 30, 40, 50].map(cost => (
              <div key={cost} className="bg-white rounded-lg p-3 border border-gray-200">
                <div className="text-xs text-gray-500">Cost £{cost}</div>
                <div className="text-lg font-bold text-green-600">
                  £{calculatePrice(cost, globalMarkup).toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Per-Supplier Markups */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div 
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setExpandedSuppliers(!expandedSuppliers)}
        >
          <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
            <Building2 className="w-5 h-5 text-blue-600" />
            Per-Supplier Markups
            <span className="text-sm font-normal text-gray-500">
              ({Object.keys(supplierMarkups).length} custom)
            </span>
          </h2>
          {expandedSuppliers ? (
            <ChevronUp className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          )}
        </div>

        {expandedSuppliers && config?.suppliers && (
          <div className="mt-4 space-y-2 max-h-96 overflow-y-auto">
            <p className="text-sm text-gray-500 mb-3">
              Set custom markup for specific suppliers. Leave empty to use global markup.
            </p>
            
            {config.suppliers.map(supplier => (
              <div 
                key={supplier.name}
                className={`flex items-center gap-4 p-3 rounded-lg border ${
                  supplierMarkups[supplier.name] !== undefined
                    ? 'bg-blue-50 border-blue-200'
                    : 'bg-gray-50 border-gray-200'
                }`}
              >
                <div className="flex-1">
                  <div className="font-medium text-gray-800">{supplier.name}</div>
                  <div className="text-xs text-gray-500">{supplier.product_count} products</div>
                </div>
                
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    value={supplierMarkups[supplier.name] ?? ''}
                    onChange={(e) => setSupplierMarkup(supplier.name, e.target.value)}
                    placeholder={globalMarkup.toString()}
                    className="w-24 text-center"
                    min="0"
                    max="500"
                  />
                  <span className="text-gray-400">%</span>
                  
                  {supplierMarkups[supplier.name] !== undefined && (
                    <button
                      onClick={() => setSupplierMarkup(supplier.name, null)}
                      className="text-xs text-red-600 hover:text-red-700"
                    >
                      Reset
                    </button>
                  )}
                </div>
                
                <div className="text-right w-24">
                  <div className="text-xs text-gray-500">£10 cost →</div>
                  <div className="font-semibold text-green-600">
                    £{calculatePrice(10, getSupplierMarkup(supplier.name)).toFixed(2)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex flex-col sm:flex-row gap-4">
          <Button
            onClick={saveConfig}
            disabled={saving}
            className="flex-1 bg-purple-600 hover:bg-purple-700"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            Save Configuration
          </Button>
          
          <Button
            onClick={recalculateAllPrices}
            disabled={recalculating}
            className="flex-1 bg-green-600 hover:bg-green-700"
          >
            {recalculating ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            Update All Prices Now
          </Button>
        </div>

        <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-amber-800">
              <strong>Important:</strong> Click "Save Configuration" to save your settings, then 
              "Update All Prices Now" to apply the new prices to all products in the database.
            </div>
          </div>
        </div>
      </div>

      {/* Last Update Results */}
      {lastUpdate && (
        <div className="mt-6 bg-green-50 border border-green-200 rounded-xl p-6">
          <h3 className="font-semibold text-green-800 flex items-center gap-2 mb-3">
            <Check className="w-5 h-5" />
            Last Update Results
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div className="bg-white rounded-lg p-3">
              <div className="text-2xl font-bold text-green-600">{lastUpdate.supplier_products_updated}</div>
              <div className="text-xs text-gray-500">Products Updated</div>
            </div>
            <div className="bg-white rounded-lg p-3">
              <div className="text-2xl font-bold text-blue-600">{lastUpdate.tiles_updated}</div>
              <div className="text-xs text-gray-500">Tiles Updated</div>
            </div>
            <div className="bg-white rounded-lg p-3">
              <div className="text-2xl font-bold text-purple-600">{lastUpdate.global_markup_percentage}%</div>
              <div className="text-xs text-gray-500">Global Markup</div>
            </div>
            <div className="bg-white rounded-lg p-3">
              <div className="text-2xl font-bold text-amber-600">{lastUpdate.supplier_markups_applied?.length || 0}</div>
              <div className="text-xs text-gray-500">Custom Markups</div>
            </div>
          </div>
          
          {lastUpdate.sample_updates?.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-medium text-green-800 mb-2">Sample Updates:</h4>
              <div className="bg-white rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left">SKU</th>
                      <th className="px-3 py-2 text-left">Supplier</th>
                      <th className="px-3 py-2 text-right">Cost</th>
                      <th className="px-3 py-2 text-right">Markup</th>
                      <th className="px-3 py-2 text-right">New Price</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lastUpdate.sample_updates.map((item, idx) => (
                      <tr key={idx} className="border-t">
                        <td className="px-3 py-2 font-mono text-xs">{item.sku}</td>
                        <td className="px-3 py-2">{item.supplier}</td>
                        <td className="px-3 py-2 text-right">£{item.cost?.toFixed(2)}</td>
                        <td className="px-3 py-2 text-right">{item.markup}%</td>
                        <td className="px-3 py-2 text-right font-semibold text-green-600">£{item.new_price?.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PricingSettings;
