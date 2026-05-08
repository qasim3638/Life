import React, { useState, useEffect } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { 
  Inbox, Mail, Star, Archive, Trash2, Search, RefreshCw,
  ChevronLeft, ChevronRight, Eye, Reply, Send, X, Check,
  Building2, Clock, User, Paperclip, MailOpen, Filter
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Card } from '../../components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';

export const EmailInbox = () => {
  const [emails, setEmails] = useState([]);
  const [stats, setStats] = useState(null);
  const [showrooms, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedEmail, setSelectedEmail] = useState(null);
  const [showEmailDialog, setShowEmailDialog] = useState(false);
  const [showReplyDialog, setShowReplyDialog] = useState(false);
  const [sending, setSending] = useState(false);
  const [selectedEmails, setSelectedEmails] = useState([]);
  
  // Store tab selection
  const [activeStore, setActiveStore] = useState('all');
  
  // Filters
  const [filters, setFilters] = useState({
    showroom_id: '',
    is_read: '',
    is_starred: '',
    search: ''
  });
  const [activeFilter, setActiveFilter] = useState('inbox'); // inbox, unread, starred, archived
  
  // Pagination
  const [pagination, setPagination] = useState({ skip: 0, limit: 25, total: 0 });
  
  // Reply form
  const [replyData, setReplyData] = useState({
    subject: '',
    body: '',
    showroom_id: ''
  });

  useEffect(() => {
    fetchStores();
  }, []);

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, activeFilter, pagination.skip, activeStore]);

  const fetchStores = async () => {
    try {
      const res = await api.getStores();
      setStores(res.data || []);
    } catch (error) {
      console.error('Failed to load showrooms:', error);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      // Build query params
      const params = {
        skip: pagination.skip,
        limit: pagination.limit,
        ...filters
      };
      
      // Apply showroom tab filter
      if (activeStore !== 'all') {
        params.showroom_id = activeStore;
      }
      
      // Apply active filter
      if (activeFilter === 'unread') {
        params.is_read = false;
      } else if (activeFilter === 'starred') {
        params.is_starred = true;
      } else if (activeFilter === 'archived') {
        params.is_archived = true;
      }
      
      // Remove empty params
      Object.keys(params).forEach(key => {
        if (params[key] === '' || params[key] === undefined) {
          delete params[key];
        }
      });
      
      const [inboxRes, statsRes] = await Promise.all([
        api.getInbox(params),
        api.getInboxStats()
      ]);
      
      setEmails(inboxRes.data.emails || []);
      setPagination(prev => ({ ...prev, total: inboxRes.data.total || 0 }));
      setStats(statsRes.data);
    } catch (error) {
      console.error('Failed to load inbox:', error);
      toast.error('Failed to load inbox');
    } finally {
      setLoading(false);
    }
  };

  const handleViewEmail = async (email) => {
    try {
      const response = await api.getInboxEmail(email.id);
      setSelectedEmail(response.data);
      setShowEmailDialog(true);
      
      // Refresh to update read status
      if (!email.is_read) {
        fetchData();
      }
    } catch (error) {
      toast.error('Failed to load email');
    }
  };

  const handleToggleStar = async (emailId, currentStarred) => {
    try {
      await api.updateInboxEmail(emailId, { is_starred: !currentStarred });
      setEmails(emails.map(e => 
        e.id === emailId ? { ...e, is_starred: !currentStarred } : e
      ));
    } catch (error) {
      toast.error('Failed to update email');
    }
  };

  const handleArchive = async (emailId) => {
    try {
      await api.updateInboxEmail(emailId, { is_archived: true });
      toast.success('Email archived');
      fetchData();
    } catch (error) {
      toast.error('Failed to archive email');
    }
  };

  const handleDelete = async (emailId) => {
    if (!window.confirm('Are you sure you want to permanently delete this email?')) return;
    
    try {
      await api.deleteInboxEmail(emailId);
      toast.success('Email deleted');
      setShowEmailDialog(false);
      fetchData();
    } catch (error) {
      toast.error('Failed to delete email');
    }
  };

  const handleMarkRead = async (emailIds, isRead) => {
    try {
      if (emailIds.length === 1) {
        await api.updateInboxEmail(emailIds[0], { is_read: isRead });
      } else {
        await api.bulkUpdateInbox(emailIds, { is_read: isRead });
      }
      toast.success(`Marked as ${isRead ? 'read' : 'unread'}`);
      fetchData();
      setSelectedEmails([]);
    } catch (error) {
      toast.error('Failed to update emails');
    }
  };

  const handleBulkArchive = async () => {
    if (selectedEmails.length === 0) return;
    
    try {
      await api.bulkUpdateInbox(selectedEmails, { is_archived: true });
      toast.success(`Archived ${selectedEmails.length} emails`);
      fetchData();
      setSelectedEmails([]);
    } catch (error) {
      toast.error('Failed to archive emails');
    }
  };

  const openReplyDialog = () => {
    if (!selectedEmail) return;
    
    setReplyData({
      subject: selectedEmail.subject.startsWith('Re:') 
        ? selectedEmail.subject 
        : `Re: ${selectedEmail.subject}`,
      body: '',
      showroom_id: selectedEmail.showroom_id || ''
    });
    setShowReplyDialog(true);
  };

  const handleSendReply = async (e) => {
    e.preventDefault();
    
    if (!replyData.subject || !replyData.body) {
      toast.error('Please enter subject and message');
      return;
    }
    
    setSending(true);
    try {
      await api.replyToEmail(selectedEmail.id, replyData);
      toast.success(`Reply sent to ${selectedEmail.from_email}`);
      setShowReplyDialog(false);
      setShowEmailDialog(false);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to send reply');
    } finally {
      setSending(false);
    }
  };

  const toggleEmailSelection = (emailId) => {
    setSelectedEmails(prev => 
      prev.includes(emailId) 
        ? prev.filter(id => id !== emailId)
        : [...prev, emailId]
    );
  };

  const toggleSelectAll = () => {
    if (selectedEmails.length === emails.length) {
      setSelectedEmails([]);
    } else {
      setSelectedEmails(emails.map(e => e.id));
    }
  };

  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
      return date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    } else if (diffDays === 1) {
      return 'Yesterday';
    } else if (diffDays < 7) {
      return date.toLocaleDateString('en-GB', { weekday: 'short' });
    } else {
      return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
    }
  };

  const getFilterLabel = () => {
    switch (activeFilter) {
      case 'unread': return 'Unread';
      case 'starred': return 'Starred';
      case 'archived': return 'Archived';
      default: return 'Inbox';
    }
  };

  // Get unread count for each showroom
  const getStoreUnreadCount = (showroomId) => {
    if (!stats?.by_showroom) return 0;
    const showroom = showrooms.find(s => s.id === showroomId);
    if (showroom && stats.by_showroom[showroom.name]) {
      return stats.by_showroom[showroom.name];
    }
    return 0;
  };

  return (
    <div className="space-y-6" data-testid="email-inbox-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-tightest mb-2">Email Inbox</h1>
          <p className="text-muted-foreground">Receive and manage customer emails by showroom</p>
        </div>
        <Button onClick={fetchData} variant="outline" disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Store Tabs */}
      <div className="flex flex-wrap gap-2 border-b pb-4">
        <button
          onClick={() => { setActiveStore('all'); setPagination(p => ({ ...p, skip: 0 })); }}
          className={`px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${
            activeStore === 'all'
              ? 'bg-primary text-primary-foreground shadow-md'
              : 'bg-muted hover:bg-muted/80 text-muted-foreground'
          }`}
        >
          <Inbox className="h-4 w-4" />
          All Inboxes
          {stats && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              activeStore === 'all' ? 'bg-white/20' : 'bg-gray-200'
            }`}>
              {stats.total}
            </span>
          )}
        </button>
        
        {showrooms.map(showroom => (
          <button
            key={showroom.id}
            onClick={() => { setActiveStore(showroom.id); setPagination(p => ({ ...p, skip: 0 })); }}
            className={`px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${
              activeStore === showroom.id
                ? 'bg-primary text-primary-foreground shadow-md'
                : 'bg-muted hover:bg-muted/80 text-muted-foreground'
            }`}
          >
            <Building2 className="h-4 w-4" />
            {showroom.name}
            {stats?.by_showroom?.[showroom.name] > 0 && (
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                activeStore === showroom.id ? 'bg-white/20' : 'bg-blue-100 text-blue-700'
              }`}>
                {stats.by_showroom[showroom.name]}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar */}
        <div className="space-y-4">
          {/* Quick Filters */}
          {stats && (
            <Card className="p-4">
              <div className="space-y-2">
                <button
                  onClick={() => setActiveFilter('inbox')}
                  className={`w-full flex items-center justify-between p-2 rounded-lg transition-colors ${
                    activeFilter === 'inbox' ? 'bg-primary/10 text-primary' : 'hover:bg-muted'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Inbox className="h-4 w-4" />
                    All
                  </span>
                  <span className="text-sm font-medium">{stats.total}</span>
                </button>
                
                <button
                  onClick={() => setActiveFilter('unread')}
                  className={`w-full flex items-center justify-between p-2 rounded-lg transition-colors ${
                    activeFilter === 'unread' ? 'bg-blue-100 text-blue-700' : 'hover:bg-muted'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Mail className="h-4 w-4" />
                    Unread
                  </span>
                  {stats.unread > 0 && (
                    <span className="text-sm font-medium bg-blue-500 text-white px-2 py-0.5 rounded-full">
                      {stats.unread}
                    </span>
                  )}
                </button>
                
                <button
                  onClick={() => setActiveFilter('starred')}
                  className={`w-full flex items-center justify-between p-2 rounded-lg transition-colors ${
                    activeFilter === 'starred' ? 'bg-yellow-100 text-yellow-700' : 'hover:bg-muted'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Star className="h-4 w-4" />
                    Starred
                  </span>
                  <span className="text-sm font-medium">{stats.starred}</span>
                </button>
                
                <button
                  onClick={() => setActiveFilter('archived')}
                  className={`w-full flex items-center justify-between p-2 rounded-lg transition-colors ${
                    activeFilter === 'archived' ? 'bg-gray-200 text-gray-700' : 'hover:bg-muted'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Archive className="h-4 w-4" />
                    Archived
                  </span>
                  <span className="text-sm font-medium">{stats.archived}</span>
                </button>
              </div>
            </Card>
          )}

          {/* Store Stats */}
          {stats?.by_showroom && Object.keys(stats.by_showroom).length > 0 && (
            <Card className="p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Building2 className="h-4 w-4" />
                Emails by Store
              </h3>
              <div className="space-y-2">
                {Object.entries(stats.by_showroom).map(([name, count]) => (
                  <div key={name} className="flex justify-between items-center text-sm">
                    <span className="text-muted-foreground truncate">{name || 'Unassigned'}</span>
                    <span className="font-medium bg-gray-100 px-2 py-0.5 rounded">{count}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* Email List */}
        <div className="lg:col-span-3">
          <Card className="overflow-hidden">
            {/* Toolbar */}
            <div className="p-3 border-b bg-muted/30 flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2">
                <button
                  onClick={toggleSelectAll}
                  className="p-1.5 hover:bg-muted rounded"
                  title="Select all"
                >
                  <Check className={`h-4 w-4 ${selectedEmails.length === emails.length && emails.length > 0 ? 'text-primary' : 'text-muted-foreground'}`} />
                </button>
                
                {selectedEmails.length > 0 && (
                  <>
                    <span className="text-sm text-muted-foreground">
                      {selectedEmails.length} selected
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleMarkRead(selectedEmails, true)}
                    >
                      <MailOpen className="h-4 w-4 mr-1" />
                      Mark Read
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleBulkArchive}
                    >
                      <Archive className="h-4 w-4 mr-1" />
                      Archive
                    </Button>
                  </>
                )}
              </div>
              
              <div className="flex-1" />
              
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search emails..."
                  value={filters.search}
                  onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                  className="pl-9 w-64 h-8"
                />
              </div>
              
              <div className="text-sm text-muted-foreground">
                {activeStore !== 'all' && (
                  <span className="mr-2 px-2 py-0.5 bg-primary/10 text-primary rounded">
                    {showrooms.find(s => s.id === activeStore)?.name}
                  </span>
                )}
                {getFilterLabel()}: {pagination.total} emails
              </div>
            </div>

            {/* Email List */}
            <div className="divide-y">
              {loading ? (
                <div className="p-8 text-center text-muted-foreground">
                  <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2" />
                  Loading emails...
                </div>
              ) : emails.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground">
                  <Inbox className="h-12 w-12 mx-auto mb-3 opacity-30" />
                  <p className="font-medium">No emails found</p>
                  <p className="text-sm">
                    {activeStore !== 'all' 
                      ? `No emails for ${showrooms.find(s => s.id === activeStore)?.name || 'this showroom'}`
                      : activeFilter === 'inbox' 
                        ? 'Your inbox is empty' 
                        : `No ${getFilterLabel().toLowerCase()} emails`}
                  </p>
                </div>
              ) : (
                emails.map((email) => (
                  <div
                    key={email.id}
                    className={`flex items-center gap-3 p-3 hover:bg-muted/50 cursor-pointer transition-colors ${
                      !email.is_read ? 'bg-blue-50/50 font-medium' : ''
                    } ${selectedEmails.includes(email.id) ? 'bg-primary/5' : ''}`}
                  >
                    {/* Checkbox */}
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleEmailSelection(email.id); }}
                      className="p-1"
                    >
                      <div className={`w-4 h-4 border rounded ${
                        selectedEmails.includes(email.id) 
                          ? 'bg-primary border-primary' 
                          : 'border-gray-300'
                      }`}>
                        {selectedEmails.includes(email.id) && (
                          <Check className="h-3 w-3 text-white" />
                        )}
                      </div>
                    </button>
                    
                    {/* Star */}
                    <button
                      onClick={(e) => { e.stopPropagation(); handleToggleStar(email.id, email.is_starred); }}
                      className="p-1"
                    >
                      <Star className={`h-4 w-4 ${
                        email.is_starred ? 'fill-yellow-400 text-yellow-400' : 'text-gray-300'
                      }`} />
                    </button>
                    
                    {/* Email Content - Click to open */}
                    <div 
                      className="flex-1 min-w-0 grid grid-cols-12 gap-2 items-center"
                      onClick={() => handleViewEmail(email)}
                    >
                      {/* From */}
                      <div className="col-span-3 truncate">
                        <span className={!email.is_read ? 'font-semibold' : ''}>
                          {email.from_name || email.from_email}
                        </span>
                      </div>
                      
                      {/* Subject & Preview */}
                      <div className="col-span-6 truncate">
                        <span className={!email.is_read ? 'font-semibold' : ''}>
                          {email.subject}
                        </span>
                        <span className="text-muted-foreground ml-2">
                          - {email.body_text?.substring(0, 60)}...
                        </span>
                      </div>
                      
                      {/* Store Badge - Only show in "All Inboxes" view */}
                      <div className="col-span-2">
                        {activeStore === 'all' && email.showroom_name && (
                          <span className="text-xs px-2 py-0.5 bg-gray-100 rounded-full truncate">
                            {email.showroom_name}
                          </span>
                        )}
                      </div>
                      
                      {/* Date */}
                      <div className="col-span-1 text-right text-sm text-muted-foreground">
                        {formatDate(email.received_at)}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Pagination */}
            {pagination.total > pagination.limit && (
              <div className="p-3 border-t flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  Showing {pagination.skip + 1}-{Math.min(pagination.skip + pagination.limit, pagination.total)} of {pagination.total}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={pagination.skip === 0}
                    onClick={() => setPagination(prev => ({ ...prev, skip: prev.skip - prev.limit }))}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={pagination.skip + pagination.limit >= pagination.total}
                    onClick={() => setPagination(prev => ({ ...prev, skip: prev.skip + prev.limit }))}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* View Email Dialog */}
      <Dialog open={showEmailDialog} onOpenChange={setShowEmailDialog}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
          {selectedEmail && (
            <>
              <DialogHeader>
                <DialogTitle className="text-xl pr-8">{selectedEmail.subject}</DialogTitle>
                <DialogDescription className="flex items-center gap-4 text-sm">
                  <span className="flex items-center gap-1">
                    <User className="h-3 w-3" />
                    {selectedEmail.from_name ? `${selectedEmail.from_name} <${selectedEmail.from_email}>` : selectedEmail.from_email}
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {new Date(selectedEmail.received_at).toLocaleString('en-GB')}
                  </span>
                  {selectedEmail.showroom_name && (
                    <span className="flex items-center gap-1 px-2 py-0.5 bg-primary/10 text-primary rounded">
                      <Building2 className="h-3 w-3" />
                      {selectedEmail.showroom_name}
                    </span>
                  )}
                </DialogDescription>
              </DialogHeader>
              
              <div className="flex-1 overflow-y-auto py-4 border-y">
                {selectedEmail.body_html ? (
                  <div 
                    className="prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{ __html: selectedEmail.body_html }}
                  />
                ) : (
                  <div className="whitespace-pre-wrap font-mono text-sm">
                    {selectedEmail.body_text}
                  </div>
                )}
                
                {selectedEmail.attachments?.length > 0 && (
                  <div className="mt-4 pt-4 border-t">
                    <p className="text-sm font-medium mb-2 flex items-center gap-1">
                      <Paperclip className="h-4 w-4" />
                      Attachments ({selectedEmail.attachments.length})
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {selectedEmail.attachments.map((att, i) => (
                        <span key={i} className="text-sm px-2 py-1 bg-gray-100 rounded">
                          {att.filename || att.name || `Attachment ${i + 1}`}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              
              <DialogFooter className="flex-row justify-between sm:justify-between">
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => handleArchive(selectedEmail.id)}>
                    <Archive className="h-4 w-4 mr-1" />
                    Archive
                  </Button>
                  <Button variant="outline" size="sm" className="text-red-600" onClick={() => handleDelete(selectedEmail.id)}>
                    <Trash2 className="h-4 w-4 mr-1" />
                    Delete
                  </Button>
                </div>
                <Button onClick={openReplyDialog}>
                  <Reply className="h-4 w-4 mr-2" />
                  Reply
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Reply Dialog */}
      <Dialog open={showReplyDialog} onOpenChange={setShowReplyDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Reply className="h-5 w-5" />
              Reply to {selectedEmail?.from_name || selectedEmail?.from_email}
            </DialogTitle>
          </DialogHeader>
          
          <form onSubmit={handleSendReply} className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-1 block">Send From</label>
              <select
                value={replyData.showroom_id}
                onChange={(e) => setReplyData({ ...replyData, showroom_id: e.target.value })}
                className="w-full h-10 px-3 border rounded-md"
              >
                <option value="">Select showroom...</option>
                {showrooms.map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="text-sm font-medium mb-1 block">Subject</label>
              <Input
                value={replyData.subject}
                onChange={(e) => setReplyData({ ...replyData, subject: e.target.value })}
                required
              />
            </div>
            
            <div>
              <label className="text-sm font-medium mb-1 block">Message</label>
              <Textarea
                value={replyData.body}
                onChange={(e) => setReplyData({ ...replyData, body: e.target.value })}
                rows={8}
                placeholder="Type your reply..."
                required
              />
            </div>
            
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowReplyDialog(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={sending}>
                {sending ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    Sending...
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4 mr-2" />
                    Send Reply
                  </>
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EmailInbox;
