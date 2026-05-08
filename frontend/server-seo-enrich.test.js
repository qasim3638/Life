/**
 * Tests for server-seo-enrich.js (dynamic per-product SEO enrichment).
 *
 * Run with: cd /app/frontend && node server-seo-enrich.test.js
 *
 * Asserts that buildProductMeta and buildCollectionMeta produce
 * sensible titles/descriptions/JSON-LD for known shapes of input.
 * Doesn't hit the live backend — tests pure data transformation.
 */
const assert = require('node:assert/strict');
const { buildProductMeta, buildCollectionMeta } = require('./server-seo-enrich');

let pass = 0, fail = 0;
const t = (name, fn) => {
  try { fn(); pass++; console.log(`  ✓ ${name}`); }
  catch (e) { fail++; console.log(`  ✗ ${name} — ${e.message}`); }
};

// ── Product meta ──────────────────────────────────────────────────────
t('product: full data → enriched title with material + price', () => {
  const meta = buildProductMeta({
    name: 'Onyx White Polished 60x120cm',
    price_per_m2: 89.50,
    material: 'Porcelain',
    images: ['https://cdn.example.com/onyx-1.jpg'],
    supplier_code: 'ONX-WHT-60120',
  }, 'onyx-white-polished');
  assert.match(meta.title, /Onyx White/, 'title has product name');
  assert.match(meta.title, /Porcelain/, 'title includes material');
  assert.match(meta.title, /£89\.50/, 'title includes price');
  assert.match(meta.title, /Tile Station/, 'title has brand');
  assert.ok(meta.title.length <= 130, 'title within 130 chars');
});

t('product: missing price → no £ in title (graceful)', () => {
  const meta = buildProductMeta({ name: 'Mystery Tile' }, 'mystery-tile');
  assert.match(meta.title, /Mystery Tile/);
  assert.doesNotMatch(meta.title, /£/);
});

t('product: JSON-LD has Schema.org Product fields', () => {
  const meta = buildProductMeta({
    name: 'Carrara White',
    price_per_m2: 65,
    material: 'Marble',
    images: ['https://cdn.example.com/carrara.jpg'],
    supplier_code: 'CAR-WHT',
  }, 'carrara-white');
  assert.equal(meta.jsonld['@context'], 'https://schema.org/');
  assert.equal(meta.jsonld['@type'], 'Product');
  assert.equal(meta.jsonld.sku, 'CAR-WHT');
  assert.equal(meta.jsonld.brand.name, 'Tile Station');
  assert.equal(meta.jsonld.offers.price, '65.00');
  assert.equal(meta.jsonld.offers.priceCurrency, 'GBP');
  assert.equal(meta.jsonld.offers.priceSpecification.unitCode, 'MTK');
  assert.equal(meta.jsonld.offers.availability, 'https://schema.org/InStock');
});

t('product: image dict shape ([{url:...}]) is normalised', () => {
  const meta = buildProductMeta({
    name: 'Tile X', price_per_m2: 30,
    images: [{ url: 'a.jpg' }, { url: 'b.jpg' }],
  }, 'tile-x');
  assert.deepEqual(meta.jsonld.image, ['a.jpg', 'b.jpg']);
});

t('product: missing input returns null', () => {
  assert.equal(buildProductMeta(null, 'whatever'), null);
});

// ── Collection meta ───────────────────────────────────────────────────
t('collection: with product_count uses it in title', () => {
  const meta = buildCollectionMeta(
    { name: 'Marble Collection', product_count: 24 },
    'marble',
  );
  assert.match(meta.title, /Marble Collection/);
  assert.match(meta.title, /24 Tiles/);
});

t('collection: without product_count still produces title', () => {
  const meta = buildCollectionMeta({ name: 'Bathroom' }, 'bathroom');
  assert.match(meta.title, /Bathroom/);
});

t('collection: null input returns null', () => {
  assert.equal(buildCollectionMeta(null, 'x'), null);
});

// ── Stealth keywords on collection meta ──────────────────────────────
t('collection: stealth keywords passed through verbatim', () => {
  const meta = buildCollectionMeta(
    { name: 'Marble Collection', product_count: 24 },
    'marble',
    ['Calacatta', 'Carrara', 'Statuario'],
  );
  assert.deepEqual(meta.stealthKeywords, ['Calacatta', 'Carrara', 'Statuario']);
});

t('collection: stealth keyword equal to display name is filtered out', () => {
  const meta = buildCollectionMeta(
    { name: 'Marble Effect', product_count: 5 },
    'marble-effect',
    ['marble effect', 'Calacatta'],  // first matches the name (case-insensitive) → drop
  );
  assert.deepEqual(meta.stealthKeywords, ['Calacatta']);
});

t('collection: empty/oversize stealth keywords filtered', () => {
  const meta = buildCollectionMeta(
    { name: 'Marble', product_count: 5 },
    'marble',
    ['  ', 'a'.repeat(100), 'OK'],
  );
  assert.deepEqual(meta.stealthKeywords, ['OK']);
});

t('collection: empty stealth keyword list omits the field entirely', () => {
  const meta = buildCollectionMeta(
    { name: 'Marble', product_count: 5 }, 'marble', [],
  );
  assert.equal(meta.stealthKeywords, undefined);
});

t('collection: non-array stealth keywords ignored gracefully', () => {
  const meta = buildCollectionMeta(
    { name: 'Marble', product_count: 5 }, 'marble', null,
  );
  assert.equal(meta.stealthKeywords, undefined);
});

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
