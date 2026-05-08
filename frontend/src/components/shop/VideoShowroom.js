import React, { useState, useEffect } from 'react';
import { Play, X } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export const VideoShowroom = () => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [config, setConfig] = useState(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const res = await fetch(`${API_URL}/api/website-admin/homepage`);
        const data = await res.json();
        if (data && data.video_showroom_visible !== false) {
          setConfig({
            badge: data.video_showroom_badge || 'Virtual Tour',
            title: data.video_showroom_title || 'Experience Our Showrooms',
            description: data.video_showroom_description || "Can't visit in person? Take a virtual tour of our stunning showrooms. See thousands of tiles displayed in realistic room settings and get inspired for your next project.",
            videoUrl: data.video_showroom_video_url || '',
            thumbnailUrl: data.video_showroom_thumbnail_url || 'https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=800&q=80',
            ctaPrimaryText: data.video_showroom_cta_primary_text || 'Watch Tour',
            ctaPrimaryLink: data.video_showroom_cta_primary_link || '',
            ctaSecondaryText: data.video_showroom_cta_secondary_text || 'Find a Showroom',
            ctaSecondaryLink: data.video_showroom_cta_secondary_link || '/shop/contact',
            stats: data.video_showroom_stats || [
              { value: '4', label: 'UK Showrooms' },
              { value: '10k+', label: 'Products' },
              { value: '25+', label: 'Years Experience' },
            ],
            floatingTitle: data.video_showroom_floating_badge_title || 'Free Design Consultation',
            floatingSubtitle: data.video_showroom_floating_badge_subtitle || 'Book your appointment today',
          });
        } else if (data && data.video_showroom_visible === false) {
          setConfig(null);
        } else {
          setConfig({
            badge: 'Virtual Tour',
            title: 'Experience Our Showrooms',
            description: "Can't visit in person? Take a virtual tour of our stunning showrooms. See thousands of tiles displayed in realistic room settings and get inspired for your next project.",
            videoUrl: '',
            thumbnailUrl: 'https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=800&q=80',
            ctaPrimaryText: 'Watch Tour',
            ctaPrimaryLink: '',
            ctaSecondaryText: 'Find a Showroom',
            ctaSecondaryLink: '/shop/contact',
            stats: [
              { value: '4', label: 'UK Showrooms' },
              { value: '10k+', label: 'Products' },
              { value: '25+', label: 'Years Experience' },
            ],
            floatingTitle: 'Free Design Consultation',
            floatingSubtitle: 'Book your appointment today',
          });
        }
      } catch (e) {
        setConfig({
          badge: 'Virtual Tour',
          title: 'Experience Our Showrooms',
          description: "Can't visit in person? Take a virtual tour of our stunning showrooms. See thousands of tiles displayed in realistic room settings and get inspired for your next project.",
          videoUrl: '',
          thumbnailUrl: 'https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=800&q=80',
          ctaPrimaryText: 'Watch Tour',
          ctaPrimaryLink: '',
          ctaSecondaryText: 'Find a Showroom',
          ctaSecondaryLink: '/shop/contact',
          stats: [
            { value: '4', label: 'UK Showrooms' },
            { value: '10k+', label: 'Products' },
            { value: '25+', label: 'Years Experience' },
          ],
          floatingTitle: 'Free Design Consultation',
          floatingSubtitle: 'Book your appointment today',
        });
      } finally {
        setLoaded(true);
      }
    };
    fetchConfig();
  }, []);

  if (!loaded || !config) return null;

  const handlePrimaryClick = () => {
    if (config.ctaPrimaryLink) {
      window.location.href = config.ctaPrimaryLink;
    } else {
      setIsPlaying(true);
    }
  };

  return (
    <section className="py-16 md:py-24 bg-slate-900 relative overflow-hidden" data-testid="video-showroom">
      {/* Background Pattern */}
      <div className="absolute inset-0 opacity-5">
        <div className="absolute inset-0" style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
        }} />
      </div>

      <div className="container mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 items-center">
          {/* Content */}
          <div className="order-2 lg:order-1">
            {config.badge && (
              <span className="inline-block bg-[#F7EA1C] text-[#333333] text-sm font-bold px-3 py-1 rounded-full mb-4 uppercase tracking-wider">
                {config.badge}
              </span>
            )}
            <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-black text-white tracking-tight mb-4 sm:mb-6">
              {config.title}
            </h2>
            <p className="text-slate-300 text-base sm:text-lg mb-6 sm:mb-8 leading-relaxed">
              {config.description}
            </p>
            {(config.ctaPrimaryText || config.ctaSecondaryText) && (
              <div className="flex flex-wrap gap-4">
                {config.ctaPrimaryText && (
                  <button 
                    onClick={handlePrimaryClick}
                    className="inline-flex items-center gap-2 sm:gap-3 bg-[#F7EA1C] hover:bg-yellow-400 text-[#333333] font-bold px-6 sm:px-8 py-3 sm:py-4 rounded-full shadow-lg hover:shadow-xl transition-all transform hover:scale-105"
                    data-testid="video-showroom-cta-primary"
                  >
                    <Play className="w-5 h-5" />
                    {config.ctaPrimaryText}
                  </button>
                )}
                {config.ctaSecondaryText && (
                  <a 
                    href={config.ctaSecondaryLink}
                    className="inline-flex items-center gap-2 border-2 border-white text-white hover:bg-white hover:text-slate-900 font-bold px-6 sm:px-8 py-3 sm:py-4 rounded-full transition-all"
                    data-testid="video-showroom-cta-secondary"
                  >
                    {config.ctaSecondaryText}
                  </a>
                )}
              </div>
            )}

            {/* Stats */}
            {config.stats && config.stats.length > 0 && (
              <div className="grid gap-8 mt-12 pt-8 border-t border-slate-700" style={{ gridTemplateColumns: `repeat(${Math.min(config.stats.length, 4)}, 1fr)` }}>
                {config.stats.map((stat, i) => (
                  <div key={i}>
                    <p className="text-3xl font-black text-[#F7EA1C]">{stat.value}</p>
                    <p className="text-slate-400 text-sm">{stat.label}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Video Thumbnail */}
          <div className="order-1 lg:order-2 relative">
            <div className="relative aspect-video rounded-2xl overflow-hidden shadow-2xl">
              <img
                src={config.thumbnailUrl}
                alt={config.title}
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-slate-900/30" />
              
              {/* Play Button */}
              <button
                onClick={() => setIsPlaying(true)}
                className="absolute inset-0 flex items-center justify-center group"
                data-testid="video-showroom-play-btn"
              >
                <div className="w-20 h-20 bg-white rounded-full flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
                  <Play className="w-8 h-8 text-slate-900 ml-1" />
                </div>
              </button>
            </div>

            {/* Floating Badge */}
            {config.floatingTitle && (
              <div className="absolute -bottom-6 -left-6 bg-white rounded-xl shadow-xl p-4 hidden md:block">
                <p className="text-sm font-bold text-slate-900">{config.floatingTitle}</p>
                <p className="text-xs text-slate-500">{config.floatingSubtitle}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Video Modal */}
      {isPlaying && config.videoUrl && (
        <div className="fixed inset-0 z-50 bg-slate-900/95 flex items-center justify-center p-4">
          <button
            onClick={() => setIsPlaying(false)}
            className="absolute top-6 right-6 w-12 h-12 bg-white/10 hover:bg-white/20 rounded-full flex items-center justify-center text-white transition-colors"
            data-testid="video-modal-close"
          >
            <X className="w-6 h-6" />
          </button>
          <div className="w-full max-w-5xl aspect-video bg-slate-800 rounded-xl overflow-hidden">
            <video
              src={config.videoUrl}
              className="w-full h-full"
              controls
              autoPlay
            />
          </div>
        </div>
      )}

      {/* No video uploaded yet - show message in modal */}
      {isPlaying && !config.videoUrl && (
        <div className="fixed inset-0 z-50 bg-slate-900/95 flex items-center justify-center p-4">
          <button
            onClick={() => setIsPlaying(false)}
            className="absolute top-6 right-6 w-12 h-12 bg-white/10 hover:bg-white/20 rounded-full flex items-center justify-center text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
          <div className="text-center text-white">
            <Play className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <p className="text-xl font-bold">Video Coming Soon</p>
            <p className="text-slate-400 mt-2">The showroom tour video is being prepared.</p>
          </div>
        </div>
      )}
    </section>
  );
};

export default VideoShowroom;
