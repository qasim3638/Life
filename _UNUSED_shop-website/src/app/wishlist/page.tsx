'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { 
  Heart, 
  ShoppingCart, 
  Trash2, 
  Loader2,
  LogIn,
  Package
} from 'lucide-react';
import api, { Product } from '@/lib/api';
import { formatPrice } from '@/lib/utils';

export default function WishlistPage() {
  const [wishlist, setWishlist] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);

  useEffect(() => {
    checkAuthAndLoadWishlist();
  }, []);

  const checkAuthAndLoadWishlist = async () => {
    const token = localStorage.getItem('shop_token');
    if (!token) {
      setIsLoggedIn(false);
      setLoading(false);
      return;
    }
    
    setIsLoggedIn(true);
    
    try {
      const data = await api.getWishlist(token);
      setWishlist(data);
    } catch (err: any) {
      console.error('Failed to load wishlist:', err);
      if (err.response?.status === 401) {
        localStorage.removeItem('shop_token');
        setIsLoggedIn(false);
      }
    } finally {
      setLoading(false);
    }
  };

  const removeFromWishlist = async (productId: string) => {
    const token = localStorage.getItem('shop_token');
    if (!token) return;
    
    setRemovingId(productId);
    
    try {
      await api.removeFromWishlist(token, productId);
      setWishlist(prev => prev.filter(p => p.id !== productId));
    } catch (err) {
      console.error('Failed to remove from wishlist:', err);
    } finally {
      setRemovingId(null);
    }
  };

  const addToCart = (product: Product) => {
    const existingCart = localStorage.getItem('shop_cart');
    const cart = existingCart ? JSON.parse(existingCart) : [];
    
    const existingIndex = cart.findIndex((item: any) => item.product_id === product.id);
    
    if (existingIndex >= 0) {
      cart[existingIndex].quantity += 1;
    } else {
      cart.push({
        product_id: product.id,
        name: product.name,
        sku: product.sku,
        price: product.price,
        quantity: 1,
        image: product.images?.[0] || ''
      });
    }
    
    localStorage.setItem('shop_cart', JSON.stringify(cart));
    window.dispatchEvent(new Event('cart-updated'));
    alert('Added to cart!');
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-16">
        <div className="flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
        </div>
      </div>
    );
  }

  if (!isLoggedIn) {
    return (
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-md mx-auto text-center">
          <div className="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <Heart className="w-10 h-10 text-slate-400" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900 mb-2">Your Wishlist</h1>
          <p className="text-slate-500 mb-8">
            Sign in to save your favorite tiles and access them from any device.
          </p>
          <Link
            href="/login?redirect=/wishlist"
            className="inline-flex items-center gap-2 bg-amber-500 hover:bg-amber-600 text-slate-900 font-semibold px-6 py-3 rounded-lg"
          >
            <LogIn className="w-5 h-5" />
            Sign In
          </Link>
          <p className="text-sm text-slate-500 mt-4">
            Don't have an account?{' '}
            <Link href="/register?redirect=/wishlist" className="text-amber-600 hover:underline">
              Create one
            </Link>
          </p>
        </div>
      </div>
    );
  }

  if (wishlist.length === 0) {
    return (
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-md mx-auto text-center">
          <div className="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <Heart className="w-10 h-10 text-slate-400" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900 mb-2">Your Wishlist is Empty</h1>
          <p className="text-slate-500 mb-8">
            Start adding tiles you love by clicking the heart icon on any product.
          </p>
          <Link
            href="/products"
            className="inline-flex items-center gap-2 bg-amber-500 hover:bg-amber-600 text-slate-900 font-semibold px-6 py-3 rounded-lg"
          >
            Browse Tiles
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900">My Wishlist</h1>
          <p className="text-slate-500">{wishlist.length} saved items</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {wishlist.map((product) => (
          <div
            key={product.id}
            className="bg-white rounded-xl shadow-sm overflow-hidden group"
          >
            {/* Product Image */}
            <Link href={`/products/${product.id}`} className="block relative aspect-square bg-gray-100">
              {product.images?.[0] ? (
                <Image
                  src={product.images[0]}
                  alt={product.name}
                  fill
                  className="object-cover group-hover:scale-105 transition-transform duration-300"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <Package className="w-16 h-16 text-gray-300" />
                </div>
              )}
              
              {/* Clearance Badge */}
              {product.clearance && (
                <span className="absolute top-2 left-2 bg-red-500 text-white text-xs font-bold px-2 py-1 rounded">
                  SALE
                </span>
              )}
              
              {/* Remove Button */}
              <button
                onClick={(e) => {
                  e.preventDefault();
                  removeFromWishlist(product.id);
                }}
                disabled={removingId === product.id}
                className="absolute top-2 right-2 p-2 bg-white rounded-full shadow-md hover:bg-red-50 transition-colors"
                title="Remove from wishlist"
              >
                {removingId === product.id ? (
                  <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
                ) : (
                  <Trash2 className="w-4 h-4 text-red-500" />
                )}
              </button>
            </Link>

            {/* Product Info */}
            <div className="p-4">
              <Link href={`/products/${product.id}`}>
                <h3 className="font-medium text-slate-900 mb-1 line-clamp-2 hover:text-amber-600">
                  {product.name}
                </h3>
              </Link>
              
              {product.sku && (
                <p className="text-xs text-slate-500 mb-2">SKU: {product.sku}</p>
              )}
              
              {/* Rating */}
              {(product.avg_rating ?? 0) > 0 && (
                <div className="flex items-center gap-1 mb-2">
                  <div className="flex">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <span
                        key={star}
                        className={star <= Math.round(product.avg_rating || 0) ? 'text-amber-400' : 'text-gray-300'}
                      >
                        ★
                      </span>
                    ))}
                  </div>
                  <span className="text-xs text-slate-500">({product.review_count})</span>
                </div>
              )}
              
              {/* Price */}
              <div className="flex items-center justify-between mt-3">
                <div>
                  {product.clearance && product.clearance_price ? (
                    <div className="flex items-center gap-2">
                      <span className="text-lg font-bold text-red-600">
                        {formatPrice(product.clearance_price)}
                      </span>
                      <span className="text-sm text-slate-400 line-through">
                        {formatPrice(product.price)}
                      </span>
                    </div>
                  ) : (
                    <span className="text-lg font-bold text-slate-900">
                      {formatPrice(product.price)}
                    </span>
                  )}
                </div>
                
                {/* Stock Status */}
                {product.in_stock ? (
                  <span className="text-xs text-green-600 font-medium">In Stock</span>
                ) : (
                  <span className="text-xs text-red-500 font-medium">Out of Stock</span>
                )}
              </div>
              
              {/* Add to Cart Button */}
              <button
                onClick={() => addToCart(product)}
                disabled={!product.in_stock}
                className="w-full mt-4 flex items-center justify-center gap-2 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-300 text-white font-medium py-2 rounded-lg transition-colors"
              >
                <ShoppingCart className="w-4 h-4" />
                Add to Cart
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
