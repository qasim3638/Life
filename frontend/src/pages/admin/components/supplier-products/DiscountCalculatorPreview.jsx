import React, { useState, useMemo, useEffect } from 'react';
import { Calculator, Eye, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

const DiscountCalculatorPreview = ({ selectedProduct, tierPricingConfig, onClose }) => {
  const [expanded, setExpanded] = useState(false);
  const [inputs, setInputs] = useState({
    basePrice: 0,
    wasPrice: 0,
    wasMarkupPct: 0,
    tradeDiscount: 0,
    creditBack: 0,
    tierEnabled: true,
    thresholds: [10, 50, 100],
    discounts: [0, 5, 10, 15],
    saleActive: false,
    pricingUnit: 'm2',
  });

  // Auto-populate from product + tier config
  useEffect(() => {
    if (!selectedProduct) return;
    const listPrice = selectedProduct.list_price || selectedProduct.price || selectedProduct.room_lot_price || 0;
    const wasMarkup = parseFloat(selectedProduct.was_markup_percent) || 0;
    let wasPrice = parseFloat(selectedProduct.was_price) || 0;
    if (!wasPrice && wasMarkup > 0 && listPrice > 0) {
      wasPrice = parseFloat((listPrice * (1 + wasMarkup / 100)).toFixed(2));
    }
    const trade = parseFloat(selectedProduct.trade_discount) || parseFloat(tierPricingConfig?.trade_discount_default) || 0;
    const creditBack = parseFloat(selectedProduct.credit_back_rate) || parseFloat(tierPricingConfig?.credit_back_default) || 0;
    const tierEnabled = !(selectedProduct.tier_pricing_disabled || tierPricingConfig?.disabled);
    const thresholds = selectedProduct.tier_thresholds || tierPricingConfig?.thresholds || [10, 50, 100];
    const discounts = selectedProduct.tier_discounts || tierPricingConfig?.discounts || [0, 5, 10, 15];
    const saleActive = selectedProduct.sale_active || selectedProduct.on_sale || false;
    const pricingUnit = selectedProduct.pricing_unit || 'm2';

    setInputs({
      basePrice: listPrice,
      wasPrice,
      wasMarkupPct: wasMarkup,
      tradeDiscount: trade,
      creditBack,
      tierEnabled,
      thresholds,
      discounts,
      saleActive,
      pricingUnit,
    });
  }, [selectedProduct, tierPricingConfig]);

  const syncWasFromMarkup = (markup) => {
    const m = parseFloat(markup) || 0;
    if (m > 0 && inputs.basePrice > 0) {
      setInputs(p => ({ ...p, wasMarkupPct: m, wasPrice: parseFloat((p.basePrice * (1 + m / 100)).toFixed(2)) }));
    } else {
      setInputs(p => ({ ...p, wasMarkupPct: m }));
    }
  };

  const syncMarkupFromWas = (was) => {
    const w = parseFloat(was) || 0;
    if (w > 0 && inputs.basePrice > 0) {
      setInputs(p => ({ ...p, wasPrice: w, wasMarkupPct: parseFloat((((w - p.basePrice) / p.basePrice) * 100).toFixed(1)) }));
    } else {
      setInputs(p => ({ ...p, wasPrice: w }));
    }
  };

  // Core calculations
  const calc = useMemo(() => {
    const { basePrice, wasPrice, tradeDiscount, creditBack, tierEnabled, thresholds, discounts, saleActive } = inputs;
    const hasWas = wasPrice > 0 && wasPrice > basePrice;
    const isSale = saleActive && hasWas;

    // Prices ex VAT for trade users
    const wasExVat = hasWas ? wasPrice / 1.2 : 0;
    const baseExVat = basePrice / 1.2;
    const tradePrice = baseExVat * (1 - tradeDiscount / 100);

    // Sale discount % (was → base)
    const saleDiscountPct = hasWas ? Math.round(((wasPrice - basePrice) / wasPrice) * 100) : 0;

    // Total savings from was → trade price (for trade users)
    const totalTradeOff = hasWas && wasExVat > 0 ? Math.round(((wasExVat - tradePrice) / wasExVat) * 100) : 0;

    // Guaranteed-sum breakdown
    const afterSale = hasWas ? wasExVat * (1 - saleDiscountPct / 100) : baseExVat;
    const afterTrade = afterSale * (1 - tradeDiscount / 100);
    const tradeContrib = wasExVat > 0 ? Math.round((afterSale - afterTrade) / wasExVat * 100) : 0;
    const saleContrib = Math.max(0, totalTradeOff - tradeContrib);

    // Collection card badge
    let badgeText = '';
    let badgePercent = 0;
    if (isSale && tradeDiscount > 0) {
      badgePercent = Math.round((1 - (1 - saleDiscountPct / 100) * (1 - tradeDiscount / 100)) * 100);
      badgeText = `Trade ${badgePercent}% OFF`;
    } else if (isSale) {
      badgePercent = saleDiscountPct;
      badgeText = `SALE ${badgePercent}% OFF`;
    } else if (tradeDiscount > 0) {
      badgePercent = tradeDiscount;
      badgeText = `Trade ${badgePercent}% OFF`;
    }

    // Non-sale badge for retail
    let retailBadgeText = '';
    if (isSale) {
      retailBadgeText = `SALE ${saleDiscountPct}% OFF`;
    }

    // Volume tiers
    const tiers = [];
    if (tierEnabled && thresholds.length > 0 && discounts.length > 0) {
      for (let i = 0; i < discounts.length; i++) {
        const qtyLabel = i === 0
          ? `0-${thresholds[0]}`
          : i < thresholds.length
            ? `${thresholds[i - 1]}-${thresholds[i]}`
            : `${thresholds[thresholds.length - 1]}+`;
        const disc = discounts[i];
        const tierTradePrice = tradePrice * (1 - disc / 100);
        const tierRetailPrice = baseExVat * (1 - disc / 100);
        const totalTierOff = hasWas && wasExVat > 0 ? Math.round(((wasExVat - tierTradePrice) / wasExVat) * 100) : 0;
        tiers.push({ qtyLabel, discount: disc, tradePrice: tierTradePrice, retailPrice: tierRetailPrice, totalOff: totalTierOff });
      }
    }

    // Ribbon save amounts (trade user)
    const tradeSaveAmount = hasWas ? (wasExVat - tradePrice).toFixed(2) : '0.00';
    // Ribbon save amounts (retail user)
    const retailSaveAmount = hasWas ? (wasExVat - baseExVat).toFixed(2) : '0.00';
    const retailSavePct = hasWas && wasExVat > 0 ? Math.round(((wasExVat - baseExVat) / wasExVat) * 100) : 0;

    return {
      hasWas, isSale, wasExVat, baseExVat, tradePrice,
      saleDiscountPct, totalTradeOff, saleContrib, tradeContrib,
      badgeText, badgePercent, retailBadgeText,
      tiers, tradeSaveAmount, retailSaveAmount, retailSavePct,
    };
  }, [inputs]);

  const unit = inputs.pricingUnit === 'unit' ? '/each' : '/m\u00B2';

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        data-testid="discount-calculator-toggle"
        className="w-full mt-3 bg-gradient-to-r from-slate-800 to-slate-700 border border-slate-600 rounded-lg p-3 flex items-center justify-between hover:from-slate-700 hover:to-slate-600 transition-all group"
      >
        <div className="flex items-center gap-2">
          <Calculator className="w-4 h-4 text-amber-400" />
          <span className="text-sm font-semibold text-white">Discount Calculator Preview</span>
        </div>
        <ChevronDown className="w-4 h-4 text-slate-400 group-hover:text-white transition-colors" />
      </button>
    );
  }

  return (
    <div className="mt-3 bg-gradient-to-br from-slate-900 to-slate-800 border border-slate-600 rounded-lg overflow-hidden" data-testid="discount-calculator-panel">
      {/* Header */}
      <button
        type="button"
        onClick={() => setExpanded(false)}
        className="w-full px-4 py-3 flex items-center justify-between bg-slate-800/50 border-b border-slate-700 hover:bg-slate-700/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Calculator className="w-4 h-4 text-amber-400" />
          <span className="text-sm font-bold text-white">Discount Calculator Preview</span>
          {selectedProduct && (
            <span className="text-xs text-slate-400 truncate max-w-[200px]">
              — {selectedProduct.product_name || selectedProduct.name}
            </span>
          )}
        </div>
        <ChevronUp className="w-4 h-4 text-slate-400" />
      </button>

      <div className="p-4 space-y-4">
        {/* Inputs Grid */}
        <div className="grid grid-cols-3 gap-3">
          <InputField label="Base Price (inc VAT)" value={inputs.basePrice} onChange={v => setInputs(p => ({ ...p, basePrice: parseFloat(v) || 0 }))} prefix="£" />
          <InputField label="WAS Price (inc VAT)" value={inputs.wasPrice} onChange={v => syncMarkupFromWas(v)} prefix="£" />
          <InputField label="WAS Markup %" value={inputs.wasMarkupPct} onChange={v => syncWasFromMarkup(v)} suffix="%" />
          <InputField label="Trade Discount" value={inputs.tradeDiscount} onChange={v => setInputs(p => ({ ...p, tradeDiscount: parseFloat(v) || 0 }))} suffix="%" />
          <InputField label="Credit Back" value={inputs.creditBack} onChange={v => setInputs(p => ({ ...p, creditBack: parseFloat(v) || 0 }))} suffix="%" />
          <div className="flex flex-col gap-1">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider">Options</span>
            <div className="flex flex-col gap-1.5 mt-0.5">
              <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
                <input type="checkbox" checked={inputs.saleActive} onChange={e => setInputs(p => ({ ...p, saleActive: e.target.checked }))} className="rounded border-slate-500 bg-slate-700 text-amber-500 focus:ring-amber-500" />
                Sale Active
              </label>
              <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
                <input type="checkbox" checked={inputs.tierEnabled} onChange={e => setInputs(p => ({ ...p, tierEnabled: e.target.checked }))} className="rounded border-slate-500 bg-slate-700 text-amber-500 focus:ring-amber-500" />
                Tier Pricing
              </label>
            </div>
          </div>
        </div>

        {/* Reset button */}
        {selectedProduct && (
          <button
            type="button"
            onClick={() => {
              const listPrice = selectedProduct.list_price || selectedProduct.price || 0;
              const wasMarkup = parseFloat(selectedProduct.was_markup_percent) || 0;
              let wasPrice = parseFloat(selectedProduct.was_price) || 0;
              if (!wasPrice && wasMarkup > 0 && listPrice > 0) wasPrice = parseFloat((listPrice * (1 + wasMarkup / 100)).toFixed(2));
              setInputs(p => ({
                ...p, basePrice: listPrice, wasPrice, wasMarkupPct: wasMarkup,
                tradeDiscount: parseFloat(selectedProduct.trade_discount) || parseFloat(tierPricingConfig?.trade_discount_default) || 0,
                creditBack: parseFloat(selectedProduct.credit_back_rate) || parseFloat(tierPricingConfig?.credit_back_default) || 0,
              }));
            }}
            className="text-xs text-amber-400 hover:text-amber-300 flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" /> Reset to product values
          </button>
        )}

        {/* ====== VISUAL PREVIEW ====== */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 mb-1">
            <Eye className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">Storefront Preview</span>
          </div>

          {/* --- Collection Card Badge --- */}
          <div className="bg-slate-800 rounded-lg p-3 border border-slate-700">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider block mb-2">Collection Card Badge</span>
            <div className="flex gap-3">
              {/* Trade user badge */}
              <div className="flex-1">
                <span className="text-[9px] text-blue-400 block mb-1">Trade Customer</span>
                {calc.badgeText ? (
                  <span className="inline-block px-2.5 py-1 bg-blue-600 text-white text-xs font-bold rounded" data-testid="calc-trade-badge">
                    {calc.badgeText}
                  </span>
                ) : (
                  <span className="text-xs text-slate-500 italic">No badge</span>
                )}
              </div>
              {/* Retail user badge */}
              <div className="flex-1">
                <span className="text-[9px] text-rose-400 block mb-1">Retail Customer</span>
                {calc.retailBadgeText ? (
                  <span className="inline-block px-2.5 py-1 bg-red-600 text-white text-xs font-bold rounded" data-testid="calc-retail-badge">
                    {calc.retailBadgeText}
                  </span>
                ) : (
                  <span className="text-xs text-slate-500 italic">No badge</span>
                )}
              </div>
            </div>
          </div>

          {/* --- Sale Ribbon (Trade) --- */}
          {calc.hasWas && (
            <div className="rounded-lg overflow-hidden border border-slate-700" data-testid="calc-sale-ribbon">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider block px-3 pt-2">Sale Ribbon (Trade Customer)</span>
              <div className="bg-gradient-to-r from-red-700 to-red-600 px-4 py-3 mt-1">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-white/60 text-xs">SALE PRICE</span>
                    <div className="flex items-baseline gap-3 mt-0.5">
                      <span className="text-white/50 text-sm line-through">WAS £{calc.wasExVat.toFixed(2)}</span>
                      <span className="text-white text-xl font-black">NOW £{calc.tradePrice.toFixed(2)}</span>
                      <span className="text-white/60 text-[10px]">ex. VAT{unit}</span>
                    </div>
                  </div>
                  <div className="bg-white/20 rounded-lg px-3 py-2 text-center">
                    <div className="text-white text-xs">SAVE</div>
                    <div className="text-yellow-300 text-lg font-black">£{calc.tradeSaveAmount}</div>
                    <div className="text-yellow-300 text-xs font-bold">{calc.totalTradeOff}% OFF</div>
                  </div>
                </div>
              </div>
              {/* Breakdown strip */}
              {(calc.saleContrib > 0 || calc.tradeContrib > 0 || inputs.creditBack > 0) && (
                <div className="bg-red-900/60 px-4 py-2 flex items-center gap-3 text-[11px] flex-wrap">
                  {calc.saleContrib > 0 && (
                    <span className="flex items-center gap-1 text-white/90 font-semibold"><span className="w-1.5 h-1.5 rounded-full bg-yellow-400" />Sale: {calc.saleContrib}%</span>
                  )}
                  {calc.tradeContrib > 0 && (
                    <><span className="text-white/30">|</span><span className="flex items-center gap-1 text-white/90 font-semibold"><span className="w-1.5 h-1.5 rounded-full bg-blue-400" />Trade: {calc.tradeContrib}%</span></>
                  )}
                  {(calc.saleContrib > 0 || calc.tradeContrib > 0) && (
                    <><span className="text-white/30">|</span><span className="flex items-center gap-1 text-white font-black"><span className="w-1.5 h-1.5 rounded-full bg-white" />Total: {calc.totalTradeOff}%</span></>
                  )}
                  {inputs.creditBack > 0 && (
                    <><span className="text-white/20 mx-0.5">&middot;</span><span className="text-green-300 italic font-semibold">+ Extra {inputs.creditBack}% Credit Back</span></>
                  )}
                </div>
              )}
            </div>
          )}

          {/* --- Sale Ribbon (Retail) --- */}
          {calc.hasWas && (
            <div className="rounded-lg overflow-hidden border border-slate-700">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider block px-3 pt-2">Sale Ribbon (Retail Customer)</span>
              <div className="bg-gradient-to-r from-red-600 to-red-500 px-4 py-3 mt-1">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-white/60 text-xs">SALE PRICE</span>
                    <div className="flex items-baseline gap-3 mt-0.5">
                      <span className="text-white/50 text-sm line-through">WAS £{calc.wasExVat.toFixed(2)}</span>
                      <span className="text-white text-xl font-black">NOW £{(inputs.basePrice / 1.2).toFixed(2)}</span>
                      <span className="text-white/60 text-[10px]">ex. VAT{unit}</span>
                    </div>
                  </div>
                  <div className="bg-white/20 rounded-lg px-3 py-2 text-center">
                    <div className="text-white text-xs">SAVE</div>
                    <div className="text-yellow-300 text-lg font-black">£{calc.retailSaveAmount}</div>
                    <div className="text-yellow-300 text-xs font-bold">{calc.retailSavePct}% OFF</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* --- Volume Pricing Table --- */}
          {inputs.tierEnabled && calc.tiers.length > 0 && (
            <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden" data-testid="calc-volume-table">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider block px-3 pt-2 pb-1">Volume Pricing Table (Trade)</span>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400">
                    <th className="px-3 py-1.5 text-left font-medium">Quantity</th>
                    <th className="px-3 py-1.5 text-right font-medium">Trade Price</th>
                    <th className="px-3 py-1.5 text-right font-medium">Retail Price</th>
                    <th className="px-3 py-1.5 text-right font-medium">Volume Disc.</th>
                    {calc.hasWas && <th className="px-3 py-1.5 text-right font-medium">Total Off</th>}
                  </tr>
                </thead>
                <tbody>
                  {calc.tiers.map((tier, i) => (
                    <tr key={i} className={`border-b border-slate-700/50 ${i === 0 ? 'bg-amber-900/20' : ''}`}>
                      <td className="px-3 py-1.5 text-slate-300 font-medium">{tier.qtyLabel}{inputs.pricingUnit === 'm2' ? 'm\u00B2' : ' units'}</td>
                      <td className="px-3 py-1.5 text-right text-blue-300 font-semibold">£{tier.tradePrice.toFixed(2)}</td>
                      <td className="px-3 py-1.5 text-right text-slate-300">£{tier.retailPrice.toFixed(2)}</td>
                      <td className="px-3 py-1.5 text-right">
                        {tier.discount > 0 ? (
                          <span className="text-amber-400 font-semibold">Extra {tier.discount}% off</span>
                        ) : (
                          <span className="text-slate-500">Base</span>
                        )}
                      </td>
                      {calc.hasWas && (
                        <td className="px-3 py-1.5 text-right text-emerald-400 font-semibold">{tier.totalOff}%</td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* No sale info */}
          {!calc.hasWas && !inputs.tierEnabled && (
            <div className="bg-slate-800 rounded-lg p-4 border border-slate-700 text-center">
              <span className="text-xs text-slate-400">Set a WAS price or enable tiers to see the full preview</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Small reusable input
const InputField = ({ label, value, onChange, prefix, suffix }) => (
  <div className="flex flex-col gap-1">
    <span className="text-[10px] text-slate-400 uppercase tracking-wider">{label}</span>
    <div className="relative">
      {prefix && <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-slate-500">{prefix}</span>}
      <input
        type="number"
        step="any"
        value={value || ''}
        onChange={e => onChange(e.target.value)}
        className={`w-full bg-slate-700 border border-slate-600 rounded px-2 py-1.5 text-xs text-white focus:ring-1 focus:ring-amber-500 focus:border-amber-500 ${prefix ? 'pl-5' : ''} ${suffix ? 'pr-5' : ''}`}
      />
      {suffix && <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-500">{suffix}</span>}
    </div>
  </div>
);

export default DiscountCalculatorPreview;
