/**
 * PaymentMethodCards — Trade Point-style payment selector cards on the
 * final checkout step. Visual reassurance only; the actual payment-method
 * choice happens on Stripe's hosted page after the shopper clicks "Pay".
 *
 * Each card shows:
 *   - method name on the left
 *   - branded inline-SVG logos on the right
 *
 * Cards only render when the admin has enabled that method in
 * Checkout Settings → Payments tab.
 */
import React from 'react';

/* -------- Brand logos as inline SVG (no external requests) -------- */

const VisaLogo = () => (
  <svg viewBox="0 0 48 16" className="h-5 w-auto" aria-label="Visa">
    <text x="0" y="13" fontFamily="Arial, sans-serif" fontWeight="900" fontSize="14" fill="#1A1F71" fontStyle="italic">VISA</text>
  </svg>
);

const MastercardLogo = () => (
  <svg viewBox="0 0 32 20" className="h-5 w-auto" aria-label="Mastercard">
    <circle cx="12" cy="10" r="8" fill="#EB001B" />
    <circle cx="20" cy="10" r="8" fill="#F79E1B" />
    <path d="M16 4.5a8 8 0 0 1 0 11 8 8 0 0 1 0-11z" fill="#FF5F00" />
  </svg>
);

const AmexLogo = () => (
  <svg viewBox="0 0 36 20" className="h-5 w-auto" aria-label="American Express">
    <rect width="36" height="20" rx="2" fill="#1F72CD" />
    <text x="18" y="14" textAnchor="middle" fontFamily="Arial, sans-serif" fontWeight="700" fontSize="7" fill="#fff">AMEX</text>
  </svg>
);

const PayPalLogo = () => (
  <svg viewBox="0 0 80 20" className="h-5 w-auto" aria-label="PayPal">
    <text x="0" y="15" fontFamily="Arial, sans-serif" fontWeight="900" fontSize="16" fontStyle="italic" fill="#003087">Pay</text>
    <text x="26" y="15" fontFamily="Arial, sans-serif" fontWeight="900" fontSize="16" fontStyle="italic" fill="#009CDE">Pal</text>
  </svg>
);

const KlarnaLogo = () => (
  <svg viewBox="0 0 64 24" className="h-5 w-auto" aria-label="Klarna">
    <rect width="64" height="24" rx="6" fill="#FFA8CD" />
    <text x="32" y="17" textAnchor="middle" fontFamily="Arial, sans-serif" fontWeight="800" fontSize="13" fill="#000">Klarna.</text>
  </svg>
);

const ApplePayLogo = () => (
  <svg viewBox="0 0 56 24" className="h-5 w-auto" aria-label="Apple Pay">
    <rect width="56" height="24" rx="4" fill="#000" />
    <path d="M14.7 9.4c-.3.4-.9.7-1.4.6 0-.6.2-1.2.6-1.5.3-.4.9-.7 1.4-.7 0 .6-.2 1.1-.6 1.6zm.5.8c-.8 0-1.5.5-1.9.5s-1-.5-1.6-.5c-.8 0-1.6.5-2 1.2-.9 1.5-.2 3.7.6 4.9.4.6.9 1.3 1.5 1.3.6 0 .8-.4 1.6-.4s.9.4 1.6.4 1-.6 1.4-1.2c.5-.7.6-1.4.6-1.4-.1-.1-1.2-.5-1.2-1.8 0-1.1.9-1.6.9-1.7-.5-.7-1.2-.8-1.5-.8z" fill="#fff" />
    <text x="22" y="16" fontFamily="Arial, sans-serif" fontWeight="600" fontSize="10" fill="#fff">Pay</text>
  </svg>
);

