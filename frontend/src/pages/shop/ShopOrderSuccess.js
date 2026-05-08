import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../../lib/api';
import { CheckCircle, Package, ArrowRight, XCircle, Loader2 } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';

export const ShopOrderSuccess = () => {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get('session_id');
  const orderId = searchParams.get('order_id');
  
  const [status, setStatus] = useState('checking'); // checking, success, failed, expired
  const [orderDetails, setOrderDetails] = useState(null);
  const [attempts, setAttempts] = useState(0);
  const maxAttempts = 10;

  useEffect(() => {
    if (sessionId) {
      pollPaymentStatus();
    } else {
      setStatus('failed');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const pollPaymentStatus = async () => {
    if (attempts >= maxAttempts) {
      setStatus('failed');
      return;
    }

    try {
      const response = await api.shopGetCheckoutStatus(sessionId);
      const data = response.data;
      
      if (data.payment_status === 'paid') {
        setStatus('success');
        setOrderDetails(data);
      } else if (data.status === 'expired') {
        setStatus('expired');
      } else {
        // Payment still processing, try again
        setAttempts(prev => prev + 1);
        setTimeout(pollPaymentStatus, 2000);
      }
    } catch (error) {
      console.error('Error checking payment status:', error);
      setAttempts(prev => prev + 1);
      if (attempts < maxAttempts - 1) {
        setTimeout(pollPaymentStatus, 2000);
      } else {
        setStatus('failed');
      }
    }
  };

  const formatPrice = (price) => `£${price?.toFixed(2) || '0.00'}`;

  if (status === 'checking') {
    return (
      <div className="min-h-[60vh] flex items-center justify-center px-4">
        <Card className="w-full max-w-md p-8 text-center">
          <Loader2 className="w-16 h-16 text-amber-500 mx-auto mb-4 animate-spin" />
          <h1 className="text-2xl font-bold text-slate-900 mb-2">Processing Payment</h1>
          <p className="text-slate-500">Please wait while we confirm your payment...</p>
          <div className="mt-4 w-full bg-gray-200 rounded-full h-2">
            <div 
              className="bg-amber-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${(attempts / maxAttempts) * 100}%` }}
            />
          </div>
        </Card>
      </div>
    );
  }

  if (status === 'expired') {
    return (
      <div className="min-h-[60vh] flex items-center justify-center px-4">
        <Card className="w-full max-w-md p-8 text-center">
          <XCircle className="w-16 h-16 text-orange-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-slate-900 mb-2">Payment Session Expired</h1>
          <p className="text-slate-500 mb-6">
            Your payment session has expired. Please try again.
          </p>
          <Link to="/shop/cart">
            <Button className="bg-amber-500 hover:bg-amber-600 text-slate-900">
              Return to Cart
            </Button>
          </Link>
        </Card>
      </div>
    );
  }

  if (status === 'failed') {
    return (
      <div className="min-h-[60vh] flex items-center justify-center px-4">
        <Card className="w-full max-w-md p-8 text-center">
          <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-slate-900 mb-2">Payment Failed</h1>
          <p className="text-slate-500 mb-6">
            We couldn&apos;t process your payment. Please try again or contact support.
          </p>
          <div className="space-y-3">
            <Link to="/shop/cart">
              <Button className="w-full bg-amber-500 hover:bg-amber-600 text-slate-900">
                Return to Cart
              </Button>
            </Link>
            <Link to="/shop">
              <Button variant="outline" className="w-full">
                Continue Shopping
              </Button>
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4 py-12">
      <Card className="w-full max-w-lg p-8 text-center">
        <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <CheckCircle className="w-12 h-12 text-green-600" />
        </div>
        
        <h1 className="text-2xl md:text-3xl font-bold text-slate-900 mb-2">
          Order Confirmed!
        </h1>
        <p className="text-slate-500 mb-6">
          Thank you for your purchase. We&apos;ve sent a confirmation email to your address.
        </p>

        {orderDetails && (
          <div className="bg-slate-50 rounded-lg p-4 mb-6 text-left">
            <div className="flex items-center gap-3 mb-3">
              <Package className="w-5 h-5 text-amber-600" />
              <span className="font-semibold">Order Details</span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">Order Number</span>
                <span className="font-medium">{orderDetails.order_number}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Amount Paid</span>
                <span className="font-medium">{formatPrice(orderDetails.amount)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Status</span>
                <span className="font-medium text-green-600">Confirmed</span>
              </div>
            </div>
          </div>
        )}

        <div className="space-y-3">
          <Link to="/shop/orders">
            <Button className="w-full bg-amber-500 hover:bg-amber-600 text-slate-900">
              View Order History
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </Link>
          <Link to="/shop">
            <Button variant="outline" className="w-full">
              Continue Shopping
            </Button>
          </Link>
        </div>

        <p className="mt-6 text-sm text-slate-400">
          Questions about your order? Contact us at info@tilestation.co.uk
        </p>
      </Card>
    </div>
  );
};

export default ShopOrderSuccess;
