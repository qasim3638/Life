import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Sparkles, Copy, Check, Mail, MessageCircle, Share2 } from 'lucide-react';
import AnnouncementRibbon from '../../components/shop/AnnouncementRibbon';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ReferAFriendPage() {
  const [searchParams] = useSearchParams();
  const initialRef = searchParams.get('ref') || '';
  const [referrer, setReferrer] = useState(initialRef);
  const [code, setCode] = useState(null); // { code, percent_off, max_uses, used_count, expires_at, share_url }
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    let cancelled = false;
    axios.get(`${API}/storefront-features/public`)
      .then(res => { if (!cancelled) setEnabled(res.data?.refer_a_friend_enabled !== false); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const fetchCode = async (input) => {
    const value = (input ?? referrer).trim();
    if (!value) return;
    setLoading(true);
    try {
      const isCode = /^BACK-/i.test(value) || /^FRIEND-/i.test(value);
      const payload = isCode ? { source_code: value.toUpperCase() } : { referrer_email: value.toLowerCase() };
      const res = await axios.post(`${API}/shop/referrals/get-code`, payload);
      setCode(res.data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not fetch your friend code');
    } finally {
      setLoading(false);
    }
  };

  // Auto-fetch if a ref param was provided
  useEffect(() => {
    if (initialRef) fetchCode(initialRef);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const shareText = code
    ? `Get ${code.percent_off}% off your tile order at Tile Station with my code ${code.code}: ${code.share_url}`
    : '';

  const copy = async () => {
    if (!code) return;
    try {
      await navigator.clipboard.writeText(`${code.code} — ${code.share_url}`);
      setCopied(true);
      toast.success('Code copied to clipboard');
      setTimeout(() => setCopied(false), 1800);
    } catch {
      toast.error('Could not copy. Long-press the code to copy manually.');
    }
  };

  const shareWhatsApp = () => {
    if (!code) return;
    window.open(`https://wa.me/?text=${encodeURIComponent(shareText)}`, '_blank');
  };
  const shareEmail = () => {
    if (!code) return;
    const subject = encodeURIComponent(`${code.percent_off}% off at Tile Station`);
    const body = encodeURIComponent(shareText);
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  };
  const shareNative = async () => {
    if (!code || !navigator.share) return;
    try {
      await navigator.share({ title: 'Tile Station discount', text: shareText, url: code.share_url });
    } catch { /* user cancelled */ }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-50 to-amber-50">
      <AnnouncementRibbon />
      <div className="max-w-2xl mx-auto px-5 py-12">
        <a href="/" className="text-xs text-gray-500 hover:text-gray-800 uppercase tracking-widest mb-4 inline-block" data-testid="back-home">← Back to Tile Station</a>

        {!enabled ? (
          <Card className="border-gray-200">
            <CardContent className="p-12 text-center">
              <Sparkles className="w-10 h-10 mx-auto text-gray-300 mb-3" />
              <h2 className="text-lg font-semibold mb-1">Referrals are currently paused</h2>
              <p className="text-sm text-gray-500">Check back soon, or contact us if you have a question.</p>
            </CardContent>
          </Card>
        ) : (
        <Card className="border-emerald-200 shadow-lg">
          <CardContent className="p-8">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-12 h-12 rounded-full bg-emerald-100 flex items-center justify-center">
                <Sparkles className="w-6 h-6 text-emerald-700" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Share & save</h1>
                <p className="text-sm text-gray-500">Give your friend 10% off their first tile order — no strings.</p>
              </div>
            </div>

            {!code && (
              <div className="space-y-3 mt-6" data-testid="refer-form">
                <Label className="text-xs uppercase tracking-wider text-gray-500">
                  Your email or your personal BACK code
                </Label>
                <div className="flex gap-2">
                  <Input
                    placeholder="you@example.com or BACK-XXXXXX"
                    value={referrer}
                    onChange={(e) => setReferrer(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && fetchCode()}
                    data-testid="referrer-input"
                  />
                  <Button onClick={() => fetchCode()} disabled={loading || !referrer.trim()} data-testid="get-code-btn">
                    {loading ? 'Working…' : 'Get my code'}
                  </Button>
                </div>
                <p className="text-xs text-gray-500">We'll generate a unique <strong>FRIEND-XXXXXX</strong> code you can share with anyone.</p>
              </div>
            )}

            {code && (
              <div className="mt-6 space-y-5" data-testid="refer-result">
                <div className="text-center bg-gradient-to-br from-emerald-50 to-emerald-100/50 border-2 border-dashed border-emerald-300 rounded-xl p-6">
                  <p className="text-[11px] uppercase tracking-widest text-emerald-700/70 mb-1">Your friend code</p>
                  <p className="text-3xl font-bold tracking-wider text-emerald-900 font-mono" data-testid="friend-code">{code.code}</p>
                  <p className="text-xs text-emerald-700 mt-2">
                    {code.percent_off}% off • {Math.max(0, (code.max_uses || 0) - (code.used_count || 0))} of {code.max_uses} uses remaining
                  </p>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <Button variant="outline" onClick={copy} data-testid="copy-btn">
                    {copied ? <Check className="w-4 h-4 mr-1" /> : <Copy className="w-4 h-4 mr-1" />}
                    Copy
                  </Button>
                  <Button variant="outline" onClick={shareWhatsApp} data-testid="share-whatsapp">
                    <MessageCircle className="w-4 h-4 mr-1" /> WhatsApp
                  </Button>
                  <Button variant="outline" onClick={shareEmail} data-testid="share-email">
                    <Mail className="w-4 h-4 mr-1" /> Email
                  </Button>
                  {typeof navigator !== 'undefined' && navigator.share && (
                    <Button variant="outline" onClick={shareNative} data-testid="share-native">
                      <Share2 className="w-4 h-4 mr-1" /> Share
                    </Button>
                  )}
                </div>

                <div className="text-center pt-2">
                  <button
                    onClick={() => { setCode(null); setReferrer(''); }}
                    className="text-xs text-gray-500 hover:text-gray-800 underline"
                    data-testid="refer-reset"
                  >
                    Use a different email or code
                  </button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
        )}

        <p className="text-center text-xs text-gray-400 mt-6">
          Friends use this code at checkout. Codes expire 30 days from creation.
        </p>
      </div>
    </div>
  );
}
