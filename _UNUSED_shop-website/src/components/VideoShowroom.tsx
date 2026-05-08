'use client';

import { useState } from 'react';
import Image from 'next/image';
import { Play, X } from 'lucide-react';

export function VideoShowroom() {
  const [isPlaying, setIsPlaying] = useState(false);

  return (
    <section className="py-16 md:py-24 bg-slate-900 relative overflow-hidden" data-testid="video-showroom">
      {/* Background Pattern */}
      <div className="absolute inset-0 opacity-5">
        <div className="absolute inset-0" style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
        }} />
      </div>

      <div className="container mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          {/* Content */}
          <div className="order-2 lg:order-1">
            <span className="inline-block bg-teal-600 text-white text-sm font-bold px-3 py-1 rounded-full mb-4 uppercase tracking-wider">
              Virtual Tour
            </span>
            <h2 
              className="text-3xl md:text-4xl lg:text-5xl font-black text-white tracking-tight mb-6"
              style={{ fontFamily: 'Chivo, sans-serif' }}
            >
              Experience Our Showrooms
            </h2>
            <p className="text-slate-300 text-lg mb-8 leading-relaxed">
              Can't visit in person? Take a virtual tour of our stunning showrooms. See thousands of tiles displayed in realistic room settings and get inspired for your next project.
            </p>
            <div className="flex flex-wrap gap-4">
              <button 
                onClick={() => setIsPlaying(true)}
                className="inline-flex items-center gap-3 bg-teal-600 hover:bg-teal-700 text-white font-bold px-8 py-4 rounded-full shadow-lg hover:shadow-xl transition-all transform hover:scale-105"
              >
                <Play className="w-5 h-5" />
                Watch Tour
              </button>
              <a 
                href="/stores"
                className="inline-flex items-center gap-2 border-2 border-white text-white hover:bg-white hover:text-slate-900 font-bold px-8 py-4 rounded-full transition-all"
              >
                Find a Showroom
              </a>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-8 mt-12 pt-8 border-t border-slate-700">
              <div>
                <p className="text-3xl font-black text-teal-500">4</p>
                <p className="text-slate-400 text-sm">UK Showrooms</p>
              </div>
              <div>
                <p className="text-3xl font-black text-teal-500">10k+</p>
                <p className="text-slate-400 text-sm">Products</p>
              </div>
              <div>
                <p className="text-3xl font-black text-teal-500">25+</p>
                <p className="text-slate-400 text-sm">Years Experience</p>
              </div>
            </div>
          </div>

          {/* Video Thumbnail */}
          <div className="order-1 lg:order-2 relative">
            <div className="relative aspect-video rounded-2xl overflow-hidden shadow-2xl">
              <Image
                src="https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=800&q=80"
                alt="Tile Station Showroom"
                fill
                className="object-cover"
              />
              <div className="absolute inset-0 bg-slate-900/30" />
              
              {/* Play Button */}
              <button
                onClick={() => setIsPlaying(true)}
                className="absolute inset-0 flex items-center justify-center group"
              >
                <div className="w-20 h-20 bg-white rounded-full flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
                  <Play className="w-8 h-8 text-slate-900 ml-1" />
                </div>
              </button>
            </div>

            {/* Floating Badge */}
            <div className="absolute -bottom-6 -left-6 bg-white rounded-xl shadow-xl p-4 hidden md:block">
              <p className="text-sm font-bold text-slate-900">Free Design Consultation</p>
              <p className="text-xs text-slate-500">Book your appointment today</p>
            </div>
          </div>
        </div>
      </div>

      {/* Video Modal */}
      {isPlaying && (
        <div className="fixed inset-0 z-50 bg-slate-900/95 flex items-center justify-center p-4">
          <button
            onClick={() => setIsPlaying(false)}
            className="absolute top-6 right-6 w-12 h-12 bg-white/10 hover:bg-white/20 rounded-full flex items-center justify-center text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
          <div className="w-full max-w-5xl aspect-video bg-slate-800 rounded-xl overflow-hidden">
            <video
              src="https://player.vimeo.com/external/434045526.sd.mp4?s=c27eecc69a27dbc4ff2b87d38afc35f1a9e7c02d&profile_id=164&oauth2_token_id=57447761"
              className="w-full h-full"
              controls
              autoPlay
            />
          </div>
        </div>
      )}
    </section>
  );
}
