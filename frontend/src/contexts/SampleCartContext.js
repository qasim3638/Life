import React, { createContext, useContext, useState, useEffect } from 'react';
import { toast } from 'sonner';
import { FULL_SIZE_SAMPLE_PRICE_GBP } from '../lib/sampleTier';

const SampleCartContext = createContext(null);

// Free samples are capped (postage subsidised, cutting labour). Paid
// full-size samples have no cap — customer pays per piece.
const MAX_FREE_SAMPLES_PER_ORDER = 3;
const SAMPLE_POSTAGE = 2.99;

export const useSampleCart = () => {
  const context = useContext(SampleCartContext);
  if (!context) {
    throw new Error('useSampleCart must be used within SampleCartProvider');
  }
  return context;
};

export const SampleCartProvider = ({ children }) => {
  const [samples, setSamples] = useState([]);

  // Load from localStorage on mount - with validation
  useEffect(() => {
    const saved = localStorage.getItem('tile_samples');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        // Filter out invalid samples (must have id at minimum)
        const validSamples = parsed.filter(s => s && s.id);
        
        if (validSamples.length !== parsed.length) {
          console.log(`Cleaned ${parsed.length - validSamples.length} invalid samples`);
          localStorage.setItem('tile_samples', JSON.stringify(validSamples));
        }
        
        setSamples(validSamples);
      } catch (e) {
        console.error('Error loading samples:', e);
        localStorage.removeItem('tile_samples');
      }
    }
  }, []);

  // Save to localStorage on change
  useEffect(() => {
    localStorage.setItem('tile_samples', JSON.stringify(samples));
  }, [samples]);

  const addSample = (tile, options = {}) => {
    // `sampleType` one of: 'free_small' | 'free_cut' | 'full_size'
    // Defaults to 'free_cut' for backward-compatibility with older
    // callers that still invoke addSample(tile).
    const sampleType = options.sampleType || 'free_cut';
    const isPaid = sampleType === 'full_size';
    const priceGbp = isPaid ? FULL_SIZE_SAMPLE_PRICE_GBP : 0;

    // Cap only applies to free samples. Paid full-size samples are
    // unlimited because the customer pays per piece + cutting labour
    // is covered by the £5.
    const freeCount = samples.filter((s) => !s.is_paid).length;
    if (!isPaid && freeCount >= MAX_FREE_SAMPLES_PER_ORDER) {
      toast.error('3 free-sample limit per order — place another order for more, or choose a Full Size Sample.');
      return false;
    }

    // Duplicate-detection is now keyed on (id + sampleType) so a
    // customer can order the same tile as BOTH a free cut sample AND
    // a full-size paid sample if they want to compare.
    if (samples.some((s) => s.id === tile.id && (s.sample_type || 'free_cut') === sampleType)) {
      toast.info('This sample is already in your basket');
      return false;
    }

    const imageUrl = tile.image || tile.images?.[0] || '';

    const sample = {
      id: tile.id,
      slug: tile.slug,
      display_name: tile.display_name || tile.name,
      image: imageUrl,
      size: tile.size,
      finish: tile.finish,
      color: tile.color,
      supplier_code: tile.supplier_code || tile.sku,
      sample_type: sampleType,         // 'free_small' | 'free_cut' | 'full_size'
      is_paid: isPaid,
      price_gbp: priceGbp,
    };

    setSamples((prev) => [...prev, sample]);
    toast.success(isPaid ? 'Full Size sample added to basket' : 'Sample added to basket');
    return true;
  };

  const removeSample = (id) => {
    setSamples(prev => prev.filter(s => s.id !== id));
    toast.success('Sample removed');
  };

  // Silent variant — used by validateAgainstServer when pruning stale
  // entries that the user never asked to remove. We don't toast each one
  // because seeing "Sample removed" 3× in a row when they hit the basket
  // would just confuse them.
  const removeSampleSilent = (id) => {
    setSamples(prev => prev.filter(s => s.id !== id));
  };

  // Validate every sample against the live products API and silently
  // drop any that no longer exist. Called by the basket page on mount.
  // Stops the long-tail bug where a customer added a sample weeks ago,
  // we deleted that product (supplier re-import / SKU rename), and now
  // they're stuck on "Product XYZ not found" at the Pay button.
  //
  // We probe BOTH catalogs in parallel because storefront samples can
  // be either `products` (UUID id) or `tiles` (24-char ObjectId).
  // A sample is only considered stale if BOTH endpoints return 404.
  const validateAgainstServer = async () => {
    if (samples.length === 0) return { ok: true, removed: [] };
    const API_URL = process.env.REACT_APP_BACKEND_URL;
    const removed = [];
    for (const s of samples) {
      try {
        const [byProduct, bySlug] = await Promise.all([
          fetch(`${API_URL}/api/shop/products/${s.id}`),
          // Tiles collection is keyed by slug on the storefront — that's
          // the only stable lookup that doesn't need an ObjectId helper.
          s.slug ? fetch(`${API_URL}/api/tiles/products/${s.slug}`) : Promise.resolve({ ok: false }),
        ]);
        if (!byProduct.ok && !bySlug.ok) {
          removed.push(s);
        }
      } catch (_e) { /* network blip — leave sample, retry next load */ }
    }
    if (removed.length > 0) {
      const removedIds = new Set(removed.map((r) => r.id));
      setSamples((prev) => prev.filter((s) => !removedIds.has(s.id)));
      toast.warning(
        `${removed.length} sample${removed.length === 1 ? '' : 's'} no longer available — removed from your basket. Please add fresh ones.`
      );
    }
    return { ok: removed.length === 0, removed };
  };

  const clearSamples = () => {
    setSamples([]);
    localStorage.removeItem('tile_samples');
  };

  const isInSamples = (id, sampleType) => {
    if (sampleType) {
      return samples.some((s) => s.id === id && (s.sample_type || 'free_cut') === sampleType);
    }
    return samples.some((s) => s.id === id);
  };

  const freeSampleCount = samples.filter((s) => !s.is_paid).length;
  const paidSampleCount = samples.filter((s) => s.is_paid).length;
  const samplesSubtotal = samples.reduce((acc, s) => acc + (s.price_gbp || 0), 0);

  return (
    <SampleCartContext.Provider value={{
      samples,
      sampleCount: samples.length,
      freeSampleCount,
      paidSampleCount,
      maxSamples: MAX_FREE_SAMPLES_PER_ORDER,
      postage: SAMPLE_POSTAGE,
      samplesSubtotal,
      // Only the FREE cap gates "Add another free sample" buttons.
      // Paid full-size samples always addable.
      canAddMore: freeSampleCount < MAX_FREE_SAMPLES_PER_ORDER,
      canAddFree: freeSampleCount < MAX_FREE_SAMPLES_PER_ORDER,
      addSample,
      removeSample,
      removeSampleSilent,
      validateAgainstServer,
      clearSamples,
      isInSamples,
    }}>
      {children}
    </SampleCartContext.Provider>
  );
};
