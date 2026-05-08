'use client';

import { useState } from 'react';
import { ShoppingCart, Minus, Plus } from 'lucide-react';
import { Product } from '@/lib/api';
import { formatPrice } from '@/lib/utils';

interface AddToCartButtonProps {
  product: Product;
  currentPrice: number;
}

export function AddToCartButton({ product, currentPrice }: AddToCartButtonProps) {
  const [quantity, setQuantity] = useState(1);
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);

  const handleAddToCart = async () => {
    setAdding(true);
    
    // For now, save to localStorage (guest cart)
    try {
      const cart = JSON.parse(localStorage.getItem('shop_cart') || '[]');
      
      const existingIdx = cart.findIndex((item: any) => item.product_id === product.id);
      
      if (existingIdx >= 0) {
        cart[existingIdx].quantity += quantity;
      } else {
        cart.push({
          product_id: product.id,
          name: product.name,
          sku: product.sku,
          price: currentPrice,
          quantity,
          image: product.images?.[0] || '',
        });
      }
      
      localStorage.setItem('shop_cart', JSON.stringify(cart));
      
      // Dispatch custom event for cart updates
      window.dispatchEvent(new CustomEvent('cart-updated'));
      
      setAdded(true);
      setTimeout(() => setAdded(false), 2000);
    } catch (error) {
      console.error('Failed to add to cart:', error);
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="flex flex-col sm:flex-row gap-4 mb-6">
      <div className="flex items-center border border-gray-200 rounded-lg">
        <button
          onClick={() => setQuantity(Math.max(1, quantity - 1))}
          disabled={quantity <= 1}
          className="p-3 hover:bg-gray-50 disabled:opacity-50"
        >
          <Minus className="w-4 h-4" />
        </button>
        <input
          type="number"
          value={quantity}
          onChange={(e) => setQuantity(Math.max(1, Math.min(product.stock, parseInt(e.target.value) || 1)))}
          className="w-16 text-center border-0 focus:ring-0"
          min="1"
          max={product.stock}
        />
        <button
          onClick={() => setQuantity(Math.min(product.stock, quantity + 1))}
          disabled={quantity >= product.stock}
          className="p-3 hover:bg-gray-50 disabled:opacity-50"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>
      
      <button
        onClick={handleAddToCart}
        disabled={adding}
        className={`flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-semibold transition-colors ${
          added
            ? 'bg-green-500 text-white'
            : 'bg-amber-500 hover:bg-amber-600 text-slate-900'
        }`}
      >
        <ShoppingCart className="w-5 h-5" />
        {adding ? 'Adding...' : added ? 'Added to Cart!' : `Add to Cart - ${formatPrice(currentPrice * quantity)}`}
      </button>
    </div>
  );
}
