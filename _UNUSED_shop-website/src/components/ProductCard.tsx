import Link from 'next/link';
import Image from 'next/image';
import { Product } from '@/lib/api';
import { formatPrice } from '@/lib/utils';

interface ProductCardProps {
  product: Product;
}

export function ProductCard({ product }: ProductCardProps) {
  const currentPrice = product.clearance && product.clearance_price 
    ? product.clearance_price 
    : product.price;

  // Get secondary images (up to 3 additional images after the main one)
  const secondaryImages = product.images?.slice(1, 4) || [];

  return (
    <Link href={`/products/${product.id}`} className="group">
      <article className="bg-white rounded-xl shadow-sm overflow-hidden hover:shadow-lg transition-shadow">
        <div className="aspect-square bg-gray-100 relative overflow-hidden">
          {product.images?.[0] ? (
            <Image
              src={product.images[0]}
              alt={product.name}
              fill
              className="object-cover group-hover:scale-105 transition-transform duration-300"
              sizes="(max-width: 768px) 50vw, 25vw"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400">
              <span className="text-4xl">🪨</span>
            </div>
          )}
          
          {product.clearance && (
            <span className="absolute top-2 left-2 bg-red-500 text-white text-xs font-semibold px-2 py-1 rounded">
              Sale
            </span>
          )}
          
          {!product.in_stock && (
            <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
              <span className="bg-white text-slate-900 text-sm font-medium px-3 py-1 rounded">
                Out of Stock
              </span>
            </div>
          )}
        </div>
        
        {/* Secondary Images Row */}
        {secondaryImages.length > 0 && (
          <div className="flex gap-1 px-1 py-1 bg-gray-50">
            {secondaryImages.map((img, idx) => (
              <div 
                key={idx} 
                className="relative aspect-square flex-1 bg-gray-100 rounded overflow-hidden"
                style={{ maxHeight: '48px' }}
              >
                <Image
                  src={img}
                  alt={`${product.name} - Image ${idx + 2}`}
                  fill
                  className="object-cover"
                  sizes="60px"
                />
              </div>
            ))}
            {/* Show "+X more" indicator if there are more images */}
            {product.images && product.images.length > 4 && (
              <div 
                className="relative aspect-square flex-1 bg-gray-200 rounded overflow-hidden flex items-center justify-center"
                style={{ maxHeight: '48px' }}
              >
                <span className="text-xs font-medium text-gray-600">
                  +{product.images.length - 4}
                </span>
              </div>
            )}
          </div>
        )}
        
        <div className="p-4">
          <h3 className="font-medium text-slate-900 group-hover:text-amber-600 transition-colors line-clamp-2">
            {product.name}
          </h3>
          <p className="text-sm text-slate-500 mt-1">{product.category_name}</p>
          
          <div className="mt-2 flex items-center gap-2">
            {product.clearance && product.clearance_price ? (
              <>
                <span className="font-bold text-red-600">{formatPrice(product.clearance_price)}</span>
                <span className="text-sm text-slate-400 line-through">{formatPrice(product.price)}</span>
              </>
            ) : (
              <span className="font-bold text-slate-900">{formatPrice(product.price)}</span>
            )}
            <span className="text-sm text-slate-500">/ {product.unit}</span>
          </div>
        </div>
      </article>
    </Link>
  );
}
