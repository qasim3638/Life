import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { 
  FileText, 
  Search, 
  Edit, 
  Eye,
  ArrowLeft,
  Building2,
  Plus,
  Printer,
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

// Get showroom prefix
const getStorePrefix = (showroomName) => {
  const prefixes = {
    'gravesend': 'GRV',
    'tonbridge': 'TNB',
    'chingford': 'CHG',
    'sydenham': 'SYD'
  };
  return prefixes[showroomName?.toLowerCase()] || showroomName?.substring(0, 3).toUpperCase() || 'INV';
};

export const ShowroomInvoiceHistory = () => {
  const { showroomSlug } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [showroom, setStore] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [viewDialogOpen, setViewDialogOpen] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Get showrooms to find current one
        const showroomsRes = await api.getStores();
        const foundStore = showroomsRes.data.find(
          s => s.name.toLowerCase().replace(/\s+/g, '-') === showroomSlug
        );
        
        if (!foundStore) {
          toast.error('Store not found');
          navigate('/admin');
          return;
        }
        
        // Check if staff user is trying to access a different showroom
        const isStaffOrManager = user?.role === 'staff' || user?.role === 'manager';
        const userStoreId = user?.showroom_id;
        
        if (isStaffOrManager && userStoreId && userStoreId !== foundStore.id) {
          const assignedStore = showroomsRes.data.find(s => s.id === userStoreId);
          const assignedName = assignedStore?.name || 'your assigned showroom';
          toast.error(`Access denied. You can only access ${assignedName}.`);
          
          if (assignedStore) {
            const assignedSlug = assignedStore.name.toLowerCase().replace(/\s+/g, '-');
            navigate(`/admin/showroom/${assignedSlug}/invoices`);
          } else {
            navigate('/admin');
          }
          return;
        }
        
        setStore(foundStore);
        
        // Get invoices for this showroom
        const invoicesRes = await api.getInvoices({ showroom_id: foundStore.id });
        setInvoices(invoicesRes.data || []);
        
      } catch (error) {
        toast.error('Failed to load data');
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, [showroomSlug, navigate, user?.role, user?.showroom_id]);

  const handleEdit = (invoice) => {
    navigate(`/admin/showroom/${showroomSlug}/epos`, { state: { editInvoice: invoice } });
  };

  const getStatusBadge = (invoice) => {
    const status = invoice.status || 'completed';
    const colors = {
      completed: 'bg-green-100 text-green-800',
      pending: 'bg-yellow-100 text-yellow-800',
      cancelled: 'bg-red-100 text-red-800'
    };
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || colors.completed}`}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  const filteredInvoices = invoices.filter(inv => {
    if (!searchTerm) return true;
    const search = searchTerm.toLowerCase();
    return (
      inv.invoice_no?.toLowerCase().includes(search) ||
      inv.customer_name?.toLowerCase().includes(search) ||
      inv.customer_phone?.includes(search)
    );
  });

  // Calculate totals for this showroom
  const totalRevenue = invoices.reduce((sum, inv) => sum + (inv.gross_total || 0), 0);
  const totalInvoices = invoices.length;
  const todayInvoices = invoices.filter(inv => inv.date === new Date().toLocaleDateString('en-GB')).length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate(`/admin/showroom/${showroomSlug}/epos`)}>
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to EPOS
          </Button>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Building2 className="h-6 w-6 text-primary" />
            {showroom?.name} - Invoice History
          </h1>
        </div>
        <Button onClick={() => navigate(`/admin/showroom/${showroomSlug}/epos`)}>
          <Plus className="h-4 w-4 mr-1" /> New Invoice
        </Button>
      </div>

      {/* Store Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-primary/10 rounded-full">
                <Building2 className="h-6 w-6 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Store</p>
                <p className="text-xl font-bold">{showroom?.name}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <p className="text-3xl font-bold text-primary">{totalInvoices}</p>
              <p className="text-sm text-muted-foreground">Total Invoices</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <p className="text-3xl font-bold text-green-600">{todayInvoices}</p>
              <p className="text-sm text-muted-foreground">Today&apos;s Invoices</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <p className="text-3xl font-bold text-blue-600">£{totalRevenue.toFixed(2)}</p>
              <p className="text-sm text-muted-foreground">Total Revenue</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <Card>
        <CardContent className="pt-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search by invoice number, customer name or phone..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
        </CardContent>
      </Card>

      {/* Invoices Table */}
      <Card>
        <CardContent className="pt-6">
          {filteredInvoices.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <FileText className="h-12 w-12 mx-auto mb-4 opacity-30" />
              <p className="text-lg font-medium">No invoices found</p>
              <p className="text-sm mt-1">
                {searchTerm ? 'Try a different search term' : `Create your first invoice for ${showroom?.name}`}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="text-left py-3 px-4 font-medium text-sm">Invoice No</th>
                    <th className="text-left py-3 px-4 font-medium text-sm">Date</th>
                    <th className="text-left py-3 px-4 font-medium text-sm">Customer</th>
                    <th className="text-left py-3 px-4 font-medium text-sm">Type</th>
                    <th className="text-left py-3 px-4 font-medium text-sm">Staff</th>
                    <th className="text-right py-3 px-4 font-medium text-sm">Total</th>
                    <th className="text-center py-3 px-4 font-medium text-sm">Status</th>
                    <th className="text-center py-3 px-4 font-medium text-sm">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredInvoices.map((invoice) => (
                    <tr key={invoice.id} className="border-b hover:bg-gray-50">
                      <td className="py-3 px-4">
                        <span className="font-mono text-sm font-medium text-primary">
                          {invoice.invoice_no}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-sm">{invoice.date} {invoice.time}</td>
                      <td className="py-3 px-4">
                        <div>
                          <p className="font-medium text-sm">{invoice.customer_name || '-'}</p>
                          <p className="text-xs text-gray-500">{invoice.customer_phone || ''}</p>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-sm">{invoice.order_type || '-'}</td>
                      <td className="py-3 px-4 text-sm">{invoice.staff_name || invoice.sales_person || '-'}</td>
                      <td className="py-3 px-4 text-right font-medium">
                        £{invoice.gross_total?.toFixed(2) || '0.00'}
                      </td>
                      <td className="py-3 px-4 text-center">
                        {getStatusBadge(invoice)}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center justify-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setSelectedInvoice(invoice);
                              setViewDialogOpen(true);
                            }}
                            title="View Details"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEdit(invoice)}
                            title="Edit"
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
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

      {/* View Invoice Dialog */}
      <Dialog open={viewDialogOpen} onOpenChange={setViewDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-primary" />
              Invoice: {selectedInvoice?.invoice_no}
            </DialogTitle>
          </DialogHeader>
          
          {selectedInvoice && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-gray-500">Date</p>
                  <p className="font-medium">{selectedInvoice.date} {selectedInvoice.time}</p>
                </div>
                <div>
                  <p className="text-gray-500">Order Type</p>
                  <p className="font-medium">{selectedInvoice.order_type || '-'}</p>
                </div>
                <div>
                  <p className="text-gray-500">Customer</p>
                  <p className="font-medium">{selectedInvoice.customer_name || '-'}</p>
                </div>
                <div>
                  <p className="text-gray-500">Phone</p>
                  <p className="font-medium">{selectedInvoice.customer_phone || '-'}</p>
                </div>
                <div>
                  <p className="text-gray-500">Payment Method</p>
                  <p className="font-medium">{selectedInvoice.payment_method || '-'}</p>
                </div>
                <div>
                  <p className="text-gray-500">Staff</p>
                  <p className="font-medium">{selectedInvoice.staff_name || selectedInvoice.sales_person || '-'}</p>
                </div>
              </div>

              <div className="border-t pt-4">
                <p className="font-medium mb-2">Line Items</p>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50">
                      <th className="text-left py-2 px-2 min-w-[200px]">Product</th>
                      <th className="text-center py-2 px-2 w-20">Qty</th>
                      <th className="text-right py-2 px-2 w-24">Price</th>
                      <th className="text-right py-2 px-2 w-24">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedInvoice.line_items?.map((item, idx) => (
                      <tr key={idx} className="border-b">
                        <td className="py-2 px-2">{item.product_name}</td>
                        <td className="py-2 px-2 text-center">{item.quantity}</td>
                        <td className="py-2 px-2 text-right">£{item.due_price?.toFixed(2) || item.price?.toFixed(2)}</td>
                        <td className="py-2 px-2 text-right">£{item.total?.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="border-t pt-4 flex justify-end">
                <div className="text-right space-y-1">
                  <p className="text-sm">Subtotal: £{selectedInvoice.subtotal?.toFixed(2)}</p>
                  <p className="text-sm">VAT (20%): £{selectedInvoice.vat?.toFixed(2)}</p>
                  <p className="text-lg font-bold text-primary">
                    Total: £{selectedInvoice.gross_total?.toFixed(2)}
                  </p>
                  {selectedInvoice.total_deposits > 0 && (
                    <>
                      <p className="text-sm text-green-600">Deposits: -£{selectedInvoice.total_deposits?.toFixed(2)}</p>
                      <p className="text-lg font-bold">
                        Outstanding: £{selectedInvoice.amount_outstanding?.toFixed(2)}
                      </p>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setViewDialogOpen(false)}>
              Close
            </Button>
            <Button variant="outline" onClick={() => {
              handleEdit(selectedInvoice);
              setViewDialogOpen(false);
            }}>
              <Edit className="h-4 w-4 mr-1" /> Edit
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ShowroomInvoiceHistory;
