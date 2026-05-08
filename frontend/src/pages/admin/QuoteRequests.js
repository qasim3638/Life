import React, { useState, useEffect } from 'react';
import { 
  FileText, Search, Filter, RefreshCw, Eye, Check, X, Clock, 
  Send, Mail, Phone, Building2, MapPin, Package, ChevronDown,
  Trash2, Edit2, AlertCircle, CheckCircle, XCircle, Timer
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter
} from '../../components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const QuoteRequests = () => {
  const [quotes, setQuotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedQuote, setSelectedQuote] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showUpdateModal, setShowUpdateModal] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [updateForm, setUpdateForm] = useState({
    status: '',
    quote_price: '',
    quote_notes: '',
    valid_until: ''
  });

  useEffect(() => {
    fetchQuotes();
    fetchStats();
  }, [statusFilter]);

  const fetchQuotes = async () => {
    setLoading(true);
    try {
      const statusParam = statusFilter !== 'all' ? `?status=${statusFilter}` : '';
      const res = await fetch(`${API_URL}/api/shop/admin/quotes${statusParam}`);
      if (res.ok) {
        const data = await res.json();
        setQuotes(data.quotes);
      }
    } catch (e) {
      console.error('Error fetching quotes:', e);
      toast.error('Failed to load quotes');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/shop/admin/quotes/stats/summary`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (e) {
      console.error('Error fetching stats:', e);
    }
  };

  const openUpdateModal = (quote) => {
    setSelectedQuote(quote);
    setUpdateForm({
      status: quote.status,
      quote_price: quote.quote_price || '',
      quote_notes: quote.quote_notes || '',
      valid_until: quote.valid_until || ''
    });
    setShowUpdateModal(true);
  };

  const handleUpdateQuote = async () => {
    if (!selectedQuote) return;
    
    setUpdating(true);
    try {
      const res = await fetch(`${API_URL}/api/shop/admin/quotes/${selectedQuote.quote_ref}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: updateForm.status,
          quote_price: updateForm.quote_price ? parseFloat(updateForm.quote_price) : null,
          quote_notes: updateForm.quote_notes || null,
          valid_until: updateForm.valid_until || null
        })
      });
      
      if (res.ok) {
        toast.success(`Quote ${selectedQuote.quote_ref} updated`);
        setShowUpdateModal(false);
        fetchQuotes();
        fetchStats();
      } else {
        toast.error('Failed to update quote');
      }
    } catch (e) {
      console.error('Error updating quote:', e);
      toast.error('Failed to update quote');
    } finally {
      setUpdating(false);
    }
  };

  const handleDeleteQuote = async (quoteRef) => {
    if (!window.confirm(`Delete quote ${quoteRef}? This cannot be undone.`)) return;
    
    try {
      const res = await fetch(`${API_URL}/api/shop/admin/quotes/${quoteRef}`, {
        method: 'DELETE'
      });
      
      if (res.ok) {
        toast.success('Quote deleted');
        fetchQuotes();
        fetchStats();
      } else {
        toast.error('Failed to delete quote');
      }
    } catch (e) {
      console.error('Error deleting quote:', e);
      toast.error('Failed to delete quote');
    }
  };

  const getStatusBadge = (status) => {
    const badges = {
      pending: { bg: 'bg-yellow-100', text: 'text-yellow-800', icon: Clock },
      quoted: { bg: 'bg-blue-100', text: 'text-blue-800', icon: Send },
      accepted: { bg: 'bg-green-100', text: 'text-green-800', icon: CheckCircle },
      declined: { bg: 'bg-red-100', text: 'text-red-800', icon: XCircle },
      expired: { bg: 'bg-gray-100', text: 'text-gray-800', icon: Timer }
    };
    const badge = badges[status] || badges.pending;
    const Icon = badge.icon;
    
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${badge.bg} ${badge.text}`}>
        <Icon className="w-3 h-3" />
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  const filteredQuotes = quotes.filter(q => {
    if (!searchTerm) return true;
    const search = searchTerm.toLowerCase();
    return (
      q.quote_ref?.toLowerCase().includes(search) ||
      q.customer_name?.toLowerCase().includes(search) ||
      q.customer_email?.toLowerCase().includes(search) ||
      q.product_name?.toLowerCase().includes(search)
    );
  });

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-GB', { 
      day: '2-digit', 
      month: 'short', 
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <FileText className="w-7 h-7 text-amber-500" />
            Quote Requests
          </h1>
          <p className="text-gray-500 mt-1">Manage customer quote requests for large orders</p>
        </div>
        <Button onClick={() => { fetchQuotes(); fetchStats(); }} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <div className="bg-white rounded-lg border p-4">
            <div className="text-2xl font-bold text-gray-900">{stats.total_quotes}</div>
            <div className="text-sm text-gray-500">Total Quotes</div>
          </div>
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div className="text-2xl font-bold text-yellow-700">{stats.pending}</div>
            <div className="text-sm text-yellow-600">Pending</div>
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="text-2xl font-bold text-blue-700">{stats.quoted}</div>
            <div className="text-sm text-blue-600">Quoted</div>
          </div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="text-2xl font-bold text-green-700">{stats.accepted}</div>
            <div className="text-sm text-green-600">Accepted</div>
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <div className="text-2xl font-bold text-amber-700">£{stats.total_accepted_value?.toLocaleString()}</div>
            <div className="text-sm text-amber-600">Accepted Value</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-6">
        <div className="flex-1 min-w-[250px]">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <Input
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by reference, customer, product..."
              className="pl-10"
            />
          </div>
        </div>
        <div className="flex gap-2">
          {['all', 'pending', 'quoted', 'accepted', 'declined', 'expired'].map(status => (
            <Button
              key={status}
              variant={statusFilter === status ? 'default' : 'outline'}
              size="sm"
              onClick={() => setStatusFilter(status)}
              className={statusFilter === status ? 'bg-amber-500 hover:bg-amber-600' : ''}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </Button>
          ))}
        </div>
      </div>

      {/* Quotes Table */}
      <div className="bg-white rounded-lg border overflow-hidden">
        {loading ? (
          <div className="p-8 text-center">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto text-gray-400" />
            <p className="text-gray-500 mt-2">Loading quotes...</p>
          </div>
        ) : filteredQuotes.length === 0 ? (
          <div className="p-8 text-center">
            <FileText className="w-12 h-12 mx-auto text-gray-300 mb-3" />
            <p className="text-gray-500">No quote requests found</p>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Reference</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Customer</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Product</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Quantity</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Quote Price</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Date</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filteredQuotes.map(quote => (
                <tr key={quote.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <span className="font-mono font-semibold text-amber-600">{quote.quote_ref}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium text-gray-900">{quote.customer_name}</div>
                    <div className="text-xs text-gray-500">{quote.customer_email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-sm text-gray-900 max-w-[200px] truncate">{quote.product_name}</div>
                    {quote.product_sku && (
                      <div className="text-xs text-gray-500">SKU: {quote.product_sku}</div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-semibold text-gray-900">{quote.quantity}m²</span>
                  </td>
                  <td className="px-4 py-3">
                    {getStatusBadge(quote.status)}
                  </td>
                  <td className="px-4 py-3">
                    {quote.quote_price ? (
                      <span className="font-semibold text-green-600">£{quote.quote_price.toLocaleString()}</span>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {formatDate(quote.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => { setSelectedQuote(quote); setShowDetailModal(true); }}
                        title="View Details"
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openUpdateModal(quote)}
                        title="Update Status"
                      >
                        <Edit2 className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteQuote(quote.quote_ref)}
                        className="text-red-500 hover:text-red-700"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Quote Detail Modal */}
      <Dialog open={showDetailModal} onOpenChange={setShowDetailModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-amber-500" />
              Quote {selectedQuote?.quote_ref}
            </DialogTitle>
          </DialogHeader>

          {selectedQuote && (
            <div className="space-y-4">
              {/* Status */}
              <div className="flex items-center justify-between">
                {getStatusBadge(selectedQuote.status)}
                <span className="text-sm text-gray-500">{formatDate(selectedQuote.created_at)}</span>
              </div>

              {/* Product Info */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1">
                  <Package className="w-4 h-4" /> Product
                </h4>
                <p className="font-medium text-gray-900">{selectedQuote.product_name}</p>
                {selectedQuote.product_sku && (
                  <p className="text-sm text-gray-500">SKU: {selectedQuote.product_sku}</p>
                )}
                <p className="text-lg font-bold text-amber-600 mt-1">{selectedQuote.quantity}m² requested</p>
              </div>

              {/* Customer Info */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Customer Details</h4>
                <div className="space-y-2 text-sm">
                  <p className="flex items-center gap-2">
                    <span className="font-medium">{selectedQuote.customer_name}</span>
                  </p>
                  <p className="flex items-center gap-2 text-gray-600">
                    <Mail className="w-4 h-4" />
                    <a href={`mailto:${selectedQuote.customer_email}`} className="text-blue-600 hover:underline">
                      {selectedQuote.customer_email}
                    </a>
                  </p>
                  <p className="flex items-center gap-2 text-gray-600">
                    <Phone className="w-4 h-4" />
                    <a href={`tel:${selectedQuote.customer_phone}`} className="text-blue-600 hover:underline">
                      {selectedQuote.customer_phone}
                    </a>
                  </p>
                  {selectedQuote.customer_company && (
                    <p className="flex items-center gap-2 text-gray-600">
                      <Building2 className="w-4 h-4" />
                      {selectedQuote.customer_company}
                    </p>
                  )}
                  {selectedQuote.delivery_postcode && (
                    <p className="flex items-center gap-2 text-gray-600">
                      <MapPin className="w-4 h-4" />
                      {selectedQuote.delivery_postcode}
                    </p>
                  )}
                </div>
              </div>

              {/* Project Details */}
              {selectedQuote.project_details && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Project Details</h4>
                  <p className="text-sm text-gray-600">{selectedQuote.project_details}</p>
                </div>
              )}

              {/* Quote Price */}
              {selectedQuote.quote_price && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <h4 className="text-sm font-semibold text-green-700 mb-1">Quoted Price</h4>
                  <p className="text-2xl font-bold text-green-600">£{selectedQuote.quote_price.toLocaleString()}</p>
                  {selectedQuote.valid_until && (
                    <p className="text-xs text-green-600 mt-1">Valid until: {formatDate(selectedQuote.valid_until)}</p>
                  )}
                </div>
              )}

              {/* Quote Notes */}
              {selectedQuote.quote_notes && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h4 className="text-sm font-semibold text-blue-700 mb-1">Notes</h4>
                  <p className="text-sm text-blue-800">{selectedQuote.quote_notes}</p>
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDetailModal(false)}>
              Close
            </Button>
            <Button onClick={() => { setShowDetailModal(false); openUpdateModal(selectedQuote); }} className="bg-amber-500 hover:bg-amber-600">
              <Edit2 className="w-4 h-4 mr-2" />
              Update Status
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Update Quote Modal */}
      <Dialog open={showUpdateModal} onOpenChange={setShowUpdateModal}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Update Quote {selectedQuote?.quote_ref}</DialogTitle>
            <DialogDescription>
              Update the status and pricing details for this quote request.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div>
              <Label>Status</Label>
              <select
                value={updateForm.status}
                onChange={(e) => setUpdateForm(prev => ({ ...prev, status: e.target.value }))}
                className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="pending">Pending</option>
                <option value="quoted">Quoted</option>
                <option value="accepted">Accepted</option>
                <option value="declined">Declined</option>
                <option value="expired">Expired</option>
              </select>
            </div>

            <div>
              <Label>Quote Price (£)</Label>
              <Input
                type="number"
                min="0"
                step="0.01"
                value={updateForm.quote_price}
                onChange={(e) => setUpdateForm(prev => ({ ...prev, quote_price: e.target.value }))}
                placeholder="Enter quoted price"
                className="mt-1"
              />
            </div>

            <div>
              <Label>Valid Until</Label>
              <Input
                type="date"
                value={updateForm.valid_until?.split('T')[0] || ''}
                onChange={(e) => setUpdateForm(prev => ({ ...prev, valid_until: e.target.value }))}
                className="mt-1"
              />
            </div>

            <div>
              <Label>Notes</Label>
              <Textarea
                value={updateForm.quote_notes}
                onChange={(e) => setUpdateForm(prev => ({ ...prev, quote_notes: e.target.value }))}
                placeholder="Add internal notes or pricing details..."
                rows={3}
                className="mt-1"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowUpdateModal(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleUpdateQuote} 
              disabled={updating}
              className="bg-amber-500 hover:bg-amber-600"
            >
              {updating ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Updating...
                </>
              ) : (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  Update Quote
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default QuoteRequests;
