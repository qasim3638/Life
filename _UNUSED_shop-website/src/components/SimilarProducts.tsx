'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Package, Loader2 } from 'lucide-react';
import api, { Product } from '@/lib/api';
import { formatPrice } from '@/lib/utils';

interface SimilarProductsProps {
  productId: string;
}

export function SimilarProducts({ productId }: SimilarProductsProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSimilarProducts();
  }, [productId]);

  const loadSimilarProducts = async () => {
    try {
      const data = await api.getSimilarProducts(productId, 4);
      setProducts(data.similar_products || []);
    } catch (err) {
      console.error('Failed to load similar products:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="py-8">
        <div className="flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
        </div>
      </div>
    );
  }

  if (products.length === 0) {
    return null;
  }

  return (
    <div className="py-8" data-testid="similar-products-section">
      <h2 className="text-xl font-bold text-slate-900 mb-6">Similar Products</h2>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {products.map((product) => (
          <Link
            key={product.id}
            href={`/products/${product.id}`}
            className="group bg-white rounded-xl shadow-sm overflow-hidden hover:shadow-md transition-shadow"
          >
            <div className="aspect-square bg-gray-100 relative overflow-hidden">
              {product.images?.[0] ? (
                <Image
                  src={product.images[0]}
                  alt={product.name}
                  fill
                  className="object-cover group-hover:scale-105 transition-transform duration-300"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <Package className="w-12 h-12 text-gray-300" />
                </div>
              )}
              {product.clearance && (
                <span className="absolute top-2 left-2 bg-red-500 text-white text-xs font-bold px-2 py-1 rounded">
                  Sale
                </span>
              )}
            </div>
            <div className="p-3">
              <h3 className="font-medium text-slate-900 text-sm line-clamp-2 group-hover:text-amber-600 mb-1">
                {product.name}
              </h3>
              <div className="flex items-center gap-2">
                {product.clearance && product.clearance_price ? (
                  <>
                    <span className="font-bold text-red-600">{formatPrice(product.clearance_price)}</span>
                    <span className="text-xs text-slate-400 line-through">{formatPrice(product.price)}</span>
                  </>
                ) : (
                  <span className="font-bold text-slate-900">{formatPrice(product.price)}</span>
                )}
              </div>
              {product.in_stock ? (
                <span className="text-xs text-green-600">In Stock</span>
              ) : (
                <span className="text-xs text-red-500">Out of Stock</span>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
