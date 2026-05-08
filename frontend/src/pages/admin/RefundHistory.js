import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { 
  RotateCcw, 
  Search, 
  Eye, 
  Trash2, 
  ArrowLeft,
  Calendar,
  TrendingDown,
  Receipt,
  Pencil,
  Mail
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { api } from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';

export const RefundHistory = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isSuperAdmin = user?.role === 'super_admin';
  const [refunds, setRefunds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [stats, setStats] = useState(null);
  const [selectedRefund, setSelectedRefund] = useState(null);
  const [showDetailDialog, setShowDetailDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [refundToDelete, setRefundToDelete] = useState(null);
  const [showEmailDialog, setShowEmailDialog] = useState(false);
  const [emailTo, setEmailTo] = useState('');
  const [sendingEmail, setSendingEmail] = useState(false);

  useEffect(() => {
    fetchData();
    
    // Listen for data sync events from other pages
    const handleDataSync = () => {
      console.log('[RefundHistory] Data sync event received');
      fetchData();
    };
    
    window.addEventListener('data-sync-event', handleDataSync);
    window.addEventListener('dataSync', handleDataSync);
    
    return () => {
      window.removeEventListener('data-sync-event', handleDataSync);
      window.removeEventListener('dataSync', handleDataSync);
    };
  }, []);

  const fetchData = async () => {
    try {
      const [refundsRes, statsRes] = await Promise.all([
        api.getRefunds(),
        api.getRefundStats({ period: 'month' })
      ]);
      setRefunds(refundsRes.data);
      setStats(statsRes.data);
    } catch (error) {
      toast.error('Failed to load refunds');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const filteredRefunds = refunds.filter(r =>
    (r.refund_no?.toLowerCase() || '').includes(searchTerm.toLowerCase()) ||
    (r.customer_name?.toLowerCase() || '').includes(searchTerm.toLowerCase()) ||
    (r.original_invoice_no?.toLowerCase() || '').includes(searchTerm.toLowerCase())
  );

  const handleViewRefund = (refund) => {
    setSelectedRefund(refund);
    setShowDetailDialog(true);
  };

  const handleDeleteClick = (refund) => {
    setRefundToDelete(refund);
    setShowDeleteDialog(true);
  };

  const handleDeleteConfirm = async () => {
    if (!refundToDelete) return;
    
    const deletedId = refundToDelete.id;
    
    try {
      await api.deleteRefund(deletedId);
      toast.success('Refund deleted');
      
      // Immediately update local state for instant UI feedback
      setRefunds(prev => prev.filter(r => r.id !== deletedId));
      
      setShowDeleteDialog(false);
      setRefundToDelete(null);
      
      // Dispatch data sync event to update other pages (Dashboard, InvoiceHistory)
      window.dispatchEvent(new CustomEvent('data-sync-event'));
      window.dispatchEvent(new CustomEvent('dataSync'));
      localStorage.setItem('dataSync', Date.now().toString());
      
      // Refetch for consistency (will also update stats)
      fetchData();
    } catch (error) {
      toast.error('Failed to delete refund');
    }
  };

  // Edit refund - navigate to refund page with edit mode
  const handleEditRefund = (refund) => {
    navigate('/admin/refund', { state: { editRefund: refund } });
  };

  // Email refund
  const handleEmailClick = (refund) => {
    setSelectedRefund(refund);
    setEmailTo(refund.customer_email || '');
    setShowEmailDialog(true);
  };

  const handleSendEmail = async () => {
    if (!emailTo || !selectedRefund) {
      toast.error('Please enter an email address');
      return;
    }

    setSendingEmail(true);
    try {
      await api.sendRefundEmail(selectedRefund.id, emailTo);
      toast.success('Refund sent via email');
      setShowEmailDialog(false);
      setEmailTo('');
    } catch (error) {
      console.error('Email error:', error);
      toast.error(error.response?.data?.detail || 'Failed to send email');
    } finally {
      setSendingEmail(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-8" data-testid="refund-history-page">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/admin/epos')}>
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to EPOS
          </Button>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <RotateCcw className="h-6 w-6 text-red-500" />
            Refund History
          </h1>
        </div>
        <Button onClick={() => navigate('/admin/refund')} className="bg-red-600 hover:bg-red-700">
          <RotateCcw className="h-4 w-4 mr-1" /> New Refund
        </Button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Total Refunds</p>
                  <p className="text-2xl font-bold">{stats.total_refunds}</p>
                </div>
                <Receipt className="h-8 w-8 text-red-500/20" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Gross Refunds</p>
                  <p className="text-2xl font-bold text-red-600">£{stats.total_gross_refunds?.toFixed(2)}</p>
                </div>
                <TrendingDown className="h-8 w-8 text-red-500/20" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Net Refunds</p>
                  <p className="text-2xl font-bold text-red-600">£{stats.total_net_refunds?.toFixed(2)}</p>
                </div>
                <TrendingDown className="h-8 w-8 text-red-500/20" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Restocking Fees</p>
                  <p className="text-2xl font-bold text-green-600">+£{stats.total_restocking_fees?.toFixed(2)}</p>
                </div>
                <Calendar className="h-8 w-8 text-green-500/20" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Search */}
      <Card>
        <CardContent className="py-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search by refund no, customer name, or invoice no..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
              data-testid="search-refund-input"
            />
          </div>
        </CardContent>
      </Card>

      {/* Refunds Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Receipt className="h-5 w-5" />
            Refunds ({filteredRefunds.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {filteredRefunds.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <RotateCcw className="h-12 w-12 mx-auto mb-4 opacity-20" />
              <p>No refunds found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-sm text-muted-foreground">
                    <th className="pb-3 font-medium">Refund No</th>
                    <th className="pb-3 font-medium">Date</th>
                    <th className="pb-3 font-medium">Original Invoice</th>
                    <th className="pb-3 font-medium">Customer</th>
                    <th className="pb-3 font-medium">Created By</th>
                    <th className="pb-3 font-medium">Method</th>
                    <th className="pb-3 font-medium">Store</th>
                    <th className="pb-3 font-medium text-right">Net Refund</th>
                    <th className="pb-3 font-medium text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRefunds.map((refund) => (
                    <tr 
                      key={refund.id} 
                      className="border-b hover:bg-muted/50 cursor-pointer"
                      onClick={() => handleViewRefund(refund)}
                    >
                      <td className="py-3">
                        <span className="font-mono font-medium text-red-600">
                          {refund.refund_no}
                        </span>
                      </td>
                      <td className="py-3 text-sm">{refund.date}</td>
                      <td className="py-3 text-sm font-mono">
                        {refund.original_invoice_no || '-'}
                      </td>
                      <td className="py-3">
                        <div>
                          <p className="font-medium">{refund.customer_name || '-'}</p>
                          {refund.customer_phone && (
                            <p className="text-xs text-muted-foreground">{refund.customer_phone}</p>
                          )}
                        </div>
                      </td>
                      <td className="py-3 text-sm">
                        {refund.staff_name || refund.processed_by || refund.created_by || '-'}
                      </td>
                      <td className="py-3 text-sm">{refund.refund_method || '-'}</td>
                      <td className="py-3 text-sm">{refund.showroom_name || '-'}</td>
                      <td className="py-3 text-right font-medium text-red-600">
                        £{(refund.net_refund || 0).toFixed(2)}
                      </td>
                      <td className="py-3">
                        <div className="flex justify-center gap-1" onClick={(e) => e.stopPropagation()}>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleViewRefund(refund)}
                            title="View"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEditRefund(refund)}
                            title="Edit"
                          >
                            <Pencil className="h-4 w-4 text-blue-500" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEmailClick(refund)}
                            title="Send Email"
                          >
                            <Mail className="h-4 w-4 text-green-500" />
                          </Button>
                          {isSuperAdmin && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteClick(refund)}
                            title="Delete (Super Admin only)"
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Refund Detail Dialog */}
      <Dialog open={showDetailDialog} onOpenChange={setShowDetailDialog}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <RotateCcw className="h-5 w-5" />
              Refund: {selectedRefund?.refund_no}
            </DialogTitle>
            <DialogDescription>
              {selectedRefund?.date} {selectedRefund?.time && `at ${selectedRefund.time}`}
            </DialogDescription>
          </DialogHeader>
          
          {selectedRefund && (
            <div className="space-y-6">
              {/* Customer Info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="font-medium mb-2">Customer Details</h4>
                  <div className="text-sm space-y-1 text-muted-foreground">
                    <p><strong>Name:</strong> {selectedRefund.customer_name || '-'}</p>
                    <p><strong>Phone:</strong> {selectedRefund.customer_phone || '-'}</p>
                    <p><strong>Email:</strong> {selectedRefund.customer_email || '-'}</p>
                  </div>
                </div>
                <div>
                  <h4 className="font-medium mb-2">Refund Info</h4>
                  <div className="text-sm space-y-1 text-muted-foreground">
                    <p><strong>Original Invoice:</strong> {selectedRefund.original_invoice_no || '-'}</p>
                    <p><strong>Method:</strong> {selectedRefund.refund_method || '-'}</p>
                    <p><strong>Type:</strong> {selectedRefund.refund_type || '-'}</p>
                    <p><strong>Store:</strong> {selectedRefund.showroom_name || '-'}</p>
                  </div>
                </div>
              </div>

              {/* Line Items */}
              <div>
                <h4 className="font-medium mb-2">Refunded Items</h4>
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted">
                      <tr>
                        <th className="px-3 py-2 text-left min-w-[200px]">Product</th>
                        <th className="px-3 py-2 text-right w-16">Qty</th>
                        <th className="px-3 py-2 text-right w-24">Price</th>
                        <th className="px-3 py-2 text-left w-32">Reason</th>
                        <th className="px-3 py-2 text-right w-24">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedRefund.line_items?.map((item, idx) => (
                        <tr key={idx} className="border-t">
                          <td className="px-3 py-2">
                            <p className="font-medium">{item.product_name}</p>
                            {item.sku && <p className="text-xs text-muted-foreground">{item.sku}</p>}
                          </td>
                          <td className="px-3 py-2 text-right">{item.quantity}</td>
                          <td className="px-3 py-2 text-right">£{(item.refund_price || 0).toFixed(2)}</td>
                          <td className="px-3 py-2 text-sm">{item.reason || '-'}</td>
                          <td className="px-3 py-2 text-right font-medium">£{(item.total || 0).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Totals */}
              <div className="flex justify-end">
                <div className="w-64 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Subtotal</span>
                    <span>£{(selectedRefund.subtotal || 0).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>VAT (20%)</span>
                    <span>£{(selectedRefund.vat || 0).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between font-medium">
                    <span>Gross Total</span>
                    <span>£{(selectedRefund.gross_total || 0).toFixed(2)}</span>
                  </div>
                  {selectedRefund.restocking_fee > 0 && (
                    <div className="flex justify-between text-orange-600">
                      <span>Restocking Fee</span>
                      <span>-£{(selectedRefund.restocking_fee || 0).toFixed(2)}</span>
                    </div>
                  )}
                  <div className="flex justify-between font-bold text-lg text-red-600 border-t pt-2">
                    <span>Net Refund</span>
                    <span>£{(selectedRefund.net_refund || 0).toFixed(2)}</span>
                  </div>
                </div>
              </div>

              {selectedRefund.notes && (
                <div className="p-3 bg-muted rounded-lg">
                  <p className="text-sm font-medium">Notes:</p>
                  <p className="text-sm text-muted-foreground">{selectedRefund.notes}</p>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Refund</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete refund {refundToDelete?.refund_no}? 
              This will reverse the stock adjustments.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDeleteConfirm}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Email Dialog */}
      <Dialog open={showEmailDialog} onOpenChange={setShowEmailDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5" />
              Send Refund via Email
            </DialogTitle>
            <DialogDescription>
              Send refund {selectedRefund?.refund_no} to the customer via email.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="text-sm font-medium">Email Address</label>
              <Input
                type="email"
                value={emailTo}
                onChange={(e) => setEmailTo(e.target.value)}
                placeholder="customer@example.com"
                className="mt-1"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEmailDialog(false)}>Cancel</Button>
            <Button onClick={handleSendEmail} disabled={sendingEmail}>
              {sendingEmail ? 'Sending...' : 'Send Email'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default RefundHistory;
