'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { ShoppingCart, User, Search, Menu, X, Heart, LogOut, Package, ChevronDown } from 'lucide-react';

interface ShopCustomer {
  id: string;
  email: string;
  name: string;
  phone?: string;
}

export function Header() {
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [customer, setCustomer] = useState<ShopCustomer | null>(null);
  const [showUserMenu, setShowUserMenu] = useState(false);

  // Check auth state on mount and listen for changes
  useEffect(() => {
    const checkAuth = () => {
      const customerData = localStorage.getItem('shop_customer');
      if (customerData) {
        try {
          setCustomer(JSON.parse(customerData));
        } catch {
          setCustomer(null);
        }
      } else {
        setCustomer(null);
      }
    };

    checkAuth();
    window.addEventListener('auth-changed', checkAuth);
    window.addEventListener('storage', checkAuth);

    return () => {
      window.removeEventListener('auth-changed', checkAuth);
      window.removeEventListener('storage', checkAuth);
    };
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('shop_token');
    localStorage.removeItem('shop_customer');
    setCustomer(null);
    setShowUserMenu(false);
    window.dispatchEvent(new Event('auth-changed'));
    router.push('/');
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      window.location.href = `/products?search=${encodeURIComponent(searchQuery)}`;
    }
  };

  const navLinks = [
    { href: '/', label: 'Home' },
    { href: '/products', label: 'All Tiles' },
    { href: '/products?clearance_only=true', label: 'Clearance', badge: 'Sale' },
    { href: '/samples', label: 'Free Samples' },
    { href: '/calculator', label: 'Tile Calculator' },
    { href: '/trade', label: 'Trade Account' },
    { href: '/stores', label: 'Our Stores' },
  ];

  return (
    <>
      {/* Top Banner */}
      <div className="bg-teal-700 text-white text-center py-2 text-sm">
        <span className="font-medium">Free UK Delivery on Orders Over £500</span>
        <span className="mx-4 hidden sm:inline">|</span>
        <span className="hidden sm:inline">Click & Collect Available</span>
      </div>

      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-50">
        <div className="container mx-auto px-4">
          {/* Main Header */}
          <div className="flex items-center justify-between h-16 lg:h-20">
            {/* Logo */}
            <Link href="/" className="flex items-center">
              <Image
                src="https://static.wixstatic.com/media/04cfc7_81b9b3537d334a94858ad1b1db83c7be~mv2.png/v1/fill/w_388,h_202,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/logo.png"
                alt="Tile Station"
                width={150}
                height={78}
                className="h-12 lg:h-14 w-auto"
                priority
              />
            </Link>

            {/* Search Bar - Desktop */}
            <form onSubmit={handleSearch} className="hidden lg:flex flex-1 max-w-xl mx-8">
              <div className="relative w-full">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="search"
                  placeholder="Search tiles, bathrooms, accessories..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 rounded-full border border-gray-200 focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 outline-none transition-colors"
                />
              </div>
            </form>

            {/* Actions */}
            <div className="flex items-center gap-2 lg:gap-4">
              {/* Search - Mobile */}
              <button className="lg:hidden p-2 hover:bg-gray-100 rounded-lg">
                <Search className="w-5 h-5" />
              </button>

              {/* Wishlist */}
              <Link href="/wishlist" className="relative p-2 hover:bg-gray-100 rounded-lg" title="Wishlist">
                <Heart className="w-5 h-5" />
              </Link>

              {/* Cart */}
              <Link href="/cart" className="relative p-2 hover:bg-gray-100 rounded-lg" title="Cart">
                <ShoppingCart className="w-5 h-5" />
              </Link>

              {/* Account - Authenticated */}
              {customer ? (
                <div className="relative hidden sm:block">
                  <button
                    onClick={() => setShowUserMenu(!showUserMenu)}
                    className="flex items-center gap-2 px-3 py-2 hover:bg-gray-100 rounded-lg text-sm font-medium transition-colors"
                    data-testid="user-menu-btn"
                  >
                    <div className="w-8 h-8 bg-teal-600 text-white rounded-full flex items-center justify-center text-sm font-bold">
                      {customer.name.charAt(0).toUpperCase()}
                    </div>
                    <span className="hidden lg:inline text-slate-700 max-w-[100px] truncate">{customer.name.split(' ')[0]}</span>
                    <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform ${showUserMenu ? 'rotate-180' : ''}`} />
                  </button>
                  
                  {/* User Dropdown */}
                  {showUserMenu && (
                    <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border border-gray-100 py-2 z-50">
                      <div className="px-4 py-2 border-b border-gray-100">
                        <p className="font-medium text-slate-900 truncate">{customer.name}</p>
                        <p className="text-sm text-slate-500 truncate">{customer.email}</p>
                      </div>
                      <Link
                        href="/account"
                        onClick={() => setShowUserMenu(false)}
                        className="flex items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-gray-50"
                      >
                        <User className="w-4 h-4" />
                        My Account
                      </Link>
                      <Link
                        href="/account/orders"
                        onClick={() => setShowUserMenu(false)}
                        className="flex items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-gray-50"
                      >
                        <Package className="w-4 h-4" />
                        My Orders
                      </Link>
                      <Link
                        href="/wishlist"
                        onClick={() => setShowUserMenu(false)}
                        className="flex items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-gray-50"
                      >
                        <Heart className="w-4 h-4" />
                        Wishlist
                      </Link>
                      <hr className="my-2" />
                      <button
                        onClick={handleLogout}
                        className="flex items-center gap-3 px-4 py-2 text-sm text-red-600 hover:bg-red-50 w-full"
                      >
                        <LogOut className="w-4 h-4" />
                        Sign Out
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <Link
                  href="/login"
                  className="hidden sm:flex items-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-sm font-medium transition-colors"
                  data-testid="sign-in-btn"
                >
                  <User className="w-4 h-4" />
                  Sign In
                </Link>
              )}

              {/* Mobile Menu Toggle */}
              <button
                className="lg:hidden p-2 hover:bg-gray-100 rounded-lg"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              >
                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>

          {/* Navigation - Desktop */}
          <nav className="hidden lg:flex items-center gap-6 py-3 border-t">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm font-medium text-slate-700 hover:text-teal-600 transition-colors flex items-center gap-1"
              >
                {link.label}
                {link.badge && (
                  <span className="bg-red-500 text-white text-xs px-1.5 py-0.5 rounded">
                    {link.badge}
                  </span>
                )}
              </Link>
            ))}
          </nav>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="lg:hidden border-t bg-white">
            <div className="container mx-auto px-4 py-4">
              {/* Mobile Search */}
              <form onSubmit={handleSearch} className="mb-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="search"
                    placeholder="Search..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 outline-none"
                  />
                </div>
              </form>

              {/* Mobile Nav Links */}
              <nav className="space-y-2">
                {navLinks.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className="block py-2 text-slate-700 hover:text-teal-600"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    {link.label}
                    {link.badge && (
                      <span className="ml-2 bg-red-500 text-white text-xs px-1.5 py-0.5 rounded">
                        {link.badge}
                      </span>
                    )}
                  </Link>
                ))}
                <hr className="my-2" />
                {customer ? (
                  <>
                    <div className="py-2">
                      <p className="font-medium text-slate-900">{customer.name}</p>
                      <p className="text-sm text-slate-500">{customer.email}</p>
                    </div>
                    <Link
                      href="/account"
                      className="block py-2 text-slate-700 hover:text-teal-600"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      My Account
                    </Link>
                    <Link
                      href="/account/orders"
                      className="block py-2 text-slate-700 hover:text-teal-600"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      My Orders
                    </Link>
                    <button
                      onClick={() => { handleLogout(); setMobileMenuOpen(false); }}
                      className="block py-2 text-red-600 hover:text-red-700 w-full text-left"
                    >
                      Sign Out
                    </button>
                  </>
                ) : (
                  <>
                    <Link
                      href="/login"
                      className="block py-2 text-slate-700 hover:text-teal-600"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      Sign In
                    </Link>
                    <Link
                      href="/register"
                      className="block py-2 text-slate-700 hover:text-teal-600"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      Create Account
                    </Link>
                  </>
                )}
              </nav>
            </div>
          </div>
        )}
      </header>
    </>
  );
}
