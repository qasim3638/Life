import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  Users, Eye, Globe, Monitor, Smartphone, Clock, TrendingUp, 
  ArrowUp, ArrowDown, RefreshCw, MapPin, ExternalLink, Activity,
  Calendar, BarChart3, PieChart, Laptop, Tablet
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const WebsiteAnalytics = () => {
  const [liveVisitors, setLiveVisitors] = useState({ count: 0, visitors: [] });
  const [stats, setStats] = useState(null);
  const [recentVisitors, setRecentVisitors] = useState([]);
  const [topPages, setTopPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('today');
  const [lastUpdated, setLastUpdated] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'Content-Type': 'application/json'
  });

  // Fetch live visitors
  const fetchLiveVisitors = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/website/live`, {
        headers: getAuthHeaders()
      });
      if (response.ok) {
        const data = await response.json();
        setLiveVisitors(data);
        setLastUpdated(new Date());
      }
    } catch (error) {
      console.error('Error fetching live visitors:', error);
    }
  }, []);

  // Fetch stats for selected period
  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/website/stats?period=${period}`, {
        headers: getAuthHeaders()
      });
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  }, [period]);

  // Fetch recent visitors
  const fetchRecentVisitors = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/website/visitors/recent?limit=20`, {
        headers: getAuthHeaders()
      });
      if (response.ok) {
        const data = await response.json();
        setRecentVisitors(data.visitors);
      }
    } catch (error) {
      console.error('Error fetching recent visitors:', error);
    }
  }, []);

  // Fetch top pages
  const fetchTopPages = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/website/pages?limit=20`, {
        headers: getAuthHeaders()
      });
      if (response.ok) {
        const data = await response.json();
        setTopPages(data.pages);
      }
    } catch (error) {
      console.error('Error fetching top pages:', error);
    }
  }, []);

  // Connect to WebSocket for real-time updates
  const connectWebSocket = useCallback(() => {
    const wsUrl = `${API_URL.replace('https://', 'wss://').replace('http://', 'ws://')}/api/website/ws/live`;
    
    try {
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = () => {
        console.log('WebSocket connected');
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'live_update') {
            setLiveVisitors(message.data);
            setLastUpdated(new Date());
          }
        } catch (e) {
          console.error('WebSocket message parse error:', e);
        }
      };
      
      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected');
        // Attempt to reconnect after 5 seconds
        reconnectTimeoutRef.current = setTimeout(connectWebSocket, 5000);
      };
      
      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (error) {
      console.error('WebSocket connection error:', error);
    }
  }, []);

  // Initial data load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([
        fetchLiveVisitors(),
        fetchStats(),
        fetchRecentVisitors(),
        fetchTopPages()
      ]);
      setLoading(false);
    };
    
    loadData();
    
    // Try to connect WebSocket
    connectWebSocket();
    
    // Polling fallback (every 30 seconds)
    const pollInterval = setInterval(fetchLiveVisitors, 30000);
    
    return () => {
      clearInterval(pollInterval);
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [fetchLiveVisitors, fetchStats, fetchRecentVisitors, fetchTopPages, connectWebSocket]);

  // Refresh stats when period changes
  useEffect(() => {
    fetchStats();
  }, [period, fetchStats]);

  const handleRefresh = async () => {
    toast.loading('Refreshing data...');
    await Promise.all([
      fetchLiveVisitors(),
      fetchStats(),
      fetchRecentVisitors(),
      fetchTopPages()
    ]);
    toast.dismiss();
    toast.success('Data refreshed');
  };

  const formatTimeAgo = (dateString) => {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    const seconds = Math.floor((new Date() - date) / 1000);
    
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  const getDeviceIcon = (deviceType) => {
    switch (deviceType?.toLowerCase()) {
      case 'mobile': return <Smartphone className="w-4 h-4" />;
      case 'tablet': return <Tablet className="w-4 h-4" />;
      default: return <Laptop className="w-4 h-4" />;
    }
  };

  const formatPageUrl = (url) => {
    if (!url) return '/';
    try {
      const urlObj = new URL(url);
      return urlObj.pathname || '/';
    } catch {
      return url.replace(/^https?:\/\/[^/]+/, '') || '/';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Website Analytics</h1>
          <p className="text-gray-500 text-sm">
            Real-time visitor tracking and insights
            {lastUpdated && (
              <span className="ml-2 text-xs text-gray-400">
                Last updated: {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </p>
        </div>
        <Button onClick={handleRefresh} variant="outline" size="sm" className="gap-2">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </Button>
      </div>

      {/* Live Visitors Banner */}
      <Card className="bg-gradient-to-r from-green-500 to-emerald-600 text-white border-0">
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-white/20 rounded-full">
                <Activity className="w-8 h-8" />
              </div>
              <div>
                <p className="text-white/80 text-sm font-medium">Live Visitors</p>
                <p className="text-4xl font-bold">{liveVisitors.count}</p>
                <p className="text-white/70 text-xs">Active in last 5 minutes</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 bg-green-300 rounded-full animate-pulse"></span>
              <span className="text-sm">Real-time</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Period Selector */}
      <div className="flex items-center gap-2">
        <Calendar className="w-5 h-5 text-gray-500" />
        <span className="text-sm text-gray-600">Period:</span>
        <div className="flex gap-1">
          {['today', 'yesterday', 'week', 'month', 'year'].map((p) => (
            <Button
              key={p}
              variant={period === p ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setPeriod(p)}
              className="capitalize"
            >
              {p === 'week' ? '7 Days' : p === 'month' ? '30 Days' : p}
            </Button>
          ))}
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Total Page Views</p>
                <p className="text-3xl font-bold text-gray-900">{stats?.total_views?.toLocaleString() || 0}</p>
              </div>
              <div className="p-3 bg-blue-100 rounded-full">
                <Eye className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Unique Visitors</p>
                <p className="text-3xl font-bold text-gray-900">{stats?.unique_visitors?.toLocaleString() || 0}</p>
              </div>
              <div className="p-3 bg-purple-100 rounded-full">
                <Users className="w-6 h-6 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Avg Pages/Visitor</p>
                <p className="text-3xl font-bold text-gray-900">{stats?.avg_views_per_visitor || 0}</p>
              </div>
              <div className="p-3 bg-green-100 rounded-full">
                <TrendingUp className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Top Countries</p>
                <p className="text-xl font-bold text-gray-900">
                  {stats?.top_countries?.[0]?.country || 'N/A'}
                </p>
              </div>
              <div className="p-3 bg-orange-100 rounded-full">
                <Globe className="w-6 h-6 text-orange-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live Visitors List */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Activity className="w-5 h-5 text-green-500" />
              Live Visitors
            </CardTitle>
            <CardDescription>Currently browsing your website</CardDescription>
          </CardHeader>
          <CardContent className="max-h-[400px] overflow-y-auto">
            {liveVisitors.visitors.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No active visitors</p>
            ) : (
              <div className="space-y-3">
                {liveVisitors.visitors.map((visitor, idx) => (
                  <div key={idx} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                    <div className="flex-shrink-0">
                      {getDeviceIcon(visitor.device_type)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {formatPageUrl(visitor.current_page)}
                      </p>
                      <p className="text-xs text-gray-500 flex items-center gap-1">
                        <MapPin className="w-3 h-3" />
                        {visitor.city}, {visitor.country}
                      </p>
                    </div>
                    <div className="flex-shrink-0 text-right">
                      <Badge variant="secondary" className="text-xs">
                        {visitor.pages_viewed} pages
                      </Badge>
                      <p className="text-xs text-gray-400 mt-1">
                        {formatTimeAgo(visitor.last_seen)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Pages */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <BarChart3 className="w-5 h-5 text-blue-500" />
              Most Visited Pages
            </CardTitle>
            <CardDescription>Pages with the highest traffic</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {(stats?.top_pages || topPages)?.slice(0, 10).map((page, idx) => (
                <div 
                  key={idx} 
                  className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center bg-blue-100 text-blue-700 font-bold rounded-full text-sm">
                    {idx + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {page.title || formatPageUrl(page.page_url)}
                    </p>
                    <p className="text-xs text-gray-500 truncate">
                      {formatPageUrl(page.page_url)}
                    </p>
                  </div>
                  <div className="flex items-center gap-4 text-right">
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{page.views?.toLocaleString()}</p>
                      <p className="text-xs text-gray-500">views</p>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-purple-600">{page.unique_visitors?.toLocaleString()}</p>
                      <p className="text-xs text-gray-500">visitors</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Second Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Device Breakdown */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Monitor className="w-5 h-5 text-indigo-500" />
              Devices
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {stats?.devices?.map((device, idx) => {
                const total = stats.devices.reduce((sum, d) => sum + d.count, 0);
                const percentage = total > 0 ? Math.round((device.count / total) * 100) : 0;
                return (
                  <div key={idx} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {getDeviceIcon(device.device_type)}
                        <span className="text-sm font-medium capitalize">{device.device_type || 'Unknown'}</span>
                      </div>
                      <span className="text-sm text-gray-500">{percentage}%</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Top Countries */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Globe className="w-5 h-5 text-green-500" />
              Top Countries
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats?.top_countries?.slice(0, 6).map((country, idx) => (
                <div key={idx} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{getCountryFlag(country.country)}</span>
                    <span className="text-sm font-medium">{country.country}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-semibold">{country.views}</span>
                    <span className="text-xs text-gray-500 ml-1">views</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Top Referrers */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <ExternalLink className="w-5 h-5 text-orange-500" />
              Traffic Sources
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <span className="text-sm font-medium">Direct</span>
                <span className="text-sm text-gray-600">
                  {stats?.total_views - (stats?.top_referrers?.reduce((sum, r) => sum + r.views, 0) || 0) || 0}
                </span>
              </div>
              {stats?.top_referrers?.slice(0, 5).map((ref, idx) => (
                <div key={idx} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                  <span className="text-sm font-medium truncate max-w-[200px]">{ref.referrer}</span>
                  <span className="text-sm text-gray-600">{ref.views}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Visitors Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Users className="w-5 h-5 text-purple-500" />
            Recent Visitors
          </CardTitle>
          <CardDescription>Latest unique visitors to your website</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <th className="pb-3 px-2">Visitor</th>
                  <th className="pb-3 px-2">Location</th>
                  <th className="pb-3 px-2">Device</th>
                  <th className="pb-3 px-2">Last Page</th>
                  <th className="pb-3 px-2">Pages</th>
                  <th className="pb-3 px-2">Source</th>
                  <th className="pb-3 px-2">Last Seen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {recentVisitors.slice(0, 15).map((visitor, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="py-3 px-2">
                      <span className="text-xs font-mono text-gray-500">
                        {visitor.visitor_id?.slice(0, 8)}...
                      </span>
                    </td>
                    <td className="py-3 px-2">
                      <div className="flex items-center gap-1">
                        <span>{getCountryFlag(visitor.country)}</span>
                        <span className="text-sm">{visitor.city}</span>
                      </div>
                    </td>
                    <td className="py-3 px-2">
                      <div className="flex items-center gap-1">
                        {getDeviceIcon(visitor.device_type)}
                        <span className="text-xs text-gray-500">{visitor.browser}</span>
                      </div>
                    </td>
                    <td className="py-3 px-2">
                      <span className="text-sm text-gray-700 truncate max-w-[200px] block">
                        {formatPageUrl(visitor.last_page)}
                      </span>
                    </td>
                    <td className="py-3 px-2">
                      <Badge variant="secondary">{visitor.pages_viewed}</Badge>
                    </td>
                    <td className="py-3 px-2">
                      <span className="text-xs text-gray-500 truncate max-w-[100px] block">
                        {visitor.referrer === 'Direct' ? 'Direct' : (() => {
                          try {
                            return new URL(visitor.referrer).hostname;
                          } catch {
                            return visitor.referrer || 'Direct';
                          }
                        })()}
                      </span>
                    </td>
                    <td className="py-3 px-2">
                      <span className="text-xs text-gray-500">
                        {formatTimeAgo(visitor.last_seen)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

// Helper function to get country flag emoji
const getCountryFlag = (country) => {
  const flags = {
    'United Kingdom': '🇬🇧',
    'United States': '🇺🇸',
    'Germany': '🇩🇪',
    'France': '🇫🇷',
    'Spain': '🇪🇸',
    'Italy': '🇮🇹',
    'Canada': '🇨🇦',
    'Australia': '🇦🇺',
    'India': '🇮🇳',
    'China': '🇨🇳',
    'Japan': '🇯🇵',
    'Netherlands': '🇳🇱',
    'Local': '🏠',
    'Unknown': '🌍'
  };
  return flags[country] || '🌍';
};

export default WebsiteAnalytics;
