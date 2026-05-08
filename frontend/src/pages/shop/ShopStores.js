import React, { useState, useEffect } from 'react';
import { api } from '../../lib/api';
import { MapPin, Phone, Mail, Clock } from 'lucide-react';
import { Card } from '../../components/ui/card';
import UseMyLocationButton from '../../components/shop/UseMyLocationButton';

export const ShopStores = () => {
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStores();
  }, []);

  const fetchStores = async () => {
    try {
      const response = await api.shopGetStores();
      setStores(response.data);
    } catch (error) {
      console.error('Failed to load stores:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-2xl md:text-3xl font-bold mb-8">Our Stores</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="p-6 animate-pulse">
              <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
              <div className="h-4 bg-gray-200 rounded w-2/3 mb-2"></div>
              <div className="h-4 bg-gray-200 rounded w-1/2"></div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8" data-testid="stores-page">
      <div className="max-w-3xl mx-auto text-center mb-12">
        <h1 className="text-2xl md:text-3xl font-bold text-slate-900 mb-4">Our Showrooms</h1>
        <p className="text-slate-500">
          Visit one of our showrooms to see our full range of tiles and bathroom products. 
          Our expert team is ready to help you find the perfect products for your project.
        </p>
        <UseMyLocationButton />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
        {stores.map((store) => (
          <Card key={store.id} className="p-6 hover:shadow-lg transition-shadow">
            <h2 className="text-xl font-bold text-slate-900 mb-4">{store.name}</h2>
            
            <div className="space-y-3 text-sm">
              {store.address && (
                <div className="flex items-start gap-3">
                  <MapPin className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                  <span className="text-slate-600">{store.address}</span>
                </div>
              )}
              
              {store.phone && (
                <div className="flex items-center gap-3">
                  <Phone className="w-5 h-5 text-amber-600 flex-shrink-0" />
                  <a href={`tel:${store.phone}`} className="text-slate-600 hover:text-amber-600">
                    {store.phone}
                  </a>
                </div>
              )}
              
              {store.email && (
                <div className="flex items-center gap-3">
                  <Mail className="w-5 h-5 text-amber-600 flex-shrink-0" />
                  <a href={`mailto:${store.email}`} className="text-slate-600 hover:text-amber-600">
                    {store.email}
                  </a>
                </div>
              )}
              
              {store.opening_hours && (
                <div className="flex items-start gap-3">
                  <Clock className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                  {typeof store.opening_hours === 'string' ? (
                    <span className="text-slate-600">{store.opening_hours}</span>
                  ) : (
                    <div className="text-slate-600 text-xs space-y-0.5">
                      {Object.entries(store.opening_hours).map(([day, hours]) => (
                        <div key={day} className="flex justify-between gap-4">
                          <span className="capitalize font-medium w-20">{day}</span>
                          <span>{hours}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>

      {/* CTA Section */}
      <div className="mt-12 text-center bg-slate-100 rounded-2xl p-8 max-w-3xl mx-auto">
        <h3 className="text-xl font-bold text-slate-900 mb-2">Can&apos;t visit in person?</h3>
        <p className="text-slate-500 mb-4">
          Browse our full collection online and get free delivery on orders over £499.
        </p>
        <a href="/shop/products" className="text-amber-600 hover:text-amber-700 font-medium">
          Shop Online →
        </a>
      </div>
    </div>
  );
};

export default ShopStores;
