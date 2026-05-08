import { Metadata } from 'next';
import { notFound } from 'next/navigation';
import Image from 'next/image';
import Link from 'next/link';
import { Truck, Store, Shield, Calculator } from 'lucide-react';
import { api, Product } from '@/lib/api';
import { formatPrice } from '@/lib/utils';
import { AddToCartButton } from './AddToCartButton';
import { WishlistButton } from './WishlistButton';
import { ProductReviews } from '@/components/ProductReviews';
import { SimilarProducts } from '@/components/SimilarProducts';
import { SeriesProducts } from '@/components/SeriesProducts';

interface ProductPageProps {
  params: { id: string };
}

async function getProduct(id: string): Promise<Product | null> {
  try {
    return await api.getProduct(id);
  } catch (error) {
    return null;
  }
}

export async function generateMetadata({ params }: ProductPageProps): Promise<Metadata> {
  const product = await getProduct(params.id);
  
  if (!product) {
    return {
      title: 'Product Not Found',
    };
  }

  const price = product.clearance && product.clearance_price 
    ? product.clearance_price 
    : product.price;

  return {
    title: product.name,
    description: product.description || `Buy ${product.name} from Tile Station. ${product.category_name}. ${formatPrice(price)} per ${product.unit}. Free UK delivery on orders over £500.`,
    alternates: {
      canonical: `/products/${product.id}`,
    },
    openGraph: {
      title: `${product.name} | Tile Station`,
      description: product.description || `Buy ${product.name} from Tile Station.`,
      type: 'website',
      images: product.images?.[0] ? [
        {
          url: product.images[0],
          width: 800,
          height: 800,
          alt: product.name,
        },
      ] : undefined,
    },
  };
}

