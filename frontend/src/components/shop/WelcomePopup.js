import React, { useState, useEffect } from 'react';
import { X, ArrowRight, Mail, Sparkles } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function WelcomePopup() {
  const [config, setConfig] = useState(null);
  const [visible, setVisible] = useState(false);
  const [closing, setClosing] = useState(false);
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const fetchPopup = async () => {
      try {
        // Master switch from storefront features
        const featRes = await fetch(`${API_URL}/api/storefront-features/public`);
        if (featRes.ok) {
          const feat = await featRes.json();
          if (feat && feat.welcome_popup_visible === false) return;
        }
        const res = await fetch(`${API_URL}/api/website-admin/welcome-popup/public`);
        if (!res.ok) return;
        const data = await res.json();
        if (!data.enabled) return;

        // Check frequency
        const freq = data.frequency || 'once';
        const storageKey = 'ts_popup_dismissed';

        if (freq === 'once') {
          if (localStorage.getItem(storageKey)) return;
        } else if (freq === 'session') {
          if (sessionStorage.getItem(storageKey)) return;
        }
        // 'always' — show every time

        setConfig(data);

        // Delay before showing
        const delay = (data.delay_seconds || 2) * 1000;
        const timer = setTimeout(() => setVisible(true), delay);
        return () => clearTimeout(timer);
      } catch (e) {
        console.error('Welcome popup fetch error:', e);
      }
    };
    fetchPopup();
  }, []);

  const handleClose = () => {
    setClosing(true);
    const freq = config?.frequency || 'once';
    if (freq === 'once') localStorage.setItem('ts_popup_dismissed', '1');
    else if (freq === 'session') sessionStorage.setItem('ts_popup_dismissed', '1');
    setTimeout(() => { setVisible(false); setConfig(null); }, 300);
  };

  const handleEmailSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setSubmitting(true);
    try {
      await fetch(`${API_URL}/api/website-admin/welcome-popup/email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() })
      });
      setSubmitted(true);
    } catch (err) {
      console.error('Email submit error:', err);
    } finally {
      setSubmitting(false);
    }
  };

  if (!config || !visible) return null;

  return (
    <div
      className={`fixed inset-0 z-[9999] flex items-center justify-center p-4 transition-opacity duration-300 ${closing ? 'opacity-0' : 'opacity-100'}`}
      data-testid="welcome-popup-overlay"
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={handleClose} />

      {/* Popup Card */}
      <div
        className={`relative bg-white rounded-2xl sm:rounded-3xl shadow-2xl overflow-hidden max-w-lg w-full mx-4 transform transition-all duration-300 ${closing ? 'scale-95 opacity-0' : 'scale-100 opacity-100'}`}
        data-testid="welcome-popup-card"
      >
        {/* Close button */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 z-10 w-9 h-9 bg-black/10 hover:bg-black/20 rounded-full flex items-center justify-center transition-colors"
          data-testid="welcome-popup-close"
        >
          <X className="w-4 h-4 text-gray-700" />
        </button>

        {/* Image */}
        {config.image_url && (
          <div className="w-full h-52 overflow-hidden">
            <img
              src={config.image_url}
              alt=""
              className="w-full h-full object-cover"
              data-testid="welcome-popup-image"
            />
          </div>
        )}

        {/* Content */}
        <div className="p-5 sm:p-7 pt-5 sm:pt-6">
          {/* Heading */}
          {config.heading && (
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900 mb-2 leading-tight" data-testid="welcome-popup-heading">
              {config.heading}
            </h2>
          )}

          {/* Message */}
          {config.message && (
            <p className="text-gray-600 mb-5 leading-relaxed whitespace-pre-line" data-testid="welcome-popup-message">
              {config.message}
            </p>
          )}

          {/* Email Capture */}
          {config.show_email_capture && !submitted && (
            <form onSubmit={handleEmailSubmit} className="mb-4" data-testid="welcome-popup-email-form">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={config.email_placeholder || 'Enter your email'}
                    className="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition-all text-sm"
                    data-testid="welcome-popup-email-input"
                  />
                </div>
                <button
                  type="submit"
                  disabled={submitting}
                  className="bg-gray-900 hover:bg-gray-800 text-white font-semibold px-5 py-3 rounded-xl transition-colors text-sm whitespace-nowrap disabled:opacity-50"
                  data-testid="welcome-popup-email-submit"
                >
                  {submitting ? '...' : (config.email_button_text || 'Subscribe')}
                </button>
              </div>
            </form>
          )}

          {/* Email Success — code is sent via email only, not revealed here, to encourage registration */}
          {config.show_email_capture && submitted && (
            <div className="mb-4 space-y-3" data-testid="welcome-popup-email-success">
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-center">
                <Sparkles className="w-5 h-5 text-emerald-600 mx-auto mb-1" />
                <p className="text-emerald-800 font-semibold text-sm">Check your inbox.</p>
                <p className="text-emerald-700/80 text-xs mt-1">
                  Your discount code is on its way to <strong>{email}</strong>.
                </p>
              </div>
              <a
                href="/shop/register"
                className="block w-full text-center text-sm font-semibold text-emerald-700 hover:text-emerald-900 underline"
                data-testid="welcome-popup-register-link"
              >
                Create an account →
              </a>
            </div>
          )}

          {/* CTA Button */}
          {config.cta_text && (
            <a
              href={config.cta_link || '#'}
              onClick={(e) => {
                if (!config.cta_link || config.cta_link === '#') {
                  e.preventDefault();
                  handleClose();
                }
              }}
              className="inline-flex items-center justify-center gap-2 w-full bg-amber-500 hover:bg-amber-600 text-white font-bold py-3.5 px-6 rounded-xl transition-colors text-center"
              data-testid="welcome-popup-cta"
            >
              {config.cta_text}
              <ArrowRight className="w-4 h-4" />
            </a>
          )}

          {/* Dismiss text */}
          {!config.cta_text && !config.show_email_capture && (
            <button
              onClick={handleClose}
              className="w-full text-center text-sm text-gray-400 hover:text-gray-600 transition-colors py-2"
            >
              No thanks, close this
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
