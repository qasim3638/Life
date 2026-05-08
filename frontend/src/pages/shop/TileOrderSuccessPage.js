import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { CheckCircle, Package, Mail, ArrowRight } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { ShopHeader, ShopFooter } from './TileStationHome';

const TileOrderSuccessPage = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { orderNumber, total, email } = location.state || {};

  if (!orderNumber) {
    navigate('/tiles');
    return null;
  }

  return (
    <div className="min-h-screen bg-white">
      <ShopHeader />

      <div className="container mx-auto px-4 py-16">
        <div className="max-w-lg mx-auto text-center">
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="h-10 w-10 text-green-600" />
          </div>

          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Thank you for your order!
          </h1>
          
          <p className="text-gray-600 mb-8">
            Your order has been placed successfully.
          </p>

          <div className="bg-gray-50 rounded-lg p-6 mb-8">
            <div className="flex justify-between items-center border-b pb-4 mb-4">
              <span className="text-gray-600">Order Number</span>
              <span className="font-bold text-lg">{orderNumber}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Total Paid</span>
              <span className="font-bold text-lg text-amber-500">£{total?.toFixed(2)}</span>
            </div>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-8">
            <div className="flex items-start gap-3 text-left">
              <Mail className="h-5 w-5 text-amber-500 mt-0.5" />
              <div>
                <p className="font-medium text-amber-600">Confirmation Email Sent</p>
                <p className="text-sm text-amber-500 mt-1">
                  We've sent a confirmation email to <strong>{email}</strong> with your order details.
                </p>
              </div>
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-8">
            <div className="flex items-start gap-3 text-left">
              <Package className="h-5 w-5 text-blue-600 mt-0.5" />
              <div>
                <p className="font-medium text-blue-800">What's Next?</p>
                <p className="text-sm text-blue-700 mt-1">
                  We'll notify you when your order is ready for delivery or collection.
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              variant="outline"
              onClick={() => navigate('/tiles')}
            >
              Continue Shopping
            </Button>
            <Button
              className="bg-[#333333] hover:bg-[#444444] text-[#F7EA1C] font-semibold"
              onClick={() => navigate('/shop/orders')}
              data-testid="view-orders-btn"
            >
              View Orders
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      <ShopFooter />
    </div>
  );
};

export default TileOrderSuccessPage;
