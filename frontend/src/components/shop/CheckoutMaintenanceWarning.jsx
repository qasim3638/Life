import React from 'react';
import { AlertTriangle, Lock } from 'lucide-react';
import { useCheckoutMaintenanceCountdown } from '../../contexts/MaintenanceContext';

/**
 * Inline warning card rendered above the Proceed-to-Checkout / Pay CTA.
 * Two tiers:
 *   - warning (3-15 min): amber, CTA still works but customer is told
 *   - blocking (0-2 min): rose, CTA is disabled (caller wires that — this
 *     component just renders the visual)
 */
export default function CheckoutMaintenanceWarning({ context = 'cart' }) {
  const cd = useCheckoutMaintenanceCountdown();
  if (!cd.active) return null;

  const { blocking, minutes } = cd;

  if (blocking) {
    return (
      <div
        role="alert"
        aria-live="assertive"
        data-testid="checkout-maintenance-blocking"
        className="rounded-xl border-2 border-rose-300 bg-rose-50 px-4 py-3 my-3 shadow-[0_1px_3px_rgba(190,18,60,0.08)]"
      >
        <div className="flex items-start gap-3">
          <Lock className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
          <div className="text-sm text-rose-900 leading-snug">
            <p className="font-semibold">Checkout is closing for scheduled maintenance.</p>
            <p className="mt-1 text-rose-800">
              The site goes offline in about <span className="font-bold tabular-nums">
                {minutes === 0 ? 'less than a minute' : `${minutes} min${minutes === 1 ? '' : 's'}`}
              </span>. To make sure your payment isn't interrupted, please come back once we're live again — your basket is saved.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="checkout-maintenance-warning"
      className="rounded-xl border-2 border-amber-300 bg-amber-50 px-4 py-3 my-3 shadow-[0_1px_3px_rgba(217,119,6,0.08)]"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="text-sm text-amber-900 leading-snug">
          <p className="font-semibold">
            Heads up — scheduled maintenance starts in{' '}
            <span className="tabular-nums">{minutes} min{minutes === 1 ? '' : 's'}</span>.
          </p>
          <p className="mt-1 text-amber-800">
            {context === 'checkout'
              ? 'You can still complete this payment. Just try to finish before the window kicks in, or your basket will be saved for after we\'re back.'
              : 'You can still proceed, but please check out promptly — once the window starts, payments will be paused.'}
          </p>
        </div>
      </div>
    </div>
  );
}
