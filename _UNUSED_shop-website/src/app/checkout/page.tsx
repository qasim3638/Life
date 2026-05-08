'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { 
  ChevronLeft, 
  Lock, 
  Truck, 
  Store, 
  CreditCard,
  UserPlus,
  Loader2
} from 'lucide-react';
import { formatPrice } from '@/lib/utils';
import api, { Store as StoreType, CartItem } from '@/lib/api';

export default function CheckoutPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [stores, setStores] = useState<StoreType[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [deliveryMethod, setDeliveryMethod] = useState<'delivery' | 'collect'>('delivery');
  const [paymentMethod, setPaymentMethod] = useState<'stripe' | 'paypal'>('stripe');
  const [createAccount, setCreateAccount] = useState(false);
  const [error, setError] = useState('');
  
  const [formData, setFormData] = useState({
    customer_name: '',
    customer_email: '',
    customer_phone: '',
    address_line1: '',
    address_line2: '',
    city: '',
    postcode: '',
    collect_store_id: '',
    notes: '',
    password: '',
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      // Load cart from localStorage
      const savedCart = localStorage.getItem('shop_cart');
      const cartItems = savedCart ? JSON.parse(savedCart) : [];
      
      if (cartItems.length === 0) {
        router.push('/cart');
        return;
      }
      
      setCart(cartItems);
      
      // Load stores for click & collect
      const storeData = await api.getStores();
      setStores(storeData);
    } catch (err) {
      console.error('Failed to load checkout data:', err);
    } finally {
      setPageLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError('');
  };

  // Calculate totals
  const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
  const vat = subtotal * 0.2;
  const deliveryFee = deliveryMethod === 'collect' ? 0 : (subtotal >= 500 ? 0 : 49.99);
  const total = subtotal + vat + deliveryFee;

  const validateForm = () => {
    if (!formData.customer_name.trim()) {
      setError('Please enter your name');
      return false;
    }
    if (!formData.customer_email.trim() || !formData.customer_email.includes('@')) {
      setError('Please enter a valid email address');
      return false;
    }
    
    if (deliveryMethod === 'delivery') {
      if (!formData.address_line1.trim()) {
        setError('Please enter your address');
        return false;
      }
      if (!formData.city.trim()) {
        setError('Please enter your city');
        return false;
      }
      if (!formData.postcode.trim()) {
        setError('Please enter your postcode');
        return false;
      }
    } else {
      if (!formData.collect_store_id) {
        setError('Please select a store for collection');
        return false;
      }
    }
    
    if (createAccount && (!formData.password || formData.password.length < 8)) {
      setError('Password must be at least 8 characters');
      return false;
    }
    
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) return;
    
    setLoading(true);
    setError('');
    
    try {
      // Create guest order
      const orderData = {
        customer_name: formData.customer_name,
        customer_email: formData.customer_email,
        customer_phone: formData.customer_phone,
        delivery_method: deliveryMethod,
        delivery_address: deliveryMethod === 'delivery' ? {
          line1: formData.address_line1,
          line2: formData.address_line2,
          city: formData.city,
          postcode: formData.postcode,
          country: 'United Kingdom'
        } : {},
        collect_store_id: deliveryMethod === 'collect' ? formData.collect_store_id : undefined,
        notes: formData.notes,
        items: cart.map(item => ({
          product_id: item.product_id,
          name: item.name,
          sku: item.sku || '',
          price: item.price,
          quantity: item.quantity,
          image: item.image || ''
        })),
        create_account: createAccount,
        password: createAccount ? formData.password : undefined
      };

      const orderResponse = await api.createGuestOrder(orderData);
      
      // Clear cart from localStorage before redirect
      localStorage.removeItem('shop_cart');
      
      if (paymentMethod === 'paypal') {
        // Create PayPal order
        const paypalResponse = await api.createPayPalOrder(
          orderResponse.order_id,
          `${window.location.origin}/paypal-success`,
          `${window.location.origin}/checkout?cancelled=true`
        );
        
        // Redirect to PayPal
        window.location.href = paypalResponse.approval_url;
      } else {
        // Create Stripe checkout session
        const checkoutResponse = await api.createGuestCheckoutSession(
          orderResponse.order_id,
          window.location.origin
        );
        
        // Redirect to Stripe checkout
        window.location.href = checkoutResponse.checkout_url;
      }
      
    } catch (err: any) {
      console.error('Checkout error:', err);
      setError(err.response?.data?.detail || 'Checkout failed. Please try again.');
      setLoading(false);
    }
  };

  if (pageLoading) {
    return (
      <div className="container mx-auto px-4 py-16">
        <div className="flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
        </div>
      </div>
    );
  }

  if (cart.length === 0) {
    return null;
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Back Button */}
      <Link
        href="/cart"
        className="inline-flex items-center text-slate-600 hover:text-slate-900 mb-6"
      >
        <ChevronLeft className="w-4 h-4 mr-1" />
        Back to Cart
      </Link>

      <h1 className="text-2xl md:text-3xl font-bold text-slate-900 mb-8">Checkout</h1>

      {/* Guest Checkout Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <p className="font-medium text-blue-900">Checking out as guest</p>
            <p className="text-sm text-blue-700">No account needed - or create one during checkout</p>
          </div>
          <Link
            href="/login?redirect=/checkout"
            className="text-sm font-medium text-blue-600 hover:text-blue-800"
          >
            Sign in instead →
          </Link>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Checkout Form */}
          <div className="lg:col-span-2 space-y-6">
            {/* Contact Information */}
            <div className="bg-white p-6 rounded-xl shadow-sm">
              <h2 className="text-lg font-semibold mb-4">Contact Information</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="customer_name" className="block text-sm font-medium text-slate-700 mb-1">
                    Full Name *
                  </label>
                  <input
                    id="customer_name"
                    name="customer_name"
                    type="text"
                    value={formData.customer_name}
                    onChange={handleInputChange}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                    required
                  />
                </div>
                <div>
                  <label htmlFor="customer_email" className="block text-sm font-medium text-slate-700 mb-1">
                    Email *
                  </label>
                  <input
                    id="customer_email"
                    name="customer_email"
                    type="email"
                    value={formData.customer_email}
                    onChange={handleInputChange}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                    required
                  />
                </div>
                <div className="md:col-span-2">
                  <label htmlFor="customer_phone" className="block text-sm font-medium text-slate-700 mb-1">
                    Phone Number
                  </label>
                  <input
                    id="customer_phone"
                    name="customer_phone"
                    type="tel"
                    value={formData.customer_phone}
                    onChange={handleInputChange}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                  />
                </div>
              </div>
            </div>

            {/* Delivery Method */}
            <div className="bg-white p-6 rounded-xl shadow-sm">
              <h2 className="text-lg font-semibold mb-4">Delivery Method</h2>
              <div className="space-y-3">
                <label 
                  className={`flex items-start gap-4 p-4 border rounded-lg cursor-pointer transition-colors ${
                    deliveryMethod === 'delivery' ? 'border-amber-500 bg-amber-50' : 'hover:bg-gray-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="delivery_method"
                    value="delivery"
                    checked={deliveryMethod === 'delivery'}
                    onChange={() => setDeliveryMethod('delivery')}
                    className="mt-1 accent-amber-500"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <Truck className="w-5 h-5 text-amber-600" />
                      <span className="font-medium">Home Delivery</span>
                    </div>
                    <p className="text-sm text-slate-500 mt-1">
                      {subtotal >= 500 ? 'FREE delivery' : '£49.99 delivery (FREE on orders over £500)'}
                    </p>
                  </div>
                </label>
                
                <label 
                  className={`flex items-start gap-4 p-4 border rounded-lg cursor-pointer transition-colors ${
                    deliveryMethod === 'collect' ? 'border-amber-500 bg-amber-50' : 'hover:bg-gray-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="delivery_method"
                    value="collect"
                    checked={deliveryMethod === 'collect'}
                    onChange={() => setDeliveryMethod('collect')}
                    className="mt-1 accent-amber-500"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <Store className="w-5 h-5 text-amber-600" />
                      <span className="font-medium">Click & Collect</span>
                    </div>
                    <p className="text-sm text-slate-500 mt-1">FREE - Collect from one of our showrooms</p>
                  </div>
                </label>
              </div>
            </div>

            {/* Delivery Address */}
            {deliveryMethod === 'delivery' && (
              <div className="bg-white p-6 rounded-xl shadow-sm">
                <h2 className="text-lg font-semibold mb-4">Delivery Address</h2>
                <div className="space-y-4">
                  <div>
                    <label htmlFor="address_line1" className="block text-sm font-medium text-slate-700 mb-1">
                      Address Line 1 *
                    </label>
                    <input
                      id="address_line1"
                      name="address_line1"
                      type="text"
                      value={formData.address_line1}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                      required={deliveryMethod === 'delivery'}
                    />
                  </div>
                  <div>
                    <label htmlFor="address_line2" className="block text-sm font-medium text-slate-700 mb-1">
                      Address Line 2
                    </label>
                    <input
                      id="address_line2"
                      name="address_line2"
                      type="text"
                      value={formData.address_line2}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="city" className="block text-sm font-medium text-slate-700 mb-1">
                        City *
                      </label>
                      <input
                        id="city"
                        name="city"
                        type="text"
                        value={formData.city}
                        onChange={handleInputChange}
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                        required={deliveryMethod === 'delivery'}
                      />
                    </div>
                    <div>
                      <label htmlFor="postcode" className="block text-sm font-medium text-slate-700 mb-1">
                        Postcode *
                      </label>
                      <input
                        id="postcode"
                        name="postcode"
                        type="text"
                        value={formData.postcode}
                        onChange={handleInputChange}
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                        required={deliveryMethod === 'delivery'}
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Store Selection */}
            {deliveryMethod === 'collect' && (
              <div className="bg-white p-6 rounded-xl shadow-sm">
                <h2 className="text-lg font-semibold mb-4">Select Store for Collection</h2>
                <div className="space-y-3">
                  {stores.map((store) => (
                    <label
                      key={store.id}
                      className={`flex items-start gap-4 p-4 border rounded-lg cursor-pointer transition-colors ${
                        formData.collect_store_id === store.id ? 'border-amber-500 bg-amber-50' : 'hover:bg-gray-50'
                      }`}
                    >
                      <input
                        type="radio"
                        name="collect_store_id"
                        value={store.id}
                        checked={formData.collect_store_id === store.id}
                        onChange={(e) => setFormData(prev => ({ ...prev, collect_store_id: e.target.value }))}
                        className="mt-1 accent-amber-500"
                      />
                      <div>
                        <span className="font-medium">{store.name}</span>
                        <p className="text-sm text-slate-500">{store.address}</p>
                        <p className="text-xs text-slate-400 mt-1">{store.opening_hours}</p>
                      </div>
                    </label>
                  ))}
                  {stores.length === 0 && (
                    <p className="text-slate-500 text-center py-4">No stores available for collection</p>
                  )}
                </div>
              </div>
            )}

            {/* Order Notes */}
            <div className="bg-white p-6 rounded-xl shadow-sm">
              <h2 className="text-lg font-semibold mb-4">Order Notes (Optional)</h2>
              <textarea
                name="notes"
                value={formData.notes}
                onChange={handleInputChange}
                placeholder="Any special instructions for your order..."
                rows={3}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none resize-none"
              />
            </div>

            {/* Create Account Option */}
            <div className="bg-white p-6 rounded-xl shadow-sm">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={createAccount}
                  onChange={(e) => setCreateAccount(e.target.checked)}
                  className="mt-1 accent-amber-500"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <UserPlus className="w-4 h-4 text-amber-600" />
                    <span className="font-medium">Create an account</span>
                  </div>
                  <p className="text-sm text-slate-500 mt-1">
                    Track your orders, save addresses, and checkout faster next time
                  </p>
                  
                  {createAccount && (
                    <div className="mt-4">
                      <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1">
                        Create Password *
                      </label>
                      <input
                        id="password"
                        name="password"
                        type="password"
                        value={formData.password}
                        onChange={handleInputChange}
                        placeholder="At least 8 characters"
                        minLength={8}
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                      />
                    </div>
                  )}
                </div>
              </label>
            </div>

            {/* Payment Method */}
            <div className="bg-white p-6 rounded-xl shadow-sm">
              <h2 className="text-lg font-semibold mb-4">Payment Method</h2>
              <div className="space-y-3">
                <label 
                  className={`flex items-center gap-4 p-4 border rounded-lg cursor-pointer transition-colors ${
                    paymentMethod === 'stripe' ? 'border-amber-500 bg-amber-50' : 'hover:bg-gray-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="payment_method"
                    value="stripe"
                    checked={paymentMethod === 'stripe'}
                    onChange={() => setPaymentMethod('stripe')}
                    className="accent-amber-500"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <CreditCard className="w-5 h-5 text-slate-600" />
                      <span className="font-medium">Credit / Debit Card</span>
                    </div>
                    <p className="text-sm text-slate-500 mt-1">Pay securely with Visa, Mastercard, Amex</p>
                  </div>
                  <div className="flex gap-1">
                    <div className="w-8 h-5 bg-[#1A1F71] rounded text-white text-[8px] flex items-center justify-center font-bold">VISA</div>
                    <div className="w-8 h-5 bg-[#EB001B] rounded-l bg-gradient-to-r from-[#EB001B] to-[#F79E1B] text-[8px]"></div>
                  </div>
                </label>
                
                <label 
                  className={`flex items-center gap-4 p-4 border rounded-lg cursor-pointer transition-colors ${
                    paymentMethod === 'paypal' ? 'border-amber-500 bg-amber-50' : 'hover:bg-gray-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="payment_method"
                    value="paypal"
                    checked={paymentMethod === 'paypal'}
                    onChange={() => setPaymentMethod('paypal')}
                    className="accent-amber-500"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none">
                        <path d="M19.5 8.5c0 3-2.5 5.5-5.5 5.5h-1l-1 4H8.5l3-12h5c1.7 0 3 1.3 3 3z" fill="#003087"/>
                        <path d="M16 5.5c0 3-2.5 5.5-5.5 5.5h-1l-1 4H5l3-12h5c1.7 0 3 1.3 3 3z" fill="#009cde"/>
                      </svg>
                      <span className="font-medium">PayPal</span>
                    </div>
                    <p className="text-sm text-slate-500 mt-1">Pay with your PayPal account</p>
                  </div>
                  <div className="w-16 h-5 bg-[#003087] rounded flex items-center justify-center">
                    <span className="text-white text-[10px] font-bold">PayPal</span>
                  </div>
                </label>
              </div>
            </div>
          </div>

          {/* Order Summary */}
          <div>
            <div className="bg-white p-6 rounded-xl shadow-sm sticky top-24">
              <h2 className="text-lg font-bold text-slate-900 mb-4">Order Summary</h2>
              
              {/* Items */}
              <div className="space-y-3 mb-4 max-h-60 overflow-y-auto">
                {cart.map((item) => (
                  <div key={item.product_id} className="flex gap-3">
                    <div className="w-12 h-12 bg-gray-100 rounded flex-shrink-0 overflow-hidden relative">
                      {item.image ? (
                        <Image 
                          src={item.image} 
                          alt={item.name} 
                          fill
                          className="object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm">🪨</div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium line-clamp-1">{item.name}</p>
                      <p className="text-xs text-slate-500">Qty: {item.quantity}</p>
                    </div>
                    <p className="text-sm font-medium">{formatPrice(item.price * item.quantity)}</p>
                  </div>
                ))}
              </div>
              
              <hr className="my-4" />
              
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">Subtotal</span>
                  <span className="font-medium">{formatPrice(subtotal)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">VAT (20%)</span>
                  <span className="font-medium">{formatPrice(vat)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Delivery</span>
                  <span className="font-medium">
                    {deliveryFee === 0 ? (
                      <span className="text-green-600">FREE</span>
                    ) : (
                      formatPrice(deliveryFee)
                    )}
                  </span>
                </div>
                
                <hr className="my-2" />
                
                <div className="flex justify-between text-lg font-bold">
                  <span>Total</span>
                  <span>{formatPrice(total)}</span>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full mt-6 flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-300 text-slate-900 font-semibold py-3 rounded-lg transition-colors"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <CreditCard className="w-5 h-5" />
                    Pay {formatPrice(total)}
                  </>
                )}
              </button>

              <div className="flex items-center justify-center gap-2 mt-4 text-xs text-slate-500">
                <Lock className="w-3 h-3" />
                Secure checkout powered by Stripe
              </div>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
