'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { 
  User, 
  Mail, 
  Phone, 
  MapPin, 
  ChevronRight, 
  ChevronLeft,
  Loader2,
  Save,
  CheckCircle
} from 'lucide-react';
import api from '@/lib/api';

interface Customer {
  id: string;
  name: string;
  email: string;
  phone?: string;
  address?: {
    line1?: string;
    line2?: string;
    city?: string;
    postcode?: string;
  };
}

export default function AccountSettingsPage() {
  const router = useRouter();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    address_line1: '',
    address_line2: '',
    city: '',
    postcode: '',
  });

  useEffect(() => {
    const token = localStorage.getItem('shop_token');
    if (!token) {
      router.push('/login?redirect=/account/settings');
      return;
    }

    const fetchProfile = async () => {
      try {
        const profileData = await api.getProfile(token);
        setCustomer(profileData);
        setFormData({
          name: profileData.name || '',
          phone: profileData.phone || '',
          address_line1: profileData.address?.line1 || '',
          address_line2: profileData.address?.line2 || '',
          city: profileData.address?.city || '',
          postcode: profileData.address?.postcode || '',
        });
      } catch (error) {
        console.error('Failed to fetch profile:', error);
        router.push('/login?redirect=/account/settings');
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, [router]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setSaved(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const token = localStorage.getItem('shop_token');
    if (!token) return;

    setSaving(true);
    setError('');
    setSaved(false);

    try {
      await api.updateProfile(token, {
        name: formData.name,
        phone: formData.phone,
        address_line1: formData.address_line1,
        address_line2: formData.address_line2,
        city: formData.city,
        postcode: formData.postcode.toUpperCase(),
      });

      // Update localStorage
      const updatedCustomer = {
        ...customer,
        name: formData.name,
        phone: formData.phone,
        address: {
          line1: formData.address_line1,
          line2: formData.address_line2,
          city: formData.city,
          postcode: formData.postcode.toUpperCase(),
        },
      };
      localStorage.setItem('shop_customer', JSON.stringify(updatedCustomer));
      window.dispatchEvent(new Event('auth-changed'));

      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: any) {
      console.error('Failed to update profile:', err);
      setError('Failed to update profile. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-teal-600" />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-2xl mx-auto">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-sm mb-6">
          <Link href="/account" className="text-slate-500 hover:text-teal-600">
            My Account
          </Link>
          <ChevronRight className="w-4 h-4 text-slate-400" />
          <span className="text-slate-900 font-medium">Settings</span>
        </nav>

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900">Account Settings</h1>
          <p className="text-slate-500">Update your personal information and address</p>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Personal Information */}
          <div className="bg-white rounded-xl shadow-sm overflow-hidden mb-6">
            <div className="p-5 border-b">
              <h3 className="font-semibold text-slate-900 flex items-center gap-2">
                <User className="w-5 h-5 text-teal-600" />
                Personal Information
              </h3>
            </div>
            <div className="p-5 space-y-5">
              {/* Name */}
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-slate-700 mb-1.5">
                  Full Name
                </label>
                <input
                  id="name"
                  name="name"
                  type="text"
                  value={formData.name}
                  onChange={handleChange}
                  className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none transition-colors"
                  data-testid="settings-name-input"
                />
              </div>

              {/* Email (read-only) */}
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-1.5">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                  <input
                    id="email"
                    type="email"
                    value={customer?.email || ''}
                    disabled
                    className="w-full pl-12 pr-4 py-3 border border-gray-200 rounded-lg bg-slate-50 text-slate-500 cursor-not-allowed"
                  />
                </div>
                <p className="text-xs text-slate-500 mt-1">Email cannot be changed</p>
              </div>

              {/* Phone */}
              <div>
                <label htmlFor="phone" className="block text-sm font-medium text-slate-700 mb-1.5">
                  Phone Number
                </label>
                <div className="relative">
                  <Phone className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                  <input
                    id="phone"
                    name="phone"
                    type="tel"
                    value={formData.phone}
                    onChange={handleChange}
                    placeholder="07123 456789"
                    className="w-full pl-12 pr-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none transition-colors"
                    data-testid="settings-phone-input"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Address */}
          <div className="bg-white rounded-xl shadow-sm overflow-hidden mb-6">
            <div className="p-5 border-b">
              <h3 className="font-semibold text-slate-900 flex items-center gap-2">
                <MapPin className="w-5 h-5 text-teal-600" />
                Default Address
              </h3>
            </div>
            <div className="p-5 space-y-5">
              {/* Address Line 1 */}
              <div>
                <label htmlFor="address_line1" className="block text-sm font-medium text-slate-700 mb-1.5">
                  Address Line 1
                </label>
                <input
                  id="address_line1"
                  name="address_line1"
                  type="text"
                  value={formData.address_line1}
                  onChange={handleChange}
                  placeholder="123 Main Street"
                  className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none transition-colors"
                  data-testid="settings-address1-input"
                />
              </div>

              {/* Address Line 2 */}
              <div>
                <label htmlFor="address_line2" className="block text-sm font-medium text-slate-700 mb-1.5">
                  Address Line 2 (Optional)
                </label>
                <input
                  id="address_line2"
                  name="address_line2"
                  type="text"
                  value={formData.address_line2}
                  onChange={handleChange}
                  placeholder="Apartment, suite, etc."
                  className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none transition-colors"
                  data-testid="settings-address2-input"
                />
              </div>

              {/* City & Postcode */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="city" className="block text-sm font-medium text-slate-700 mb-1.5">
                    City
                  </label>
                  <input
                    id="city"
                    name="city"
                    type="text"
                    value={formData.city}
                    onChange={handleChange}
                    placeholder="London"
                    className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none transition-colors"
                    data-testid="settings-city-input"
                  />
                </div>
                <div>
                  <label htmlFor="postcode" className="block text-sm font-medium text-slate-700 mb-1.5">
                    Postcode
                  </label>
                  <input
                    id="postcode"
                    name="postcode"
                    type="text"
                    value={formData.postcode}
                    onChange={handleChange}
                    placeholder="SW1A 1AA"
                    className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none transition-colors uppercase"
                    data-testid="settings-postcode-input"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm mb-6">
              {error}
            </div>
          )}

          {/* Success Message */}
          {saved && (
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm mb-6 flex items-center gap-2">
              <CheckCircle className="w-5 h-5" />
              Your changes have been saved successfully!
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-semibold py-3 rounded-lg transition-colors"
              data-testid="settings-save-btn"
            >
              {saving ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-5 h-5" />
                  Save Changes
                </>
              )}
            </button>
            <Link
              href="/account"
              className="flex-1 flex items-center justify-center gap-2 border border-slate-200 hover:bg-slate-50 text-slate-700 font-semibold py-3 rounded-lg transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
              Back to Account
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
