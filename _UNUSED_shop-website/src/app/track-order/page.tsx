'use client';

import { useState } from 'react';
import Link from 'next/link';
import { 
  Search, 
  Package, 
  Truck, 
  CheckCircle, 
  Clock, 
  MapPin,
  Loader2,
  AlertCircle
} from 'lucide-react';
import api from '@/lib/api';
import { formatPrice, formatDate } from '@/lib/utils';

interface OrderStatus {
  order_number: string;
  status: string;
  payment_status: string;
  delivery_method: string;
  store_name?: string;
  tracking: {
    number?: string;
    url?: string;
    carrier?: string;
  };
  status_history: Array<{
    status: string;
    timestamp: string;
    notes?: string;
  }>;
  items: Array<{
    name: string;
    quantity: number;
    price: number;
  }>;
  subtotal: number;
  vat: number;
  delivery_fee: number;
  total: number;
  created_at: string;
  estimated_delivery?: string;
}

const statusConfig: Record<string, { label: string; icon: any; color: string }> = {
  pending_payment: { label: 'Awaiting Payment', icon: Clock, color: 'text-yellow-500' },
  confirmed: { label: 'Order Confirmed', icon: CheckCircle, color: 'text-green-500' },
  processing: { label: 'Processing', icon: Package, color: 'text-blue-500' },
  shipped: { label: 'Shipped', icon: Truck, color: 'text-blue-600' },
  delivered: { label: 'Delivered', icon: CheckCircle, color: 'text-green-600' },
  ready_for_collection: { label: 'Ready for Collection', icon: MapPin, color: 'text-amber-500' },
  collected: { label: 'Collected', icon: CheckCircle, color: 'text-green-600' },
  cancelled: { label: 'Cancelled', icon: AlertCircle, color: 'text-red-500' },
};

export default function TrackOrderPage() {
  const [orderNumber, setOrderNumber] = useState('');
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [orderData, setOrderData] = useState<OrderStatus | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!orderNumber.trim() || !email.trim()) {
      setError('Please enter both order number and email');
      return;
    }
    
    setLoading(true);
    setError('');
    setOrderData(null);
    
    try {
      const data = await api.trackOrder(orderNumber.trim(), email.trim());
      setOrderData(data);
    } catch (err: any) {
      console.error('Track order error:', err);
      setError(err.response?.data?.detail || 'Order not found. Please check your details and try again.');
    } finally {
      setLoading(false);
    }
  };

  const getStatusInfo = (status: string) => {
    return statusConfig[status] || { label: status, icon: Package, color: 'text-slate-500' };
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl md:text-3xl font-bold text-slate-900 mb-2">Track Your Order</h1>
        <p className="text-slate-500 mb-8">
          Enter your order number and email to see the status of your order
        </p>

        {/* Search Form */}
        <div className="bg-white rounded-xl shadow-sm p-6 mb-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="orderNumber" className="block text-sm font-medium text-slate-700 mb-1">
                Order Number
              </label>
              <input
                id="orderNumber"
                type="text"
                value={orderNumber}
                onChange={(e) => setOrderNumber(e.target.value)}
                placeholder="e.g. TS-250125-ABC123"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none"
                data-testid="order-number-input"
              />
            </div>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-1">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email used for your order"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none"
                data-testid="order-email-input"
              />
            </div>
            
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}
            
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-semibold py-3 rounded-lg transition-colors"
              data-testid="track-order-submit-btn"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="w-5 h-5" />
                  Track Order
                </>
              )}
            </button>
          </form>
        </div>

        {/* Order Results */}
        {orderData && (
          <div className="bg-white rounded-xl shadow-sm overflow-hidden">
            {/* Order Header */}
            <div className="p-6 border-b bg-slate-50">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <p className="text-sm text-slate-500">Order Number</p>
                  <p className="text-xl font-bold text-slate-900">{orderData.order_number}</p>
                </div>
                <div className="text-left sm:text-right">
                  <p className="text-sm text-slate-500">Placed on</p>
                  <p className="font-medium text-slate-900">{formatDate(orderData.created_at)}</p>
                </div>
              </div>
            </div>

            {/* Current Status */}
            <div className="p-6 border-b">
              {(() => {
                const statusInfo = getStatusInfo(orderData.status);
                const StatusIcon = statusInfo.icon;
                return (
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center ${statusInfo.color}`}>
                      <StatusIcon className="w-6 h-6" />
                    </div>
                    <div>
                      <p className="font-semibold text-slate-900 text-lg">{statusInfo.label}</p>
                      {orderData.delivery_method === 'delivery' && orderData.estimated_delivery && (
                        <p className="text-sm text-slate-500">
                          Estimated delivery: {orderData.estimated_delivery}
                        </p>
                      )}
                      {orderData.delivery_method === 'collect' && orderData.store_name && (
                        <p className="text-sm text-slate-500">
                          Collection from: {orderData.store_name}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })()}
              
              {/* Tracking Link */}
              {orderData.tracking?.url && (
                <a
                  href={orderData.tracking.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-4 inline-flex items-center gap-2 text-teal-600 hover:text-teal-700 font-medium"
                >
                  <Truck className="w-4 h-4" />
                  Track with carrier
                  {orderData.tracking.number && ` (${orderData.tracking.number})`}
                </a>
              )}
            </div>

            {/* Status Timeline */}
            {orderData.status_history && orderData.status_history.length > 0 && (
              <div className="p-6 border-b">
                <h3 className="font-semibold text-slate-900 mb-4">Order Timeline</h3>
                <div className="space-y-4">
                  {orderData.status_history.map((entry, index) => {
                    const statusInfo = getStatusInfo(entry.status);
                    return (
                      <div key={index} className="flex gap-4">
                        <div className={`w-2 h-2 mt-2 rounded-full ${index === 0 ? 'bg-teal-500' : 'bg-slate-300'}`} />
                        <div className="flex-1">
                          <p className={`font-medium ${index === 0 ? 'text-slate-900' : 'text-slate-600'}`}>
                            {statusInfo.label}
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
            )}

            {/* Order Items */}
            <div className="p-6 border-b">
              <h3 className="font-semibold text-slate-900 mb-4">Order Items</h3>
              <div className="space-y-3">
                {orderData.items.map((item, index) => (
                  <div key={index} className="flex justify-between text-sm">
                    <span className="text-slate-700">
                      {item.name} <span className="text-slate-500">x{item.quantity}</span>
                    </span>
                    <span className="font-medium">{formatPrice(item.price * item.quantity)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Order Total */}
            <div className="p-6 bg-slate-50">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">Subtotal</span>
                  <span>{formatPrice(orderData.subtotal)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">VAT (20%)</span>
                  <span>{formatPrice(orderData.vat)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Delivery</span>
                  <span>{orderData.delivery_fee === 0 ? 'FREE' : formatPrice(orderData.delivery_fee)}</span>
                </div>
                <hr className="my-2" />
                <div className="flex justify-between text-base font-bold">
                  <span>Total</span>
                  <span>{formatPrice(orderData.total)}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Help Section */}
        <div className="mt-8 text-center">
          <p className="text-sm text-slate-500">
            Need help with your order?{' '}
            <a href="mailto:support@tilestation.co.uk" className="text-teal-600 hover:underline">
              Contact support
            </a>
          </p>
          <Link href="/products" className="text-sm text-teal-600 hover:underline mt-2 inline-block">
            Continue Shopping →
          </Link>
        </div>
      </div>
    </div>
  );
}
