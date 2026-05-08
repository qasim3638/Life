import React from 'react';

export const RefundPrintPreview = ({
  printRef,
  refundData,
  totals
}) => {
  return (
    <div ref={printRef} className="bg-white p-8 border rounded-lg print-preview" style={{ maxWidth: '850px', margin: '0 auto' }}>
      {/* Refund Header */}
      <div className="flex justify-between items-start mb-4">
        {/* Refund Title - Large Left */}
        <div>
          <h1 className="text-4xl font-bold" style={{ fontFamily: 'Georgia, serif' }}>Refund Note</h1>
          <div className="mt-2 px-3 py-1 bg-gray-100 border border-gray-300 inline-block rounded">
            <span className="text-lg font-bold" style={{ color: '#000' }}>
              No: {refundData.refundNo}
            </span>
          </div>
          {refundData.originalInvoiceNo && (
            <div className="mt-1 text-sm text-gray-600">
              Original Invoice: <span className="font-semibold">{refundData.originalInvoiceNo}</span>
            </div>
          )}
        </div>
        
        {/* Company Details - Right */}
        <div className="text-right text-xs leading-relaxed">
          <p className="font-semibold">{refundData.date} {refundData.time}</p>
          <p className="font-bold text-sm mt-1">{refundData.companyInfo.name}</p>
          <p>{refundData.companyInfo.address}</p>
          <p>{refundData.companyInfo.city}</p>
          <p>Telephone: {refundData.companyInfo.telephone}</p>
          <p>E-mail: {refundData.companyInfo.email}</p>
          <p>Company No. {refundData.companyInfo.companyNo} / VAT No. {refundData.companyInfo.vatNo}</p>
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

      {/* Refund Table */}
      <table className="w-full border-collapse mb-4" style={{ fontSize: '11px' }}>
        <thead>
          <tr style={{ backgroundColor: '#000', color: '#fff' }}>
            <th className="border border-gray-400 px-2 py-2 text-center" style={{ width: '50px' }}>Qty</th>
            <th className="border border-gray-400 px-2 py-2 text-left">Product</th>
            <th className="border border-gray-400 px-2 py-2 text-left" style={{ width: '80px' }}>SKU</th>
            <th className="border border-gray-400 px-2 py-2 text-right" style={{ width: '70px' }}>Orig. Price</th>
            <th className="border border-gray-400 px-2 py-2 text-right" style={{ width: '70px' }}>Refund Price</th>
            <th className="border border-gray-400 px-2 py-2 text-left" style={{ width: '100px' }}>Reason</th>
            <th className="border border-gray-400 px-2 py-2 text-right" style={{ width: '70px' }}>Total</th>
          </tr>
        </thead>
        <tbody>
          {refundData.lineItems.map((item, index) => {
            if (!item.product && !item.qty) return null;
            const lineTotal = (parseFloat(item.qty) || 0) * (parseFloat(item.refundPrice) || 0);
            return (
              <tr key={index}>
                <td className="border border-gray-300 px-2 py-1 text-center">{item.qty || ''}</td>
                <td className="border border-gray-300 px-2 py-1">{item.product || ''}</td>
                <td className="border border-gray-300 px-2 py-1">{item.sku || '-'}</td>
                <td className="border border-gray-300 px-2 py-1 text-right">£{parseFloat(item.originalPrice || 0).toFixed(2)}</td>
                <td className="border border-gray-300 px-2 py-1 text-right">£{parseFloat(item.refundPrice || 0).toFixed(2)}</td>
                <td className="border border-gray-300 px-2 py-1 text-xs">{item.reason || '-'}</td>
                <td className="border border-gray-300 px-2 py-1 text-right">£{lineTotal.toFixed(2)}</td>
              </tr>
            );
          })}
          {/* Empty rows for manual entry when printed */}
          {refundData.lineItems.filter(i => i.product || i.qty).length < 8 && 
            [...Array(8 - refundData.lineItems.filter(i => i.product || i.qty).length)].map((_, i) => (
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
                <td className="py-1 border-b border-gray-400">{refundData.customerName || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Phone</td>
                <td className="py-1 border-b border-gray-400">{refundData.customerPhone || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Address</td>
                <td className="py-1 border-b border-gray-400">{refundData.customerAddress || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Email</td>
                <td className="py-1 border-b border-gray-400">{refundData.customerEmail || ''}</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Processed By</td>
                <td className="py-1 border-b border-gray-400">{refundData.salesPerson || ''}</td>
              </tr>
            </tbody>
          </table>

          {/* Notes Section */}
          {refundData.notes && (
            <div className="mt-3 p-2 bg-gray-50 border rounded text-xs">
              <p className="font-bold mb-1">Notes:</p>
              <p>{refundData.notes}</p>
            </div>
          )}
        </div>

        {/* Right Column - Refund Summary */}
        <div className="w-64">
          {/* Refund Type Badge */}
          <div className="mb-2 px-3 py-2 text-center text-sm font-bold rounded bg-red-100 text-red-800 border-2 border-red-400">
            {refundData.refundType || 'Refund'}
          </div>
          
          <table className="w-full border-collapse" style={{ fontSize: '11px' }}>
            <tbody>
              <tr>
                <td className="border border-gray-400 px-2 py-1 font-bold bg-gray-100">Refund Method</td>
                <td className="border border-gray-400 px-2 py-1 font-bold text-right bg-gray-100">{refundData.refundMethod || '-'}</td>
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
                  <td className="border border-gray-400 px-2 py-1 text-orange-700">Restocking Fee ({refundData.restockingFeePercent}%)</td>
                  <td className="border border-gray-400 px-2 py-1 text-right text-orange-700">-£{totals.restockingFee.toFixed(2)}</td>
                </tr>
              )}
            </tbody>
          </table>

          {/* Net Refund Amount - Highlighted */}
          <div className="mt-2 p-3 bg-red-700 text-white rounded">
            <div className="flex justify-between items-center">
              <span className="font-bold">NET REFUND</span>
              <span className="text-xl font-bold">£{totals.netRefund.toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tagline */}
      <div className="text-center text-sm font-semibold mb-4" style={{ letterSpacing: '1px' }}>
        Amazing Tiles - Beautiful Bathrooms - Excellent Service
      </div>

      {/* Refund Policy */}
      <div style={{ borderTop: '1px solid #333', paddingTop: '10px' }}>
        <p className="font-bold text-xs mb-1">Refund Policy:</p>
        <p style={{ fontSize: '10px', lineHeight: '1.4', color: '#333' }}>
          • Refunds will be processed within 5-7 working days • Original receipt required for all refunds • 
          Stocked tiles incur a 20% restocking fee • Special order tiles are non-refundable • 
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
