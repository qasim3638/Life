'use client';

import { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { CheckCircle, Package, Mail, ArrowRight, Loader2, XCircle } from 'lucide-react';
import api from '@/lib/api';
import { formatPrice } from '@/lib/utils';

function PayPalSuccessContent() {
  const searchParams = useSearchParams();
  const paymentId = searchParams.get('paymentId');
  const payerId = searchParams.get('PayerID');
  
  const [loading, setLoading] = useState(true);
  const [orderData, setOrderData] = useState<any>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (paymentId && payerId) {
      capturePayment();
    } else {
      setError('Missing payment information');
      setLoading(false);
    }
  }, [paymentId, payerId]);

  const capturePayment = async () => {
    try {
      const result = await api.capturePayPalPayment(paymentId!, payerId!);
      setOrderData(result);
    } catch (err: any) {
      console.error('Failed to capture PayPal payment:', err);
      setError(err.response?.data?.detail || 'Payment capture failed. Please contact support.');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-lg mx-auto text-center">
          <Loader2 className="w-12 h-12 animate-spin text-amber-500 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-slate-900 mb-2">Processing Payment...</h1>
          <p className="text-slate-500">Please wait while we confirm your PayPal payment</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-lg mx-auto text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <XCircle className="w-8 h-8 text-red-500" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900 mb-2">Payment Issue</h1>
          <p className="text-slate-500 mb-8">{error}</p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/cart"
              className="inline-flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-600 text-slate-900 font-semibold px-6 py-3 rounded-lg"
            >
              Return to Cart
            </Link>
            <a
              href="mailto:support@tilestation.co.uk"
              className="inline-flex items-center justify-center gap-2 border border-slate-300 hover:bg-slate-50 text-slate-700 font-semibold px-6 py-3 rounded-lg"
            >
              Contact Support
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-16">
      <div className="max-w-2xl mx-auto">
        {/* Success Header */}
        <div className="text-center mb-10">
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="w-10 h-10 text-green-500" />
          </div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Payment Successful!</h1>
          <p className="text-slate-500">Thank you for your PayPal payment</p>
        </div>

        {/* Order Details Card */}
        <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
          <div className="flex items-center justify-between pb-4 border-b">
            <div>
              <p className="text-sm text-slate-500">Order Number</p>
              <p className="text-lg font-bold text-slate-900">{orderData?.order_number || 'Processing...'}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-slate-500">Payment Method</p>
              <div className="flex items-center gap-2 justify-end">
                <div className="w-16 h-5 bg-[#003087] rounded flex items-center justify-center">
                  <span className="text-white text-[10px] font-bold">PayPal</span>
                </div>
              </div>
            </div>
          </div>

          {/* What's Next */}
          <div className="py-6">
            <h2 className="font-semibold text-slate-900 mb-4">What happens next?</h2>
            <div className="space-y-4">
              <div className="flex gap-4">
                <div className="w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0">
                  <Mail className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <p className="font-medium text-slate-900">Confirmation Email</p>
                  <p className="text-sm text-slate-500">
                    We've sent an order confirmation to your email with all the details.
                  </p>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0">
                  <Package className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <p className="font-medium text-slate-900">Order Processing</p>
                  <p className="text-sm text-slate-500">
                    We're preparing your order. You'll receive tracking information once it ships.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Track Order Info */}
          <div className="pt-4 border-t bg-slate-50 -mx-6 -mb-6 p-6 rounded-b-xl">
            <p className="text-sm text-slate-600 mb-3">
              <strong>Save your order number:</strong> {orderData?.order_number}
            </p>
            <p className="text-sm text-slate-500">
              You can track your order status anytime using your order number and email address.
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/track-order"
            className="inline-flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-600 text-slate-900 font-semibold px-6 py-3 rounded-lg"
          >
            Track Your Order
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            href="/products"
            className="inline-flex items-center justify-center gap-2 border border-slate-300 hover:bg-slate-50 text-slate-700 font-semibold px-6 py-3 rounded-lg"
          >
            Continue Shopping
          </Link>
        </div>

        {/* Help Section */}
        <div className="mt-10 text-center">
          <p className="text-sm text-slate-500">
            Questions about your order? Contact us at{' '}
            <a href="mailto:support@tilestation.co.uk" className="text-amber-600 hover:underline">
              support@tilestation.co.uk
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}

export default function PayPalSuccessPage() {
  return (
    <Suspense fallback={
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-lg mx-auto text-center">
          <Loader2 className="w-12 h-12 animate-spin text-amber-500 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-slate-900">Loading...</h1>
        </div>
      </div>
    }>
      <PayPalSuccessContent />
    </Suspense>
  );
}
