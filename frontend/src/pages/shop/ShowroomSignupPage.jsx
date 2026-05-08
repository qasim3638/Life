import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { CheckCircle2, Mail, Loader2 } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Showroom email-capture landing page.
 *
 * Designed for a tablet at the till — large-tap-target inputs, single screen,
 * no header chrome. Customers leave their email + name with explicit opt-in.
 * Shows a "thanks!" confirmation that auto-resets after 6 seconds so the next
 * walk-in finds a clean form.
 *
 * Copy is admin-controlled via /api/marketing/admin/settings — fetched here
 * via the public /api/marketing/public/lead-capture endpoint.
 */
export default function ShowroomSignupPage() {
  const [params] = useSearchParams();
  const showroomId = params.get('showroom') || '';

  const [config, setConfig] = useState(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    axios.get(`${API_URL}/api/marketing/public/lead-capture`)
      .then((r) => setConfig(r.data))
      .catch(() => setConfig({
        enabled: true,
        title: 'Hear about trade offers + new collections',
        subtitle: 'Drop your email below. Unsubscribe anytime.',
        consent_text: 'I agree to receive marketing emails.',
        success_message: "Thanks — you're on the list. See you soon!",
      }));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!name.trim() || !email.trim()) {
      setError('Name and email are required');
      return;
    }
    if (!consent) {
      setError('Please tick the consent box to continue');
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(`${API_URL}/api/marketing/showroom-signup`, {
        name: name.trim(),
        email: email.trim().toLowerCase(),
        consent: true,
        showroom_id: showroomId,
        source: 'showroom_tablet',
      });
      setSubmitted(true);
      setTimeout(() => {
        setName(''); setEmail(''); setConsent(false); setSubmitted(false);
      }, 6000);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not submit. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (!config) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0e0e0e] text-white">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  if (config.enabled === false) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0e0e0e] text-white p-8">
        <p className="text-center text-lg">Lead capture is currently paused. Please check back soon.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0e0e0e] via-[#1a1a1a] to-[#2a2a0a] flex items-center justify-center p-6">
      <div className="w-full max-w-xl bg-white rounded-3xl shadow-2xl p-8 sm:p-12" data-testid="showroom-signup-form">
        {submitted ? (
          <div className="text-center py-12" data-testid="showroom-signup-success">
            <div className="w-20 h-20 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-12 h-12 text-emerald-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900">{config.success_message}</h2>
            <p className="text-sm text-gray-500 mt-3">This screen will reset in a moment.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="text-center">
              <div className="w-14 h-14 rounded-2xl bg-[#F7EA1C] flex items-center justify-center mx-auto mb-3">
                <Mail className="w-7 h-7 text-[#1a1a1a]" />
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 leading-tight">{config.title}</h1>
              <p className="text-sm text-gray-600 mt-2">{config.subtitle}</p>
            </div>

            <div className="space-y-3">
              <div>
                <Label className="text-sm font-semibold">Your name</Label>
                <Input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="h-12 text-base mt-1"
                  placeholder="First name"
                  required
                  data-testid="showroom-signup-name"
                />
              </div>
              <div>
                <Label className="text-sm font-semibold">Email address</Label>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-12 text-base mt-1"
                  placeholder="you@example.com"
                  required
                  data-testid="showroom-signup-email"
                />
              </div>
            </div>

            <label className="flex items-start gap-3 cursor-pointer p-3 bg-gray-50 rounded-lg border">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-1 w-5 h-5"
                data-testid="showroom-signup-consent"
              />
              <span className="text-xs text-gray-700 leading-relaxed">{config.consent_text}</span>
            </label>

            {error && (
              <div className="bg-rose-50 border border-rose-200 text-rose-700 text-sm rounded-lg px-3 py-2" data-testid="showroom-signup-error">
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={submitting || !consent}
              className="w-full h-12 text-base font-bold bg-[#1a1a1a] hover:bg-[#333] text-[#F7EA1C] disabled:opacity-50"
              data-testid="showroom-signup-submit"
            >
              {submitting ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Saving…</> : 'Sign me up'}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
