'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useParams } from 'next/navigation';
import { 
  Package, 
  ChevronRight, 
  ChevronLeft,
  Loader2,
  Truck,
  MapPin,
  CheckCircle,
  Clock,
  AlertCircle,
  CreditCard,
  Download
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
  payment_method?: string;
  delivery_method: string;
  store_name?: string;
  items: OrderItem[];
  subtotal: number;
  vat: number;
  delivery_fee: number;
  total: number;
  created_at: string;
  estimated_delivery?: string;
  tracking?: {
    number?: string;
    url?: string;
    carrier?: string;
  };
  status_history?: Array<{
    status: string;
    timestamp: string;
    notes?: string;
  }>;
  shipping_address?: {
    name: string;
    line1: string;
    line2?: string;
    city: string;
    postcode: string;
  };
  billing_address?: {
    name: string;
    line1: string;
    line2?: string;
    city: string;
    postcode: string;
  };
}

const statusConfig: Record<string, { label: string; icon: any; color: string; bgColor: string }> = {
  pending_payment: { label: 'Awaiting Payment', icon: Clock, color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
  confirmed: { label: 'Order Confirmed', icon: CheckCircle, color: 'text-green-600', bgColor: 'bg-green-100' },
  processing: { label: 'Processing', icon: Package, color: 'text-blue-600', bgColor: 'bg-blue-100' },
  shipped: { label: 'Shipped', icon: Truck, color: 'text-indigo-600', bgColor: 'bg-indigo-100' },
  delivered: { label: 'Delivered', icon: CheckCircle, color: 'text-green-600', bgColor: 'bg-green-100' },
  ready_for_collection: { label: 'Ready for Collection', icon: MapPin, color: 'text-amber-600', bgColor: 'bg-amber-100' },
  collected: { label: 'Collected', icon: CheckCircle, color: 'text-green-600', bgColor: 'bg-green-100' },
  cancelled: { label: 'Cancelled', icon: AlertCircle, color: 'text-red-600', bgColor: 'bg-red-100' },
};

export default function OrderDetailPage() {
  const router = useRouter();
  const params = useParams();
  const orderId = params.id as string;
  
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('shop_token');
    if (!token) {
      router.push('/login?redirect=/account/orders');
      return;
    }

    const fetchOrder = async () => {
      try {
        const orderData = await api.getOrder(token, orderId);
        setOrder(orderData);
      } catch (err: any) {
        console.error('Failed to fetch order:', err);
        setError('Order not found');
      } finally {
        setLoading(false);
      }
    };

    fetchOrder();
  }, [router, orderId]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: 'GBP',
    }).format(price);
  };

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-teal-600" />
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto text-center py-12">
          <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-slate-900 mb-2">Order Not Found</h2>
          <p className="text-slate-500 mb-6">The order you're looking for doesn't exist or you don't have access to it.</p>
          <Link
            href="/account/orders"
            className="inline-flex items-center gap-2 text-teal-600 hover:text-teal-700 font-medium"
          >
            <ChevronLeft className="w-4 h-4" />
            Back to Orders
          </Link>
        </div>
      </div>
    );
  }

  const statusInfo = statusConfig[order.status] || statusConfig.confirmed;
  const StatusIcon = statusInfo.icon;

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-sm mb-6">
          <Link href="/account" className="text-slate-500 hover:text-teal-600">
            My Account
          </Link>
          <ChevronRight className="w-4 h-4 text-slate-400" />
          <Link href="/account/orders" className="text-slate-500 hover:text-teal-600">
            Orders
          </Link>
          <ChevronRight className="w-4 h-4 text-slate-400" />
          <span className="text-slate-900 font-medium">{order.order_number}</span>
        </nav>

        {/* Order Header */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden mb-6">
          <div className="p-6 border-b">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <h1 className="text-xl md:text-2xl font-bold text-slate-900">{order.order_number}</h1>
                <p className="text-slate-500">Placed on {formatDate(order.created_at)}</p>
              </div>
              <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full ${statusInfo.bgColor} ${statusInfo.color}`}>
                <StatusIcon className="w-5 h-5" />
                <span className="font-semibold">{statusInfo.label}</span>
              </div>
            </div>
          </div>

          {/* Status Details */}
          <div className="p-6 bg-slate-50">
            <div className="flex flex-col md:flex-row md:items-center gap-4">
              {order.delivery_method === 'delivery' && order.estimated_delivery && (
                <div className="flex items-center gap-2 text-slate-600">
                  <Truck className="w-5 h-5" />
                  <span>Estimated delivery: <strong>{order.estimated_delivery}</strong></span>
                </div>
              )}
              {order.delivery_method === 'collect' && order.store_name && (
                <div className="flex items-center gap-2 text-slate-600">
                  <MapPin className="w-5 h-5" />
                  <span>Collection from: <strong>{order.store_name}</strong></span>
                </div>
              )}
              {order.tracking?.url && (
                <a
                  href={order.tracking.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-teal-600 hover:text-teal-700 font-medium"
                >
                  <Truck className="w-4 h-4" />
                  Track Package
                  {order.tracking.number && <span className="text-slate-500">({order.tracking.number})</span>}
                </a>
              )}
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left Column - Items & Timeline */}
          <div className="lg:col-span-2 space-y-6">
            {/* Order Items */}
            <div className="bg-white rounded-xl shadow-sm overflow-hidden">
              <div className="p-5 border-b">
                <h3 className="font-semibold text-slate-900">Order Items</h3>
              </div>
              <div className="divide-y">
                {order.items.map((item, index) => (
                  <div key={index} className="p-5 flex items-center gap-4">
                    <div className="w-16 h-16 bg-slate-100 rounded-lg flex items-center justify-center overflow-hidden flex-shrink-0">
                      {item.image ? (
                        <img src={item.image} alt={item.name} className="w-full h-full object-cover" />
                      ) : (
                        <Package className="w-6 h-6 text-slate-400" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="font-medium text-slate-900 truncate">{item.name}</h4>
                      <p className="text-sm text-slate-500">Qty: {item.quantity}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-slate-900">{formatPrice(item.price * item.quantity)}</p>
                      <p className="text-sm text-slate-500">{formatPrice(item.price)} each</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Status Timeline */}
            {order.status_history && order.status_history.length > 0 && (
              <div className="bg-white rounded-xl shadow-sm overflow-hidden">
                <div className="p-5 border-b">
                  <h3 className="font-semibold text-slate-900">Order Timeline</h3>
                </div>
                <div className="p-5">
                  <div className="space-y-4">
                    {order.status_history.map((entry, index) => {
                      const entryStatus = statusConfig[entry.status] || statusConfig.confirmed;
                      return (
                        <div key={index} className="flex gap-4">
                          <div className={`w-3 h-3 mt-1.5 rounded-full ${index === 0 ? 'bg-teal-500' : 'bg-slate-300'}`} />
                          <div className="flex-1">
                            <p className={`font-medium ${index === 0 ? 'text-slate-900' : 'text-slate-600'}`}>
                              {entryStatus.label}
                            </p>
                            <p className="text-sm text-slate-500">{formatDate(entry.timestamp)}</p>
                            {entry.notes && (
                              <p className="text-sm text-slate-500 mt-1">{entry.notes}</p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Column - Summary & Addresses */}
          <div className="space-y-6">
            {/* Order Summary */}
            <div className="bg-white rounded-xl shadow-sm overflow-hidden">
              <div className="p-5 border-b">
                <h3 className="font-semibold text-slate-900">Order Summary</h3>
              </div>
              <div className="p-5 space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Subtotal</span>
                  <span>{formatPrice(order.subtotal)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">VAT (20%)</span>
                  <span>{formatPrice(order.vat)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Delivery</span>
                  <span>{order.delivery_fee === 0 ? 'FREE' : formatPrice(order.delivery_fee)}</span>
                </div>
                <hr />
                <div className="flex justify-between font-semibold">
                  <span>Total</span>
                  <span className="text-lg">{formatPrice(order.total)}</span>
                </div>
              </div>
            </div>

            {/* Payment Info */}
            <div className="bg-white rounded-xl shadow-sm overflow-hidden">
              <div className="p-5 border-b">
                <h3 className="font-semibold text-slate-900">Payment</h3>
              </div>
              <div className="p-5">
                <div className="flex items-center gap-3">
                  <CreditCard className="w-5 h-5 text-slate-400" />
                  <div>
                    <p className="font-medium text-slate-900 capitalize">
                      {order.payment_method || 'Card'}
                    </p>
                    <p className="text-sm text-slate-500 capitalize">{order.payment_status}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Shipping Address */}
            {order.shipping_address && (
              <div className="bg-white rounded-xl shadow-sm overflow-hidden">
                <div className="p-5 border-b">
                  <h3 className="font-semibold text-slate-900">
                    {order.delivery_method === 'delivery' ? 'Delivery Address' : 'Collection Point'}
                  </h3>
                </div>
                <div className="p-5 text-sm text-slate-600">
                  <p className="font-medium text-slate-900">{order.shipping_address.name}</p>
                  <p>{order.shipping_address.line1}</p>
                  {order.shipping_address.line2 && <p>{order.shipping_address.line2}</p>}
                  <p>{order.shipping_address.city}</p>
                  <p>{order.shipping_address.postcode}</p>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="space-y-3">
              {order.status === 'pending_payment' && (
                <Link
                  href={`/checkout?order_id=${order.id}`}
                  className="w-full flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold py-3 rounded-lg transition-colors"
                >
                  Complete Payment
                </Link>
              )}
              <Link
                href="/account/orders"
                className="w-full flex items-center justify-center gap-2 border border-slate-200 hover:bg-slate-50 text-slate-700 font-semibold py-3 rounded-lg transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
                Back to Orders
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
