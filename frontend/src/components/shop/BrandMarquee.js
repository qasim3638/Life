import React from 'react';

const defaultBrands = [
  { name: 'Porcelanosa', displayName: 'PORCELANOSA' },
  { name: 'RAK Ceramics', displayName: 'RAK CERAMICS' },
  { name: 'Villeroy & Boch', displayName: 'VILLEROY & BOCH' },
  { name: 'Roca', displayName: 'ROCA' },
  { name: 'Grohe', displayName: 'GROHE' },
  { name: 'Ideal Standard', displayName: 'IDEAL STANDARD' },
  { name: 'British Ceramic', displayName: 'BRITISH CERAMIC TILE' },
  { name: 'Johnson Tiles', displayName: 'JOHNSON TILES' },
];

export const BrandMarquee = ({ visible = true, title, brands }) => {
  if (!visible) return null;

  const displayBrands = brands && brands.length > 0 ? brands : defaultBrands;
  const displayTitle = title || 'Trusted by Leading Brands';

  return (
    <section className="py-10 bg-slate-50 border-y border-slate-200 overflow-hidden" data-testid="brand-marquee">
      <div className="container mx-auto px-4 mb-6">
        <h2 className="text-center text-slate-500 text-sm font-medium uppercase tracking-wider">
          {displayTitle}
        </h2>
      </div>
      
      <div className="relative">
        <div className="absolute left-0 top-0 bottom-0 w-32 bg-gradient-to-r from-slate-50 to-transparent z-10" />
        <div className="absolute right-0 top-0 bottom-0 w-32 bg-gradient-to-l from-slate-50 to-transparent z-10" />
        
        <div className="flex animate-marquee">
          {[...displayBrands, ...displayBrands].map((brand, index) => (
            <div
              key={`${brand.name}-${index}`}
              className="flex-shrink-0 mx-10 opacity-50 hover:opacity-100 transition-all duration-300"
            >
              <span className="text-xl md:text-2xl font-bold tracking-tight text-slate-700 whitespace-nowrap">
                {brand.displayName || brand.name}
              </span>
            </div>
          ))}
        </div>
      </div>

      <style>{`
        @keyframes marquee {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .animate-marquee {
          animation: marquee 40s linear infinite;
        }
        .animate-marquee:hover {
          animation-play-state: paused;
        }
      `}</style>
    </section>
  );
};

export default BrandMarquee;
