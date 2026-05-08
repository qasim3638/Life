/**
 * Tracks the storefront cart so we can send abandoned-basket reminders.
 *
 * Fires `POST /api/abandoned-carts/save` whenever:
 *   - the user has provided an email (logged-in customer or typed at checkout)
 *   - and the cart is non-empty
 *
 * Debounced (3s) so rapid +/- buttons don't spam the API.
 */
import { useEffect, useRef } from 'react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function useAbandonedCartTracker({ email, name, phone, items, total }) {
  const timeout = useRef(null);
  const lastPayload = useRef('');

  useEffect(() => {
    if (!email || !items || items.length === 0 || !(total > 0)) return;

    const payload = {
      customer_email: email.trim().toLowerCase(),
      customer_name: name || '',
      customer_phone: (phone || '').trim(),
      items: items.map(i => ({
        product_id: String(i.product_id || i.id || i.sku || ''),
        name: i.name || i.product_name || 'Product',
        price: Number(i.price || i.unit_price || 0),
        quantity: Number(i.quantity || i.qty || 1),
        image: i.image || i.image_url || '',
        sku: i.sku || '',
      })),
      cart_total: Number(total),
    };

    const sig = JSON.stringify(payload);
    if (sig === lastPayload.current) return;

    if (timeout.current) clearTimeout(timeout.current);
    timeout.current = setTimeout(() => {
      lastPayload.current = sig;
      axios.post(`${API}/abandoned-carts/save`, payload).catch(() => {
        /* fire-and-forget; never block the storefront */
      });
    }, 3000);

    return () => { if (timeout.current) clearTimeout(timeout.current); };
  }, [email, name, items, total]);
}
