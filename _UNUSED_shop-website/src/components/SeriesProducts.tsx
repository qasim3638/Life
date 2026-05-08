'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Package, Loader2, ChevronRight, Palette, Ruler, Sparkles } from 'lucide-react';
import api, { Product } from '@/lib/api';
import { formatPrice } from '@/lib/utils';

interface SeriesProductsProps {
  productId: string;
  productName: string;
}

interface SeriesData {
  series_name: string | null;
  series_products: Product[];
  variant_counts: {
    colors: number;
    sizes: number;
    finishes: number;
  };
  total_in_series: number;
}

export function SeriesProducts({ productId, productName }: SeriesProductsProps) {
  const [seriesData, setSeriesData] = useState<SeriesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [displayStyle, setDisplayStyle] = useState<'cards' | 'collection'>('cards');

  useEffect(() => {
    loadSeriesProducts();
    // Randomly choose display style based on product ID hash
    const hash = productId.split('').reduce((a, b) => a + b.charCodeAt(0), 0);
    setDisplayStyle(hash % 2 === 0 ? 'cards' : 'collection');
  }, [productId]);

  const loadSeriesProducts = async () => {
    try {
      const data = await api.getSeriesProducts(productId, 8);
      setSeriesData(data);
    } catch (err) {
      console.error('Failed to load series products:', err);
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

  if (!seriesData || !seriesData.series_name || seriesData.series_products.length === 0) {
    return null;
  }

  const { series_name, series_products, variant_counts, total_in_series } = seriesData;

  // Style 1: "More from [Series] Series" - Product Cards Grid
  if (displayStyle === 'cards') {
    return (
      <div className="py-10 border-t border-slate-200" data-testid="series-products-section">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-slate-900">
              More from {series_name} Series
            </h2>
            <div className="flex items-center gap-4 mt-2 text-sm text-slate-500">
              {variant_counts.colors > 0 && (
                <span className="flex items-center gap-1">
                  <Palette className="w-4 h-4" />
                  {variant_counts.colors} Colors
                </span>
              )}
              {variant_counts.sizes > 0 && (
                <span className="flex items-center gap-1">
                  <Ruler className="w-4 h-4" />
                  {variant_counts.sizes} Sizes
                </span>
              )}
              {variant_counts.finishes > 0 && (
                <span className="flex items-center gap-1">
                  <Sparkles className="w-4 h-4" />
                  {variant_counts.finishes} Finishes
                </span>
              )}
            </div>
          </div>
          {total_in_series > 4 && (
            <Link
              href={`/products?search=${encodeURIComponent(series_name)}`}
              className="flex items-center gap-1 text-amber-600 hover:text-amber-700 text-sm font-medium"
            >
              View All {total_in_series} Products
              <ChevronRight className="w-4 h-4" />
            </Link>
          )}
        </div>

        {/* Product Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {series_products.slice(0, 4).map((product) => (
            <Link
              key={product.id}
              href={`/products/${product.id}`}
              className="group bg-white rounded-xl shadow-sm overflow-hidden hover:shadow-lg transition-all duration-300 border border-slate-100"
              data-testid={`series-product-${product.id}`}
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
              <div className="p-4">
                <h3 className="font-medium text-slate-900 text-sm line-clamp-2 group-hover:text-amber-600 transition-colors mb-2">
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
                <div className="mt-2">
                  {product.in_stock ? (
                    <span className="inline-flex items-center text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full">
                      In Stock
                    </span>
                  ) : (
                    <span className="inline-flex items-center text-xs text-red-500 bg-red-50 px-2 py-1 rounded-full">
                      Out of Stock
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    );
  }

  // Style 2: "Complete the Look" - Collection Style
  return (
    <div className="py-10 border-t border-slate-200" data-testid="series-collection-section">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-900">
          Complete the Look - {series_name} Collection
        </h2>
        <p className="text-slate-500 mt-1">
          Explore {total_in_series} products in this collection
          {variant_counts.colors > 1 && ` • ${variant_counts.colors} color options`}
          {variant_counts.sizes > 1 && ` • ${variant_counts.sizes} sizes`}
        </p>
      </div>

      {/* Horizontal Scroll Carousel */}
      <div className="relative">
        <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-hide snap-x snap-mandatory">
          {series_products.map((product) => (
            <Link
              key={product.id}
              href={`/products/${product.id}`}
              className="group flex-shrink-0 w-48 snap-start"
              data-testid={`collection-product-${product.id}`}
            >
              <div className="aspect-square bg-gray-100 rounded-xl overflow-hidden relative mb-3">
                {product.images?.[0] ? (
                  <Image
                    src={product.images[0]}
                    alt={product.name}
                    fill
                    className="object-cover group-hover:scale-110 transition-transform duration-500"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <Package className="w-10 h-10 text-gray-300" />
                  </div>
                )}
                {product.clearance && (
                  <span className="absolute top-2 left-2 bg-red-500 text-white text-xs font-bold px-2 py-0.5 rounded">
                    Sale
                  </span>
                )}
                {/* Hover overlay */}
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-300" />
              </div>
              <h3 className="font-medium text-slate-900 text-sm line-clamp-2 group-hover:text-amber-600 transition-colors">
                {product.name}
              </h3>
              <div className="flex items-center gap-2 mt-1">
                {product.clearance && product.clearance_price ? (
                  <>
                    <span className="font-semibold text-red-600 text-sm">{formatPrice(product.clearance_price)}</span>
                    <span className="text-xs text-slate-400 line-through">{formatPrice(product.price)}</span>
                  </>
                ) : (
                  <span className="font-semibold text-slate-900 text-sm">{formatPrice(product.price)}</span>
                )}
              </div>
            </Link>
          ))}
          
          {/* View All Card */}
          {total_in_series > series_products.length && (
            <Link
              href={`/products?search=${encodeURIComponent(series_name)}`}
              className="flex-shrink-0 w-48 snap-start"
            >
              <div className="aspect-square bg-gradient-to-br from-amber-50 to-amber-100 rounded-xl flex flex-col items-center justify-center border-2 border-dashed border-amber-300 hover:border-amber-400 transition-colors">
                <span className="text-3xl font-bold text-amber-600">+{total_in_series - series_products.length}</span>
                <span className="text-amber-600 text-sm font-medium mt-2">View All</span>
                <ChevronRight className="w-5 h-5 text-amber-500 mt-1" />
              </div>
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