const GooglePayLogo = () => (
  <svg viewBox="0 0 64 24" className="h-5 w-auto" aria-label="Google Pay">
    <rect width="64" height="24" rx="12" fill="#fff" stroke="#dadce0" strokeWidth="1" />
    <text x="6" y="16" fontFamily="Arial, sans-serif" fontWeight="500" fontSize="10" fill="#4285F4">G</text>
    <text x="13" y="16" fontFamily="Arial, sans-serif" fontWeight="500" fontSize="10" fill="#EA4335">o</text>
    <text x="19" y="16" fontFamily="Arial, sans-serif" fontWeight="500" fontSize="10" fill="#FBBC05">o</text>
    <text x="25" y="16" fontFamily="Arial, sans-serif" fontWeight="500" fontSize="10" fill="#4285F4">g</text>
    <text x="31" y="16" fontFamily="Arial, sans-serif" fontWeight="500" fontSize="10" fill="#34A853">l</text>
    <text x="34" y="16" fontFamily="Arial, sans-serif" fontWeight="500" fontSize="10" fill="#EA4335">e</text>
    <text x="42" y="16" fontFamily="Arial, sans-serif" fontWeight="600" fontSize="10" fill="#5F6368">Pay</text>
  </svg>
);

/* -------- Card primitive -------- */

const MethodCard = ({ title, subtitle, logos, testId, selected, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    aria-pressed={selected}
    className={`w-full text-left bg-white border rounded-xl px-5 py-4 flex items-center justify-between gap-4 transition-all cursor-pointer ${
      selected
        ? 'border-[#1C1917] ring-2 ring-[#1C1917]/15 shadow-[0_2px_12px_rgba(28,25,23,0.10)]'
        : 'border-[#E7E5E4] hover:border-[#1C1917]/30'
    }`}
    data-testid={testId}
    data-selected={selected ? '1' : '0'}
  >
    <div className="flex items-center gap-3 flex-1 min-w-0">
      {/* Selection radio */}
      <span
        aria-hidden
        className={`flex items-center justify-center h-5 w-5 rounded-full border-2 flex-shrink-0 transition-colors ${
          selected ? 'border-[#1C1917] bg-[#1C1917]' : 'border-gray-300 bg-white'
        }`}
      >
        {selected && <span className="h-2 w-2 rounded-full bg-[#F7EA1C]" />}
      </span>
      <div className="flex flex-col min-w-0">
        <span className="text-[14px] font-semibold text-[#1C1917]">{title}</span>
        {subtitle && <span className="text-[11px] text-[#78716C] mt-0.5 truncate">{subtitle}</span>}
      </div>
    </div>
    <div className="flex items-center gap-2 flex-shrink-0">
      {logos.map((Logo, i) => (
        <span key={i} className="inline-flex items-center justify-center">
          <Logo />
        </span>
      ))}
    </div>
  </button>
);

/* -------- Main component -------- */

export default function PaymentMethodCards({ payments = {}, selected = 'card', onSelect }) {
  // Cards always shown (cards always available via Stripe)
  const cards = [
    {
      key: 'card',
      show: true,
      title: 'Credit / Debit Cards',
      subtitle: 'Visa, Mastercard, Amex',
      logos: [VisaLogo, MastercardLogo, AmexLogo],
      testId: 'pay-method-card',
    },
    {
      key: 'paypal',
      show: !!payments.paypal_enabled,
      title: 'PayPal',
      subtitle: 'Pay with your PayPal balance or linked bank',
      logos: [PayPalLogo],
      testId: 'pay-method-paypal',
    },
    {
      key: 'klarna',
      show: !!payments.klarna_enabled,
      title: 'Klarna',
      subtitle: 'Pay in 3 interest-free instalments',
      logos: [KlarnaLogo],
      testId: 'pay-method-klarna',
    },
    {
      key: 'wallet',
      show: !!payments.wallet_express_enabled,
      title: 'Apple Pay & Google Pay',
      subtitle: 'One-tap on supported devices',
      logos: [ApplePayLogo, GooglePayLogo],
      testId: 'pay-method-wallet',
    },
  ].filter(c => c.show);

  return (
    <div className="space-y-3" data-testid="payment-method-cards" role="radiogroup" aria-label="Payment method">
      {cards.map(c => (
        <MethodCard
          key={c.key}
          title={c.title}
          subtitle={c.subtitle}
          logos={c.logos}
          testId={c.testId}
          selected={selected === c.key}
          onClick={() => onSelect && onSelect(c.key)}
        />
      ))}
    </div>
  );
}
