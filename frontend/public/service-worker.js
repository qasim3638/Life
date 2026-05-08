// Service Worker with Network-First Strategy
// This ensures users always get the latest version
const CACHE_VERSION = Date.now(); // Dynamic version based on deployment time
const CACHE_NAME = `tilestation-v${CACHE_VERSION}`;

// Only cache static assets that rarely change
const STATIC_ASSETS = [
  '/icon-192.png',
  '/icon-512.png'
];

// Install event - cache only essential static files
self.addEventListener('install', (event) => {
  console.log('[SW] Installing new service worker...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Caching static assets');
        return cache.addAll(STATIC_ASSETS);
      })
      .catch((error) => {
        console.log('[SW] Cache installation failed:', error);
      })
  );
  // Don't call skipWaiting() here - wait for user action or next page load
  // This prevents interrupting ongoing requests during login/form submissions
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating new service worker...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          // Delete all old caches
          if (cacheName !== CACHE_NAME && cacheName.startsWith('tilestation-')) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
    // Don't call clients.claim() immediately - let pages continue with their current SW
    // They'll get the new SW on next page load
  );
});

// Fetch event - NETWORK FIRST strategy
// Always try network first, fall back to cache only if offline
self.addEventListener('fetch', (event) => {
  const request = event.request;
  
  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }
  
  // Skip API calls - never cache these
  if (request.url.includes('/api/')) {
    return;
  }
  
  // Skip external resources
  if (!request.url.startsWith(self.location.origin)) {
    return;
  }

  event.respondWith(
    // NETWORK FIRST - always try to get fresh content
    fetch(request)
      .then((response) => {
        // If we got a valid response, cache it for offline use
        if (response && response.status === 200) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseToCache);
          });
        }
        return response;
      })
      .catch(() => {
        // Network failed - try cache as fallback (offline mode)
        return caches.match(request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          // If no cache, return offline message for navigation requests
          if (request.mode === 'navigate') {
            return new Response(
              '<!DOCTYPE html><html><head><title>Offline</title></head><body style="font-family:sans-serif;text-align:center;padding:50px;"><h1>You are offline</h1><p>Please check your internet connection and try again.</p><button onclick="location.reload()">Retry</button></body></html>',
              { headers: { 'Content-Type': 'text/html' } }
            );
          }
        });
      })
  );
});

// Listen for messages from the client
self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
  if (event.data === 'clearCache') {
    caches.keys().then((cacheNames) => {
      cacheNames.forEach((cacheName) => {
        if (cacheName.startsWith('tilestation-')) {
          caches.delete(cacheName);
        }
      });
    });
  }
});

// ─── Web Push Notifications ────────────────────────────────────────────
// Fired when the push service delivers a message from our backend.
// Payload shape: {title, body, url, icon, image, tag}
self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { title: 'Tile Station', body: event.data ? event.data.text() : '' };
  }

  const title = payload.title || 'Tile Station';
  const options = {
    body: payload.body || '',
    icon: payload.icon || '/icon-192.png',
    badge: '/icon-192.png',
    image: payload.image || undefined,
    tag: payload.tag || 'tilestation-push',
    data: { url: payload.url || '/' },
    requireInteraction: false,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// Open the URL embedded in the notification when the user clicks
// (or focus an existing tab on the same origin).
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const c of clientList) {
        try {
          const u = new URL(c.url);
          if (u.origin === self.location.origin && 'focus' in c) {
            c.navigate(target).catch(() => {});
            return c.focus();
          }
        } catch { /* ignore */ }
      }
      if (clients.openWindow) return clients.openWindow(target);
    })
  );
});
