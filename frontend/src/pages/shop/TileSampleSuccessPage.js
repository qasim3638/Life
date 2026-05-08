import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle, Package, Mail, ArrowRight, Loader2, AlertTriangle } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { ShopHeader, ShopFooter } from './TileStationHome';
import { useSampleCart } from '../../contexts/SampleCartContext';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const TileSampleSuccessPage = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { clearSamples } = useSampleCart();

  // Two entry points:
  //  1. Stripe redirect → ?session_id=...&order_id=...  (the new, real flow)
  //  2. Legacy nav-state → location.state.{orderNumber,...}  (fallback for
  //     anyone landing here without going through Stripe — shouldn't happen
  //     after the Apr 30 fix but we keep the path defensive).
  const sessionId = params.get('session_id');
  const orderId = params.get('order_id');

  const [verifying, setVerifying] = useState(!!sessionId);
  const [verifyError, setVerifyError] = useState('');
  const [info, setInfo] = useState(() => {
    if (location.state?.orderNumber) {
      return location.state;
    }
    try {
      const cached = sessionStorage.getItem('tile_sample_pending');
      const parsed = cached ? JSON.parse(cached) : null;
      // Breadcrumb is written by the cart page in snake_case (matches the
      // backend response). Normalise to camelCase here so the destructure
      // in the JSX below works. This was the bug that silently redirected
      // every paid customer to /tiles for ~28 hours on May 1-2 2026 —
      // info.orderNumber was undefined because the stored field was
      // `order_number`, so `!info?.orderNumber` evaluated truthy and we
      // bounced to /tiles instead of showing the success summary.
      if (parsed) {
        return {
          orderNumber: parsed.orderNumber || parsed.order_number,
          sampleCount: parsed.sampleCount ?? parsed.sample_count,
          postage: parsed.postage,
          email: parsed.email || '',
        };
      }
      return null;
    } catch { return null; }
  });

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API_URL}/api/shop/samples/checkout/status/${sessionId}`);
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          throw new Error(body.detail || 'Could not verify your payment');
        }
        const data = await r.json();
        if (cancelled) return;
        if (data.payment_status === 'paid') {
          // Confirmed paid — clear the cart & cached breadcrumb, then show the
          // friendly summary using whatever metadata we have on hand.
          clearSamples();
          try { sessionStorage.removeItem('tile_sample_pending'); } catch (_) {}
          // ALWAYS overwrite info with the verified server response so we
          // don't render a half-stale breadcrumb. Order number from the
          // server is authoritative.
          setInfo((prev) => ({
            orderNumber: data.order_number || prev?.orderNumber || orderId || 'PAID',
            sampleCount: prev?.sampleCount,
            postage: prev?.postage,
            email: prev?.email || '',
          }));
          setVerifying(false);
        } else {
          setVerifyError(
            "We didn't receive confirmation of your payment. If you completed checkout, refresh this page in a moment — Stripe sometimes takes a few seconds. Otherwise please try again."
          );
          setVerifying(false);
        }
      } catch (e) {
        if (!cancelled) {
          setVerifyError(e.message || 'Could not verify your payment');
          setVerifying(false);
        }
      }
    })();
    return () => { cancelled = true; };
  }, [sessionId, clearSamples]);

  // Verifying state — never claim "paid!" until Stripe confirms.
  if (verifying) {
    return (
      <div className="min-h-screen bg-gray-50">
        <ShopHeader />
        <div className="container mx-auto px-4 py-24 text-center" data-testid="sample-success-verifying">
          <Loader2 className="h-12 w-12 mx-auto text-[#333] animate-spin mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Confirming your sample order…</h1>
          <p className="text-gray-500">Just a moment while we verify your payment with Stripe.</p>
        </div>
        <ShopFooter />
      </div>
    );
  }

  // Verification failed — be honest, don't pretend it succeeded
  if (verifyError) {
    return (
      <div className="min-h-screen bg-gray-50">
        <ShopHeader />
        <div className="container mx-auto px-4 py-16 max-w-lg mx-auto text-center" data-testid="sample-success-error">
          <AlertTriangle className="h-12 w-12 mx-auto text-amber-500 mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Payment not confirmed</h1>
          <p className="text-gray-600 mb-6">{verifyError}</p>
          <div className="flex gap-3 justify-center">
            <Button variant="outline" onClick={() => navigate('/shop/tile-samples')}>
              Back to samples
            </Button>
            <Button onClick={() => window.location.reload()} className="bg-[#333] hover:bg-[#444] text-[#F7EA1C]">
              Refresh
            </Button>
          </div>
        </div>
        <ShopFooter />
      </div>
    );
  }

  // No info at all → render a friendly fallback success page using the
  // raw order_id from the URL. NEVER redirect silently to /tiles — that
  // was the bug that made paying customers think their order vanished.
  if (!info?.orderNumber) {
    const fallbackNumber = orderId || 'CONFIRMED';
    return (
      <div className="min-h-screen bg-gray-50">
        <ShopHeader />
        <div className="container mx-auto px-4 py-16 max-w-lg mx-auto text-center" data-testid="sample-success-fallback">
          <CheckCircle className="h-12 w-12 mx-auto text-green-600 mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Payment Received</h1>
          <p className="text-gray-600 mb-2">Reference: <span className="font-mono">{fallbackNumber}</span></p>
          <p className="text-gray-600 mb-6">Your samples are on their way — you'll receive a confirmation email shortly.</p>
          <Button onClick={() => navigate('/tiles')} className="bg-[#333] hover:bg-[#444] text-[#F7EA1C]">
            Continue browsing
          </Button>
        </div>
        <ShopFooter />
      </div>
    );
  }
  const { orderNumber, sampleCount, postage, email } = info;

  return (
    <div className="min-h-screen bg-gray-50">
      <ShopHeader />

      <div className="container mx-auto px-4 py-16">
        <div className="max-w-lg mx-auto text-center">
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="h-10 w-10 text-green-600" />
          </div>

          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Sample Order Placed!
          </h1>
          
          <p className="text-gray-600 mb-8">
            Your free tile samples are on their way.
          </p>

          <div className="bg-white rounded-lg shadow-sm p-6 mb-8 text-left">
            <div className="flex justify-between items-center border-b pb-4 mb-4">
              <span className="text-gray-600">Order Number</span>
              <span className="font-bold text-lg">{orderNumber}</span>
            </div>
            {sampleCount != null && (
              <div className="flex justify-between items-center border-b pb-4 mb-4">
                <span className="text-gray-600">Samples</span>
                <span className="font-medium">{sampleCount} × FREE</span>
              </div>
            )}
            {postage != null && (
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Delivery Paid</span>
                <span className="font-bold text-lg text-[#333333]">£{Number(postage).toFixed(2)}</span>
              </div>
            )}
          </div>

          {email && (
            <div className="bg-[#333333] rounded-lg p-4 mb-8">
              <div className="flex items-start gap-3 text-left">
                <Mail className="h-5 w-5 text-[#F7EA1C] mt-0.5" />
                <div>
                  <p className="font-medium text-[#F7EA1C]">Confirmation Email Sent</p>
                  <p className="text-sm text-gray-300 mt-1">
                    We've sent a confirmation to <strong className="text-white">{email}</strong>
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-8">
            <div className="flex items-start gap-3 text-left">
              <Package className="h-5 w-5 text-blue-600 mt-0.5" />
              <div>
                <p className="font-medium text-blue-800">Delivery Estimate</p>
                <p className="text-sm text-blue-700 mt-1">
                  Your samples will arrive within 3-5 working days via Royal Mail.
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              variant="outline"
              onClick={() => navigate('/tiles')}
            >
              Continue Browsing
            </Button>
            <Button
              className="bg-[#333333] hover:bg-[#444444] text-[#F7EA1C] font-semibold"
              onClick={() => navigate('/tiles')}
              data-testid="back-to-home-btn"
            >
              Back to Home
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      <ShopFooter />
    </div>
  );
};

export default TileSampleSuccessPage;
