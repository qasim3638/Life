import React from 'react';
import { ShieldCheck, BadgeCheck, Award } from 'lucide-react';

/**
 * PriceMatchBadge - Trust signal badge showing price match guarantee
 */
export const PriceMatchBadge = ({ variant = 'default', className = '' }) => {
  if (variant === 'compact') {
    return (
      <div 
        className={`inline-flex items-center gap-1.5 bg-green-50 text-green-700 px-3 py-1.5 rounded-full border border-green-200 ${className}`}
        data-testid="price-match-badge-compact"
      >
        <ShieldCheck className="h-4 w-4" />
        <span className="text-xs font-semibold">Price Match Guarantee</span>
      </div>
    );
  }
  
  if (variant === 'banner') {
    return (
      <div 
        className={`bg-gradient-to-r from-green-600 to-emerald-600 text-white p-4 rounded-lg ${className}`}
        data-testid="price-match-badge-banner"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-white/20 rounded-full">
            <Award className="h-6 w-6" />
          </div>
          <div>
            <h3 className="font-bold text-lg">Price Match Guarantee</h3>
            <p className="text-sm text-green-100">
              Found it cheaper? We'll match any UK competitor's price!
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Default variant
  return (
    <div 
      className={`bg-gradient-to-br from-green-50 to-emerald-50 border border-green-200 rounded-lg p-4 ${className}`}
      data-testid="price-match-badge"
    >
      <div className="flex items-start gap-3">
        <div className="p-2 bg-green-100 rounded-lg">
          <BadgeCheck className="h-6 w-6 text-green-600" />
        </div>
        <div>
          <h4 className="font-semibold text-green-800 mb-1">Price Match Guarantee</h4>
          <p className="text-sm text-green-700">
            Found this tile cheaper elsewhere? We'll match the price!
          </p>
          <p className="text-xs text-green-600 mt-2">
            Contact us with proof of the lower price and we'll beat it.
          </p>
        </div>
      </div>
    </div>
  );
};

export default PriceMatchBadge;
