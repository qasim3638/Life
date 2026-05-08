import React from 'react';
import { Link } from 'react-router-dom';
import { Wrench, ArrowLeft, Home } from 'lucide-react';

const DEFAULT_HEADLINE = 'Under Maintenance';
const DEFAULT_MESSAGE = "We're working on making this page even better for you.";

export default function MaintenancePage({ headline, message }) {
  const finalHeadline = headline || DEFAULT_HEADLINE;
  const finalMessage = message || DEFAULT_MESSAGE;
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4" data-testid="maintenance-page">
      <div className="max-w-lg w-full text-center">
        {/* Icon */}
        <div className="mx-auto w-24 h-24 bg-amber-100 rounded-full flex items-center justify-center mb-8">
          <Wrench className="w-12 h-12 text-amber-600" />
        </div>

        {/* Heading */}
        <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4" data-testid="maintenance-headline">
          {finalHeadline}
        </h1>

        {/* Message */}
        <p className="text-lg text-gray-600 mb-10 leading-relaxed whitespace-pre-line" data-testid="maintenance-message">
          {finalMessage}
        </p>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            to="/shop"
            className="inline-flex items-center gap-2 bg-gray-900 hover:bg-gray-800 text-white font-semibold px-6 py-3 rounded-xl transition-colors"
            data-testid="maintenance-home-btn"
          >
            <Home className="w-4 h-4" />
            Go to Homepage
          </Link>
          <button
            onClick={() => window.history.back()}
            className="inline-flex items-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold px-6 py-3 rounded-xl transition-colors"
            data-testid="maintenance-back-btn"
          >
            <ArrowLeft className="w-4 h-4" />
            Go Back
          </button>
        </div>

        {/* Branding */}
        <p className="mt-12 text-sm text-gray-400">Tile Station</p>
      </div>
    </div>
  );
}
