import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity, AlertTriangle, CheckCircle2, XCircle, ChevronDown,
  ChevronRight, RefreshCw, Package, Image, Tag, FileText,
  Hash, Copy, Link2Off, ArrowRight, Search, Filter,
  ExternalLink, ChevronUp
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ISSUE_META = {
  missing_sku:         { label: 'Missing SKU',          icon: Hash,        severity: 'high',   color: 'text-red-600',    bg: 'bg-red-50',      border: 'border-red-200' },
  missing_price:       { label: 'Missing Price',        icon: Tag,         severity: 'high',   color: 'text-red-600',    bg: 'bg-red-50',      border: 'border-red-200' },
  missing_images:      { label: 'Missing Images',       icon: Image,       severity: 'medium', color: 'text-amber-600',  bg: 'bg-amber-50',    border: 'border-amber-200' },
  missing_category:    { label: 'Missing Category',     icon: Package,     severity: 'medium', color: 'text-amber-600',  bg: 'bg-amber-50',    border: 'border-amber-200' },
  missing_name:        { label: 'Missing Name',         icon: FileText,    severity: 'high',   color: 'text-red-600',    bg: 'bg-red-50',      border: 'border-red-200' },
  missing_description: { label: 'Missing Description',  icon: FileText,    severity: 'low',    color: 'text-blue-600',   bg: 'bg-blue-50',     border: 'border-blue-200' },
  duplicate_codes:     { label: 'Duplicate Codes',      icon: Copy,        severity: 'high',   color: 'text-red-600',    bg: 'bg-red-50',      border: 'border-red-200' },
  duplicate_names:     { label: 'Duplicate Names',      icon: Copy,        severity: 'medium', color: 'text-amber-600',  bg: 'bg-amber-50',    border: 'border-amber-200' },
  not_synced:          { label: 'Not Synced to DB',     icon: Link2Off,    severity: 'low',    color: 'text-blue-600',   bg: 'bg-blue-50',     border: 'border-blue-200' },
};

const SEVERITY_ORDER = ['high', 'medium', 'low'];

/* ---------- Small Reusable Components ---------- */

const StatusBadge = ({ status, size = 'sm' }) => {
  const config = {
    healthy:  { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-300', icon: CheckCircle2, label: 'Healthy' },
    warning:  { bg: 'bg-amber-100',   text: 'text-amber-700',   border: 'border-amber-300',   icon: AlertTriangle, label: 'Warning' },
    critical: { bg: 'bg-red-100',     text: 'text-red-700',     border: 'border-red-300',     icon: XCircle,       label: 'Critical' },
  };
  const c = config[status] || config.healthy;
  const Icon = c.icon;
  const sizeClass = size === 'lg' ? 'px-3 py-1.5 text-sm' : 'px-2 py-0.5 text-xs';
  return (
    <span className={`inline-flex items-center gap-1.5 ${sizeClass} rounded-full font-semibold ${c.bg} ${c.text} border ${c.border}`}>
      <Icon className={size === 'lg' ? 'w-4 h-4' : 'w-3 h-3'} />
      {c.label}
    </span>
  );
};

const ScoreRing = ({ score, size = 64 }) => {
  const radius = (size - 6) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 80 ? '#059669' : score >= 50 ? '#d97706' : '#dc2626';
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="#e5e7eb" strokeWidth="4" />
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.6s ease' }} />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-bold text-gray-900" style={{ fontSize: size * 0.28 }}>{score}</span>
    </div>
  );
};

/* ---------- Product Table for an Issue ---------- */

