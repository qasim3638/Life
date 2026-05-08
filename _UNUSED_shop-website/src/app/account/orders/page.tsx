'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { 
  Package, 
  ChevronRight, 
  ChevronLeft,
  Loader2,
  Search,
  Filter
} from 'lucide-react';
import api from '@/lib/api';

interface OrderItem {
  product_id: string;
  name: string;
  quantity: number;
  price: number;
  image?: string;
}

interface Order {
  id: string;
  order_number: string;
  status: string;
  payment_status: string;
  delivery_method: string;
  items: OrderItem[];
  subtotal: number;
  vat: number;
  delivery_fee: number;
  total: number;
  created_at: string;
  shipping_address?: {
    name: string;
    line1: string;
    line2?: string;
    city: string;
    postcode: string;
  };
}

export default function OrdersPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<Order[]>([]);
  const [filteredOrders, setFilteredOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('shop_token');
    if (!token) {
      router.push('/login?redirect=/account/orders');
      return;
    }

    const fetchOrders = async () => {
      try {
        const ordersData = await api.getOrders(token);
        setOrders(ordersData);
        setFilteredOrders(ordersData);
      } catch (error) {
        console.error('Failed to fetch orders:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchOrders();
  }, [router]);

  useEffect(() => {
    let result = orders;

    // Filter by status
    if (statusFilter !== 'all') {
      result = result.filter(order => order.status === statusFilter);
    }

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(order => 
        order.order_number.toLowerCase().includes(query) ||
        order.items.some(item => item.name.toLowerCase().includes(query))
      );
    }

    setFilteredOrders(result);
  }, [orders, statusFilter, searchQuery]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: 'GBP',
    }).format(price);
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      pending_payment: 'bg-yellow-100 text-yellow-800',
      confirmed: 'bg-green-100 text-green-800',
      processing: 'bg-blue-100 text-blue-800',
      shipped: 'bg-indigo-100 text-indigo-800',
      delivered: 'bg-green-100 text-green-800',
      ready_for_collection: 'bg-amber-100 text-amber-800',
      collected: 'bg-green-100 text-green-800',
      cancelled: 'bg-red-100 text-red-800',
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      pending_payment: 'Awaiting Payment',
      confirmed: 'Confirmed',
      processing: 'Processing',
      shipped: 'Shipped',
      delivered: 'Delivered',
      ready_for_collection: 'Ready for Collection',
      collected: 'Collected',
      cancelled: 'Cancelled',
    };
    return labels[status] || status;
  };

  const statuses = [
    { value: 'all', label: 'All Orders' },
    { value: 'pending_payment', label: 'Awaiting Payment' },
    { value: 'confirmed', label: 'Confirmed' },
    { value: 'processing', label: 'Processing' },
    { value: 'shipped', label: 'Shipped' },
    { value: 'delivered', label: 'Delivered' },
  ];

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-teal-600" />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-sm mb-6">
          <Link href="/account" className="text-slate-500 hover:text-teal-600">
            My Account
          </Link>
          <ChevronRight className="w-4 h-4 text-slate-400" />
          <span className="text-slate-900 font-medium">Orders</span>
        </nav>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-slate-900">My Orders</h1>
            <p className="text-slate-500">{orders.length} order{orders.length !== 1 ? 's' : ''} total</p>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl shadow-sm p-4 mb-6">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                placeholder="Search orders..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none"
              />
            </div>

            {/* Status Filter */}
            <div className="relative">
              <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="pl-10 pr-8 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none appearance-none bg-white min-w-[180px]"
              >
                {statuses.map((status) => (
                  <option key={status.value} value={status.value}>
                    {status.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Orders List */}
        {filteredOrders.length > 0 ? (
          <div className="space-y-4">
            {filteredOrders.map((order) => (
              <Link
                key={order.id}
                href={`/account/orders/${order.id}`}
                className="block bg-white rounded-xl shadow-sm overflow-hidden hover:shadow-md transition-shadow"
              >
                {/* Order Header */}
                <div className="p-5 border-b bg-slate-50">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div>
                      <span className="font-semibold text-slate-900">{order.order_number}</span>
                      <span className="text-slate-500 text-sm ml-3">{formatDate(order.created_at)}</span>
                    </div>
                    <span className={`text-xs px-3 py-1 rounded-full font-medium ${getStatusColor(order.status)}`}>
                      {getStatusLabel(order.status)}
                    </span>
                  </div>
                </div>

                {/* Order Items Preview */}
                <div className="p-5">
                  <div className="flex items-center gap-4">
                    {/* Item thumbnails */}
                    <div className="flex -space-x-3">
                      {order.items.slice(0, 3).map((item, index) => (
                        <div
                          key={index}
                          className="w-12 h-12 bg-slate-100 rounded-lg border-2 border-white flex items-center justify-center overflow-hidden"
                        >
                          {item.image ? (
                            <img src={item.image} alt={item.name} className="w-full h-full object-cover" />
                          ) : (
                            <Package className="w-5 h-5 text-slate-400" />
                          )}
                        </div>
                      ))}
                      {order.items.length > 3 && (
                        <div className="w-12 h-12 bg-slate-200 rounded-lg border-2 border-white flex items-center justify-center text-sm font-medium text-slate-600">
                          +{order.items.length - 3}
                        </div>
                      )}
                    </div>

                    {/* Item names */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-600 truncate">
                        {order.items.map(item => item.name).join(', ')}
                      </p>
                      <p className="text-sm text-slate-500">
                        {order.items.reduce((sum, item) => sum + item.quantity, 0)} item{order.items.reduce((sum, item) => sum + item.quantity, 0) !== 1 ? 's' : ''}
                      </p>
                    </div>

                    {/* Total */}
                    <div className="text-right">
                      <p className="font-semibold text-slate-900">{formatPrice(order.total)}</p>
                      <p className="text-xs text-slate-500">
                        {order.delivery_method === 'delivery' ? 'Delivery' : 'Collection'}
                      </p>
                    </div>

                    <ChevronRight className="w-5 h-5 text-slate-400" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm p-12 text-center">
            <Package className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-slate-900 mb-2">
              {orders.length === 0 ? 'No orders yet' : 'No orders found'}
            </h3>
            <p className="text-slate-500 mb-6">
              {orders.length === 0 
                ? 'Start shopping to see your orders here'
                : 'Try adjusting your search or filter'
              }
            </p>
            {orders.length === 0 && (
              <Link
                href="/products"
                className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
              >
                Browse Products
              </Link>
            )}
          </div>
        )}

        {/* Back Link */}
        <div className="mt-8">
          <Link
            href="/account"
            className="inline-flex items-center gap-2 text-slate-600 hover:text-teal-600 font-medium"
          >
            <ChevronLeft className="w-4 h-4" />
            Back to Account
          </Link>
        </div>
      </div>
    </div>
  );
}
