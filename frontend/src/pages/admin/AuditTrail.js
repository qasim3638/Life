import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { 
  History, Search, Filter, ChevronDown, ChevronRight, 
  User, Package, FileText, ShoppingCart, Building2, 
  LogIn, DollarSign, X, Eye, ArrowRight, FileDown, ArrowRightLeft
} from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';

const ENTITY_ICONS = {
  invoice: FileText,
  product: Package,
  order: ShoppingCart,
  user: User,
  showroom: Building2,
  auth: LogIn,
  price: DollarSign,
};

// Moved outside component to fix ESLint react/no-unstable-nested-components
const EntityIcon = ({ type }) => {
  const Icon = ENTITY_ICONS[type] || History;
  return <Icon className="h-4 w-4" />;
};

const ACTION_COLORS = {
  CREATE: 'bg-emerald-100 text-emerald-800',
  UPDATE: 'bg-blue-100 text-blue-800',
  DELETE: 'bg-red-100 text-red-800',
  LOGIN: 'bg-purple-100 text-purple-800',
  LOGOUT: 'bg-gray-100 text-gray-800',
  STATUS_CHANGE: 'bg-amber-100 text-amber-800',
};

const ENTITY_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'invoice', label: 'Invoices' },
  { value: 'product', label: 'Products' },
  { value: 'order', label: 'Orders' },
  { value: 'user', label: 'Users' },
  { value: 'store', label: 'Stores' },
  { value: 'auth', label: 'Authentication' },
  { value: 'price', label: 'Pricing' },
];

const ACTIONS = [
  { value: '', label: 'All Actions' },
  { value: 'CREATE', label: 'Create' },
  { value: 'UPDATE', label: 'Update' },
  { value: 'DELETE', label: 'Delete' },
  { value: 'LOGIN', label: 'Login' },
  { value: 'STATUS_CHANGE', label: 'Status Change' },
  { value: 'TRANSFER', label: 'Transfer' },
];

// Valid tabs for AuditTrail
const VALID_TABS = ['all', 'transfers'];

