import React, { useMemo, useState, useEffect } from 'react';
import { Elements, ExpressCheckoutElement, useElements, useStripe } from '@stripe/react-stripe-js';
import { loadStripe } from '@stripe/stripe-js';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const STRIPE_PK = process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY;

// Load Stripe.js once (module scope — required by Stripe)
const stripePromise = STRIPE_PK ? loadStripe(STRIPE_PK) : null;

/**
 * WalletExpressButton — mounts Stripe's ExpressCheckoutElement (Apple Pay +
 * Google Pay) inside an Elements provider. Hidden automatically when neither
 * wallet is available on the browser (the element reports via onReady).
 *
 * Props:
 *   cart: current basket items
 *   total: current basket total in £ (for the button's amount label)
 *   onSuccess: called with order_id after Stripe confirms payment
 */
const InnerButton = ({ cart, total, clientSecret, orderId, paymentIntentId, onSuccess }) => {
  const stripe = useStripe();
  const elements = useElements();
  const [ready, setReady] = useState(false);

  const handleConfirm = async (event) => {
    if (!stripe || !elements) return;

    // 1. Confirm the PaymentIntent with Stripe in-page (no redirect)
    const { error, paymentIntent } = await stripe.confirmPayment({
      elements,
      clientSecret,
      confirmParams: {
        return_url: `${window.location.origin}/shop/order-success?order_id=${orderId}`,
      },
      redirect: 'if_required',
    });

    if (error) {
      toast.error(error.message || 'Payment was not completed');
      return;
    }

    if (paymentIntent?.status === 'succeeded') {
      // 2. Tell the backend about the wallet's shipping / contact details
      //    so the order has useful data even before the webhook fires.
      const ship = event?.shippingAddress || {};
      const billing = event?.billingDetails || {};
      try {
        await fetch(`${API_URL}/api/shop/wallet-express/confirm`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            order_id: orderId,
            payment_intent_id: paymentIntentId,
            email: event?.email || billing.email || '',
            name: billing.name || ship.name || '',
            phone: event?.payerPhone || billing.phone || '',
            shipping_address: ship.address ? {
              line1: ship.address.line1 || '',
              line2: ship.address.line2 || '',
              city: ship.address.city || '',
              postcode: ship.address.postal_code || '',
              country: ship.address.country || 'GB',
            } : {},
          }),
        });
      } catch (e) {
        // Non-fatal — webhook will reconcile
        console.warn('[wallet-express] confirm call failed (non-fatal):', e);
      }
      onSuccess(orderId);
    }
  };

  return (
    <div className={ready ? 'block' : 'hidden'} data-testid="wallet-express-container">
      <ExpressCheckoutElement
        options={{
          paymentMethods: {
            applePay: 'always',
            googlePay: 'always',
            paypal: 'never', // we use our own PayPal Express
            link: 'never',
            amazonPay: 'never',
          },
          buttonType: { applePay: 'buy', googlePay: 'buy' },
          buttonHeight: 48,
          buttonTheme: { applePay: 'black', googlePay: 'black' },
        }}
        onReady={({ availablePaymentMethods }) => {
          // Auto-hide when the browser can't do Apple Pay or Google Pay
          const hasAny = availablePaymentMethods && (availablePaymentMethods.applePay || availablePaymentMethods.googlePay);
          setReady(!!hasAny);
        }}
        onConfirm={handleConfirm}
      />
    </div>
  );
};

const WalletExpressButton = ({ cart, total, enabled, onSuccess }) => {
  const [session, setSession] = useState(null);
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    if (!enabled || !STRIPE_PK || cart.length === 0 || total <= 0 || fetching || session) return;
    setFetching(true);
    (async () => {
      try {
        const items = cart.map(c => ({
          product_id: c.id || c.slug || '',
          quantity: Number(c.quantity) || 0,
          price: Number(c.price) || 0,
          name: c.name || c.display_name || c.title || 'Product',
          sku: c.sku || '',
          image: c.image || '',
        }));
        const res = await fetch(`${API_URL}/api/shop/wallet-express/create-intent`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items, origin_url: window.location.origin }),
        });
        if (!res.ok) {
          // Soft-fail: just don't render — the button will stay hidden.
          console.warn('[wallet-express] intent creation failed:', res.status);
          return;
        }
        const data = await res.json();
        setSession(data);
      } catch (e) {
        console.warn('[wallet-express] fetch failed:', e);
      } finally {
        setFetching(false);
      }
    })();
    // Re-create the intent whenever the basket total changes materially
  }, [enabled, cart.length, total]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!enabled || !STRIPE_PK || !session || !stripePromise) return null;

  const options = {
    clientSecret: session.client_secret,
    appearance: {
      theme: 'stripe',
      variables: { colorPrimary: '#1C1917' },
    },
  };

  return (
    <Elements stripe={stripePromise} options={options}>
      <InnerButton
        cart={cart}
        total={total}
        clientSecret={session.client_secret}
        orderId={session.order_id}
        paymentIntentId={session.payment_intent_id}
        onSuccess={onSuccess}
      />
    </Elements>
  );
};

export default WalletExpressButton;
