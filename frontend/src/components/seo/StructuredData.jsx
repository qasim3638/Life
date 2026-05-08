/**
 * StructuredData — emits JSON-LD schema.org markup for the storefront.
 *
 * Strategy: each page renders one or more <script type="application/ld+json">
 * tags. Google reads these to display rich results (star ratings, breadcrumbs,
 * FAQ accordions, store info, prices) directly in search snippets. Rich
 * results lift CTR by 25-50% on average.
 *
 * Coverage:
 *   - Organization + LocalBusiness on every page (for sitelinks + brand
 *     knowledge panel)
 *   - Product schema on each PDP (price, availability, aggregateRating,
 *     brand, image)
 *   - BreadcrumbList on category + product pages
 *   - FAQPage on category pages with FAQ blocks
 *   - SearchAction sitelinks search box on home
 *
 * All emitted markup follows Google's required-properties list as of 2026.
 */
import React from 'react';

const SHOP_URL = 'https://tilestation.co.uk';
const BRAND = 'Tile Station';
const LOGO = `${SHOP_URL}/logo.png`;
// Showrooms — keep in sync with backend /api/website/locations if added later.
const SHOWROOMS = [
  {
    name: 'Tile Station Gravesend',
    streetAddress: 'Unit 2, Riverside Industrial Estate',
    addressLocality: 'Gravesend',
    addressRegion: 'Kent',
    postalCode: 'DA12 2RU',
    addressCountry: 'GB',
    telephone: '+44-1474-000000',
    geo: { latitude: 51.4413, longitude: 0.3697 },
    radius_miles: 25,
  },
];


const Json = ({ data }) => (
  <script
    type="application/ld+json"
    dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
  />
);


/** Always-on Organization + sitelinks search box (mount in App root once). */
export const OrganizationSchema = () => {
  const data = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: BRAND,
    url: SHOP_URL,
    logo: LOGO,
    sameAs: [
      'https://www.facebook.com/tilestation',
      'https://www.instagram.com/tilestation',
    ],
    potentialAction: {
      '@type': 'SearchAction',
      target: `${SHOP_URL}/shop/search?q={search_term_string}`,
      'query-input': 'required name=search_term_string',
    },
  };
  return <Json data={data} />;
};


/** LocalBusiness for each showroom — Google Maps + local pack ranking. */
export const LocalBusinessSchema = () => {
  const data = SHOWROOMS.map((s, i) => ({
    '@context': 'https://schema.org',
    '@type': 'TileShop',
    '@id': `${SHOP_URL}#showroom-${i}`,
    name: s.name,
    url: SHOP_URL,
    image: LOGO,
    telephone: s.telephone,
    priceRange: '££',
    address: {
      '@type': 'PostalAddress',
      streetAddress: s.streetAddress,
      addressLocality: s.addressLocality,
      addressRegion: s.addressRegion,
      postalCode: s.postalCode,
      addressCountry: s.addressCountry,
    },
    geo: { '@type': 'GeoCoordinates', latitude: s.geo.latitude, longitude: s.geo.longitude },
    areaServed: {
      '@type': 'GeoCircle',
      geoMidpoint: { '@type': 'GeoCoordinates', latitude: s.geo.latitude, longitude: s.geo.longitude },
      geoRadius: `${(s.radius_miles * 1609).toFixed(0)}`,
    },
    openingHoursSpecification: [
      {
        '@type': 'OpeningHoursSpecification',
        dayOfWeek: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
        opens: '09:00',
        closes: '17:30',
      },
      {
        '@type': 'OpeningHoursSpecification',
        dayOfWeek: 'Saturday',
        opens: '09:00',
        closes: '16:00',
      },
    ],
  }));
  return data.map((d, i) => <Json key={i} data={d} />);
};


/** Product schema for a tile/product detail page. */
export const ProductSchema = ({ product }) => {
  if (!product || !product.name) return null;
  const data = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: product.name,
    image: product.images || product.image_url ? [product.images?.[0] || product.image_url] : undefined,
    description: product.description || `${product.name} — premium tiles from Tile Station.`,
    sku: product.sku || product.id,
    brand: { '@type': 'Brand', name: product.brand || BRAND },
    offers: {
      '@type': 'Offer',
      url: `${SHOP_URL}${product.url || ''}`,
      priceCurrency: 'GBP',
      price: product.price || product.room_lot_price || 0,
      availability: (product.in_stock !== false)
        ? 'https://schema.org/InStock'
        : 'https://schema.org/OutOfStock',
      seller: { '@type': 'Organization', name: BRAND },
    },
  };
  if (product.aggregate_rating?.rating_value && product.aggregate_rating?.review_count) {
    data.aggregateRating = {
      '@type': 'AggregateRating',
      ratingValue: product.aggregate_rating.rating_value,
      reviewCount: product.aggregate_rating.review_count,
    };
  } else if (product.avg_rating && product.review_count) {
    // Accept the flat shape returned by /api/products/* — single source of
    // truth, no rename gymnastics needed in the React layer.
    data.aggregateRating = {
      '@type': 'AggregateRating',
      ratingValue: Number(product.avg_rating),
      reviewCount: Number(product.review_count),
    };
  }
  return <Json data={data} />;
};


/** ReviewList — emits one Review per row. Google requires AggregateRating
 * to also be present (we emit that on ProductSchema) for stars to show
 * in SERP. Keeping these split keeps the markup easy to debug. */
export const ProductReviewsSchema = ({ product, reviews }) => {
  if (!product?.name || !reviews?.length) return null;
  return reviews.slice(0, 10).map((r, i) => (
    <Json
      key={i}
      data={{
        '@context': 'https://schema.org',
        '@type': 'Review',
        itemReviewed: { '@type': 'Product', name: product.name, sku: product.sku || product.id },
        author: { '@type': 'Person', name: r.author_name || r.user_name || 'Verified buyer' },
        reviewRating: {
          '@type': 'Rating',
          ratingValue: Number(r.rating || 5),
          bestRating: 5,
          worstRating: 1,
        },
        reviewBody: (r.comment || r.body || '').slice(0, 500),
        datePublished: r.created_at || r.date,
      }}
    />
  ));
};


/** BreadcrumbList — improves "site path" in SERP snippets. */
export const BreadcrumbSchema = ({ items }) => {
  if (!items?.length) return null;
  const data = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((it, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: it.name,
      item: it.url?.startsWith('http') ? it.url : `${SHOP_URL}${it.url || ''}`,
    })),
  };
  return <Json data={data} />;
};


/** FAQPage — eligible for the FAQ accordion in SERP. */
export const FAQSchema = ({ faqs }) => {
  if (!faqs?.length) return null;
  const data = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqs.map((f) => ({
      '@type': 'Question',
      name: f.question,
      acceptedAnswer: { '@type': 'Answer', text: f.answer },
    })),
  };
  return <Json data={data} />;
};
