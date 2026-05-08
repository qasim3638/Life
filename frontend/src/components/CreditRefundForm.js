import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { RotateCcw, Plus, Trash2, Printer, Save, History, ArrowLeft, Receipt, Building2, Lock, FileText } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card } from '../../components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { RefundPrintPreview, CreditNotePrintPreview } from '../../components/invoice';

const defaultCompanyInfo = {
  name: 'Tile Station',
  address: 'Unit 3 Trade City Coldharbour Road',
  city: 'Northfleet Gravesend DA11 8AB',
  telephone: '01474 878 989',
  email: 'gravesend@tilestation.co.uk',
  companyNo: '11982550',
  vatNo: '324 251 828'
};

const paymentMethods = ['Cash', 'Card', 'Bank Transfer', 'Store Credit'];
const documentTypes = ['Full', 'Partial', 'Exchange'];

const emptyLineItem = {
  qty: '',
  product: '',
  originalPrice: '',
  adjustedPrice: '',
  productId: '',
  sku: '',
  reason: ''
};

// Generate document number with prefix
const generateDocNo = (prefix = 'DOC') => {
  const timestamp = Date.now().toString().slice(-12);
  return `${prefix}-${timestamp}`;
};

/**
 * CreditRefundForm - A shared component for Refund and Credit Note pages
 * @param {string} documentType - 'refund' or 'creditNote'
 */
