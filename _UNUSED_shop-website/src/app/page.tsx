import { Metadata } from 'next';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { HeroSlider } from '@/components/HeroSlider';
import { USPBar } from '@/components/USPBar';
import { CategoryBentoGrid } from '@/components/CategoryBentoGrid';
import { BrandMarquee } from '@/components/BrandMarquee';
import { ProductCarousel } from '@/components/ProductCarousel';
import { VideoShowroom } from '@/components/VideoShowroom';

export const metadata: Metadata = {
  title: 'Tile Station | Premium Tiles & Bathroom Products UK',
  description: 'Discover premium tiles and bathroom products at Tile Station. Quality craftsmanship, competitive prices. Free UK delivery on orders over £500. Visit our 4 showrooms.',
  alternates: {
    canonical: '/',
  },
};

export default async function HomePage() {
  return (
    <div data-testid="homepage">
      {/* Hero Slider with Auto-play and Videos */}
      <HeroSlider />
      
      {/* USP Bar - Trust signals */}
      <USPBar />
      
      {/* Category Bento Grid */}
      <CategoryBentoGrid />
      
      {/* Featured Products Carousel */}
      <ProductCarousel 
        title="Featured Products"
        subtitle="Handpicked tiles for every style and budget"
        viewAllHref="/products"
      />
      
      {/* Brand Marquee */}
      <BrandMarquee />
      
      {/* Clearance Products Carousel */}
      <ProductCarousel 
        title="Clearance Sale"
        subtitle="Amazing deals on quality tiles - up to 70% off"
        viewAllHref="/products?clearance_only=true"
        clearanceOnly={true}
      />
      
      {/* Video Showroom CTA */}
      <VideoShowroom />
      
      {/* Newsletter / Final CTA */}
      <section className="bg-gradient-to-br from-teal-600 to-teal-700 py-16 md:py-20">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 
            className="text-3xl md:text-4xl font-black text-white tracking-tight mb-4"
            style={{ fontFamily: 'Chivo, sans-serif' }}
          >
            Ready to Transform Your Space?
          </h2>
          <p className="text-white/90 text-lg mb-8 max-w-2xl mx-auto">
            Visit one of our 4 UK showrooms to see thousands of tiles in person, 
            or order free samples delivered to your door.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <Link
              href="/stores"
              className="inline-flex items-center gap-2 bg-white text-teal-700 hover:bg-slate-100 font-bold px-8 py-4 rounded-full shadow-lg transition-all transform hover:scale-105"
              data-testid="cta-find-store"
            >
              Find a Showroom
              <ArrowRight className="w-5 h-5" />
            </Link>
            <Link
              href="/samples"
              className="inline-flex items-center gap-2 bg-transparent border-2 border-white text-white hover:bg-white hover:text-teal-700 font-bold px-8 py-4 rounded-full transition-all"
              data-testid="cta-free-samples"
            >
              Order Free Samples
            </Link>
          </div>
        </div>
      </section>

      {/* Schema.org WebSite markup */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'WebSite',
            name: 'Tile Station',
            url: process.env.NEXT_PUBLIC_SITE_URL,
            potentialAction: {
              '@type': 'SearchAction',
              target: {
                '@type': 'EntryPoint',
                urlTemplate: `${process.env.NEXT_PUBLIC_SITE_URL}/products?search={search_term_string}`,
              },
              'query-input': 'required name=search_term_string',
            },
          }),
        }}
      />
    </div>
  );
}
