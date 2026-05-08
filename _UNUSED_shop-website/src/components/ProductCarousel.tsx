'use client';

import { useState, useRef, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { ChevronLeft, ChevronRight, Eye, ShoppingCart } from 'lucide-react';
import api, { Product } from '@/lib/api';
import { formatPrice } from '@/lib/utils';

interface ProductCarouselProps {
  title: string;
  subtitle?: string;
  viewAllHref?: string;
  clearanceOnly?: boolean;
  limit?: number;
}

export function ProductCarousel({ 
  title, 
  subtitle, 
  viewAllHref = '/products',
  clearanceOnly = false,
  limit = 8 
}: ProductCarouselProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  useEffect(() => {
    loadProducts();
  }, [clearanceOnly, limit]);

  const loadProducts = async () => {
    try {
      const data = await api.getProducts({ 
        limit, 
        in_stock_only: true,
        clearance_only: clearanceOnly 
      });
      setProducts(data.products);
    } catch (err) {
      console.error('Failed to load products:', err);
    } finally {
      setLoading(false);
    }
  };

  const checkScroll = () => {
    if (scrollRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = scrollRef.current;
      setCanScrollLeft(scrollLeft > 0);
      setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 10);
    }
  };

  const scroll = (direction: 'left' | 'right') => {
    if (scrollRef.current) {
      const scrollAmount = 320;
      scrollRef.current.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth'
      });
    }
  };

  useEffect(() => {
    const ref = scrollRef.current;
    if (ref) {
      ref.addEventListener('scroll', checkScroll);
      checkScroll();
      return () => ref.removeEventListener('scroll', checkScroll);
    }
  }, [products]);

  const addToCart = (product: Product, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
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
        price: product.clearance ? product.clearance_price : product.price,
        quantity: 1,
        image: product.images?.[0] || ''
      });
    }
    
    localStorage.setItem('shop_cart', JSON.stringify(cart));
    window.dispatchEvent(new Event('cart-updated'));
  };

  if (loading) {
    return (
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <div className="animate-pulse">
            <div className="h-8 bg-slate-200 rounded w-48 mb-4" />
            <div className="flex gap-6">
              {[1,2,3,4].map(i => (
                <div key={i} className="w-72 flex-shrink-0">
                  <div className="aspect-square bg-slate-200 rounded-xl mb-4" />
                  <div className="h-4 bg-slate-200 rounded w-3/4 mb-2" />
                  <div className="h-4 bg-slate-200 rounded w-1/2" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    );
  }

  if (products.length === 0) return null;

  return (
    <section className="py-16 md:py-24 bg-white" data-testid="product-carousel">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="flex items-end justify-between mb-8">
          <div>
            <h2 
              className="text-3xl md:text-4xl font-black text-slate-900 tracking-tight"
              style={{ fontFamily: 'Chivo, sans-serif' }}
            >
              {title}
            </h2>
            {subtitle && <p className="text-slate-600 mt-2">{subtitle}</p>}
          </div>
          <div className="hidden md:flex items-center gap-4">
            <button
              onClick={() => scroll('left')}
              disabled={!canScrollLeft}
              className="w-10 h-10 rounded-full border border-slate-200 flex items-center justify-center hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              aria-label="Scroll left"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <button
              onClick={() => scroll('right')}
              disabled={!canScrollRight}
              className="w-10 h-10 rounded-full border border-slate-200 flex items-center justify-center hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              aria-label="Scroll right"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
            <Link 
              href={viewAllHref}
              className="text-teal-600 hover:text-teal-700 font-semibold transition-colors ml-4"
            >
              View All
            </Link>
          </div>
        </div>

        {/* Carousel */}
        <div
          ref={scrollRef}
          className="flex gap-6 overflow-x-auto scrollbar-hide scroll-smooth pb-4"
          style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
        >
          {products.map((product) => (
            <Link
              key={product.id}
              href={`/products/${product.id}`}
              className="group flex-shrink-0 w-64 md:w-72"
              data-testid={`product-card-${product.id}`}
            >
              <article className="bg-white border border-slate-100 rounded-2xl overflow-hidden hover:shadow-[0_8px_30px_rgb(0,0,0,0.12)] transition-all duration-300">
                {/* Image */}
                <div className="relative aspect-square bg-slate-100 overflow-hidden">
                  {product.images?.[0] ? (
                    <Image
                      src={product.images[0]}
                      alt={product.name}
                      fill
                      className="object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-4xl">🪨</div>
                  )}
                  
                  {/* Badges */}
                  <div className="absolute top-3 left-3 flex flex-col gap-2">
                    {product.clearance && (
                      <span className="bg-red-600 text-white text-xs font-bold px-2 py-1 rounded uppercase tracking-wider">
                        Sale
                      </span>
                    )}
                  </div>

                  {/* Quick Actions */}
                  <div className="absolute inset-0 bg-slate-900/0 group-hover:bg-slate-900/20 transition-colors flex items-center justify-center gap-3 opacity-0 group-hover:opacity-100">
                    <button
                      onClick={(e) => addToCart(product, e)}
                      className="w-12 h-12 bg-white rounded-full flex items-center justify-center shadow-lg hover:bg-teal-600 hover:text-white transition-colors"
                      title="Add to cart"
                    >
                      <ShoppingCart className="w-5 h-5" />
                    </button>
                    <span
                      className="w-12 h-12 bg-white rounded-full flex items-center justify-center shadow-lg hover:bg-slate-900 hover:text-white transition-colors"
                      title="Quick view"
                    >
                      <Eye className="w-5 h-5" />
                    </span>
                  </div>
                </div>

                {/* Content */}
                <div className="p-4">
                  <h3 className="font-semibold text-slate-900 group-hover:text-teal-600 transition-colors line-clamp-2 min-h-[48px]">
                    {product.name}
                  </h3>
                  {product.category_name && (
                    <p className="text-sm text-slate-500 mt-1">{product.category_name}</p>
                  )}
                  <div className="mt-3 flex items-center gap-2">
                    {product.clearance && product.clearance_price ? (
                      <>
                        <span className="text-lg font-bold text-red-600">{formatPrice(product.clearance_price)}</span>
                        <span className="text-sm text-slate-400 line-through">{formatPrice(product.price)}</span>
                      </>
                    ) : (
                      <span className="text-lg font-bold text-slate-900">{formatPrice(product.price)}</span>
                    )}
                    <span className="text-sm text-slate-500">/ {product.unit || 'unit'}</span>
                  </div>
                </div>
              </article>
            </Link>
          ))}
        </div>

        {/* Mobile View All */}
        <div className="md:hidden mt-6 text-center">
          <Link 
            href={viewAllHref}
            className="inline-flex items-center gap-2 bg-slate-900 text-white font-semibold px-6 py-3 rounded-full hover:bg-slate-800 transition-colors"
          >
            View All Products
          </Link>
        </div>
      </div>
    </section>
  );
}
