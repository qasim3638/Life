import React from 'react';

export const CreditNotePrintPreview = ({
  printRef,
  creditNoteData,
  totals
}) => {
  return (
    <div ref={printRef} className="bg-white p-8 border rounded-lg print-preview" style={{ maxWidth: '850px', margin: '0 auto' }}>
      {/* CreditNote Header */}
      <div className="flex justify-between items-start mb-4">
        {/* CreditNote Title - Large Left */}
        <div>
          <h1 className="text-4xl font-bold " style={{ fontFamily: 'Georgia, serif' }}>Credit Note</h1>
          <div className="mt-2 px-3 py-1 bg-gray-100 border border-gray-300 inline-block rounded">
            <span className="text-lg font-bold" style={{ color: '#000' }}>
              No: {creditNoteData.creditNoteNo}
            </span>
          </div>
          {creditNoteData.originalInvoiceNo && (
            <div className="mt-1 text-sm text-gray-600">
              Original Invoice: <span className="font-semibold">{creditNoteData.originalInvoiceNo}</span>
            </div>
          )}
        </div>
        
        {/* Company Details - Right */}
        <div className="text-right text-xs leading-relaxed">
          <p className="font-semibold">{creditNoteData.date} {creditNoteData.time}</p>
          <p className="font-bold text-sm mt-1">{creditNoteData.companyInfo.name}</p>
          <p>{creditNoteData.companyInfo.address}</p>
          <p>{creditNoteData.companyInfo.city}</p>
          <p>Telephone: {creditNoteData.companyInfo.telephone}</p>
          <p>E-mail: {creditNoteData.companyInfo.email}</p>
          <p>Company No. {creditNoteData.companyInfo.companyNo} / VAT No. {creditNoteData.companyInfo.vatNo}</p>
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

      {/* CreditNote Table */}
      <table className="w-full border-collapse mb-4" style={{ fontSize: '11px' }}>
        <thead>
          <tr style={{ backgroundColor: '#000', color: '#fff' }}>
            <th className="border border-gray-400 px-2 py-2 text-center" style={{ width: '50px' }}>Qty</th>
            <th className="border border-gray-400 px-2 py-2 text-left">Product</th>
            <th className="border border-gray-400 px-2 py-2 text-left" style={{ width: '80px' }}>SKU</th>
            <th className="border border-gray-400 px-2 py-2 text-right" style={{ width: '70px' }}>Orig. Price</th>
            <th className="border border-gray-400 px-2 py-2 text-right" style={{ width: '70px' }}>CreditNote Price</th>
            <th className="border border-gray-400 px-2 py-2 text-left" style={{ width: '100px' }}>Reason</th>
            <th className="border border-gray-400 px-2 py-2 text-right" style={{ width: '70px' }}>Total</th>
          </tr>
        </thead>
        <tbody>
          {creditNoteData.lineItems.map((item, index) => {
            if (!item.product && !item.qty) return null;
            const lineTotal = (parseFloat(item.qty) || 0) * (parseFloat(item.creditNotePrice) || 0);
            return (
              <tr key={index}>
                <td className="border border-gray-300 px-2 py-1 text-center">{item.qty || ''}</td>
                <td className="border border-gray-300 px-2 py-1">{item.product || ''}</td>
                <td className="border border-gray-300 px-2 py-1">{item.sku || '-'}</td>
                <td className="border border-gray-300 px-2 py-1 text-right">£{parseFloat(item.originalPrice || 0).toFixed(2)}</td>
                <td className="border border-gray-300 px-2 py-1 text-right">£{parseFloat(item.creditNotePrice || 0).toFixed(2)}</td>
                <td className="border border-gray-300 px-2 py-1 text-xs">{item.reason || '-'}</td>
                <td className="border border-gray-300 px-2 py-1 text-right">£{lineTotal.toFixed(2)}</td>
              </tr>
            );
          })}
          {/* Empty rows for manual entry when printed */}
          {creditNoteData.lineItems.filter(i => i.product || i.qty).length < 8 && 
            [...Array(8 - creditNoteData.lineItems.filter(i => i.product || i.qty).length)].map((_, i) => (
              <tr key={`empty-${i}`}>
                <td className="border border-gray-300 px-2 py-1 text-center">&nbsp;</td>
                <td className="border border-gray-300 px-2 py-1">&nbsp;</td>
                <td className="border border-gray-300 px-2 py-1">&nbsp;</td>
                <td className="border border-gray-300 px-2 py-1 text-right">&nbsp;</td>
                <td className="border border-gray-300 px-2 py-1 text-right">&nbsp;</td>
                <td className="border border-gray-300 px-2 py-1">&nbsp;</td>
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
                <td className="py-1 border-b border-gray-400">{creditNoteData.customerName || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Phone</td>
                <td className="py-1 border-b border-gray-400">{creditNoteData.customerPhone || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Address</td>
                <td className="py-1 border-b border-gray-400">{creditNoteData.customerAddress || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Email</td>
                <td className="py-1 border-b border-gray-400">{creditNoteData.customerEmail || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Processed By</td>
                <td className="py-1 border-b border-gray-400">{creditNoteData.salesPerson || ''}</td>
              </tr>
            </tbody>
          </table>

          {/* Notes Section */}
          {creditNoteData.notes && (
            <div className="mt-3 p-2 bg-gray-50 border rounded text-xs">
              <p className="font-bold mb-1">Notes:</p>
              <p>{creditNoteData.notes}</p>
            </div>
          )}
        </div>

        {/* Right Column - CreditNote Summary */}
        <div className="w-64">
          {/* CreditNote Type Badge */}
          <div className="mb-2 px-3 py-2 text-center text-sm font-bold rounded bg-gray-100 text-red-800 border-2 border-red-400">
            {creditNoteData.creditNoteType || 'CreditNote'}
          </div>
          
          <table className="w-full border-collapse" style={{ fontSize: '11px' }}>
            <tbody>
              <tr>
                <td className="border border-gray-400 px-2 py-1 font-bold bg-gray-100">CreditNote Method</td>
                <td className="border border-gray-400 px-2 py-1 font-bold text-right bg-gray-100">{creditNoteData.creditNoteMethod || '-'}</td>
              </tr>
              <tr>
                <td className="border border-gray-400 px-2 py-1">Subtotal</td>
                <td className="border border-gray-400 px-2 py-1 text-right">£{totals.subtotal.toFixed(2)}</td>
              </tr>
              <tr>
                <td className="border border-gray-400 px-2 py-1">VAT (20%)</td>
                <td className="border border-gray-400 px-2 py-1 text-right">£{totals.vat.toFixed(2)}</td>
              </tr>
              <tr>
                <td className="border border-gray-400 px-2 py-1 font-bold">Gross Total</td>
                <td className="border border-gray-400 px-2 py-1 text-right font-bold">£{totals.grossTotal.toFixed(2)}</td>
              </tr>
              {totals.restockingFee > 0 && (
                <tr>
                  <td className="border border-gray-400 px-2 py-1 text-orange-700">Restocking Fee ({creditNoteData.restockingFeePercent}%)</td>
                  <td className="border border-gray-400 px-2 py-1 text-right text-orange-700">-£{totals.restockingFee.toFixed(2)}</td>
                </tr>
              )}
            </tbody>
          </table>

          {/* Net CreditNote Amount - Highlighted */}
          <div className="mt-2 p-3 bg-red-700 text-white rounded">
            <div className="flex justify-between items-center">
              <span className="font-bold">NET CREDIT NOTE</span>
              <span className="text-xl font-bold">£{totals.netCreditNote.toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tagline */}
      <div className="text-center text-sm font-semibold mb-4" style={{ letterSpacing: '1px' }}>
        Amazing Tiles - Beautiful Bathrooms - Excellent Service
      </div>

      {/* CreditNote Policy */}
      <div style={{ borderTop: '1px solid #333', paddingTop: '10px' }}>
        <p className="font-bold text-xs mb-1">CreditNote Policy:</p>
        <p style={{ fontSize: '10px', lineHeight: '1.4', color: '#333' }}>
          • CreditNotes will be processed within 5-7 working days • Original receipt required for all creditNotes • 
          Stocked tiles incur a 20% restocking fee • Special order tiles are non-creditNoteable • 
          Bathroom products are exchange only • Credit notes are valid for 12 months from date of issue
        </p>
      </div>

      {/* Signature Line */}
      <div className="mt-6 flex justify-between" style={{ fontSize: '11px' }}>
        <div className="w-1/3">
          <div className="border-t border-gray-400 pt-1 mt-8">
            <p className="text-center text-xs text-gray-600">Customer Signature</p>
          </div>
        </div>
        <div className="w-1/3">
          <div className="border-t border-gray-400 pt-1 mt-8">
            <p className="text-center text-xs text-gray-600">Staff Signature</p>
          </div>
        </div>
      </div>
    </div>
  );
};
