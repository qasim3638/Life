import React, { useState, useEffect, useRef } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { 
  Mail, Send, Building2, User, FileText, 
  Paperclip, Clock, CheckCircle, AlertCircle,
  RefreshCw, Search, X, Upload, File, Trash2,
  Plus, Users, Eye, EyeOff
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
import { EMAIL_CONFIG } from '../../config/emailConfig';

// Email templates
const EMAIL_TEMPLATES = [
  {
    id: 'custom',
    name: 'Custom Email',
    subject: '',
    body: ''
  },
  {
    id: 'order_update',
    name: 'Order Update',
    subject: 'Update on Your Order - Tile Station',
    body: `Dear {customer_name},

We wanted to update you on the status of your recent order.

{message}

If you have any questions, please don't hesitate to contact us.

Best regards,
{showroom_name} - Tile Station
Tel: 01474 878 989`
  },
  {
    id: 'stock_arrival',
    name: 'Stock Arrival Notification',
    subject: 'Good News! Your Items Are In Stock - Tile Station',
    body: `Dear {customer_name},

Great news! The items you were waiting for have arrived at our {showroom_name} showroom.

{message}

Please visit us or call to arrange collection/delivery.

Best regards,
{showroom_name} - Tile Station
Tel: 01474 878 989`
  },
  {
    id: 'payment_reminder',
    name: 'Payment Reminder',
    subject: 'Payment Reminder - Tile Station',
    body: `Dear {customer_name},

This is a friendly reminder regarding your outstanding balance.

{message}

Please contact us if you have any questions about your account.

Best regards,
{showroom_name} - Tile Station
Tel: 01474 878 989`
  },
  {
    id: 'thank_you',
    name: 'Thank You',
    subject: 'Thank You for Your Purchase - Tile Station',
    body: `Dear {customer_name},

Thank you for choosing Tile Station for your recent purchase!

We truly appreciate your business and hope you're delighted with your new tiles.

{message}

We look forward to serving you again in the future.

Best regards,
{showroom_name} - Tile Station
Tel: 01474 878 989`
  },
  {
    id: 'promotion',
    name: 'Special Promotion',
    subject: 'Exclusive Offer Just For You - Tile Station',
    body: `Dear {customer_name},

As a valued customer, we'd like to share an exclusive offer with you!

{message}

Visit our {showroom_name} showroom to take advantage of this special promotion.

Best regards,
{showroom_name} - Tile Station
Tel: 01474 878 989`
  }
];

// Max file size: 10MB
const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ALLOWED_FILE_TYPES = [
  'application/pdf',
  'image/jpeg',
  'image/png',
  'image/gif',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/plain',
  'text/csv'
];

// Email input chip component
const EmailChips = ({ emails, onAdd, onRemove, placeholder, label, icon: Icon }) => {
  const [inputValue, setInputValue] = useState('');
  const inputRef = useRef(null);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',' || e.key === ' ' || e.key === 'Tab') {
      e.preventDefault();
      addEmail();
    } else if (e.key === 'Backspace' && !inputValue && emails.length > 0) {
      onRemove(emails.length - 1);
    }
  };

  const addEmail = () => {
    const email = inputValue.trim().replace(/,/g, '');
    if (email && isValidEmail(email) && !emails.includes(email)) {
      onAdd(email);
      setInputValue('');
    } else if (email && !isValidEmail(email)) {
      toast.error(`Invalid email: ${email}`);
    }
  };

  const isValidEmail = (email) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const pastedText = e.clipboardData.getData('text');
    const pastedEmails = pastedText.split(/[,;\s\n]+/).filter(e => e.trim());
    
    pastedEmails.forEach(email => {
      const trimmed = email.trim();
      if (isValidEmail(trimmed) && !emails.includes(trimmed)) {
        onAdd(trimmed);
      }
    });
  };

  return (
    <div>
      <label className="text-sm font-medium mb-1 block flex items-center gap-2">
        <Icon className="h-4 w-4" />
        {label}
      </label>
      <div 
        className="min-h-[42px] p-2 border rounded-md flex flex-wrap gap-1 items-center cursor-text bg-white"
        onClick={() => inputRef.current?.focus()}
      >
        {emails.map((email, index) => (
          <span 
            key={index}
            className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
          >
            {email}
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onRemove(index); }}
              className="hover:bg-blue-200 rounded-full p-0.5"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={addEmail}
          onPaste={handlePaste}
          placeholder={emails.length === 0 ? placeholder : ''}
          className="flex-1 min-w-[150px] outline-none text-sm bg-transparent"
        />
      </div>
      <p className="text-xs text-muted-foreground mt-1">
        Press Enter, comma, or space to add multiple emails
      </p>
    </div>
  );
};