export const CreditRefundForm = ({ documentType = 'refund' }) => {
  const navigate = useNavigate();
  const printRef = useRef();
  const { user } = useAuth();
  const [products, setProducts] = useState([]);
  const [showrooms, setStores] = useState([]);
  const [selectedStore, setSelectedStore] = useState(null);
  const [saving, setSaving] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeLineIndex, setActiveLineIndex] = useState(null);
  
  // Staff PIN states
  const [staffPin, setStaffPin] = useState('');
  const [verifiedStaff, setVerifiedStaff] = useState(null);
  const [showPinDialog, setShowPinDialog] = useState(false);
  const [verifyingPin, setVerifyingPin] = useState(false);
  
  // Invoice search for linking
  const [invoiceSearchTerm, setInvoiceSearchTerm] = useState('');
  const [invoiceSearchResults, setInvoiceSearchResults] = useState([]);
  const [showInvoiceSearch, setShowInvoiceSearch] = useState(false);

  // Configuration based on document type
  const isRefund = documentType === 'refund';
  const config = {
    title: isRefund ? 'Process Refund' : 'Process Credit Note',
    icon: RotateCcw,
    iconColor: 'text-red-500',
    prefix: isRefund ? 'REF' : 'CN',
    numberField: isRefund ? 'refundNo' : 'creditNoteNo',
    priceField: isRefund ? 'refundPrice' : 'creditAmount',
    methodField: isRefund ? 'refundMethod' : 'creditNoteMethod',
    typeField: isRefund ? 'refundType' : 'creditNoteType',
    netField: isRefund ? 'netRefund' : 'netCreditNote',
    historyPath: isRefund ? '/admin/refund-history' : '/admin/credit-note-history',
    saveLabel: isRefund ? 'Process Refund' : 'Process Credit Note',
    summaryTitle: isRefund ? 'Refund Summary' : 'Credit Note Summary',
    netLabel: isRefund ? 'Net Refund' : 'Net Credit Note',
    apiCreate: isRefund ? api.createRefund : api.createCreditNote,
    PrintPreview: isRefund ? RefundPrintPreview : CreditNotePrintPreview,
    testId: isRefund ? 'refund-page' : 'creditNote-page'
  };

  // Document data
  const [documentData, setDocumentData] = useState({
    [config.numberField]: generateDocNo(config.prefix),
    date: new Date().toLocaleDateString('en-GB'),
    time: new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
    originalInvoiceNo: '',
    originalInvoiceId: '',
    customerName: '',
    customerPhone: '',
    customerEmail: '',
    customerAddress: '',
    salesPerson: user?.name || '',
    [config.methodField]: '',
    [config.typeField]: '',
    notes: '',
    lineItems: [{ ...emptyLineItem }],
    companyInfo: { ...defaultCompanyInfo },
    restockingFeePercent: 0
  });

  // Check if user can switch showrooms
  const canFreelySwitchStores = user?.role === 'super_admin' || user?.role === 'admin' || user?.role === 'manager';
  
  // Filter showrooms based on user role and assignment
  const availableStores = showrooms.filter(showroom => {
    if (user?.role === 'super_admin' || user?.role === 'admin' || user?.role === 'manager') {
      return true;
    }
    if (user?.showroom_id) {
      return showroom.id === user.showroom_id;
    }
    return false;
  });

  // Load data
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [productsRes, showroomsRes] = await Promise.all([
          api.getProducts(),
          api.getStores()
        ]);
        setProducts(productsRes.data);
        setStores(showroomsRes.data);
        
        // Set default showroom if user has one
        if (user?.showroom_id) {
          const userStore = showroomsRes.data.find(s => s.id === user.showroom_id);
          if (userStore) {
            setSelectedStore(userStore);
            setDocumentData(prev => ({
              ...prev,
              companyInfo: {
                ...prev.companyInfo,
                address: userStore.address?.split(',')[0] || prev.companyInfo.address,
                city: userStore.address?.split(',').slice(1).join(',').trim() || prev.companyInfo.city,
                telephone: userStore.phone || prev.companyInfo.telephone,
                email: userStore.email || prev.companyInfo.email
              }
            }));
          }
        } else if (showroomsRes.data?.length > 0) {
          setSelectedStore(showroomsRes.data[0]);
        }
      } catch (error) {
        console.error('Failed to load data', error);
      }
    };
    fetchData();
  }, [user?.showroom_id]);

  // Search invoices for linking
  const searchInvoices = async (term) => {
    if (term.length < 2) {
      setInvoiceSearchResults([]);
      return;
    }
    try {
      const res = await api.getInvoices({ search: term });
      setInvoiceSearchResults(res.data.slice(0, 10));
    } catch (error) {
      console.error('Failed to search invoices', error);
    }
  };

  // Select invoice to link
  const selectInvoice = (invoice) => {
    setDocumentData(prev => ({
      ...prev,
      originalInvoiceNo: invoice.invoice_no,
      originalInvoiceId: invoice.id,
      customerName: invoice.customer_name || '',
      customerPhone: invoice.customer_phone || '',
      customerEmail: invoice.customer_email || '',
      customerAddress: invoice.customer_address || ''
    }));
    setShowInvoiceSearch(false);
    setInvoiceSearchTerm('');
    setInvoiceSearchResults([]);
    toast.success(`Linked to invoice ${invoice.invoice_no}`);
  };

  // Calculate totals
  const calculateTotals = () => {
    const validItems = documentData.lineItems.filter(item => 
      item.product && parseFloat(item.qty) > 0 && parseFloat(item.adjustedPrice) >= 0
    );
    
    const subtotal = validItems.reduce((sum, item) => {
      const qty = parseFloat(item.qty) || 0;
      const price = parseFloat(item.adjustedPrice) || 0;
      return sum + (qty * price);
    }, 0);
    
    const vat = subtotal * 0.2;
    const grossTotal = subtotal + vat;
    const restockingFee = grossTotal * (documentData.restockingFeePercent / 100);
    const netAmount = grossTotal - restockingFee;
    
    return { subtotal, vat, grossTotal, restockingFee, [config.netField]: netAmount, netAmount };
  };

  const totals = calculateTotals();

  // Line item handlers
  const updateLineItem = (index, field, value) => {
    setDocumentData(prev => {
      const newItems = [...prev.lineItems];
      newItems[index] = { ...newItems[index], [field]: value };
      return { ...prev, lineItems: newItems };
    });
  };

  const addLineItem = () => {
    setDocumentData(prev => ({
      ...prev,
      lineItems: [...prev.lineItems, { ...emptyLineItem }]
    }));
  };

  const removeLineItem = (index) => {
    if (documentData.lineItems.length > 1) {
      setDocumentData(prev => ({
        ...prev,
        lineItems: prev.lineItems.filter((_, i) => i !== index)
      }));
    }
  };

  // Product search
  const filteredProducts = products.filter(p =>
    p.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.sku?.toLowerCase().includes(searchTerm.toLowerCase())
  ).slice(0, 10);

  const selectProduct = (product, index) => {
    updateLineItem(index, 'product', product.name);
    updateLineItem(index, 'productId', product.id);
    updateLineItem(index, 'sku', product.sku || '');
    updateLineItem(index, 'originalPrice', product.price?.toString() || '');
    updateLineItem(index, 'adjustedPrice', product.price?.toString() || '');
    setSearchTerm('');
    setActiveLineIndex(null);
  };

  // Verify staff PIN
  const verifyPin = async () => {
    if (staffPin.length < 4) {
      toast.error('Please enter a valid PIN');
      return;
    }
    setVerifyingPin(true);
    try {
      const res = await api.verifyStaffPin(staffPin);
      setVerifiedStaff(res.data);
      setShowPinDialog(false);
      setStaffPin('');
      toast.success(`Verified: ${res.data.name || res.data.staff_name}`);
    } catch (error) {
      toast.error('Invalid PIN');
      setStaffPin('');
    } finally {
      setVerifyingPin(false);
    }
  };

  // Handle store change
  const handleStoreChange = (showroomId) => {
    const showroom = showrooms.find(s => s.id === showroomId);
    setSelectedStore(showroom || null);
    if (showroom) {
      setDocumentData(prev => ({
        ...prev,
        companyInfo: {
          ...prev.companyInfo,
          address: showroom.address?.split(',')[0] || prev.companyInfo.address,
          city: showroom.address?.split(',').slice(1).join(',').trim() || prev.companyInfo.city,
          telephone: showroom.phone || prev.companyInfo.telephone,
          email: showroom.email || prev.companyInfo.email
        }
      }));
    }
  };

  // Save document
  const handleSave = async () => {
    // Require PIN verification
    if (!verifiedStaff) {
      toast.error('Staff PIN verification is required to save');
      setShowPinDialog(true);
      return;
    }
    
    // Validation
    const validItems = documentData.lineItems.filter(item => 
      item.product && parseFloat(item.qty) > 0 && parseFloat(item.adjustedPrice) >= 0
    );
    
    if (validItems.length === 0) {
      toast.error('Please add at least one item');
      return;
    }
    
    if (!documentData[config.methodField]) {
      toast.error(`Please select a ${isRefund ? 'refund' : 'credit note'} method`);
      return;
    }
    
    setSaving(true);
    try {
      const payload = isRefund ? {
        refund_no: documentData[config.numberField],
        date: documentData.date,
        time: documentData.time,
        original_invoice_no: documentData.originalInvoiceNo || null,
        original_invoice_id: documentData.originalInvoiceId || null,
        customer_name: documentData.customerName,
        customer_phone: documentData.customerPhone,
        customer_email: documentData.customerEmail,
        customer_address: documentData.customerAddress,
        notes: documentData.notes,
        sales_person: verifiedStaff?.name || verifiedStaff?.staff_name,
        staff_pin: staffPin || null,
        refund_method: documentData[config.methodField],
        refund_type: documentData[config.typeField],
        showroom_id: selectedStore?.id || null,
        showroom_name: selectedStore?.name || null,
        line_items: validItems.map(item => ({
          product_id: item.productId || null,
          product_name: item.product,
          sku: item.sku || null,
          quantity: parseFloat(item.qty),
          original_price: parseFloat(item.originalPrice) || 0,
          refund_price: parseFloat(item.adjustedPrice) || 0,
          total: parseFloat(item.qty) * parseFloat(item.adjustedPrice),
          reason: item.reason || ''
        })),
        subtotal: totals.subtotal,
        vat: totals.vat,
        gross_total: totals.grossTotal,
        restocking_fee: totals.restockingFee,
        net_refund: totals.netAmount
      } : {
        credit_note_no: documentData[config.numberField],
        date: documentData.date,
        time: documentData.time,
        original_invoice_no: documentData.originalInvoiceNo || null,
        original_invoice_id: documentData.originalInvoiceId || null,
        customer_name: documentData.customerName,
        customer_phone: documentData.customerPhone,
        customer_email: documentData.customerEmail,
        customer_address: documentData.customerAddress,
        notes: documentData.notes,
        sales_person: verifiedStaff?.name || verifiedStaff?.staff_name,
        staff_pin: staffPin || null,
        creditNote_method: documentData[config.methodField],
        creditNote_type: documentData[config.typeField],
        showroom_id: selectedStore?.id || null,
        showroom_name: selectedStore?.name || null,
        line_items: validItems.map(item => ({
          product_id: item.productId || null,
          product_name: item.product,
          sku: item.sku || null,
          quantity: parseFloat(item.qty),
          original_price: parseFloat(item.originalPrice) || 0,
          credit_note_price: parseFloat(item.adjustedPrice) || 0,
          total: parseFloat(item.qty) * parseFloat(item.adjustedPrice),
          reason: item.reason || ''
        })),
        subtotal: totals.subtotal,
        vat: totals.vat,
        gross_total: totals.grossTotal,
        restocking_fee: totals.restockingFee,
        net_creditNote: totals.netAmount
      };
      
      const res = await config.apiCreate(payload);
      const docNo = isRefund ? res.data.refund_no : res.data.credit_note_no;
      toast.success(`${isRefund ? 'Refund' : 'Credit Note'} ${docNo} processed successfully!`);
      
      // Reset form
      handleNew();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || `Failed to process ${isRefund ? 'refund' : 'credit note'}`;
      toast.error(errorMsg);
    } finally {
      setSaving(false);
    }
  };

  // New document
  const handleNew = () => {
    const prefix = selectedStore ? 
      (isRefund ? 'REF' : selectedStore.name.substring(0, 3).toUpperCase()) : config.prefix;
    
    setDocumentData({
      [config.numberField]: generateDocNo(prefix),
      date: new Date().toLocaleDateString('en-GB'),
      time: new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
      originalInvoiceNo: '',
      originalInvoiceId: '',
      customerName: '',
      customerPhone: '',
      customerEmail: '',
      customerAddress: '',
      salesPerson: verifiedStaff?.name || user?.name || '',
      [config.methodField]: '',
      [config.typeField]: '',
      notes: '',
      lineItems: [{ ...emptyLineItem }],
      companyInfo: { ...defaultCompanyInfo },
      restockingFeePercent: 0
    });
  };

  // Print
  const handlePrint = () => {
    window.print();
  };

  // Prepare data for print preview (map field names)
  const preparePreviewData = () => {
    if (isRefund) {
      return {
        refundNo: documentData[config.numberField],
        date: documentData.date,
        time: documentData.time,
        originalInvoiceNo: documentData.originalInvoiceNo,
        customerName: documentData.customerName,
        customerPhone: documentData.customerPhone,
        customerEmail: documentData.customerEmail,
        customerAddress: documentData.customerAddress,
        refundMethod: documentData[config.methodField],
        refundType: documentData[config.typeField],
        notes: documentData.notes,
        lineItems: documentData.lineItems.map(item => ({
          ...item,
          refundPrice: item.adjustedPrice
        })),
        companyInfo: documentData.companyInfo,
        restockingFeePercent: documentData.restockingFeePercent
      };
    } else {
      return {
        creditNoteNo: documentData[config.numberField],
        date: documentData.date,
        time: documentData.time,
        originalInvoiceNo: documentData.originalInvoiceNo,
        customerName: documentData.customerName,
        customerPhone: documentData.customerPhone,
        customerEmail: documentData.customerEmail,
        customerAddress: documentData.customerAddress,
        creditNoteMethod: documentData[config.methodField],
        creditNoteType: documentData[config.typeField],
        notes: documentData.notes,
        lineItems: documentData.lineItems.map(item => ({
          ...item,
          creditAmount: item.adjustedPrice
        })),
        companyInfo: documentData.companyInfo,
        restockingFeePercent: documentData.restockingFeePercent
      };
    }
  };

  const IconComponent = config.icon;

  return (
    <div className="space-y-6 pb-8" data-testid={config.testId}>
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/admin/epos')}>
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to EPOS
          </Button>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <IconComponent className={`h-6 w-6 ${config.iconColor}`} />
            {config.title}
          </h1>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(config.historyPath)}>
            <History className="h-4 w-4 mr-1" /> History
          </Button>
          <Button variant="outline" onClick={handleNew}>
            <Plus className="h-4 w-4 mr-1" /> New
          </Button>
          <Button variant="outline" onClick={handlePrint}>
            <Printer className="h-4 w-4 mr-1" /> Print
          </Button>
          <Button onClick={handleSave} disabled={saving} className="bg-red-600 hover:bg-red-700">
            <Save className="h-4 w-4 mr-1" /> {saving ? 'Processing...' : config.saveLabel}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Left Column - Form */}
        <div className="col-span-2 space-y-6">
          {/* Document Details */}
          <Card className="p-6">
            <h3 className="font-bold mb-4 flex items-center gap-2">
              <Receipt className="h-5 w-5" /> {isRefund ? 'Refund' : 'Credit Note'} Details
            </h3>
            <div className="grid grid-cols-4 gap-4">
              <div>
                <label className="text-xs text-muted-foreground">{isRefund ? 'Refund' : 'Credit Note'} No</label>
                <Input 
                  value={documentData[config.numberField]} 
                  onChange={(e) => setDocumentData(prev => ({ ...prev, [config.numberField]: e.target.value }))}
                  className="font-mono"
                  data-testid={`${documentType}-no-input`}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Date</label>
                <Input 
                  value={documentData.date} 
                  onChange={(e) => setDocumentData(prev => ({ ...prev, date: e.target.value }))}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">{isRefund ? 'Refund' : 'Credit Note'} Method</label>
                <select 
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  value={documentData[config.methodField]}
                  onChange={(e) => setDocumentData(prev => ({ ...prev, [config.methodField]: e.target.value }))}
                  data-testid={`${documentType}-method-select`}
                >
                  <option value="">Select Method</option>
                  {paymentMethods.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">{isRefund ? 'Refund' : 'Credit Note'} Type</label>
                <select 
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  value={documentData[config.typeField]}
                  onChange={(e) => setDocumentData(prev => ({ ...prev, [config.typeField]: e.target.value }))}
                >
                  <option value="">Select Type</option>
                  {documentTypes.map(t => <option key={t} value={`${t} ${isRefund ? 'Refund' : 'Credit Note'}`}>{t} {isRefund ? 'Refund' : 'Credit Note'}</option>)}
                </select>
              </div>
            </div>
            
            {/* Link to Original Invoice */}
            <div className="mt-4">
              <label className="text-xs text-muted-foreground">Original Invoice (Optional)</label>
              <div className="relative">
                <Input 
                  placeholder="Search invoice by number or customer..."
                  value={invoiceSearchTerm || documentData.originalInvoiceNo}
                  onChange={(e) => {
                    setInvoiceSearchTerm(e.target.value);
                    searchInvoices(e.target.value);
                    setShowInvoiceSearch(true);
                  }}
                  onFocus={() => setShowInvoiceSearch(true)}
                />
                {showInvoiceSearch && invoiceSearchResults.length > 0 && (
                  <div className="absolute z-10 w-full bg-white border rounded-md shadow-lg mt-1 max-h-60 overflow-y-auto">
                    {invoiceSearchResults.map(inv => (
                      <div 
                        key={inv.id}
                        className="p-3 hover:bg-gray-100 cursor-pointer border-b"
                        onClick={() => selectInvoice(inv)}
                      >
                        <div className="font-medium">{inv.invoice_no}</div>
                        <div className="text-xs text-muted-foreground">
                          {inv.customer_name} • {inv.date} • £{inv.gross_total?.toFixed(2)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {documentData.originalInvoiceNo && (
                <div className="mt-2 text-sm text-green-600">
                  ✓ Linked to: {documentData.originalInvoiceNo}
                </div>
              )}
            </div>
          </Card>

          {/* Customer Details */}
          <Card className="p-6">
            <h3 className="font-bold mb-4">Customer Details</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-muted-foreground">Customer Name</label>
                <Input 
                  value={documentData.customerName}
                  onChange={(e) => setDocumentData(prev => ({ ...prev, customerName: e.target.value }))}
                  placeholder="Customer name"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Phone</label>
                <Input 
                  value={documentData.customerPhone}
                  onChange={(e) => setDocumentData(prev => ({ ...prev, customerPhone: e.target.value }))}
                  placeholder="Phone number"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Email</label>
                <Input 
                  value={documentData.customerEmail}
                  onChange={(e) => setDocumentData(prev => ({ ...prev, customerEmail: e.target.value }))}
                  placeholder="Email address"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Address</label>
                <Input 
                  value={documentData.customerAddress}
                  onChange={(e) => setDocumentData(prev => ({ ...prev, customerAddress: e.target.value }))}
                  placeholder="Address"
                />
              </div>
            </div>
          </Card>

          {/* Line Items */}
          <Card className="p-6">
            <h3 className="font-bold mb-4">{isRefund ? 'Refund' : 'Credit Note'} Items</h3>
            <table className="w-full">
              <thead>
                <tr className="text-xs text-muted-foreground border-b">
                  <th className="text-left pb-2 w-12">Qty</th>
                  <th className="text-left pb-2">Product</th>
                  <th className="text-left pb-2 w-24">Original £</th>
                  <th className="text-left pb-2 w-24">{isRefund ? 'Refund' : 'Credit'} £</th>
                  <th className="text-left pb-2 w-32">Reason</th>
                  <th className="text-right pb-2 w-24">Total</th>
                  <th className="w-8"></th>
                </tr>
              </thead>
              <tbody>
                {documentData.lineItems.map((item, index) => (
                  <tr key={index} className="border-b">
                    <td className="py-2">
                      <Input
                        type="number"
                        value={item.qty}
                        onChange={(e) => updateLineItem(index, 'qty', e.target.value)}
                        className="w-16 text-center"
                        min="0"
                      />
                    </td>
                    <td className="py-2 relative">
                      <Input
                        value={item.product}
                        onChange={(e) => {
                          updateLineItem(index, 'product', e.target.value);
                          setSearchTerm(e.target.value);
                          setActiveLineIndex(index);
                        }}
                        onFocus={() => setActiveLineIndex(index)}
                        placeholder="Search product..."
                      />
                      {activeLineIndex === index && searchTerm && filteredProducts.length > 0 && (
                        <div className="absolute z-10 w-full bg-white border rounded-md shadow-lg mt-1 max-h-48 overflow-y-auto">
                          {filteredProducts.map(p => (
                            <div 
                              key={p.id}
                              className="p-2 hover:bg-gray-100 cursor-pointer text-sm"
                              onClick={() => selectProduct(p, index)}
                            >
                              <div className="font-medium">{p.name}</div>
                              <div className="text-xs text-muted-foreground">
                                {p.sku} • £{p.price?.toFixed(2)}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="py-2">
                      <Input
                        type="number"
                        value={item.originalPrice}
                        onChange={(e) => updateLineItem(index, 'originalPrice', e.target.value)}
                        className="w-24"
                        step="0.01"
                        readOnly
                      />
                    </td>
                    <td className="py-2">
                      <Input
                        type="number"
                        value={item.adjustedPrice}
                        onChange={(e) => updateLineItem(index, 'adjustedPrice', e.target.value)}
                        className="w-24"
                        step="0.01"
                      />
                    </td>
                    <td className="py-2">
                      <select
                        className="w-full px-2 py-1 border rounded text-sm"
                        value={item.reason}
                        onChange={(e) => updateLineItem(index, 'reason', e.target.value)}
                      >
                        <option value="">Select reason</option>
                        <option value="Damaged">Damaged</option>
                        <option value="Wrong item">Wrong item</option>
                        <option value="Not needed">Not needed</option>
                        <option value="Quality issue">Quality issue</option>
                        <option value="Other">Other</option>
                      </select>
                    </td>
                    <td className="py-2 text-right font-medium">
                      £{((parseFloat(item.qty) || 0) * (parseFloat(item.adjustedPrice) || 0)).toFixed(2)}
                    </td>
                    <td className="py-2">
                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={() => removeLineItem(index)}
                        disabled={documentData.lineItems.length === 1}
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Button variant="outline" className="mt-4" onClick={addLineItem}>
              <Plus className="h-4 w-4 mr-1" /> Add Item
            </Button>
          </Card>

          {/* Notes */}
          <Card className="p-6">
            <h3 className="font-bold mb-4">Notes</h3>
            <textarea
              className="w-full p-3 border rounded-md text-sm"
              rows={3}
              value={documentData.notes}
              onChange={(e) => setDocumentData(prev => ({ ...prev, notes: e.target.value }))}
              placeholder={`Add any notes about this ${isRefund ? 'refund' : 'credit note'}...`}
            />
          </Card>
        </div>

        {/* Right Column - Summary */}
        <div className="space-y-6">
          {/* Store Selection */}
          <Card className="p-6">
            <h3 className="font-bold mb-4 flex items-center gap-2">
              <Building2 className="h-5 w-5" /> Store
              {!canFreelySwitchStores && user?.showroom_id && (
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Lock className="h-3 w-3" /> Your showroom
                </span>
              )}
            </h3>
            <select
              className="w-full px-3 py-2 border rounded-md"
              value={selectedStore?.id || ''}
              onChange={(e) => handleStoreChange(e.target.value)}
              disabled={!canFreelySwitchStores && user?.showroom_id}
            >
              <option value="">Select Store</option>
              {availableStores.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </Card>

          {/* Restocking Fee */}
          <Card className="p-6">
            <h3 className="font-bold mb-4">Restocking Fee</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">Fee Percentage</span>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    value={documentData.restockingFeePercent}
                    onChange={(e) => setDocumentData(prev => ({ 
                      ...prev, 
                      restockingFeePercent: Math.min(100, Math.max(0, parseFloat(e.target.value) || 0))
                    }))}
                    className="w-20 text-center"
                    min="0"
                    max="100"
                  />
                  <span className="text-sm">%</span>
                </div>
              </div>
              <div className="text-xs text-muted-foreground space-y-1">
                <p>• Stocked Tiles: 20%</p>
                <p>• Special Order: 50%</p>
                <p>• Bathroom Products: Non-refundable</p>
              </div>
            </div>
          </Card>

          {/* Summary */}
          <Card className="p-6 bg-red-50 border-red-200">
            <h3 className="font-bold mb-4 text-red-800">{config.summaryTitle}</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span>Subtotal</span>
                <span>£{totals.subtotal.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span>VAT (20%)</span>
                <span>£{totals.vat.toFixed(2)}</span>
              </div>
              <div className="flex justify-between font-medium">
                <span>Gross Total</span>
                <span>£{totals.grossTotal.toFixed(2)}</span>
              </div>
              {totals.restockingFee > 0 && (
                <div className="flex justify-between text-orange-600">
                  <span>Restocking Fee ({documentData.restockingFeePercent}%)</span>
                  <span>-£{totals.restockingFee.toFixed(2)}</span>
                </div>
              )}
              <div className="border-t pt-2 mt-2">
                <div className="flex justify-between text-lg font-bold text-red-700">
                  <span>{config.netLabel}</span>
                  <span>£{totals.netAmount.toFixed(2)}</span>
                </div>
              </div>
            </div>
          </Card>

          {/* Staff Verification */}
          <Card className="p-6">
            <h3 className="font-bold mb-4">Staff Verification</h3>
            {verifiedStaff ? (
              <div className="text-green-600 text-sm">
                ✓ Verified: {verifiedStaff.name || verifiedStaff.staff_name}
              </div>
            ) : (
              <Button variant="outline" className="w-full" onClick={() => setShowPinDialog(true)}>
                Verify Staff PIN
              </Button>
            )}
          </Card>
        </div>
      </div>

      {/* Print Preview Section */}
      <div className="mt-8 print:mt-0">
        <h2 className="text-lg font-bold mb-4 print:hidden">Print Preview</h2>
        {isRefund ? (
          <RefundPrintPreview 
            printRef={printRef}
            refundData={preparePreviewData()}
            totals={totals}
          />
        ) : (
          <CreditNotePrintPreview 
            printRef={printRef}
            creditNoteData={preparePreviewData()}
            totals={totals}
          />
        )}
      </div>

      {/* Staff PIN Dialog */}
      <Dialog open={showPinDialog} onOpenChange={setShowPinDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Enter Staff PIN</DialogTitle>
            <DialogDescription>Verify your identity to process this {isRefund ? 'refund' : 'credit note'}.</DialogDescription>
          </DialogHeader>
          <Input
            type="password"
            value={staffPin}
            onChange={(e) => setStaffPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
            placeholder="Enter PIN"
            className="text-center text-2xl tracking-widest"
            onKeyPress={(e) => e.key === 'Enter' && verifyPin()}
            autoFocus
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowPinDialog(false)}>Cancel</Button>
            <Button onClick={verifyPin} disabled={verifyingPin}>
              {verifyingPin ? 'Verifying...' : 'Verify'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default CreditRefundForm;
