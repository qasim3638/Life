import React, { useState, useEffect, useCallback } from 'react';
import {
  Plus,
  Save,
  Trash2,
  Edit,
  X,
  Loader2,
  MapPin,
  Phone,
  Mail,
  Clock,
  Image,
  Upload,
  Eye,
  EyeOff,
  Building2,
  GripVertical,
  ExternalLink,
  Headphones,
  MessageCircle,
  Move
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Switch } from '../../components/ui/switch';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function ShowroomsManager() {
  const [showrooms, setShowrooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingShowroom, setEditingShowroom] = useState(null);
  const [showModal, setShowModal] = useState(false);

  const fetchShowrooms = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/showrooms`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setShowrooms(data.showrooms || []);
      }
    } catch (error) {
      console.error('Error:', error);
      toast.error('Failed to load showrooms');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchShowrooms();
  }, [fetchShowrooms]);

  const seedDefaults = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/showrooms/seed-defaults`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        toast.success('Default showrooms created!');
        fetchShowrooms();
      }
    } catch (error) {
      toast.error('Failed to seed defaults');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this showroom?')) return;
    
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/showrooms/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        toast.success('Showroom deleted');
        fetchShowrooms();
      }
    } catch (error) {
      toast.error('Failed to delete');
    }
  };

  const [dragIndex, setDragIndex] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);

  const handleDragStartCard = (index) => {
    setDragIndex(index);
  };

  const handleDragOverCard = (e, index) => {
    e.preventDefault();
    setDragOverIndex(index);
  };

  const handleDropCard = async (index) => {
    if (dragIndex === null || dragIndex === index) {
      setDragIndex(null);
      setDragOverIndex(null);
      return;
    }
    const reordered = [...showrooms];
    const [moved] = reordered.splice(dragIndex, 1);
    reordered.splice(index, 0, moved);
    setShowrooms(reordered);
    setDragIndex(null);
    setDragOverIndex(null);

    // Save new order to backend
    try {
      const token = localStorage.getItem('token');
      const updates = reordered.map((s, i) => ({ id: s.id, display_order: i }));
      await fetch(`${API_URL}/api/website-admin/showrooms/reorder`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ order: updates })
      });
      toast.success('Order saved');
    } catch (e) {
      toast.error('Failed to save order');
      fetchShowrooms();
    }
  };

  const handleDragEnd = () => {
    setDragIndex(null);
    setDragOverIndex(null);
  };

  const handleEdit = (showroom) => {
    setEditingShowroom(showroom);
    setShowModal(true);
  };

  const handleCreate = () => {
    setEditingShowroom(null);
    setShowModal(true);
  };

  return (
    <div className="p-6 max-w-6xl mx-auto" data-testid="showrooms-manager">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Showrooms Manager</h1>
          <p className="text-gray-500 mt-1">Manage showroom locations displayed on the Contact page</p>
        </div>
        <div className="flex gap-2">
          {showrooms.length === 0 && (
            <Button onClick={seedDefaults} variant="outline">
              Load Default Showrooms
            </Button>
          )}
          <Button onClick={handleCreate}>
            <Plus className="w-4 h-4 mr-2" />
            Add Showroom
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
        </div>
      ) : showrooms.length === 0 ? (
        <div className="text-center py-20 bg-gray-50 rounded-xl">
          <Building2 className="w-16 h-16 mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Showrooms Yet</h3>
          <p className="text-gray-500 mb-4">Add your showroom locations or load the defaults</p>
          <Button onClick={seedDefaults}>
            Load Default Tile Station Showrooms
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          {showrooms.map((showroom, index) => (
            <div
              key={showroom.id}
              draggable
              onDragStart={() => handleDragStartCard(index)}
              onDragOver={(e) => handleDragOverCard(e, index)}
              onDrop={() => handleDropCard(index)}
              onDragEnd={handleDragEnd}
              className={`transition-all duration-200 ${
                dragIndex === index ? 'opacity-40 scale-[0.98]' : ''
              } ${
                dragOverIndex === index && dragIndex !== index ? 'border-t-4 border-blue-500 pt-1' : ''
              }`}
            >
              <ShowroomCard
                showroom={showroom}
                index={index}
                onEdit={() => handleEdit(showroom)}
                onDelete={() => handleDelete(showroom.id)}
                onRefresh={fetchShowrooms}
              />
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <ShowroomModal
          showroom={editingShowroom}
          onClose={() => setShowModal(false)}
          onSaved={() => {
            setShowModal(false);
            fetchShowrooms();
          }}
        />
      )}

      {/* Online Enquiries Settings */}
      <OnlineEnquiriesEditor />

      {/* Preview Link */}
      <div className="mt-8 p-4 bg-blue-50 rounded-lg flex items-center justify-between">
        <div>
          <h3 className="font-medium text-gray-900">Preview Contact Page</h3>
          <p className="text-sm text-gray-600">See how your showrooms appear on the website</p>
        </div>
        <a
          href="/shop/contact"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium"
        >
          Open Contact Page
          <ExternalLink className="w-4 h-4" />
        </a>
      </div>
    </div>
  );
}

