import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const TOKEN_KEY = "life_auth_token";

export const authStore = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  setToken: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export const api = axios.create({ baseURL: API });

// Attach Bearer token on every request
api.interceptors.request.use((config) => {
  const t = authStore.getToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

// Global 401 handler — invalid/expired token wipes state & reloads so the
// AuthGate lock screen shows.
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      authStore.clear();
      // Avoid loop on /auth/me probe: AuthGate itself drives UI
      if (!err.config?.url?.includes("/auth/")) {
        window.dispatchEvent(new Event("life:auth-expired"));
      }
    }
    return Promise.reject(err);
  },
);
