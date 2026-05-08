import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { 
  RefreshCw, Play, Pause, Clock, CheckCircle, XCircle, 
  AlertTriangle, Settings, Calendar, Database, ArrowLeft,
  Loader2, Download, Eye
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const SCRAPERS = [
  { 
    id: 'splendour_tiles', 
    name: 'Splendour Tiles', 
    website: 'splendourtiles.co.uk',
    color: 'bg-teal-500',
    icon: '🏪'
  },
  { 
    id: 'wallcano_tiles', 
    name: 'Wallcano', 
    website: 'wallcanotiles.com',
    color: 'bg-orange-500',
    icon: '🧱'
  },
  { 
    id: 'ceramica_impex', 
    name: 'Ceramica Impex', 
    website: 'portal.ceramicaimpex.co.uk',
    color: 'bg-purple-500',
    icon: '🎨'
  }
];

export default function ScrapingPortal() {
  const navigate = useNavigate();
  const [schedules, setSchedules] = useState([
    { supplier_id: 'splendour_tiles', enabled: true, frequency: 'daily', time: '03:00' },
    { supplier_id: 'wallcano_tiles', enabled: true, frequency: 'daily', time: '02:30' },
    { supplier_id: 'ceramica_impex', enabled: true, frequency: 'daily', time: '02:00' }
  ]);
  const [syncLogs, setSyncLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [runningScrapers, setRunningScrapers] = useState({});
  const [productStats, setProductStats] = useState({});

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      // Fetch schedules - handle errors gracefully with timeout
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        
        const schedulesRes = await api.get('/import/schedules', { signal: controller.signal });
        clearTimeout(timeoutId);
        
        console.log('Schedules response:', schedulesRes);
        if (schedulesRes.data) {
          setSchedules(Array.isArray(schedulesRes.data) ? schedulesRes.data : []);
        }
      } catch (schedErr) {
        console.error('Error fetching schedules:', schedErr);
        // Keep default schedules if API fails
      }
      
      // Fetch sync logs (public endpoint)
      try {
        const logsRes = await fetch(`${API_URL}/api/supplier-sync/logs?limit=20`);
        if (logsRes.ok) {
          const logs = await logsRes.json();
          setSyncLogs(Array.isArray(logs) ? logs : []);
        }
      } catch (logsErr) {
        console.error('Error fetching logs:', logsErr);
      }
      
      // Fetch product stats
      try {
        const statsRes = await fetch(`${API_URL}/api/supplier-sync/stats`);
        if (statsRes.ok) {
          const stats = await statsRes.json();
          setProductStats(stats);
        }
      } catch (statsErr) {
        console.error('Error fetching stats:', statsErr);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  };

  const [jobStatuses, setJobStatuses] = useState({});
  const pollIntervalsRef = useRef({});

  const handleManualRun = async (supplierId) => {
    try {
      setRunningScrapers(prev => ({ ...prev, [supplierId]: true }));
      toast.info(`Starting ${supplierId} scraper...`);
      
      // Map supplier IDs to the new supplier-sync endpoints
      const endpointMap = {
        'splendour_tiles': '/supplier-sync/splendour/scrape-portal',
        'wallcano_tiles': '/supplier-sync/wallcano/scrape-dealer-portal',
        'ceramica_impex': '/supplier-sync/ceramica-impex/scrape-portal'
      };
      
      const endpoint = endpointMap[supplierId];
      if (!endpoint) {
        toast.error(`Unknown supplier: ${supplierId}`);
        setRunningScrapers(prev => ({ ...prev, [supplierId]: false }));
        return;
      }
      
      const response = await api.post(endpoint);
      
      if (response.data && response.data.job_id) {
        const jobId = response.data.job_id;
        toast.success(`${supplierId} scraper started successfully`);
        
        // Start polling for job status using new endpoints
        startPollingJobStatus(supplierId, jobId);
      }
    } catch (error) {
      console.error('Error running scraper:', error);
      toast.error(`Failed to start ${supplierId} scraper: ${error.message}`);
      setRunningScrapers(prev => ({ ...prev, [supplierId]: false }));
    }
  };

  const startPollingJobStatus = (supplierId, jobId) => {
    // Clear any existing interval for this scraper
    if (pollIntervalsRef.current[supplierId]) {
      clearInterval(pollIntervalsRef.current[supplierId]);
    }
    
    // Map supplier IDs to the new status endpoints
    const statusEndpointMap = {
      'splendour_tiles': `/supplier-sync/splendour/scrape-status/${jobId}`,
      'wallcano_tiles': `/supplier-sync/wallcano/scrape-status/${jobId}`,
      'ceramica_impex': `/supplier-sync/ceramica-impex/scrape-status/${jobId}`
    };
    
    const statusEndpoint = statusEndpointMap[supplierId];
    
    // Poll every 3 seconds
    const pollInterval = setInterval(async () => {
      try {
        const response = await api.get(statusEndpoint);
        const status = response.data;
        
        // Update job status - map new format to expected format
        setJobStatuses(prev => ({ 
          ...prev, 
          [supplierId]: {
            ...status,
            products_imported: status.products_synced || 0,
            products_updated: status.products_found || 0
          }
        }));
        
        // Check if job completed
        if (status.status === 'completed' || status.status === 'failed' || status.status === 'timeout') {
          clearInterval(pollIntervalsRef.current[supplierId]);
          delete pollIntervalsRef.current[supplierId];
          setRunningScrapers(prev => ({ ...prev, [supplierId]: false }));
          
          if (status.status === 'completed') {
            toast.success(`${supplierId}: Synced ${status.products_synced || 0} products to staging`);
          } else {
            toast.error(`${supplierId} failed: ${status.errors?.join(', ') || 'Unknown error'}`);
          }
          
          // Refresh data to show updated counts
          fetchData();
        }
      } catch (error) {
        console.error('Error polling job status:', error);
        // Don't clear on network error - keep trying
      }
    }, 3000);
    
    pollIntervalsRef.current[supplierId] = pollInterval;
  };

  // Cleanup intervals on unmount
  useEffect(() => {
    return () => {
      Object.values(pollIntervalsRef.current).forEach(interval => clearInterval(interval));
    };
  }, []);

  const handleToggleSchedule = async (supplierId, currentEnabled) => {
    try {
      await api.patch(`/import/schedules/${supplierId}`, {
        enabled: !currentEnabled
      });
      toast.success(`Schedule ${!currentEnabled ? 'enabled' : 'disabled'}`);
      fetchData();
    } catch (error) {
      console.error('Error toggling schedule:', error);
      toast.error('Failed to update schedule');
    }
  };

  const getScheduleForScraper = (scraperId) => {
    return schedules.find(s => s.supplier === scraperId);
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'error':
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'running':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      default:
        return <Clock className="w-5 h-5 text-gray-400" />;
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getSupplierProductCount = (scraperId) => {
    const mapping = {
      'splendour_tiles': 'Splendour',
      'wallcano_tiles': 'Wallcano',
      'ceramica_impex': 'Ceramica Impex'
    };
    return productStats[mapping[scraperId]] || 0;
  };

  return (
    <div className="p-6 space-y-6" data-testid="scraping-portal">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate('/admin/products-hub')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Database className="w-6 h-6" />
              Scraping Portal
            </h1>
            <p className="text-gray-500">Manage automated supplier product syncing</p>
          </div>
        </div>
        <Button onClick={fetchData} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Scraper Cards */}
      <div className="grid md:grid-cols-3 gap-6">
        {SCRAPERS.map(scraper => {
          const schedule = getScheduleForScraper(scraper.id);
          const isRunning = runningScrapers[scraper.id];
          const productCount = getSupplierProductCount(scraper.id);
          
          return (
            <Card key={scraper.id} className="overflow-hidden">
              <div className={`h-2 ${scraper.color}`} />
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">{scraper.icon}</span>
                    <div>
                      <h3 className="font-semibold">{scraper.name}</h3>
                      <p className="text-xs text-gray-500 font-normal">{scraper.website}</p>
                    </div>
                  </div>
                  {schedule?.enabled ? (
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full">Active</span>
                  ) : (
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full">Paused</span>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Live Progress when Running */}
                {isRunning && jobStatuses[scraper.id] && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 space-y-2">
                    <div className="flex items-center gap-2">
                      <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                      <span className="text-sm font-medium text-blue-700">
                        {jobStatuses[scraper.id].progress?.message || 'Running...'}
                      </span>
                    </div>
                    <div className="text-xs text-blue-600 space-y-1">
                      <p>Products found: {jobStatuses[scraper.id].products_found || 0}</p>
                      {jobStatuses[scraper.id].progress?.current > 0 && (
                        <p>Progress: {jobStatuses[scraper.id].progress.current} / {jobStatuses[scraper.id].progress.total || '?'}</p>
                      )}
                    </div>
                  </div>
                )}

                {/* Stats */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-gray-900">{productCount}</p>
                    <p className="text-xs text-gray-500">Products</p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <p className="text-lg font-semibold text-gray-900">{schedule?.time || '--:--'}</p>
                    <p className="text-xs text-gray-500">Scheduled</p>
                  </div>
                </div>

                {/* Last Run Info */}
                <div className="border-t pt-3">
                  <div className="flex items-center gap-2 text-sm">
                    {getStatusIcon(schedule?.last_run_status)}
                    <span className="text-gray-600">
                      Last run: {formatDate(schedule?.last_run)}
                    </span>
                  </div>
                  {schedule?.last_run_status === 'success' && schedule?.last_run_products_imported > 0 && (
                    <p className="text-xs text-green-600 mt-1 ml-7">
                      +{schedule.last_run_products_imported} new products
                    </p>
                  )}
                  {schedule?.last_run_error && (
                    <p className="text-xs text-red-600 mt-1 ml-7 line-clamp-2">
                      {schedule.last_run_error}
                    </p>
                  )}
                </div>

                {/* Actions */}
                <div className="flex gap-2 pt-2">
                  <Button 
                    className="flex-1" 
                    onClick={() => handleManualRun(scraper.id)}
                    disabled={isRunning}
                  >
                    {isRunning ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Running...
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4 mr-2" />
                        Run Now
                      </>
                    )}
                  </Button>
                  <Button 
                    variant="outline"
                    onClick={() => handleToggleSchedule(scraper.id, schedule?.enabled)}
                  >
                    {schedule?.enabled ? (
                      <Pause className="w-4 h-4" />
                    ) : (
                      <Play className="w-4 h-4" />
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Schedule Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="w-5 h-5" />
            Overnight Schedule
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {SCRAPERS.map(scraper => {
              const schedule = getScheduleForScraper(scraper.id);
              return (
                <div key={scraper.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${schedule?.enabled ? 'bg-green-500' : 'bg-gray-300'}`} />
                    <span className="font-medium">{scraper.name}</span>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-gray-600">
                    <span className="flex items-center gap-1">
                      <Clock className="w-4 h-4" />
                      {schedule?.time || '--:--'} AM
                    </span>
                    <span>Daily</span>
                    <span className={schedule?.enabled ? 'text-green-600' : 'text-gray-400'}>
                      {schedule?.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-sm text-gray-500 mt-4">
            Scrapers run automatically overnight to fetch the latest products and stock levels from supplier portals.
          </p>
        </CardContent>
      </Card>

      {/* Recent Sync Logs */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Recent Sync Activity
          </CardTitle>
        </CardHeader>
        <CardContent>
          {syncLogs.length > 0 ? (
            <div className="space-y-2">
              {syncLogs.slice(0, 10).map((log, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center gap-3">
                    {getStatusIcon(log.status)}
                    <div>
                      <p className="font-medium">{log.supplier}</p>
                      <p className="text-xs text-gray-500">{log.source || 'Automated Scraper'}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium">{log.products_synced || log.synced || 0} products</p>
                    <p className="text-xs text-gray-500">{formatDate(log.timestamp)}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">No sync activity yet</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
