import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { RefreshCw } from 'lucide-react';

// Component to handle app updates
export function useAppUpdate() {
  const [updateAvailable, setUpdateAvailable] = useState(false);

  useEffect(() => {
    if ('serviceWorker' in navigator) {
      // Listen for service worker updates
      navigator.serviceWorker.ready.then((registration) => {
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          if (newWorker) {
            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                setUpdateAvailable(true);
                // Show toast notification
                toast.info(
                  <div className="flex items-center gap-3">
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>New version available!</span>
                    <button 
                      onClick={() => {
                        newWorker.postMessage('skipWaiting');
                        window.location.reload();
                      }}
                      className="px-2 py-1 bg-primary text-primary-foreground rounded text-sm"
                    >
                      Update Now
                    </button>
                  </div>,
                  { duration: 10000 }
                );
              }
            });
          }
        });
      });
    }
  }, []);

  const refreshApp = () => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.ready.then((registration) => {
        registration.update();
      });
    }
    // Clear all caches
    if ('caches' in window) {
      caches.keys().then((names) => {
        names.forEach((name) => {
          caches.delete(name);
        });
      });
    }
    window.location.reload();
  };

  return { updateAvailable, refreshApp };
}

export default useAppUpdate;
