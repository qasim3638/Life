import React, { useState, useRef, useEffect } from 'react';
import { Camera, Search, X, Package, AlertCircle, CheckCircle, Barcode } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const BarcodeScanner = ({ onProductScanned, showroomId }) => {
  const [manualCode, setManualCode] = useState('');
  const [scanning, setScanning] = useState(false);
  const [lastScanned, setLastScanned] = useState(null);
  const [searchResults, setSearchResults] = useState([]);
  const inputRef = useRef(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  // Auto-focus input for USB scanner
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  // Handle keyboard input (USB scanner typically sends keystrokes followed by Enter)
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && manualCode.trim()) {
      handleLookup(manualCode.trim());
    }
  };

  const handleLookup = async (code) => {
    if (!code) return;
    
    try {
      const url = showroomId 
        ? `${API_URL}/api/barcode/lookup/${encodeURIComponent(code)}?showroom_id=${showroomId}`
        : `${API_URL}/api/barcode/lookup/${encodeURIComponent(code)}`;
      
      const res = await fetch(url);
      
      if (res.ok) {
        const data = await res.json();
        setLastScanned(data);
        setManualCode('');
        toast.success(`Found: ${data.product.name}`);
        
        if (onProductScanned) {
          onProductScanned(data.product);
        }
      } else {
        const error = await res.json();
        toast.error(error.detail?.message || 'Product not found');
        setLastScanned(null);
      }
    } catch (e) {
      console.error('Lookup error:', e);
      toast.error('Failed to lookup product');
    }
  };

  const handleSearch = async (query) => {
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }
    
    try {
      const res = await fetch(`${API_URL}/api/barcode/search?q=${encodeURIComponent(query)}&limit=5`);
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.results || []);
      }
    } catch (e) {
      console.error('Search error:', e);
    }
  };

  const startCameraScanning = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }
      });
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        streamRef.current = stream;
        setScanning(true);
        toast.info('Camera started. Point at barcode to scan.');
      }
    } catch (e) {
      console.error('Camera error:', e);
      toast.error('Could not access camera. Please allow camera permissions or use manual entry.');
    }
  };

  const stopCameraScanning = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setScanning(false);
  };

  return (
    <div className="space-y-4" data-testid="barcode-scanner">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2">
            <Barcode className="h-5 w-5" />
            Barcode Scanner
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Manual Entry / USB Scanner Input */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                ref={inputRef}
                type="text"
                placeholder="Scan barcode or type SKU..."
                value={manualCode}
                onChange={(e) => {
                  setManualCode(e.target.value);
                  handleSearch(e.target.value);
                }}
                onKeyDown={handleKeyDown}
                className="pl-10"
                data-testid="barcode-input"
              />
              
              {/* Search Results Dropdown */}
              {searchResults.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-60 overflow-auto">
                  {searchResults.map((product, idx) => (
                    <button
                      key={idx}
                      className="w-full px-4 py-2 text-left hover:bg-gray-50 border-b last:border-0"
                      onClick={() => {
                        handleLookup(product.sku);
                        setSearchResults([]);
                      }}
                    >
                      <p className="font-medium text-sm">{product.name}</p>
                      <p className="text-xs text-gray-500">SKU: {product.sku}</p>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <Button onClick={() => handleLookup(manualCode)} disabled={!manualCode.trim()}>
              Lookup
            </Button>
          </div>

          {/* Camera Scanner */}
          <div className="flex gap-2">
            {!scanning ? (
              <Button variant="outline" onClick={startCameraScanning} className="flex-1">
                <Camera className="h-4 w-4 mr-2" />
                Use Camera Scanner
              </Button>
            ) : (
              <Button variant="outline" onClick={stopCameraScanning} className="flex-1">
                <X className="h-4 w-4 mr-2" />
                Stop Camera
              </Button>
            )}
          </div>

          {/* Camera Preview */}
          {scanning && (
            <div className="relative rounded-lg overflow-hidden bg-black">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                className="w-full h-48 object-cover"
              />
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-48 h-24 border-2 border-green-500 rounded-lg"></div>
              </div>
              <p className="absolute bottom-2 left-0 right-0 text-center text-white text-sm bg-black/50 py-1">
                Position barcode within the frame
              </p>
            </div>
          )}

          {/* Last Scanned Result */}
          {lastScanned && (
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-start gap-3">
                <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                <div className="flex-1">
                  <h4 className="font-medium text-green-900">{lastScanned.product.name}</h4>
                  <div className="text-sm text-green-700 space-y-1 mt-1">
                    <p>SKU: {lastScanned.product.sku}</p>
                    <p>Stock: {lastScanned.product.stock || 0}</p>
                    <p>Price: £{lastScanned.product.price?.toFixed(2)}</p>
                    <p className="text-xs text-green-600">Matched by: {lastScanned.matched_by}</p>
                  </div>
                </div>
                <Button 
                  size="sm" 
                  onClick={() => onProductScanned && onProductScanned(lastScanned.product)}
                >
                  Add to Order
                </Button>
              </div>
            </div>
          )}

          {/* Tips */}
          <div className="text-xs text-gray-500 bg-gray-50 p-3 rounded-lg">
            <p className="font-medium mb-1">Tips:</p>
            <ul className="list-disc list-inside space-y-0.5">
              <li>USB barcode scanners work automatically - just scan</li>
              <li>Type SKU/barcode manually and press Enter</li>
              <li>Use camera to scan barcodes from your phone</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default BarcodeScanner;
