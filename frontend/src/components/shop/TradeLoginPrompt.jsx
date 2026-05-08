/**
 * TradeLoginPrompt - PROTECTED CRITICAL COMPONENT
 * 
 * DO NOT REMOVE OR CONDITIONALLY HIDE THIS COMPONENT
 * based on tier pricing, product settings, or any admin config.
 * 
 * This component MUST be visible to all non-logged-in visitors
 * on every product page (Collection and Individual).
 * 
 * Visibility rules:
 *   - SHOW when user is NOT logged in (no shop_token/tile_shop_token)
 *   - HIDE when user IS logged in as a trade customer
 *   - NEVER hide based on tier_pricing_disabled or any product flag
 */
import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { User, Users } from 'lucide-react';
import { Button } from '../ui/button';

/**
 * Full Trade Login box used on Collection Detail pages.
 * Shows Sign Up + Trade Login buttons in an amber-themed card.
 */
export const TradeLoginBox = ({ isLoggedIn }) => {
  if (isLoggedIn) return null;

  return (
    <div data-testid="trade-customer-box" className="bg-amber-50 border border-amber-200 rounded-lg p-4">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0">
          <User className="w-5 h-5 text-amber-600" />
        </div>
        <div>
          <p className="font-medium text-gray-900">Trade Customer?</p>
          <p className="text-sm text-gray-600">Login to see your discounted trade prices</p>
        </div>
      </div>
      <div className="flex gap-2">
        <Link
          to="/shop/trade/register"
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-center hover:bg-white transition"
          data-testid="trade-signup-link"
        >
          Sign Up
        </Link>
        <Link
          to="/shop/trade/login"
          className="flex-1 px-4 py-2 bg-amber-500 text-white rounded-lg text-sm font-medium text-center hover:bg-amber-600 transition"
          data-testid="trade-login-link"
        >
          Trade Login
        </Link>
      </div>
    </div>
  );
};

/**
 * Compact Trade Login prompt used on Individual Product (Tile Detail) pages.
 * Shows as a gradient banner with Sign Up + Login buttons inline.
 */
export const TradeLoginBanner = ({ isTrade }) => {
  const navigate = useNavigate();

  if (isTrade) return null;

  return (
    <div data-testid="trade-login-banner" className="bg-gradient-to-r from-gray-100 to-amber-50 rounded-lg p-3 mt-3 border border-amber-200">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="bg-amber-500 text-white p-1.5 rounded-full">
            <Users className="w-4 h-4" />
          </div>
          <div>
            <p className="text-gray-800 text-sm font-semibold">Trade Customer?</p>
            <p className="text-gray-500 text-xs">Login to see your discounted prices</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            className="border-amber-400 text-amber-700 hover:bg-amber-50"
            onClick={() => navigate('/shop/trade/register')}
            data-testid="trade-banner-signup"
          >
            Sign Up
          </Button>
          <Button
            size="sm"
            className="bg-amber-500 hover:bg-amber-600 text-white"
            onClick={() => navigate('/shop/trade/login?redirect=' + encodeURIComponent(window.location.pathname))}
            data-testid="trade-banner-login"
          >
            Login
          </Button>
        </div>
      </div>
    </div>
  );
};
