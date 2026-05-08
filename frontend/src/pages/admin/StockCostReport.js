import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { 
  Building2, 
  Package, 
  Download, 
  RefreshCw, 
  PoundSterling,
  AlertCircle,
  Boxes
} from 'lucide-react';

export const StockCostReport = () => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generatingPdf, setGeneratingPdf] = useState(false);

  useEffect(() => {
    fetchReport();
  }, []);

  const fetchReport = async () => {
    setLoading(true);
    try {
      const res = await api.get('/reports/stock-cost');
      setReport(res.data);
    } catch (error) {
      console.error('Failed to load stock cost report:', error);
      toast.error('Failed to load stock cost report');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: 'GBP',
      minimumFractionDigits: 2
    }).format(value || 0);
  };

  const formatNumber = (value) => {
    return new Intl.NumberFormat('en-GB').format(value || 0);
  };

  const generatePDF = async () => {
    if (!report) return;
    
    setGeneratingPdf(true);
    try {
      // Using jsPDF for client-side PDF generation
      const jsPDFModule = await import('jspdf');
      const jsPDF = jsPDFModule.default;
      const { default: autoTable } = await import('jspdf-autotable');
      
      const doc = new jsPDF();
      const pageWidth = doc.internal.pageSize.getWidth();
      
      // Title
      doc.setFontSize(20);
      doc.setTextColor(33, 37, 41);
      doc.text('Stock Cost Report', pageWidth / 2, 20, { align: 'center' });
      
      // Generated date
      doc.setFontSize(10);
      doc.setTextColor(108, 117, 125);
      const generatedDate = new Date(report.generated_at).toLocaleString('en-GB', {
        dateStyle: 'full',
        timeStyle: 'short'
      });
      doc.text(`Generated: ${generatedDate}`, pageWidth / 2, 28, { align: 'center' });
      
      // Grand Total Summary Box
      doc.setFillColor(240, 240, 240);
      doc.roundedRect(14, 35, pageWidth - 28, 30, 3, 3, 'F');
      
      doc.setFontSize(14);
      doc.setTextColor(33, 37, 41);
      doc.text('Grand Total Stock Value', 20, 45);
      
      doc.setFontSize(24);
      doc.setTextColor(16, 185, 129);
      doc.text(formatCurrency(report.grand_total?.total_cost), 20, 58);
      
      doc.setFontSize(10);
      doc.setTextColor(108, 117, 125);
      doc.text(`Total Items: ${formatNumber(report.grand_total?.total_quantity)} | Products: ${formatNumber(report.grand_total?.total_products)}`, pageWidth - 20, 52, { align: 'right' });
      
      // Showroom breakdown table
      const tableData = report.showroom_breakdown.map(showroom => [
        showroom.showroom_name,
        formatNumber(showroom.total_quantity),
        formatNumber(showroom.product_count),
        formatCurrency(showroom.total_cost)
      ]);
      
      // Add unallocated row
      if (report.unallocated?.total_quantity > 0) {
        tableData.push([
          'Unallocated Stock',
          formatNumber(report.unallocated.total_quantity),
          formatNumber(report.unallocated.product_count),
          formatCurrency(report.unallocated.total_cost)
        ]);
      }
      
      autoTable(doc, {
        startY: 72,
        head: [['Store', 'Quantity', 'Products', 'Total Cost']],
        body: tableData,
        theme: 'striped',
        headStyles: {
          fillColor: [79, 70, 229],
          textColor: 255,
          fontStyle: 'bold'
        },
        styles: {
          fontSize: 10,
          cellPadding: 5
        },
        columnStyles: {
          0: { cellWidth: 70 },
          1: { halign: 'right', cellWidth: 35 },
          2: { halign: 'right', cellWidth: 35 },
          3: { halign: 'right', cellWidth: 40 }
        },
        foot: [[
          'GRAND TOTAL',
          formatNumber(report.grand_total?.total_quantity),
          formatNumber(report.grand_total?.total_products),
          formatCurrency(report.grand_total?.total_cost)
        ]],
        footStyles: {
          fillColor: [33, 37, 41],
          textColor: 255,
          fontStyle: 'bold'
        }
      });
      
      // Notes section
      const finalY = doc.lastAutoTable?.finalY ? doc.lastAutoTable.finalY + 10 : 200;
      doc.setFontSize(9);
      doc.setTextColor(108, 117, 125);
      doc.text('Note: ' + report.notes, 14, finalY, { maxWidth: pageWidth - 28 });
      
      // Products without cost warning
      if (report.grand_total?.products_without_cost > 0) {
        doc.setTextColor(220, 53, 69);
        doc.text(
          `Warning: ${report.grand_total.products_without_cost} products have no cost price set and are not included in cost calculations.`,
          14,
          finalY + 8,
          { maxWidth: pageWidth - 28 }
        );
      }
      
      // Footer
      doc.setFontSize(8);
      doc.setTextColor(150, 150, 150);
      doc.text('Tile Station - Stock Cost Report', pageWidth / 2, doc.internal.pageSize.getHeight() - 10, { align: 'center' });
      
      // Save
      const fileName = `stock-cost-report-${new Date().toISOString().split('T')[0]}.pdf`;
      doc.save(fileName);
      toast.success('PDF downloaded successfully');
    } catch (error) {
      console.error('Failed to generate PDF:', error);
      toast.error('Failed to generate PDF');
    } finally {
      setGeneratingPdf(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="stock-cost-loading">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">Failed to load report</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="stock-cost-report-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-heading font-bold tracking-tight">Stock Cost Report</h1>
          <p className="text-muted-foreground">Total inventory value breakdown by store</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchReport} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={generatePDF} disabled={generatingPdf} data-testid="download-pdf-btn">
            {generatingPdf ? (
              <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Download className="h-4 w-4 mr-2" />
            )}
            Download PDF
          </Button>
        </div>
      </div>

      {/* Grand Total Card */}
      <Card className="p-6 bg-gradient-to-br from-emerald-50 to-white border-emerald-200" data-testid="grand-total-card">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-emerald-600 mb-1">Grand Total Stock Value</p>
            <p className="text-4xl font-bold text-emerald-700" data-testid="grand-total-value">
              {formatCurrency(report.grand_total?.total_cost)}
            </p>
          </div>
          <div className="p-3 bg-emerald-100 rounded-full">
            <PoundSterling className="h-8 w-8 text-emerald-600" />
          </div>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">Total Items</p>
            <p className="font-semibold text-lg">{formatNumber(report.grand_total?.total_quantity)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Products</p>
            <p className="font-semibold text-lg">{formatNumber(report.grand_total?.total_products)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">With Cost Price</p>
            <p className="font-semibold text-lg">{formatNumber(report.grand_total?.products_with_cost)}</p>
          </div>
        </div>
      </Card>

      {/* Warning for products without cost */}
      {report.grand_total?.products_without_cost > 0 && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-amber-800">Missing Cost Prices</p>
            <p className="text-sm text-amber-700">
              {report.grand_total.products_without_cost} products have no cost price set. 
              These items are included in quantity counts but contribute £0 to cost totals.
            </p>
          </div>
        </div>
      )}

      {/* Store Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {report.showroom_breakdown.map((showroom) => (
          <Card key={showroom.showroom_id} className="p-5" data-testid={`showroom-card-${showroom.showroom_id}`}>
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <Building2 className="h-5 w-5 text-primary" />
                </div>
                <h3 className="font-semibold">{showroom.showroom_name}</h3>
              </div>
            </div>
            
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Stock Value</span>
                <span className="text-xl font-bold text-primary">
                  {formatCurrency(showroom.total_cost)}
                </span>
              </div>
              
              <div className="h-px bg-border" />
              
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="flex items-center gap-2">
                  <Boxes className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-muted-foreground">Items</p>
                    <p className="font-medium">{formatNumber(showroom.total_quantity)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Package className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-muted-foreground">Products</p>
                    <p className="font-medium">{formatNumber(showroom.product_count)}</p>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        ))}

        {/* Unallocated Stock Card */}
        {report.unallocated?.total_quantity > 0 && (
          <Card className="p-5 border-dashed border-2" data-testid="unallocated-card">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="p-2 bg-gray-100 rounded-lg">
                  <Package className="h-5 w-5 text-gray-500" />
                </div>
                <h3 className="font-semibold text-gray-600">Unallocated Stock</h3>
              </div>
            </div>
            
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Stock Value</span>
                <span className="text-xl font-bold text-gray-600">
                  {formatCurrency(report.unallocated.total_cost)}
                </span>
              </div>
              
              <div className="h-px bg-border" />
              
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="flex items-center gap-2">
                  <Boxes className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-muted-foreground">Items</p>
                    <p className="font-medium">{formatNumber(report.unallocated.total_quantity)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Package className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-muted-foreground">Products</p>
                    <p className="font-medium">{formatNumber(report.unallocated.product_count)}</p>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        )}
      </div>

      {/* Summary Table */}
      <Card className="overflow-hidden" data-testid="summary-table">
        <div className="p-4 border-b bg-muted/30">
          <h3 className="font-semibold">Summary Breakdown</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Store</th>
                <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">Items</th>
                <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">Products</th>
                <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">Stock Value</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {report.showroom_breakdown.map((showroom) => (
                <tr key={showroom.showroom_id} className="hover:bg-muted/30">
                  <td className="px-4 py-3 font-medium">{showroom.showroom_name}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{formatNumber(showroom.total_quantity)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{formatNumber(showroom.product_count)}</td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums">{formatCurrency(showroom.total_cost)}</td>
                </tr>
              ))}
              {report.unallocated?.total_quantity > 0 && (
                <tr className="hover:bg-muted/30 text-gray-500">
                  <td className="px-4 py-3 font-medium italic">Unallocated</td>
                  <td className="px-4 py-3 text-right tabular-nums">{formatNumber(report.unallocated.total_quantity)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{formatNumber(report.unallocated.product_count)}</td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums">{formatCurrency(report.unallocated.total_cost)}</td>
                </tr>
              )}
            </tbody>
            <tfoot className="bg-primary text-primary-foreground font-bold">
              <tr>
                <td className="px-4 py-3">Grand Total</td>
                <td className="px-4 py-3 text-right tabular-nums">{formatNumber(report.grand_total?.total_quantity)}</td>
                <td className="px-4 py-3 text-right tabular-nums">{formatNumber(report.grand_total?.total_products)}</td>
                <td className="px-4 py-3 text-right tabular-nums">{formatCurrency(report.grand_total?.total_cost)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </Card>

      {/* Generated timestamp */}
      <p className="text-xs text-muted-foreground text-center">
        Report generated: {new Date(report.generated_at).toLocaleString('en-GB', {
          dateStyle: 'full',
          timeStyle: 'short'
        })}
      </p>
    </div>
  );
};

export default StockCostReport;
