import React from 'react';
import { RefreshCw, Check, X, Eye, Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../../components/ui/dialog';
import { Button } from '../../../../components/ui/button';
import { toast } from 'sonner';

const CanopyStockModal = ({
  open,
  onOpenChange,
  canopyStockStep,
  setCanopyStockStep,
  canopyStockText,
  setCanopyStockText,
  canopyStockLoading,
  setCanopyStockLoading,
  canopyStockPreview,
  setCanopyStockPreview,
  api,
  fetchProducts
}) => {
  const handleParse = async () => {
    setCanopyStockLoading(true);
    try {
      const response = await api.post('/canopy-stock/parse', {
        raw_text: canopyStockText
      });
      setCanopyStockPreview(response.data);
      setCanopyStockStep('preview');
    } catch (error) {
      toast.error('Failed to parse stock data: ' + (error.response?.data?.detail || error.message));
    } finally {
      setCanopyStockLoading(false);
    }
  };

  const handleApply = async () => {
    setCanopyStockLoading(true);
    try {
      const response = await api.post('/canopy-stock/update', {
        raw_text: canopyStockText
      });
      setCanopyStockPreview({
        ...canopyStockPreview,
        result: response.data
      });
      setCanopyStockStep('result');
      fetchProducts?.();
    } catch (error) {
      toast.error('Failed to update stock: ' + (error.response?.data?.detail || error.message));
    } finally {
      setCanopyStockLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <RefreshCw className="w-5 h-5 text-amber-600" />
            Canopy Stock Update
          </DialogTitle>
        </DialogHeader>

        {canopyStockStep === 'input' && (
          <div className="space-y-4">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <h4 className="font-medium text-amber-800 mb-2">How to update stock:</h4>
              <ol className="list-decimal list-inside text-sm text-amber-700 space-y-1">
                <li>Open <a href="https://canopyflooring.co.uk/pages/stock-report" target="_blank" rel="noopener noreferrer" className="text-amber-600 underline hover:text-amber-800">Canopy Stock Report</a> in a new tab</li>
                <li>Wait for the page to load (complete the reCAPTCHA if needed)</li>
                <li>Select and copy the stock data from the table (Ctrl+A, Ctrl+C)</li>
                <li>Paste it in the text area below</li>
              </ol>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Paste Stock Data Here:
              </label>
              <textarea
                className="w-full h-64 p-3 border border-gray-300 rounded-lg font-mono text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                placeholder={`Paste stock data here...

Example formats supported:
Product Name    Quantity
Swinley Oak     50
Ashdown Oak     30

Or comma-separated:
Swinley Oak, 50, In Stock
Ashdown Oak, 0, Out of Stock`}
                value={canopyStockText}
                onChange={(e) => setCanopyStockText(e.target.value)}
              />
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                className="bg-amber-600 hover:bg-amber-700"
                disabled={!canopyStockText.trim() || canopyStockLoading}
                onClick={handleParse}
              >
                {canopyStockLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Parsing...
                  </>
                ) : (
                  <>
                    <Eye className="w-4 h-4 mr-2" />
                    Preview Changes
                  </>
                )}
              </Button>
            </DialogFooter>
          </div>
        )}

        {canopyStockStep === 'preview' && canopyStockPreview && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-gray-50 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-gray-700">{canopyStockPreview.total_items}</div>
                <div className="text-sm text-gray-500">Total Items</div>
              </div>
              <div className="bg-green-50 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-green-600">{canopyStockPreview.matched}</div>
                <div className="text-sm text-green-600">Matched</div>
              </div>
              <div className="bg-red-50 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-red-600">{canopyStockPreview.unmatched}</div>
                <div className="text-sm text-red-600">Not Found</div>
              </div>
            </div>

            <div className="border rounded-lg max-h-80 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left">Status</th>
                    <th className="px-3 py-2 text-left">Input Name</th>
                    <th className="px-3 py-2 text-left">Matched Product</th>
                    <th className="px-3 py-2 text-right">Packs</th>
                    <th className="px-3 py-2 text-right">m²</th>
                    <th className="px-3 py-2 text-center">Stock</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {canopyStockPreview.items?.map((item, idx) => (
                    <tr key={idx} className={item.matched ? '' : 'bg-red-50'}>
                      <td className="px-3 py-2">
                        {item.matched ? (
                          <Check className="w-4 h-4 text-green-600" />
                        ) : (
                          <X className="w-4 h-4 text-red-600" />
                        )}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs truncate max-w-[200px]" title={item.input_name}>
                        {item.input_name}
                      </td>
                      <td className="px-3 py-2 text-xs truncate max-w-[180px]" title={item.matched_product}>
                        {item.matched_product || <span className="text-red-500 italic">Not found</span>}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-xs">
                        {item.packs !== null ? item.packs.toLocaleString() : '-'}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-xs">
                        {item.stock_m2 !== null ? item.stock_m2.toLocaleString() : '-'}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <span className={`px-2 py-1 rounded text-xs ${
                          item.status === 'in_stock' ? 'bg-green-100 text-green-700' :
                          item.status === 'out_of_stock' ? 'bg-red-100 text-red-700' :
                          'bg-yellow-100 text-yellow-700'
                        }`}>
                          {item.status === 'in_stock' ? 'In Stock' : item.status === 'out_of_stock' ? 'Out' : 'Low'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setCanopyStockStep('input')}>
                Back
              </Button>
              <Button
                className="bg-amber-600 hover:bg-amber-700"
                disabled={canopyStockLoading || canopyStockPreview.matched === 0}
                onClick={handleApply}
              >
                {canopyStockLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Updating...
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4 mr-2" />
                    Apply {canopyStockPreview.matched} Updates
                  </>
                )}
              </Button>
            </DialogFooter>
          </div>
        )}

        {canopyStockStep === 'result' && canopyStockPreview?.result && (
          <div className="space-y-4">
            <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
              <Check className="w-12 h-12 text-green-600 mx-auto mb-3" />
              <h3 className="text-xl font-bold text-green-800">Stock Updated Successfully!</h3>
              <p className="text-green-600 mt-2">
                {canopyStockPreview.result.updated} products updated
              </p>
              {canopyStockPreview.result.not_found > 0 && (
                <p className="text-amber-600 text-sm mt-1">
                  {canopyStockPreview.result.not_found} products not found
                </p>
              )}
            </div>

            {canopyStockPreview.result.not_found_items?.length > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                <h4 className="font-medium text-amber-800 mb-2">Products Not Found:</h4>
                <div className="text-sm text-amber-700 max-h-32 overflow-y-auto">
                  {canopyStockPreview.result.not_found_items.map((name, idx) => (
                    <div key={idx} className="py-1">{name}</div>
                  ))}
                </div>
              </div>
            )}

            <DialogFooter>
              <Button onClick={() => onOpenChange(false)}>
                Done
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default CanopyStockModal;
