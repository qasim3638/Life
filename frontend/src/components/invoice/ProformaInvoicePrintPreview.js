import React from 'react';

// Capitalize first letter of every word (Title Case)
const toTitleCase = (str) => {
  if (!str) return '';
  return str.replace(/\b\w/g, char => char.toUpperCase());
};

// Bank Details for Proforma Invoice
const BANK_DETAILS = {
  name: 'TILE STATION LTD',
  accountType: 'Business',
  accountNumber: '33604637',
  sortCode: '23-05-80'
};

export const ProformaInvoicePrintPreview = ({
  printRef,
  invoiceData,
  totals,
  calculateLineTotal
}) => {
  // Calculate line totals if not provided
  const getLineTotal = (item) => {
    if (calculateLineTotal) {
      return calculateLineTotal(item);
    }
    const qty = parseFloat(item.qty) || 0;
    const duePrice = parseFloat(item.duePrice) || parseFloat(item.price) || 0;
    const total = qty * duePrice;
    const listPrice = parseFloat(item.price) || 0;
    const savings = qty * (listPrice - duePrice);
    const discountPercent = listPrice > 0 ? ((listPrice - duePrice) / listPrice) * 100 : 0;
    return { due: total, duePrice, savings, discountPercent };
  };

  return (
    <div ref={printRef} className="bg-white p-8 border rounded-lg" style={{ maxWidth: '850px', margin: '0 auto' }}>
      {/* Invoice Header */}
      <div className="flex justify-between items-start mb-4">
        {/* Invoice Title - Large Left */}
        <div>
          <h1 className="text-4xl font-bold text-blue-900" style={{ fontFamily: 'Georgia, serif' }}>Proforma Invoice</h1>
          <div className="mt-2 px-3 py-1 bg-blue-50 border border-blue-300 inline-block rounded">
            <span className="text-lg font-bold text-blue-900">
              No: {invoiceData.proformaNo}
            </span>
          </div>
        </div>
        
        {/* Company Details - Right */}
        <div className="text-right text-xs leading-relaxed">
          <p className="font-semibold">{invoiceData.date} {invoiceData.time}</p>
          <p className="font-bold text-sm mt-1">{invoiceData.companyInfo?.name || 'Tile Station'}</p>
          <p>{invoiceData.companyInfo?.address}</p>
          <p>{invoiceData.companyInfo?.city}</p>
          <p>Telephone: {invoiceData.companyInfo?.telephone}</p>
          <p>E-mail: {invoiceData.companyInfo?.email}</p>
          <p>Company No. {invoiceData.companyInfo?.companyNo} / VAT No. {invoiceData.companyInfo?.vatNo}</p>
        </div>
      </div>

      {/* Large Logo */}
      <div className="mb-4">
        <h2 className="text-4xl font-black tracking-wider" style={{ 
          fontFamily: 'Impact, Arial Black, sans-serif',
          letterSpacing: '4px'
        }}>
          TILE STATION
        </h2>
      </div>

      {/* Validity Notice */}
      <div className="mb-4 p-2 bg-blue-50 border border-blue-300 rounded text-sm">
        <p className="font-semibold text-blue-800">
          This proforma invoice is valid for {invoiceData.validityDays || 30} days from the date above.
        </p>
      </div>

      {/* Invoice Table */}
      <table className="w-full border-collapse mb-4" style={{ fontSize: '11px' }}>
        <thead>
          <tr style={{ backgroundColor: '#1e3a5f', color: '#fff' }}>
            <th className="border border-gray-400 px-2 py-2 text-center" style={{ width: '50px' }}>Qty</th>
            <th className="border border-gray-400 px-2 py-2 text-center" style={{ width: '35px' }}>m2</th>
            <th className="border border-gray-400 px-2 py-2 text-left">Product</th>
            <th className="border border-gray-400 px-2 py-2 text-right" style={{ width: '60px' }}>List Price</th>
            <th className="border border-gray-400 px-2 py-2 text-right" style={{ width: '60px' }}>Unit Price</th>
            <th className="border border-gray-400 px-2 py-2 text-center" style={{ width: '45px' }}>Disc %</th>
            <th className="border border-gray-400 px-2 py-2 text-right" style={{ width: '55px' }}>Savings</th>
            <th className="border border-gray-400 px-2 py-2 text-right" style={{ width: '60px' }}>Total</th>
          </tr>
        </thead>
        <tbody>
          {invoiceData.lineItems.map((item, index) => {
            const calc = getLineTotal(item);
            if (!item.product && !item.qty && !item.price) return null;
            return (
              <tr key={index}>
                <td className="border border-gray-300 px-2 py-1 text-center">{item.qty || ''}</td>
                <td className="border border-gray-300 px-2 py-1 text-center">{item.m2 || '0'}</td>
                <td className="border border-gray-300 px-2 py-1">{toTitleCase(item.product) || ''}</td>
                <td className="border border-gray-300 px-2 py-1 text-right">£{parseFloat(item.price || 0).toFixed(2)}</td>
                <td className="border border-gray-300 px-2 py-1 text-right">£{calc.duePrice.toFixed(2)}</td>
                <td className="border border-gray-300 px-2 py-1 text-center">{calc.discountPercent > 0 ? `${calc.discountPercent.toFixed(1)}%` : '-'}</td>
                <td className="border border-gray-300 px-2 py-1 text-right">{calc.savings > 0 ? `£${calc.savings.toFixed(2)}` : '-'}</td>
                <td className="border border-gray-300 px-2 py-1 text-right">£{calc.due.toFixed(2)}</td>
              </tr>
            );
          })}
          {/* Empty rows for manual entry when printed */}
          {invoiceData.lineItems.filter(i => i.product || i.qty || i.price).length < 10 && 
            [...Array(10 - invoiceData.lineItems.filter(i => i.product || i.qty || i.price).length)].map((_, i) => (
              <tr key={`empty-${i}`}>
                <td className="border border-gray-300 px-2 py-1 text-center">&nbsp;</td>
                <td className="border border-gray-300 px-2 py-1 text-center">&nbsp;</td>
                <td className="border border-gray-300 px-2 py-1">&nbsp;</td>
                <td className="border border-gray-300 px-2 py-1 text-right">&nbsp;</td>
                <td className="border border-gray-300 px-2 py-1 text-right">&nbsp;</td>
                <td className="border border-gray-300 px-2 py-1 text-center">&nbsp;</td>
                <td className="border border-gray-300 px-2 py-1 text-right">&nbsp;</td>
                <td className="border border-gray-300 px-2 py-1 text-right">&nbsp;</td>
              </tr>
            ))
          }
        </tbody>
      </table>

      {/* Bottom Section - Three Columns */}
      <div className="flex gap-4 text-xs mb-4">
        {/* Left Column - Customer Details */}
        <div className="flex-1">
          <table className="w-full" style={{ fontSize: '11px' }}>
            <tbody>
              <tr>
                <td className="py-1 font-bold w-24">Name</td>
                <td className="py-1 border-b border-gray-400">{invoiceData.customerName || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Phone</td>
                <td className="py-1 border-b border-gray-400">{invoiceData.customerPhone || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Address</td>
                <td className="py-1 border-b border-gray-400">{invoiceData.customerAddress || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Email</td>
                <td className="py-1 border-b border-gray-400">{invoiceData.customerEmail || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Sales Person</td>
                <td className="py-1 border-b border-gray-400">{invoiceData.salesPerson || ''}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Middle Column - Bank Details */}
        <div className="w-48">
          <div className="p-2 bg-blue-50 border-2 border-blue-400 rounded">
            <p className="font-bold text-sm text-blue-800 mb-2 border-b border-blue-300 pb-1">Payment Details</p>
            <table className="w-full" style={{ fontSize: '10px' }}>
              <tbody>
                <tr>
                  <td className="py-0.5 font-semibold text-blue-700">Account Name:</td>
                </tr>
                <tr>
                  <td className="pb-1 text-blue-900">{BANK_DETAILS.name}</td>
                </tr>
                <tr>
                  <td className="py-0.5 font-semibold text-blue-700">Account Type:</td>
                </tr>
                <tr>
                  <td className="pb-1 text-blue-900">{BANK_DETAILS.accountType}</td>
                </tr>
                <tr>
                  <td className="py-0.5 font-semibold text-blue-700">Account No:</td>
                </tr>
                <tr>
                  <td className="pb-1 text-blue-900 font-mono">{BANK_DETAILS.accountNumber}</td>
                </tr>
                <tr>
                  <td className="py-0.5 font-semibold text-blue-700">Sort Code:</td>
                </tr>
                <tr>
                  <td className="pb-1 text-blue-900 font-mono">{BANK_DETAILS.sortCode}</td>
                </tr>
              </tbody>
            </table>
            <p className="text-[9px] text-blue-600 mt-1 italic">
              Ref: {invoiceData.proformaNo}
            </p>
          </div>
        </div>

        {/* Right Column - Summary */}
        <div className="w-52">
          {/* Proforma Invoice Badge */}
          <div className="mb-2 px-3 py-2 text-center text-sm font-bold rounded bg-blue-100 text-blue-800 border-2 border-blue-400">
            PROFORMA INVOICE
          </div>
          
          <table className="w-full border-collapse" style={{ fontSize: '11px' }}>
            <tbody>
              <tr>
                <td className="border border-gray-400 px-2 py-1 font-bold bg-gray-100" colSpan={2}>Summary</td>
                <td className="border border-gray-400 px-2 py-1 font-bold text-right bg-gray-100">Total</td>
              </tr>
              <tr>
                <td className="border border-gray-400 px-2 py-1" colSpan={2}>Subtotal</td>
                <td className="border border-gray-400 px-2 py-1 text-right">£ {totals.subtotal.toFixed(2)}</td>
              </tr>
              <tr>
                <td className="border border-gray-400 px-2 py-1" colSpan={2}>VAT (20%)</td>
                <td className="border border-gray-400 px-2 py-1 text-right">£ {totals.vat.toFixed(2)}</td>
              </tr>
              <tr>
                <td className="border border-gray-400 px-2 py-1 font-bold" colSpan={2}>Total Due</td>
                <td className="border border-gray-400 px-2 py-1 text-right font-bold text-lg">£ {totals.grossTotal.toFixed(2)}</td>
              </tr>
            </tbody>
          </table>

          {/* Total Savings */}
          {totals.totalSavings > 0 && (
            <div className="mt-2 p-2 bg-green-50 border border-green-400 rounded text-center">
              <p className="font-semibold text-sm text-green-700">
                You Save: £{totals.totalSavings.toFixed(2)}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Tagline */}
      <div className="text-center text-sm font-semibold mb-4" style={{ letterSpacing: '1px' }}>
        Amazing Tiles - Beautiful Bathrooms - Excellent Service
      </div>

      {/* Proforma Invoice Notes */}
      <div style={{ borderTop: '1px solid #333', paddingTop: '10px' }}>
        <p className="font-bold text-xs mb-1">Proforma Invoice Notes:</p>
        <p style={{ fontSize: '10px', lineHeight: '1.4', color: '#333' }}>
          {invoiceData.notes || 'This is a proforma invoice. Payment is required before goods will be dispatched. Please use the payment details above and quote the invoice reference number.'}
        </p>
        <p style={{ fontSize: '10px', lineHeight: '1.4', color: '#666', marginTop: '8px' }}>
          • VAT included (20%) • Payment required before dispatch • Stock subject to availability
        </p>
        <p style={{ fontSize: '9px', lineHeight: '1.4', color: '#888', marginTop: '8px', fontStyle: 'italic' }}>
          This is a proforma invoice and is not a demand for payment. A tax invoice will be issued upon receipt of payment.
        </p>
      </div>
    </div>
  );
};
