'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { 
  Calculator, 
  Ruler, 
  Box, 
  Package,
  Check,
  AlertCircle,
  Loader2,
  Search,
  ShoppingCart,
  Info
} from 'lucide-react';
import api, { Product } from '@/lib/api';
import { formatPrice } from '@/lib/utils';

interface CalculationResult {
  room_area_m2: number;
  area_with_wastage_m2: number;
  wastage_percent: number;
  product_name: string;
  product_id: string;
  price_per_unit: number;
  unit: string;
  boxes_needed?: number;
  tiles_needed?: number;
  units_needed?: number;
  box_m2_coverage?: number;
  tile_m2_per_piece?: number;
  tiles_per_box?: number;
  total_coverage_m2?: number;
  total_price: number;
  in_stock: boolean;
  current_stock: number;
}

export default function TileCalculatorPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [showProductSearch, setShowProductSearch] = useState(false);
  const [result, setResult] = useState<CalculationResult | null>(null);
  const [error, setError] = useState('');
  
  const [dimensions, setDimensions] = useState({
    length: '',
    width: '',
    wastage: '10'
  });

  useEffect(() => {
    loadProducts();
  }, []);

  const loadProducts = async () => {
    try {
      const data = await api.getProducts({ limit: 100, in_stock_only: true });
      setProducts(data.products);
    } catch (err) {
      console.error('Failed to load products:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredProducts = products.filter(p => 
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.sku.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCalculate = async () => {
    if (!selectedProduct) {
      setError('Please select a tile product');
      return;
    }
    
    const length = parseFloat(dimensions.length);
    const width = parseFloat(dimensions.width);
    const wastage = parseFloat(dimensions.wastage) || 10;
    
    if (!length || length <= 0) {
      setError('Please enter a valid room length');
      return;
    }
    
    if (!width || width <= 0) {
      setError('Please enter a valid room width');
      return;
    }
    
    setCalculating(true);
    setError('');
    setResult(null);
    
    try {
      const calcResult = await api.calculateTiles({
        room_length: length,
        room_width: width,
        product_id: selectedProduct.id,
        wastage_percent: wastage
      });
      setResult(calcResult);
    } catch (err: any) {
      console.error('Calculation error:', err);
      setError(err.response?.data?.detail || 'Calculation failed. Please try again.');
    } finally {
      setCalculating(false);
    }
  };

  const addToCart = () => {
    if (!result || !selectedProduct) return;
    
    const quantity = result.boxes_needed || result.tiles_needed || result.units_needed || 1;
    
    // Get existing cart
    const existingCart = localStorage.getItem('shop_cart');
    const cart = existingCart ? JSON.parse(existingCart) : [];
    
    // Check if product already in cart
    const existingIndex = cart.findIndex((item: any) => item.product_id === selectedProduct.id);
    
    if (existingIndex >= 0) {
      cart[existingIndex].quantity += quantity;
    } else {
      cart.push({
        product_id: selectedProduct.id,
        name: selectedProduct.name,
        sku: selectedProduct.sku,
        price: selectedProduct.price,
        quantity: quantity,
        image: selectedProduct.images?.[0] || ''
      });
    }
    
    localStorage.setItem('shop_cart', JSON.stringify(cart));
    
    // Dispatch event for cart update
    window.dispatchEvent(new Event('cart-updated'));
    
    // Show success message (could use toast, but keeping it simple)
    alert(`Added ${quantity} ${result.boxes_needed ? 'boxes' : result.tiles_needed ? 'tiles' : 'units'} to cart!`);
  };

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="text-center mb-10">
        <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Calculator className="w-8 h-8 text-amber-600" />
        </div>
        <h1 className="text-2xl md:text-3xl font-bold text-slate-900 mb-2">Tile Calculator</h1>
        <p className="text-slate-500 max-w-xl mx-auto">
          Calculate exactly how many tiles you need for your project. Enter your room dimensions and select a tile to get an accurate estimate.
        </p>
      </div>

      <div className="max-w-4xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Calculator Form */}
          <div className="space-y-6">
            {/* Room Dimensions */}
            <div className="bg-white p-6 rounded-xl shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
                <Ruler className="w-5 h-5 text-amber-600" />
                Room Dimensions
              </h2>
              
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="length" className="block text-sm font-medium text-slate-700 mb-1">
                      Length (metres)
                    </label>
                    <input
                      id="length"
                      type="number"
                      step="0.01"
                      min="0"
                      value={dimensions.length}
                      onChange={(e) => setDimensions(prev => ({ ...prev, length: e.target.value }))}
                      placeholder="e.g. 4.5"
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                      data-testid="calc-length-input"
                    />
                  </div>
                  <div>
                    <label htmlFor="width" className="block text-sm font-medium text-slate-700 mb-1">
                      Width (metres)
                    </label>
                    <input
                      id="width"
                      type="number"
                      step="0.01"
                      min="0"
                      value={dimensions.width}
                      onChange={(e) => setDimensions(prev => ({ ...prev, width: e.target.value }))}
                      placeholder="e.g. 3.2"
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                      data-testid="calc-width-input"
                    />
                  </div>
                </div>
                
                <div>
                  <label htmlFor="wastage" className="block text-sm font-medium text-slate-700 mb-1">
                    Wastage Allowance (%)
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      id="wastage"
                      type="range"
                      min="5"
                      max="20"
                      value={dimensions.wastage}
                      onChange={(e) => setDimensions(prev => ({ ...prev, wastage: e.target.value }))}
                      className="flex-1 accent-amber-500"
                    />
                    <span className="w-12 text-center font-medium">{dimensions.wastage}%</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    We recommend 10% for simple layouts, 15-20% for complex patterns or diagonal layouts.
                  </p>
                </div>
              </div>
            </div>

            {/* Product Selection */}
            <div className="bg-white p-6 rounded-xl shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
                <Box className="w-5 h-5 text-amber-600" />
                Select Tile
              </h2>
              
              {selectedProduct ? (
                <div className="flex items-center gap-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                  <div className="w-16 h-16 bg-gray-100 rounded-lg overflow-hidden flex-shrink-0 relative">
                    {selectedProduct.images?.[0] ? (
                      <Image
                        src={selectedProduct.images[0]}
                        alt={selectedProduct.name}
                        fill
                        className="object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-2xl">🪨</div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-slate-900 line-clamp-1">{selectedProduct.name}</p>
                    <p className="text-sm text-slate-500">{formatPrice(selectedProduct.price)} per {selectedProduct.unit || 'unit'}</p>
                    {selectedProduct.box_m2_coverage && (
                      <p className="text-xs text-amber-600">{selectedProduct.box_m2_coverage} m² per box</p>
                    )}
                  </div>
                  <button
                    onClick={() => {
                      setSelectedProduct(null);
                      setResult(null);
                    }}
                    className="text-sm text-slate-500 hover:text-slate-700"
                  >
                    Change
                  </button>
                </div>
              ) : (
                <div className="relative">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Search tiles by name or SKU..."
                      value={searchQuery}
                      onChange={(e) => {
                        setSearchQuery(e.target.value);
                        setShowProductSearch(true);
                      }}
                      onFocus={() => setShowProductSearch(true)}
                      className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                      data-testid="product-search-input"
                    />
                  </div>
                  
                  {showProductSearch && (
                    <div className="absolute z-10 w-full mt-2 bg-white border border-gray-200 rounded-lg shadow-lg max-h-64 overflow-y-auto">
                      {loading ? (
                        <div className="p-4 text-center text-slate-500">
                          <Loader2 className="w-5 h-5 animate-spin mx-auto" />
                        </div>
                      ) : filteredProducts.length === 0 ? (
                        <div className="p-4 text-center text-slate-500">
                          No tiles found
                        </div>
                      ) : (
                        filteredProducts.slice(0, 10).map((product) => (
                          <button
                            key={product.id}
                            onClick={() => {
                              setSelectedProduct(product);
                              setShowProductSearch(false);
                              setSearchQuery('');
                              setResult(null);
                            }}
                            className="w-full flex items-center gap-3 p-3 hover:bg-gray-50 text-left border-b last:border-0"
                          >
                            <div className="w-10 h-10 bg-gray-100 rounded overflow-hidden flex-shrink-0 relative">
                              {product.images?.[0] ? (
                                <Image
                                  src={product.images[0]}
                                  alt={product.name}
                                  fill
                                  className="object-cover"
                                />
                              ) : (
                                <div className="w-full h-full flex items-center justify-center text-sm">🪨</div>
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-sm text-slate-900 line-clamp-1">{product.name}</p>
                              <p className="text-xs text-slate-500">{formatPrice(product.price)}</p>
                            </div>
                            {product.in_stock ? (
                              <span className="text-xs text-green-600">In Stock</span>
                            ) : (
                              <span className="text-xs text-red-500">Out of Stock</span>
                            )}
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}

            {/* Calculate Button */}
            <button
              onClick={handleCalculate}
              disabled={calculating || !selectedProduct}
              className="w-full flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-300 text-slate-900 font-semibold py-3 rounded-lg transition-colors"
              data-testid="calculate-btn"
            >
              {calculating ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Calculating...
                </>
              ) : (
                <>
                  <Calculator className="w-5 h-5" />
                  Calculate Tiles Needed
                </>
              )}
            </button>
          </div>

          {/* Results */}
          <div>
            {result ? (
              <div className="bg-white p-6 rounded-xl shadow-sm space-y-6">
                <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
                  <Package className="w-5 h-5 text-amber-600" />
                  Your Estimate
                </h2>

                {/* Summary Cards */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-50 p-4 rounded-lg text-center">
                    <p className="text-sm text-slate-500">Room Area</p>
                    <p className="text-2xl font-bold text-slate-900">{result.room_area_m2} m²</p>
                  </div>
                  <div className="bg-amber-50 p-4 rounded-lg text-center">
                    <p className="text-sm text-slate-500">With {result.wastage_percent}% Wastage</p>
                    <p className="text-2xl font-bold text-amber-600">{result.area_with_wastage_m2} m²</p>
                  </div>
                </div>

                {/* What You Need */}
                <div className="border-t pt-6">
                  <h3 className="font-medium text-slate-900 mb-3">What You Need</h3>
                  <div className="space-y-3">
                    {result.boxes_needed && (
                      <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                        <div className="flex items-center gap-2">
                          <Box className="w-5 h-5 text-green-600" />
                          <span className="font-medium">Boxes Required</span>
                        </div>
                        <span className="text-xl font-bold text-green-600">{result.boxes_needed}</span>
                      </div>
                    )}
                    {result.tiles_needed && (
                      <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                        <div className="flex items-center gap-2">
                          <Package className="w-5 h-5 text-blue-600" />
                          <span className="font-medium">Tiles Required</span>
                        </div>
                        <span className="text-xl font-bold text-blue-600">{result.tiles_needed}</span>
                      </div>
                    )}
                    {result.units_needed && !result.boxes_needed && !result.tiles_needed && (
                      <div className="flex items-center justify-between p-3 bg-purple-50 rounded-lg">
                        <div className="flex items-center gap-2">
                          <Package className="w-5 h-5 text-purple-600" />
                          <span className="font-medium">Units Required</span>
                        </div>
                        <span className="text-xl font-bold text-purple-600">{result.units_needed}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Coverage Info */}
                {(result.box_m2_coverage || result.tile_m2_per_piece) && (
                  <div className="text-sm text-slate-500 space-y-1">
                    {result.box_m2_coverage && (
                      <p>• Each box covers {result.box_m2_coverage} m²</p>
                    )}
                    {result.tiles_per_box && (
                      <p>• {result.tiles_per_box} tiles per box</p>
                    )}
                    {result.total_coverage_m2 && (
                      <p>• Total coverage: {result.total_coverage_m2} m²</p>
                    )}
                  </div>
                )}

                {/* Price & Stock */}
                <div className="border-t pt-6">
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-slate-500">Estimated Total</span>
                    <span className="text-2xl font-bold text-slate-900">{formatPrice(result.total_price)}</span>
                  </div>
                  
                  <div className="flex items-center gap-2 mb-4">
                    {result.in_stock ? (
                      <>
                        <Check className="w-5 h-5 text-green-500" />
                        <span className="text-green-600 font-medium">In Stock ({result.current_stock} available)</span>
                      </>
                    ) : (
                      <>
                        <AlertCircle className="w-5 h-5 text-orange-500" />
                        <span className="text-orange-600 font-medium">
                          Low Stock - Only {result.current_stock} available
                        </span>
                      </>
                    )}
                  </div>

                  <button
                    onClick={addToCart}
                    disabled={!result.in_stock}
                    className="w-full flex items-center justify-center gap-2 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-300 text-white font-semibold py-3 rounded-lg transition-colors"
                    data-testid="add-to-cart-btn"
                  >
                    <ShoppingCart className="w-5 h-5" />
                    Add {result.boxes_needed || result.tiles_needed || result.units_needed} to Cart
                  </button>
                </div>

                {/* Info Note */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex gap-3">
                  <Info className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-blue-700">
                    <p className="font-medium mb-1">Important Note</p>
                    <p>This is an estimate only. Actual requirements may vary based on tile layout, pattern, and room shape. We recommend consulting with our team for complex projects.</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-white p-6 rounded-xl shadow-sm">
                <div className="text-center py-12">
                  <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Calculator className="w-8 h-8 text-slate-400" />
                  </div>
                  <h3 className="font-medium text-slate-900 mb-2">Ready to Calculate</h3>
                  <p className="text-sm text-slate-500 max-w-xs mx-auto">
                    Enter your room dimensions and select a tile to see how many you need for your project.
                  </p>
                </div>
              </div>
            )}

            {/* Quick Tips */}
            <div className="mt-6 bg-slate-50 p-4 rounded-xl">
              <h3 className="font-medium text-slate-900 mb-3">Quick Tips</h3>
              <ul className="text-sm text-slate-600 space-y-2">
                <li>• Measure your room at the widest points</li>
                <li>• Don't forget alcoves and recesses</li>
                <li>• Add extra wastage for diagonal patterns</li>
                <li>• Keep spare tiles for future repairs</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Browse Products CTA */}
        <div className="mt-12 text-center">
          <p className="text-slate-500 mb-4">Not sure which tile to choose?</p>
          <Link
            href="/products"
            className="inline-flex items-center gap-2 text-amber-600 hover:text-amber-700 font-medium"
          >
            Browse our tile collection →
          </Link>
        </div>
      </div>
    </div>
  );
}
