/**
 * TileProductRedirect - Resolves /tiles/:slug to either:
 *   1. An approved city/town SEO landing page (renders inline)
 *   2. A tile product (redirects to its collection page)
 *   3. Not-found
 *
 * The city-landing-page check runs FIRST and is fast (single Mongo
 * lookup) so SEO traffic to /tiles/tile-shop-gravesend etc. lands on
 * the right page without a wasteful redirect.
 */
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import CityLandingPage from './CityLandingPage';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const TileProductRedirect = () => {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState(null);
  const [isCityPage, setIsCityPage] = useState(null);  // null=checking, true/false=resolved

  useEffect(() => {
    if (!slug) return;
    let alive = true;

    (async () => {
      // 1. Try city landing page first.
      try {
        const r = await fetch(`${API_URL}/api/shop/city-page/${slug}`);
        if (alive && r.ok) {
          setIsCityPage(true);
          return;
        }
      } catch { /* fall through to product lookup */ }

      if (!alive) return;
      setIsCityPage(false);

      // 2. Fall back to product → collection redirect.
      try {
        const res = await fetch(`${API_URL}/api/tiles/products/${slug}/collection-info`);
        if (!res.ok) {
          if (res.status === 404) {
            if (alive) setError('Product not found');
            return;
          }
          throw new Error('Failed to fetch product info');
        }
        const data = await res.json();
        const collectionName = data.collection_name;
        if (collectionName) {
          navigate(`/shop/collection/${encodeURIComponent(collectionName)}?product=${slug}`, { replace: true });
        } else if (alive) {
          setError('Collection not found for this product');
        }
      } catch (err) {
        console.error('Error redirecting product:', err);
        if (alive) setError('Failed to load product');
      }
    })();

    return () => { alive = false; };
  }, [slug, navigate]);

  // Render city landing page in-place once we know it's one.
  if (isCityPage === true) return <CityLandingPage />;

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-800 mb-2">Product Not Found</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <a href="/tiles" className="text-blue-600 hover:underline">Browse all tiles</a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full mx-auto mb-4"></div>
        <p className="text-gray-600">Loading product...</p>
      </div>
    </div>
  );
};

export default TileProductRedirect;
