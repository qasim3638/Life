import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

const apiClient = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Types
export interface Product {
  id: string;
  name: string;
  description: string;
  sku: string;
  price: number;
  stock: number;
  category_id: string;
  category_name: string;
  unit: string;
  m2_quantity?: number;
  tile_width?: number;
  tile_height?: number;
  tile_m2_per_piece?: number;
  tiles_per_box?: number;
  box_m2_coverage?: number;
  clearance: boolean;
  clearance_price?: number;
  images: string[];
  in_stock: boolean;
  avg_rating?: number;
  review_count?: number;
}

export interface Category {
  id: string;
  name: string;
  description?: string;
  product_count: number;
}

export interface Store {
  id: string;
  name: string;
  address: string;
  phone: string;
  email: string;
  opening_hours: string;
}

export interface CartItem {
  product_id: string;
  name: string;
  sku: string;
  price: number;
  quantity: number;
  image: string;
}

export interface ProductsResponse {
  products: Product[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

// API Functions
export const api = {
  // Products (Public)
  getProducts: async (params?: {
    category_id?: string;
    search?: string;
    min_price?: number;
    max_price?: number;
    in_stock_only?: boolean;
    clearance_only?: boolean;
    sort_by?: string;
    page?: number;
    limit?: number;
  }): Promise<ProductsResponse> => {
    const response = await apiClient.get('/shop/products', { params });
    return response.data;
  },

  getProduct: async (id: string): Promise<Product> => {
    const response = await apiClient.get(`/shop/products/${id}`);
    return response.data;
  },

  getCategories: async (): Promise<Category[]> => {
    const response = await apiClient.get('/shop/categories');
    return response.data;
  },

  getFeatured: async (limit = 8): Promise<Product[]> => {
    const response = await apiClient.get('/shop/featured', { params: { limit } });
    return response.data;
  },

  getStores: async (): Promise<Store[]> => {
    const response = await apiClient.get('/shop/stores');
    return response.data;
  },

  // Auth
  login: async (email: string, password: string) => {
    const response = await apiClient.post('/shop/auth/login', { email, password });
    return response.data;
  },

  register: async (data: {
    email: string;
    password: string;
    name: string;
    phone?: string;
    address_line1?: string;
    address_line2?: string;
    city?: string;
    postcode?: string;
  }) => {
    const response = await apiClient.post('/shop/auth/register', data);
    return response.data;
  },

  getProfile: async (token: string) => {
    const response = await apiClient.get('/shop/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  updateProfile: async (token: string, data: {
    name?: string;
    phone?: string;
    address_line1?: string;
    address_line2?: string;
    city?: string;
    postcode?: string;
  }) => {
    const response = await apiClient.put('/shop/auth/profile', null, {
      headers: { Authorization: `Bearer ${token}` },
      params: data,
    });
    return response.data;
  },

  getOrder: async (token: string, orderId: string) => {
    const response = await apiClient.get(`/shop/orders/${orderId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  // Cart
  getCart: async (token: string): Promise<CartItem[]> => {
    const response = await apiClient.get('/shop/cart', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  addToCart: async (token: string, item: CartItem) => {
    const response = await apiClient.post('/shop/cart/add', item, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  updateCart: async (token: string, productId: string, quantity: number) => {
    const response = await apiClient.put('/shop/cart/update', null, {
      headers: { Authorization: `Bearer ${token}` },
      params: { product_id: productId, quantity },
    });
    return response.data;
  },

  removeFromCart: async (token: string, productId: string) => {
    const response = await apiClient.delete(`/shop/cart/remove/${productId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  clearCart: async (token: string) => {
    const response = await apiClient.delete('/shop/cart/clear', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  // Orders
  createOrder: async (token: string, data: any) => {
    const response = await apiClient.post('/shop/orders', data, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  getOrders: async (token: string) => {
    const response = await apiClient.get('/shop/orders', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  // Checkout
  createCheckoutSession: async (token: string, orderId: string, originUrl: string) => {
    const response = await apiClient.post(
      '/shop/checkout/create-session',
      { order_id: orderId, origin_url: originUrl },
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  getCheckoutStatus: async (sessionId: string) => {
    const response = await apiClient.get(`/shop/checkout/status/${sessionId}`);
    return response.data;
  },

  // Guest Checkout
  createGuestOrder: async (data: {
    customer_name: string;
    customer_email: string;
    customer_phone?: string;
    delivery_address?: {
      line1?: string;
      line2?: string;
      city?: string;
      postcode?: string;
      country?: string;
    };
    delivery_method: 'delivery' | 'collect';
    collect_store_id?: string;
    notes?: string;
    items: CartItem[];
    create_account?: boolean;
    password?: string;
  }) => {
    const response = await apiClient.post('/shop/guest/orders', data);
    return response.data;
  },

  createGuestCheckoutSession: async (orderId: string, originUrl: string) => {
    const response = await apiClient.post('/shop/guest/checkout/create-session', {
      order_id: orderId,
      origin_url: originUrl,
    });
    return response.data;
  },

  // Order Tracking
  trackOrder: async (orderNumber: string, email: string) => {
    const response = await apiClient.get(`/shop/track/${orderNumber}`, {
      params: { email },
    });
    return response.data;
  },

  // Tile Calculator
  calculateTiles: async (data: {
    room_length: number;
    room_width: number;
    product_id: string;
    wastage_percent?: number;
  }) => {
    const response = await apiClient.post('/shop/calculator/tiles', data);
    return response.data;
  },

  quickEstimate: async (length: number, width: number, wastage: number = 10) => {
    const response = await apiClient.get('/shop/calculator/estimate', {
      params: { length, width, wastage },
    });
    return response.data;
  },

  // Wishlist (requires auth)
  getWishlist: async (token: string): Promise<Product[]> => {
    const response = await apiClient.get('/shop/wishlist', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  addToWishlist: async (token: string, productId: string) => {
    const response = await apiClient.post(`/shop/wishlist/add/${productId}`, {}, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  removeFromWishlist: async (token: string, productId: string) => {
    const response = await apiClient.delete(`/shop/wishlist/remove/${productId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  // Product Reviews
  getProductReviews: async (productId: string, page: number = 1, limit: number = 10) => {
    const response = await apiClient.get(`/shop/products/${productId}/reviews`, {
      params: { page, limit },
    });
    return response.data;
  },

  createProductReview: async (token: string, productId: string, data: {
    rating: number;
    title?: string;
    comment?: string;
  }) => {
    const response = await apiClient.post(`/shop/products/${productId}/reviews`, data, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  markReviewHelpful: async (reviewId: string) => {
    const response = await apiClient.post(`/shop/reviews/${reviewId}/helpful`);
    return response.data;
  },

  // PayPal
  createPayPalOrder: async (orderId: string, returnUrl: string, cancelUrl: string) => {
    const response = await apiClient.post('/shop/paypal/create-order', {
      order_id: orderId,
      return_url: returnUrl,
      cancel_url: cancelUrl,
    });
    return response.data;
  },

  capturePayPalPayment: async (paymentId: string, payerId: string) => {
    const response = await apiClient.post(`/shop/paypal/capture/${paymentId}?payer_id=${payerId}`);
    return response.data;
  },

  // Trade Account
  applyForTradeAccount: async (data: {
    business_name: string;
    business_type: string;
    vat_number?: string;
    contact_name: string;
    email: string;
    phone: string;
    estimated_monthly_spend?: string;
    notes?: string;
  }) => {
    const response = await apiClient.post('/shop/trade/apply', data);
    return response.data;
  },

  getTradeStatus: async (token: string) => {
    const response = await apiClient.get('/shop/trade/status', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  calculatePricing: async (productId: string, quantity: number, token?: string) => {
    const headers: any = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await apiClient.get('/shop/pricing/calculate', {
      params: { product_id: productId, quantity },
      headers,
    });
    return response.data;
  },

  // Similar Products
  getSimilarProducts: async (productId: string, limit: number = 4) => {
    const response = await apiClient.get(`/shop/products/${productId}/similar`, {
      params: { limit },
    });
    return response.data;
  },

  // Series Products - Get products from same series
  getSeriesProducts: async (productId: string, limit: number = 8) => {
    const response = await apiClient.get(`/shop/products/${productId}/series`, {
      params: { limit },
    });
    return response.data;
  },

  // Sample Ordering
  getSampleInfo: async () => {
    const response = await apiClient.get('/shop/samples/info');
    return response.data;
  },

  createSampleOrder: async (data: {
    customer_name: string;
    customer_email: string;
    customer_phone?: string;
    delivery_address: {
      line1: string;
      line2?: string;
      city: string;
      postcode: string;
      country?: string;
    };
    product_ids: string[];
    notes?: string;
  }) => {
    const response = await apiClient.post('/shop/samples/order', data);
    return response.data;
  },

  createSampleCheckout: async (orderId: string, originUrl: string) => {
    const response = await apiClient.post(`/shop/samples/checkout/${orderId}?origin_url=${encodeURIComponent(originUrl)}`);
    return response.data;
  },

  getSampleOrderStatus: async (orderId: string) => {
    const response = await apiClient.get(`/shop/samples/status/${orderId}`);
    return response.data;
  },
};

export default api;
