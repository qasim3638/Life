import React, { useEffect, useState } from 'react';
import { Button } from './ui/button';
import { Download, X } from 'lucide-react';

export const InstallPWA = () => {
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [showInstall, setShowInstall] = useState(false);

  useEffect(() => {
    const handler = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
      setShowInstall(true);
    };

    window.addEventListener('beforeinstallprompt', handler);

    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;

    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    
    if (outcome === 'accepted') {
      console.log('User accepted the install prompt');
    }
    
    setDeferredPrompt(null);
    setShowInstall(false);
  };

  const handleDismiss = () => {
    setShowInstall(false);
    localStorage.setItem('pwa-dismissed', 'true');
  };

  // Don't show if already dismissed or not available
  if (!showInstall || localStorage.getItem('pwa-dismissed')) {
    return null;
  }

  return (
    <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96 z-50">
      <div className="bg-card border border-border rounded-lg shadow-lg p-4">
        <button
          onClick={handleDismiss}
          className="absolute top-2 right-2 text-muted-foreground hover:text-foreground"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4" />
        </button>
        <div className="flex items-start gap-3 mb-3">
          <div className="p-2 bg-primary rounded-md">
            <Download className="h-5 w-5 text-primary-foreground" />
          </div>
          <div className="flex-1">
            <h3 className="font-heading font-bold tracking-tightest mb-1">Install Tile Station</h3>
            <p className="text-sm text-muted-foreground">
              Install our app for quick access and offline functionality
            </p>
          </div>
        </div>
        <Button 
          onClick={handleInstall} 
          className="w-full bg-accent hover:bg-accent/90"
          data-testid="install-pwa-button"
        >
          <Download className="mr-2 h-4 w-4" /> Install App
        </Button>
      </div>
    </div>
  );
};
