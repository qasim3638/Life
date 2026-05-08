import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';

const CompareContext = createContext(null);
const STORAGE_KEY = 'tilestation_compare';

export const CompareProvider = ({ children, max = 3 }) => {
  const [items, setItems] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch { return []; }
  });

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(items)); } catch { /* noop */ }
  }, [items]);

  const add = useCallback((tile) => {
    setItems(prev => {
      if (prev.find(t => t.slug === tile.slug)) return prev;
      if (prev.length >= max) return prev; // capped
      return [...prev, {
        slug: tile.slug,
        name: tile.name || tile.product_name || tile.display_name || tile.slug,
        image: tile.image_url || tile.image || (tile.images && tile.images[0]) || '',
        price: Number(tile.price || tile.list_price || 0),
      }];
    });
  }, [max]);

  const remove = useCallback((slug) => setItems(prev => prev.filter(t => t.slug !== slug)), []);
  const clear = useCallback(() => setItems([]), []);
  const has = useCallback((slug) => items.some(t => t.slug === slug), [items]);
  const isFull = items.length >= max;

  return (
    <CompareContext.Provider value={{ items, add, remove, clear, has, isFull, max }}>
      {children}
    </CompareContext.Provider>
  );
};

export const useCompare = () => {
  const ctx = useContext(CompareContext);
  if (!ctx) {
    return {
      items: [], add: () => {}, remove: () => {}, clear: () => {},
      has: () => false, isFull: false, max: 3,
    };
  }
  return ctx;
};
