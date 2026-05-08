/**
 * Sample-tier classification — JS mirror of backend/services/sample_tier.py
 *
 * MUST stay in sync with the Python version. Any tuning knob change
 * should happen in both files.
 *
 * Tiers:
 *   • free_small  — tile ≤ 200×200mm or ≤100×300mm. Tile IS the sample.
 *                   FREE + £2.99 delivery.
 *   • free_cut    — standard ~10×10cm cut piece. FREE + £2.99 delivery.
 *   • full_size   — 300×600mm cut piece, branded "Full Size Sample".
 *                   £5 each + £2.99 delivery. Additive on large-format tiles
 *                   (≥400mm short side AND ≥600mm long side).
 */

const SMALL_TILE_MAX_MM = 200;
const SMALL_TILE_RECT_NARROW_MM = 100;
const SMALL_TILE_RECT_LONG_MM = 300;
const LARGE_FORMAT_MIN_LONG_MM = 600;
const LARGE_FORMAT_MIN_SHORT_MM = 400;

export const FREE_SAMPLE_POSTAGE_GBP = 2.99;
export const FULL_SIZE_SAMPLE_PRICE_GBP = 5.00;

function normaliseDim(value) {
  if (value === null || value === undefined) return null;
  const v = parseFloat(value);
  if (!isFinite(v) || v <= 0) return null;
  return v;
}

/**
 * Classify a tile's dimensions into sample tiers.
 *
 * @param {number|string|null} tileWidth  — millimetres
 * @param {number|string|null} tileHeight — millimetres
 * @returns {{
 *   primary: 'free_small' | 'free_cut',
 *   offers: Array<'free_small' | 'free_cut' | 'full_size'>,
 *   widthMm: number|null,
 *   heightMm: number|null,
 *   fullSizeNote: string|null,
 * }}
 */
export function classifySample(tileWidth, tileHeight) {
  const w = normaliseDim(tileWidth);
  const h = normaliseDim(tileHeight);

  if (w === null || h === null) {
    return {
      primary: 'free_cut',
      offers: ['free_cut'],
      widthMm: w,
      heightMm: h,
      fullSizeNote: null,
    };
  }

  const longSide = Math.max(w, h);
  const shortSide = Math.min(w, h);

  const isSmallSquare = longSide <= SMALL_TILE_MAX_MM;
  const isNarrowRect =
    shortSide <= SMALL_TILE_RECT_NARROW_MM &&
    longSide <= SMALL_TILE_RECT_LONG_MM;

  if (isSmallSquare || isNarrowRect) {
    return {
      primary: 'free_small',
      offers: ['free_small'],
      widthMm: w,
      heightMm: h,
      fullSizeNote: null,
    };
  }

  if (longSide >= LARGE_FORMAT_MIN_LONG_MM && shortSide >= LARGE_FORMAT_MIN_SHORT_MM) {
    const note =
      longSide <= 600 && shortSide <= 300
        ? null
        : `This is a large sample cut to approximately 300×600 mm from a ${Math.round(longSide)}×${Math.round(shortSide)} mm tile.`;
    return {
      primary: 'free_cut',
      offers: ['free_cut', 'full_size'],
      widthMm: w,
      heightMm: h,
      fullSizeNote: note,
    };
  }

  return {
    primary: 'free_cut',
    offers: ['free_cut'],
    widthMm: w,
    heightMm: h,
    fullSizeNote: null,
  };
}

/**
 * Extract tile_width / tile_height from a product object. Products have
 * inconsistent field names across the codebase (tile_width, size string,
 * etc.). This helper hides that detail from callers.
 */
export function getTileDims(product) {
  if (!product) return { width: null, height: null };
  // Preferred: explicit numeric fields
  if (product.tile_width && product.tile_height) {
    return { width: product.tile_width, height: product.tile_height };
  }
  // Fallback: parse "600x1200", "600 x 1200mm", "600X1200" from size string
  const sizeStr = product.size || product.tile_size;
  if (typeof sizeStr === 'string') {
    const m = sizeStr.match(/(\d+)\s*[xX×]\s*(\d+)/);
    if (m) return { width: parseInt(m[1], 10), height: parseInt(m[2], 10) };
  }
  return { width: null, height: null };
}

/**
 * Convenience: classify straight from a product object.
 */
export function classifySampleForProduct(product) {
  const { width, height } = getTileDims(product);
  return classifySample(width, height);
}

export const SAMPLE_TIER_LABELS = {
  free_small: 'Free Sample (actual tile)',
  free_cut:   'Free Sample (10×10 cm cut piece)',
  full_size:  'Full Size Sample (300×600 mm) — £5',
};

export const SAMPLE_TIER_SHORT = {
  free_small: 'Free sample',
  free_cut:   'Free sample',
  full_size:  'Full Size £5',
};
