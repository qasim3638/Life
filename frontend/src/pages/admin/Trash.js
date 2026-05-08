import React, { useState, useEffect } from 'react';
import { api } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { toast } from 'sonner';
import { Trash2, RotateCcw, AlertTriangle, Clock, FileText, Receipt, CreditCard } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../../components/ui/alert-dialog";

const Trash = () => {
  const [trash, setTrash] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState({ open: false, type: null, id: null, docType: null });

  const fetchTrash = async () => {
    try {
      setLoading(true);
      const response = await api.getTrash();
      setTrash(response.data);
    } catch (error) {
      toast.error('Failed to fetch deleted documents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrash();
  }, []);

  const handleRestore = async (docType, id) => {
    try {
      setActionLoading(`restore-${id}`);
      const restoreMethods = {
        invoices: api.restoreInvoice,
        quotations: api.restoreQuotation,
        cash_quotations: api.restoreCashQuotation,
        refunds: api.restoreRefund,
        credit_notes: api.restoreCreditNote,
      };
      const resp = await restoreMethods[docType](id);
      const reapplied = resp?.data?.credits_reapplied;
      let msg = 'Document restored successfully';
      if (docType === 'invoices' && reapplied && (reapplied.earned_reapplied > 0 || reapplied.redeemed_reapplied > 0)) {
        const parts = [];
        if (reapplied.earned_reapplied > 0) parts.push(`+£${Number(reapplied.earned_reapplied).toFixed(2)} earned re-applied`);
        if (reapplied.redeemed_reapplied > 0) parts.push(`-£${Number(reapplied.redeemed_reapplied).toFixed(2)} redeemed re-deducted`);
        msg += ` · Trade credit: ${parts.join(', ')}`;
      }
      toast.success(msg, { duration: 6000 });
      fetchTrash();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to restore document');
    } finally {
      setActionLoading(null);
    }
  };

  const handlePermanentDelete = async (docType, id) => {
    try {
      setActionLoading(`delete-${id}`);
      const deleteMethods = {
        invoices: api.permanentDeleteInvoice,
        quotations: api.permanentDeleteQuotation,
        cash_quotations: api.permanentDeleteCashQuotation,
        refunds: api.permanentDeleteRefund,
        credit_notes: api.permanentDeleteCreditNote,
      };
      const resp = await deleteMethods[docType](id);
      const reversed = resp?.data?.credits_reversed;
      let msg = 'Document permanently deleted';
      if (docType === 'invoices' && reversed && (reversed.earned_reversed > 0 || reversed.redeemed_reversed > 0)) {
        const parts = [];
        if (reversed.earned_reversed > 0) parts.push(`-£${Number(reversed.earned_reversed).toFixed(2)} earned`);
        if (reversed.redeemed_reversed > 0) parts.push(`+£${Number(reversed.redeemed_reversed).toFixed(2)} redeemed refunded`);
        msg += ` · Trade credit: ${parts.join(', ')}`;
      }
      toast.success(msg, { duration: 6000 });
      fetchTrash();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete document');
    } finally {
      setActionLoading(null);
      setConfirmDialog({ open: false, type: null, id: null, docType: null });
    }
  };

  const handleCleanup = async () => {
    try {
      setActionLoading('cleanup');
      const response = await api.cleanupTrash();
      toast.success(`Cleanup completed. ${response.data.total_deleted} documents permanently deleted.`);
      fetchTrash();
    } catch (error) {
      toast.error('Failed to cleanup trash');
    } finally {
      setActionLoading(null);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getDocIcon = (docType) => {
    switch (docType) {
      case 'invoices': return <Receipt className="h-4 w-4" />;
      case 'quotations': return <FileText className="h-4 w-4" />;
      case 'cash_quotations': return <FileText className="h-4 w-4" />;
      case 'refunds': return <CreditCard className="h-4 w-4" />;
      case 'credit_notes': return <CreditCard className="h-4 w-4" />;
      default: return <FileText className="h-4 w-4" />;
    }
  };

  const renderDocumentTable = (documents, docType) => {
    if (!documents || documents.length === 0) {
      return (
        <div className="text-center py-8 text-muted-foreground">
          No deleted {docType.replace('_', ' ')} found
        </div>
      );
    }

    return (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="text-left p-3">Document No</th>
              <th className="text-left p-3">Customer</th>
              <th className="text-left p-3">Showroom</th>
              <th className="text-right p-3">Amount</th>
              <th className="text-left p-3">Deleted By</th>
              <th className="text-left p-3">Deleted At</th>
              <th className="text-center p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.id} className="border-b hover:bg-muted/30">
                <td className="p-3 font-medium">{doc.document_no}</td>
                <td className="p-3">{doc.customer_name || '-'}</td>
                <td className="p-3">{doc.showroom_name || '-'}</td>
                <td className="p-3 text-right">
                  £{(doc.gross_total || doc.net_refund || doc.net_credit_note || 0).toFixed(2)}
                </td>
                <td className="p-3">{doc.deleted_by_name || doc.deleted_by || '-'}</td>
                <td className="p-3">{formatDate(doc.deleted_at)}</td>
                <td className="p-3">
                  <div className="flex items-center justify-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleRestore(docType, doc.id)}
                      disabled={actionLoading === `restore-${doc.id}`}
                      className="text-green-600 hover:text-green-700 hover:bg-green-50"
                    >
                      <RotateCcw className="h-4 w-4 mr-1" />
                      Restore
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setConfirmDialog({ 
                        open: true, 
                        type: 'permanent', 
                        id: doc.id, 
                        docType,
                        docNo: doc.document_no 
                      })}
                      disabled={actionLoading === `delete-${doc.id}`}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                    >
                      <Trash2 className="h-4 w-4 mr-1" />
                      Delete Forever
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  const tabConfig = [
    { key: 'invoices', label: 'Invoices', count: trash?.invoices?.length || 0 },
    { key: 'quotations', label: 'Quotations', count: trash?.quotations?.length || 0 },
    { key: 'cash_quotations', label: 'Cash Quotations', count: trash?.cash_quotations?.length || 0 },
    { key: 'refunds', label: 'Refunds', count: trash?.refunds?.length || 0 },
    { key: 'credit_notes', label: 'Credit Notes', count: trash?.credit_notes?.length || 0 },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Trash2 className="h-6 w-6" />
            Trash
          </h1>
          <p className="text-muted-foreground mt-1">
            Deleted documents can be restored or permanently deleted manually
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={fetchTrash}
            disabled={loading}
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {tabConfig.map(tab => (
          <Card key={tab.key}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                {getDocIcon(tab.key)}
                <span className="text-sm text-muted-foreground">{tab.label}</span>
              </div>
              <p className="text-2xl font-bold mt-1">{tab.count}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Warning Banner */}
      {trash?.total_count > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-blue-600 mt-0.5" />
          <div>
            <p className="font-medium text-blue-800">
              {trash.total_count} document(s) in trash
            </p>
            <p className="text-sm text-blue-700 mt-1">
              Documents in trash are not permanently deleted automatically. 
              Use &ldquo;Restore&rdquo; to recover a document or &ldquo;Delete Forever&rdquo; to permanently remove it.
            </p>
          </div>
        </div>
      )}

      {/* Document Tabs */}
      <Card>
        <CardContent className="p-0">
          <Tabs defaultValue="invoices">
            <TabsList className="w-full justify-start border-b rounded-none p-0 h-auto">
              {tabConfig.map(tab => (
                <TabsTrigger 
                  key={tab.key}
                  value={tab.key} 
                  className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-6 py-3"
                >
                  {tab.label} ({tab.count})
                </TabsTrigger>
              ))}
            </TabsList>
            {tabConfig.map(tab => (
              <TabsContent key={tab.key} value={tab.key} className="p-0 mt-0">
                {renderDocumentTable(trash?.[tab.key], tab.key)}
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>

      {/* Confirmation Dialog */}
      <AlertDialog 
        open={confirmDialog.open} 
        onOpenChange={(open) => !open && setConfirmDialog({ open: false, type: null, id: null, docType: null })}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 text-red-600">
              <AlertTriangle className="h-5 w-5" />
              Permanently Delete Document?
            </AlertDialogTitle>
            <AlertDialogDescription>
              You are about to permanently delete <strong>{confirmDialog.docNo}</strong>.
              <br /><br />
              <span className="text-red-600 font-medium">
                This action cannot be undone. The document will be permanently removed from the system.
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={() => handlePermanentDelete(confirmDialog.docType, confirmDialog.id)}
            >
              Delete Forever
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default Trash;
