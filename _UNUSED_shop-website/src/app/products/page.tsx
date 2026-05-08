import { Metadata } from 'next';
import { Suspense } from 'react';
import { api, Category } from '@/lib/api';
import { ProductsGrid } from './ProductsGrid';

interface ProductsPageProps {
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
}

export async function generateMetadata({ searchParams }: ProductsPageProps): Promise<Metadata> {
  const { category_id, search, clearance_only } = searchParams;
  
  let title = 'All Tiles & Products';
  let description = 'Browse our complete collection of premium tiles and bathroom products. Filter by category, price, and availability.';

  if (clearance_only === 'true') {
    title = 'Clearance Sale - Up to 50% Off';
    description = 'Shop our clearance sale and save up to 50% on premium tiles. Limited stock available.';
  } else if (search) {
    title = `Search: ${search}`;
    description = `Search results for "${search}" - Find the perfect tiles for your project.`;
  } else if (category_id) {
    // We could fetch category name here for better titles
    title = 'Category Products';
  }

  return {
    title,
    description,
    alternates: {
      canonical: '/products',
    },
    openGraph: {
      title: `${title} | Tile Station`,
      description,
      type: 'website',
    },
  };
}

async function getCategories(): Promise<Category[]> {
  try {
    return await api.getCategories();
  } catch (error) {
    console.error('Failed to fetch categories:', error);
    return [];
  }
}

export default async function ProductsPage({ searchParams }: ProductsPageProps) {
  const categories = await getCategories();
  
  const { clearance_only, search } = searchParams;
  
  let pageTitle = 'All Tiles';
  if (clearance_only === 'true') {
    pageTitle = 'Clearance Sale';
  } else if (search) {
    pageTitle = `Search: "${search}"`;
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-2xl md:text-3xl font-bold text-slate-900 mb-6">{pageTitle}</h1>
      
      <Suspense fallback={<ProductsGridSkeleton />}>
        <ProductsGrid searchParams={searchParams} categories={categories} />
      </Suspense>
    </div>
  );
}

function ProductsGridSkeleton() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
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
  );
}