export const AuditTrail = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Get initial tab from URL
  const getInitialTab = useCallback(() => {
    const urlTab = searchParams.get('tab');
    if (urlTab && VALID_TABS.includes(urlTab)) {
      return urlTab;
    }
    return 'all';
  }, [searchParams]);

  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [activeTab, setActiveTab] = useState(getInitialTab);
  
  // Handle tab change with URL update
  const handleTabChange = useCallback((newTab) => {
    setActiveTab(newTab);
    setSearchParams({ tab: newTab }, { replace: true });
    setPagination(prev => ({ ...prev, skip: 0 }));
  }, [setSearchParams]);

  // Sync tab with URL on mount
  useEffect(() => {
    const urlTab = searchParams.get('tab');
    if (!urlTab) {
      setSearchParams({ tab: activeTab }, { replace: true });
    }
  }, [searchParams, activeTab, setSearchParams]);

  const [filters, setFilters] = useState({
    entity_type: '',
    action: '',
    user_email: '',
  });
  const [selectedLog, setSelectedLog] = useState(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [pagination, setPagination] = useState({ skip: 0, limit: 50, total: 0 });

  useEffect(() => {
    fetchLogs();
    fetchStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, pagination.skip, activeTab]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params = {
        ...filters,
        skip: pagination.skip,
        limit: pagination.limit,
      };
      
      // If on transfers tab, filter for TRANSFER action on invoices
      if (activeTab === 'transfers') {
        params.entity_type = 'invoice';
        params.action = 'TRANSFER';
      }
      // Remove empty filters
      Object.keys(params).forEach(key => {
        if (params[key] === '') delete params[key];
      });
      
      const response = await api.getAuditLogs(params);
      setLogs(response.data.logs);
      setPagination(prev => ({ ...prev, total: response.data.total }));
    } catch (error) {
      toast.error('Failed to load audit logs');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await api.getAuditStats();
      setStats(response.data);
    } catch (error) {
      console.error('Failed to load audit stats', error);
    }
  };

  const handleViewDetail = async (log) => {
    try {
      const response = await api.getAuditLogDetail(log.id);
      setSelectedLog(response.data);
      setDetailModalOpen(true);
    } catch (error) {
      toast.error('Failed to load log details');
    }
  };

  const handleExportCsv = async () => {
    setExporting(true);
    try {
      const params = { ...filters };
      // Remove empty filters
      Object.keys(params).forEach(key => {
        if (params[key] === '') delete params[key];
      });
      
      const response = await api.exportAuditLogsCsv(params);
      const blob = new Blob([response.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_logs_export_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success('Audit logs exported successfully!');
    } catch (error) {
      toast.error('Failed to export audit logs');
      console.error(error);
    } finally {
      setExporting(false);
    }
  };

  const formatDate = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const renderValue = (value) => {
    if (value === null || value === undefined) return <span className="text-muted-foreground italic">null</span>;
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    if (typeof value === 'object') return JSON.stringify(value, null, 2);
    return String(value);
  };

  return (
    <div className="space-y-6" data-testid="audit-trail-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-tightest mb-2">Audit Trail</h1>
          <p className="text-muted-foreground">Track all system changes with detailed before/after values</p>
        </div>
        <Button 
          variant="outline" 
          onClick={handleExportCsv}
          disabled={exporting}
          data-testid="export-audit-logs-btn"
        >
          <FileDown className="mr-2 h-4 w-4" />
          {exporting ? 'Exporting...' : 'Export CSV'}
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b">
        <button
          onClick={() => handleTabChange('all')}
          className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'all'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          data-testid="all-logs-tab"
        >
          <History className="h-4 w-4 inline mr-2" />
          All Activity
        </button>
        <button
          onClick={() => handleTabChange('transfers')}
          className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'transfers'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          data-testid="transfer-history-tab"
        >
          <ArrowRightLeft className="h-4 w-4 inline mr-2" />
          Transfer History
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Card className="p-4">
            <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">Total Logs</p>
            <p className="text-2xl font-heading font-bold">{stats.total_logs?.toLocaleString() || 0}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">Last 24 Hours</p>
            <p className="text-2xl font-heading font-bold">{stats.recent_activity || 0}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">Top Entity</p>
            <p className="text-2xl font-heading font-bold capitalize">
              {Object.entries(stats.by_entity_type || {}).sort((a, b) => b[1] - a[1])[0]?.[0] || '-'}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">Top Action</p>
            <p className="text-2xl font-heading font-bold capitalize">
              {Object.entries(stats.by_action || {}).sort((a, b) => b[1] - a[1])[0]?.[0] || '-'}
            </p>
          </Card>
        </div>
      )}

      {/* Transfer History Header (only show on transfers tab) */}
      {activeTab === 'transfers' && (
        <Card className="p-4 bg-indigo-50 border-indigo-200">
          <div className="flex items-center gap-3">
            <ArrowRightLeft className="h-6 w-6 text-indigo-600" />
            <div>
              <h3 className="font-semibold text-indigo-800">Invoice Transfer History</h3>
              <p className="text-sm text-indigo-600">
                Track all invoice and revenue transfers between showrooms. Only Super Admins can perform transfers.
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Filters (hide on transfers tab) */}
      {activeTab === 'all' && (
        <Card className="p-4">
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex-1 min-w-[200px]">
              <label className="text-sm font-medium mb-1 block">Search User</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by email..."
                  value={filters.user_email}
                  onChange={(e) => setFilters(prev => ({ ...prev, user_email: e.target.value }))}
                  className="pl-9"
                />
              </div>
            </div>
            
            <div className="w-40">
              <label className="text-sm font-medium mb-1 block">Entity Type</label>
              <select
                value={filters.entity_type}
                onChange={(e) => setFilters(prev => ({ ...prev, entity_type: e.target.value }))}
                className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm"
              >
                {ENTITY_TYPES.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            
            <div className="w-40">
              <label className="text-sm font-medium mb-1 block">Action</label>
              <select
                value={filters.action}
                onChange={(e) => setFilters(prev => ({ ...prev, action: e.target.value }))}
                className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm"
              >
                {ACTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            
            <Button 
              variant="outline" 
              onClick={() => setFilters({ entity_type: '', action: '', user_email: '' })}
            >
              Clear Filters
            </Button>
          </div>
        </Card>
      )}

      {/* Logs Table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-semibold">Timestamp</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">User</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">Action</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">Entity</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">Details</th>
                <th className="px-4 py-3 text-center text-sm font-semibold">View</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    Loading...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    No audit logs found
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-muted/50">
                    <td className="px-4 py-3 text-sm font-mono">
                      {formatDate(log.timestamp)}
                    </td>
                    <td className="px-4 py-3">
                      <div>
                        <p className="text-sm font-medium">{log.user_name || log.user_email}</p>
                        <p className="text-xs text-muted-foreground">{log.user_role}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${ACTION_COLORS[log.action] || 'bg-gray-100'}`}>
                        {log.action}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <EntityIcon type={log.entity_type} />
                        <div>
                          <p className="text-sm font-medium capitalize">{log.entity_type}</p>
                          <p className="text-xs text-muted-foreground truncate max-w-[150px]" title={log.entity_name}>
                            {log.entity_name || '-'}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-muted-foreground truncate max-w-[250px]" title={log.details}>
                        {log.details || '-'}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleViewDetail(log)}
                        data-testid={`view-log-${log.id}`}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        
        {/* Pagination */}
        {pagination.total > pagination.limit && (
          <div className="flex items-center justify-between px-4 py-3 border-t">
            <p className="text-sm text-muted-foreground">
              Showing {pagination.skip + 1} - {Math.min(pagination.skip + pagination.limit, pagination.total)} of {pagination.total}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={pagination.skip === 0}
                onClick={() => setPagination(prev => ({ ...prev, skip: Math.max(0, prev.skip - prev.limit) }))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={pagination.skip + pagination.limit >= pagination.total}
                onClick={() => setPagination(prev => ({ ...prev, skip: prev.skip + prev.limit }))}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Detail Modal */}
      <Dialog open={detailModalOpen} onOpenChange={setDetailModalOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <History className="h-5 w-5" />
              Audit Log Detail
            </DialogTitle>
          </DialogHeader>
          
          {selectedLog && (
            <div className="space-y-6">
              {/* Summary */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">Timestamp</p>
                  <p className="font-medium">{formatDate(selectedLog.timestamp)}</p>
                </div>
                <div>
                  <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">User</p>
                  <p className="font-medium">{selectedLog.user_name || selectedLog.user_email}</p>
                  <p className="text-xs text-muted-foreground">{selectedLog.user_role}</p>
                </div>
                <div>
                  <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">Action</p>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${ACTION_COLORS[selectedLog.action] || 'bg-gray-100'}`}>
                    {selectedLog.action}
                  </span>
                </div>
                <div>
                  <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">Entity</p>
                  <p className="font-medium capitalize">{selectedLog.entity_type}</p>
                  <p className="text-xs text-muted-foreground">{selectedLog.entity_name}</p>
                </div>
              </div>

              {selectedLog.details && (
                <div>
                  <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">Details</p>
                  <p className="text-sm">{selectedLog.details}</p>
                </div>
              )}

              {/* Changes (Before/After) */}
              {selectedLog.changes && selectedLog.changes.length > 0 && (
                <div>
                  <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-3">Changes</p>
                  <div className="space-y-2">
                    {selectedLog.changes.map((change, idx) => (
                      <div key={idx} className="p-3 bg-muted rounded-md">
                        <p className="text-sm font-semibold capitalize mb-2">{change.field.replace(/_/g, ' ')}</p>
                        <div className="flex items-center gap-3 text-sm">
                          <div className="flex-1 p-2 bg-red-50 rounded border border-red-200">
                            <p className="text-xs text-red-600 mb-1">Before</p>
                            <code className="text-xs break-all">{renderValue(change.old_value)}</code>
                          </div>
                          <ArrowRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                          <div className="flex-1 p-2 bg-emerald-50 rounded border border-emerald-200">
                            <p className="text-xs text-emerald-600 mb-1">After</p>
                            <code className="text-xs break-all">{renderValue(change.new_value)}</code>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Full Before/After Data */}
              {(selectedLog.before_data || selectedLog.after_data) && !selectedLog.changes?.length && (
                <div className="grid grid-cols-2 gap-4">
                  {selectedLog.before_data && (
                    <div>
                      <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-2">Before</p>
                      <pre className="p-3 bg-red-50 rounded border border-red-200 text-xs overflow-auto max-h-48">
                        {JSON.stringify(selectedLog.before_data, null, 2)}
                      </pre>
                    </div>
                  )}
                  {selectedLog.after_data && (
                    <div>
                      <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-2">After</p>
                      <pre className="p-3 bg-emerald-50 rounded border border-emerald-200 text-xs overflow-auto max-h-48">
                        {JSON.stringify(selectedLog.after_data, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}

              {selectedLog.showroom_name && (
                <div>
                  <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">Store</p>
                  <p className="text-sm">{selectedLog.showroom_name}</p>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AuditTrail;
