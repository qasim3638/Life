'use client';

import { useState, useEffect } from 'react';
import { Heart, Loader2 } from 'lucide-react';
import api from '@/lib/api';

interface WishlistButtonProps {
  productId: string;
}

export function WishlistButton({ productId }: WishlistButtonProps) {
  const [isInWishlist, setIsInWishlist] = useState(false);
  const [loading, setLoading] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    checkWishlistStatus();
  }, [productId]);

  const checkWishlistStatus = async () => {
    const token = localStorage.getItem('shop_token');
    if (!token) {
      setIsLoggedIn(false);
      return;
    }
    
    setIsLoggedIn(true);
    
    try {
      const wishlist = await api.getWishlist(token);
      setIsInWishlist(wishlist.some(p => p.id === productId));
    } catch (err) {
      console.error('Failed to check wishlist:', err);
    }
  };

  const toggleWishlist = async () => {
    const token = localStorage.getItem('shop_token');
    
    if (!token) {
      // Redirect to login
      window.location.href = `/login?redirect=/products/${productId}`;
      return;
    }
    
    setLoading(true);
    
    try {
      if (isInWishlist) {
        await api.removeFromWishlist(token, productId);
        setIsInWishlist(false);
      } else {
        await api.addToWishlist(token, productId);
        setIsInWishlist(true);
      }
    } catch (err) {
      console.error('Failed to update wishlist:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={toggleWishlist}
      disabled={loading}
      className={`flex items-center justify-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
        isInWishlist
          ? 'bg-red-50 text-red-600 border border-red-200 hover:bg-red-100'
          : 'border border-slate-300 text-slate-700 hover:bg-slate-50'
      }`}
      title={isInWishlist ? 'Remove from wishlist' : 'Add to wishlist'}
      data-testid="wishlist-btn"
    >
      {loading ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : (
        <Heart className={`w-4 h-4 ${isInWishlist ? 'fill-red-500' : ''}`} />
      )}
      {isInWishlist ? 'Saved' : 'Save'}
    </button>
  );
}
