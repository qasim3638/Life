import React, { useState, useEffect } from 'react';
import { 
  Upload, 
  Play, 
  X, 
  RefreshCw, 
  Clock, 
  Package,
  Eye,
  Save,
  Calendar,
  Trash2,
  Power,
  PlayCircle,
  Settings
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ProductImport = () => {
  const [jobs, setJobs] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [isStarting, setIsStarting] = useState(false);
  const [showCredentialsModal, setShowCredentialsModal] = useState(false);
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [activeTab, setActiveTab] = useState('jobs');
  const [credentials, setCredentials] = useState({
    supplier: 'splendour_tiles',
    email: '',
    password: '',
    limit: 50,
    dryRun: true
  });
  const [scheduleForm, setScheduleForm] = useState({
    supplier: 'splendour_tiles',
    email: '',
    password: '',
    frequency: 'daily',
    time: '03:00',
    enabled: true
  });
  const [previewProducts, setPreviewProducts] = useState([]);
  const [schedulerStatus, setSchedulerStatus] = useState(null);

  const token = localStorage.getItem('token');

  useEffect(() => {
    fetchJobs();
    fetchSchedules();
    fetchSchedulerStatus();
    const interval = setInterval(() => {
      fetchJobs();
      fetchSchedules();
    }, 10000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchJobs = async () => {
    try {
      const res = await fetch(`${API_URL}/api/import/jobs`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setJobs(data);
      }
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
    }
  };

  const fetchSchedules = async () => {
    try {
      const res = await fetch(`${API_URL}/api/import/schedules`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSchedules(data);
      }
    } catch (err) {
      console.error('Failed to fetch schedules:', err);
    }
  };

  const fetchSchedulerStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/import/scheduler/status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSchedulerStatus(data);
      }
    } catch (err) {
      console.error('Failed to fetch scheduler status:', err);
    }
  };

  const startImport = async () => {
    setIsStarting(true);
    try {
      const res = await fetch(`${API_URL}/api/import/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          supplier: credentials.supplier,
          credentials: {
            email: credentials.email,
            password: credentials.password
          },
          limit: credentials.limit || null,
          dry_run: credentials.dryRun
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        setShowCredentialsModal(false);
        fetchJobs();
        pollJobStatus(data.job_id);
      } else {
        const error = await res.json();
        alert('Failed to start import: ' + (error.detail || 'Unknown error'));
      }
    } catch (err) {
      console.error('Failed to start import:', err);
      alert('Failed to start import');
    }
    setIsStarting(false);
  };

  const createSchedule = async () => {
    try {
      const res = await fetch(`${API_URL}/api/import/schedule`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          supplier: scheduleForm.supplier,
          credentials: {
            email: scheduleForm.email,
            password: scheduleForm.password
          },
          frequency: scheduleForm.frequency,
          time: scheduleForm.time,
          enabled: scheduleForm.enabled
        })
      });
      
      if (res.ok) {
        setShowScheduleModal(false);
        fetchSchedules();
        fetchSchedulerStatus();
        alert('Schedule created successfully!');
      } else {
        const error = await res.json();
        alert('Failed to create schedule: ' + (error.detail || 'Unknown error'));
      }
    } catch (err) {
      console.error('Failed to create schedule:', err);
      alert('Failed to create schedule');
    }
  };

  const toggleSchedule = async (scheduleId, enabled) => {
    try {
      const res = await fetch(`${API_URL}/api/import/schedules/${scheduleId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ enabled: !enabled })
      });
      
      if (res.ok) {
        fetchSchedules();
        fetchSchedulerStatus();
      }
    } catch (err) {
      console.error('Failed to toggle schedule:', err);
    }
  };

  const deleteSchedule = async (scheduleId) => {
    if (!window.confirm('Are you sure you want to delete this schedule?')) return;
    
    try {
      const res = await fetch(`${API_URL}/api/import/schedules/${scheduleId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.ok) {
        fetchSchedules();
        fetchSchedulerStatus();
      }
    } catch (err) {
      console.error('Failed to delete schedule:', err);
    }
  };

  const runScheduleNow = async (scheduleId) => {
    try {
      const res = await fetch(`${API_URL}/api/import/schedules/${scheduleId}/run-now`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.ok) {
        const data = await res.json();
        alert(`Import started! Job ID: ${data.job_id}`);
        fetchJobs();
        setActiveTab('jobs');
      } else {
        const error = await res.json();
        alert('Failed to run: ' + (error.detail || 'Unknown error'));
      }
    } catch (err) {
      console.error('Failed to run schedule:', err);
    }
  };

  const pollJobStatus = async (jobId) => {
    const checkStatus = async () => {
      try {
        const res = await fetch(`${API_URL}/api/import/status/${jobId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const job = await res.json();
          setJobs(prev => {
            const idx = prev.findIndex(j => j.id === jobId);
            if (idx >= 0) {
              const updated = [...prev];
              updated[idx] = job;
              return updated;
            }
            return [job, ...prev];
          });
          
          if (job.status === 'running') {
            setTimeout(checkStatus, 2000);
          } else if (job.status === 'completed' && job.dry_run) {
            setSelectedJob(job);
            setPreviewProducts(job.preview_products || []);
          }
        }
      } catch (err) {
        console.error('Failed to check job status:', err);
      }
    };
    checkStatus();
  };

  const confirmImport = async (jobId) => {
    try {
      const res = await fetch(`${API_URL}/api/import/confirm/${jobId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        alert('Products are being saved!');
        fetchJobs();
      } else {
        const error = await res.json();
        alert('Failed to confirm: ' + (error.detail || 'Unknown error'));
      }
    } catch (err) {
      alert('Failed to confirm import');
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      running: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      cancelled: 'bg-gray-100 text-gray-800'
    };
    return (
      <span className={`px-2 py-1 text-xs rounded-full font-medium ${styles[status] || 'bg-gray-100'}`}>
        {status}
      </span>
    );
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('en-GB');
  };

  const getFrequencyLabel = (frequency) => {
    const labels = {
      daily: 'Daily',
      weekly: 'Weekly (Monday)',
      monthly: 'Monthly (1st)'
    };
    return labels[frequency] || frequency;
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Product Import</h1>
          <p className="text-gray-500">Import products from supplier portals</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowScheduleModal(true)}
            className="flex items-center gap-2 px-4 py-2 border border-teal-600 text-teal-600 rounded-lg hover:bg-teal-50 transition-colors"
          >
            <Calendar className="w-5 h-5" />
            Schedule Import
          </button>
          <button
            onClick={() => setShowCredentialsModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition-colors"
          >
            <Upload className="w-5 h-5" />
            Start Import
          </button>
        </div>
      </div>

      {/* Scheduler Status */}
      {schedulerStatus && (
        <div className="mb-4 p-3 bg-gray-50 rounded-lg flex items-center gap-3 text-sm">
          <div className={`w-2 h-2 rounded-full ${schedulerStatus.running ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-gray-600">
            Scheduler: {schedulerStatus.running ? 'Running' : 'Stopped'} 
            {schedulerStatus.job_count > 0 && ` • ${schedulerStatus.job_count} active job(s)`}
          </span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b mb-4">
        <button
          onClick={() => setActiveTab('jobs')}
          className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'jobs' 
              ? 'border-teal-600 text-teal-600' 
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          Import Jobs
        </button>
        <button
          onClick={() => setActiveTab('schedules')}
          className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'schedules' 
              ? 'border-teal-600 text-teal-600' 
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          Scheduled Imports ({schedules.length})
        </button>
      </div>

      {/* Import Jobs Tab */}
      {activeTab === 'jobs' && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="p-4 border-b bg-gray-50">
            <h2 className="font-semibold text-gray-900">Import Jobs</h2>
          </div>
          
          {jobs.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <Package className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p>No import jobs yet. Start your first import above.</p>
            </div>
          ) : (
            <div className="divide-y">
              {jobs.map(job => (
                <div key={job.id} className="p-4 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-sm text-gray-600">{job.id}</span>
                        {getStatusBadge(job.status)}
                        {job.dry_run && (
                          <span className="px-2 py-1 text-xs rounded-full bg-yellow-100 text-yellow-800">
                            Dry Run
                          </span>
                        )}
                        {job.scheduled && (
                          <span className="px-2 py-1 text-xs rounded-full bg-purple-100 text-purple-800">
                            Scheduled
                          </span>
                        )}
                      </div>
                      <div className="text-sm text-gray-500 mt-1">
                        {job.supplier} • Started {formatDate(job.started_at)}
                      </div>
                      {job.status === 'running' && (
                        <div className="mt-2">
                          <div className="flex items-center gap-2 text-sm text-blue-600">
                            <RefreshCw className="w-4 h-4 animate-spin" />
                            {job.progress?.message || 'Processing...'}
                          </div>
                          <div className="w-48 bg-gray-200 rounded-full h-2 mt-2">
                            <div 
                              className="bg-blue-600 h-2 rounded-full transition-all"
                              style={{ width: `${job.progress?.total ? (job.progress.current / job.progress.total) * 100 : 0}%` }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <div className="text-sm font-medium">
                          {job.products_found} found
                        </div>
                        {job.products_imported > 0 && (
                          <div className="text-sm text-green-600">
                            {job.products_imported} imported
                          </div>
                        )}
                        {job.products_updated > 0 && (
                          <div className="text-sm text-blue-600">
                            {job.products_updated} updated
                          </div>
                        )}
                      </div>
                      
                      {job.status === 'completed' && job.dry_run && job.preview_products?.length > 0 && (
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              setSelectedJob(job);
                              setPreviewProducts(job.preview_products);
                            }}
                            className="flex items-center gap-1 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50"
                          >
                            <Eye className="w-4 h-4" />
                            Preview
                          </button>
                          <button
                            onClick={() => confirmImport(job.id)}
                            className="flex items-center gap-1 px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700"
                          >
                            <Save className="w-4 h-4" />
                            Save All
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Schedules Tab */}
      {activeTab === 'schedules' && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="p-4 border-b bg-gray-50">
            <h2 className="font-semibold text-gray-900">Scheduled Imports</h2>
          </div>
          
          {schedules.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <Calendar className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p>No scheduled imports. Create one to auto-sync products.</p>
            </div>
          ) : (
            <div className="divide-y">
              {schedules.map(schedule => (
                <div key={schedule.id} className="p-4 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-3">
                        <span className="font-medium text-gray-900 capitalize">
                          {schedule.supplier?.replace('_', ' ')}
                        </span>
                        <span className={`px-2 py-1 text-xs rounded-full font-medium ${
                          schedule.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                        }`}>
                          {schedule.enabled ? 'Active' : 'Disabled'}
                        </span>
                      </div>
                      <div className="text-sm text-gray-500 mt-1">
                        {getFrequencyLabel(schedule.frequency)} at {schedule.time} UTC
                      </div>
                      {schedule.next_run && schedule.enabled && (
                        <div className="text-sm text-blue-600 mt-1 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          Next run: {formatDate(schedule.next_run)}
                        </div>
                      )}
                      {schedule.last_run && (
                        <div className={`text-sm mt-1 ${
                          schedule.last_run_status === 'completed' ? 'text-green-600' : 'text-red-600'
                        }`}>
                          Last run: {formatDate(schedule.last_run)} 
                          {schedule.last_run_status === 'completed' && schedule.last_run_products_imported > 0 && (
                            <span className="ml-1">
                              ({schedule.last_run_products_imported} new, {schedule.last_run_products_updated || 0} updated)
                            </span>
                          )}
                          {schedule.last_run_error && (
                            <span className="ml-1">- {schedule.last_run_error}</span>
                          )}
                        </div>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => runScheduleNow(schedule.id)}
                        className="p-2 text-gray-500 hover:text-teal-600 hover:bg-teal-50 rounded-lg transition-colors"
                        title="Run now"
                      >
                        <PlayCircle className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => toggleSchedule(schedule.id, schedule.enabled)}
                        className={`p-2 rounded-lg transition-colors ${
                          schedule.enabled 
                            ? 'text-green-600 hover:bg-green-50' 
                            : 'text-gray-400 hover:bg-gray-100'
                        }`}
                        title={schedule.enabled ? 'Disable' : 'Enable'}
                      >
                        <Power className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => deleteSchedule(schedule.id)}
                        className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Preview Modal */}
      {selectedJob && previewProducts.length > 0 && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-4xl max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b flex items-center justify-between">
              <h3 className="font-semibold text-lg">
                Preview: {previewProducts.length} Products
              </h3>
              <button onClick={() => setSelectedJob(null)} className="text-gray-500 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="overflow-auto max-h-[60vh]">
              <table className="w-full">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Product</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">SKU</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Size</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Stock</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {previewProducts.map((product, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          {product.images?.[0] ? (
                            <img 
                              src={product.images[0].startsWith('http') ? product.images[0] : `https://www.splendourtiles.co.uk${product.images[0]}`}
                              alt={product.name}
                              className="w-12 h-12 object-cover rounded"
                            />
                          ) : (
                            <div className="w-12 h-12 bg-gray-100 rounded flex items-center justify-center">
                              <Package className="w-6 h-6 text-gray-400" />
                            </div>
                          )}
                          <div>
                            <div className="font-medium text-gray-900 text-sm">{product.name}</div>
                            <div className="text-xs text-gray-500">{product.range}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{product.sku || '-'}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{product.size || '-'}</td>
                      <td className="px-4 py-3 text-sm">
                        {product.stock_sqm ? (
                          <span className="text-green-600">{product.stock_sqm} m²</span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{product.category}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="p-4 border-t bg-gray-50 flex justify-between">
              <button
                onClick={() => setSelectedJob(null)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-100"
              >
                Close
              </button>
              <button
                onClick={() => {
                  confirmImport(selectedJob.id);
                  setSelectedJob(null);
                }}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
              >
                <Save className="w-5 h-5" />
                Import {previewProducts.length} Products
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Credentials Modal */}
      {showCredentialsModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-md">
            <div className="p-4 border-b">
              <h3 className="font-semibold text-lg">Import Products</h3>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Supplier
                </label>
                <select
                  value={credentials.supplier}
                  onChange={e => setCredentials({...credentials, supplier: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-teal-500/20"
                >
                  <option value="splendour_tiles">Splendour Tiles</option>
                  <option value="wix">Tile Station Wix (One-time Import)</option>
                </select>
              </div>
              
              {credentials.supplier !== 'wix' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Email / Username
                    </label>
                    <input
                      type="email"
                      value={credentials.email}
                      onChange={e => setCredentials({...credentials, email: e.target.value})}
                      placeholder="your@email.com"
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-teal-500/20"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Password
                    </label>
                    <input
                      type="password"
                      value={credentials.password}
                      onChange={e => setCredentials({...credentials, password: e.target.value})}
                      placeholder="••••••••"
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-teal-500/20"
                    />
                  </div>
                </>
              )}
              
              {credentials.supplier === 'wix' && (
                <div className="p-3 bg-blue-50 text-blue-800 text-sm rounded-lg">
                  <strong>Note:</strong> This is a one-time import from your existing Wix website (tilestation.co.uk). 
                  No credentials required - the public product pages will be scraped. This data will not be auto-synced.
                </div>
              )}
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Limit (optional)
                </label>
                <input
                  type="number"
                  value={credentials.limit}
                  onChange={e => setCredentials({...credentials, limit: parseInt(e.target.value) || null})}
                  placeholder="Leave empty for all products"
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-teal-500/20"
                />
              </div>
              
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="dryRun"
                  checked={credentials.dryRun}
                  onChange={e => setCredentials({...credentials, dryRun: e.target.checked})}
                  className="w-4 h-4 text-teal-600 rounded"
                />
                <label htmlFor="dryRun" className="text-sm text-gray-700">
                  Preview only (don&apos;t save products)
                </label>
              </div>
            </div>
            <div className="p-4 border-t bg-gray-50 flex justify-end gap-3">
              <button
                onClick={() => setShowCredentialsModal(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={startImport}
                disabled={isStarting || (credentials.supplier !== 'wix' && (!credentials.email || !credentials.password))}
                className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 disabled:opacity-50"
              >
                {isStarting ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    Starting...
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    Start Import
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Schedule Modal */}
      {showScheduleModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-md">
            <div className="p-4 border-b">
              <h3 className="font-semibold text-lg">Schedule Automatic Import</h3>
              <p className="text-sm text-gray-500 mt-1">
                Set up automatic product sync from your supplier
              </p>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Supplier
                </label>
                <select
                  value={scheduleForm.supplier}
                  onChange={e => setScheduleForm({...scheduleForm, supplier: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-teal-500/20"
                >
                  <option value="splendour_tiles">Splendour Tiles</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email / Username
                </label>
                <input
                  type="email"
                  value={scheduleForm.email}
                  onChange={e => setScheduleForm({...scheduleForm, email: e.target.value})}
                  placeholder="your@email.com"
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-teal-500/20"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  value={scheduleForm.password}
                  onChange={e => setScheduleForm({...scheduleForm, password: e.target.value})}
                  placeholder="••••••••"
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-teal-500/20"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Frequency
                  </label>
                  <select
                    value={scheduleForm.frequency}
                    onChange={e => setScheduleForm({...scheduleForm, frequency: e.target.value})}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-teal-500/20"
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Time (UTC)
                  </label>
                  <input
                    type="time"
                    value={scheduleForm.time}
                    onChange={e => setScheduleForm({...scheduleForm, time: e.target.value})}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-teal-500/20"
                  />
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="enabled"
                  checked={scheduleForm.enabled}
                  onChange={e => setScheduleForm({...scheduleForm, enabled: e.target.checked})}
                  className="w-4 h-4 text-teal-600 rounded"
                />
                <label htmlFor="enabled" className="text-sm text-gray-700">
                  Enable schedule immediately
                </label>
              </div>
              
              <div className="p-3 bg-blue-50 text-blue-800 text-sm rounded-lg">
                <strong>Note:</strong> The scheduler will automatically import all products from the supplier portal and update existing products with new stock levels and prices.
              </div>
            </div>
            <div className="p-4 border-t bg-gray-50 flex justify-end gap-3">
              <button
                onClick={() => setShowScheduleModal(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={createSchedule}
                disabled={!scheduleForm.email || !scheduleForm.password}
                className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 disabled:opacity-50"
              >
                <Calendar className="w-5 h-5" />
                Create Schedule
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProductImport;
