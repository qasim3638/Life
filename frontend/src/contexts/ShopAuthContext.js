import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../lib/api';
import { tagFromCustomerProfile } from '../lib/preciseLocation';

const ShopAuthContext = createContext(null);

export const useShopAuth = () => {
  const context = useContext(ShopAuthContext);
  if (!context) {
    throw new Error('useShopAuth must be used within ShopAuthProvider');
  }
  return context;
};

export const ShopAuthProvider = ({ children }) => {
  const [customer, setCustomer] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cart, setCart] = useState([]);

  useEffect(() => {
    const token = localStorage.getItem('shop_token');
    if (token) {
      fetchCustomer(token);
    } else {
      setLoading(false);
      // Load cart from localStorage for guest users
      const savedCart = localStorage.getItem('shop_cart');
      if (savedCart) {
        setCart(JSON.parse(savedCart));
      }
    }
  }, []);

  const fetchCustomer = async (token) => {
    try {
      const response = await api.shopGetProfile(token);
      setCustomer(response.data);
      // Tag the current visitor session with the customer's stored postcode
      // so admin Live Visitors shows a precise location for returning
      // logged-in customers without any GPS prompt or form interaction.
      tagFromCustomerProfile(response.data).catch(() => { /* non-fatal */ });
      // Fetch cart from server
      const cartResponse = await api.shopGetCart(token);
      setCart(cartResponse.data || []);
    } catch (error) {
      localStorage.removeItem('shop_token');
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const response = await api.shopLogin({ email, password });
    const { token, customer: customerData } = response.data;
    localStorage.setItem('shop_token', token);
    setCustomer(customerData);
    // Same auto-tag on fresh login
    tagFromCustomerProfile(customerData).catch(() => { /* non-fatal */ });
    // Fetch cart after login
    const cartResponse = await api.shopGetCart(token);
    setCart(cartResponse.data || []);
    return customerData;
  };

  const register = async (data) => {
    const response = await api.shopRegister(data);
    const { token, customer: customerData } = response.data;
    localStorage.setItem('shop_token', token);
    setCustomer(customerData);
    // Tag from the freshly-registered profile too
    tagFromCustomerProfile(customerData).catch(() => { /* non-fatal */ });
    return customerData;
  };

  const logout = () => {
    localStorage.removeItem('shop_token');
    setCustomer(null);
    setCart([]);
  };

  const addToCart = async (item) => {
    const token = localStorage.getItem('shop_token');
    if (token) {
      // Logged in - save to server
      try {
        const response = await api.shopAddToCart(token, item);
        setCart(response.data.cart);
      } catch (error) {
        throw error;
      }
    } else {
      // Guest - save to localStorage
      const newCart = [...cart];
      const existingIdx = newCart.findIndex(c => c.product_id === item.product_id);
      if (existingIdx >= 0) {
        newCart[existingIdx].quantity += item.quantity;
      } else {
        newCart.push(item);
      }
      setCart(newCart);
      localStorage.setItem('shop_cart', JSON.stringify(newCart));
    }
  };

  const updateCartItem = async (productId, quantity) => {
    const token = localStorage.getItem('shop_token');
    if (token) {
      try {
        const response = await api.shopUpdateCart(token, productId, quantity);
        setCart(response.data.cart);
      } catch (error) {
        throw error;
      }
    } else {
      const newCart = cart.filter(c => c.product_id !== productId);
      if (quantity > 0) {
        const item = cart.find(c => c.product_id === productId);
        if (item) {
          newCart.push({ ...item, quantity });
        }
      }
      setCart(newCart);
      localStorage.setItem('shop_cart', JSON.stringify(newCart));
    }
  };

  const removeFromCart = async (productId) => {
    const token = localStorage.getItem('shop_token');
    if (token) {
      try {
        const response = await api.shopRemoveFromCart(token, productId);
        setCart(response.data.cart);
      } catch (error) {
        throw error;
      }
    } else {
      const newCart = cart.filter(c => c.product_id !== productId);
      setCart(newCart);
      localStorage.setItem('shop_cart', JSON.stringify(newCart));
    }
  };

  const clearCart = async () => {
    const token = localStorage.getItem('shop_token');
    if (token) {
      try {
        await api.shopClearCart(token);
        setCart([]);
      } catch (error) {
        throw error;
      }
    } else {
      setCart([]);
      localStorage.removeItem('shop_cart');
    }
  };

  const cartTotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
  const cartCount = cart.reduce((sum, item) => sum + item.quantity, 0);

  return (
    <ShopAuthContext.Provider value={{
      customer,
      loading,
      cart,
      cartTotal,
      cartCount,
      login,
      register,
      logout,
      addToCart,
      updateCartItem,
      removeFromCart,
      clearCart,
      isAuthenticated: !!customer
    }}>
      {children}
    </ShopAuthContext.Provider>
  );
};
