'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { 
  MapPin, 
  ChevronRight, 
  ChevronLeft,
  Loader2,
  Plus,
  Home,
  Check
} from 'lucide-react';
import api from '@/lib/api';

interface Customer {
  id: string;
  name: string;
  email: string;
  address?: {
    line1?: string;
    line2?: string;
    city?: string;
    postcode?: string;
  };
}

export default function AddressesPage() {
  const router = useRouter();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('shop_token');
    if (!token) {
      router.push('/login?redirect=/account/addresses');
      return;
    }

    const fetchProfile = async () => {
      try {
        const profileData = await api.getProfile(token);
        setCustomer(profileData);
      } catch (error) {
        console.error('Failed to fetch profile:', error);
        router.push('/login?redirect=/account/addresses');
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, [router]);

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-teal-600" />
      </div>
    );
  }

  const hasAddress = customer?.address?.line1;

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-2xl mx-auto">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-sm mb-6">
          <Link href="/account" className="text-slate-500 hover:text-teal-600">
            My Account
          </Link>
          <ChevronRight className="w-4 h-4 text-slate-400" />
          <span className="text-slate-900 font-medium">Addresses</span>
        </nav>

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-slate-900">My Addresses</h1>
            <p className="text-slate-500">Manage your delivery addresses</p>
          </div>
          <Link
            href="/account/settings"
            className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold px-4 py-2 rounded-lg transition-colors text-sm"
          >
            <Plus className="w-4 h-4" />
            {hasAddress ? 'Edit Address' : 'Add Address'}
          </Link>
        </div>

        {/* Address Card */}
        {hasAddress ? (
          <div className="bg-white rounded-xl shadow-sm overflow-hidden">
            <div className="p-5 border-b flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-teal-50 rounded-lg flex items-center justify-center">
                  <Home className="w-5 h-5 text-teal-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900">Default Address</h3>
                  <p className="text-sm text-slate-500">Used for deliveries</p>
                </div>
              </div>
              <span className="inline-flex items-center gap-1 text-sm text-green-600 bg-green-50 px-2 py-1 rounded-full">
                <Check className="w-4 h-4" />
                Default
              </span>
            </div>
            <div className="p-5">
              <p className="font-medium text-slate-900">{customer?.name}</p>
              <p className="text-slate-600 mt-1">{customer?.address?.line1}</p>
              {customer?.address?.line2 && (
                <p className="text-slate-600">{customer?.address?.line2}</p>
              )}
              <p className="text-slate-600">{customer?.address?.city}</p>
              <p className="text-slate-600">{customer?.address?.postcode}</p>
              <p className="text-slate-600">United Kingdom</p>

              <div className="mt-4 pt-4 border-t flex gap-4">
                <Link
                  href="/account/settings"
                  className="text-teal-600 hover:text-teal-700 font-medium text-sm"
                >
                  Edit
                </Link>
              </div>
            </div>
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm p-12 text-center">
            <MapPin className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-slate-900 mb-2">No Address Saved</h3>
            <p className="text-slate-500 mb-6">
              Add your delivery address for faster checkout
            </p>
            <Link
              href="/account/settings"
              className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
            >
              <Plus className="w-5 h-5" />
              Add Address
            </Link>
          </div>
        )}

        {/* Info */}
        <div className="mt-6 bg-slate-50 rounded-lg p-4 text-sm text-slate-600">
          <p>
            <strong>Note:</strong> You can add or change your delivery address during checkout. 
            The address saved here will be used as the default for faster checkout.
          </p>
        </div>

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
