import React from "react";
import ReactDOM from "react-dom/client";
import * as Sentry from "@sentry/react";
import "@/index.css";
import App from "@/App";

// Sentry — only activates when REACT_APP_SENTRY_DSN is set in .env.
// No-op otherwise, so this is safe to keep in production builds.
const SENTRY_DSN = process.env.REACT_APP_SENTRY_DSN;
if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: process.env.REACT_APP_SENTRY_ENV || "production",
    release: process.env.REACT_APP_SENTRY_RELEASE || "tile-station-frontend",
    integrations: [Sentry.browserTracingIntegration()],
    // 10 % of transactions traced — enough to catch slow pages without quota burn
    tracesSampleRate: 0.1,
    // Don't send PII by default; we filter on the backend if needed
    sendDefaultPii: false,
    // Drop noisy chunks (failed analytics, browser extensions)
    beforeSend(event) {
      const msg = event.exception?.values?.[0]?.value || "";
      if (/extension|chrome-extension|moz-extension|adsbygoogle/i.test(msg)) return null;
      return event;
    },
  });
}

// Build version - auto-updated
console.log('Tile Station Build: 2026-04-28-sentry-enabled');

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <Sentry.ErrorBoundary fallback={({ error, resetError }) => (
      <div style={{ padding: 32, fontFamily: 'system-ui', maxWidth: 540, margin: '64px auto', textAlign: 'center' }}>
        <h1 style={{ fontSize: 22, marginBottom: 8 }}>Something went wrong</h1>
        <p style={{ color: '#666', marginBottom: 16 }}>We've been notified. Please try refreshing the page.</p>
        <button
          onClick={resetError}
          style={{ padding: '8px 16px', background: '#1C1917', color: '#F7EA1C', border: 0, borderRadius: 8, cursor: 'pointer' }}
        >Try again</button>
        {process.env.NODE_ENV === 'development' && (
          <pre style={{ marginTop: 16, fontSize: 11, color: '#999', textAlign: 'left', overflow: 'auto' }}>{String(error)}</pre>
        )}
      </div>
    )}>
      <App />
    </Sentry.ErrorBoundary>
  </React.StrictMode>,
);

// Register service worker for PWA functionality
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/service-worker.js')
      .then((registration) => {
        console.log('ServiceWorker registered: ', registration);
      })
      .catch((error) => {
        console.log('ServiceWorker registration failed: ', error);
      });
  });
}
