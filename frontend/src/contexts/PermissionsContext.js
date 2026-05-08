import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from './AuthContext';

const PermissionsContext = createContext(null);
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const PermissionsProvider = ({ children }) => {
  const { user, token } = useAuth();
  const [pages, setPages] = useState([]);
  const [actions, setActions] = useState([]);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!token || !user) {
      setPages([]); setActions([]); setIsSuperAdmin(false);
      return;
    }
    try {
      setLoading(true);
      const res = await axios.get(`${API}/permissions/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPages(res.data.pages || []);
      setActions(res.data.actions || []);
      setIsSuperAdmin(!!res.data.is_super_admin);
    } catch (err) {
      console.error('Failed to load permissions', err);
      setPages([]); setActions([]); setIsSuperAdmin(false);
    } finally {
      setLoading(false);
    }
  }, [token, user]);

  useEffect(() => { refresh(); }, [refresh]);

  const hasPage = useCallback((key) => isSuperAdmin || pages.includes(key), [isSuperAdmin, pages]);
  const hasAction = useCallback((key) => isSuperAdmin || actions.includes(key), [isSuperAdmin, actions]);

  return (
    <PermissionsContext.Provider value={{ pages, actions, isSuperAdmin, loading, hasPage, hasAction, refresh }}>
      {children}
    </PermissionsContext.Provider>
  );
};

export const usePermissions = () => {
  const ctx = useContext(PermissionsContext);
  if (!ctx) {
    // Safe fallback so components don't crash if rendered outside provider
    return { pages: [], actions: [], isSuperAdmin: false, loading: false, hasPage: () => false, hasAction: () => false, refresh: () => {} };
  }
  return ctx;
};
