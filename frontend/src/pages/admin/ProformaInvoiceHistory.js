import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { 
  FileBadge, 
  Search, 
  Edit, 
  Trash2, 
  Eye,
  ArrowLeft,
  Filter,
  CheckCircle,
  Clock,
  XCircle,
  RotateCcw,
  Download,
  Mail,
  FileText
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
import { useAuth } from '../../contexts/AuthContext';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Bank Details
const BANK_DETAILS = {
  name: 'TILE STATION LTD',
  accountType: 'Business',
  accountNumber: '33604637',
  sortCode: '23-05-80'
};

const toTitleCase = (str) => {
  if (!str) return '';
  return str.replace(/\b\w/g, char => char.toUpperCase());
};

export const ProformaInvoiceHistory = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isSuperAdmin = user?.role === 'super_admin';
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [invoiceToDelete, setInvoiceToDelete] = useState(null);
  const [viewDialogOpen, setViewDialogOpen] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);

  useEffect(() => {
    fetchInvoices();
    
    const handleDataSync = () => {
      console.log('[ProformaInvoiceHistory] Data sync event received');
      fetchInvoices();
    };
    
    window.addEventListener('data-sync-event', handleDataSync);
    window.addEventListener('dataSync', handleDataSync);
    
    return () => {
      window.removeEventListener('data-sync-event', handleDataSync);
      window.removeEventListener('dataSync', handleDataSync);
    };
  }, []);

  const fetchInvoices = async () => {
    try {
      const response = await fetch(`${API_URL}/api/proforma-invoices`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      if (!response.ok) throw new Error('Failed to fetch');
      const data = await response.json();
      setInvoices(data.data || []);
    } catch (error) {
      console.error('Failed to load proforma invoices:', error);
      toast.error('Failed to load proforma invoices');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (invoice) => {
    navigate('/admin/epos?tab=proforma-invoice', { state: { editInvoice: invoice } });
  };

  const handleConvertToInvoice = async (invoice) => {
    try {
      // Prepare data for conversion to regular invoice
      const invoiceData = {
        customerName: invoice.customer_name,
        customerPhone: invoice.customer_phone,
        customerEmail: invoice.customer_email,
        customerAddress: invoice.customer_address,
        notes: `Converted from Proforma Invoice ${invoice.proforma_no}`,
        showroom_id: invoice.showroom_id,
        showroom_name: invoice.showroom_name,
        lineItems: invoice.line_items?.map(item => ({
          productId: item.product_id,
          product: item.product_name,
          sku: item.sku || '',
          qty: item.quantity?.toString() || '1',
          m2: item.m2?.toString() || '0',
          price: item.price?.toString() || '0',
          duePrice: item.due_price?.toString() || item.price?.toString() || '0',
          discount: item.discount || '0'
        })),
        fromProforma: invoice.proforma_no
      };
      
      // Mark proforma as converted
      await fetch(`${API_URL}/api/proforma-invoices/${invoice.id}/convert`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      // Navigate to invoice creation with the data
      navigate('/admin/invoice', { state: { convertFromProforma: invoiceData } });
      toast.info(`Creating invoice from Proforma ${invoice.proforma_no}`);
    } catch (error) {
      console.error('Error converting:', error);
      toast.error('Failed to convert proforma invoice');
    }
  };

  const handleView = (invoice) => {
    setSelectedInvoice(invoice);
    setViewDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!invoiceToDelete) return;
    
    try {
      const response = await fetch(`${API_URL}/api/proforma-invoices/${invoiceToDelete.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      if (!response.ok) throw new Error('Failed to delete');
      
      toast.success('Proforma invoice deleted');
      fetchInvoices();
    } catch (error) {
      toast.error('Failed to delete proforma invoice');
    } finally {
      setDeleteDialogOpen(false);
      setInvoiceToDelete(null);
    }
  };

  const handleRestore = async (invoice) => {
    try {
      const response = await fetch(`${API_URL}/api/proforma-invoices/${invoice.id}/restore`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      if (!response.ok) throw new Error('Failed to restore');
      
      toast.success('Proforma invoice restored');
      fetchInvoices();
    } catch (error) {
      toast.error('Failed to restore proforma invoice');
    }
  };

  const handleDownloadPdf = async (invoice) => {
    try {
      const response = await fetch(`${API_URL}/api/proforma-invoices/${invoice.id}/pdf`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) throw new Error('Failed to download PDF');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ProformaInvoice_${invoice.proforma_no}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      toast.success('PDF downloaded!');
    } catch (error) {
      console.error('Error downloading PDF:', error);
      toast.error('Failed to download PDF');
    }
  };

  const filteredInvoices = invoices.filter(invoice => {
    const matchesSearch = 
      invoice.proforma_no?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      invoice.customer_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      invoice.customer_phone?.includes(searchTerm);
    
    const matchesStatus = statusFilter === 'all' || invoice.status === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'active':
        return <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800 flex items-center gap-1"><CheckCircle className="h-3 w-3" /> Active</span>;
      case 'converted':
        return <span className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-800 flex items-center gap-1"><FileText className="h-3 w-3" /> Converted</span>;
      case 'expired':
        return <span className="px-2 py-1 text-xs rounded-full bg-yellow-100 text-yellow-800 flex items-center gap-1"><Clock className="h-3 w-3" /> Expired</span>;
      case 'deleted':
        return <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-800 flex items-center gap-1"><XCircle className="h-3 w-3" /> Deleted</span>;
      default:
        return <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-800">{status}</span>;
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
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => navigate('/admin/epos?tab=proforma-invoice')}>
            <ArrowLeft className="h-4 w-4 mr-1" /> New Proforma
          </Button>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileBadge className="h-6 w-6 text-blue-600" />
            Proforma Invoice History
          </h1>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search by invoice no, customer name or phone..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border rounded-md"
            >
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="converted">Converted</option>
              <option value="expired">Expired</option>
              {isSuperAdmin && <option value="deleted">Deleted</option>}
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Invoice List */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left p-4 font-medium">Proforma No</th>
                  <th className="text-left p-4 font-medium">Date</th>
                  <th className="text-left p-4 font-medium">Customer</th>
                  <th className="text-left p-4 font-medium">Phone</th>
                  <th className="text-right p-4 font-medium">Total (inc VAT)</th>
                  <th className="text-center p-4 font-medium">Status</th>
                  <th className="text-right p-4 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredInvoices.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="text-center p-8 text-gray-500">
                      No proforma invoices found
                    </td>
                  </tr>
                ) : (
                  filteredInvoices.map((invoice) => (
                    <tr key={invoice.id} className="border-b hover:bg-gray-50">
                      <td className="p-4 font-mono">{invoice.proforma_no}</td>
                      <td className="p-4">{invoice.date}</td>
                      <td className="p-4">{toTitleCase(invoice.customer_name) || '-'}</td>
                      <td className="p-4">{invoice.customer_phone || '-'}</td>
                      <td className="p-4 text-right font-medium">£{(invoice.gross_total || invoice.subtotal || 0).toFixed(2)}</td>
                      <td className="p-4 text-center">{getStatusBadge(invoice.status)}</td>
                      <td className="p-4">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="sm" onClick={() => handleView(invoice)} title="View">
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDownloadPdf(invoice)} title="Download PDF">
                            <Download className="h-4 w-4" />
                          </Button>
                          {invoice.status === 'active' && (
                            <>
                              <Button variant="ghost" size="sm" onClick={() => handleEdit(invoice)} title="Edit">
                                <Edit className="h-4 w-4" />
                              </Button>
                              <Button variant="ghost" size="sm" onClick={() => handleConvertToInvoice(invoice)} title="Convert to Invoice">
                                <FileText className="h-4 w-4 text-blue-600" />
                              </Button>
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                onClick={() => { setInvoiceToDelete(invoice); setDeleteDialogOpen(true); }}
                                title="Delete"
                              >
                                <Trash2 className="h-4 w-4 text-red-500" />
                              </Button>
                            </>
                          )}
                          {invoice.status === 'deleted' && isSuperAdmin && (
                            <Button variant="ghost" size="sm" onClick={() => handleRestore(invoice)} title="Restore">
                              <RotateCcw className="h-4 w-4 text-green-600" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* View Dialog */}
      <Dialog open={viewDialogOpen} onOpenChange={setViewDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileBadge className="h-5 w-5 text-blue-600" />
              Proforma Invoice {selectedInvoice?.proforma_no}
            </DialogTitle>
          </DialogHeader>
          
          {selectedInvoice && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="font-medium">Date:</span> {selectedInvoice.date}
                </div>
                <div>
                  <span className="font-medium">Time:</span> {selectedInvoice.time}
                </div>
                <div>
                  <span className="font-medium">Customer:</span> {toTitleCase(selectedInvoice.customer_name) || '-'}
                </div>
                <div>
                  <span className="font-medium">Phone:</span> {selectedInvoice.customer_phone || '-'}
                </div>
                <div>
                  <span className="font-medium">Email:</span> {selectedInvoice.customer_email || '-'}
                </div>
                <div>
                  <span className="font-medium">Sales Person:</span> {selectedInvoice.sales_person || '-'}
                </div>
              </div>

              {/* Line Items */}
              <div className="border rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left p-2">Product</th>
                      <th className="text-right p-2">Qty</th>
                      <th className="text-right p-2">Price</th>
                      <th className="text-right p-2">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedInvoice.line_items?.map((item, idx) => (
                      <tr key={idx} className="border-t">
                        <td className="p-2">{item.product_name}</td>
                        <td className="p-2 text-right">{item.quantity}</td>
                        <td className="p-2 text-right">£{(item.due_price || item.price || 0).toFixed(2)}</td>
                        <td className="p-2 text-right">£{(item.total || 0).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Totals */}
              <div className="border-t pt-3 space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>Subtotal:</span>
                  <span>£{(selectedInvoice.subtotal || 0).toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-gray-600">
                  <span>VAT (20%):</span>
                  <span>£{(selectedInvoice.vat || 0).toFixed(2)}</span>
                </div>
                <div className="flex justify-between font-bold text-lg">
                  <span>Total:</span>
                  <span>£{(selectedInvoice.gross_total || 0).toFixed(2)}</span>
                </div>
              </div>

              {/* Bank Details */}
              <div className="bg-blue-50 p-4 rounded-md">
                <h4 className="font-medium text-blue-800 mb-2">Payment Details</h4>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <span className="text-blue-700">Account Name:</span>
                  <span>{BANK_DETAILS.name}</span>
                  <span className="text-blue-700">Account Type:</span>
                  <span>{BANK_DETAILS.accountType}</span>
                  <span className="text-blue-700">Account Number:</span>
                  <span className="font-mono">{BANK_DETAILS.accountNumber}</span>
                  <span className="text-blue-700">Sort Code:</span>
                  <span className="font-mono">{BANK_DETAILS.sortCode}</span>
                </div>
              </div>

              {selectedInvoice.notes && (
                <div className="bg-gray-50 p-3 rounded-md">
                  <span className="font-medium">Notes:</span>
                  <p className="text-sm mt-1">{selectedInvoice.notes}</p>
                </div>
              )}
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewDialogOpen(false)}>Close</Button>
            <Button onClick={() => handleDownloadPdf(selectedInvoice)}>
              <Download className="h-4 w-4 mr-1" /> Download PDF
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Proforma Invoice</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete proforma invoice {invoiceToDelete?.proforma_no}? This action can be undone by a super admin.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ProformaInvoiceHistory;
