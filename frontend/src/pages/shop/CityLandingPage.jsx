/**
 * CityLandingPage — public route at `/tiles/<slug>` for AI-generated
 * UK city/town landing pages. SEO-optimised: H1 + structured data +
 * meta tags via document title + descriptive intro.
 *
 * Renders the body markdown + a CTA grid + breadcrumb. The storefront
 * shell (header/footer) is provided by the parent route.
 */
import React, { useEffect, useState } from 'react';
import { useParams, Link, Navigate } from 'react-router-dom';
import { Loader2, MapPin, Phone } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { ShopHeader, ShopFooter } from './TileStationHome';
import { BreadcrumbSchema } from '../../components/seo/StructuredData';
import SeoHead from '../../components/seo/SeoHead';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const CityLandingPage = () => {
  const { slug } = useParams();
  const [page, setPage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setNotFound(false);
    // `credentials: include` so the A/B sticky cookie set by the API is
    // accepted by the browser on cross-subdomain Railway → Vercel.
    fetch(`${API_URL}/api/shop/city-page/${slug}`, { credentials: 'include' })
      .then((r) => {
        if (r.status === 404) { setNotFound(true); return null; }
        return r.json();
      })
      .then((d) => { if (alive && d) setPage(d); })
      .catch(() => { if (alive) setNotFound(true); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [slug]);

  // (SEO title + meta description handled declaratively by <SeoHead> below.)

  if (notFound) return <Navigate to="/tiles" replace />;

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!page) return null;

  const breadcrumbs = [
    { name: 'Home', url: '/' },
    { name: 'Tiles', url: '/tiles' },
    { name: page.town, url: `/tiles/${slug}` },
  ];

  const trackCtaClick = () => {
    // Fire-and-forget — never block navigation. The active_variant field
    // is only present when an A/B test is running on this page; if it
    // isn't there we skip the call entirely.
    if (!page.active_variant) return;
    try {
      fetch(`${API_URL}/api/shop/city-page/track-cta-click`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug, variant: page.active_variant }),
        keepalive: true,
      });
    } catch { /* ignore — tracking must never break the click */ }
  };

  return (
    <div className="min-h-screen bg-white flex flex-col" data-testid="city-landing-page">
      <SeoHead
        title={page.meta_title || `${page.h1} | Tile Station`}
        description={page.meta_description}
        canonical={`/tiles/${slug}`}
        type="website"
        keywords={Array.from(new Set([
          page.intent_phrase,
          `tile shop ${page.town}`,
          `tiles ${page.town}`,
          page.county ? `tiles ${page.county}` : null,
        ].filter(Boolean))).join(', ')}
      />
      <BreadcrumbSchema items={breadcrumbs} />
      <ShopHeader />

      <main className="flex-1 container mx-auto px-4 sm:px-6 py-8 max-w-4xl">
        <nav className="text-xs text-gray-500 mb-4" aria-label="Breadcrumb">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="mx-2">/</span>
          <Link to="/tiles" className="hover:underline">Tiles</Link>
          <span className="mx-2">/</span>
          <span className="text-gray-800 font-medium">{page.town}</span>
        </nav>

        <h1 className="text-3xl sm:text-4xl font-heading font-bold text-gray-900 leading-tight">
          {page.h1}
        </h1>
        <div className="flex items-center gap-2 mt-2 text-sm text-gray-500">
          <MapPin className="w-4 h-4" /> Serving {page.town}, {page.county}
        </div>

        <article className="prose prose-stone max-w-none mt-6 prose-headings:font-heading prose-headings:font-bold prose-h1:hidden prose-h2:text-2xl prose-h2:mt-8 prose-a:text-indigo-700 prose-img:rounded prose-li:my-1">
          {page.body_md && <ReactMarkdown>{page.body_md}</ReactMarkdown>}
        </article>

        <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            to="/tiles"
            onClick={trackCtaClick}
            className="block p-5 bg-[#F7EA1C] rounded-lg hover:bg-yellow-300 transition"
            data-testid="city-landing-cta-shop"
          >
            <div className="font-bold text-gray-900">Browse our full tile range</div>
            <div className="text-sm text-gray-700 mt-1">Free UK delivery on orders over £500</div>
          </Link>
          <a
            href="tel:+441474000000"
            onClick={trackCtaClick}
            className="block p-5 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition"
            data-testid="city-landing-cta-call"
          >
            <div className="font-bold flex items-center gap-2"><Phone className="w-4 h-4" /> Call our showroom</div>
            <div className="text-sm text-gray-300 mt-1">Local fitters available · samples on request</div>
          </a>
        </div>
      </main>
      <ShopFooter />
    </div>
  );
};

export default CityLandingPage;