const ProductIssueTable = ({ items, isDuplicate, issueKey, supplierName, navigate }) => {
  const [showAll, setShowAll] = useState(false);
  if (!items || items.length === 0) return null;

  const INITIAL_LIMIT = 15;
  const hasMore = !isDuplicate && items.length > INITIAL_LIMIT;
  const visibleItems = !isDuplicate && !showAll ? items.slice(0, INITIAL_LIMIT) : items;

  if (isDuplicate) {
    return (
      <div className="space-y-2">
        {items.map((dup, i) => (
          <div key={i} className="rounded-lg bg-gray-50 border border-gray-200 p-3">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="font-mono text-sm text-amber-700 font-semibold">{dup.code || dup.name}</span>
              <span className="text-xs text-gray-500 bg-gray-200 px-1.5 py-0.5 rounded">appears {dup.count}x</span>
            </div>
            {dup.products && (
              <div className="pl-3 space-y-1 border-l-2 border-gray-300">
                {dup.products.map((p, j) => (
                  <div key={j} className="text-xs text-gray-600 flex items-center gap-2">
                    <span className="text-gray-400">&bull;</span>
                    <span>{p.name || p.code}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div>
      <div className="rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm" data-testid={`issue-table-${issueKey}`}>
          <thead>
            <tr className="bg-gray-100">
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider w-8">#</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Code</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Product Name</th>
              <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider w-16"></th>
            </tr>
          </thead>
          <tbody>
            {visibleItems.map((item, i) => (
              <tr key={item.id || i} className="border-t border-gray-100 hover:bg-gray-50 transition-colors group">
                <td className="px-3 py-2 text-xs text-gray-400">{i + 1}</td>
                <td className="px-3 py-2">
                  <span className="font-mono text-xs text-gray-800 bg-gray-100 px-1.5 py-0.5 rounded font-medium">{item.code || 'N/A'}</span>
                </td>
                <td className="px-3 py-2 text-gray-700 text-xs">{item.name || '(unnamed)'}</td>
                <td className="px-3 py-2 text-right">
                  <button
                    onClick={() => navigate(`/admin/supplier-products?supplier=${encodeURIComponent(supplierName)}&search=${encodeURIComponent(item.code || item.name || '')}`)}
                    className="opacity-0 group-hover:opacity-100 inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-medium transition-all"
                    data-testid={`jump-to-product-${item.code || i}`}
                    title="Jump to this product"
                  >
                    <ExternalLink className="w-3 h-3" />
                    Fix
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hasMore && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="mt-2 text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1 font-medium transition-colors"
          data-testid={`show-more-${issueKey}`}
        >
          {showAll ? (
            <><ChevronUp className="w-3 h-3" /> Show less</>
          ) : (
            <><ChevronDown className="w-3 h-3" /> Show all {items.length} products</>
          )}
        </button>
      )}
    </div>
  );
};

/* ---------- Issue Section (one per issue type) ---------- */

const IssueSection = ({ issueKey, count, total, items, isDuplicate, supplierName, navigate }) => {
  const [expanded, setExpanded] = useState(false);
  const meta = ISSUE_META[issueKey];
  if (!meta || count === 0) return null;
  const Icon = meta.icon;
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;

  return (
    <div className={`rounded-xl border ${meta.border} ${meta.bg} overflow-hidden`} data-testid={`issue-section-${issueKey}`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-black/[0.03] transition-colors text-left"
        data-testid={`issue-toggle-${issueKey}`}
      >
        <Icon className={`w-4 h-4 flex-shrink-0 ${meta.color}`} />
        <span className={`text-sm font-semibold flex-1 ${meta.color}`}>{meta.label}</span>
        <span className={`text-sm font-mono font-bold ${meta.color}`}>
          {isDuplicate ? `${count} group${count > 1 ? 's' : ''}` : count}
        </span>
        {!isDuplicate && (
          <div className="w-20 h-1.5 bg-black/10 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${Math.max(pct, 3)}%`, backgroundColor: pct > 30 ? '#dc2626' : pct > 10 ? '#d97706' : '#059669' }}
            />
          </div>
        )}
        {!isDuplicate && <span className="text-xs text-gray-500 w-10 text-right font-medium">{pct}%</span>}
        {expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
      </button>
      {expanded && (
        <div className="px-4 pb-4 pt-1">
          <ProductIssueTable items={items} isDuplicate={isDuplicate} issueKey={issueKey} supplierName={supplierName} navigate={navigate} />
        </div>
      )}
    </div>
  );
};

/* ---------- Supplier Overview Card (sidebar) ---------- */

const SupplierOverviewCard = ({ data, isSelected, onSelect }) => {
  return (
    <button
      onClick={() => onSelect(data.supplier)}
      className={`w-full rounded-xl border p-3 text-left transition-all duration-200 ${
        isSelected ? 'border-blue-400 bg-blue-50 ring-2 ring-blue-200' :
        data.status === 'critical' ? 'border-red-200 bg-red-50/50 hover:bg-red-50' :
        data.status === 'warning' ? 'border-amber-200 bg-amber-50/50 hover:bg-amber-50' :
        'border-gray-200 bg-white hover:bg-gray-50'
      }`}
      data-testid={`supplier-overview-${data.supplier}`}
    >
      <div className="flex items-center gap-3">
        <ScoreRing score={data.health_score} size={44} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <h3 className="text-sm font-bold text-gray-900 truncate">{data.supplier}</h3>
            <StatusBadge status={data.status} />
          </div>
          <p className="text-xs text-gray-500">
            {data.total_products} products {data.total_issues > 0 && <>&middot; <span className={data.status === 'critical' ? 'text-red-600 font-medium' : 'text-amber-600 font-medium'}>{data.total_issues} issues</span></>}
          </p>
        </div>
        <ArrowRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
      </div>
    </button>
  );
};

/* ---------- Supplier Detail View ---------- */

const SupplierDetailView = ({ data, navigate }) => {
  const sortedIssues = useMemo(() => {
    return Object.entries(data.issue_counts)
      .filter(([, count]) => count > 0)
      .sort((a, b) => {
        const metaA = ISSUE_META[a[0]];
        const metaB = ISSUE_META[b[0]];
        const sevA = SEVERITY_ORDER.indexOf(metaA?.severity || 'low');
        const sevB = SEVERITY_ORDER.indexOf(metaB?.severity || 'low');
        if (sevA !== sevB) return sevA - sevB;
        return b[1] - a[1];
      });
  }, [data]);

  const noIssues = sortedIssues.length === 0;

  return (
    <div className="space-y-5" data-testid={`supplier-detail-${data.supplier}`}>
      {/* Supplier Header */}
      <div className="flex items-center gap-4 p-5 rounded-xl border border-gray-200 bg-white shadow-sm">
        <ScoreRing score={data.health_score} size={72} />
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-1">
            <h2 className="text-lg font-bold text-gray-900">{data.supplier}</h2>
            <StatusBadge status={data.status} size="lg" />
          </div>
          <div className="flex items-center gap-4 text-sm text-gray-500">
            <span>{data.total_products} products</span>
            <span className="text-gray-300">&middot;</span>
            <span className={data.total_issues > 0 ? (data.status === 'critical' ? 'text-red-600 font-medium' : 'text-amber-600 font-medium') : 'text-emerald-600 font-medium'}>
              {data.total_issues} issue{data.total_issues !== 1 ? 's' : ''}
            </span>
          </div>
        </div>
        <button
          onClick={() => navigate(`/admin/supplier-products?supplier=${encodeURIComponent(data.supplier)}`)}
          className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-gray-900 hover:bg-gray-800 text-white transition-colors"
          data-testid={`go-to-products-${data.supplier}`}
        >
          <ExternalLink className="w-4 h-4" />
          Manage Products
        </button>
      </div>

      {/* Issue Breakdown */}
      {noIssues ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-8 text-center">
          <CheckCircle2 className="w-10 h-10 text-emerald-600 mx-auto mb-3" />
          <p className="text-sm text-emerald-700 font-semibold">No issues found</p>
          <p className="text-xs text-gray-500 mt-1">All products for this supplier pass quality checks.</p>
        </div>
      ) : (
        <div className="space-y-3">
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider px-1">Issues by Type</h3>
          {sortedIssues.map(([key, count]) => (
            <IssueSection
              key={key}
              issueKey={key}
              count={count}
              total={data.total_products}
              items={data.issues[key]}
              isDuplicate={key === 'duplicate_codes' || key === 'duplicate_names'}
              supplierName={data.supplier}
              navigate={navigate}
            />
          ))}
        </div>
      )}
    </div>
  );
};

/* ---------- Main Dashboard ---------- */

export default function SupplierHealthDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedSupplier, setSelectedSupplier] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const navigate = useNavigate();

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/supplier-health/check`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (!res.ok) throw new Error('Failed to fetch health data');
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchHealth(); }, [fetchHealth]);

  const filteredSuppliers = useMemo(() => {
    if (!data) return [];
    let list = data.suppliers;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      list = list.filter(s => s.supplier.toLowerCase().includes(term));
    }
    if (statusFilter !== 'all') {
      list = list.filter(s => s.status === statusFilter);
    }
    return list;
  }, [data, searchTerm, statusFilter]);

  const selectedData = useMemo(() => {
    if (!selectedSupplier || !data) return null;
    return data.suppliers.find(s => s.supplier === selectedSupplier) || null;
  }, [selectedSupplier, data]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]" data-testid="health-loading">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
          <p className="text-sm text-gray-500">Scanning all suppliers...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]" data-testid="health-error">
        <div className="text-center space-y-3">
          <XCircle className="w-10 h-10 text-red-500 mx-auto" />
          <p className="text-sm text-gray-600">{error}</p>
          <button onClick={fetchHealth} className="text-sm text-blue-600 hover:underline font-medium">Retry</button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { summary } = data;

  return (
    <div className="space-y-5 max-w-6xl" data-testid="supplier-health-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-100 border border-emerald-200">
            <Activity className="w-5 h-5 text-emerald-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Supplier Health</h1>
            <p className="text-xs text-gray-500 mt-0.5">Data quality checks across all suppliers</p>
          </div>
        </div>
        <button
          onClick={() => { setSelectedSupplier(null); fetchHealth(); }}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 shadow-sm transition-colors"
          data-testid="refresh-health"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3" data-testid="health-summary">
        <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
          <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Avg Score</p>
          <p className={`text-2xl font-bold mt-1 ${
            summary.average_score >= 80 ? 'text-emerald-600' :
            summary.average_score >= 50 ? 'text-amber-600' : 'text-red-600'
          }`}>{summary.average_score}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
          <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Suppliers</p>
          <p className="text-2xl font-bold mt-1 text-gray-900">{summary.total_suppliers}</p>
        </div>
        <div className={`rounded-xl border p-3 shadow-sm cursor-pointer transition-colors ${statusFilter === 'healthy' ? 'border-emerald-400 bg-emerald-100 ring-2 ring-emerald-200' : 'border-emerald-200 bg-emerald-50 hover:bg-emerald-100'}`}
          onClick={() => { setStatusFilter(statusFilter === 'healthy' ? 'all' : 'healthy'); setSelectedSupplier(null); }}>
          <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Healthy</p>
          <p className="text-2xl font-bold mt-1 text-emerald-600">{summary.healthy}</p>
        </div>
        <div className={`rounded-xl border p-3 shadow-sm cursor-pointer transition-colors ${statusFilter === 'warning' ? 'border-amber-400 bg-amber-100 ring-2 ring-amber-200' : 'border-amber-200 bg-amber-50 hover:bg-amber-100'}`}
          onClick={() => { setStatusFilter(statusFilter === 'warning' ? 'all' : 'warning'); setSelectedSupplier(null); }}>
          <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Warning</p>
          <p className="text-2xl font-bold mt-1 text-amber-600">{summary.warning}</p>
        </div>
        <div className={`rounded-xl border p-3 shadow-sm cursor-pointer transition-colors ${statusFilter === 'critical' ? 'border-red-400 bg-red-100 ring-2 ring-red-200' : 'border-red-200 bg-red-50 hover:bg-red-100'}`}
          onClick={() => { setStatusFilter(statusFilter === 'critical' ? 'all' : 'critical'); setSelectedSupplier(null); }}>
          <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Critical</p>
          <p className="text-2xl font-bold mt-1 text-red-600">{summary.critical}</p>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex gap-5">
        {/* Left: Supplier List */}
        <div className="w-72 flex-shrink-0 space-y-3" data-testid="supplier-sidebar">
          {/* Search & Filter */}
          <div className="space-y-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search suppliers..."
                value={searchTerm}
                onChange={(e) => { setSearchTerm(e.target.value); setSelectedSupplier(null); }}
                className="w-full pl-9 pr-3 py-2 text-sm rounded-lg bg-white border border-gray-300 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 transition-colors"
                data-testid="supplier-search"
              />
            </div>
            {statusFilter !== 'all' && (
              <button
                onClick={() => setStatusFilter('all')}
                className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 font-medium transition-colors"
                data-testid="clear-filter"
              >
                <Filter className="w-3 h-3" />
                Showing: {statusFilter} — Clear filter
              </button>
            )}
          </div>

          {/* Supplier List */}
          <div className="space-y-2 max-h-[calc(100vh-360px)] overflow-y-auto pr-1" data-testid="supplier-list">
            {filteredSuppliers.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-sm text-gray-400">No suppliers match</p>
              </div>
            ) : (
              filteredSuppliers.map((s) => (
                <SupplierOverviewCard
                  key={s.supplier}
                  data={s}
                  isSelected={selectedSupplier === s.supplier}
                  onSelect={setSelectedSupplier}
                />
              ))
            )}
          </div>

          {/* Orphaned Products Warning */}
          {summary.null_supplier_products > 0 && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3">
              <p className="text-xs text-red-700 font-semibold">Orphaned Products</p>
              <p className="text-xs text-gray-600 mt-0.5">{summary.null_supplier_products} products have no supplier assigned</p>
            </div>
          )}
        </div>

        {/* Right: Detail Panel */}
        <div className="flex-1 min-w-0">
          {selectedData ? (
            <SupplierDetailView data={selectedData} navigate={navigate} />
          ) : (
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-10 text-center" data-testid="no-supplier-selected">
              <div className="max-w-sm mx-auto">
                <Filter className="w-10 h-10 text-gray-300 mx-auto mb-4" />
                <p className="text-sm text-gray-600 font-medium mb-1">Select a supplier</p>
                <p className="text-xs text-gray-400">
                  Click on a supplier from the list to view their detailed health report and see all affected products.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Timestamp */}
      <p className="text-xs text-gray-400 text-right">
        Last checked: {new Date(data.timestamp).toLocaleString()}
      </p>
    </div>
  );
}
