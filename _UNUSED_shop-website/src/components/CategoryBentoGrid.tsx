'use client';

import Image from 'next/image';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

const categories = [
  {
    id: 'bathroom',
    name: 'Bathroom Tiles',
    description: 'Transform your sanctuary',
    image: 'https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea?w=800&q=80',
    href: '/products?category=bathroom',
    size: 'large', // Takes 2 columns, 2 rows
  },
  {
    id: 'kitchen',
    name: 'Kitchen Tiles',
    description: 'Splashbacks & floors',
    image: 'https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=600&q=80',
    href: '/products?category=kitchen',
    size: 'medium',
  },
  {
    id: 'floor',
    name: 'Floor Tiles',
    description: 'Durable & stylish',
    image: 'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=600&q=80',
    href: '/products?category=floor',
    size: 'medium',
  },
  {
    id: 'wall',
    name: 'Wall Tiles',
    description: 'Statement walls',
    image: 'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=600&q=80',
    href: '/products?category=wall',
    size: 'small',
  },
  {
    id: 'outdoor',
    name: 'Outdoor & Paving',
    description: 'Garden & patio',
    image: 'https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=600&q=80',
    href: '/products?category=outdoor',
    size: 'small',
  },
  {
    id: 'clearance',
    name: 'Clearance Sale',
    description: 'Up to 70% off',
    image: 'https://images.unsplash.com/photo-1600573472591-ee6b68d14c68?w=600&q=80',
    href: '/products?clearance_only=true',
    size: 'small',
    badge: 'SALE',
  },
];

export function CategoryBentoGrid() {
  return (
    <section className="py-16 md:py-24 bg-white" data-testid="category-grid">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-end justify-between mb-12">
          <div>
            <h2 
              className="text-3xl md:text-4xl font-black text-slate-900 tracking-tight"
              style={{ fontFamily: 'Chivo, sans-serif' }}
            >
              Shop by Category
            </h2>
            <p className="text-slate-600 mt-2">Find the perfect tiles for every space</p>
          </div>
          <Link 
            href="/products"
            className="hidden md:flex items-center gap-2 text-teal-600 hover:text-teal-700 font-semibold transition-colors"
          >
            View All Categories
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        {/* Bento Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
          {categories.map((category, index) => {
            const isLarge = category.size === 'large';
            const isMedium = category.size === 'medium';
            
            return (
              <Link
                key={category.id}
                href={category.href}
                className={`group relative overflow-hidden rounded-2xl ${
                  isLarge 
                    ? 'col-span-2 row-span-2 aspect-square md:aspect-auto md:h-[500px]' 
                    : isMedium
                    ? 'col-span-1 aspect-[4/5]'
                    : 'col-span-1 aspect-square'
                }`}
                data-testid={`category-${category.id}`}
              >
                <Image
                  src={category.image}
                  alt={category.name}
                  fill
                  className="object-cover group-hover:scale-110 transition-transform duration-700"
                />
                
                {/* Overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-slate-900/90 via-slate-900/40 to-transparent" />
                
                {/* Badge */}
                {category.badge && (
                  <span className="absolute top-4 left-4 bg-red-600 text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
                    {category.badge}
                  </span>
                )}
                
                {/* Content */}
                <div className="absolute bottom-0 left-0 right-0 p-6">
                  <h3 className={`font-bold text-white ${isLarge ? 'text-2xl md:text-3xl' : 'text-lg md:text-xl'}`}>
                    {category.name}
                  </h3>
                  <p className="text-slate-300 text-sm mt-1">{category.description}</p>
                  <div className="flex items-center gap-2 text-teal-400 mt-3 opacity-0 group-hover:opacity-100 transition-opacity">
                    <span className="text-sm font-semibold">Shop Now</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>
              </Link>
            );
          })}
        </div>

        {/* Mobile View All */}
        <div className="md:hidden mt-8 text-center">
          <Link 
            href="/products"
            className="inline-flex items-center gap-2 text-teal-600 hover:text-teal-700 font-semibold transition-colors"
          >
            View All Categories
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </section>
  );
}
