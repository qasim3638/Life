import React, { useState, useEffect } from 'react';
import { Package, Truck, CheckCircle, Clock, MapPin, Search, ExternalLink, MessageSquare } from 'lucide-react';
import { api } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';

export const OrderTracking = () => {
  const [orderNumber, setOrderNumber] = useState('');
  const [email, setEmail] = useState('');
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  // "Did you mean…?" recovery cards — populated when strict lookup 404s
  // but we found other paid orders for the same email.
  const [suggestions, setSuggestions] = useState([]);

  // Auto-track when ?order=…&email=… are present in the URL — used by the
  // "Track Your Order" CTA in confirmation/status emails so the customer
  // skips the form entirely.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const o = params.get('order');
    const e = params.get('email');
    if (o && e) {
      setOrderNumber(o);
      setEmail(e);
      runTrack(o, e);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runTrack = async (orderNo, em) => {
    setLoading(true);
    setSearched(true);
    setSuggestions([]);
    try {
      const response = await api.shopTrackOrder(orderNo, em);
      setOrder(response.data);
    } catch (error) {
      setOrder(null);
      // Fall back to fuzzy "did you mean" lookup by email only.
      try {
        const apiBase = process.env.REACT_APP_BACKEND_URL;
        const r = await fetch(`${apiBase}/api/shop/track/suggest?email=${encodeURIComponent(em.trim())}`);
        if (r.ok) {
          const data = await r.json();
          const list = (data.suggestions || []).filter(
            (s) => (s.order_number || '').toUpperCase() !== (orderNo || '').trim().toUpperCase().replace(/^#/, '')
          );
          setSuggestions(list);
        }
      } catch { /* non-fatal — we just don't show suggestions */ }
      // Only show the toast when we couldn't help with a suggestion either.
      toast.error(error.response?.data?.detail || 'Order not found');
    } finally {
      setLoading(false);
    }
  };

  const handleTrack = async (e) => {
    e.preventDefault();
    if (!orderNumber || !email) {
      toast.error('Please enter order number and email');
      return;
    }
    await runTrack(orderNumber, email);
  };

  const applySuggestion = (s) => {
    setOrderNumber(s.order_number);
    runTrack(s.order_number, email);
  };

  const formatPrice = (price) => `£${price?.toFixed(2) || '0.00'}`;
  
  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending_payment':
        return <Clock className="w-5 h-5 text-yellow-500" />;
      case 'confirmed':
      case 'processing':
        return <Package className="w-5 h-5 text-blue-500" />;
      case 'shipped':
        return <Truck className="w-5 h-5 text-indigo-500" />;
      case 'delivered':
      case 'collected':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'ready_for_collection':
        return <MapPin className="w-5 h-5 text-amber-500" />;
      default:
        return <Package className="w-5 h-5 text-slate-500" />;
    }
  };

  const getStatusLabel = (status) => {
    const labels = {
      pending_payment: 'Awaiting Payment',
      confirmed: 'Order Confirmed',
      processing: 'Processing',
      shipped: 'Shipped',
      delivered: 'Delivered',
      ready_for_collection: 'Ready for Collection',
      collected: 'Collected',
      cancelled: 'Cancelled'
    };
    return labels[status] || status;
  };

  const getStatusColor = (status) => {
    const colors = {
      pending_payment: 'bg-yellow-100 text-yellow-800',
      confirmed: 'bg-blue-100 text-blue-800',
      processing: 'bg-purple-100 text-purple-800',
      shipped: 'bg-indigo-100 text-indigo-800',
      delivered: 'bg-green-100 text-green-800',
      ready_for_collection: 'bg-amber-100 text-amber-800',
      collected: 'bg-green-100 text-green-800',
      cancelled: 'bg-red-100 text-red-800'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const statusSteps = ['confirmed', 'processing', 'shipped', 'delivered'];
  const collectSteps = ['confirmed', 'processing', 'ready_for_collection', 'collected'];

  const getCurrentStep = (status, isCollect) => {
    const steps = isCollect ? collectSteps : statusSteps;
    const index = steps.indexOf(status);
    return index >= 0 ? index : -1;
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl md:text-3xl font-bold text-slate-900 mb-2 text-center">
          Track Your Order
        </h1>
        <p className="text-slate-500 text-center mb-8">
          Enter your order number and email to track your delivery
        </p>

        {/* Search Form */}
        <Card className="p-6 mb-8">
          <form onSubmit={handleTrack} className="space-y-4">
            <div>
              <Label htmlFor="order-number">Order Number</Label>
              <Input
                id="order-number"
                placeholder="e.g. TS-260125-ABC123"
                value={orderNumber}
                onChange={(e) => setOrderNumber(e.target.value.toUpperCase())}
                data-testid="track-order-input"
              />
            </div>
            <div>
              <Label htmlFor="email">Email Address</Label>
              <Input
                id="email"
                type="email"
                placeholder="The email used for your order"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="track-email-input"
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading} data-testid="track-submit-btn">
              <Search className="w-4 h-4 mr-2" />
              {loading ? 'Searching...' : 'Track Order'}
            </Button>
          </form>
        </Card>

        {/* Order Details */}
        {searched && order && (
          <div className="space-y-6">
            {/* Status Header */}
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-sm text-slate-500">Order #{order.order_number}</p>
                  <p className="text-xs text-slate-400">Placed on {formatDate(order.created_at)}</p>
                </div>
                <Badge className={getStatusColor(order.status)}>
                  {getStatusLabel(order.status)}
                </Badge>
              </div>

              {/* Progress Tracker */}
              {order.payment_status === 'paid' && order.status !== 'cancelled' && (
                <div className="mt-6">
                  <div className="flex justify-between mb-2">
                    {(order.delivery_method === 'collect' ? collectSteps : statusSteps).map((step, index) => {
                      const currentStep = getCurrentStep(order.status, order.delivery_method === 'collect');
                      const isActive = index <= currentStep;
                      const isCurrent = index === currentStep;
                      
                      return (
                        <div key={step} className="flex flex-col items-center flex-1">
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                            isActive ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-400'
                          } ${isCurrent ? 'ring-2 ring-green-300' : ''}`}>
                            {isActive ? <CheckCircle className="w-5 h-5" /> : index + 1}
                          </div>
                          <span className={`text-xs mt-1 text-center ${isActive ? 'text-green-600' : 'text-slate-400'}`}>
                            {getStatusLabel(step)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Latest Note from team — prominently shown above tracking
                  info so customers see any custom message the team left
                  with the most recent status update (e.g. "Your tiles are
                  on the next van — should arrive Monday morning"). */}
              {(() => {
                const latestNote = (order.status_history || [])
                  .slice()
                  .reverse()
                  .find(h => h && (h.notes || '').trim());
                if (!latestNote) return null;
                return (
                  <div
                    className="mt-4 p-4 bg-gradient-to-br from-amber-50 to-orange-50 border-l-4 border-amber-400 rounded-r-lg"
                    data-testid="track-latest-note"
                  >
                    <div className="flex items-start gap-2">
                      <MessageSquare className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 mb-1">
                          Note from our team
                        </p>
                        <p className="text-sm text-slate-800 whitespace-pre-wrap">
                          &ldquo;{latestNote.notes}&rdquo;
                        </p>
                        <p className="text-[11px] text-slate-500 mt-1">
                          {formatDate(latestNote.timestamp)}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* Tracking Info */}
              {order.tracking?.number && (
                <div className="mt-4 p-3 bg-slate-50 rounded-lg">
                  <p className="text-sm">
                    <span className="text-slate-500">Tracking Number: </span>
                    <span className="font-medium">{order.tracking.number}</span>
                  </p>
                  {order.tracking.url && (
                    <a
                      href={order.tracking.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-amber-600 hover:text-amber-700 flex items-center gap-1 mt-1"
                    >
                      Track with carrier <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              )}

              {/* Collection Store */}
              {order.delivery_method === 'collect' && order.store_name && (
                <div className="mt-4 p-3 bg-amber-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <MapPin className="w-4 h-4 text-amber-600" />
                    <span className="text-sm">
                      <span className="text-slate-500">Collect from: </span>
                      <span className="font-medium">{order.store_name}</span>
                    </span>
                  </div>
                </div>
              )}
            </Card>

            {/* Status History */}
            {order.status_history && order.status_history.length > 0 && (
              <Card className="p-6">
                <h3 className="font-semibold mb-4">Order History</h3>
                <div className="space-y-4">
                  {order.status_history.slice().reverse().map((entry, index) => (
                    <div key={index} className="flex gap-3">
                      <div className="flex-shrink-0 mt-1">
                        {getStatusIcon(entry.status)}
                      </div>
                      <div>
                        <p className="font-medium">{getStatusLabel(entry.status)}</p>
                        {entry.notes && <p className="text-sm text-slate-500">{entry.notes}</p>}
                        <p className="text-xs text-slate-400">{formatDate(entry.timestamp)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* Order Items */}
            <Card className="p-6">
              <h3 className="font-semibold mb-4">Order Items</h3>
              <div className="space-y-3">
                {order.items?.map((item, index) => (
                  <div key={index} className="flex justify-between items-center">
                    <div>
                      <p className="font-medium">{item.name}</p>
                      <p className="text-sm text-slate-500">Qty: {item.quantity}</p>
                    </div>
                    <p className="font-medium">{formatPrice(item.price * item.quantity)}</p>
                  </div>
                ))}
              </div>
              <hr className="my-4" />
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">Subtotal</span>
                  <span>{formatPrice(order.subtotal)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">VAT</span>
                  <span>{formatPrice(order.vat)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Delivery</span>
                  <span>{order.delivery_fee === 0 ? 'FREE' : formatPrice(order.delivery_fee)}</span>
                </div>
                <div className="flex justify-between font-bold text-lg pt-2 border-t">
                  <span>Total</span>
                  <span>{formatPrice(order.total)}</span>
                </div>
              </div>
            </Card>
          </div>
        )}

        {searched && !order && !loading && (
          <>
            {suggestions.length > 0 && (
              <Card
                className="p-5 mb-4 border-amber-200 bg-amber-50"
                data-testid="track-suggestions-card"
              >
                <div className="flex items-start gap-3 mb-3">
                  <Search className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <h3 className="font-semibold text-slate-900">
                      Did you mean one of these?
                    </h3>
                    <p className="text-sm text-slate-600">
                      We couldn&apos;t find that order number, but here&apos;s what we found
                      for <span className="font-medium">{email}</span>:
                    </p>
                  </div>
                </div>
                <div className="space-y-2">
                  {suggestions.map((s) => (
                    <button
                      key={s.order_number}
                      type="button"
                      onClick={() => applySuggestion(s)}
                      className="w-full text-left bg-white hover:bg-amber-100/40 border border-amber-200 hover:border-amber-300 rounded-lg p-3 transition flex items-center justify-between gap-3"
                      data-testid={`track-suggestion-${s.order_number}`}
                    >
                      <div className="min-w-0">
                        <p className="font-medium text-slate-900">
                          #{s.order_number}
                        </p>
                        <p className="text-xs text-slate-500">
                          {s.created_at ? formatDate(s.created_at) : ''}
                          {s.delivery_method ? ` · ${s.delivery_method === 'collect' ? 'Click & Collect' : 'Delivery'}` : ''}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0">
                        <Badge className={getStatusColor(s.status)}>
                          {getStatusLabel(s.status)}
                        </Badge>
                        <span className="font-semibold text-slate-900 tabular-nums">
                          {formatPrice(s.total)}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              </Card>
            )}
            <Card className="p-8 text-center" data-testid="track-empty-state">
              <Package className="w-12 h-12 text-slate-300 mx-auto mb-4" />
              <h3 className="font-semibold text-slate-900 mb-2">Order Not Found</h3>
              <p className="text-slate-500 text-sm">
                {suggestions.length > 0
                  ? 'Tap a result above, or double-check the order number you entered.'
                  : 'Please check your order number and email address and try again.'}
              </p>
            </Card>
          </>
        )}
      </div>
    </div>
  );
};

export default OrderTracking;
