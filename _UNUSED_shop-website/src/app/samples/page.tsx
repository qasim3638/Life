'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { 
  Scissors, 
  Package, 
  Truck, 
  X, 
  Plus,
  Loader2,
  Check,
  Info
} from 'lucide-react';
import api, { Product } from '@/lib/api';
import { formatPrice } from '@/lib/utils';

interface SampleInfo {
  max_samples: number;
  postage_fee: number;
  delivery_time: string;
  description: string;
  terms: string[];
}

export default function SamplesPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedSamples, setSelectedSamples] = useState<Product[]>([]);
  const [sampleInfo, setSampleInfo] = useState<SampleInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showCheckout, setShowCheckout] = useState(false);
  const [error, setError] = useState('');
  
  const [formData, setFormData] = useState({
    customer_name: '',
    customer_email: '',
    customer_phone: '',
    address_line1: '',
    address_line2: '',
    city: '',
    postcode: '',
    notes: ''
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [productsData, infoData] = await Promise.all([
        api.getProducts({ limit: 50, in_stock_only: true }),
        api.getSampleInfo()
      ]);
      setProducts(productsData.products);
      setSampleInfo(infoData);
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredProducts = products.filter(p =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.sku.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toggleSample = (product: Product) => {
    const isSelected = selectedSamples.some(s => s.id === product.id);
    
    if (isSelected) {
      setSelectedSamples(prev => prev.filter(s => s.id !== product.id));
    } else {
      if (selectedSamples.length >= (sampleInfo?.max_samples || 3)) {
        setError(`Maximum ${sampleInfo?.max_samples || 3} samples allowed`);
        return;
      }
      setSelectedSamples(prev => [...prev, product]);
      setError('');
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (selectedSamples.length === 0) {
      setError('Please select at least one sample');
      return;
    }
    
    if (!formData.customer_name || !formData.customer_email) {
      setError('Please fill in your name and email');
      return;
    }
    
    if (!formData.address_line1 || !formData.city || !formData.postcode) {
      setError('Please fill in your delivery address');
      return;
    }
    
    setSubmitting(true);
    setError('');
    
    try {
      // Create sample order
      const orderData = {
        customer_name: formData.customer_name,
        customer_email: formData.customer_email,
        customer_phone: formData.customer_phone,
        delivery_address: {
          line1: formData.address_line1,
          line2: formData.address_line2,
          city: formData.city,
          postcode: formData.postcode,
          country: 'United Kingdom'
        },
        product_ids: selectedSamples.map(s => s.id),
        notes: formData.notes
      };
      
      const orderResponse = await api.createSampleOrder(orderData);
      
      // Create checkout session
      const checkoutResponse = await api.createSampleCheckout(
        orderResponse.order_id,
        window.location.origin
      );
      
      // Redirect to Stripe
      window.location.href = checkoutResponse.checkout_url;
      
    } catch (err: any) {
      console.error('Sample order error:', err);
      setError(err.response?.data?.detail || 'Failed to create sample order');
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-16">
        <div className="flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="text-center mb-10">
        <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Scissors className="w-8 h-8 text-amber-600" />
        </div>
        <h1 className="text-2xl md:text-3xl font-bold text-slate-900 mb-2">Order Free Samples</h1>
        <p className="text-slate-500 max-w-xl mx-auto">
          {sampleInfo?.description || 'Order up to 3 free cut samples. You only pay postage.'}
        </p>
      </div>

      {/* Info Banner */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-8 max-w-3xl mx-auto">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-amber-800">
            <p className="font-medium mb-1">How it works:</p>
            <ul className="space-y-1">
              {sampleInfo?.terms.map((term, idx) => (
                <li key={idx}>• {term}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {!showCheckout ? (
        <>
          {/* Selected Samples */}
          <div className="max-w-3xl mx-auto mb-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-slate-900">
                Selected Samples ({selectedSamples.length}/{sampleInfo?.max_samples || 3})
              </h2>
              {selectedSamples.length > 0 && (
                <button
                  onClick={() => setSelectedSamples([])}
                  className="text-sm text-slate-500 hover:text-slate-700"
                >
                  Clear all
                </button>
              )}
            </div>
            
            {selectedSamples.length > 0 ? (
              <div className="bg-white rounded-xl shadow-sm p-4">
                <div className="flex flex-wrap gap-3">
                  {selectedSamples.map((sample) => (
                    <div
                      key={sample.id}
                      className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg p-2 pr-3"
                    >
                      <div className="w-10 h-10 bg-gray-100 rounded overflow-hidden relative flex-shrink-0">
                        {sample.images?.[0] ? (
                          <Image src={sample.images[0]} alt={sample.name} fill className="object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-sm">🪨</div>
                        )}
                      </div>
                      <span className="text-sm font-medium text-slate-700 max-w-[150px] truncate">
                        {sample.name}
                      </span>
                      <button
                        onClick={() => toggleSample(sample)}
                        className="ml-1 p-1 hover:bg-amber-100 rounded"
                      >
                        <X className="w-4 h-4 text-slate-500" />
                      </button>
                    </div>
                  ))}
                </div>
                
                <div className="flex items-center justify-between mt-4 pt-4 border-t">
                  <div>
                    <p className="text-sm text-slate-500">Postage Fee</p>
                    <p className="text-lg font-bold text-slate-900">{formatPrice(sampleInfo?.postage_fee || 4.99)}</p>
                  </div>
                  <button
                    onClick={() => setShowCheckout(true)}
                    className="bg-amber-500 hover:bg-amber-600 text-slate-900 font-semibold px-6 py-2 rounded-lg transition-colors"
                  >
                    Continue to Checkout
                  </button>
                </div>
              </div>
            ) : (
              <div className="bg-slate-50 rounded-xl p-8 text-center">
                <Package className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-500">Select up to {sampleInfo?.max_samples || 3} tiles to sample</p>
              </div>
            )}
          </div>

          {error && (
            <div className="max-w-3xl mx-auto mb-6">
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            </div>
          )}

          {/* Product Search */}
          <div className="max-w-3xl mx-auto mb-6">
            <input
              type="text"
              placeholder="Search tiles..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
            />
          </div>

          {/* Product Grid */}
          <div className="max-w-5xl mx-auto">
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {filteredProducts.map((product) => {
                const isSelected = selectedSamples.some(s => s.id === product.id);
                return (
                  <button
                    key={product.id}
                    onClick={() => toggleSample(product)}
                    className={`text-left bg-white rounded-xl shadow-sm overflow-hidden transition-all ${
                      isSelected ? 'ring-2 ring-amber-500' : 'hover:shadow-md'
                    }`}
                  >
                    <div className="aspect-square bg-gray-100 relative">
                      {product.images?.[0] ? (
                        <Image
                          src={product.images[0]}
                          alt={product.name}
                          fill
                          className="object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <Package className="w-10 h-10 text-gray-300" />
                        </div>
                      )}
                      {isSelected && (
                        <div className="absolute inset-0 bg-amber-500/20 flex items-center justify-center">
                          <div className="w-8 h-8 bg-amber-500 rounded-full flex items-center justify-center">
                            <Check className="w-5 h-5 text-white" />
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="p-2">
                      <p className="text-xs font-medium text-slate-900 line-clamp-2">{product.name}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </>
      ) : (
        /* Checkout Form */
        <div className="max-w-2xl mx-auto">
          <button
            onClick={() => setShowCheckout(false)}
            className="text-amber-600 hover:text-amber-700 mb-6 inline-flex items-center gap-1"
          >
            ← Back to sample selection
          </button>
          
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-6">Delivery Details</h2>
            
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Full Name *</label>
                  <input
                    name="customer_name"
                    type="text"
                    value={formData.customer_name}
                    onChange={handleInputChange}
                    required
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Email *</label>
                  <input
                    name="customer_email"
                    type="email"
                    value={formData.customer_email}
                    onChange={handleInputChange}
                    required
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Phone</label>
                <input
                  name="customer_phone"
                  type="tel"
                  value={formData.customer_phone}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Address Line 1 *</label>
                <input
                  name="address_line1"
                  type="text"
                  value={formData.address_line1}
                  onChange={handleInputChange}
                  required
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Address Line 2</label>
                <input
                  name="address_line2"
                  type="text"
                  value={formData.address_line2}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">City *</label>
                  <input
                    name="city"
                    type="text"
                    value={formData.city}
                    onChange={handleInputChange}
                    required
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Postcode *</label>
                  <input
                    name="postcode"
                    type="text"
                    value={formData.postcode}
                    onChange={handleInputChange}
                    required
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Notes (optional)</label>
                <textarea
                  name="notes"
                  value={formData.notes}
                  onChange={handleInputChange}
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none resize-none"
                />
              </div>
              
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                  {error}
                </div>
              )}
              
              {/* Order Summary */}
              <div className="border-t pt-4 mt-6">
                <h3 className="font-medium text-slate-900 mb-3">Order Summary</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-500">{selectedSamples.length} Sample(s)</span>
                    <span className="text-green-600 font-medium">FREE</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Postage</span>
                    <span className="font-medium">{formatPrice(sampleInfo?.postage_fee || 4.99)}</span>
                  </div>
                  <hr />
                  <div className="flex justify-between font-bold">
                    <span>Total</span>
                    <span>{formatPrice(sampleInfo?.postage_fee || 4.99)}</span>
                  </div>
                </div>
              </div>
              
              <button
                type="submit"
                disabled={submitting}
                className="w-full flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-300 text-slate-900 font-semibold py-3 rounded-lg transition-colors"
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <Truck className="w-5 h-5" />
                    Pay {formatPrice(sampleInfo?.postage_fee || 4.99)} Postage
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
