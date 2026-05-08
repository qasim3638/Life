import React, { useState, useEffect, useRef } from 'react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { toast } from 'sonner';
import {
  Save, Loader2, Upload, Plus, X, Trash2, Eye, EyeOff,
  Star, Download, Sparkles, Percent, Truck, Shield,
  Building2, MessageSquare, Mail, FileText, BarChart3,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ICON_OPTIONS = [
  { value: 'sparkles', label: 'Sparkles', icon: Sparkles },
  { value: 'percent', label: 'Percent', icon: Percent },
  { value: 'truck', label: 'Truck', icon: Truck },
  { value: 'shield', label: 'Shield', icon: Shield },
  { value: 'building', label: 'Building', icon: Building2 },
  { value: 'message', label: 'Message', icon: MessageSquare },
  { value: 'mail', label: 'Mail', icon: Mail },
  { value: 'star', label: 'Star', icon: Star },
];

export default function BathroomPageAdmin() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [stats, setStats] = useState(null);
  const [content, setContent] = useState({
    hero_title: 'Bath Station',
    hero_subtitle: 'Luxury Bathrooms at Unbeatable Prices',
    hero_description: '',
    public_discount: '35',
    trade_discount: '50',
    catalogue_filename: '',
    catalogue_path: '',
    video_url: '',
    features: [],
    how_to_order_title: 'How to Order Bathrooms',
    how_to_order_intro: '',
    how_to_order_channels: [],
    trade_credit_back_text: '',
    review_quote: '',
    review_author: '',
    cta_title: 'Transform Your Bathroom Today',
    cta_description: '',
    content_sections: [],
  });

  const pdfInputRef = useRef(null);
  const videoInputRef = useRef(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const token = localStorage.getItem('token');
        const headers = { 'Authorization': `Bearer ${token}` };
        const [pageRes, statsRes] = await Promise.all([
          fetch(`${API_URL}/api/bathroom/page`, { headers }),
          fetch(`${API_URL}/api/bathroom/downloads/stats`, { headers }),
        ]);
        const pageData = await pageRes.json();
        const statsData = await statsRes.json();
        if (pageData && Object.keys(pageData).length > 0) {
          setContent(prev => ({ ...prev, ...pageData }));
        }
        setStats(statsData);
      } catch (e) {
        console.error('Failed to load bathroom admin data', e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/bathroom/page`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(content),
      });
      if (res.ok) toast.success('Bathroom page saved');
      else toast.error('Failed to save');
    } catch (e) {
      toast.error('Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const updateField = (field, value) => setContent(prev => ({ ...prev, [field]: value }));

  const handlePdfUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.type !== 'application/pdf') { toast.error('Only PDF files'); return; }
    if (file.size > 250 * 1024 * 1024) { toast.error('Max 250MB'); return; }

    const formData = new FormData();
    formData.append('file', file);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/bathroom/catalogue/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (!res.ok) throw new Error('Upload failed');
      const result = await res.json();
      updateField('catalogue_path', result.path);
      updateField('catalogue_filename', result.filename);
      toast.success(`Catalogue uploaded: ${result.filename} (${(result.size / 1024 / 1024).toFixed(1)}MB)`);
    } catch (err) {
      toast.error('Upload failed');
    } finally {
      if (pdfInputRef.current) pdfInputRef.current.value = '';
    }
  };

  const handleVideoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 200 * 1024 * 1024) { toast.error('Max 200MB'); return; }
    const valid = ['video/mp4', 'video/webm', 'video/quicktime'];
    if (!valid.includes(file.type)) { toast.error('MP4, WebM, or MOV only'); return; }

    const formData = new FormData();
    formData.append('file', file);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/website-admin/homepage/upload-video`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (!res.ok) throw new Error('Upload failed');
      const result = await res.json();
      const servePath = result.storage_path.replace('tile-station/homepage/', '');
      updateField('video_url', `${API_URL}/api/website-admin/homepage/media/${servePath}`);
      toast.success('Video uploaded');
    } catch (err) {
      toast.error('Video upload failed');
    } finally {
      if (videoInputRef.current) videoInputRef.current.value = '';
    }
  };

  const updateListItem = (field, idx, key, val) => {
    setContent(prev => ({
      ...prev,
      [field]: prev[field].map((item, i) => i === idx ? { ...item, [key]: val } : item),
    }));
  };

  const removeListItem = (field, idx) => {
    setContent(prev => ({ ...prev, [field]: prev[field].filter((_, i) => i !== idx) }));
  };

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin" /></div>;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8" data-testid="bathroom-admin">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Bathroom Page</h1>
          <p className="text-sm text-gray-500">Manage the bathroom catalogue landing page</p>
        </div>
        <div className="flex gap-2">
          <a href="/shop/bathroom" target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50">
            <Eye className="w-4 h-4" /> Preview
          </a>
          <Button onClick={save} disabled={saving} data-testid="save-bathroom-page">
            {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
            Save
          </Button>
        </div>
      </div>

      {/* Download Stats */}
      {stats && (
        <div className="grid grid-cols-3 gap-4" data-testid="download-stats">
          <div className="bg-white border rounded-xl p-5">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
                <BarChart3 className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
                <p className="text-xs text-gray-500">Total Downloads</p>
              </div>
            </div>
          </div>
          <div className="bg-white border rounded-xl p-5">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 bg-green-50 rounded-lg flex items-center justify-center">
                <Download className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{stats.public}</p>
                <p className="text-xs text-gray-500">Public Downloads</p>
              </div>
            </div>
          </div>
          <div className="bg-white border rounded-xl p-5">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 bg-amber-50 rounded-lg flex items-center justify-center">
                <Star className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{stats.trade}</p>
                <p className="text-xs text-gray-500">Trade Downloads</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Hero Content */}
      <div className="bg-white border rounded-xl p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">Hero Section</h2>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Title</Label>
            <Input value={content.hero_title} onChange={(e) => updateField('hero_title', e.target.value)} data-testid="hero-title" />
          </div>
          <div className="space-y-2">
            <Label>Subtitle</Label>
            <Input value={content.hero_subtitle} onChange={(e) => updateField('hero_subtitle', e.target.value)} data-testid="hero-subtitle" />
          </div>
        </div>
        <div className="space-y-2">
          <Label>Description</Label>
          <Textarea value={content.hero_description} onChange={(e) => updateField('hero_description', e.target.value)} rows={3} data-testid="hero-desc" />
        </div>
      </div>

      {/* Pricing */}
      <div className="bg-white border rounded-xl p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">Discount Pricing</h2>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Public Discount (%)</Label>
            <Input value={content.public_discount} onChange={(e) => updateField('public_discount', e.target.value)} placeholder="35" data-testid="public-discount" />
          </div>
          <div className="space-y-2">
            <Label>Trade Discount (%)</Label>
            <Input value={content.trade_discount} onChange={(e) => updateField('trade_discount', e.target.value)} placeholder="50" data-testid="trade-discount" />
          </div>
        </div>
      </div>

      {/* Catalogue Upload */}
      <div className="bg-white border rounded-xl p-6 space-y-4" data-testid="catalogue-section">
        <h2 className="font-semibold text-gray-900 flex items-center gap-2">
          <FileText className="w-4 h-4" /> Catalogue PDF
        </h2>
        {content.catalogue_filename && (
          <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-lg p-3">
            <FileText className="w-5 h-5 text-green-600" />
            <span className="text-sm font-medium text-green-800">{content.catalogue_filename}</span>
          </div>
        )}
        <input ref={pdfInputRef} type="file" accept="application/pdf" className="hidden" onChange={handlePdfUpload} />
        <Button variant="outline" onClick={() => pdfInputRef.current?.click()} data-testid="upload-catalogue">
          <Upload className="w-4 h-4 mr-2" /> {content.catalogue_filename ? 'Replace Catalogue' : 'Upload Catalogue'}
        </Button>
      </div>

      {/* Video */}
      <div className="bg-white border rounded-xl p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">Promo Video</h2>
        {content.video_url && (
          <div className="max-w-sm rounded-lg overflow-hidden bg-gray-900 aspect-video">
            <video src={content.video_url} className="w-full h-full object-cover" controls />
          </div>
        )}
        <input ref={videoInputRef} type="file" accept="video/mp4,video/webm,video/quicktime" className="hidden" onChange={handleVideoUpload} />
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => videoInputRef.current?.click()}>
            <Upload className="w-4 h-4 mr-2" /> {content.video_url ? 'Replace Video' : 'Upload Video'}
          </Button>
        </div>
        <div className="space-y-2">
          <Label>Or paste video URL</Label>
          <Input value={content.video_url || ''} onChange={(e) => updateField('video_url', e.target.value)} placeholder="https://..." />
        </div>
      </div>

      {/* Feature Cards */}
      <div className="bg-white border rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">Feature Highlights ({content.features?.length || 0})</h2>
          <Button variant="outline" size="sm" onClick={() => updateField('features', [...(content.features || []), { icon: 'sparkles', title: '', description: '' }])} data-testid="add-feature">
            <Plus className="w-4 h-4 mr-1" /> Add
          </Button>
        </div>
        <div className="space-y-3">
          {(content.features || []).map((f, i) => (
            <div key={i} className="border rounded-lg p-3 space-y-2" data-testid={`feature-editor-${i}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <select
                    value={f.icon}
                    onChange={(e) => updateListItem('features', i, 'icon', e.target.value)}
                    className="text-sm border rounded px-2 py-1"
                  >
                    {ICON_OPTIONS.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                  <span className="font-medium text-sm">{f.title || 'New Feature'}</span>
                </div>
                <button onClick={() => removeListItem('features', i)} className="text-red-400 hover:text-red-600">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Input value={f.title} onChange={(e) => updateListItem('features', i, 'title', e.target.value)} placeholder="Title" className="h-9 text-sm" />
                <Input value={f.description} onChange={(e) => updateListItem('features', i, 'description', e.target.value)} placeholder="Description" className="h-9 text-sm" />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* How to Order */}
      <div className="bg-white border rounded-xl p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">How to Order</h2>
        <div className="space-y-2">
          <Label>Section Title</Label>
          <Input value={content.how_to_order_title} onChange={(e) => updateField('how_to_order_title', e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label>Intro Text</Label>
          <Textarea value={content.how_to_order_intro} onChange={(e) => updateField('how_to_order_intro', e.target.value)} rows={2} />
        </div>
        <div className="flex items-center justify-between mt-4">
          <h3 className="text-sm font-medium text-gray-700">Order Channels ({content.how_to_order_channels?.length || 0})</h3>
          <Button variant="outline" size="sm" onClick={() => updateField('how_to_order_channels', [...(content.how_to_order_channels || []), { icon: 'building', title: '', description: '' }])}>
            <Plus className="w-4 h-4 mr-1" /> Add
          </Button>
        </div>
        <div className="space-y-3">
          {(content.how_to_order_channels || []).map((ch, i) => (
            <div key={i} className="border rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <select value={ch.icon} onChange={(e) => updateListItem('how_to_order_channels', i, 'icon', e.target.value)} className="text-sm border rounded px-2 py-1">
                  {ICON_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
                <button onClick={() => removeListItem('how_to_order_channels', i)} className="text-red-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Input value={ch.title} onChange={(e) => updateListItem('how_to_order_channels', i, 'title', e.target.value)} placeholder="Title" className="h-9 text-sm" />
                <Input value={ch.description} onChange={(e) => updateListItem('how_to_order_channels', i, 'description', e.target.value)} placeholder="Description" className="h-9 text-sm" />
              </div>
            </div>
          ))}
        </div>
        <div className="space-y-2 mt-4">
          <Label>Trade Credit Back Text</Label>
          <Input value={content.trade_credit_back_text} onChange={(e) => updateField('trade_credit_back_text', e.target.value)} placeholder="Trade customers receive 2% Credit Back..." />
        </div>
      </div>

      {/* Review */}
      <div className="bg-white border rounded-xl p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">Customer Review</h2>
        <div className="space-y-2">
          <Label>Quote</Label>
          <Textarea value={content.review_quote} onChange={(e) => updateField('review_quote', e.target.value)} rows={2} />
        </div>
        <div className="space-y-2">
          <Label>Author</Label>
          <Input value={content.review_author} onChange={(e) => updateField('review_author', e.target.value)} placeholder="Peter B." />
        </div>
      </div>

      {/* CTA */}
      <div className="bg-white border rounded-xl p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">Bottom CTA</h2>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Title</Label>
            <Input value={content.cta_title} onChange={(e) => updateField('cta_title', e.target.value)} />
          </div>
        </div>
        <div className="space-y-2">
          <Label>Description</Label>
          <Textarea value={content.cta_description} onChange={(e) => updateField('cta_description', e.target.value)} rows={2} />
        </div>
      </div>
    </div>
  );
}
