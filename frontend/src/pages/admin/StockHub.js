import React from 'react';
import HubPage from '../../components/HubPage';
import { 
  Warehouse, Boxes, Layers, Upload, Truck, 
  PackageSearch, PoundSterling, ClipboardList, BarChart3
} from 'lucide-react';

export default function StockHub() {
  const cards = [
    {
      title: 'Stock Allocation',
      description: 'Allocate stock to stores and locations',
      icon: Boxes,
      link: '/admin/stock-allocation',
      color: 'bg-blue-600'
    },
    {
      title: 'Bulk Stock Edit',
      description: 'Update multiple stock quantities at once',
      icon: Layers,
      link: '/admin/bulk-stock',
      color: 'bg-green-600'
    },
    {
      title: 'Stock Import',
      description: 'Import stock from spreadsheet',
      icon: Upload,
      link: '/admin/stock-import',
      color: 'bg-purple-600'
    },
    {
      title: 'Delivery Check-In',
      description: 'Check in deliveries and update stock',
      icon: Truck,
      link: '/admin/delivery-check-in',
      color: 'bg-orange-600'
    },
    {
      title: 'To Order Report',
      description: 'Products that need to be reordered',
      icon: PackageSearch,
      link: '/admin/to-order',
      color: 'bg-red-600'
    },
    {
      title: 'Stock Value',
      description: 'Total value of current stock',
      icon: PoundSterling,
      link: '/admin/stock-cost',
      color: 'bg-emerald-600'
    },
    {
      title: 'Stocktake Report',
      description: 'Generate stocktake reports',
      icon: ClipboardList,
      link: '/admin/stocktake-report',
      color: 'bg-cyan-600'
    },
    {
      title: 'Stock Analytics',
      description: 'Stock movement and trends',
      icon: BarChart3,
      link: '/admin/stock-analytics',
      color: 'bg-slate-600'
    },
  ];

  return (
    <HubPage 
      title="Stock Management" 
      subtitle="Manage inventory across all locations"
      icon={Warehouse}
      cards={cards} 
    />
  );
}