export const EmailComposer = () => {
  const [showrooms, setStores] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [emailHistory, setEmailHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [showCustomerSearch, setShowCustomerSearch] = useState(false);
  const [showHistoryDialog, setShowHistoryDialog] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const [showCcBcc, setShowCcBcc] = useState(false);
  const fileInputRef = useRef(null);
  
  const [formData, setFormData] = useState({
    to_emails: [],
    to_name: '',
    cc_emails: [],
    bcc_emails: [],
    subject: '',
    body: '',
    showroom_id: '',
    template_id: 'custom'
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [showroomsRes, customersRes, historyRes] = await Promise.all([
        api.getStores(),
        api.getCustomers().catch(() => ({ data: [] })),
        api.getEmailHistory().catch(() => ({ data: [] }))
      ]);
      setStores(showroomsRes.data || []);
      setCustomers(customersRes.data || []);
      setEmailHistory(historyRes.data || []);
      
      // Set default showroom if available
      if (showroomsRes.data?.length > 0) {
        setFormData(prev => ({ ...prev, showroom_id: showroomsRes.data[0].id }));
      }
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTemplateChange = (templateId) => {
    const template = EMAIL_TEMPLATES.find(t => t.id === templateId);
    if (template) {
      const showroom = showrooms.find(s => s.id === formData.showroom_id);
      let body = template.body
        .replace(/{showroom_name}/g, showroom?.name || 'Tile Station')
        .replace(/{customer_name}/g, formData.to_name || 'Valued Customer')
        .replace(/{message}/g, '');
      
      setFormData(prev => ({
        ...prev,
        template_id: templateId,
        subject: template.subject,
        body: body
      }));
    }
  };

  const handleCustomerSelect = (customer) => {
    if (customer.email && !formData.to_emails.includes(customer.email)) {
      setFormData(prev => ({
        ...prev,
        to_emails: [...prev.to_emails, customer.email],
        to_name: prev.to_name || customer.name
      }));
    }
    setShowCustomerSearch(false);
    setSearchTerm('');
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    
    for (const file of files) {
      // Check file size
      if (file.size > MAX_FILE_SIZE) {
        toast.error(`File "${file.name}" exceeds 10MB limit`);
        continue;
      }
      
      // Check file type
      if (!ALLOWED_FILE_TYPES.includes(file.type)) {
        toast.error(`File type "${file.type}" is not supported`);
        continue;
      }
      
      // Check if already added
      if (attachments.some(a => a.name === file.name)) {
        toast.error(`File "${file.name}" is already attached`);
        continue;
      }
      
      // Convert to base64
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result.split(',')[1];
        setAttachments(prev => [...prev, {
          name: file.name,
          type: file.type,
          size: file.size,
          content: base64
        }]);
      };
      reader.readAsDataURL(file);
    }
    
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeAttachment = (index) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const getFileIcon = (type) => {
    if (type.startsWith('image/')) return '🖼️';
    if (type.includes('pdf')) return '📄';
    if (type.includes('word') || type.includes('document')) return '📝';
    if (type.includes('excel') || type.includes('spreadsheet')) return '📊';
    return '📎';
  };

  const handleSendEmail = async (e) => {
    e.preventDefault();
    
    if (formData.to_emails.length === 0) {
      toast.error('Please add at least one recipient');
      return;
    }
    if (!formData.subject) {
      toast.error('Please enter a subject');
      return;
    }
    if (!formData.body) {
      toast.error('Please enter email body');
      return;
    }
    if (!formData.showroom_id) {
      toast.error('Please select a showroom');
      return;
    }

    setSending(true);
    try {
      const showroom = showrooms.find(s => s.id === formData.showroom_id);
      await api.sendManualEmail({
        to_emails: formData.to_emails,
        to_name: formData.to_name || null,
        cc_emails: formData.cc_emails.length > 0 ? formData.cc_emails : null,
        bcc_emails: formData.bcc_emails.length > 0 ? formData.bcc_emails : null,
        subject: formData.subject,
        body: formData.body,
        showroom_id: formData.showroom_id,
        showroom_name: showroom?.name,
        attachments: attachments.length > 0 ? attachments : undefined
      });
      
      const totalRecipients = formData.to_emails.length + formData.cc_emails.length + formData.bcc_emails.length;
      toast.success(`Email sent to ${totalRecipients} recipient(s)${attachments.length > 0 ? ` with ${attachments.length} attachment(s)` : ''}`);
      
      // Clear form but keep showroom
      setFormData(prev => ({
        ...prev,
        to_emails: [],
        to_name: '',
        cc_emails: [],
        bcc_emails: [],
        subject: '',
        body: '',
        template_id: 'custom'
      }));
      setAttachments([]);
      setShowCcBcc(false);
      
      // Refresh history
      fetchData();
    } catch (error) {
      if (error.response?.data?.detail) {
        toast.error(error.response.data.detail);
      } else {
        toast.error('Failed to send email');
      }
    } finally {
      setSending(false);
    }
  };

  const filteredCustomers = customers.filter(c => 
    c.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.name?.toLowerCase().includes(searchTerm.toLowerCase())
  ).slice(0, 10);

  const selectedStore = showrooms.find(s => s.id === formData.showroom_id);

  const totalRecipients = formData.to_emails.length + formData.cc_emails.length + formData.bcc_emails.length;

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>;
  }

  // Show disabled state if email is not enabled
  if (!EMAIL_CONFIG.EMAIL_ENABLED) {
    return (
      <div className="space-y-6" data-testid="email-composer-page">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-4xl font-heading font-bold tracking-tightest mb-2">Email</h1>
            <p className="text-muted-foreground">Send emails to customers from your showroom</p>
          </div>
        </div>

        {/* Disabled Notice */}
        <Card className="p-8 text-center">
          <div className="flex flex-col items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center">
              <AlertCircle className="h-8 w-8 text-amber-600" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-800 mb-2">Email Service Temporarily Unavailable</h2>
              <p className="text-muted-foreground max-w-md mx-auto">
                The email service is currently being configured. Domain verification is in progress.
                All email settings and history are preserved and will be available once the service is restored.
              </p>
            </div>
            <div className="mt-4 p-4 bg-blue-50 rounded-lg text-sm text-blue-700">
              <p className="font-medium">What you can do in the meantime:</p>
              <ul className="mt-2 text-left list-disc list-inside space-y-1">
                <li>Print invoices and quotations directly</li>
                <li>Download PDF documents to send manually</li>
                <li>Use your regular email client to contact customers</li>
              </ul>
            </div>
          </div>
        </Card>

        {/* Email History - Still viewable */}
        <Card className="p-4">
          <h3 className="font-semibold mb-3 flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Previous Email History
          </h3>
          <div className="space-y-2">
            {emailHistory.slice(0, 5).map((email, index) => (
              <div key={index} className="text-sm p-2 bg-gray-50 rounded">
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-3 w-3 text-green-500 shrink-0" />
                  <span className="font-medium truncate">{email.to_email}</span>
                </div>
                <p className="text-xs text-muted-foreground truncate mt-1">{email.subject}</p>
                <p className="text-xs text-muted-foreground">
                  {new Date(email.sent_at).toLocaleDateString('en-GB', {
                    day: '2-digit',
                    month: 'short',
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </p>
              </div>
            ))}
            {emailHistory.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                No emails sent yet
              </p>
            )}
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="email-composer-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-tightest mb-2">Email</h1>
          <p className="text-muted-foreground">Send emails to customers from your showroom</p>
        </div>
        <Button 
          variant="outline" 
          onClick={() => setShowHistoryDialog(true)}
          data-testid="view-history-btn"
        >
          <Clock className="h-4 w-4 mr-2" />
          Email History
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Email Form */}
        <div className="lg:col-span-2">
          <Card className="p-6">
            <form onSubmit={handleSendEmail} className="space-y-4">
              {/* From Store */}
              <div>
                <label className="text-sm font-medium mb-1 block flex items-center gap-2">
                  <Building2 className="h-4 w-4" />
                  Send From <span className="text-red-500">*</span>
                </label>
                <select
                  value={formData.showroom_id}
                  onChange={(e) => setFormData({ ...formData, showroom_id: e.target.value })}
                  className="w-full h-10 px-3 border rounded-md"
                  data-testid="showroom-select"
                >
                  <option value="">Select showroom...</option>
                  {showrooms.map(showroom => (
                    <option key={showroom.id} value={showroom.id}>
                      {showroom.name}
                    </option>
                  ))}
                </select>
                {selectedStore && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Email will be sent from: {selectedStore.name.toLowerCase()}@tilestation.co.uk
                  </p>
                )}
              </div>

              {/* To Recipients */}
              <div className="relative">
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm font-medium flex items-center gap-2">
                    <Mail className="h-4 w-4" />
                    To <span className="text-red-500">*</span>
                  </label>
                  <div className="flex items-center gap-2">
                    <Button 
                      type="button" 
                      variant="ghost" 
                      size="sm"
                      onClick={() => setShowCustomerSearch(!showCustomerSearch)}
                      title="Search customers"
                    >
                      <Search className="h-4 w-4 mr-1" />
                      Find Customer
                    </Button>
                    <Button 
                      type="button" 
                      variant="ghost" 
                      size="sm"
                      onClick={() => setShowCcBcc(!showCcBcc)}
                    >
                      {showCcBcc ? <EyeOff className="h-4 w-4 mr-1" /> : <Eye className="h-4 w-4 mr-1" />}
                      CC/BCC
                    </Button>
                  </div>
                </div>
                
                <EmailChips
                  emails={formData.to_emails}
                  onAdd={(email) => setFormData(prev => ({ ...prev, to_emails: [...prev.to_emails, email] }))}
                  onRemove={(index) => setFormData(prev => ({ ...prev, to_emails: prev.to_emails.filter((_, i) => i !== index) }))}
                  placeholder="Enter email addresses..."
                  label=""
                  icon={Mail}
                />
                
                {/* Customer Search Dropdown */}
                {showCustomerSearch && (
                  <div className="absolute z-10 w-full mt-1 bg-white border rounded-md shadow-lg max-h-60 overflow-y-auto">
                    <div className="p-2 border-b">
                      <Input
                        type="text"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        placeholder="Search by name or email..."
                        autoFocus
                      />
                    </div>
                    {filteredCustomers.length > 0 ? (
                      filteredCustomers.map(customer => (
                        <button
                          key={customer.id}
                          type="button"
                          onClick={() => handleCustomerSelect(customer)}
                          className="w-full px-3 py-2 text-left hover:bg-gray-100 flex flex-col"
                        >
                          <span className="font-medium">{customer.name}</span>
                          <span className="text-sm text-muted-foreground">{customer.email}</span>
                        </button>
                      ))
                    ) : (
                      <div className="px-3 py-2 text-muted-foreground text-sm">
                        No customers found
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => setShowCustomerSearch(false)}
                      className="w-full px-3 py-2 text-center text-sm text-muted-foreground hover:bg-gray-100 border-t"
                    >
                      Close
                    </button>
                  </div>
                )}
              </div>

              {/* CC and BCC */}
              {showCcBcc && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-gray-50 rounded-lg">
                  <EmailChips
                    emails={formData.cc_emails}
                    onAdd={(email) => setFormData(prev => ({ ...prev, cc_emails: [...prev.cc_emails, email] }))}
                    onRemove={(index) => setFormData(prev => ({ ...prev, cc_emails: prev.cc_emails.filter((_, i) => i !== index) }))}
                    placeholder="CC recipients..."
                    label="CC (Carbon Copy)"
                    icon={Users}
                  />
                  <EmailChips
                    emails={formData.bcc_emails}
                    onAdd={(email) => setFormData(prev => ({ ...prev, bcc_emails: [...prev.bcc_emails, email] }))}
                    onRemove={(index) => setFormData(prev => ({ ...prev, bcc_emails: prev.bcc_emails.filter((_, i) => i !== index) }))}
                    placeholder="BCC recipients..."
                    label="BCC (Blind Carbon Copy)"
                    icon={EyeOff}
                  />
                </div>
              )}

              {/* Recipient Name */}
              <div>
                <label className="text-sm font-medium mb-1 block flex items-center gap-2">
                  <User className="h-4 w-4" />
                  Recipient Name (optional)
                </label>
                <Input
                  type="text"
                  value={formData.to_name}
                  onChange={(e) => setFormData({ ...formData, to_name: e.target.value })}
                  placeholder="John Smith (used in template greeting)"
                  data-testid="to-name-input"
                />
              </div>

              {/* Template */}
              <div>
                <label className="text-sm font-medium mb-1 block flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  Email Template
                </label>
                <select
                  value={formData.template_id}
                  onChange={(e) => handleTemplateChange(e.target.value)}
                  className="w-full h-10 px-3 border rounded-md"
                  data-testid="template-select"
                >
                  {EMAIL_TEMPLATES.map(template => (
                    <option key={template.id} value={template.id}>
                      {template.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Subject */}
              <div>
                <label className="text-sm font-medium mb-1 block">
                  Subject <span className="text-red-500">*</span>
                </label>
                <Input
                  type="text"
                  value={formData.subject}
                  onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                  placeholder="Email subject..."
                  data-testid="subject-input"
                />
              </div>

              {/* Body */}
              <div>
                <label className="text-sm font-medium mb-1 block">
                  Message <span className="text-red-500">*</span>
                </label>
                <Textarea
                  value={formData.body}
                  onChange={(e) => setFormData({ ...formData, body: e.target.value })}
                  placeholder="Type your message here..."
                  rows={8}
                  className="font-mono text-sm"
                  data-testid="body-textarea"
                />
              </div>

              {/* Attachments */}
              <div>
                <label className="text-sm font-medium mb-2 block flex items-center gap-2">
                  <Paperclip className="h-4 w-4" />
                  Attachments
                </label>
                
                {/* File Upload Area */}
                <div 
                  className="border-2 border-dashed rounded-lg p-4 text-center hover:border-primary/50 transition-colors cursor-pointer"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    onChange={handleFileSelect}
                    className="hidden"
                    accept=".pdf,.jpg,.jpeg,.png,.gif,.doc,.docx,.xls,.xlsx,.txt,.csv"
                    data-testid="file-input"
                  />
                  <Upload className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                  <p className="text-sm text-muted-foreground">
                    Click to upload or drag and drop
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    PDF, Images, Word, Excel (Max 10MB each)
                  </p>
                </div>

                {/* Attached Files List */}
                {attachments.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {attachments.map((file, index) => (
                      <div 
                        key={index}
                        className="flex items-center justify-between p-2 bg-gray-50 rounded-lg border"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-lg">{getFileIcon(file.type)}</span>
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">{file.name}</p>
                            <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
                          </div>
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => removeAttachment(index)}
                          className="text-red-500 hover:text-red-700 hover:bg-red-50"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                    <p className="text-xs text-muted-foreground">
                      {attachments.length} file(s) attached • Total: {formatFileSize(attachments.reduce((sum, f) => sum + f.size, 0))}
                    </p>
                  </div>
                )}
              </div>

              {/* Send Button */}
              <div className="flex justify-between items-center gap-2 pt-4 border-t">
                <div className="text-sm text-muted-foreground">
                  {totalRecipients > 0 && (
                    <span className="flex items-center gap-1">
                      <Users className="h-4 w-4" />
                      {totalRecipients} recipient(s)
                      {formData.cc_emails.length > 0 && ` (${formData.cc_emails.length} CC)`}
                      {formData.bcc_emails.length > 0 && ` (${formData.bcc_emails.length} BCC)`}
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setFormData({
                        ...formData,
                        to_emails: [],
                        to_name: '',
                        cc_emails: [],
                        bcc_emails: [],
                        subject: '',
                        body: '',
                        template_id: 'custom'
                      });
                      setAttachments([]);
                    }}
                  >
                    Clear
                  </Button>
                  <Button 
                    type="submit" 
                    disabled={sending || formData.to_emails.length === 0}
                    className="bg-blue-600 hover:bg-blue-700"
                    data-testid="send-email-btn"
                  >
                    {sending ? (
                      <>
                        <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                        Sending...
                      </>
                    ) : (
                      <>
                        <Send className="h-4 w-4 mr-2" />
                        Send Email
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </form>
          </Card>
        </div>

        {/* Sidebar - Quick Stats & Recent */}
        <div className="space-y-4">
          {/* Stats */}
          <Card className="p-4">
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <Mail className="h-4 w-4" />
              Email Stats
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Emails sent today</span>
                <span className="font-medium">
                  {emailHistory.filter(e => {
                    const sent = new Date(e.sent_at);
                    const today = new Date();
                    return sent.toDateString() === today.toDateString();
                  }).length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total sent</span>
                <span className="font-medium">{emailHistory.length}</span>
              </div>
            </div>
          </Card>

          {/* Recent Emails */}
          <Card className="p-4">
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Recent Emails
            </h3>
            <div className="space-y-2">
              {emailHistory.slice(0, 5).map((email, index) => (
                <div key={index} className="text-sm p-2 bg-gray-50 rounded">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-3 w-3 text-green-500 shrink-0" />
                    <span className="font-medium truncate">{email.to_email}</span>
                  </div>
                  <p className="text-xs text-muted-foreground truncate mt-1">
                    {email.subject}
                    {email.has_attachments && ' 📎'}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <p className="text-xs text-muted-foreground">
                      {new Date(email.sent_at).toLocaleDateString('en-GB', {
                        day: '2-digit',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </p>
                    {email.cc_emails?.length > 0 && (
                      <span className="text-xs bg-gray-200 px-1 rounded">CC: {email.cc_emails.length}</span>
                    )}
                  </div>
                </div>
              ))}
              {emailHistory.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No emails sent yet
                </p>
              )}
            </div>
          </Card>

          {/* Tips */}
          <Card className="p-4 bg-blue-50 border-blue-200">
            <h3 className="font-semibold mb-2 text-blue-800">Tips</h3>
            <ul className="text-sm text-blue-700 space-y-1">
              <li>• Add multiple emails with Enter or comma</li>
              <li>• Paste a list of emails to add them all</li>
              <li>• Use CC for visible copies</li>
              <li>• Use BCC for hidden copies</li>
              <li>• Max 10MB per attachment</li>
            </ul>
          </Card>
        </div>
      </div>

      {/* Email History Dialog */}
      <Dialog open={showHistoryDialog} onOpenChange={setShowHistoryDialog}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Email History
            </DialogTitle>
            <DialogDescription>
              All emails sent from the application
            </DialogDescription>
          </DialogHeader>
          
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white">
                <tr className="border-b">
                  <th className="text-left py-2 px-3">Date</th>
                  <th className="text-left py-2 px-3">To</th>
                  <th className="text-left py-2 px-3">CC/BCC</th>
                  <th className="text-left py-2 px-3">Subject</th>
                  <th className="text-left py-2 px-3">From</th>
                  <th className="text-center py-2 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {emailHistory.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-muted-foreground">
                      No emails sent yet
                    </td>
                  </tr>
                ) : (
                  emailHistory.map((email, index) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="py-2 px-3 whitespace-nowrap">
                        {new Date(email.sent_at).toLocaleDateString('en-GB', {
                          day: '2-digit',
                          month: 'short',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </td>
                      <td className="py-2 px-3">
                        <div className="font-medium max-w-[150px] truncate" title={email.to_email}>
                          {email.to_email}
                        </div>
                        {email.to_name && (
                          <div className="text-xs text-muted-foreground">{email.to_name}</div>
                        )}
                      </td>
                      <td className="py-2 px-3">
                        {email.cc_emails?.length > 0 && (
                          <span className="text-xs bg-blue-100 text-blue-700 px-1 rounded mr-1">
                            CC: {email.cc_emails.length}
                          </span>
                        )}
                        {email.bcc_emails?.length > 0 && (
                          <span className="text-xs bg-gray-200 text-gray-700 px-1 rounded">
                            BCC: {email.bcc_emails.length}
                          </span>
                        )}
                        {!email.cc_emails?.length && !email.bcc_emails?.length && '-'}
                      </td>
                      <td className="py-2 px-3 max-w-[200px] truncate">
                        {email.subject}
                        {email.has_attachments && (
                          <span className="ml-1 text-muted-foreground">📎{email.attachment_count}</span>
                        )}
                      </td>
                      <td className="py-2 px-3 text-muted-foreground">
                        {email.showroom_name || 'Tile Station'}
                      </td>
                      <td className="py-2 px-3 text-center">
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 rounded-full text-xs">
                          <CheckCircle className="h-3 w-3" />
                          Sent
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowHistoryDialog(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EmailComposer;
