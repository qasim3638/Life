import React from 'react';

/**
 * SeoHead — single source of truth for per-page <title>, meta tags,
 * canonical URL, Open Graph and Twitter card.
 *
 * Implementation: uses React 19's native document metadata support.
 * Any <title>, <meta>, <link> or <script type="application/ld+json">
 * rendered inside a component is automatically hoisted into <head>
 * by React 19 — no provider, no portal library needed.
 *
 * Why a wrapper instead of inline tags everywhere?
 *   1. Forces every page to set a canonical URL (the #1 SEO crime is
 *      having two URLs render the same content with no canonical).
 *   2. Sensible defaults for OG/Twitter so we never ship a page with
 *      blank social previews.
 *   3. One place to extend later (price/availability for products,
 *      breadcrumbs, etc.) without touching every page.
 *
 * NOTE: react-helmet-async@2 was tried first but does not support
 * React 19 (peer-dep capped at ^18). React 19's native metadata
 * hoisting is the maintained, officially-supported approach.
 */

const DEFAULT_HOST = (
  process.env.REACT_APP_PUBLIC_SITE_URL ||
  'https://tilestation.co.uk'
).replace(/\/$/, '');

const DEFAULT_DESCRIPTION =
  'Tile Station — premium kitchen, bathroom and floor tiles delivered ' +
  'across the UK from our Kent and London showrooms. Trade pricing, ' +
  'free samples, expert advice.';

const DEFAULT_OG_IMAGE = `${DEFAULT_HOST}/og-image.jpg`;

function buildCanonical(canonicalPath) {
  if (!canonicalPath) {
    if (typeof window !== 'undefined') {
      return `${DEFAULT_HOST}${window.location.pathname}`;
    }
    return DEFAULT_HOST;
  }
  if (canonicalPath.startsWith('http')) return canonicalPath;
  const path = canonicalPath.startsWith('/') ? canonicalPath : `/${canonicalPath}`;
  return `${DEFAULT_HOST}${path}`;
}

export default function SeoHead({
  title,
  description,
  canonical,
  image,
  type = 'website',         // 'product' for tile pages, 'article' for info
  noindex = false,          // for cart, checkout, account etc
  keywords,                 // optional comma-separated string
  jsonLd,                   // optional JSON-LD object or array
}) {
  const finalTitle = title
    ? (title.includes('Tile Station') ? title : `${title} | Tile Station`)
    : 'Tile Station — Premium Tiles, Free UK Delivery';
  const finalDescription = (description || DEFAULT_DESCRIPTION).slice(0, 300);
  const canonicalUrl = buildCanonical(canonical);
  const ogImage = image || DEFAULT_OG_IMAGE;

  // React 19 hoists these tags to <head> automatically.
  return (
    <>
      <title>{finalTitle}</title>
      <meta name="description" content={finalDescription} />
      {keywords ? <meta name="keywords" content={keywords} /> : null}
      {noindex ? <meta name="robots" content="noindex, nofollow" /> : null}
      <link rel="canonical" href={canonicalUrl} />

      {/* Open Graph — for Facebook, WhatsApp, Slack, LinkedIn previews */}
      <meta property="og:type" content={type} />
      <meta property="og:site_name" content="Tile Station" />
      <meta property="og:title" content={finalTitle} />
      <meta property="og:description" content={finalDescription} />
      <meta property="og:url" content={canonicalUrl} />
      <meta property="og:image" content={ogImage} />
      <meta property="og:locale" content="en_GB" />

      {/* Twitter card — almost identical but Twitter ignores OG */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={finalTitle} />
      <meta name="twitter:description" content={finalDescription} />
      <meta name="twitter:image" content={ogImage} />

      {/* Optional inline JSON-LD for structured data */}
      {jsonLd ? (
        <script type="application/ld+json">
          {JSON.stringify(jsonLd)}
        </script>
      ) : null}
    </>
  );
}
