'use client';

import { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { ChevronLeft, ChevronRight, Play, Pause } from 'lucide-react';

interface Slide {
  id: number;
  type: 'image' | 'video';
  src: string;
  alt: string;
  title: string;
  subtitle: string;
  cta: {
    text: string;
    href: string;
  };
  secondaryCta?: {
    text: string;
    href: string;
  };
}

const slides: Slide[] = [
  {
    id: 1,
    type: 'image',
    src: 'https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea?w=1920&q=80',
    alt: 'Luxury Bathroom Tiles',
    title: 'Transform Your Space',
    subtitle: 'Premium tiles and bathroom products at unbeatable prices',
    cta: { text: 'Shop Bathroom', href: '/products?category=bathroom' },
    secondaryCta: { text: 'View Offers', href: '/products?clearance_only=true' }
  },
  {
    id: 2,
    type: 'image',
    src: 'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=1920&q=80',
    alt: 'Modern Kitchen Design',
    title: 'Kitchens That Inspire',
    subtitle: 'Discover our stunning range of kitchen tiles and splashbacks',
    cta: { text: 'Shop Kitchen', href: '/products?category=kitchen' },
    secondaryCta: { text: 'Free Samples', href: '/samples' }
  },
  {
    id: 3,
    type: 'image',
    src: 'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=1920&q=80',
    alt: 'Floor Tiles Collection',
    title: 'Floors That Last',
    subtitle: 'Durable, stylish floor tiles for every room in your home',
    cta: { text: 'Shop Floor Tiles', href: '/products?category=floor' },
    secondaryCta: { text: 'Tile Calculator', href: '/calculator' }
  },
  {
    id: 4,
    type: 'video',
    src: 'https://player.vimeo.com/external/434045526.sd.mp4?s=c27eecc69a27dbc4ff2b87d38afc35f1a9e7c02d&profile_id=164&oauth2_token_id=57447761',
    alt: 'Showroom Tour',
    title: 'Visit Our Showrooms',
    subtitle: 'Experience quality first-hand at our 4 UK locations',
    cta: { text: 'Find a Store', href: '/stores' },
  }
];

export function HeroSlider() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [isVideoPlaying, setIsVideoPlaying] = useState(false);

  const nextSlide = useCallback(() => {
    setCurrentSlide((prev) => (prev + 1) % slides.length);
  }, []);

  const prevSlide = useCallback(() => {
    setCurrentSlide((prev) => (prev - 1 + slides.length) % slides.length);
  }, []);

  const goToSlide = (index: number) => {
    setCurrentSlide(index);
  };

  // Auto-play
  useEffect(() => {
    if (!isPlaying || isVideoPlaying) return;
    
    const interval = setInterval(() => {
      nextSlide();
    }, 5000);

    return () => clearInterval(interval);
  }, [isPlaying, isVideoPlaying, nextSlide]);

  const currentSlideData = slides[currentSlide];

  return (
    <section className="relative w-full h-[500px] md:h-[600px] lg:h-[700px] overflow-hidden bg-slate-900" data-testid="hero-slider">
      {/* Slides */}
      {slides.map((slide, index) => (
        <div
          key={slide.id}
          className={`absolute inset-0 transition-opacity duration-1000 ${
            index === currentSlide ? 'opacity-100 z-10' : 'opacity-0 z-0'
          }`}
        >
          {slide.type === 'image' ? (
            <Image
              src={slide.src}
              alt={slide.alt}
              fill
              className="object-cover"
              priority={index === 0}
            />
          ) : (
            <video
              src={slide.src}
              className="w-full h-full object-cover"
              muted
              loop
              playsInline
              autoPlay={index === currentSlide}
              onPlay={() => setIsVideoPlaying(true)}
              onPause={() => setIsVideoPlaying(false)}
            />
          )}
          
          {/* Overlay */}
          <div className="absolute inset-0 bg-gradient-to-r from-slate-900/80 via-slate-900/50 to-transparent" />
        </div>
      ))}

      {/* Content */}
      <div className="relative z-20 h-full flex items-center">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-2xl">
            <h1 
              className="text-4xl md:text-5xl lg:text-6xl font-black text-white mb-4 leading-tight tracking-tight"
              style={{ fontFamily: 'Chivo, sans-serif' }}
            >
              {currentSlideData.title}
            </h1>
            <p className="text-lg md:text-xl text-slate-200 mb-8 font-light">
              {currentSlideData.subtitle}
            </p>
            <div className="flex flex-wrap gap-4">
              <Link
                href={currentSlideData.cta.href}
                className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white font-bold px-8 py-4 rounded-full shadow-lg hover:shadow-xl transition-all transform hover:scale-105"
                data-testid="hero-cta-primary"
              >
                {currentSlideData.cta.text}
              </Link>
              {currentSlideData.secondaryCta && (
                <Link
                  href={currentSlideData.secondaryCta.href}
                  className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-sm border-2 border-white text-white hover:bg-white hover:text-slate-900 font-bold px-8 py-4 rounded-full transition-all"
                  data-testid="hero-cta-secondary"
                >
                  {currentSlideData.secondaryCta.text}
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Arrows */}
      <button
        onClick={prevSlide}
        className="absolute left-4 top-1/2 -translate-y-1/2 z-30 w-12 h-12 bg-white/10 backdrop-blur-sm hover:bg-white/20 rounded-full flex items-center justify-center text-white transition-all"
        aria-label="Previous slide"
        data-testid="hero-prev-btn"
      >
        <ChevronLeft className="w-6 h-6" />
      </button>
      <button
        onClick={nextSlide}
        className="absolute right-4 top-1/2 -translate-y-1/2 z-30 w-12 h-12 bg-white/10 backdrop-blur-sm hover:bg-white/20 rounded-full flex items-center justify-center text-white transition-all"
        aria-label="Next slide"
        data-testid="hero-next-btn"
      >
        <ChevronRight className="w-6 h-6" />
      </button>

      {/* Dots & Controls */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-30 flex items-center gap-4">
        {/* Play/Pause */}
        <button
          onClick={() => setIsPlaying(!isPlaying)}
          className="w-10 h-10 bg-white/10 backdrop-blur-sm hover:bg-white/20 rounded-full flex items-center justify-center text-white transition-all"
          aria-label={isPlaying ? 'Pause slideshow' : 'Play slideshow'}
        >
          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
        </button>
        
        {/* Dots */}
        <div className="flex gap-2">
          {slides.map((_, index) => (
            <button
              key={index}
              onClick={() => goToSlide(index)}
              className={`w-3 h-3 rounded-full transition-all ${
                index === currentSlide 
                  ? 'bg-teal-500 w-8' 
                  : 'bg-white/40 hover:bg-white/60'
              }`}
              aria-label={`Go to slide ${index + 1}`}
              data-testid={`hero-dot-${index}`}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
