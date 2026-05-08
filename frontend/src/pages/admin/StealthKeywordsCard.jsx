/**
 * StealthKeywordsCard
 * ───────────────────
 * Surfaces the "stealth-keyword" SEO targeting feature on /admin/seo.
 *
 * What it lets the admin do:
 *   1. See live coverage stats: X / Y products carry stealth keywords
 *   2. ONE-CLICK auto-fill every product in the catalogue with its
 *      own supplier-original name + supplier code (the killer move —
 *      takes coverage from ~0% to ~100% in a single button press)
 *   3. Drill into a collection, see per-product chips, and edit/clear
 *      individual rows (granular override for any product whose
 *      original name shouldn't be indexed)
 *   4. Bulk-apply a custom keyword list to one collection
 *      (merge / replace / append-supplier-original modes)
 *   5. Set collection-wide alternate names (read at SSR time on
 *      /collections/<slug> pages — separate from per-product keys)
 *
 * Design choice: we DON'T let the admin paste 10KB of keyword spam.
 * Backend `_normalise()` caps each keyword at 80 chars and the whole
 * list at 25 entries — we mirror those caps in the UI's helper text
 * so the admin sees the limits before they hit them.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import {
  Loader2, Search, Sparkles, X, Plus, Wand2, Lock, Layers,
  ChevronRight, RefreshCw,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const token = () => localStorage.getItem('token') || localStorage.getItem('access_token') || '';
const authHeaders = () => ({ headers: { Authorization: `Bearer ${token()}` } });

const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString());

const splitKeywords = (raw) => {
  if (!raw) return [];
  return String(raw).split(/[,\n]+/).map((s) => s.trim()).filter(Boolean);
};


const StealthKeywordsCard = () => {
  const [stats, setStats] = useState(null);
  const [collections, setCollections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [autoFilling, setAutoFilling] = useState(false);
  const [selectedCollection, setSelectedCollection] = useState('');
  const [showOnlyMissing, setShowOnlyMissing] = useState(false);
  const [products, setProducts] = useState([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [collectionKeywords, setCollectionKeywords] = useState([]);
  const [collectionInput, setCollectionInput] = useState('');
  const [savingCollectionKws, setSavingCollectionKws] = useState(false);

  const loadStats = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([
        axios.get(`${API_URL}/api/admin/seo/stealth-keywords/stats`, authHeaders()),
        axios.get(`${API_URL}/api/admin/seo/stealth-keywords/collections`, authHeaders()),
      ]);
      setStats(s.data);
      setCollections(c.data.collections || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not load stealth-keyword stats');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);

  const loadProducts = useCallback(async () => {
    if (!selectedCollection) {
      setProducts([]);
      return;
    }
    setProductsLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/admin/seo/stealth-keywords/products`, {
        ...authHeaders(),
        params: { collection: selectedCollection, only_missing: showOnlyMissing, limit: 200 },
      });
      setProducts(r.data.products || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not load products');
    } finally {
      setProductsLoading(false);
    }
  }, [selectedCollection, showOnlyMissing]);

  useEffect(() => { loadProducts(); }, [loadProducts]);

  const loadCollectionKws = useCallback(async () => {
    if (!selectedCollection) {
      setCollectionKeywords([]);
      return;
    }
    try {
      const r = await axios.get(
        `${API_URL}/api/admin/seo/stealth-keywords/collection/${encodeURIComponent(selectedCollection)}`,
        authHeaders()
      );
      setCollectionKeywords(r.data.keywords || []);
    } catch {
      setCollectionKeywords([]);
    }
  }, [selectedCollection]);

  useEffect(() => { loadCollectionKws(); }, [loadCollectionKws]);

  const autoFillAll = async () => {
    if (autoFilling) return;
    // Step 1: dry-run preview
    setAutoFilling(true);
    try {
      const dr = await axios.post(
        `${API_URL}/api/admin/seo/stealth-keywords/auto-fill-all?dry_run=true`, {}, authHeaders()
      );
      const d = dr.data;
      const msg =
        `Stealth-fill preview:\n\n` +
        `• ${d.matched} active products scanned\n` +
        `• ${d.updated} would gain new keywords (+${d.keywords_added} alt-names total)\n` +
        `• ${d.skipped_already_have} already covered\n` +
        `• ${d.skipped_no_supplier_data} skipped (no original_name or supplier_code)\n\n` +
        `Apply now? (idempotent — safe to re-run)`;
      if (!window.confirm(msg)) {
        setAutoFilling(false);
        return;
      }
      const r = await axios.post(
        `${API_URL}/api/admin/seo/stealth-keywords/auto-fill-all`, {}, authHeaders()
      );
      const res = r.data;
      toast.success(
        `Stealth-fill complete · ${res.updated} products updated · +${res.keywords_added} alt-names indexable`
      );
      loadStats();
      loadProducts();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Auto-fill failed');
    } finally {
      setAutoFilling(false);
    }
  };

  const setProductKws = async (productId, keywords) => {
    try {
      await axios.post(
        `${API_URL}/api/admin/seo/stealth-keywords/products/${encodeURIComponent(productId)}`,
        { keywords },
        authHeaders()
      );
      toast.success('Keywords saved');
      loadProducts();
      loadStats();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    }
  };

  const applySuggested = (product) => {
    const merged = [...product.stealth_keywords, ...(product.suggested_keywords || [])];
    const seen = new Set();
    const deduped = [];
    for (const k of merged) {
      const lk = k.toLowerCase();
      if (!seen.has(lk)) { seen.add(lk); deduped.push(k); }
    }
    setProductKws(product.id, deduped);
  };

  const bulkApplySupplierToCollection = async () => {
    if (!selectedCollection) return;
    if (!window.confirm(
      `Append each product's supplier-original name + supplier code to its stealth keywords ` +
      `for every product in "${selectedCollection}"?\n\n` +
      `Idempotent — products that already have these keywords are skipped.`
    )) return;
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/seo/stealth-keywords/bulk-apply`,
        { collection: selectedCollection, keywords: [], mode: 'append_supplier_original' },
        authHeaders()
      );
      toast.success(
        `Updated ${r.data.updated} of ${r.data.matched} products in "${selectedCollection}"`
      );
      loadProducts();
      loadStats();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Bulk apply failed');
    }
  };

  const saveCollectionKeywords = async () => {
    if (!selectedCollection) return;
    setSavingCollectionKws(true);
    try {
      const kws = splitKeywords(collectionInput).slice(0, 25);
      await axios.post(
        `${API_URL}/api/admin/seo/stealth-keywords/collection/${encodeURIComponent(selectedCollection)}`,
        { keywords: kws },
        authHeaders()
      );
      setCollectionInput('');
      toast.success(`Saved ${kws.length} collection-wide keywords`);
      loadCollectionKws();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally {
      setSavingCollectionKws(false);
    }
  };

  const removeCollectionKeyword = async (kw) => {
    const next = collectionKeywords.filter((k) => k !== kw);
    try {
      await axios.post(
        `${API_URL}/api/admin/seo/stealth-keywords/collection/${encodeURIComponent(selectedCollection)}`,
        { keywords: next },
        authHeaders()
      );
      setCollectionKeywords(next);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Remove failed');
    }
  };

  if (loading) {
    return (
      <Card className="p-6 flex items-center gap-2 text-slate-500" data-testid="stealth-card-loading">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading stealth-keyword SEO…
      </Card>
    );
  }

  const coverage = stats?.coverage_pct || 0;
  const eligible = stats?.products_eligible || 0;
  const coveredCount = stats?.products_with_keywords || 0;
  const totalCount = stats?.products_total || 0;

  return (
    <Card className="overflow-hidden" data-testid="stealth-keywords-card">
      {/* Header */}
      <div className="bg-gradient-to-br from-slate-900 to-fuchsia-950 text-white px-6 py-5">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-widest text-fuchsia-300 font-semibold flex items-center gap-1.5">
              <Lock className="w-3 h-3" /> Stealth-Keyword SEO Targeting
            </div>
            <h3 className="text-xl font-bold mt-1 flex items-center gap-2">
              <Wand2 className="w-5 h-5 text-fuchsia-300" />
              Index supplier-original names · invisible on the page
            </h3>
            <p className="text-sm text-fuchsia-200/80 mt-1 max-w-2xl">
              Customers searching the supplier-original product names ("Opal", "LP-6611") land on
              your re-branded "Artisan Marble" listing. Names index in Google + Bing JSON-LD and
              meta tags only — never visible in the customer-facing UI.
            </p>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={loadStats}
            className="text-white hover:bg-white/10"
            data-testid="stealth-refresh-btn"
          >
            <RefreshCw className="w-4 h-4 mr-1" /> Refresh
          </Button>
        </div>

        {/* Stats strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-4 text-xs">
          <Stat label="Products" value={fmt(totalCount)} sub="active in catalogue" />
          <Stat
            label="Coverage"
            value={`${coverage}%`}
            sub={`${fmt(coveredCount)} / ${fmt(totalCount)} have keywords`}
            highlight={coverage >= 80}
          />
          <Stat
            label="Eligible"
            value={fmt(eligible)}
            sub="have a supplier-original name"
          />
          <Stat
            label="Collection sets"
            value={fmt(stats?.collection_keyword_sets || 0)}
            sub="collection-wide keywords"
          />
        </div>
      </div>

      <div className="p-5 space-y-5">
        {/* One-click auto-fill */}
        <div
          className="rounded-lg border-2 border-fuchsia-200 bg-gradient-to-br from-fuchsia-50 to-rose-50 p-4 flex items-start gap-3"
          data-testid="stealth-auto-fill-strip"
        >
          <div className="shrink-0 w-10 h-10 rounded-full bg-fuchsia-100 text-fuchsia-700 flex items-center justify-center">
            <Sparkles className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-slate-900">
              One-click: stealth-fill every product with its supplier-original name
            </div>
            <div className="text-xs text-slate-600 mt-0.5">
              Sweeps the entire catalogue and adds each product's <code className="px-1 bg-white rounded text-[10px] border">original_name</code> +{' '}
              <code className="px-1 bg-white rounded text-[10px] border">supplier_code</code> as
              indexable alt-names. Idempotent — already-covered products are skipped. Only the next
              Railway deploy + Semrush crawl needed for Google to pick them up.
            </div>
          </div>
          <Button
            onClick={autoFillAll}
            disabled={autoFilling || eligible === 0}
            className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white shrink-0"
            data-testid="stealth-auto-fill-btn"
          >
            {autoFilling
              ? <Loader2 className="w-4 h-4 animate-spin mr-2" />
              : <Sparkles className="w-4 h-4 mr-2" />}
            Auto-fill all {fmt(eligible)}
          </Button>
        </div>

        {/* Per-collection drill-down */}
        <div className="border-t pt-4">
          <h4 className="text-sm font-semibold text-slate-800 flex items-center gap-1.5 mb-3">
            <Layers className="w-4 h-4 text-slate-500" /> Drill into a collection
          </h4>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <select
              value={selectedCollection}
              onChange={(e) => setSelectedCollection(e.target.value)}
              className="border rounded px-3 py-2 text-sm min-w-[260px]"
              data-testid="stealth-collection-select"
            >
              <option value="">— pick a collection —</option>
              {collections.map((c) => (
                <option key={c.collection} value={c.collection}>
                  {c.collection || '(uncategorised)'} · {c.product_count} products · {c.coverage_pct}% covered
                </option>
              ))}
            </select>
            <label className="text-xs text-slate-600 inline-flex items-center gap-1.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={showOnlyMissing}
                onChange={(e) => setShowOnlyMissing(e.target.checked)}
                className="h-3.5 w-3.5 accent-fuchsia-600"
                data-testid="stealth-only-missing"
              />
              Only show products without keywords
            </label>
            {selectedCollection && (
              <Button
                size="sm"
                variant="outline"
                onClick={bulkApplySupplierToCollection}
                className="ml-auto"
                data-testid="stealth-bulk-supplier-btn"
              >
                <Wand2 className="w-3.5 h-3.5 mr-1" /> Append supplier-original to all in collection
              </Button>
            )}
          </div>

          {selectedCollection && (
            <CollectionKeywordsRow
              keywords={collectionKeywords}
              input={collectionInput}
              onInputChange={setCollectionInput}
              onSave={saveCollectionKeywords}
              onRemove={removeCollectionKeyword}
              saving={savingCollectionKws}
              collection={selectedCollection}
            />
          )}

          {selectedCollection && productsLoading && (
            <div className="text-center py-6 text-slate-500 text-sm">
              <Loader2 className="w-4 h-4 animate-spin inline mr-1.5" /> Loading products…
            </div>
          )}

          {selectedCollection && !productsLoading && products.length === 0 && (
            <div className="text-center py-8 text-slate-500 text-sm border rounded">
              {showOnlyMissing
                ? 'Every product in this collection already has stealth keywords.'
                : 'No products found in this collection.'}
            </div>
          )}

          {selectedCollection && !productsLoading && products.length > 0 && (
            <div className="overflow-x-auto border rounded">
              <table className="w-full text-sm">
                <thead className="text-xs text-slate-500 uppercase bg-slate-50">
                  <tr>
                    <th className="text-left py-2 px-3">Product</th>
                    <th className="text-left">Stealth keywords</th>
                    <th className="text-right pr-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((p) => (
                    <ProductRow
                      key={p.id}
                      product={p}
                      onSave={(kws) => setProductKws(p.id, kws)}
                      onUseSuggested={() => applySuggested(p)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
};


const Stat = ({ label, value, sub, highlight = false }) => (
  <div className={`rounded p-2 border ${highlight ? 'bg-emerald-500/15 border-emerald-300/40' : 'bg-white/10 border-white/20'}`}>
    <div className="text-[10px] uppercase tracking-wide text-fuchsia-200/70">{label}</div>
    <div className="text-lg font-bold mt-0.5 font-mono">{value}</div>
    {sub && <div className="text-[10px] text-fuchsia-200/60 mt-0.5">{sub}</div>}
  </div>
);


const CollectionKeywordsRow = ({
  keywords, input, onInputChange, onSave, onRemove, saving, collection,
}) => (
  <div
    className="rounded-lg border border-fuchsia-200 bg-fuchsia-50/40 p-3 mb-3"
    data-testid="stealth-collection-kws"
  >
    <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-800 mb-1.5">
      <Layers className="w-3.5 h-3.5 text-fuchsia-700" />
      Collection-wide alt-names for "{collection}"
      <span className="text-[10px] font-normal text-slate-500 ml-1">
        ({keywords.length} active · injected on /collections/&lt;slug&gt;)
      </span>
    </div>
    {keywords.length > 0 && (
      <div className="flex flex-wrap gap-1.5 mb-2" data-testid="stealth-collection-kw-chips">
        {keywords.map((kw) => (
          <Chip key={kw} label={kw} onRemove={() => onRemove(kw)} variant="fuchsia" />
        ))}
      </div>
    )}
    <div className="flex gap-2 items-center">
      <Input
        value={input}
        onChange={(e) => onInputChange(e.target.value)}
        placeholder="comma-separated alt-names · max 25 · 80 chars each"
        className="text-xs h-8"
        data-testid="stealth-collection-kw-input"
        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); onSave(); } }}
      />
      <Button
        size="sm"
        onClick={onSave}
        disabled={saving || !input.trim()}
        className="h-8 bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
        data-testid="stealth-collection-kw-save"
      >
        {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Plus className="w-3.5 h-3.5 mr-1" />}
        Save
      </Button>
    </div>
  </div>
);


