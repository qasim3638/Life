'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { 
  User, 
  Package, 
  Heart, 
  MapPin, 
  Settings, 
  LogOut,
  ChevronRight,
  ShoppingBag,
  Loader2
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
  created_at: string;
}

interface Order {
  id: string;
  order_number: string;
  status: string;
  total: number;
  created_at: string;
  items: Array<{ name: string; quantity: number }>;
}

export default function AccountPage() {
  const router = useRouter();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [recentOrders, setRecentOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('shop_token');
    if (!token) {
      router.push('/login?redirect=/account');
      return;
    }

    const fetchData = async () => {
      try {
        const [profileData, ordersData] = await Promise.all([
          api.getProfile(token),
          api.getOrders(token),
        ]);
        setCustomer(profileData);
        setRecentOrders(ordersData.slice(0, 3)); // Last 3 orders
      } catch (error) {
        console.error('Failed to fetch account data:', error);
        localStorage.removeItem('shop_token');
        localStorage.removeItem('shop_customer');
        router.push('/login?redirect=/account');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem('shop_token');
    localStorage.removeItem('shop_customer');
    window.dispatchEvent(new Event('auth-changed'));
    router.push('/');
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: 'GBP',
    }).format(price);
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      pending_payment: 'bg-yellow-100 text-yellow-800',
      confirmed: 'bg-green-100 text-green-800',
      processing: 'bg-blue-100 text-blue-800',
      shipped: 'bg-indigo-100 text-indigo-800',
      delivered: 'bg-green-100 text-green-800',
      cancelled: 'bg-red-100 text-red-800',
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      pending_payment: 'Awaiting Payment',
      confirmed: 'Confirmed',
      processing: 'Processing',
      shipped: 'Shipped',
      delivered: 'Delivered',
      cancelled: 'Cancelled',
    };
    return labels[status] || status;
  };

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-teal-600" />
      </div>
    );
  }

  if (!customer) {
    return null;
  }

  const menuItems = [
    { href: '/account/orders', icon: Package, label: 'My Orders', description: 'View and track your orders' },
    { href: '/wishlist', icon: Heart, label: 'Wishlist', description: 'Items you\'ve saved' },
    { href: '/account/addresses', icon: MapPin, label: 'Addresses', description: 'Manage delivery addresses' },
    { href: '/account/settings', icon: Settings, label: 'Account Settings', description: 'Update your details' },
  ];

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-slate-900">My Account</h1>
            <p className="text-slate-500">Welcome back, {customer.name.split(' ')[0]}!</p>
          </div>
          <button
            onClick={handleLogout}
            className="inline-flex items-center gap-2 text-red-600 hover:text-red-700 font-medium"
          >
            <LogOut className="w-4 h-4" />
            Sign Out
          </button>
        </div>

        <div className="grid lg:grid-cols-3 gap-8">
          {/* Left Column - Profile Summary */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl shadow-sm p-6">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-16 h-16 bg-teal-600 text-white rounded-full flex items-center justify-center text-2xl font-bold">
                  {customer.name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <h2 className="font-semibold text-slate-900">{customer.name}</h2>
                  <p className="text-sm text-slate-500">{customer.email}</p>
                </div>
              </div>

              {customer.phone && (
                <div className="text-sm text-slate-600 mb-2">
                  <span className="text-slate-500">Phone:</span> {customer.phone}
                </div>
              )}

              {customer.address?.line1 && (
                <div className="text-sm text-slate-600">
                  <span className="text-slate-500">Address:</span><br />
                  {customer.address.line1}<br />
                  {customer.address.line2 && <>{customer.address.line2}<br /></>}
                  {customer.address.city}, {customer.address.postcode}
                </div>
              )}

              <Link
                href="/account/settings"
                className="mt-4 inline-flex items-center gap-2 text-teal-600 hover:text-teal-700 text-sm font-medium"
              >
                Edit Profile
                <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
          </div>

          {/* Right Column - Menu & Recent Orders */}
          <div className="lg:col-span-2 space-y-6">
            {/* Quick Actions */}
            <div className="grid sm:grid-cols-2 gap-4">
              {menuItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="bg-white rounded-xl shadow-sm p-5 hover:shadow-md transition-shadow group"
                >
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 bg-teal-50 rounded-lg flex items-center justify-center text-teal-600 group-hover:bg-teal-100 transition-colors">
                      <item.icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold text-slate-900 group-hover:text-teal-600 transition-colors">
                        {item.label}
                      </h3>
                      <p className="text-sm text-slate-500">{item.description}</p>
                    </div>
                    <ChevronRight className="w-5 h-5 text-slate-400 group-hover:text-teal-600 transition-colors" />
                  </div>
                </Link>
              ))}
            </div>

            {/* Recent Orders */}
            <div className="bg-white rounded-xl shadow-sm overflow-hidden">
              <div className="p-5 border-b flex items-center justify-between">
                <h3 className="font-semibold text-slate-900 flex items-center gap-2">
                  <ShoppingBag className="w-5 h-5 text-teal-600" />
                  Recent Orders
                </h3>
                <Link
                  href="/account/orders"
                  className="text-sm text-teal-600 hover:text-teal-700 font-medium"
                >
                  View All
                </Link>
              </div>

              {recentOrders.length > 0 ? (
                <div className="divide-y">
                  {recentOrders.map((order) => (
                    <Link
                      key={order.id}
                      href={`/account/orders/${order.id}`}
                      className="block p-5 hover:bg-slate-50 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-slate-900">{order.order_number}</span>
                        <span className={`text-xs px-2 py-1 rounded-full ${getStatusColor(order.status)}`}>
                          {getStatusLabel(order.status)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-500">
                          {order.items.length} item{order.items.length !== 1 ? 's' : ''} • {formatDate(order.created_at)}
                        </span>
                        <span className="font-semibold text-slate-900">{formatPrice(order.total)}</span>
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="p-8 text-center">
                  <Package className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                  <p className="text-slate-500">No orders yet</p>
                  <Link
                    href="/products"
                    className="mt-3 inline-flex items-center gap-2 text-teal-600 hover:text-teal-700 font-medium text-sm"
                  >
                    Start Shopping
                    <ChevronRight className="w-4 h-4" />
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
