import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { MessageSquare, Clock, Phone, Mail, Package, CheckCircle, XCircle, AlertCircle, Trash2 } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';

const statusConfig = {
  pending: { 
    label: 'Pending', 
    color: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    icon: Clock
  },
  contacted: { 
    label: 'Contacted', 
    color: 'bg-blue-100 text-blue-800 border-blue-200',
    icon: Phone
  },
  quoted: { 
    label: 'Quoted', 
    color: 'bg-purple-100 text-purple-800 border-purple-200',
    icon: MessageSquare
  },
  closed: { 
    label: 'Closed', 
    color: 'bg-green-100 text-green-800 border-green-200',
    icon: CheckCircle
  }
};

export const BulkInquiries = () => {
  const [inquiries, setInquiries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [editingNotes, setEditingNotes] = useState(null);
  const [notes, setNotes] = useState('');

  useEffect(() => {
    fetchInquiries();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  const fetchInquiries = async () => {
    try {
      const status = filter === 'all' ? null : filter;
      const response = await api.getBulkInquiries(status);
      setInquiries(response.data);
    } catch (error) {
      toast.error('Failed to load inquiries');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const updateStatus = async (id, newStatus) => {
    try {
      await api.updateBulkInquiry(id, { status: newStatus });
      toast.success('Status updated');
      fetchInquiries();
    } catch (error) {
      toast.error('Failed to update status');
    }
  };

  const saveNotes = async (id) => {
    try {
      await api.updateBulkInquiry(id, { admin_notes: notes });
      toast.success('Notes saved');
      setEditingNotes(null);
      fetchInquiries();
    } catch (error) {
      toast.error('Failed to save notes');
    }
  };

  const deleteInquiry = async (id) => {
    if (!window.confirm('Are you sure you want to delete this inquiry?')) return;
    
    try {
      await api.deleteBulkInquiry(id);
      toast.success('Inquiry deleted');
      fetchInquiries();
    } catch (error) {
      toast.error('Failed to delete inquiry');
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>;
  }

  const pendingCount = inquiries.filter(i => i.status === 'pending').length;

  return (
    <div className="space-y-6" data-testid="bulk-inquiries-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-tightest mb-2 flex items-center gap-3">
            Bulk Inquiries
            {pendingCount > 0 && (
              <Badge className="bg-red-500 text-white">{pendingCount} pending</Badge>
            )}
          </h1>
          <p className="text-muted-foreground">Manage customer requests for bulk orders and custom quotes</p>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2">
        {['all', 'pending', 'contacted', 'quoted', 'closed'].map(status => (
          <Button
            key={status}
            variant={filter === status ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter(status)}
            className={filter === status ? 'bg-accent' : ''}
            data-testid={`filter-${status}`}
          >
            {status === 'all' ? 'All' : statusConfig[status]?.label || status}
            {status === 'pending' && pendingCount > 0 && (
              <span className="ml-2 bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                {pendingCount}
              </span>
            )}
          </Button>
        ))}
      </div>

      {/* Inquiries List */}
      {inquiries.length === 0 ? (
        <Card className="p-12 text-center">
          <MessageSquare className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-20" />
          <h3 className="text-lg font-semibold mb-2">No inquiries found</h3>
          <p className="text-muted-foreground">
            {filter === 'all' 
              ? 'When customers submit bulk order inquiries, they will appear here.'
              : `No ${filter} inquiries at the moment.`}
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {inquiries.map(inquiry => {
            const status = statusConfig[inquiry.status] || statusConfig.pending;
            const StatusIcon = status.icon;
            
            return (
              <Card key={inquiry.id} className="p-6" data-testid={`inquiry-${inquiry.id}`}>
                <div className="flex flex-col lg:flex-row gap-6">
                  {/* Main Info */}
                  <div className="flex-1 space-y-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-heading font-bold text-lg">{inquiry.product_name}</h3>
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${status.color}`}>
                            <StatusIcon className="h-3 w-3" />
                            {status.label}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground font-mono">{inquiry.product_sku}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-2xl font-bold text-accent">{inquiry.quantity_needed} pieces</p>
                        <p className="text-xs text-muted-foreground">requested quantity</p>
                      </div>
                    </div>

                    {/* Customer Info */}
                    <div className="bg-secondary rounded-lg p-4">
                      <p className="text-sm font-semibold mb-2">Customer Details</p>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                        <div className="flex items-center gap-2">
                          <Package className="h-4 w-4 text-muted-foreground" />
                          <span>{inquiry.customer_name}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Mail className="h-4 w-4 text-muted-foreground" />
                          <a href={`mailto:${inquiry.customer_email}`} className="text-accent hover:underline">
                            {inquiry.customer_email}
                          </a>
                        </div>
                        {inquiry.customer_phone && (
                          <div className="flex items-center gap-2">
                            <Phone className="h-4 w-4 text-muted-foreground" />
                            <a href={`tel:${inquiry.customer_phone}`} className="text-accent hover:underline">
                              {inquiry.customer_phone}
                            </a>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Customer Message */}
                    {inquiry.message && (
                      <div>
                        <p className="text-sm font-semibold mb-1">Customer Notes</p>
                        <p className="text-sm text-muted-foreground bg-secondary/50 rounded-lg p-3">
                          &ldquo;{inquiry.message}&rdquo;
                        </p>
                      </div>
                    )}

                    {/* Admin Notes */}
                    <div>
                      <p className="text-sm font-semibold mb-1">Admin Notes</p>
                      {editingNotes === inquiry.id ? (
                        <div className="space-y-2">
                          <textarea
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            className="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm"
                            placeholder="Add notes about this inquiry..."
                          />
                          <div className="flex gap-2">
                            <Button size="sm" onClick={() => saveNotes(inquiry.id)}>Save</Button>
                            <Button size="sm" variant="outline" onClick={() => setEditingNotes(null)}>Cancel</Button>
                          </div>
                        </div>
                      ) : (
                        <div 
                          className="text-sm text-muted-foreground bg-secondary/50 rounded-lg p-3 cursor-pointer hover:bg-secondary"
                          onClick={() => {
                            setEditingNotes(inquiry.id);
                            setNotes(inquiry.admin_notes || '');
                          }}
                        >
                          {inquiry.admin_notes || 'Click to add notes...'}
                        </div>
                      )}
                    </div>

                    {/* Timestamp */}
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      Submitted {formatDate(inquiry.created_at)}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="lg:w-48 flex flex-col gap-2">
                    <p className="text-sm font-semibold mb-1">Update Status</p>
                    <select
                      value={inquiry.status}
                      onChange={(e) => updateStatus(inquiry.id, e.target.value)}
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      data-testid={`status-select-${inquiry.id}`}
                    >
                      <option value="pending">Pending</option>
                      <option value="contacted">Contacted</option>
                      <option value="quoted">Quoted</option>
                      <option value="closed">Closed</option>
                    </select>
                    
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      onClick={() => deleteInquiry(inquiry.id)}
                      data-testid={`delete-inquiry-${inquiry.id}`}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};
