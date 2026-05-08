import React, { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight, Users, Tag, Filter, Sliders, Eye, AlertTriangle } from 'lucide-react';
import { Badge } from '../../../../components/ui/badge';

const getProductKey = (p) => `${p.supplier || 'unknown'}|||${p.sku || p.supplier_code || p._id}`;

const ScopeSummaryPanel = ({
  perAttributeScopes = {},
  bulkCategorySelections = {},
  selectedProducts = new Set(),
  products = [],
  compact = false
}) => {
  const [expanded, setExpanded] = useState(!compact);
  const [expandedGroups, setExpandedGroups] = useState({});

  const totalProducts = selectedProducts.size;

  // Build a product key → name map for display
  const productNameMap = useMemo(() => {
    const map = {};
    const selectedKeys = Array.from(selectedProducts);
    products.forEach(p => {
      const key = getProductKey(p);
      if (selectedKeys.includes(key)) {
        map[key] = p.product_name || p.name || p.sku || p.supplier_code || key.split('|||')[1];
      }
    });
    return map;
  }, [products, selectedProducts]);

  // Parse all active selections and scopes into structured summary
  const summary = useMemo(() => {
    const categories = [];
    const filters = [];
    const specs = [];

    for (const [key, value] of Object.entries(bulkCategorySelections)) {
      if (!value || (Array.isArray(value) && value.length === 0)) continue;

      const scope = perAttributeScopes[key];
      const scopeSize = scope?.size || 0;
      const scopeKeys = scope ? Array.from(scope) : [];
      const isScoped = scopeSize > 0 && scopeSize < totalProducts;

      if (key.startsWith('cat_') && value === true) {
        const label = key.replace('cat_', '').replace(/-/g, ' ');
        categories.push({ key, label, isScoped, scopeSize, scopeKeys });
      } else if (key.startsWith('filter_') && !key.includes('__')) {
        const filterSlug = key.replace('filter_', '');
        const values = Array.isArray(value) ? value : [value];

        // Check for per-value scopes
        const perValueScopes = [];
        values.forEach(v => {
          const pvKey = `filter_${filterSlug}__${v}`;
          const pvScope = perAttributeScopes[pvKey];
          if (pvScope?.size > 0 && pvScope.size < totalProducts) {
            perValueScopes.push({
              value: v,
              scopeSize: pvScope.size,
              scopeKeys: Array.from(pvScope)
            });
          }
        });

        filters.push({
          key,
          label: filterSlug.replace(/-/g, ' '),
          values,
          isScoped,
          scopeSize,
          scopeKeys,
          perValueScopes
        });
      } else if (key.startsWith('spec_') && !key.includes('__')) {
        const specSlug = key.replace('spec_', '');
        const values = Array.isArray(value) ? value : [value];

        // Check for per-value scopes
        const perValueScopes = [];
        values.forEach(v => {
          const pvKey = `spec_${specSlug}__${v}`;
          const pvScope = perAttributeScopes[pvKey];
          if (pvScope?.size > 0 && pvScope.size < totalProducts) {
            perValueScopes.push({
              value: v,
              scopeSize: pvScope.size,
              scopeKeys: Array.from(pvScope)
            });
          }
        });

        specs.push({
          key,
          label: specSlug.replace(/_/g, ' '),
          values,
          isScoped,
          scopeSize,
          scopeKeys,
          perValueScopes
        });
      }
    }

    return { categories, filters, specs };
  }, [bulkCategorySelections, perAttributeScopes, totalProducts]);

  const hasAnyScopes = Object.values(perAttributeScopes).some(s => s?.size > 0);
  const totalAttributes = summary.categories.length + summary.filters.length + summary.specs.length;
  const scopedCount = [
    ...summary.categories.filter(c => c.isScoped),
    ...summary.filters.filter(f => f.isScoped || f.perValueScopes.length > 0),
    ...summary.specs.filter(s => s.isScoped || s.perValueScopes.length > 0)
  ].length;

  if (totalAttributes === 0) return null;

  const toggleGroup = (groupKey) => {
    setExpandedGroups(prev => ({ ...prev, [groupKey]: !prev[groupKey] }));
  };

  const titleCase = (s) => s.replace(/\b\w/g, c => c.toUpperCase());

  const renderProductList = (scopeKeys) => {
    if (!scopeKeys?.length) return null;
    return (
      <div className="ml-4 mt-1 space-y-0.5">
        {scopeKeys.slice(0, 5).map(k => (
          <div key={k} className="text-[10px] text-gray-500 flex items-center gap-1 truncate">
            <span className="w-1 h-1 rounded-full bg-amber-400 shrink-0" />
            <span className="truncate">{productNameMap[k] || k.split('|||')[1]}</span>
          </div>
        ))}
        {scopeKeys.length > 5 && (
          <span className="text-[10px] text-gray-400 ml-3">+{scopeKeys.length - 5} more</span>
        )}
      </div>
    );
  };

  const renderAttributeRow = (item, type) => {
    const hasPerValue = item.perValueScopes?.length > 0;
    const groupKey = `${type}_${item.key}`;
    const isExpanded = expandedGroups[groupKey];

    if (type === 'category') {
      return (
        <div key={item.key} className="py-1" data-testid={`scope-summary-item-${item.key}`}>
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-700 truncate flex-1">{titleCase(item.label)}</span>
            {item.isScoped ? (
              <button
                onClick={() => toggleGroup(groupKey)}
                className="flex items-center gap-1 text-xs shrink-0 ml-2"
              >
                <Badge className="bg-amber-100 text-amber-800 border border-amber-300 text-[10px] px-1.5 py-0">
                  {item.scopeSize}/{totalProducts}
                </Badge>
                {isExpanded ? <ChevronDown className="w-3 h-3 text-gray-400" /> : <ChevronRight className="w-3 h-3 text-gray-400" />}
              </button>
            ) : (
              <span className="text-[10px] text-emerald-600 font-medium shrink-0 ml-2">All {totalProducts}</span>
            )}
          </div>
          {isExpanded && item.isScoped && renderProductList(item.scopeKeys)}
        </div>
      );
    }

    // Filters and Specs with per-value scopes
    return (
      <div key={item.key} className="py-1" data-testid={`scope-summary-item-${item.key}`}>
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-700 truncate flex-1">{titleCase(item.label)}</span>
          {item.isScoped && !hasPerValue ? (
            <button
              onClick={() => toggleGroup(groupKey)}
              className="flex items-center gap-1 text-xs shrink-0 ml-2"
            >
              <Badge className="bg-amber-100 text-amber-800 border border-amber-300 text-[10px] px-1.5 py-0">
                {item.scopeSize}/{totalProducts}
              </Badge>
              {isExpanded ? <ChevronDown className="w-3 h-3 text-gray-400" /> : <ChevronRight className="w-3 h-3 text-gray-400" />}
            </button>
          ) : hasPerValue ? (
            <button
              onClick={() => toggleGroup(groupKey)}
              className="flex items-center gap-1 text-xs shrink-0 ml-2"
            >
              <Badge className="bg-blue-100 text-blue-800 border border-blue-300 text-[10px] px-1.5 py-0">
                {item.perValueScopes.length} scoped
              </Badge>
              {isExpanded ? <ChevronDown className="w-3 h-3 text-gray-400" /> : <ChevronRight className="w-3 h-3 text-gray-400" />}
            </button>
          ) : (
            <span className="text-[10px] text-emerald-600 font-medium shrink-0 ml-2">All {totalProducts}</span>
          )}
        </div>

        {/* Per-value breakdown */}
        {isExpanded && hasPerValue && (
          <div className="ml-3 mt-1 space-y-1 border-l-2 border-blue-200 pl-2">
            {item.values.map(v => {
              const pvScope = item.perValueScopes.find(pv => pv.value === v);
              const pvGroupKey = `${groupKey}__${v}`;
              const pvExpanded = expandedGroups[pvGroupKey];
              return (
                <div key={v}>
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-gray-600">{titleCase(String(v))}</span>
                    {pvScope ? (
                      <button
                        onClick={() => toggleGroup(pvGroupKey)}
                        className="flex items-center gap-1 shrink-0"
                      >
                        <Badge className="bg-amber-50 text-amber-700 border border-amber-200 text-[10px] px-1 py-0">
                          {pvScope.scopeSize}/{totalProducts}
                        </Badge>
                      </button>
                    ) : (
                      <span className="text-[10px] text-emerald-500">All</span>
                    )}
                  </div>
                  {pvExpanded && pvScope && renderProductList(pvScope.scopeKeys)}
                </div>
              );
            })}
          </div>
        )}

        {isExpanded && !hasPerValue && item.isScoped && renderProductList(item.scopeKeys)}
      </div>
    );
  };

  const SectionGroup = ({ title, icon: Icon, items, type, color }) => {
    if (items.length === 0) return null;
    const scopedItems = items.filter(i => i.isScoped || (i.perValueScopes?.length > 0));
    return (
      <div className="space-y-0.5">
        <div className="flex items-center gap-1.5 mb-1">
          <Icon className={`w-3.5 h-3.5 ${color}`} />
          <span className={`text-xs font-semibold ${color}`}>{title}</span>
          <span className="text-[10px] text-gray-400">{items.length} selected</span>
          {scopedItems.length > 0 && (
            <Badge className="bg-amber-100 text-amber-700 text-[10px] px-1 py-0 ml-auto">
              {scopedItems.length} scoped
            </Badge>
          )}
        </div>
        <div className="divide-y divide-gray-100">
          {items.map(item => renderAttributeRow(item, type))}
        </div>
      </div>
    );
  };

  return (
    <div
      className={`border rounded-lg overflow-hidden ${
        hasAnyScopes ? 'border-amber-300 bg-amber-50/50' : 'border-gray-200 bg-gray-50/50'
      }`}
      data-testid="scope-summary-panel"
    >
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className={`w-full flex items-center justify-between px-3 py-2 transition-colors ${
          hasAnyScopes ? 'hover:bg-amber-100/50' : 'hover:bg-gray-100'
        }`}
        data-testid="scope-summary-toggle"
      >
        <div className="flex items-center gap-2">
          {expanded ? <ChevronDown className="w-4 h-4 text-gray-500" /> : <ChevronRight className="w-4 h-4 text-gray-500" />}
          <Eye className={`w-4 h-4 ${hasAnyScopes ? 'text-amber-600' : 'text-gray-500'}`} />
          <span className="text-sm font-semibold text-gray-800">Scope Summary</span>
          <span className="text-xs text-gray-500">
            {totalAttributes} attribute{totalAttributes !== 1 ? 's' : ''}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {scopedCount > 0 && (
            <div className="flex items-center gap-1">
              <AlertTriangle className="w-3 h-3 text-amber-500" />
              <span className="text-xs font-medium text-amber-700">
                {scopedCount} partially applied
              </span>
            </div>
          )}
          {scopedCount === 0 && totalAttributes > 0 && (
            <span className="text-xs text-emerald-600 font-medium">All apply to {totalProducts} products</span>
          )}
        </div>
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-3 border-t border-gray-200/50">
          {totalAttributes === 0 ? (
            <p className="text-xs text-gray-400 py-2 text-center">No attributes selected yet</p>
          ) : (
            <>
              <SectionGroup
                title="Categories"
                icon={Tag}
                items={summary.categories}
                type="category"
                color="text-emerald-700"
              />
              <SectionGroup
                title="Filters"
                icon={Filter}
                items={summary.filters}
                type="filter"
                color="text-blue-700"
              />
              <SectionGroup
                title="Specifications"
                icon={Sliders}
                items={summary.specs}
                type="spec"
                color="text-purple-700"
              />
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default ScopeSummaryPanel;
