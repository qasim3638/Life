import React, { useState, useRef, useCallback } from 'react';
import { ZoomIn, X } from 'lucide-react';

/**
 * ImageZoom - Component that provides hover-to-zoom functionality
 * and a full-screen lightbox view for product images
 */
export const ImageZoom = ({ src, alt, className = '' }) => {
  const [isZoomed, setIsZoomed] = useState(false);
  const [showLightbox, setShowLightbox] = useState(false);
  const [zoomPosition, setZoomPosition] = useState({ x: 50, y: 50 });
  const containerRef = useRef(null);

  const handleMouseMove = useCallback((e) => {
    if (!containerRef.current) return;
    
    const rect = containerRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    
    setZoomPosition({ x, y });
  }, []);

  const handleMouseEnter = () => setIsZoomed(true);
  const handleMouseLeave = () => {
    setIsZoomed(false);
    setZoomPosition({ x: 50, y: 50 });
  };

  if (!src) {
    return (
      <div className={`flex items-center justify-center bg-gray-100 text-gray-400 ${className}`}>
        No Image Available
      </div>
    );
  }

  return (
    <>
      {/* Main Image Container with Zoom */}
      <div
        ref={containerRef}
        className={`relative overflow-hidden cursor-zoom-in ${className}`}
        onMouseMove={handleMouseMove}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onClick={() => setShowLightbox(true)}
        data-testid="image-zoom-container"
      >
        {/* Base Image */}
        <img
          src={src}
          alt={alt}
          className="w-full h-full object-cover transition-opacity duration-200"
          style={{ opacity: isZoomed ? 0.5 : 1 }}
        />
        
        {/* Zoomed Image Overlay */}
        {isZoomed && (
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              backgroundImage: `url(${src})`,
              backgroundSize: '200%',
              backgroundPosition: `${zoomPosition.x}% ${zoomPosition.y}%`,
              backgroundRepeat: 'no-repeat'
            }}
          />
        )}
        
        {/* Zoom Indicator */}
        <div className="absolute bottom-3 right-3 bg-black/60 text-white text-xs px-2 py-1 rounded flex items-center gap-1 opacity-70 group-hover:opacity-100 transition">
          <ZoomIn className="h-3 w-3" />
          <span>Hover to zoom</span>
        </div>
      </div>

      {/* Lightbox Modal */}
      {showLightbox && (
        <div 
          className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4"
          onClick={() => setShowLightbox(false)}
          data-testid="image-lightbox"
        >
          <button
            onClick={() => setShowLightbox(false)}
            className="absolute top-4 right-4 p-2 bg-white/10 hover:bg-white/20 rounded-full transition"
          >
            <X className="h-6 w-6 text-white" />
          </button>
          <img
            src={src}
            alt={alt}
            className="max-w-full max-h-[90vh] object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
};

export default ImageZoom;
