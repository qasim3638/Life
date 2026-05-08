import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { ChevronUp } from 'lucide-react';

// Scrolls to top on every route/search param change
export const ScrollToTop = () => {
  const { pathname, search } = useLocation();
  
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, [pathname, search]);
  
  return null;
};

// Floating "back to top" button — appears when scrolled past 400px
export const BackToTopButton = () => {
  const [visible, setVisible] = useState(false);
  
  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 400);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  
  if (!visible) return null;
  
  return (
    <button
      onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
      className="fixed bottom-20 right-6 z-50 bg-gray-900 text-white p-3 rounded-full shadow-lg hover:bg-gray-700 transition-all opacity-80 hover:opacity-100"
      aria-label="Back to top"
      data-testid="back-to-top-btn"
    >
      <ChevronUp className="w-5 h-5" />
    </button>
  );
};
