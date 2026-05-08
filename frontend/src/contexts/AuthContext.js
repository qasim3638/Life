import React, { createContext, useState, useContext, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Generate a unique device ID based on browser fingerprint
const getDeviceId = () => {
  let deviceId = localStorage.getItem('device_id');
  if (!deviceId) {
    // Create a fingerprint from available browser info
    const fingerprint = [
      navigator.userAgent,
      navigator.language,
      screen.width,
      screen.height,
      screen.colorDepth,
      new Date().getTimezoneOffset(),
      navigator.hardwareConcurrency || 'unknown',
      navigator.platform
    ].join('|');
    
    // Simple hash function
    let hash = 0;
    for (let i = 0; i < fingerprint.length; i++) {
      const char = fingerprint.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    deviceId = 'device_' + Math.abs(hash).toString(36) + '_' + Date.now().toString(36);
    localStorage.setItem('device_id', deviceId);
  }
  return deviceId;
};

// Get device name from user agent
const getDeviceName = () => {
  const ua = navigator.userAgent;
  let browser = 'Unknown Browser';
  let os = 'Unknown OS';
  
  if (ua.includes('Chrome') && !ua.includes('Edg')) browser = 'Chrome';
  else if (ua.includes('Safari') && !ua.includes('Chrome')) browser = 'Safari';
  else if (ua.includes('Firefox')) browser = 'Firefox';
  else if (ua.includes('Edg')) browser = 'Edge';
  else if (ua.includes('Opera') || ua.includes('OPR')) browser = 'Opera';
  
  if (ua.includes('Windows')) os = 'Windows';
  else if (ua.includes('Mac')) os = 'macOS';
  else if (ua.includes('Linux')) os = 'Linux';
  else if (ua.includes('Android')) os = 'Android';
  else if (ua.includes('iPhone') || ua.includes('iPad')) os = 'iOS';
  
  return `${browser} on ${os}`;
};

// Get device type
const getDeviceType = () => {
  const ua = navigator.userAgent;
  if (/Mobi|Android/i.test(ua)) return 'mobile';
  if (/Tablet|iPad/i.test(ua)) return 'tablet';
  return 'desktop';
};

// Helper: check if a JWT token string is expired
const isTokenExpired = (tokenStr) => {
  if (!tokenStr) return true;
  try {
    const parts = tokenStr.split('.');
    if (parts.length !== 3) return true;
    const payload = JSON.parse(atob(parts[1]));
    return (payload.exp * 1000) < Date.now();
  } catch {
    return true;
  }
};

// Helper: get token expiry timestamp in ms
const getTokenExpiry = (tokenStr) => {
  try {
    const parts = tokenStr.split('.');
    if (parts.length !== 3) return 0;
    const payload = JSON.parse(atob(parts[1]));
    return payload.exp * 1000;
  } catch {
    return 0;
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('user');
    return savedUser ? JSON.parse(savedUser) : null;
  });
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);
  const [justLoggedIn, setJustLoggedIn] = useState(false);

  // Use refs for values accessed inside intervals/callbacks to avoid stale closures
  const tokenRef = useRef(token);
  const refreshInProgressRef = useRef(false);

  // Keep tokenRef in sync
  useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  // Verify interval: only re-verify every 30 minutes (reduced API calls)
  const VERIFY_INTERVAL = 30 * 60 * 1000;
  // Refresh interval: refresh token every 12 hours to keep session alive
  const REFRESH_INTERVAL = 12 * 60 * 60 * 1000;

  // Persist lastVerified to localStorage so page refreshes don't force re-verification
  const getLastVerified = () => {
    const v = localStorage.getItem('auth_last_verified');
    return v ? parseInt(v, 10) : 0;
  };
  const setLastVerified = (ts) => {
    localStorage.setItem('auth_last_verified', String(ts));
  };

  // On mount: decide whether to verify the token
  useEffect(() => {
    if (token) {
      // Quick client-side expiry check first
      if (isTokenExpired(token)) {
        logout();
        return;
      }

      if (justLoggedIn) {
        setLoading(false);
        setJustLoggedIn(false);
        setLastVerified(Date.now());
        return;
      }

      const savedUser = localStorage.getItem('user');
      const timeSinceLastVerify = Date.now() - getLastVerified();

      if (savedUser && timeSinceLastVerify < VERIFY_INTERVAL) {
        // Use cached data, skip network verification
        setUser(JSON.parse(savedUser));
        setLoading(false);
      } else {
        fetchCurrentUser();
      }
    } else {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Periodic token refresh to keep session alive
  useEffect(() => {
    if (!token) return;

    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        refreshToken();
      }
    }, REFRESH_INTERVAL);

    // Refresh when user returns to tab after long absence
    const handleVisibility = () => {
      if (document.visibilityState === 'visible' && tokenRef.current) {
        const timeSinceVerify = Date.now() - getLastVerified();
        if (timeSinceVerify > VERIFY_INTERVAL) {
          refreshToken();
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Setup global axios interceptor: auto-refresh on 401 and retry the failed request
  useEffect(() => {
    const interceptorId = axios.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        // Only handle 401s from our API, and only for requests that had an auth header
        if (
          error.response?.status === 401 &&
          originalRequest?.headers?.Authorization &&
          !originalRequest._retried &&
          originalRequest.url?.startsWith(API)
        ) {
          const currentToken = tokenRef.current;

          // If token is truly expired client-side, just logout
          if (isTokenExpired(currentToken)) {
            logout();
            return Promise.reject(error);
          }

          // Token looks valid client-side but backend rejected it — try refreshing
          originalRequest._retried = true;

          try {
            const newToken = await doRefreshToken(currentToken);
            if (newToken) {
              // Retry the original request with the new token
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
              return axios(originalRequest);
            }
          } catch {
            // Refresh failed — don't logout if token still has time
            const expiry = getTokenExpiry(currentToken);
            if (expiry > Date.now()) {
              // Token still valid, might be a backend hiccup
              return Promise.reject(error);
            }
          }
        }

        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.response.eject(interceptorId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Core refresh logic (returns new token or null)
  const doRefreshToken = async (currentToken) => {
    if (refreshInProgressRef.current) return null;
    refreshInProgressRef.current = true;

    try {
      const response = await axios.post(`${API}/auth/refresh-token`, {}, {
        headers: { Authorization: `Bearer ${currentToken}` },
        timeout: 15000,
      });

      if (response.data.token) {
        setToken(response.data.token);
        localStorage.setItem('token', response.data.token);
        setUser(response.data.user);
        localStorage.setItem('user', JSON.stringify(response.data.user));
        setLastVerified(Date.now());
        return response.data.token;
      }
      return null;
    } catch {
      return null;
    } finally {
      refreshInProgressRef.current = false;
    }
  };

  // Public refresh function
  const refreshToken = useCallback(async () => {
    const currentToken = tokenRef.current;
    if (!currentToken || isTokenExpired(currentToken)) return;
    await doRefreshToken(currentToken);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchCurrentUser = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 15000,
      });
      setUser(response.data);
      localStorage.setItem('user', JSON.stringify(response.data));
      setLastVerified(Date.now());
    } catch (error) {
      if (error.response?.status === 401) {
        // Only logout if token is actually expired
        if (isTokenExpired(token)) {
          logout();
          return;
        }
        // Token looks valid but backend rejected — use cached data
        const savedUser = localStorage.getItem('user');
        if (savedUser) {
          setUser(JSON.parse(savedUser));
        } else {
          logout();
          return;
        }
      } else if (error.response?.status === 403) {
        // Device approval / permission issue — keep cached data
        const savedUser = localStorage.getItem('user');
        if (savedUser) {
          setUser(JSON.parse(savedUser));
        } else {
          logout();
          return;
        }
      } else {
        // Network / server error — keep cached data, don't logout
        const savedUser = localStorage.getItem('user');
        if (savedUser) {
          setUser(JSON.parse(savedUser));
        }
      }
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const deviceInfo = {
      email,
      password,
      device_id: getDeviceId(),
      device_name: getDeviceName(),
      device_type: getDeviceType()
    };
    const response = await axios.post(`${API}/auth/login`, deviceInfo);
    setJustLoggedIn(true);
    setLoading(false);
    setToken(response.data.token);
    setUser(response.data.user);
    localStorage.setItem('token', response.data.token);
    localStorage.setItem('user', JSON.stringify(response.data.user));
    setLastVerified(Date.now());
    return response.data;
  };

  const register = async (email, password, name, role, inviteCode = null, additionalData = null) => {
    const data = { email, password, name, role };
    if (inviteCode) {
      data.invite_code = inviteCode;
    }
    if (additionalData) {
      data.company_name = additionalData.company_name;
      data.company_reg_number = additionalData.company_reg_number;
      data.vat_number = additionalData.vat_number;
      data.address = additionalData.address;
    }
    const response = await axios.post(`${API}/auth/register`, data);
    setJustLoggedIn(true);
    setLoading(false);
    setToken(response.data.token);
    setUser(response.data.user);
    localStorage.setItem('token', response.data.token);
    localStorage.setItem('user', JSON.stringify(response.data.user));
    setLastVerified(Date.now());
    return response.data;
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('auth_last_verified');
  };

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
