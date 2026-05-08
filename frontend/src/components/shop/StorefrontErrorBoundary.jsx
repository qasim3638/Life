import React from 'react';
import * as Sentry from '@sentry/react';

/**
 * Per-route error boundary for the storefront.
 *
 * Customer-facing crashes used to bubble up to the root Sentry
 * boundary which renders "Something went wrong" with no context.
 * That's a dead-end UX. This boundary:
 *   • Renders a recoverable fallback that links back to the shop
 *   • Reports the actual error name + stack to Sentry with a tag
 *     so we can filter for storefront crashes specifically
 *   • Prints the stack in development
 *
 * Wrap individual pages where a crash on ONE product/collection
 * shouldn't take down the rest of the user's session.
 */
export class StorefrontErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, errorInfo) {
    // Report with structured context so Sentry groups storefront
    // crashes together rather than mixing them with admin / API ones.
    try {
      Sentry.withScope((scope) => {
        scope.setTag('boundary', 'storefront');
        scope.setTag('route', this.props.routeName || 'unknown');
        scope.setExtra('componentStack', errorInfo?.componentStack);
        scope.setExtra('url', typeof window !== 'undefined' ? window.location.href : 'ssr');
        Sentry.captureException(error);
      });
    } catch (_) {
      // Sentry may not be initialised in dev — silently no-op.
    }
    if (typeof console !== 'undefined') {
      // eslint-disable-next-line no-console
      console.error('[storefront] crash on route', this.props.routeName, error, errorInfo);
    }
  }

  reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="min-h-[60vh] flex items-center justify-center px-4 py-16 bg-gray-50">
        <div className="max-w-md w-full text-center bg-white rounded-xl shadow-sm p-8 border border-gray-200">
          <div className="text-5xl mb-3" aria-hidden="true">😕</div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            We couldn't load this collection
          </h2>
          <p className="text-sm text-gray-600 mb-5 leading-relaxed">
            Sorry — something went wrong on our end. Our team has been notified.
            In the meantime, try refreshing or browse our other tile collections.
          </p>
          <div className="flex flex-col sm:flex-row gap-2 justify-center">
            <button
              type="button"
              onClick={this.reset}
              className="px-4 py-2.5 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-800"
              data-testid="storefront-error-retry"
            >
              Try again
            </button>
            <a
              href="/shop/collections"
              className="px-4 py-2.5 rounded-lg bg-white border border-gray-300 text-gray-800 text-sm font-medium hover:bg-gray-50"
              data-testid="storefront-error-browse-all"
            >
              Browse all collections
            </a>
          </div>
          <p className="text-xs text-gray-400 mt-5">
            Need help right away? Call us on{' '}
            <a href="tel:01732424242" className="underline">01732 424242</a>{' '}
            or pop into any showroom.
          </p>
          {process.env.NODE_ENV === 'development' && (
            <pre className="text-[10px] text-left text-rose-700 mt-4 overflow-auto max-h-32 bg-rose-50 p-2 rounded">
              {String(this.state.error?.message || this.state.error)}
              {'\n\n'}
              {this.state.error?.stack || ''}
            </pre>
          )}
        </div>
      </div>
    );
  }
}

export default StorefrontErrorBoundary;
