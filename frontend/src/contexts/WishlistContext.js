import React, { createContext, useContext, useState, useEffect } from 'react';

const WishlistContext = createContext();

export const useWishlist = () => {
  const context = useContext(WishlistContext);
  if (!context) {
    throw new Error('useWishlist must be used within a WishlistProvider');
  }
  return context;
};

export const WishlistProvider = ({ children }) => {
  const [wishlist, setWishlist] = useState([]);

  // Load wishlist from localStorage on mount
  useEffect(() => {
    const savedWishlist = localStorage.getItem('tilestation_wishlist');
    if (savedWishlist) {
      try {
        setWishlist(JSON.parse(savedWishlist));
      } catch (e) {
        console.error('Error loading wishlist:', e);
      }
    }
  }, []);

  // Save wishlist to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('tilestation_wishlist', JSON.stringify(wishlist));
  }, [wishlist]);

  const addToWishlist = (tile) => {
    setWishlist(prev => {
      if (prev.find(item => item.id === tile.id)) {
        return prev;
      }
      return [...prev, {
        id: tile.id,
        slug: tile.slug,
        display_name: tile.display_name,
        image: tile.images?.[0] || '',
        price: tile.room_lot_price || tile.price,
        size: tile.size,
        finish: tile.finish
      }];
    });
  };

  const removeFromWishlist = (tileId) => {
    setWishlist(prev => prev.filter(item => item.id !== tileId));
  };

  const isInWishlist = (tileId) => {
    return wishlist.some(item => item.id === tileId);
  };

  const toggleWishlist = (tile) => {
    if (isInWishlist(tile.id)) {
      removeFromWishlist(tile.id);
      return false;
    } else {
      addToWishlist(tile);
      return true;
    }
  };

  const value = {
    wishlist,
    addToWishlist,
    removeFromWishlist,
    isInWishlist,
    toggleWishlist
  };

  return (
    <WishlistContext.Provider value={value}>
      {children}
    </WishlistContext.Provider>
  );
};

export default WishlistProvider;
