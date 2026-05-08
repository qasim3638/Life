import React, { useState, useEffect, useCallback, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { format } from 'date-fns';
import {
  Truck,
  MapPin,
  Clock,
  User,
  Phone,
  Package,
  CheckCircle,
  AlertTriangle,
  Navigation,
  Calendar,
  Filter,
  RefreshCw,
  Plus,
  Printer,
  Route,
  Building2,
  ChevronRight,
  X
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';

// Fix Leaflet default marker icon issue
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Custom marker icons
const createCustomIcon = (color, isStore = false) => {
  const size = isStore ? 35 : 30;
  return L.divIcon({
    className: 'custom-marker',
    html: `<div style="
      background-color: ${color};
      width: ${size}px;
      height: ${size}px;
      border-radius: ${isStore ? '8px' : '50%'};
      border: 3px solid white;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: bold;
      font-size: ${isStore ? '14px' : '12px'};
    ">${isStore ? '🏬' : ''}</div>`,
    iconSize: [size, size],
    iconAnchor: [size/2, size],
    popupAnchor: [0, -size],
  });
};

const statusColors = {
  pending: '#fbbf24',
  assigned: '#3b82f6',
  in_transit: '#8b5cf6',
  arrived: '#06b6d4',
  delivered: '#22c55e',
  failed: '#ef4444',
  rescheduled: '#f97316',
};

// Map center controller component
const MapController = ({ center, zoom }) => {
  const map = useMap();
  useEffect(() => {
    if (center) {
      map.setView(center, zoom || 12);
    }
  }, [center, zoom, map]);
  return null;
};

const DeliveryManagement = () => {
  const [deliveries, setDeliveries] = useState([]);
  const [showrooms, setStores] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [statuses, setStatuses] = useState({});
  const [timeSlots, setTimeSlots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(format(new Date(), 'yyyy-MM-dd'));
  const [selectedStore, setSelectedStore] = useState('all');
  const [selectedDriver, setSelectedDriver] = useState('all');
  const [summary, setSummary] = useState(null);
  
  // Map state
  const [mapCenter, setMapCenter] = useState([51.5074, -0.1278]); // Default London
  const [optimizedRoute, setOptimizedRoute] = useState(null);
  
  // Dialog states
  const [selectedDelivery, setSelectedDelivery] = useState(null);
  const [showDeliveryDialog, setShowDeliveryDialog] = useState(false);
  const [showDriverDialog, setShowDriverDialog] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [editStatus, setEditStatus] = useState('');
  const [editDriver, setEditDriver] = useState('');
  const [editNotes, setEditNotes] = useState('');
  
  // New driver form
  const [newDriver, setNewDriver] = useState({ name: '', phone: '', vehicle_reg: '' });
  
  const printRef = useRef();

  // Fetch initial data
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const [statusRes, slotsRes, showroomsRes] = await Promise.all([
          api.get('/api/deliveries/statuses'),
          api.get('/api/deliveries/time-slots'),
          api.get('/api/showrooms'),
        ]);
        setStatuses(statusRes.data);
        setTimeSlots(slotsRes.data);
        setStores(showroomsRes.data);
        
        // Set map center to first showroom with coordinates
        const showroomWithCoords = showroomsRes.data.find(s => s.lat && s.lng);
        if (showroomWithCoords) {
          setMapCenter([showroomWithCoords.lat, showroomWithCoords.lng]);
        }
      } catch (err) {
        console.error('Error fetching initial data:', err);
      }
    };
    fetchInitialData();
  }, []);

  // Fetch deliveries and drivers
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = { date: selectedDate };
      if (selectedStore !== 'all') params.showroom_id = selectedStore;
      if (selectedDriver !== 'all') params.driver_id = selectedDriver;
      
      const [deliveriesRes, driversRes, summaryRes] = await Promise.all([
        api.get('/api/deliveries', { params }),
        api.get('/api/deliveries/drivers/list', { params: { showroom_id: selectedStore !== 'all' ? selectedStore : undefined } }),
        api.get('/api/deliveries/summary', { params: { date: selectedDate, showroom_id: selectedStore !== 'all' ? selectedStore : undefined } }),
      ]);
      
      setDeliveries(deliveriesRes.data);
      setDrivers(driversRes.data);
      setSummary(summaryRes.data);
    } catch (err) {
      console.error('Error fetching data:', err);
      toast.error('Failed to load deliveries');
    } finally {
      setLoading(false);
    }
  }, [selectedDate, selectedStore, selectedDriver]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handle delivery click
  const handleDeliveryClick = (delivery) => {
    setSelectedDelivery(delivery);
    setEditStatus(delivery.status || 'pending');
    setEditDriver(delivery.driver_id || '');
    setEditNotes(delivery.notes || '');
    setShowDeliveryDialog(true);
  };

  // Update delivery
  const handleUpdateDelivery = async () => {
    if (!selectedDelivery) return;
    
    try {
      await api.put(`/api/deliveries/${selectedDelivery.id}`, {
        status: editStatus,
        driver_id: editDriver || null,
        notes: editNotes,
      });
      toast.success('Delivery updated');
      setShowDeliveryDialog(false);
      fetchData();
    } catch (err) {
      toast.error('Failed to update delivery');
    }
  };

  // Get directions
  const handleGetDirections = (delivery) => {
    if (delivery.delivery_lat && delivery.delivery_lng) {
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${delivery.delivery_lat},${delivery.delivery_lng}`, '_blank');
    } else if (delivery.delivery_address) {
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(delivery.delivery_address)}`, '_blank');
    } else {
      toast.error('No address available');
    }
  };

  // Optimize route
  const handleOptimizeRoute = async () => {
    if (selectedStore === 'all') {
      toast.error('Please select a showroom first');
      return;
    }
    
    try {
      const params = {
        date: selectedDate,
        showroom_id: selectedStore,
      };
      if (selectedDriver !== 'all') params.driver_id = selectedDriver;
      
      const res = await api.post('/api/deliveries/optimize-route', null, { params });
      setOptimizedRoute(res.data);
      toast.success(`Route optimized: ${res.data.total_distance} km total`);
    } catch (err) {
      toast.error('Failed to optimize route');
    }
  };

  // Create driver
  const handleCreateDriver = async () => {
    if (!newDriver.name || !newDriver.phone) {
      toast.error('Name and phone are required');
      return;
    }
    
    try {
      await api.post('/api/deliveries/drivers', {
        ...newDriver,
        showroom_id: selectedStore !== 'all' ? selectedStore : null,
      });
      toast.success('Driver created');
      setShowDriverDialog(false);
      setNewDriver({ name: '', phone: '', vehicle_reg: '' });
      fetchData();
    } catch (err) {
      toast.error('Failed to create driver');
    }
  };

  // Print delivery run sheet
  const handlePrintRunSheet = () => {
    const printWindow = window.open('', '_blank');
    const sortedDeliveries = optimizedRoute?.optimized_route || deliveries;
    
    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Delivery Run Sheet - ${selectedDate}</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 20px; }
          h1 { text-align: center; margin-bottom: 20px; }
          .info { margin-bottom: 20px; }
          table { width: 100%; border-collapse: collapse; }
          th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
          th { background-color: #f5f5f5; }
          .signature { margin-top: 20px; border-top: 1px solid #000; width: 200px; }
          @media print { body { print-color-adjust: exact; } }
        </style>
      </head>
      <body>
        <h1>Delivery Run Sheet</h1>
        <div class="info">
          <p><strong>Date:</strong> ${selectedDate}</p>
          <p><strong>Driver:</strong> ${selectedDriver !== 'all' ? drivers.find(d => d.id === selectedDriver)?.name || 'Unassigned' : 'All Drivers'}</p>
          <p><strong>Total Deliveries:</strong> ${sortedDeliveries.length}</p>
          ${optimizedRoute ? `<p><strong>Total Distance:</strong> ${optimizedRoute.total_distance} km</p>` : ''}
        </div>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Customer</th>
              <th>Address</th>
              <th>Phone</th>
              <th>Time Slot</th>
              <th>Items</th>
              <th>Signature</th>
            </tr>
          </thead>
          <tbody>
            ${sortedDeliveries.map((d, i) => `
              <tr>
                <td>${d.route_sequence || i + 1}</td>
                <td>${d.customer_name}</td>
                <td>${d.delivery_address}</td>
                <td>${d.customer_phone}</td>
                <td>${timeSlots.find(t => t.id === d.time_slot)?.label || d.time_slot}</td>
                <td>${d.items_summary || '-'}</td>
                <td style="height: 40px;"></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
        <div class="signature">
          <p>Driver Signature: ________________</p>
        </div>
      </body>
      </html>
    `);
    
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => {
      printWindow.print();
      printWindow.close();
    }, 250);
  };

  // Get route polyline coordinates
  const getRouteCoordinates = () => {
    if (!optimizedRoute?.optimized_route?.length) return [];
    
    const coords = [];
    if (optimizedRoute.start_location) {
      coords.push([optimizedRoute.start_location.lat, optimizedRoute.start_location.lng]);
    }
    
    optimizedRoute.optimized_route.forEach(d => {
      if (d.delivery_lat && d.delivery_lng) {
        coords.push([d.delivery_lat, d.delivery_lng]);
      }
    });
    
    return coords;
  };

  return (
    <div className="h-[calc(100vh-80px)] flex flex-col" data-testid="delivery-management-page">
      {/* Header */}
      <div className="p-4 bg-white border-b">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
              <Truck className="w-7 h-7 text-blue-600" />
              Delivery Management
            </h1>
            <p className="text-slate-500 mt-1">Track and manage deliveries with map view</p>
          </div>
          
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2">
            <Input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="w-[150px]"
            />
            
            <Select value={selectedStore} onValueChange={setSelectedStore}>
              <SelectTrigger className="w-[160px]">
                <Building2 className="w-4 h-4 mr-2" />
                <SelectValue placeholder="All Stores" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Stores</SelectItem>
                {showrooms.map((s) => (
                  <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            <Select value={selectedDriver} onValueChange={setSelectedDriver}>
              <SelectTrigger className="w-[150px]">
                <User className="w-4 h-4 mr-2" />
                <SelectValue placeholder="All Drivers" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Drivers</SelectItem>
                {drivers.map((d) => (
                  <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
        
        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
          <Card className="bg-gradient-to-br from-blue-500 to-blue-600 text-white">
            <CardContent className="p-3">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-blue-100 text-xs">Total</p>
                  <p className="text-2xl font-bold">{summary?.total || 0}</p>
                </div>
                <Package className="w-8 h-8 text-blue-200" />
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-gradient-to-br from-amber-500 to-amber-600 text-white">
            <CardContent className="p-3">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-amber-100 text-xs">Pending</p>
                  <p className="text-2xl font-bold">{summary?.pending || 0}</p>
                </div>
                <Clock className="w-8 h-8 text-amber-200" />
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-gradient-to-br from-purple-500 to-purple-600 text-white">
            <CardContent className="p-3">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-purple-100 text-xs">In Progress</p>
                  <p className="text-2xl font-bold">{summary?.in_progress || 0}</p>
                </div>
                <Truck className="w-8 h-8 text-purple-200" />
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-gradient-to-br from-emerald-500 to-emerald-600 text-white">
            <CardContent className="p-3">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-emerald-100 text-xs">Completed</p>
                  <p className="text-2xl font-bold">{summary?.completed || 0}</p>
                </div>
                <CheckCircle className="w-8 h-8 text-emerald-200" />
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-gradient-to-br from-slate-500 to-slate-600 text-white">
            <CardContent className="p-3">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-slate-200 text-xs">Unassigned</p>
                  <p className="text-2xl font-bold">{summary?.unassigned || 0}</p>
                </div>
                <AlertTriangle className="w-8 h-8 text-slate-300" />
              </div>
            </CardContent>
          </Card>
        </div>
        
        {/* Action Buttons */}
        <div className="flex flex-wrap gap-2 mt-4">
          <Button variant="outline" size="sm" onClick={() => setShowDriverDialog(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Add Driver
          </Button>
          <Button variant="outline" size="sm" onClick={handleOptimizeRoute} disabled={selectedStore === 'all'}>
            <Route className="w-4 h-4 mr-2" />
            Optimize Route
          </Button>
          <Button variant="outline" size="sm" onClick={handlePrintRunSheet}>
            <Printer className="w-4 h-4 mr-2" />
            Print Run Sheet
          </Button>
        </div>
      </div>
      
      {/* Main Content - Map and List */}
      <div className="flex-1 flex overflow-hidden">
        {/* Map */}
        <div className="flex-1 relative">
          <MapContainer
            center={mapCenter}
            zoom={12}
            style={{ height: '100%', width: '100%' }}
          >
            <MapController center={mapCenter} zoom={12} />
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            
            {/* Store markers */}
            {showrooms.filter(s => s.lat && s.lng).map(showroom => (
              <Marker
                key={`showroom-${showroom.id}`}
                position={[showroom.lat, showroom.lng]}
                icon={createCustomIcon('#1e40af', true)}
              >
                <Popup>
                  <div className="font-semibold">{showroom.name}</div>
                  <div className="text-sm text-gray-600">{showroom.address}</div>
                  <div className="text-sm">{showroom.phone}</div>
                </Popup>
              </Marker>
            ))}
            
            {/* Delivery markers */}
            {deliveries.filter(d => d.delivery_lat && d.delivery_lng).map((delivery, idx) => (
              <Marker
                key={`delivery-${delivery.id}`}
                position={[delivery.delivery_lat, delivery.delivery_lng]}
                icon={createCustomIcon(statusColors[delivery.status] || '#64748b')}
                eventHandlers={{
                  click: () => handleDeliveryClick(delivery),
                }}
              >
                <Popup>
                  <div className="min-w-[200px]">
                    <div className="font-semibold">{delivery.customer_name}</div>
                    <div className="text-sm text-gray-600">{delivery.delivery_address}</div>
                    <div className="flex items-center gap-1 mt-1">
                      <Badge style={{ backgroundColor: statusColors[delivery.status] }} className="text-white text-xs">
                        {statuses[delivery.status]?.label || delivery.status}
                      </Badge>
                    </div>
                    <div className="flex gap-2 mt-2">
                      <Button size="sm" variant="outline" onClick={() => handleGetDirections(delivery)}>
                        <Navigation className="w-3 h-3 mr-1" />
                        Directions
                      </Button>
                    </div>
                  </div>
                </Popup>
              </Marker>
            ))}
            
            {/* Optimized route line */}
            {optimizedRoute && getRouteCoordinates().length > 1 && (
              <Polyline
                positions={getRouteCoordinates()}
                color="#3b82f6"
                weight={3}
                opacity={0.7}
                dashArray="10, 10"
              />
            )}
          </MapContainer>
          
          {/* Route info overlay */}
          {optimizedRoute && (
            <div className="absolute top-4 right-4 bg-white p-3 rounded-lg shadow-lg z-[1000]">
              <div className="font-semibold text-sm">Optimized Route</div>
              <div className="text-sm text-gray-600">
                {optimizedRoute.delivery_count} stops • {optimizedRoute.total_distance} km
              </div>
              <Button size="sm" variant="ghost" onClick={() => setOptimizedRoute(null)} className="mt-1">
                <X className="w-3 h-3 mr-1" /> Clear
              </Button>
            </div>
          )}
        </div>
        
        {/* Delivery List Sidebar */}
        <div className="w-80 bg-white border-l overflow-y-auto">
          <div className="p-3 border-b bg-slate-50">
            <h3 className="font-semibold text-sm">Deliveries ({deliveries.length})</h3>
          </div>
          
          <div className="divide-y">
            {(optimizedRoute?.optimized_route || deliveries).map((delivery, idx) => (
              <div
                key={delivery.id}
                className="p-3 hover:bg-slate-50 cursor-pointer"
                onClick={() => handleDeliveryClick(delivery)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      {delivery.route_sequence && (
                        <span className="w-5 h-5 bg-blue-100 text-blue-700 rounded-full text-xs flex items-center justify-center font-bold">
                          {delivery.route_sequence}
                        </span>
                      )}
                      <span className="font-medium text-sm">{delivery.customer_name}</span>
                    </div>
                    <div className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                      <MapPin className="w-3 h-3" />
                      {delivery.delivery_address?.substring(0, 30)}...
                    </div>
                    <div className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {timeSlots.find(t => t.id === delivery.time_slot)?.label || delivery.time_slot}
                    </div>
                    {delivery.driver_name && (
                      <div className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                        <User className="w-3 h-3" />
                        {delivery.driver_name}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <Badge 
                      style={{ backgroundColor: statusColors[delivery.status] }} 
                      className="text-white text-xs"
                    >
                      {statuses[delivery.status]?.label || delivery.status}
                    </Badge>
                    {delivery.distance_from_prev && (
                      <span className="text-xs text-slate-400">{delivery.distance_from_prev} km</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
            
            {deliveries.length === 0 && (
              <div className="p-8 text-center text-slate-400">
                <Package className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>No deliveries for this date</p>
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Delivery Details Dialog */}
      <Dialog open={showDeliveryDialog} onOpenChange={setShowDeliveryDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Truck className="w-5 h-5" />
              Delivery Details
            </DialogTitle>
          </DialogHeader>
          
          {selectedDelivery && (
            <div className="space-y-4">
              <div className="p-3 bg-slate-50 rounded-lg">
                <div className="font-medium">{selectedDelivery.customer_name}</div>
                <div className="text-sm text-slate-600 flex items-center gap-1 mt-1">
                  <Phone className="w-3 h-3" />
                  {selectedDelivery.customer_phone}
                </div>
                <div className="text-sm text-slate-600 flex items-start gap-1 mt-1">
                  <MapPin className="w-3 h-3 mt-0.5" />
                  {selectedDelivery.delivery_address}
                </div>
              </div>
              
              {selectedDelivery.items_summary && (
                <div>
                  <label className="text-sm font-medium">Items</label>
                  <p className="text-sm text-slate-600">{selectedDelivery.items_summary}</p>
                </div>
              )}
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium">Status</label>
                  <Select value={editStatus} onValueChange={setEditStatus}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(statuses).map(([key, val]) => (
                        <SelectItem key={key} value={key}>
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: val.color }} />
                            {val.label}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div>
                  <label className="text-sm font-medium">Driver</label>
                  <Select value={editDriver || "unassigned"} onValueChange={(val) => setEditDriver(val === "unassigned" ? "" : val)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Unassigned" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="unassigned">Unassigned</SelectItem>
                      {drivers.map((d) => (
                        <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <div>
                <label className="text-sm font-medium">Notes</label>
                <Textarea 
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                  rows={2}
                />
              </div>
            </div>
          )}
          
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={() => handleGetDirections(selectedDelivery)}>
              <Navigation className="w-4 h-4 mr-2" />
              Directions
            </Button>
            <Button onClick={handleUpdateDelivery}>
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      {/* Add Driver Dialog */}
      <Dialog open={showDriverDialog} onOpenChange={setShowDriverDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Driver</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Name *</label>
              <Input 
                value={newDriver.name}
                onChange={(e) => setNewDriver({ ...newDriver, name: e.target.value })}
                placeholder="Driver name"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Phone *</label>
              <Input 
                value={newDriver.phone}
                onChange={(e) => setNewDriver({ ...newDriver, phone: e.target.value })}
                placeholder="Phone number"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Vehicle Registration</label>
              <Input 
                value={newDriver.vehicle_reg}
                onChange={(e) => setNewDriver({ ...newDriver, vehicle_reg: e.target.value })}
                placeholder="e.g., AB12 CDE"
              />
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDriverDialog(false)}>Cancel</Button>
            <Button onClick={handleCreateDriver}>Add Driver</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default DeliveryManagement;
