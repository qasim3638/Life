import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  User, Mail, Phone, MapPin, LogOut, Package, 
  Heart, ChevronRight, Edit2, Clock, Wallet,
  ShoppingBag, Settings, CheckCircle2, Loader2, Building2, Gift,
  RotateCw, ShoppingCart
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { ShopHeader, ShopFooter } from './TileStationHome';
import { toast } from 'sonner';
import { useCart } from '../../contexts/TileCartContext';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ICON_MAP = { ShoppingBag, Heart, MapPin, Package, User, Gift, Wallet };
const getIcon = (name) => ICON_MAP[name] || ShoppingBag;

const COLOR_MAP = {
  blue: { bg: 'bg-blue-100', text: 'text-blue-600' },
  pink: { bg: 'bg-pink-100', text: 'text-pink-600' },
  green: { bg: 'bg-green-100', text: 'text-green-600' },
  purple: { bg: 'bg-purple-100', text: 'text-purple-600' },
};

const TAB_ICONS = { overview: User, orders: Package, wishlist: Heart, settings: Settings };

const CustomerAccountPage = () => {
  const navigate = useNavigate();
  const { addToCart } = useCart();
  const [customer, setCustomer] = useState(null);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [settings, setSettings] = useState(null);
  const [reorderingId, setReorderingId] = useState(null);
  // In-store re-engagement nudge — single fetch on mount surfaces a 5%-off
  // voucher when the customer has any IN-STORE invoice older than 30 days
  // AND no fresh online order in that window. Same code reused across rows.
  const [reengagement, setReengagement] = useState({
    eligible: false,
    voucher_code: null,
    percent_off: 5,
    qualifying_invoice_ids: [],
  });
  const [voucherCopied, setVoucherCopied] = useState(false);

  // One-click "Order again" — pulls fresh prices/stock for an existing order
  // (online OR in-store) and pushes the items into the cart. Free-typed EPOS
  // line items without a product_id come back as `available: false` so we
  // skip them gracefully.
  const handleReorder = async (orderId) => {
    const token = localStorage.getItem('tile_shop_token');
    if (!token || !orderId) return;
    setReorderingId(orderId);
    try {
      const res = await fetch(`${API_URL}/api/shop/orders/${orderId}/reorder-items`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || 'Could not load reorder items');
      }
      const data = await res.json();
      const items = data.items || [];
      let added = 0;
      let skipped = 0;
      for (const item of items) {
        if (!item.available) { skipped++; continue; }
        addToCart(item, item.quantity || 1);
        added++;
      }
      if (added > 0) {
        toast.success(
          skipped > 0
            ? `Added ${added} item${added > 1 ? 's' : ''} — ${skipped} unavailable, skipped`
            : `Added ${added} item${added > 1 ? 's' : ''} to cart`,
          { action: { label: 'View cart', onClick: () => navigate('/shop/tile-cart') } }
        );
      } else if (skipped > 0) {
        toast.error('None of those items are reorderable online right now');
      } else {
        toast.error('No items to reorder');
      }
    } catch (e) {
      toast.error(e.message || 'Could not reorder items');
    } finally {
      setReorderingId(null);
    }
  };

  useEffect(() => {
    fetchAccountData();
    fetch(`${API_URL}/api/website-admin/public/customer-account-settings`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.settings && Object.keys(d.settings).length) setSettings(d.settings); })
      .catch(() => {});
    // Fire-and-forget re-engagement check; non-fatal if it fails.
    const token = localStorage.getItem('tile_shop_token');
    if (token) {
      fetch(`${API_URL}/api/shop/account/instore-reengagement`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d) setReengagement(d); })
        .catch(() => {});
    }
  }, []);

  const handleCopyVoucher = async () => {
    if (!reengagement.voucher_code) return;
    try {
      await navigator.clipboard.writeText(reengagement.voucher_code);
      setVoucherCopied(true);
      toast.success(`Code ${reengagement.voucher_code} copied — paste at checkout`, { duration: 2400 });
      setTimeout(() => setVoucherCopied(false), 1800);
    } catch {
      toast.error('Could not copy — long-press the code to copy manually');
    }
  };

  const isQualifyingForNudge = (orderId) =>
    reengagement.eligible
    && !!reengagement.voucher_code
    && (reengagement.qualifying_invoice_ids || []).includes(orderId);

  // Dynamic content from admin settings
  const portal = settings?.portal || {};
  const welcomeMsg = portal.welcome_message || 'Welcome back, {name}!';
  const welcomeSub = portal.welcome_subtext || 'Manage your account, track orders, and save your favourites.';
  const showTradeUpgrade = portal.show_trade_upgrade !== false;
  const tradeUpgradeTitle = portal.trade_upgrade_title || 'Trade Professional?';
  const tradeUpgradeText = portal.trade_upgrade_text || 'Get exclusive discounts & credit back rewards';
  const tradeUpgradeBtn = portal.trade_upgrade_button || 'Open Trade Account';

  const dashboard = settings?.dashboard || {};
  const dbStats = (dashboard.stats || []).filter(s => s.enabled !== false);
  const dbActions = (dashboard.quick_actions || []).filter(a => a.enabled !== false);
  const dbTabs = (dashboard.sidebar_tabs || []).filter(t => t.enabled !== false);

  const defaultStats = [
    { id: 'orders', label: 'Total Orders', icon: 'ShoppingBag', color: 'blue' },
    { id: 'wishlist', label: 'Wishlist Items', icon: 'Heart', color: 'pink' },
    { id: 'addresses', label: 'Saved Addresses', icon: 'MapPin', color: 'green' },
  ];
  const displayStats = dbStats.length > 0 ? dbStats : defaultStats;

  const defaultActions = [
    { id: 'shop', title: 'Browse Tiles', description: 'Explore our collections', link: '/tiles' },
    { id: 'samples', title: 'Order Samples', description: 'Try before you buy', link: '/shop/sample-service' },
  ];
  const displayActions = dbActions.length > 0 ? dbActions : defaultActions;

  const defaultTabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'orders', label: 'Orders' },
    { id: 'wishlist', label: 'Wishlist' },
    { id: 'settings', label: 'Settings' },
  ];
  const displayTabs = dbTabs.length > 0 ? dbTabs : defaultTabs;

  // Stat values from customer data
  const statValues = {
    orders: orders.length.toString(),
    wishlist: '0',
    addresses: customer?.address ? '1' : '0',
  };

  const fetchAccountData = async () => {
    try {
      const token = localStorage.getItem('tile_shop_token');
      if (!token) { navigate('/shop/tile-login?redirect=/shop/account'); return; }
      const [customerRes, ordersRes] = await Promise.all([
        fetch(`${API_URL}/api/shop/auth/me`, { headers: { 'Authorization': `Bearer ${token}` } }),
        fetch(`${API_URL}/api/shop/orders`, { headers: { 'Authorization': `Bearer ${token}` } })
      ]);
      if (!customerRes.ok) {
        // Stale/invalid token — clear both token and cached customer to avoid
        // the "phantom logged-in" state where header shows account but API rejects.
        const status = customerRes.status;
        let detail = '';
        try { const body = await customerRes.json(); detail = body.detail || ''; } catch {}
        console.error(`[Account] /auth/me failed: ${status} ${detail}`);
        localStorage.removeItem('tile_shop_token');
        localStorage.removeItem('tile_shop_customer');
        window.dispatchEvent(new Event('trade-auth-change'));
        toast.error(status === 401 ? 'Session expired — please sign in again' : 'Could not load your account, please sign in');
        navigate('/shop/tile-login?redirect=/shop/account');
        return;
      }
      const customerData = await customerRes.json();
      if (customerData.is_trade) { navigate('/shop/trade/account'); return; }
      setCustomer(customerData);
      // Refresh cached customer so header stays accurate.
      try { localStorage.setItem('tile_shop_customer', JSON.stringify(customerData)); } catch {}
      window.dispatchEvent(new Event('trade-auth-change'));
      if (ordersRes.ok) {
        // Endpoint returns a plain array; tolerate the legacy `{orders}`
        // shape too in case a future refactor wraps it.
        const ordersData = await ordersRes.json();
        setOrders(Array.isArray(ordersData) ? ordersData : (ordersData.orders || []));
      }
    } catch (error) {
      console.error('[Account] Network error:', error);
      toast.error('Network error — please try again');
    } finally { setLoading(false); }
  };

  const handleLogout = () => {
    localStorage.removeItem('tile_shop_token');
    localStorage.removeItem('tile_shop_customer');
    toast.success('Logged out successfully');
    navigate('/');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <ShopHeader />
        <div className="container mx-auto px-4 py-16 flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
        </div>
        <ShopFooter />
      </div>
    );
  }

  if (!customer) return null;

  const resolvedWelcome = welcomeMsg.replace('{name}', customer.name?.split(' ')[0] || 'there');

  return (
    <div className="min-h-screen bg-gray-50">
      <ShopHeader />
      <div className="container mx-auto px-4 py-8">
        <nav className="text-sm text-gray-500 mb-6">
          <Link to="/" className="hover:text-[#F7EA1C]">Home</Link>
          <span className="mx-2">/</span>
          <span className="text-gray-900">My Account</span>
        </nav>

        <div className="grid lg:grid-cols-4 gap-6">
          {/* Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl shadow-sm p-6 sticky top-24">
              <div className="text-center mb-6 pb-6 border-b">
                <div className="w-16 h-16 bg-[#333333] rounded-full flex items-center justify-center mx-auto mb-3">
                  <User className="w-8 h-8 text-[#F7EA1C]" />
                </div>
                <h2 className="font-bold text-gray-900">{customer.name}</h2>
                <p className="text-sm text-gray-500">{customer.email}</p>
              </div>
              <nav className="space-y-1">
                {displayTabs.map(tab => {
                  const TabIcon = TAB_ICONS[tab.id] || User;
                  return (
                    <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                      className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors ${activeTab === tab.id ? 'bg-[#333333] text-[#F7EA1C]' : 'text-gray-600 hover:bg-gray-100'}`}>
                      <TabIcon className="w-5 h-5" />{tab.label}
                    </button>
                  );
                })}
              </nav>
              <button onClick={handleLogout} className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-red-600 hover:bg-red-50 mt-4">
                <LogOut className="w-5 h-5" />Sign Out
              </button>

              {showTradeUpgrade && (
                <div className="mt-6 pt-6 border-t">
                  <div className="bg-[#333333] rounded-xl p-4 text-white">
                    <div className="flex items-center gap-2 mb-2">
                      <Building2 className="w-5 h-5 text-[#F7EA1C]" />
                      <span className="font-semibold text-sm">{tradeUpgradeTitle}</span>
                    </div>
                    <p className="text-xs text-gray-400 mb-3">{tradeUpgradeText}</p>
                    <Link to="/shop/trade/register" className="block w-full text-center bg-[#F7EA1C] text-[#333333] text-sm font-semibold py-2 rounded-lg hover:bg-[#e5d91a]">
                      {tradeUpgradeBtn}
                    </Link>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Main Content */}
          <div className="lg:col-span-3">
            {activeTab === 'overview' && (
              <div className="space-y-6">
                <div className="bg-gradient-to-br from-[#333333] to-[#444444] rounded-2xl p-6 text-white">
                  <h2 className="text-2xl font-bold mb-2">{resolvedWelcome}</h2>
                  <p className="text-gray-300">{welcomeSub}</p>
                </div>

                <div className="grid md:grid-cols-3 gap-4">
                  {displayStats.map(stat => {
                    const StatIcon = getIcon(stat.icon);
                    const colors = COLOR_MAP[stat.color] || COLOR_MAP.blue;
                    return (
                      <div key={stat.id} className="bg-white rounded-xl p-5 shadow-sm">
                        <div className="flex items-center gap-3 mb-2">
                          <div className={`w-10 h-10 ${colors.bg} rounded-lg flex items-center justify-center`}>
                            <StatIcon className={`w-5 h-5 ${colors.text}`} />
                          </div>
                          <span className="text-gray-500 text-sm">{stat.label}</span>
                        </div>
                        <p className="text-2xl font-bold text-gray-900">{statValues[stat.id] || '0'}</p>
                      </div>
                    );
                  })}
                </div>

                <div className="bg-white rounded-xl shadow-sm p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-bold text-gray-900">Recent Orders</h3>
                    <button onClick={() => setActiveTab('orders')} className="text-sm text-[#333333] hover:text-[#F7EA1C] flex items-center gap-1">
                      View All <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                  {orders.length > 0 ? (
                    <div className="space-y-3">
                      {orders.slice(0, 3).map(order => {
                        const isInStore = order.source === 'in_store';
                        const isVoided = order.status === 'deleted' || order.status === 'cancelled';
                        return (
                        <React.Fragment key={order.id}>
                        <div
                          className={`flex items-center justify-between p-3 rounded-lg ${
                            isVoided ? 'bg-gray-100 border border-dashed border-gray-300 opacity-70' : 'bg-gray-50'
                          }`}
                          data-testid={`retail-recent-order-${order.id}`}
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="w-10 h-10 bg-gray-200 rounded-lg flex items-center justify-center"><Package className="w-5 h-5 text-gray-500" /></div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <p className={`font-medium text-gray-900 truncate ${isVoided ? 'line-through' : ''}`}>
                                  Order #{order.order_number || order.id?.slice(-8)}
                                </p>
                                {isInStore && (
                                  <span
                                    className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-sky-100 text-sky-700"
                                    data-testid={`order-instore-badge-${order.id}`}
                                  >
                                    In-store
                                  </span>
                                )}
                              </div>
                              <p className="text-sm text-gray-500">{new Date(order.created_at).toLocaleDateString()}</p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className={`font-semibold text-gray-900 ${isVoided ? 'line-through' : ''}`}>£{order.total?.toFixed(2)}</p>
                            <span className={`text-xs px-2 py-1 rounded ${isVoided ? 'bg-rose-100 text-rose-700' : order.status === 'completed' || order.status === 'delivered' ? 'bg-green-100 text-green-700' : order.status === 'processing' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'}`}>
                              {isVoided ? (order.status === 'deleted' ? 'Deleted' : 'Cancelled') : (order.status || 'Pending')}
                            </span>
                            {isInStore && !isVoided && (
                              <button
                                type="button"
                                onClick={() => handleReorder(order.id)}
                                disabled={reorderingId === order.id}
                                data-testid={`reorder-instore-btn-${order.id}`}
                                className="mt-2 inline-flex items-center justify-center gap-1.5 px-2.5 py-1 text-[11px] font-semibold rounded-md transition bg-[#1a1a1a] hover:bg-[#333] text-[#F7EA1C] disabled:opacity-60 disabled:cursor-wait"
                              >
                                {reorderingId === order.id ? (
                                  <><Loader2 className="w-3 h-3 animate-spin" />Adding…</>
                                ) : (
                                  <><RotateCw className="w-3 h-3" />Order again</>
                                )}
                              </button>
                            )}
                          </div>
                        </div>
                        {isInStore && !isVoided && isQualifyingForNudge(order.id) && (
                          <div
                            data-testid={`reengagement-nudge-${order.id}`}
                            className="mt-2 px-3 py-2 rounded-md bg-amber-50 border border-amber-200 flex items-center gap-2 flex-wrap"
                          >
                            <Gift className="w-3.5 h-3.5 text-amber-700 shrink-0" />
                            <span className="text-[11px] text-amber-900 leading-tight">
                              Running low? Use{' '}
                              <code className="font-mono font-bold bg-amber-200/70 px-1 rounded">{reengagement.voucher_code}</code>
                              {' '}for <strong>{reengagement.percent_off}% off</strong> your next online order.
                            </span>
                            <button
                              type="button"
                              onClick={handleCopyVoucher}
                              className="ml-auto text-[10px] font-semibold text-amber-800 hover:text-amber-900 underline shrink-0"
                              data-testid={`copy-voucher-btn-${order.id}`}
                            >
                              {voucherCopied ? 'Copied' : 'Copy code'}
                            </button>
                          </div>
                        )}
                        </React.Fragment>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-gray-500">
                      <Package className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No orders yet</p>
                      <Link to="/tiles" className="text-[#333333] hover:text-[#F7EA1C] mt-2 inline-block">Start Shopping</Link>
                    </div>
                  )}
                </div>

                <div className="grid md:grid-cols-2 gap-4">
                  {displayActions.map((action, idx) => (
                    <Link key={action.id || idx} to={action.link} className="bg-white rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow flex items-center gap-4">
                      <div className={`w-12 h-12 ${idx === 0 ? 'bg-[#F7EA1C]' : 'bg-[#333333]'} rounded-xl flex items-center justify-center`}>
                        {idx === 0 ? <ShoppingBag className="w-6 h-6 text-[#333333]" /> : <Package className="w-6 h-6 text-[#F7EA1C]" />}
                      </div>
                      <div>
                        <h3 className="font-bold text-gray-900">{action.title}</h3>
                        <p className="text-sm text-gray-500">{action.description}</p>
                      </div>
                      <ChevronRight className="w-5 h-5 text-gray-400 ml-auto" />
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'orders' && (
              <div className="bg-white rounded-2xl shadow-sm p-6">
                <h2 className="text-xl font-bold text-gray-900 mb-6">Order History</h2>
                {orders.length > 0 ? (
                  <div className="space-y-4">
                    {orders.map(order => {
                      const isInStore = order.source === 'in_store';
                      const isVoided = order.status === 'deleted' || order.status === 'cancelled';
                      return (
                      <div
                        key={order.id}
                        className={`border rounded-xl p-4 transition-colors ${
                          isVoided ? 'bg-gray-50 border-dashed border-gray-300 opacity-75' : 'hover:border-[#F7EA1C]'
                        }`}
                        data-testid={`retail-order-row-${order.id}`}
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <p className={`font-bold text-gray-900 ${isVoided ? 'line-through' : ''}`}>
                                Order #{order.order_number || order.id?.slice(-8)}
                              </p>
                              {isInStore && (
                                <span
                                  className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-sky-100 text-sky-700"
                                  data-testid={`order-history-instore-badge-${order.id}`}
                                >
                                  In-store
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-gray-500 mt-1"><Clock className="w-4 h-4 inline mr-1" />{new Date(order.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
                            {isVoided && order.void_reason && (
                              <p className="text-xs text-rose-700 mt-1 italic">{order.void_reason}</p>
                            )}
                          </div>
                          <div className="text-right">
                            <p className={`text-xl font-bold text-gray-900 ${isVoided ? 'line-through' : ''}`}>£{order.total?.toFixed(2)}</p>
                            <span className={`inline-flex items-center gap-1 text-sm px-3 py-1 rounded-full mt-1 ${isVoided ? 'bg-rose-100 text-rose-700' : order.status === 'completed' || order.status === 'delivered' ? 'bg-green-100 text-green-700' : order.status === 'processing' ? 'bg-blue-100 text-blue-700' : order.status === 'shipped' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'}`}>
                              {!isVoided && order.status === 'completed' && <CheckCircle2 className="w-4 h-4" />}
                              {isVoided ? (order.status === 'deleted' ? 'Deleted' : 'Cancelled') : (order.status?.charAt(0).toUpperCase() + order.status?.slice(1) || 'Pending')}
                            </span>
                            {isInStore && !isVoided && (
                              <button
                                type="button"
                                onClick={() => handleReorder(order.id)}
                                disabled={reorderingId === order.id}
                                data-testid={`reorder-history-btn-${order.id}`}
                                className="mt-2 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition bg-[#1a1a1a] hover:bg-[#333] text-[#F7EA1C] disabled:opacity-60 disabled:cursor-wait"
                                title="Pre-fill cart with the same SKUs at today's prices"
                              >
                                {reorderingId === order.id ? (
                                  <><Loader2 className="w-3.5 h-3.5 animate-spin" />Adding…</>
                                ) : (
                                  <><ShoppingCart className="w-3.5 h-3.5" />Order again</>
                                )}
                              </button>
                            )}
                          </div>
                        </div>
                        {/* Savings pill — surfaces volume-tier savings to retail
                            customers (trade discount won't apply for them, but
                            the volume-tier discount will). Persisted on the
                            order via savings_meta. */}
                        {order.savings_meta && (order.savings_meta.total_saved || 0) >= 0.01 && (
                          <div
                            data-testid={`order-savings-pill-${order.id}`}
                            className="mt-3 px-4 py-3 bg-gradient-to-r from-emerald-500 to-emerald-600 text-white rounded-xl shadow-md flex items-center gap-3"
                          >
                            <Gift className="w-5 h-5 text-emerald-100 flex-shrink-0" />
                            <div className="min-w-0 flex-1">
                              <div className="text-[10px] font-semibold uppercase tracking-wider text-emerald-100">Savings on this order</div>
                              <div className="text-[13px] font-bold leading-tight">
                                Volume discount saved you{' '}
                                <span className="tabular-nums">£{Number(order.savings_meta.total_saved).toFixed(2)}</span>
                              </div>
                              <div className="text-[11px] text-emerald-100 mt-0.5">
                                across {order.savings_meta.lines_with_savings || 0} line{(order.savings_meta.lines_with_savings || 0) === 1 ? '' : 's'} · {order.savings_meta.percent_off_retail || 0}% off retail
                              </div>
                            </div>
                          </div>
                        )}
                        {isInStore && !isVoided && isQualifyingForNudge(order.id) && (
                          <div
                            data-testid={`reengagement-nudge-history-${order.id}`}
                            className="mt-3 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 flex items-center gap-2 flex-wrap"
                          >
                            <Gift className="w-4 h-4 text-amber-700 shrink-0" />
                            <span className="text-xs text-amber-900 leading-tight">
                              Running low? Use{' '}
                              <code className="font-mono font-bold bg-amber-200/70 px-1.5 py-0.5 rounded">{reengagement.voucher_code}</code>
                              {' '}for <strong>{reengagement.percent_off}% off</strong> your next online order.
                            </span>
                            <button
                              type="button"
                              onClick={handleCopyVoucher}
                              className="ml-auto text-[11px] font-semibold text-amber-800 hover:text-amber-900 underline shrink-0"
                              data-testid={`copy-voucher-history-btn-${order.id}`}
                            >
                              {voucherCopied ? 'Copied' : 'Copy code'}
                            </button>
                          </div>
                        )}
                      </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    <Package className="w-16 h-16 mx-auto mb-4 opacity-30" />
                    <p className="text-lg">No orders yet</p>
                    <p className="text-sm mt-1">Start shopping to see your orders here</p>
                    <Link to="/tiles" className="inline-flex items-center gap-2 bg-[#333333] text-[#F7EA1C] px-6 py-3 rounded-lg mt-4 hover:bg-[#444444]">Browse Products <ChevronRight className="w-4 h-4" /></Link>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'wishlist' && (
              <div className="bg-white rounded-2xl shadow-sm p-6">
                <h2 className="text-xl font-bold text-gray-900 mb-6">My Wishlist</h2>
                <div className="text-center py-12 text-gray-500">
                  <Heart className="w-16 h-16 mx-auto mb-4 opacity-30" />
                  <p className="text-lg">Your wishlist is empty</p>
                  <p className="text-sm mt-1">Save items you love by clicking the heart icon</p>
                  <Link to="/tiles" className="inline-flex items-center gap-2 bg-[#333333] text-[#F7EA1C] px-6 py-3 rounded-lg mt-4 hover:bg-[#444444]">Discover Products <ChevronRight className="w-4 h-4" /></Link>
                </div>
              </div>
            )}

            {activeTab === 'settings' && (
              <div className="space-y-6">
                <div className="bg-white rounded-2xl shadow-sm p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-bold text-gray-900">Personal Information</h3>
                    <Button variant="outline" size="sm"><Edit2 className="w-4 h-4 mr-1" /> Edit</Button>
                  </div>
                  <div className="grid md:grid-cols-2 gap-4">
                    <div className="flex items-center gap-3"><User className="w-5 h-5 text-gray-400" /><div><p className="text-sm text-gray-500">Full Name</p><p className="font-medium">{customer.name}</p></div></div>
                    <div className="flex items-center gap-3"><Mail className="w-5 h-5 text-gray-400" /><div><p className="text-sm text-gray-500">Email</p><p className="font-medium">{customer.email}</p></div></div>
                    <div className="flex items-center gap-3"><Phone className="w-5 h-5 text-gray-400" /><div><p className="text-sm text-gray-500">Phone</p><p className="font-medium">{customer.phone || 'Not provided'}</p></div></div>
                  </div>
                </div>
                <div className="bg-white rounded-2xl shadow-sm p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-bold text-gray-900">Delivery Address</h3>
                    <Button variant="outline" size="sm"><Edit2 className="w-4 h-4 mr-1" /> Edit</Button>
                  </div>
                  <div className="flex items-start gap-3">
                    <MapPin className="w-5 h-5 text-gray-400 mt-0.5" />
                    <div>
                      {customer.address ? (
                        <>{customer.address.line1 && <p>{customer.address.line1}</p>}{customer.address.line2 && <p>{customer.address.line2}</p>}<p>{customer.address.city}, {customer.address.postcode}</p></>
                      ) : <p className="text-gray-500">No address saved</p>}
                    </div>
                  </div>
                </div>
                <div className="bg-white rounded-2xl shadow-sm p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-bold text-gray-900">Password</h3>
                      <p className="text-sm text-gray-500 mt-1">Update your password to keep your account secure</p>
                    </div>
                    <Button variant="outline" size="sm">Change Password</Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      <ShopFooter />
    </div>
  );
};

export default CustomerAccountPage;
