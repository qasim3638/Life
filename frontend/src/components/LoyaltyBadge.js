import React, { useState, useEffect } from 'react';
import { Star, Gift, Award } from 'lucide-react';
import { Button } from './ui/button';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const TIER_ICONS = {
  bronze: '🥉',
  silver: '🥈',
  gold: '🥇',
  platinum: '💎'
};

/**
 * LoyaltyBadge - Shows customer loyalty status and points
 * Can be used on Invoice page to show/enroll customers
 */
export const LoyaltyBadge = ({
  email,
  name = '',
  className = '',
  showEnrollButton = true,
  compact = false
}) => {
  const [loyalty, setLoyalty] = useState(null);
  const [loading, setLoading] = useState(false);
  const [enrolling, setEnrolling] = useState(false);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (email && email.includes('@')) {
      checkLoyaltyStatus(email);
    } else {
      setLoyalty(null);
      setChecked(false);
    }
  }, [email]);

  const checkLoyaltyStatus = async (customerEmail) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/loyalty/account/${encodeURIComponent(customerEmail)}`);
      if (res.ok) {
        const data = await res.json();
        if (data.enrolled) {
          setLoyalty(data);
        } else {
          setLoyalty(null);
        }
      } else {
        setLoyalty(null);
      }
    } catch (e) {
      console.log('Loyalty check error:', e);
      setLoyalty(null);
    } finally {
      setLoading(false);
      setChecked(true);
    }
  };

  const handleEnroll = async () => {
    if (!email || !email.includes('@')) {
      toast.error('Valid email required to enroll');
      return;
    }
    
    setEnrolling(true);
    try {
      const res = await fetch(`${API_URL}/api/loyalty/enroll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_id: email,
          email: email,
          name: name || 'Customer'
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        setLoyalty({
          enrolled: true,
          current_points: 0,
          tier: data.tier
        });
        toast.success(`Customer enrolled! They'll earn 10 points per £1 spent.`);
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Failed to enroll');
      }
    } catch (e) {
      console.error('Enroll error:', e);
      toast.error('Failed to enroll customer');
    } finally {
      setEnrolling(false);
    }
  };

  // Don't show anything until email is entered
  if (!email || !email.includes('@') || !checked) {
    return null;
  }

  // Loading state
  if (loading) {
    return (
      <div className={`inline-flex items-center gap-1 text-xs text-gray-400 ${className}`}>
        <div className="animate-spin h-3 w-3 border-2 border-gray-300 border-t-gray-600 rounded-full"></div>
        <span>Checking loyalty...</span>
      </div>
    );
  }

  // Customer is enrolled
  if (loyalty?.enrolled) {
    const tierIcon = TIER_ICONS[loyalty.tier?.tier_id] || '⭐';
    const tierName = loyalty.tier?.name || 'Bronze';
    const points = loyalty.current_points || 0;
    const discount = loyalty.tier?.discount || 0;

    if (compact) {
      return (
        <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${className}`}
             style={{ backgroundColor: `${loyalty.tier?.color}20`, color: loyalty.tier?.color || '#CD7F32' }}
             title={`${points.toLocaleString()} points - ${discount}% discount`}>
          <span>{tierIcon}</span>
          <span>{tierName}</span>
          <span className="text-gray-500">({points.toLocaleString()} pts)</span>
        </div>
      );
    }

    return (
      <div className={`flex items-center gap-3 p-2 rounded-lg bg-gradient-to-r from-amber-50 to-yellow-50 border border-amber-200 ${className}`}>
        <div className="flex items-center gap-2">
          <span className="text-2xl">{tierIcon}</span>
          <div>
            <p className="text-sm font-medium text-amber-800">{tierName} Member</p>
            <p className="text-xs text-amber-600">{points.toLocaleString()} points</p>
          </div>
        </div>
        {discount > 0 && (
          <div className="ml-auto text-right">
            <p className="text-sm font-bold text-green-600">{discount}% OFF</p>
            <p className="text-xs text-gray-500">Loyalty discount</p>
          </div>
        )}
      </div>
    );
  }

  // Not enrolled - show enroll option
  if (showEnrollButton) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <span className="text-xs text-gray-500">Not in loyalty program</span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleEnroll}
          disabled={enrolling}
          className="h-6 text-xs px-2 border-amber-400 text-amber-600 hover:bg-amber-50"
        >
          {enrolling ? (
            <>
              <div className="animate-spin h-3 w-3 border-2 border-amber-400 border-t-transparent rounded-full mr-1"></div>
              Enrolling...
            </>
          ) : (
            <>
              <Gift className="h-3 w-3 mr-1" />
              Enroll
            </>
          )}
        </Button>
      </div>
    );
  }

  return null;
};

export default LoyaltyBadge;
