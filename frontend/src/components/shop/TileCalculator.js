import React, { useState } from 'react';
import { Calculator, Info, ShoppingCart } from 'lucide-react';
import { api } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';

export const TileCalculator = ({ product, onAddToCart }) => {
  const [roomLength, setRoomLength] = useState('');
  const [roomWidth, setRoomWidth] = useState('');
  const [wastage, setWastage] = useState(10);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleCalculate = async () => {
    if (!roomLength || !roomWidth) {
      toast.error('Please enter room dimensions');
      return;
    }

    setLoading(true);
    try {
      const response = await api.shopCalculateTiles({
        room_length: parseFloat(roomLength),
        room_width: parseFloat(roomWidth),
        product_id: product.id,
        wastage_percent: wastage
      });
      setResult(response.data);
    } catch (error) {
      toast.error('Calculation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleAddCalculatedToCart = () => {
    if (!result) return;
    
    const quantity = result.boxes_needed || result.tiles_needed || result.units_needed;
    onAddToCart(quantity);
  };

  const formatPrice = (price) => `£${price?.toFixed(2) || '0.00'}`;

  return (
    <Card className="p-4 bg-amber-50 border-amber-200">
      <div className="flex items-center gap-2 mb-4">
        <Calculator className="w-5 h-5 text-amber-600" />
        <h3 className="font-semibold text-slate-900">Tile Calculator</h3>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <Label htmlFor="room-length" className="text-sm">Room Length (m)</Label>
          <Input
            id="room-length"
            type="number"
            step="0.1"
            min="0"
            placeholder="e.g. 5.0"
            value={roomLength}
            onChange={(e) => setRoomLength(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="room-width" className="text-sm">Room Width (m)</Label>
          <Input
            id="room-width"
            type="number"
            step="0.1"
            min="0"
            placeholder="e.g. 4.0"
            value={roomWidth}
            onChange={(e) => setRoomWidth(e.target.value)}
          />
        </div>
      </div>

      <div className="mb-4">
        <Label htmlFor="wastage" className="text-sm flex items-center gap-1">
          Wastage Allowance
          <span className="text-xs text-slate-500">(recommended: 10%)</span>
        </Label>
        <div className="flex items-center gap-2">
          <Input
            id="wastage"
            type="number"
            min="0"
            max="30"
            value={wastage}
            onChange={(e) => setWastage(parseInt(e.target.value) || 0)}
            className="w-20"
          />
          <span className="text-sm text-slate-500">%</span>
        </div>
      </div>

      <Button 
        onClick={handleCalculate} 
        disabled={loading}
        className="w-full mb-4"
        variant="outline"
      >
        {loading ? 'Calculating...' : 'Calculate'}
      </Button>

      {result && (
        <div className="bg-white rounded-lg p-4 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-slate-500">Room Area:</span>
            <span className="font-medium">{result.room_area_m2} m²</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-500">With {wastage}% Wastage:</span>
            <span className="font-medium">{result.area_with_wastage_m2} m²</span>
          </div>
          
          <hr className="my-2" />
          
          {result.boxes_needed && (
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Boxes Needed:</span>
              <span className="font-bold text-lg">{result.boxes_needed}</span>
            </div>
          )}
          {result.tiles_needed && (
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Tiles Needed:</span>
              <span className="font-bold text-lg">{result.tiles_needed}</span>
            </div>
          )}
          {result.units_needed && !result.boxes_needed && !result.tiles_needed && (
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Units Needed:</span>
              <span className="font-bold text-lg">{result.units_needed}</span>
            </div>
          )}
          
          <div className="flex justify-between text-sm">
            <span className="text-slate-500">Estimated Total:</span>
            <span className="font-bold text-amber-600">{formatPrice(result.total_price)}</span>
          </div>

          {!result.in_stock && (
            <p className="text-xs text-red-600 mt-2">
              ⚠️ Not enough stock available. Current stock: {result.current_stock}
            </p>
          )}

          {result.in_stock && onAddToCart && (
            <Button 
              onClick={handleAddCalculatedToCart}
              className="w-full mt-3 bg-amber-500 hover:bg-amber-600 text-slate-900"
            >
              <ShoppingCart className="w-4 h-4 mr-2" />
              Add {result.boxes_needed || result.tiles_needed || result.units_needed} to Cart
            </Button>
          )}
        </div>
      )}

      <p className="text-xs text-slate-500 mt-3 flex items-start gap-1">
        <Info className="w-3 h-3 mt-0.5 flex-shrink-0" />
        We recommend ordering 10% extra for cuts and wastage. Actual coverage may vary.
      </p>
    </Card>
  );
};

export default TileCalculator;
