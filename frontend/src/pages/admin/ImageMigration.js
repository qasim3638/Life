import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Progress } from '../../components/ui/progress';
import { Badge } from '../../components/ui/badge';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { 
  Cloud, 
  Upload, 
  CheckCircle2, 
  XCircle, 
  Pause, 
  Play, 
  RefreshCw, 
  Image as ImageIcon,
  AlertTriangle,
  Loader2
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function ImageMigration() {
  const [config, setConfig] = useState(null);
  const [suppliers, setSuppliers] = useState([]);
  const [tilesInfo, setTilesInfo] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = { Authorization: `Bearer ${token}` };

      const [configRes, suppliersRes, statusRes] = await Promise.all([
        fetch(`${API_URL}/api/image-migration/config`, { headers }),
        fetch(`${API_URL}/api/image-migration/suppliers`, { headers }),
        fetch(`${API_URL}/api/image-migration/status`, { headers })
      ]);

      if (configRes.ok) setConfig(await configRes.json());
      if (suppliersRes.ok) {
        const data = await suppliersRes.json();
        setSuppliers(data.suppliers || []);
        setTilesInfo(data.tiles_collection);
      }
      if (statusRes.ok) setStatus(await statusRes.json());
      
      setError(null);
    } catch (err) {
      setError('Failed to load migration data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    
    // Poll for status updates while migration is running
    const interval = setInterval(() => {
      if (status?.is_running) {
        fetchData();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [fetchData, status?.is_running]);

  const startMigration = async (supplierName, collection = 'supplier_products') => {
    setStarting(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/image-migration/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ supplier_name: supplierName, collection })
      });

      if (res.ok) {
        setTimeout(fetchData, 1000);
      } else {
        const data = await res.json();
        setError(data.detail || 'Failed to start migration');
      }
    } catch (err) {
      setError('Failed to start migration');
    } finally {
      setStarting(false);
    }
  };

  const stopMigration = async () => {
    try {
      const token = localStorage.getItem('token');
      await fetch(`${API_URL}/api/image-migration/stop`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      setTimeout(fetchData, 1000);
    } catch (err) {
      setError('Failed to stop migration');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
      </div>
    );
  }

  const progress = status?.progress || {};
  const progressPercent = progress.total_products > 0 
    ? Math.round((progress.processed_products / progress.total_products) * 100) 
    : 0;

  return (
    <div className="space-y-6 p-6" data-testid="image-migration-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Image Migration</h1>
          <p className="text-gray-600">Migrate product images to cloud storage (Cloudflare R2)</p>
        </div>
        <Button onClick={fetchData} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* R2 Configuration Status */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Cloud className="h-5 w-5" />
            Cloud Storage Configuration
          </CardTitle>
        </CardHeader>
        <CardContent>
          {config?.is_configured ? (
            <div className="flex items-center gap-4">
              <Badge className="bg-green-100 text-green-800">
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Configured
              </Badge>
              <span className="text-sm text-gray-600">
                Bucket: <code className="bg-gray-100 px-1 rounded">{config.bucket_name}</code>
              </span>
              <span className="text-sm text-gray-600">
                URL: <code className="bg-gray-100 px-1 rounded">{config.public_url}</code>
              </span>
            </div>
          ) : (
            <Alert variant="destructive">
              <XCircle className="h-4 w-4" />
              <AlertDescription>
                R2 storage not configured. Missing: {config?.missing?.join(', ')}
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Active Migration Status */}
      {status?.is_running && (
        <Card className="border-blue-200 bg-blue-50">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
              Migration In Progress
            </CardTitle>
            <CardDescription>
              Migrating: {status.current_supplier}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Products: {progress.processed_products} / {progress.total_products}</span>
                <span>{progressPercent}%</span>
              </div>
              <Progress value={progressPercent} className="h-2" />
            </div>

            <div className="grid grid-cols-4 gap-4 text-center">
              <div className="bg-white rounded-lg p-3">
                <div className="text-2xl font-bold text-green-600">{progress.uploaded_images}</div>
                <div className="text-xs text-gray-500">Uploaded</div>
              </div>
              <div className="bg-white rounded-lg p-3">
                <div className="text-2xl font-bold text-red-600">{progress.failed_images}</div>
                <div className="text-xs text-gray-500">Failed</div>
              </div>
              <div className="bg-white rounded-lg p-3">
                <div className="text-2xl font-bold text-gray-600">{progress.skipped_images}</div>
                <div className="text-xs text-gray-500">Skipped</div>
              </div>
              <div className="bg-white rounded-lg p-3">
                <div className="text-2xl font-bold text-blue-600">{progress.total_images}</div>
                <div className="text-xs text-gray-500">Total</div>
              </div>
            </div>

            <Button onClick={stopMigration} variant="destructive" className="w-full">
              <Pause className="h-4 w-4 mr-2" />
              Stop Migration
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Tiles Collection (Published Products) */}
      {tilesInfo && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <ImageIcon className="h-5 w-5" />
              Published Products (Tiles Collection)
            </CardTitle>
            <CardDescription>
              Images displayed on your live website
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold">{tilesInfo.total}</div>
                  <div className="text-xs text-gray-500">Total Products</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">{tilesInfo.migrated}</div>
                  <div className="text-xs text-gray-500">Migrated</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-amber-600">{tilesInfo.pending}</div>
                  <div className="text-xs text-gray-500">Pending</div>
                </div>
              </div>
              <Button 
                onClick={() => startMigration('all', 'tiles')}
                disabled={status?.is_running || starting || tilesInfo.pending === 0}
              >
                {starting ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Upload className="h-4 w-4 mr-2" />
                )}
                Migrate Tiles Images
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Supplier Products */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Supplier Products</CardTitle>
              <CardDescription>
                Images in staging (supplier_products collection)
              </CardDescription>
            </div>
            <Button 
              onClick={() => startMigration('all', 'supplier_products')}
              disabled={status?.is_running || starting}
              variant="outline"
            >
              {starting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Play className="h-4 w-4 mr-2" />
              )}
              Migrate All
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {suppliers.length === 0 ? (
              <p className="text-gray-500 text-center py-4">No suppliers with images found</p>
            ) : (
              suppliers.map((supplier) => (
                <div 
                  key={supplier.supplier_name} 
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center gap-4">
                    <div>
                      <div className="font-medium">{supplier.supplier_name}</div>
                      <div className="text-xs text-gray-500">
                        {supplier.product_count} products • {supplier.image_count} images
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      {supplier.pending_count === 0 ? (
                        <Badge className="bg-green-100 text-green-800">
                          <CheckCircle2 className="h-3 w-3 mr-1" />
                          Complete
                        </Badge>
                      ) : (
                        <Badge variant="secondary">
                          {supplier.pending_count} pending
                        </Badge>
                      )}
                    </div>
                    <Button 
                      size="sm"
                      onClick={() => startMigration(supplier.supplier_name)}
                      disabled={status?.is_running || starting || supplier.pending_count === 0}
                    >
                      <Upload className="h-3 w-3 mr-1" />
                      Migrate
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Recent Errors */}
      {status?.recent_errors?.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg text-red-600">Recent Errors</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {status.recent_errors.map((err, idx) => (
                <div key={idx} className="text-sm p-2 bg-red-50 rounded border border-red-100">
                  <span className="font-medium">{err.product}:</span> {err.error}
                  {err.url && (
                    <div className="text-xs text-gray-500 truncate mt-1">{err.url}</div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
