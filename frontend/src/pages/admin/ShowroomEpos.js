import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { toast } from 'sonner';
import { 
  FileText, 
  Printer, 
  Save, 
  Plus, 
  Trash2, 
  Search, 
  User, 
  Building2,
  History,
  ArrowLeft,
  Lock,
  CheckCircle,
  Shield
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
import { api } from '../../lib/api';
import { InvoiceLineItemsTable, InvoicePrintPreview, InvoiceDepositsSection } from '../../components/invoice';

const defaultCompanyInfo = {
  name: 'Tile Station',
  address: 'Unit 3 Trade City, Coldharbour Road',
  city: 'Northfleet Gravesend DA11 8AB',
  telephone: '01234 567 890',
  email: 'info@tilestation.co.uk',
  companyNo: '00000000',
  vatNo: '000 0000 00'
};

const defaultTerms = `• Any unwanted Full packs of STOCKED TILES will occur a 20% re-stocking fee
• No refund will be given for Special Order Tiles
• Payment of the balance must be paid before collection
• Please ensure that you have ordered enough as colour matches cannot be guaranteed
• Please examine tiles before laying. Once laid, we cannot accept any claims
• Goods must be collected/delivered within 3 months of the order being placed`;

const emptyLineItem = {
  qty: '',
  m2: '',
  product: '',
  price: '',
  duePrice: '',
  discount: 0,
  productId: '',
  sku: '',
  stock: 0,
  tile_m2_per_piece: null,
  max_discount: null
};

const paymentMethods = ['Card', 'Cash', 'Bank Transfer', 'Link Payment', 'Finance'];
const orderTypes = ['Store Order', 'Delivery', 'Deposit Order', 'Special Order', 'Click & Collect'];

// Capitalize first letter of every word (Title Case)
const toTitleCase = (str) => {
  if (!str) return '';
  return str.replace(/\b\w/g, char => char.toUpperCase());
};

// Generate showroom-specific invoice number
const generateInvoiceNo = (showroomPrefix) => {
  const now = new Date();
  const dateStr = now.toISOString().slice(2, 10).replace(/-/g, '');
  const timeStr = now.getHours().toString().padStart(2, '0') + now.getMinutes().toString().padStart(2, '0');
  const random = Math.floor(Math.random() * 100).toString().padStart(2, '0');
  return `${showroomPrefix}-${dateStr}${timeStr}${random}`;
};

// Get showroom prefix for invoice numbers
const getStorePrefix = (showroomName) => {
  const prefixes = {
    'gravesend': 'GRV',
    'tonbridge': 'TNB',
    'chingford': 'CHG',
    'sydenham': 'SYD'
  };
  return prefixes[showroomName?.toLowerCase()] || showroomName?.substring(0, 3).toUpperCase() || 'INV';
};

export const ShowroomEpos = () => {
  const { showroomSlug } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const printRef = useRef();
  const { user } = useAuth();
  
  const [showroom, setStore] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [products, setProducts] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeLineIndex, setActiveLineIndex] = useState(null);
  const [customerSearchTerm, setCustomerSearchTerm] = useState('');
  const [showCustomerSearch, setShowCustomerSearch] = useState(false);
  
  // Staff PIN states
  const [staffPin, setStaffPin] = useState('');
  const [verifiedStaff, setVerifiedStaff] = useState(null);
  const [showPinDialog, setShowPinDialog] = useState(false);
  const [verifyingPin, setVerifyingPin] = useState(false);
  
  // Day lock state - requires PIN on page load
  const [showDayLockDialog, setShowDayLockDialog] = useState(false);
  const [dayLockPin, setDayLockPin] = useState('');
  const [isDayLocked, setIsDayLocked] = useState(false);
  const [lockedByStaff, setLockedByStaff] = useState(null);
  
  // Check if user is super_admin or admin (can bypass day lock)
  const canBypassDayLock = user?.role === 'super_admin' || user?.role === 'admin';
  
  // Invoice data
  const [invoiceData, setInvoiceData] = useState({
    invoiceNo: '',
    date: new Date().toLocaleDateString('en-GB'),
    time: new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
    customerName: '',
    customerPhone: '',
    customerEmail: '',
    customerAddress: '',
    salesPerson: user?.name || '',
    paymentMethod: '',
    orderType: '',
    notes: '',
    deposits: [{ date: new Date().toLocaleDateString('en-GB'), amount: '', method: '', note: '' }],
    lineItems: [{ ...emptyLineItem }],
    companyInfo: { ...defaultCompanyInfo },
    termsAndConditions: defaultTerms
  });

  // Check for existing day lock in localStorage
  useEffect(() => {
    if (showroom && !canBypassDayLock) {
      const today = new Date().toLocaleDateString('en-GB');
      const lockKey = `showroom_lock_${showroom.id}_${today}`;
      const savedLock = localStorage.getItem(lockKey);
      
      if (savedLock) {
        try {
          const lockData = JSON.parse(savedLock);
          setIsDayLocked(true);
          setLockedByStaff(lockData);
          setVerifiedStaff(lockData);
          setInvoiceData(prev => ({
            ...prev,
            salesPerson: lockData.staff_name || ''
          }));
        } catch (e) {
          // Invalid data, show lock dialog
          setShowDayLockDialog(true);
        }
      } else {
        // No lock for today, show dialog
        setShowDayLockDialog(true);
      }
    }
  }, [showroom, canBypassDayLock]);

  // Load showroom data
  useEffect(() => {
    const fetchStoreData = async () => {
      try {
        const [showroomsRes, productsRes, customersRes] = await Promise.all([
          api.getStores(),
          api.getProducts(),
          api.getCustomers().catch(() => ({ data: [] }))
        ]);
        
        // Find showroom by slug
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
          // Staff is trying to access a showroom they're not assigned to
          const assignedStore = showroomsRes.data.find(s => s.id === userStoreId);
          const assignedName = assignedStore?.name || 'your assigned showroom';
          toast.error(`Access denied. You can only access ${assignedName}.`);
          
          // Redirect to their assigned showroom
          if (assignedStore) {
            const assignedSlug = assignedStore.name.toLowerCase().replace(/\s+/g, '-');
            navigate(`/admin/showroom/${assignedSlug}/epos`);
          } else {
            navigate('/admin');
          }
          return;
        }
        
        setStore(foundStore);
        setProducts(productsRes.data);
        setCustomers(customersRes.data || []);
        
        // Set showroom-specific invoice number and company info
        const prefix = getStorePrefix(foundStore.name);
        setInvoiceData(prev => ({
          ...prev,
          invoiceNo: generateInvoiceNo(prefix),
          companyInfo: {
            ...defaultCompanyInfo,
            name: 'Tile Station - ' + foundStore.name,
            address: foundStore.address?.split(',')[0] || defaultCompanyInfo.address,
            city: foundStore.address?.split(',').slice(1).join(',').trim() || defaultCompanyInfo.city,
            telephone: foundStore.phone || defaultCompanyInfo.telephone,
            email: foundStore.email || defaultCompanyInfo.email
          }
        }));
        
      } catch (error) {
        toast.error('Failed to load showroom data');
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchStoreData();
  }, [showroomSlug, navigate, user?.role, user?.showroom_id]);

  // Handle day lock PIN verification
  const handleDayLockVerify = async () => {
    if (dayLockPin.length < 4) {
      toast.error('Please enter a valid PIN');
      return;
    }
    
    setVerifyingPin(true);
    try {
      const res = await api.verifyStaffPin(dayLockPin);
      const staffData = {
        ...res.data,
        staff_name: res.data.name || res.data.staff_name
      };
      
      // Save day lock to localStorage
      const today = new Date().toLocaleDateString('en-GB');
      const lockKey = `showroom_lock_${showroom.id}_${today}`;
      localStorage.setItem(lockKey, JSON.stringify(staffData));
      
      setLockedByStaff(staffData);
      setVerifiedStaff(staffData);
      setIsDayLocked(true);
      setShowDayLockDialog(false);
      setDayLockPin('');
      
      // Update sales person
      setInvoiceData(prev => ({
        ...prev,
        salesPerson: staffData.staff_name || ''
      }));
      
      toast.success(`${showroom.name} locked for today by ${staffData.staff_name}`);
    } catch (error) {
      toast.error('Invalid PIN. Please try again.');
      setDayLockPin('');
    } finally {
      setVerifyingPin(false);
    }
  };

  // Handle cancel - go back to dashboard
  const handleCancelDayLock = () => {
    setShowDayLockDialog(false);
    navigate('/admin');
  };

  // Handle quotation conversion
  useEffect(() => {
    if (location.state?.fromQuotation && showroom) {
      const quotation = location.state.fromQuotation;
      const prefix = getStorePrefix(showroom.name);
      
      const lineItems = quotation.lineItems?.map(item => ({
        productId: item.productId || '',
        product: item.product || '',
        sku: item.sku || '',
        qty: item.qty || '',
        m2: item.m2 || '',
        price: item.price || '',
        duePrice: item.duePrice || item.price || '',
        discount: item.discount || 0,
        stock: item.stock || 0
      })) || [{ ...emptyLineItem }];
      
      setInvoiceData(prev => ({
        ...prev,
        invoiceNo: generateInvoiceNo(prefix),
        customerName: quotation.customerName || '',
        customerPhone: quotation.customerPhone || '',
        customerEmail: quotation.customerEmail || '',
        customerAddress: quotation.customerAddress || '',
        salesPerson: quotation.salesPerson || user?.name || '',
        notes: quotation.notes || '',
        lineItems
      }));
      
      toast.success('Quotation loaded - Complete the invoice details');
      window.history.replaceState({}, document.title);
    }
  }, [location.state, showroom, user]);

  // Calculate line item total
  const calculateLineTotal = (item) => {
    const qty = parseFloat(item.qty) || 0;
    const price = parseFloat(item.price) || 0;
    const duePrice = parseFloat(item.duePrice) || price;
    const listTotal = qty * price;
    const due = qty * duePrice;
    const savings = listTotal - due;
    const discountPercent = price > 0 ? ((price - duePrice) / price) * 100 : 0;
    return { listTotal, due, savings, discountPercent, duePrice };
  };

  // Calculate totals
  const calculateTotals = () => {
    let totalDue = 0;
    let totalList = 0;
    
    invoiceData.lineItems.forEach(item => {
      const calc = calculateLineTotal(item);
      totalDue += calc.due;
      totalList += calc.listTotal;
    });
    
    const totalSavings = totalList - totalDue;
    const vat = totalDue * 0.2;
    const grossTotal = totalDue + vat;
    const totalDeposits = invoiceData.deposits.reduce((sum, d) => sum + (parseFloat(d.amount) || 0), 0);
    const amountOutstanding = grossTotal - totalDeposits;
    
    return { totalDue, totalList, totalSavings, vat, grossTotal, totalDeposits, amountOutstanding };
  };

  const totals = calculateTotals();

  // Helper to clean None patterns from strings
  const cleanNonePatterns = (str) => {
    if (!str) return '';
    return str
      .replace(/\s*NonexNone\s*/gi, ' ')
      .replace(/\s*NoneXNone\s*/gi, ' ')
      .replace(/\s*None\s*x\s*None\s*/gi, ' ')
      .replace(/\s*xNone\s*/gi, ' ')
      .replace(/\s*Nonex\s*/gi, ' ')
      .replace(/\s*\(None\)\s*/gi, ' ')
      .replace(/\s*\(None\d*[Kk]?g?\)\s*/gi, ' ')
      .replace(/\s*None\s*[Kk]g\s*/gi, ' ')
      .replace(/\s+None\s*$/gi, '')
      .replace(/\s+/g, ' ')
      .trim();
  };

  // Select product
  const selectProduct = (index, product) => {
    const newItems = [...invoiceData.lineItems];
    // Build product display name with size/color if available
    let productDisplayName = cleanNonePatterns(toTitleCase(product.name));
    if (product.description) {
      const sizeMatch = product.description.match(/Size:\s*([^|]+)/i);
      const colorMatch = product.description.match(/Color:\s*([^|]+)/i);
      const extras = [];
      if (sizeMatch && !sizeMatch[1].includes('None')) extras.push(sizeMatch[1].trim());
      // Only add color if it's not already in the product name
      if (colorMatch && !colorMatch[1].includes('None')) {
        const colorValue = colorMatch[1].trim();
        if (!product.name.toLowerCase().includes(colorValue.toLowerCase())) {
          extras.push(colorValue);
        }
      }
      if (extras.length > 0) {
        productDisplayName += ` (${extras.join(', ')})`;
      }
    }
    newItems[index] = {
      ...newItems[index],
      productId: product.id,
      product: productDisplayName,
      sku: product.sku || '',
      price: product.price,
      duePrice: product.price,
      stock: product.stock,
      tile_m2_per_piece: product.tile_m2_per_piece || null,
      tiles_per_box: product.tiles_per_box || null,
      box_m2_coverage: product.box_m2_coverage || null,
      max_discount: product.max_discount || null
    };
    if (product.tile_m2_per_piece && newItems[index].qty) {
      const qty = parseFloat(newItems[index].qty) || 0;
      newItems[index].m2 = (qty * product.tile_m2_per_piece).toFixed(2);
    }
    setInvoiceData({ ...invoiceData, lineItems: newItems });
    setActiveLineIndex(null);
    setSearchTerm('');
  };

  // Update line item
  const updateLineItem = (index, field, value) => {
    const newItems = [...invoiceData.lineItems];
    newItems[index] = { ...newItems[index], [field]: value };
    
    if (field === 'qty' && newItems[index].tile_m2_per_piece) {
      const qty = parseFloat(value) || 0;
      newItems[index].m2 = (qty * newItems[index].tile_m2_per_piece).toFixed(2);
    }
    
    setInvoiceData({ ...invoiceData, lineItems: newItems });
  };

  // Add/remove line items
  const addLineItem = () => {
    setInvoiceData({
      ...invoiceData,
      lineItems: [...invoiceData.lineItems, { ...emptyLineItem }]
    });
  };

  const removeLineItem = (index) => {
    if (invoiceData.lineItems.length === 1) return;
    const newItems = invoiceData.lineItems.filter((_, i) => i !== index);
    setInvoiceData({ ...invoiceData, lineItems: newItems });
  };

  // Box info helpers
  const getBoxInfo = (item) => {
    if (!item.tiles_per_box || !item.qty) return null;
    const qty = parseFloat(item.qty) || 0;
    const tilesPerBox = parseInt(item.tiles_per_box);
    const fullBoxes = Math.floor(qty / tilesPerBox);
    const looseTiles = qty % tilesPerBox;
    return { fullBoxes, looseTiles, tilesPerBox };
  };

  const roundUpToBox = (index) => {
    const item = invoiceData.lineItems[index];
    if (!item.tiles_per_box || !item.qty) return;
    const currentQty = parseFloat(item.qty) || 0;
    const tilesPerBox = parseInt(item.tiles_per_box);
    const boxes = Math.ceil(currentQty / tilesPerBox);
    const roundedQty = boxes * tilesPerBox;
    updateLineItem(index, 'qty', roundedQty.toString());
  };

  // Deposit management
  const addDeposit = () => {
    setInvoiceData({
      ...invoiceData,
      deposits: [...invoiceData.deposits, { date: new Date().toLocaleDateString('en-GB'), amount: '', method: '', note: '' }]
    });
  };

  const updateDeposit = (index, field, value) => {
    const newDeposits = [...invoiceData.deposits];
    newDeposits[index] = { ...newDeposits[index], [field]: value };
    setInvoiceData({ ...invoiceData, deposits: newDeposits });
  };

  const removeDeposit = (index) => {
    if (invoiceData.deposits.length === 1) return;
    const newDeposits = invoiceData.deposits.filter((_, i) => i !== index);
    setInvoiceData({ ...invoiceData, deposits: newDeposits });
  };

  // Customer selection
  const selectCustomer = (customer) => {
    setInvoiceData({
      ...invoiceData,
      customerName: customer.name || '',
      customerPhone: customer.phone || '',
      customerEmail: customer.email || '',
      customerAddress: customer.address ? 
        `${customer.address.line1 || ''} ${customer.address.line2 || ''} ${customer.address.city || ''} ${customer.address.postcode || ''}`.trim() 
        : ''
    });
    setShowCustomerSearch(false);
    setCustomerSearchTerm('');
  };

  // Filter customers
  const filteredCustomers = customers.filter(c => {
    if (!customerSearchTerm) return true;
    const search = customerSearchTerm.toLowerCase();
    return (
      (c.name && c.name.toLowerCase().includes(search)) ||
      (c.email && c.email.toLowerCase().includes(search)) ||
      (c.phone && c.phone.toLowerCase().includes(search))
    );
  });

  // PIN verification
  const handleVerifyPin = async () => {
    if (staffPin.length < 4) {
      toast.error('Please enter a valid PIN');
      return;
    }
    
    setVerifyingPin(true);
    try {
      const verifiedPin = staffPin;
      const res = await api.verifyStaffPin(staffPin);
      const staffData = {
        ...res.data,
        staff_name: res.data.name || res.data.staff_name
      };
      setVerifiedStaff(staffData);
      setShowPinDialog(false);
      setStaffPin('');
      toast.success(`PIN verified: ${staffData.staff_name}`);
      
      await proceedWithSave(staffData, verifiedPin);
    } catch (error) {
      toast.error('Invalid PIN. Please try again.');
      setStaffPin('');
    } finally {
      setVerifyingPin(false);
    }
  };

  // Save invoice
  const handleSaveInvoice = async () => {
    // Validation
    if (!invoiceData.paymentMethod) {
      toast.error('Payment Method is required');
      return;
    }
    if (!invoiceData.orderType) {
      toast.error('Order Type is required');
      return;
    }
    
    // Validate that ALL deposits with amounts have a payment method selected
    const depositsWithAmounts = invoiceData.deposits.filter(d => d.amount && parseFloat(d.amount) > 0);
    
    // Each deposit with amount MUST have a method - method field only, not note
    for (let i = 0; i < depositsWithAmounts.length; i++) {
      const deposit = depositsWithAmounts[i];
      const hasMethod = deposit.method && deposit.method.trim() !== '';
      if (!hasMethod) {
        const amount = parseFloat(deposit.amount) || 0;
        toast.error(`Please select a Payment Method for payment ${i + 1} (£${amount.toFixed(2)})`);
        return;
      }
    }
    
    // If no sales person and no verified staff, show PIN dialog
    if (!invoiceData.salesPerson && !verifiedStaff) {
      setShowPinDialog(true);
      return;
    }
    
    await proceedWithSave(verifiedStaff);
  };

  const proceedWithSave = async (staffData = verifiedStaff, pinUsed = null) => {
    // Validate line items
    const validItems = invoiceData.lineItems.filter(item => 
      (item.productId || (item.product && item.product.trim())) && item.qty && parseFloat(item.qty) > 0
    );
    
    if (validItems.length === 0) {
      toast.error('Please add at least one product with quantity');
      return;
    }

    // Validate phone
    if (!invoiceData.customerPhone || invoiceData.customerPhone.replace(/\D/g, '').length < 10) {
      toast.error('Please enter a valid phone number');
      return;
    }

    setSaving(true);
    try {
      const salesPersonName = staffData?.staff_name || invoiceData.salesPerson;
      
      const payload = {
        invoice_no: invoiceData.invoiceNo,
        date: invoiceData.date,
        time: invoiceData.time,
        order_type: invoiceData.orderType,
        showroom_id: showroom.id,
        customer_name: invoiceData.customerName || null,
        customer_phone: invoiceData.customerPhone || null,
        customer_email: invoiceData.customerEmail || null,
        customer_address: invoiceData.customerAddress || null,
        sales_person: salesPersonName || null,
        payment_method: invoiceData.paymentMethod || null,
        notes: invoiceData.notes || null,
        staff_pin: staffData ? (pinUsed || staffPin || invoiceData.staffPin) : null,
        deposits: invoiceData.deposits
          .filter(d => d.amount && parseFloat(d.amount) > 0)
          .map(d => ({ 
            date: d.date, 
            amount: parseFloat(d.amount), 
            method: d.method || '', // Only use method field, not note
            note: d.note || '' 
          })),
        line_items: validItems.map(item => {
          const calc = calculateLineTotal(item);
          return {
            product_id: item.productId || null,
            product_name: item.product,
            sku: item.sku,
            quantity: parseFloat(item.qty),
            m2: parseFloat(item.m2) || 0,
            price: parseFloat(item.price),
            due_price: calc.duePrice,
            total: calc.due,
            discount: parseFloat(item.discount) || 0
          };
        }),
        subtotal: totals.totalDue,
        vat: totals.vat,
        gross_total: totals.grossTotal,
        total_deposits: totals.totalDeposits,
        amount_outstanding: totals.amountOutstanding,
        company_info: invoiceData.companyInfo,
        terms_and_conditions: invoiceData.termsAndConditions
      };

      await api.saveInvoice(payload);
      toast.success('Invoice saved successfully!');
      
      // Trigger cross-page data sync for Dashboard and Invoice History
      localStorage.setItem('dataSync', Date.now().toString());
      window.dispatchEvent(new CustomEvent('dataSync'));
      
      // Reset form with new invoice number
      const prefix = getStorePrefix(showroom.name);
      setInvoiceData({
        invoiceNo: generateInvoiceNo(prefix),
        date: new Date().toLocaleDateString('en-GB'),
        time: new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
        customerName: '',
        customerPhone: '',
        customerEmail: '',
        customerAddress: '',
        salesPerson: user?.name || '',
        paymentMethod: '',
        orderType: '',
        notes: '',
        deposits: [{ date: new Date().toLocaleDateString('en-GB'), amount: '', method: '', note: '' }],
        lineItems: [{ ...emptyLineItem }],
        companyInfo: invoiceData.companyInfo,
        termsAndConditions: defaultTerms
      });
      
    } catch (error) {
      const detail = error.response?.data?.detail;
      let errorMessage = 'Failed to save invoice';
      if (typeof detail === 'string') {
        errorMessage = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        errorMessage = detail[0]?.msg || 'Validation error';
      }
      toast.error(errorMessage);
    } finally {
      setSaving(false);
    }
  };

  // Print invoice
  const handlePrint = () => {
    const printContent = printRef.current;
    const printWindow = window.open('', '_blank');
    
    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Invoice ${invoiceData.invoiceNo}</title>
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
          body { font-family: Arial, sans-serif; padding: 20px; font-size: 12px; }
          table { width: 100%; border-collapse: collapse; margin: 20px 0; }
          th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
          th { background-color: #000 !important; color: #fff !important; font-weight: bold; }
          @media print { 
            * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
            th { background-color: #000 !important; color: #fff !important; }
          }
        </style>
      </head>
      <body>
        ${printContent.innerHTML}
      </body>
      </html>
    `);
    
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => {
      printWindow.print();
      printWindow.close();
    }, 250);
  };

  // New invoice
  const handleNewInvoice = () => {
    const prefix = getStorePrefix(showroom?.name);
    setInvoiceData({
      invoiceNo: generateInvoiceNo(prefix),
      date: new Date().toLocaleDateString('en-GB'),
      time: new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
      customerName: '',
      customerPhone: '',
      customerEmail: '',
      customerAddress: '',
      salesPerson: lockedByStaff?.staff_name || user?.name || '',
      paymentMethod: '',
      orderType: '',
      notes: '',
      deposits: [{ date: new Date().toLocaleDateString('en-GB'), amount: '', method: '', note: '' }],
      lineItems: [{ ...emptyLineItem }],
      companyInfo: invoiceData.companyInfo,
      termsAndConditions: defaultTerms
    });
    setVerifiedStaff(lockedByStaff || null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!showroom) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <p className="text-lg text-gray-500">Store not found</p>
        <Button onClick={() => navigate('/admin')} className="mt-4">
          Go Back
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-8">
      {/* Day Lock PIN Dialog */}
      <Dialog open={showDayLockDialog} onOpenChange={() => {}}>
        <DialogContent className="sm:max-w-md" onPointerDownOutside={(e) => e.preventDefault()}>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-primary" />
              Lock {showroom.name} for Today
            </DialogTitle>
            <DialogDescription>
              Enter your staff PIN to lock this showroom. All invoices created today will be assigned to you.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="p-4 bg-primary/5 border border-primary/20 rounded-lg">
              <div className="flex items-center gap-3">
                <Building2 className="h-8 w-8 text-primary" />
                <div>
                  <p className="font-bold text-lg">{showroom.name}</p>
                  <p className="text-sm text-muted-foreground">{showroom.address}</p>
                </div>
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium mb-2 block">Enter Your Staff PIN</label>
              <Input
                type="password"
                value={dayLockPin}
                onChange={(e) => setDayLockPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="Enter 4-6 digit PIN"
                maxLength={6}
                className="text-center text-2xl tracking-widest"
                onKeyPress={(e) => e.key === 'Enter' && handleDayLockVerify()}
                autoFocus
                data-testid="day-lock-pin-input"
              />
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={handleCancelDayLock}>
              Cancel
            </Button>
            <Button 
              onClick={handleDayLockVerify} 
              disabled={verifyingPin || dayLockPin.length < 4}
              data-testid="verify-day-lock-btn"
            >
              {verifyingPin ? 'Verifying...' : 'Lock & Continue'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/admin')}>
            <ArrowLeft className="h-4 w-4 mr-1" /> Back
          </Button>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Building2 className="h-6 w-6 text-primary" />
            {showroom.name} EPOS
          </h1>
          <span className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm font-medium">
            {getStorePrefix(showroom.name)}
          </span>
          {/* Day Lock Indicator */}
          {isDayLocked && lockedByStaff && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-green-100 text-green-800 rounded-full text-sm" data-testid="day-lock-indicator">
              <Lock className="h-4 w-4" />
              <span className="font-medium">Locked by {lockedByStaff.staff_name}</span>
            </div>
          )}
          {canBypassDayLock && !isDayLocked && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-100 text-blue-800 rounded-full text-sm">
              <CheckCircle className="h-4 w-4" />
              <span className="font-medium">Admin Access</span>
            </div>
          )}
        </div>
        <div className="flex gap-2">
          <Button 
            variant="outline" 
            onClick={() => navigate(`/admin/showroom/${showroomSlug}/invoices`)}
          >
            <History className="h-4 w-4 mr-1" /> Invoice History
          </Button>
          <Button variant="outline" onClick={handleNewInvoice}>
            <Plus className="h-4 w-4 mr-1" /> New
          </Button>
          <Button variant="outline" onClick={handlePrint}>
            <Printer className="h-4 w-4 mr-1" /> Print
          </Button>
          <Button onClick={handleSaveInvoice} disabled={saving}>
            <Save className="h-4 w-4 mr-1" /> {saving ? 'Saving...' : 'Save & Update Stock'}
          </Button>
        </div>
      </div>

      {/* Store Badge */}
      <Card className="bg-primary/5 border-primary/20">
        <CardContent className="py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Building2 className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium">{showroom.name}</p>
                <p className="text-sm text-muted-foreground">{showroom.address}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted-foreground">Invoice Prefix</p>
              <p className="font-mono font-bold text-primary">{getStorePrefix(showroom.name)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Form */}
        <div className="lg:col-span-2 space-y-6">
          {/* Invoice Details */}
          <Card>
            <CardHeader className="pb-4">
              <CardTitle className="text-lg">Invoice Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="text-sm font-medium mb-1 block">Invoice No</label>
                  <Input
                    value={invoiceData.invoiceNo}
                    onChange={(e) => setInvoiceData({ ...invoiceData, invoiceNo: e.target.value })}
                    className="font-mono"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-1 block">Date</label>
                  <Input
                    value={invoiceData.date}
                    onChange={(e) => setInvoiceData({ ...invoiceData, date: e.target.value })}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-1 block">Payment Method *</label>
                  <select
                    className="w-full px-3 py-2 border rounded-md"
                    value={invoiceData.paymentMethod}
                    onChange={(e) => setInvoiceData({ ...invoiceData, paymentMethod: e.target.value })}
                  >
                    <option value="">Select Payment Method</option>
                    {paymentMethods.map(method => (
                      <option key={method} value={method}>{method}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-sm font-medium mb-1 block">Order Type *</label>
                  <select
                    className="w-full px-3 py-2 border rounded-md"
                    value={invoiceData.orderType}
                    onChange={(e) => setInvoiceData({ ...invoiceData, orderType: e.target.value })}
                  >
                    <option value="">Select Order Type</option>
                    {orderTypes.map(type => (
                      <option key={type} value={type}>{type}</option>
                    ))}
                  </select>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium mb-1 block">
                    Sales Person {!verifiedStaff && <span className="text-xs text-muted-foreground">(or verify with Staff PIN)</span>}
                  </label>
                  <Input
                    value={verifiedStaff?.staff_name || invoiceData.salesPerson}
                    onChange={(e) => setInvoiceData({ ...invoiceData, salesPerson: e.target.value })}
                    placeholder="Sales person name"
                    disabled={!!verifiedStaff}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Customer Details */}
          <Card>
            <CardHeader className="pb-4">
              <div className="flex justify-between items-center">
                <CardTitle className="text-lg flex items-center gap-2">
                  <User className="h-5 w-5" /> Customer Details
                </CardTitle>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowCustomerSearch(!showCustomerSearch)}
                >
                  <Search className="h-4 w-4 mr-1" /> Find Customer
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {showCustomerSearch && (
                <div className="relative mb-4">
                  <Input
                    placeholder="Search by name, email, or phone..."
                    value={customerSearchTerm}
                    onChange={(e) => setCustomerSearchTerm(e.target.value)}
                    autoFocus
                  />
                  {customerSearchTerm && (
                    <div className="absolute z-50 top-full left-0 right-0 bg-white border rounded-md shadow-lg max-h-48 overflow-y-auto mt-1">
                      {filteredCustomers.length === 0 ? (
                        <div className="px-3 py-2 text-sm text-gray-500">No customers found</div>
                      ) : (
                        filteredCustomers.slice(0, 10).map(customer => (
                          <div
                            key={customer.email}
                            className="px-3 py-2 hover:bg-gray-100 cursor-pointer text-sm border-b"
                            onClick={() => selectCustomer(customer)}
                          >
                            <div className="font-medium">{customer.name}</div>
                            <div className="text-xs text-gray-500">{customer.email} • {customer.phone}</div>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium mb-1 block">Name</label>
                  <Input
                    value={invoiceData.customerName}
                    onChange={(e) => setInvoiceData({ ...invoiceData, customerName: e.target.value })}
                    onBlur={(e) => setInvoiceData({ ...invoiceData, customerName: toTitleCase(e.target.value) })}
                    placeholder="Customer name"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-1 block">Phone</label>
                  <Input
                    value={invoiceData.customerPhone}
                    onChange={(e) => setInvoiceData({ ...invoiceData, customerPhone: e.target.value })}
                    placeholder="Phone number"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-1 block">Email</label>
                  <Input
                    value={invoiceData.customerEmail}
                    onChange={(e) => setInvoiceData({ ...invoiceData, customerEmail: e.target.value })}
                    placeholder="Email address"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-1 block">Address</label>
                  <Input
                    value={invoiceData.customerAddress}
                    onChange={(e) => setInvoiceData({ ...invoiceData, customerAddress: e.target.value })}
                    onBlur={(e) => setInvoiceData({ ...invoiceData, customerAddress: toTitleCase(e.target.value) })}
                    placeholder="Address"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Line Items */}
          <Card>
            <CardContent className="pt-6">
              <InvoiceLineItemsTable
                lineItems={invoiceData.lineItems}
                products={products}
                searchTerm={searchTerm}
                activeLineIndex={activeLineIndex}
                authorizedDiscounts={{}}
                user={user}
                onSearchTermChange={setSearchTerm}
                onActiveLineIndexChange={setActiveLineIndex}
                onSelectProduct={selectProduct}
                onUpdateLineItem={updateLineItem}
                onAddLineItem={addLineItem}
                onRemoveLineItem={removeLineItem}
                onRoundUpToBox={roundUpToBox}
                calculateLineTotal={calculateLineTotal}
                getMinAllowedPrice={() => 0}
                isDiscountExceeded={() => false}
                getBoxInfo={getBoxInfo}
                totals={totals}
              />
            </CardContent>
          </Card>

          {/* Deposits */}
          <InvoiceDepositsSection
            deposits={invoiceData.deposits}
            totals={totals}
            onAddDeposit={addDeposit}
            onUpdateDeposit={updateDeposit}
            onRemoveDeposit={removeDeposit}
          />
        </div>

        {/* Right Column - Summary */}
        <div className="space-y-6">
          <Card className="sticky top-4">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg">Invoice Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Subtotal</span>
                  <span>£{totals.totalDue.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>VAT (20%)</span>
                  <span>£{totals.vat.toFixed(2)}</span>
                </div>
                <div className="flex justify-between font-bold text-lg border-t pt-2">
                  <span>Total</span>
                  <span>£{totals.grossTotal.toFixed(2)}</span>
                </div>
                {totals.totalDeposits > 0 && (
                  <>
                    <div className="flex justify-between text-sm text-green-600">
                      <span>Deposits Paid</span>
                      <span>-£{totals.totalDeposits.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between font-bold text-lg">
                      <span>Outstanding</span>
                      <span>£{totals.amountOutstanding.toFixed(2)}</span>
                    </div>
                  </>
                )}
              </div>
              
              {totals.totalSavings > 0 && (
                <div className="p-3 bg-green-50 rounded-lg text-center">
                  <p className="text-sm text-green-700 font-medium">
                    Customer Saves: £{totals.totalSavings.toFixed(2)}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Print Preview */}
      <Card className="mt-8">
        <CardHeader>
          <CardTitle className="text-lg">Print Preview</CardTitle>
        </CardHeader>
        <CardContent>
          <InvoicePrintPreview
            printRef={printRef}
            invoiceData={invoiceData}
            totals={totals}
            calculateLineTotal={calculateLineTotal}
          />
        </CardContent>
      </Card>

      {/* Staff PIN Dialog */}
      <Dialog open={showPinDialog} onOpenChange={setShowPinDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Staff PIN Required</DialogTitle>
            <DialogDescription>
              Enter your staff PIN to save this invoice.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Input
              type="password"
              placeholder="Enter 4-6 digit PIN"
              value={staffPin}
              onChange={(e) => setStaffPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
              maxLength={6}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowPinDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleVerifyPin} disabled={verifyingPin || staffPin.length < 4}>
              {verifyingPin ? 'Verifying...' : 'Verify & Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ShowroomEpos;