export default async function ProductPage({ params }: ProductPageProps) {
  const product = await getProduct(params.id);

  if (!product) {
    notFound();
  }

  const currentPrice = product.clearance && product.clearance_price 
    ? product.clearance_price 
    : product.price;

  const discount = product.clearance && product.clearance_price
    ? Math.round((1 - product.clearance_price / product.price) * 100)
    : 0;

  // JSON-LD structured data for SEO
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: product.name,
    description: product.description,
    image: product.images,
    sku: product.sku,
    category: product.category_name,
    aggregateRating: (product.review_count ?? 0) > 0 ? {
      '@type': 'AggregateRating',
      ratingValue: product.avg_rating || 0,
      reviewCount: product.review_count || 0,
    } : undefined,
    offers: {
      '@type': 'Offer',
      price: currentPrice,
      priceCurrency: 'GBP',
      availability: product.in_stock 
        ? 'https://schema.org/InStock' 
        : 'https://schema.org/OutOfStock',
      seller: {
        '@type': 'Organization',
        name: 'Tile Station',
      },
    },
  };

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-slate-500 mb-8" aria-label="Breadcrumb">
        <Link href="/" className="hover:text-amber-600">Home</Link>
        <span>/</span>
        <Link href="/products" className="hover:text-amber-600">Products</Link>
        <span>/</span>
        <span className="text-slate-900">{product.name}</span>
      </nav>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12">
        {/* Product Images */}
        <div className="space-y-4">
          <div className="aspect-square bg-gray-100 rounded-xl overflow-hidden relative">
            {product.images?.[0] ? (
              <Image
                src={product.images[0]}
                alt={product.name}
                fill
                className="object-cover"
                sizes="(max-width: 1024px) 100vw, 50vw"
                priority
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-400">
                <span className="text-8xl">🪨</span>
              </div>
            )}
            {product.clearance && (
              <span className="absolute top-4 left-4 bg-red-500 text-white text-lg font-semibold px-3 py-1 rounded">
                Sale
              </span>
            )}
          </div>
          
          {/* Thumbnail Images */}
          {product.images && product.images.length > 1 && (
            <div className="flex gap-2 overflow-x-auto pb-2">
              {product.images.map((img, idx) => (
                <div
                  key={idx}
                  className="w-20 h-20 flex-shrink-0 rounded-lg overflow-hidden border-2 border-transparent hover:border-amber-500 cursor-pointer"
                >
                  <Image
                    src={img}
                    alt={`${product.name} - Image ${idx + 1}`}
                    width={80}
                    height={80}
                    className="w-full h-full object-cover"
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Product Info */}
        <div>
          <div className="mb-4">
            <p className="text-sm text-slate-500 mb-1">SKU: {product.sku}</p>
            <h1 className="text-2xl md:text-3xl font-bold text-slate-900">{product.name}</h1>
            {product.category_name && (
              <Link
                href={`/products?category_id=${product.category_id}`}
                className="text-amber-600 hover:text-amber-700 text-sm mt-1 inline-block"
              >
                {product.category_name}
              </Link>
            )}
            {/* Rating Summary */}
            {(product.review_count ?? 0) > 0 && (
              <div className="flex items-center gap-2 mt-2">
                <div className="flex">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <span
                      key={star}
                      className={`text-lg ${star <= Math.round(product.avg_rating || 0) ? 'text-amber-400' : 'text-gray-300'}`}
                    >
                      ★
                    </span>
                  ))}
                </div>
                <span className="text-sm text-slate-500">
                  {product.avg_rating?.toFixed(1)} ({product.review_count} reviews)
                </span>
              </div>
            )}
          </div>

          {/* Price */}
          <div className="mb-6">
            {product.clearance && product.clearance_price ? (
              <div className="flex items-center gap-3">
                <span className="text-3xl font-bold text-red-600">
                  {formatPrice(product.clearance_price)}
                </span>
                <span className="text-xl text-slate-400 line-through">
                  {formatPrice(product.price)}
                </span>
                <span className="bg-red-100 text-red-700 text-sm font-medium px-2 py-1 rounded">
                  Save {discount}%
                </span>
              </div>
            ) : (
              <span className="text-3xl font-bold text-slate-900">
                {formatPrice(product.price)}
              </span>
            )}
            <p className="text-slate-500 mt-1">per {product.unit}</p>
          </div>

          {/* Stock Status - thresholds: 0 = Out of Stock, <30m² = Low Stock, >30m² = In Stock */}
          <div className="mb-6" data-testid="stock-status-badge">
            {(() => {
              const stockQty = product.stock || 0;
              const lowStockThreshold = 30;
              
              if (product.always_in_stock || stockQty > lowStockThreshold) {
                return (
                  <div className="flex items-center gap-2 text-green-600">
                    <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    <span className="font-medium">In Stock</span>
                  </div>
                );
              } else if (stockQty > 0) {
                return (
                  <div className="flex items-center gap-2 text-amber-600">
                    <span className="w-2 h-2 bg-amber-500 rounded-full" />
                    <span className="font-medium">Low Stock</span>
                  </div>
                );
              } else {
                return (
                  <div className="flex items-center gap-2 text-red-600">
                    <span className="w-2 h-2 bg-red-500 rounded-full" />
                    <span className="font-medium">Out of Stock</span>
                  </div>
                );
              }
            })()}
          </div>

          {/* Tile Specifications */}
          {(product.tile_width || product.tile_height || product.tiles_per_box) && (
            <div className="p-4 mb-6 bg-slate-50 rounded-xl">
              <h3 className="font-semibold mb-3">Specifications</h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                {product.tile_width && product.tile_height && (
                  <div>
                    <span className="text-slate-500">Size:</span>
                    <span className="ml-2 font-medium">{product.tile_width}x{product.tile_height}cm</span>
                  </div>
                )}
                {product.finish && (
                  <div>
                    <span className="text-slate-500">Finish:</span>
                    <span className="ml-2 font-medium">{product.finish}</span>
                  </div>
                )}
                {product.tiles_per_box && (
                  <div>
                    <span className="text-slate-500">Tiles per Box:</span>
                    <span className="ml-2 font-medium">{product.tiles_per_box}</span>
                  </div>
                )}
                {(product.box_m2_coverage || product.sqm_per_box) && (
                  <div>
                    <span className="text-slate-500">m² per Box:</span>
                    <span className="ml-2 font-medium">{product.box_m2_coverage || product.sqm_per_box}m²</span>
                  </div>
                )}
                {product.material && (
                  <div>
                    <span className="text-slate-500">Material:</span>
                    <span className="ml-2 font-medium">{product.material}</span>
                  </div>
                )}
                {product.series && (
                  <div>
                    <span className="text-slate-500">Series:</span>
                    <span className="ml-2 font-medium">{product.series}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Add to Cart & Wishlist */}
          {product.in_stock && (
            <div className="space-y-3 mb-6">
              <AddToCartButton product={product} currentPrice={currentPrice} />
              <div className="flex gap-3">
                <WishlistButton productId={product.id} />
                <Link
                  href={`/calculator?product=${product.id}`}
                  className="flex-1 flex items-center justify-center gap-2 border border-slate-300 hover:bg-slate-50 text-slate-700 font-medium py-2 rounded-lg transition-colors"
                >
                  <Calculator className="w-4 h-4" />
                  Calculate Tiles Needed
                </Link>
              </div>
            </div>
          )}

          {/* Collapsible Tile Calculator - Always show with fallback */}
          <details className="mb-6 border border-slate-200 rounded-xl overflow-hidden" data-testid="tile-calculator">
            <summary className="flex items-center justify-between p-4 bg-slate-50 cursor-pointer hover:bg-slate-100 transition-colors">
              <span className="font-medium text-gray-700 flex items-center gap-2">
                <Calculator className="w-4 h-4 text-amber-600" />
                Tile Calculator
              </span>
              <span className="text-xs text-gray-500">Click to expand</span>
            </summary>
            <div className="p-4 bg-white">
              {(product.box_m2_coverage || product.sqm_per_box) ? (
                <>
                  <p className="text-sm text-gray-600 mb-3">
                    Quick box quantity selector for this product:
                  </p>
                  <div className="grid grid-cols-4 gap-2">
                    {[1, 2, 3, 5, 10, 15, 20, 25].map((boxes) => {
                      const sqmPerBox = product.box_m2_coverage || product.sqm_per_box || 1;
                      const totalSqm = (boxes * sqmPerBox).toFixed(1);
                      const totalPrice = (boxes * sqmPerBox * currentPrice).toFixed(2);
                      return (
                        <div 
                          key={boxes}
                          className="p-2 border border-slate-200 rounded-lg text-center hover:border-amber-500 hover:bg-amber-50 cursor-pointer transition-colors"
                        >
                          <div className="font-bold text-lg text-slate-800">{boxes}</div>
                          <div className="text-xs text-slate-500">boxes</div>
                          <div className="text-xs text-amber-600 font-medium">{totalSqm}m²</div>
                          <div className="text-xs text-slate-600">£{totalPrice}</div>
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-xs text-gray-500 mt-3">
                    Box coverage: {product.box_m2_coverage || product.sqm_per_box}m² per box
                  </p>
                </>
              ) : (
                <>
                  <p className="text-sm text-gray-600 mb-3">
                    Calculate how much you need based on your room size:
                  </p>
                  <div className="grid grid-cols-4 gap-2 mb-4">
                    {[5, 10, 15, 20, 25, 30, 40, 50].map((sqm) => {
                      const totalPrice = (sqm * currentPrice).toFixed(2);
                      return (
                        <div 
                          key={sqm}
                          className="p-2 border border-slate-200 rounded-lg text-center hover:border-amber-500 hover:bg-amber-50 cursor-pointer transition-colors"
                        >
                          <div className="font-bold text-lg text-slate-800">{sqm}</div>
                          <div className="text-xs text-slate-500">m²</div>
                          <div className="text-xs text-amber-600 font-medium">£{totalPrice}</div>
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-xs text-gray-500">
                    Tile size: {product.tile_width && product.tile_height ? `${product.tile_width}x${product.tile_height}cm` : 'See specifications'} • We recommend ordering 10% extra for cuts and wastage
                  </p>
                </>
              )}
            </div>
          </details>

          {/* Description */}
          {product.description && (
            <div className="mb-6">
              <h3 className="font-semibold mb-2">Description</h3>
              <p className="text-slate-600">{product.description}</p>
            </div>
          )}

          {/* Features */}
          <div className="border-t pt-6 space-y-3">
            <div className="flex items-center gap-3 text-sm">
              <Truck className="w-5 h-5 text-amber-600" />
              <span>Free delivery on orders over £500</span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <Store className="w-5 h-5 text-amber-600" />
              <span>Click & collect from our showrooms</span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <Shield className="w-5 h-5 text-amber-600" />
              <span>Quality guaranteed</span>
            </div>
          </div>
        </div>
      </div>

      {/* Product Reviews Section */}
      <div className="mt-12 border-t">
        <ProductReviews productId={product.id} productName={product.name} />
      </div>

      {/* Similar Products Section */}
      <div className="border-t">
        {/* Series Products - More from same series */}
        <SeriesProducts productId={product.id} productName={product.name} />
        
        {/* Similar Products - Related by category */}
        <SimilarProducts productId={product.id} />
      </div>

      {/* JSON-LD Structured Data */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
    </div>
  );
}