function ShowroomCard({ showroom, index, onEdit, onDelete, onRefresh }) {
  const [uploading, setUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState(null);
  const [imagePos, setImagePos] = useState({
    x: showroom.image_position_x ?? 50,
    y: showroom.image_position_y ?? 50
  });
  const containerRef = React.useRef(null);

  const savePosition = async (x, y) => {
    try {
      const token = localStorage.getItem('token');
      await fetch(`${API_URL}/api/website-admin/showrooms/${showroom.id}`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_position_x: x, image_position_y: y })
      });
    } catch (e) { /* silent */ }
  };

  const handleDragStart = (e) => {
    if (!showroom.image_url) return;
    e.preventDefault();
    setIsDragging(true);
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    setDragStart({ x: clientX, y: clientY, posX: imagePos.x, posY: imagePos.y });
  };

  const handleDragMove = React.useCallback((e) => {
    if (!isDragging || !dragStart || !containerRef.current) return;
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    const rect = containerRef.current.getBoundingClientRect();
    const dx = ((clientX - dragStart.x) / rect.width) * -100;
    const dy = ((clientY - dragStart.y) / rect.height) * -100;
    const newX = Math.max(0, Math.min(100, dragStart.posX + dx));
    const newY = Math.max(0, Math.min(100, dragStart.posY + dy));
    setImagePos({ x: newX, y: newY });
  }, [isDragging, dragStart]);

  const handleDragEnd = React.useCallback(() => {
    if (isDragging) {
      setIsDragging(false);
      setDragStart(null);
      savePosition(Math.round(imagePos.x), Math.round(imagePos.y));
    }
  }, [isDragging, imagePos]);

  React.useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleDragMove);
      window.addEventListener('mouseup', handleDragEnd);
      window.addEventListener('touchmove', handleDragMove);
      window.addEventListener('touchend', handleDragEnd);
      return () => {
        window.removeEventListener('mousemove', handleDragMove);
        window.removeEventListener('mouseup', handleDragEnd);
        window.removeEventListener('touchmove', handleDragMove);
        window.removeEventListener('touchend', handleDragEnd);
      };
    }
  }, [isDragging, handleDragMove, handleDragEnd]);

  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const token = localStorage.getItem('token');
      const uploadRes = await fetch(`${API_URL}/api/website-admin/showrooms/upload-image`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });

      if (uploadRes.ok) {
        const { url } = await uploadRes.json();
        
        // Update showroom with new image
        await fetch(`${API_URL}/api/website-admin/showrooms/${showroom.id}`, {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ image_url: url })
        });

        toast.success('Image uploaded!');
        onRefresh();
      }
    } catch (error) {
      toast.error('Failed to upload image');
    } finally {
      setUploading(false);
    }
  };

  const toggleActive = async () => {
    try {
      const token = localStorage.getItem('token');
      await fetch(`${API_URL}/api/website-admin/showrooms/${showroom.id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ is_active: !showroom.is_active })
      });
      onRefresh();
    } catch (error) {
      toast.error('Failed to update');
    }
  };

  return (
    <div className={`bg-white border rounded-xl overflow-hidden group ${!showroom.is_active ? 'opacity-60' : ''}`}>
      {/* Image Section - full width across top, draggable to reposition */}
      <div ref={containerRef} className="relative w-full h-52 bg-gray-100 overflow-hidden">
        {showroom.image_url ? (
          <img
            src={showroom.image_url}
            alt={showroom.name}
            className={`w-full h-full object-cover select-none ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
            style={{ objectPosition: `${imagePos.x}% ${imagePos.y}%` }}
            onMouseDown={handleDragStart}
            onTouchStart={handleDragStart}
            draggable={false}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Building2 className="w-12 h-12 text-gray-300" />
          </div>
        )}
        
        {/* Drag hint */}
        {showroom.image_url && !isDragging && (
          <div className="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded flex items-center gap-1 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity">
            <Move className="w-3 h-3" /> Drag to reposition
          </div>
        )}

        {/* Upload overlay - only on right side to not conflict with drag */}
        <label className="absolute top-2 right-2 bg-black/60 hover:bg-black/80 text-white rounded-lg px-3 py-1.5 cursor-pointer transition-colors flex items-center gap-1.5 text-sm">
          <input
            type="file"
            accept="image/*"
            onChange={handleImageUpload}
            className="hidden"
            disabled={uploading}
          />
          {uploading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <><Upload className="w-4 h-4" /> Upload</>
          )}
        </label>

        {showroom.is_coming_soon && (
          <div className="absolute top-2 left-2 bg-amber-500 text-white text-xs px-2 py-1 rounded">
            Coming Soon
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-2">
              <div className="mt-1 cursor-grab text-gray-300 hover:text-gray-500" title="Drag to reorder">
                <GripVertical className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">{showroom.name}</h3>
                <div className="flex items-center gap-1 text-sm text-gray-500 mt-1">
                  <MapPin className="w-4 h-4" />
                  {showroom.address}, {showroom.city} {showroom.postcode}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={toggleActive}
                className={`p-2 rounded-lg ${showroom.is_active ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'}`}
                title={showroom.is_active ? 'Active' : 'Inactive'}
              >
                {showroom.is_active ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
              </button>
              <button onClick={onEdit} className="p-2 bg-blue-100 text-blue-600 rounded-lg hover:bg-blue-200">
                <Edit className="w-4 h-4" />
              </button>
              <button onClick={onDelete} className="p-2 bg-red-100 text-red-600 rounded-lg hover:bg-red-200">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="flex flex-wrap gap-4 mt-3 text-sm">
            {showroom.phone && (
              <div className="flex items-center gap-1 text-gray-600">
                <Phone className="w-4 h-4" />
                {showroom.phone}
              </div>
            )}
            {showroom.email && (
              <div className="flex items-center gap-1 text-gray-600">
                <Mail className="w-4 h-4" />
                {showroom.email}
              </div>
            )}
            {showroom.opening_hours && Object.keys(showroom.opening_hours).length > 0 && (
              <div className="flex items-center gap-1 text-gray-600">
                <Clock className="w-4 h-4" />
                {showroom.opening_hours.monday || 'Hours set'}
              </div>
            )}
          </div>
        </div>
    </div>
  );
}

function ShowroomModal({ showroom, onClose, onSaved }) {
  const [form, setForm] = useState({
    name: showroom?.name || '',
    address: showroom?.address || '',
    city: showroom?.city || '',
    postcode: showroom?.postcode || '',
    phone: showroom?.phone || '',
    email: showroom?.email || '',
    is_coming_soon: showroom?.is_coming_soon || false,
    display_order: showroom?.display_order || 0,
    opening_hours: showroom?.opening_hours || {
      monday: '8:00 - 18:00',
      tuesday: '8:00 - 18:00',
      wednesday: '8:00 - 18:00',
      thursday: '8:00 - 18:00',
      friday: '8:00 - 18:00',
      saturday: '9:00 - 18:00',
      sunday: '10:00 - 16:00'
    },
    holiday_hours: showroom?.holiday_hours || {}
  });
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('details');
  const [holidays, setHolidays] = useState([]);

  // Fetch UK holidays on mount
  React.useEffect(() => {
    const fetchHolidays = async () => {
      try {
        const res = await fetch(`${API_URL}/api/website-admin/uk-holidays`);
        if (res.ok) {
          const data = await res.json();
          const allHolidays = data.holidays || [];
          // Filter to only show upcoming holidays (from 30 days ago onward)
          const cutoff = new Date();
          cutoff.setDate(cutoff.getDate() - 30);
          const upcoming = allHolidays.filter(h => new Date(h.date) >= cutoff);
          setHolidays(upcoming);
        }
      } catch (error) {
        console.error('Error fetching holidays:', error);
      }
    };
    fetchHolidays();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.city.trim()) {
      toast.error('Name and City are required');
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      const url = showroom
        ? `${API_URL}/api/website-admin/showrooms/${showroom.id}`
        : `${API_URL}/api/website-admin/showrooms`;
      
      const res = await fetch(url, {
        method: showroom ? 'PUT' : 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(form)
      });

      if (res.ok) {
        toast.success(showroom ? 'Showroom updated!' : 'Showroom created!');
        onSaved();
      }
    } catch (error) {
      toast.error('Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const updateHours = (day, value) => {
    setForm({
      ...form,
      opening_hours: { ...form.opening_hours, [day]: value }
    });
  };

  const updateHolidayHours = (date, value) => {
    setForm({
      ...form,
      holiday_hours: { ...form.holiday_hours, [date]: value }
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-3xl w-full max-h-[90vh] overflow-auto">
        <div className="p-6 border-b flex items-center justify-between">
          <h2 className="text-xl font-bold">
            {showroom ? 'Edit Showroom' : 'Add New Showroom'}
          </h2>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b px-6">
          <button
            onClick={() => setActiveTab('details')}
            className={`px-4 py-3 font-medium border-b-2 transition-colors ${
              activeTab === 'details' 
                ? 'border-amber-500 text-amber-600' 
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Details
          </button>
          <button
            onClick={() => setActiveTab('hours')}
            className={`px-4 py-3 font-medium border-b-2 transition-colors ${
              activeTab === 'hours' 
                ? 'border-amber-500 text-amber-600' 
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Opening Hours
          </button>
          <button
            onClick={() => setActiveTab('holidays')}
            className={`px-4 py-3 font-medium border-b-2 transition-colors ${
              activeTab === 'holidays' 
                ? 'border-amber-500 text-amber-600' 
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Holiday Hours
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {activeTab === 'details' && (
            <>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Showroom Name *</label>
                  <Input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="e.g., Gravesend"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">City *</label>
                  <Input
                    value={form.city}
                    onChange={(e) => setForm({ ...form, city: e.target.value })}
                    placeholder="e.g., London"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
                <Input
                  value={form.address}
                  onChange={(e) => setForm({ ...form, address: e.target.value })}
                  placeholder="e.g., Unit 3, Trade City, Coldharbour Road"
                />
              </div>

              <div className="grid sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Postcode</label>
                  <Input
                    value={form.postcode}
                    onChange={(e) => setForm({ ...form, postcode: e.target.value })}
                    placeholder="e.g., DA11 8AB"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                  <Input
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    placeholder="e.g., 01234 567890"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  <Input
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    placeholder="e.g., store@tilestation.co.uk"
                  />
                </div>
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Display Order</label>
                  <Input
                    type="number"
                    value={form.display_order}
                    onChange={(e) => setForm({ ...form, display_order: parseInt(e.target.value) || 0 })}
                  />
                </div>
                <div className="flex items-center gap-2 pt-6">
                  <input
                    type="checkbox"
                    id="coming_soon"
                    checked={form.is_coming_soon}
                    onChange={(e) => setForm({ ...form, is_coming_soon: e.target.checked })}
                    className="w-4 h-4 rounded border-gray-300"
                  />
                  <label htmlFor="coming_soon" className="text-sm text-gray-700">Mark as "Coming Soon"</label>
                </div>
              </div>
            </>
          )}

          {activeTab === 'hours' && (
            <div>
              <p className="text-sm text-gray-500 mb-4">Set regular opening hours for each day of the week. Leave blank or type "Closed" for days you're not open.</p>
              <div className="space-y-3">
                {['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].map(day => (
                  <div key={day} className="flex items-center gap-4">
                    <label className="w-24 text-sm font-medium text-gray-700 capitalize">{day}</label>
                    <Input
                      value={form.opening_hours[day] || ''}
                      onChange={(e) => updateHours(day, e.target.value)}
                      placeholder="e.g., 9:00 - 17:00 or Closed"
                      className="flex-1"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'holidays' && (
            <div>
              <p className="text-sm text-gray-500 mb-4">Set special hours for UK bank holidays. Leave blank to use regular hours, or type "Closed" if not open.</p>
              <div className="space-y-3 max-h-[400px] overflow-y-auto">
                {holidays.map(holiday => (
                  <div key={holiday.date} className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg">
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900">{holiday.name}</p>
                      <p className="text-xs text-gray-500">{new Date(holiday.date).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</p>
                    </div>
                    <Input
                      value={form.holiday_hours[holiday.date] || ''}
                      onChange={(e) => updateHolidayHours(holiday.date, e.target.value)}
                      placeholder="e.g., 10:00 - 16:00 or Closed"
                      className="w-48"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
              {showroom ? 'Update' : 'Create'} Showroom
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}


function OnlineEnquiriesEditor() {
  const [phone, setPhone] = useState('');
  const [whatsapp, setWhatsapp] = useState('');
  const [emails, setEmails] = useState([]);
  const [phoneVisible, setPhoneVisible] = useState(true);
  const [whatsappVisible, setWhatsappVisible] = useState(true);
  const [liveChatEnabled, setLiveChatEnabled] = useState(true);
  const [liveChatWelcome, setLiveChatWelcome] = useState('Hi! How can we help you today?');
  const [liveChatAI, setLiveChatAI] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchSettings();
    fetchChatSettings();
  }, []);

  const fetchChatSettings = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/live-chat/settings`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setLiveChatEnabled(data.enabled !== false);
        setLiveChatWelcome(data.welcome_message || 'Hi! How can we help you today?');
        setLiveChatAI(data.ai_enabled !== false);
      }
    } catch (error) {
      console.error('Error fetching chat settings:', error);
    }
  };

  const saveChatSettings = async () => {
    try {
      const token = localStorage.getItem('token');
      await fetch(`${API_URL}/api/live-chat/settings`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          enabled: liveChatEnabled,
          welcome_message: liveChatWelcome,
          ai_enabled: liveChatAI
        })
      });
    } catch (error) {
      console.error('Error saving chat settings:', error);
    }
  };

  const fetchSettings = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/contact-settings`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setPhone(data.phone || '');
        setWhatsapp(data.whatsapp || '');
        setEmails(data.emails || []);
        setPhoneVisible(data.phone_visible !== false);
        setWhatsappVisible(data.whatsapp_visible !== false);
      }
    } catch (error) {
      console.error('Error fetching contact settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/contact-settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ phone, whatsapp, phone_visible: phoneVisible, whatsapp_visible: whatsappVisible, emails: emails.filter(e => e.email.trim()) })
      });
      if (res.ok) {
        await saveChatSettings();
        toast.success('Contact settings saved');
      } else {
        toast.error('Failed to save');
      }
    } catch (error) {
      toast.error('Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const addEmail = () => {
    setEmails([...emails, { label: '', email: '' }]);
  };

  const updateEmail = (index, field, value) => {
    const updated = [...emails];
    updated[index] = { ...updated[index], [field]: value };
    setEmails(updated);
  };

  const removeEmail = (index) => {
    setEmails(emails.filter((_, i) => i !== index));
  };

  if (loading) return null;

  return (
    <div className="mt-10 bg-white border border-gray-200 rounded-xl p-6" data-testid="online-enquiries-editor">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
          <Headphones className="w-5 h-5 text-amber-600" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-gray-900">Online Enquiries</h2>
          <p className="text-sm text-gray-500">Manage the phone number and department emails shown on the Contact page</p>
        </div>
      </div>

      {/* Phone Number */}
      <div className={`mb-6 ${!phoneVisible ? 'opacity-50' : ''}`}>
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-sm font-medium text-gray-700">Phone Number</label>
          <div className="flex items-center gap-2">
            {phoneVisible ? <Eye className="w-3.5 h-3.5 text-green-500" /> : <EyeOff className="w-3.5 h-3.5 text-gray-400" />}
            <Switch checked={phoneVisible} onCheckedChange={setPhoneVisible} data-testid="phone-visibility-toggle" />
          </div>
        </div>
        <div className="flex items-center gap-2 max-w-md">
          <Phone className="w-4 h-4 text-gray-400" />
          <Input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="e.g., 01234 567890"
            data-testid="enquiry-phone-input"
          />
        </div>
      </div>

      {/* WhatsApp Number */}
      <div className={`mb-6 ${!whatsappVisible ? 'opacity-50' : ''}`}>
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-sm font-medium text-gray-700">WhatsApp</label>
          <div className="flex items-center gap-2">
            {whatsappVisible ? <Eye className="w-3.5 h-3.5 text-green-500" /> : <EyeOff className="w-3.5 h-3.5 text-gray-400" />}
            <Switch checked={whatsappVisible} onCheckedChange={setWhatsappVisible} data-testid="whatsapp-visibility-toggle" />
          </div>
        </div>
        <div className="flex items-center gap-2 max-w-md">
          <MessageCircle className="w-4 h-4 text-green-500" />
          <Input
            value={whatsapp}
            onChange={(e) => setWhatsapp(e.target.value)}
            placeholder="e.g., +44 7123 456789"
            data-testid="enquiry-whatsapp-input"
          />
        </div>
      </div>

      {/* Email Addresses */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <label className="text-sm font-medium text-gray-700">Email Addresses</label>
          <Button variant="outline" size="sm" onClick={addEmail} data-testid="add-email-btn">
            <Plus className="w-3.5 h-3.5 mr-1.5" />
            Add Email
          </Button>
        </div>

        {emails.length === 0 ? (
          <p className="text-sm text-gray-400 italic py-3">No email addresses added yet. Click "Add Email" to create one.</p>
        ) : (
          <div className="space-y-3">
            {emails.map((entry, i) => (
              <div key={i} className={`flex items-center gap-3 bg-gray-50 rounded-lg p-3 ${entry.visible === false ? 'opacity-50' : ''}`} data-testid={`email-row-${i}`}>
                <Mail className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <Input
                  value={entry.label}
                  onChange={(e) => updateEmail(i, 'label', e.target.value)}
                  placeholder="Label (e.g., Orders, Quotes)"
                  className="w-44"
                  data-testid={`email-label-${i}`}
                />
                <Input
                  value={entry.email}
                  onChange={(e) => updateEmail(i, 'email', e.target.value)}
                  placeholder="email@example.com"
                  className="flex-1"
                  data-testid={`email-address-${i}`}
                />
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  {entry.visible !== false ? <Eye className="w-3.5 h-3.5 text-green-500" /> : <EyeOff className="w-3.5 h-3.5 text-gray-400" />}
                  <Switch
                    checked={entry.visible !== false}
                    onCheckedChange={(checked) => updateEmail(i, 'visible', checked)}
                    data-testid={`email-visibility-${i}`}
                  />
                </div>
                <Button variant="ghost" size="sm" onClick={() => removeEmail(i)} className="text-red-500 hover:text-red-700 hover:bg-red-50 px-2" data-testid={`remove-email-${i}`}>
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Live Chat */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <label className="text-sm font-medium text-gray-700">Live Chat</label>
          <div className="flex items-center gap-2">
            {liveChatEnabled ? <Eye className="w-3.5 h-3.5 text-green-500" /> : <EyeOff className="w-3.5 h-3.5 text-gray-400" />}
            <Switch checked={liveChatEnabled} onCheckedChange={setLiveChatEnabled} data-testid="livechat-toggle" />
          </div>
        </div>

        <div className={`space-y-3 p-4 bg-gray-50 rounded-lg ${!liveChatEnabled ? 'opacity-50 pointer-events-none' : ''}`}>
          <div className="flex items-center gap-3">
            <MessageCircle className="w-5 h-5 text-blue-500 flex-shrink-0" />
            <div className="flex-1">
              <label className="text-xs font-medium text-gray-500 mb-1 block">Welcome Message</label>
              <Input
                value={liveChatWelcome}
                onChange={(e) => setLiveChatWelcome(e.target.value)}
                placeholder="Hi! How can we help you today?"
                data-testid="livechat-welcome-input"
              />
            </div>
          </div>
          <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-600">
            <input
              type="checkbox"
              checked={liveChatAI}
              onChange={(e) => setLiveChatAI(e.target.checked)}
              className="w-4 h-4 rounded text-blue-500"
              data-testid="livechat-ai-toggle"
            />
            Enable AI auto-reply when no agent is available
          </label>
          <a
            href="/admin/live-chat"
            className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800 font-medium"
            data-testid="livechat-admin-link"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Open Live Chat Dashboard
          </a>
        </div>
      </div>

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving} data-testid="save-contact-settings-btn">
          {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
          Save Contact Settings
        </Button>
      </div>
    </div>
  );
}