const Chip = ({ label, onRemove, variant = 'slate' }) => {
  const colours = {
    slate: 'bg-slate-100 text-slate-800 border-slate-200',
    fuchsia: 'bg-fuchsia-100 text-fuchsia-900 border-fuchsia-200',
    emerald: 'bg-emerald-100 text-emerald-900 border-emerald-200',
    amber: 'bg-amber-100 text-amber-900 border-amber-200',
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${colours[variant]}`}>
      {label}
      {onRemove && (
        <button
          onClick={onRemove}
          className="hover:text-rose-600"
          aria-label={`Remove ${label}`}
          data-testid={`stealth-chip-remove-${label}`}
        >
          <X className="w-3 h-3" />
        </button>
      )}
    </span>
  );
};


const ProductRow = ({ product, onSave, onUseSuggested }) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState((product.stealth_keywords || []).join(', '));

  const saveDraft = () => {
    onSave(splitKeywords(draft).slice(0, 25));
    setEditing(false);
  };
  const cancel = () => {
    setDraft((product.stealth_keywords || []).join(', '));
    setEditing(false);
  };

  return (
    <tr className="border-t hover:bg-slate-50" data-testid={`stealth-product-row-${product.id}`}>
      <td className="py-2 px-3 align-top">
        <div className="flex items-start gap-2 min-w-0">
          {product.image_url && (
            <img
              src={product.image_url} alt=""
              className="w-10 h-10 rounded object-cover border shrink-0"
              loading="lazy"
            />
          )}
          <div className="min-w-0">
            <div className="font-medium text-slate-900 truncate max-w-[280px]">{product.name}</div>
            {product.original_name && (
              <div className="text-[10px] text-slate-500 truncate max-w-[280px]">
                ↪ supplier: <span className="font-mono">{product.original_name}</span>
              </div>
            )}
            {product.supplier_code && (
              <div className="text-[10px] text-slate-500">
                code: <span className="font-mono">{product.supplier_code}</span>
              </div>
            )}
          </div>
        </div>
      </td>
      <td className="align-top py-2">
        {editing ? (
          <div className="space-y-1.5">
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="comma-separated stealth keywords"
              className="text-xs h-8"
              data-testid={`stealth-product-edit-input-${product.id}`}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') { e.preventDefault(); saveDraft(); }
                if (e.key === 'Escape') cancel();
              }}
            />
            <div className="text-[10px] text-slate-500">25 max · 80 chars each</div>
          </div>
        ) : (product.stealth_keywords || []).length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {product.stealth_keywords.map((kw) => <Chip key={kw} label={kw} variant="emerald" />)}
            {(product.suggested_keywords || []).filter(
              (s) => !product.stealth_keywords.some((k) => k.toLowerCase() === s.toLowerCase())
            ).map((s) => <Chip key={s} label={`+ ${s}`} variant="amber" />)}
          </div>
        ) : (product.suggested_keywords || []).length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {product.suggested_keywords.map((s) => <Chip key={s} label={s} variant="amber" />)}
            <span className="text-[10px] text-amber-700 italic ml-1">suggested · click ✨ to apply</span>
          </div>
        ) : (
          <span className="text-[10px] text-slate-400 italic">no keywords yet</span>
        )}
      </td>
      <td className="align-top text-right pr-3 py-2 whitespace-nowrap">
        {editing ? (
          <>
            <Button
              size="sm" variant="outline"
              onClick={cancel}
              className="h-7 px-2 text-xs mr-1"
              data-testid={`stealth-product-cancel-${product.id}`}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={saveDraft}
              className="h-7 px-2 text-xs bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
              data-testid={`stealth-product-save-${product.id}`}
            >
              Save
            </Button>
          </>
        ) : (
          <>
            {(product.suggested_keywords || []).length > 0 && (
              <Button
                size="sm" variant="ghost"
                onClick={onUseSuggested}
                className="h-7 px-2 text-xs text-amber-800 hover:bg-amber-100"
                title="Add suggested supplier-original name + code"
                data-testid={`stealth-product-use-suggested-${product.id}`}
              >
                <Sparkles className="w-3.5 h-3.5 mr-1" /> Use suggested
              </Button>
            )}
            <Button
              size="sm" variant="ghost"
              onClick={() => setEditing(true)}
              className="h-7 px-2 text-xs"
              data-testid={`stealth-product-edit-${product.id}`}
            >
              Edit <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
            </Button>
          </>
        )}
      </td>
    </tr>
  );
};


export default StealthKeywordsCard;
