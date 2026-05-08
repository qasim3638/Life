'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Filter, Grid, List, SlidersHorizontal, X } from 'lucide-react';
import { api, Product, Category, ProductsResponse } from '@/lib/api';
import { ProductCard } from '@/components/ProductCard';

interface ProductsGridProps {
  searchParams: {
    category_id?: string;
    search?: string;
    min_price?: string;
    max_price?: string;
    in_stock_only?: string;
    clearance_only?: string;
    sort_by?: string;
    page?: string;
  };
  categories: Category[];
}

export function ProductsGrid({ searchParams, categories }: ProductsGridProps) {
  const router = useRouter();
  const urlSearchParams = useSearchParams();
  
  const [products, setProducts] = useState<Product[]>([]);
  const [totalProducts, setTotalProducts] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showFilters, setShowFilters] = useState(false);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  const currentPage = parseInt(searchParams.page || '1');
  const categoryId = searchParams.category_id || '';
  const search = searchParams.search || '';
  const minPrice = searchParams.min_price || '';
  const maxPrice = searchParams.max_price || '';
  const inStockOnly = searchParams.in_stock_only === 'true';
  const clearanceOnly = searchParams.clearance_only === 'true';
  const sortBy = searchParams.sort_by || 'name';

  useEffect(() => {
    fetchProducts();
  }, [searchParams]);

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const params: any = {
        page: currentPage,
        limit: 20,
        sort_by: sortBy,
      };
      
      if (categoryId) params.category_id = categoryId;
      if (search) params.search = search;
      if (minPrice) params.min_price = parseFloat(minPrice);
      if (maxPrice) params.max_price = parseFloat(maxPrice);
      if (inStockOnly) params.in_stock_only = true;
      if (clearanceOnly) params.clearance_only = true;

      const data = await api.getProducts(params);
      setProducts(data.products);
      setTotalProducts(data.total);
      setTotalPages(data.total_pages);
    } catch (error) {
      console.error('Failed to load products:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateFilter = (key: string, value: string) => {
    const params = new URLSearchParams(urlSearchParams.toString());
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    params.set('page', '1');
    router.push(`/products?${params.toString()}`);
  };

  const clearFilters = () => {
    router.push('/products');
  };

  const hasActiveFilters = categoryId || search || minPrice || maxPrice || inStockOnly || clearanceOnly;

  return (
    <div className="flex gap-6">
      {/* Filters Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-80 bg-white shadow-lg transform transition-transform lg:relative lg:inset-auto lg:z-auto lg:w-64 lg:shadow-none lg:transform-none
        ${showFilters ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        <div className="p-4 lg:p-0 h-full overflow-y-auto">
          {/* Mobile Close Button */}
          <div className="flex items-center justify-between mb-4 lg:hidden">
            <h3 className="font-semibold">Filters</h3>
            <button
              onClick={() => setShowFilters(false)}
              className="p-2 hover:bg-gray-100 rounded-lg"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Clear Filters */}
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="w-full mb-4 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50"
            >
              Clear All Filters
            </button>
          )}

          {/* Categories */}
          <div className="mb-6">
            <h3 className="font-semibold mb-3">Categories</h3>
            <div className="space-y-2">
              <button
                className={`block text-sm w-full text-left px-2 py-1 rounded ${!categoryId ? 'bg-amber-100 text-amber-700' : 'hover:bg-gray-100'}`}
                onClick={() => updateFilter('category_id', '')}
              >
                All Categories
              </button>
              {categories.map((cat) => (
                <button
                  key={cat.id}
                  className={`block text-sm w-full text-left px-2 py-1 rounded ${categoryId === cat.id ? 'bg-amber-100 text-amber-700' : 'hover:bg-gray-100'}`}
                  onClick={() => updateFilter('category_id', cat.id)}
                >
                  {cat.name} ({cat.product_count})
                </button>
              ))}
            </div>
          </div>

          {/* Price Range */}
          <div className="mb-6">
            <h3 className="font-semibold mb-3">Price Range</h3>
            <div className="flex items-center gap-2">
              <input
                type="number"
                placeholder="Min"
                value={minPrice}
                onChange={(e) => updateFilter('min_price', e.target.value)}
                className="w-24 px-2 py-1 border border-gray-200 rounded text-sm"
              />
              <span className="text-slate-400">-</span>
              <input
                type="number"
                placeholder="Max"
                value={maxPrice}
                onChange={(e) => updateFilter('max_price', e.target.value)}
                className="w-24 px-2 py-1 border border-gray-200 rounded text-sm"
              />
            </div>
          </div>

          {/* Availability */}
          <div className="mb-6">
            <h3 className="font-semibold mb-3">Availability</h3>
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={inStockOnly}
                  onChange={(e) => updateFilter('in_stock_only', e.target.checked ? 'true' : '')}
                  className="rounded border-gray-300 text-amber-500 focus:ring-amber-500"
                />
                <span className="text-sm">In Stock Only</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={clearanceOnly}
                  onChange={(e) => updateFilter('clearance_only', e.target.checked ? 'true' : '')}
                  className="rounded border-gray-300 text-amber-500 focus:ring-amber-500"
                />
                <span className="text-sm">Clearance Items</span>
              </label>
            </div>
          </div>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {showFilters && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setShowFilters(false)}
        />
      )}

      {/* Products */}
      <div className="flex-1">
        {/* Controls */}
        <div className="flex items-center justify-between mb-6">
          <p className="text-slate-500">{totalProducts} products found</p>
          
          <div className="flex items-center gap-3">
            <button
              className="lg:hidden flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg text-sm"
              onClick={() => setShowFilters(true)}
            >
              <SlidersHorizontal className="w-4 h-4" />
              Filters
            </button>
            
            <select
              value={sortBy}
              onChange={(e) => updateFilter('sort_by', e.target.value)}
              className="px-3 py-2 border border-gray-200 rounded-lg text-sm"
            >
              <option value="name">Name (A-Z)</option>
              <option value="price_asc">Price (Low to High)</option>
              <option value="price_desc">Price (High to Low)</option>
              <option value="newest">Newest First</option>
            </select>
            
            <div className="hidden sm:flex border border-gray-200 rounded-lg overflow-hidden">
              <button
                className={`p-2 ${viewMode === 'grid' ? 'bg-slate-900 text-white' : 'hover:bg-gray-100'}`}
                onClick={() => setViewMode('grid')}
              >
                <Grid className="w-4 h-4" />
              </button>
              <button
                className={`p-2 ${viewMode === 'list' ? 'bg-slate-900 text-white' : 'hover:bg-gray-100'}`}
                onClick={() => setViewMode('list')}
              >
                <List className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Products Grid */}
        {loading ? (
          <div className={`grid gap-4 ${viewMode === 'grid' ? 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4' : 'grid-cols-1'}`}>
            {[...Array(8)].map((_, i) => (
              <div key={i} className="bg-white rounded-xl shadow-sm overflow-hidden animate-pulse">
                <div className="aspect-square bg-gray-200" />
                <div className="p-4 space-y-2">
                  <div className="h-4 bg-gray-200 rounded w-3/4" />
                  <div className="h-4 bg-gray-200 rounded w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : products.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-slate-500 mb-4">No products found</p>
            <button
              onClick={clearFilters}
              className="px-4 py-2 border border-gray-200 rounded-lg hover:bg-gray-50"
            >
              Clear Filters
            </button>
          </div>
        ) : (
          <>
            <div className={`grid gap-4 ${viewMode === 'grid' ? 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4' : 'grid-cols-1'}`}>
              {products.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex justify-center gap-2 mt-8">
                <button
                  disabled={currentPage === 1}
                  onClick={() => updateFilter('page', String(currentPage - 1))}
                  className="px-4 py-2 border border-gray-200 rounded-lg disabled:opacity-50 hover:bg-gray-50"
                >
                  Previous
                </button>
                
                <div className="flex items-center gap-1">
                  {[...Array(Math.min(5, totalPages))].map((_, i) => {
                    let pageNum: number;
                    if (totalPages <= 5) {
                      pageNum = i + 1;
                    } else if (currentPage <= 3) {
                      pageNum = i + 1;
                    } else if (currentPage >= totalPages - 2) {
                      pageNum = totalPages - 4 + i;
                    } else {
                      pageNum = currentPage - 2 + i;
                    }
                    
                    return (
                      <button
                        key={pageNum}
                        onClick={() => updateFilter('page', String(pageNum))}
                        className={`w-10 h-10 rounded-lg ${
                          currentPage === pageNum
                            ? 'bg-slate-900 text-white'
                            : 'border border-gray-200 hover:bg-gray-50'
                        }`}
                      >
                        {pageNum}
                      </button>
                    );
                  })}
                </div>
                
                <button
                  disabled={currentPage === totalPages}
                  onClick={() => updateFilter('page', String(currentPage + 1))}
                  className="px-4 py-2 border border-gray-200 rounded-lg disabled:opacity-50 hover:bg-gray-50"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
