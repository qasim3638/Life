import React from 'react';

// Capitalize first letter of every word (Title Case)
const toTitleCase = (str) => {
  if (!str) return '';
  return str.replace(/\b\w/g, char => char.toUpperCase());
};

export const CashQuotationPrintPreview = ({
  printRef,
  quotationData,
  totals,
  calculateLineTotal
}) => {
  return (
    <div ref={printRef} className="bg-white p-8 border rounded-lg" style={{ maxWidth: '850px', margin: '0 auto' }}>
      {/* Quotation Header */}
      <div className="flex justify-between items-start mb-4">
        {/* Quotation Title - Large Left */}
        <div>
          <h1 className="text-4xl font-bold" style={{ fontFamily: 'Georgia, serif' }}>Cash Quotation</h1>
          <div className="mt-2 px-3 py-1 bg-gray-100 border border-gray-300 inline-block rounded">
            <span className="text-lg font-bold" style={{ color: '#000' }}>
              No: {quotationData.quotationNo}
            </span>
          </div>
        </div>
        
        {/* Company Details - Right */}
        <div className="text-right text-xs leading-relaxed">
          <p className="font-semibold">{quotationData.date} {quotationData.time}</p>
          <p className="font-bold text-sm mt-1">{quotationData.companyInfo.name}</p>
          <p>{quotationData.companyInfo.address}</p>
          <p>{quotationData.companyInfo.city}</p>
          <p>Telephone: {quotationData.companyInfo.telephone}</p>
          <p>E-mail: {quotationData.companyInfo.email}</p>
          <p>Company No. {quotationData.companyInfo.companyNo} / VAT No. {quotationData.companyInfo.vatNo}</p>
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
      <div className="mb-4 p-2 bg-gray-100 border border-gray-400 rounded text-sm">
        <p className="font-semibold">
          This quotation is valid for {quotationData.validityDays || 30} days from the date above.
        </p>
      </div>

      {/* Quotation Table */}
      <table className="w-full border-collapse mb-4" style={{ fontSize: '11px' }}>
        <thead>
          <tr style={{ backgroundColor: '#000', color: '#fff' }}>
            <th className="border border-gray-400 px-2 py-2 text-center" style={{ width: '50px' }}>Qty</th>
            <th className="border border-gray-400 px-2 py-2 text-center" style={{ width: '35px' }}>m²</th>
            <th className="border border-gray-400 px-2 py-2 text-left">Product</th>
            <th className="border border-gray-400 px-2 py-2 text-right" style={{ width: '60px' }}>List Price</th>
            <th className="border border-gray-400 px-2 py-2 text-right" style={{ width: '60px' }}>Quote Price</th>
            <th className="border border-gray-400 px-2 py-2 text-center" style={{ width: '45px' }}>Disc %</th>
            <th className="border border-gray-400 px-2 py-2 text-right" style={{ width: '55px' }}>Savings</th>
            <th className="border border-gray-400 px-2 py-2 text-right" style={{ width: '60px' }}>Total</th>
          </tr>
        </thead>
        <tbody>
          {quotationData.lineItems.map((item, index) => {
            const calc = calculateLineTotal(item);
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
          {/* Empty rows for manual entry when printed - completely blank for tidy look */}
          {quotationData.lineItems.filter(i => i.product || i.qty || i.price).length < 12 && 
            [...Array(12 - quotationData.lineItems.filter(i => i.product || i.qty || i.price).length)].map((_, i) => (
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

      {/* Bottom Section - Two Columns */}
      <div className="flex gap-6 text-xs mb-4">
        {/* Left Column - Customer Details */}
        <div className="flex-1">
          <table className="w-full" style={{ fontSize: '11px' }}>
            <tbody>
              <tr>
                <td className="py-1 font-bold w-24">Name</td>
                <td className="py-1 border-b border-gray-400">{quotationData.customerName || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Phone</td>
                <td className="py-1 border-b border-gray-400">{quotationData.customerPhone || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Address</td>
                <td className="py-1 border-b border-gray-400">{quotationData.customerAddress || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Email</td>
                <td className="py-1 border-b border-gray-400">{quotationData.customerEmail || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Sales Person</td>
                <td className="py-1 border-b border-gray-400">{quotationData.salesPerson || ''}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Right Column - Summary */}
        <div className="w-64">
          {/* Cash Quotation Badge */}
          <div className="mb-2 px-3 py-2 text-center text-sm font-bold rounded bg-green-100 text-green-800 border-2 border-green-400">
            CASH QUOTATION
          </div>
          
          <table className="w-full border-collapse" style={{ fontSize: '11px' }}>
            <tbody>
              <tr>
                <td className="border border-gray-400 px-2 py-1 font-bold bg-gray-100" colSpan={2}>Summary</td>
                <td className="border border-gray-400 px-2 py-1 font-bold text-right bg-gray-100">Total</td>
              </tr>
              <tr>
                <td className="border border-gray-400 px-2 py-1" colSpan={2}>Subtotal</td>
                <td className="border border-gray-400 px-2 py-1 text-right">£ {totals.totalDue.toFixed(2)}</td>
              </tr>
              <tr>
                <td className="border border-gray-400 px-2 py-1 italic text-gray-500" colSpan={2}>No VAT</td>
                <td className="border border-gray-400 px-2 py-1 text-right text-gray-500">£ 0.00</td>
              </tr>
              <tr>
                <td className="border border-gray-400 px-2 py-1 font-bold" colSpan={2}>Total</td>
                <td className="border border-gray-400 px-2 py-1 text-right font-bold text-lg">£ {totals.totalDue.toFixed(2)}</td>
              </tr>
            </tbody>
          </table>

          {/* Total Savings */}
          {totals.totalSavings > 0 && (
            <div className="mt-2 p-2 bg-gray-100 border border-gray-400 rounded text-center">
              <p className="font-semibold text-sm">
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

      {/* Cash Quotation Notes */}
      <div style={{ borderTop: '1px solid #333', paddingTop: '10px' }}>
        <p className="font-bold text-xs mb-1">Cash Quotation Notes:</p>
        <p style={{ fontSize: '10px', lineHeight: '1.4', color: '#333' }}>
          {quotationData.notes || 'This is a cash quotation without VAT. Prices are subject to stock availability. To proceed with your order, please contact us or visit one of our showrooms.'}
        </p>
        <p style={{ fontSize: '10px', lineHeight: '1.4', color: '#666', marginTop: '8px' }}>
          • No VAT included • Cash payment only • Stock subject to availability
        </p>
      </div>
    </div>
  );
};
