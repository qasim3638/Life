/**
 * Sample Room Editor — modal for admins to:
 *   • Replace a sample room's image (paste URL OR upload file → fal.ai)
 *   • Visually re-tag the surface polygon by dragging 4 corner handles
 *   • Tweak label, room_type, surface_kind, m², tile repeat size, order
 *
 * Polygon storage convention matches `services/visualizer.py`: a list
 * of 4 [x, y] integer pixel coords in the original image's coordinate
 * space. We render the image at a capped CSS width and scale the
 * handle coordinates with `naturalWidth/displayWidth`.
 */
import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, Save, Upload, X, Link as LinkIcon, RotateCcw } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

const API = process.env.REACT_APP_BACKEND_URL;
const tokenHdr = () => {
  const t = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
  return t ? { Authorization: `Bearer ${t}` } : {};
};

const ROOM_TYPES = ['kitchen', 'bathroom', 'hallway', 'living_room', 'utility', 'conservatory'];
const DISPLAY_WIDTH = 720;  // px on screen — image scales to this width

// Default polygon for a fresh image, sized in 0..1 normalised coords.
// Multiplied by natural dims when applied. Floor = bottom trapezoid;
// wall = top rectangle (matches the SAM2 fallback in services/visualizer.py).
const DEFAULT_POLYGON_NORM = {
  floor: [[0.08, 0.95], [0.92, 0.95], [0.78, 0.55], [0.22, 0.55]],
  wall: [[0.20, 0.10], [0.80, 0.10], [0.80, 0.55], [0.20, 0.55]],
};

const defaultPolygonForImage = (W, H, surfaceKind) => {
  const norm = DEFAULT_POLYGON_NORM[surfaceKind] || DEFAULT_POLYGON_NORM.floor;
  return norm.map(([x, y]) => [Math.round(x * W), Math.round(y * H)]);
};


const SampleRoomEditor = ({ room, onClose, onSaved }) => {
  const isNew = !room?.id;
  const [form, setForm] = useState(() => ({
    id: room?.id || '',
    label: room?.label || 'New Sample Room',
    room_type: room?.room_type || 'kitchen',
    surface_kind: room?.surface_kind || 'floor',
    image_url: room?.image_url || '',
    surface_polygon: room?.surface_polygon || [[60, 660], [970, 660], [780, 360], [240, 360]],
    default_surface_m2: room?.default_surface_m2 ?? 9,
    tile_repeat_size_px: room?.tile_repeat_size_px ?? 180,
    display_order: room?.display_order ?? 100,
    active: room?.active !== false,
  }));
  const [pasteUrl, setPasteUrl] = useState('');
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [imgDims, setImgDims] = useState({ natural: { w: 1024, h: 683 }, display: { w: DISPLAY_WIDTH, h: 480 } });
  const fileRef = useRef(null);
  const imgRef = useRef(null);
  const containerRef = useRef(null);

  // Polygon dragging state — index of handle currently being dragged
  const [dragIdx, setDragIdx] = useState(null);

  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const onImgLoad = () => {
    const img = imgRef.current;
    if (!img) return;
    const naturalW = img.naturalWidth || 1024;
    const naturalH = img.naturalHeight || 683;
    const displayW = img.clientWidth || DISPLAY_WIDTH;
    const displayH = img.clientHeight || (DISPLAY_WIDTH * naturalH) / naturalW;
    setImgDims({ natural: { w: naturalW, h: naturalH }, display: { w: displayW, h: displayH } });
  };

  // When the surface_kind toggles or the image changes drastically, offer
  // a "Reset polygon" button rather than auto-clobbering the admin's edits.
  const resetPolygon = () => {
    const { w, h } = imgDims.natural;
    update('surface_polygon', defaultPolygonForImage(w, h, form.surface_kind));
    toast.message('Polygon reset to default for ' + form.surface_kind);
  };

  // ── Drag handlers ──────────────────────────────────────────────────
  const scaleX = imgDims.display.w / Math.max(1, imgDims.natural.w);
  const scaleY = imgDims.display.h / Math.max(1, imgDims.natural.h);
  const toDisplay = ([x, y]) => [x * scaleX, y * scaleY];
  const fromDisplay = (dx, dy) => [
    Math.max(0, Math.min(imgDims.natural.w, Math.round(dx / scaleX))),
    Math.max(0, Math.min(imgDims.natural.h, Math.round(dy / scaleY))),
  ];

  const onPointerDown = (idx, e) => {
    e.preventDefault();
    setDragIdx(idx);
    e.target.setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e) => {
    if (dragIdx === null || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const dx = e.clientX - rect.left;
    const dy = e.clientY - rect.top;
    const next = fromDisplay(dx, dy);
    setForm((f) => ({
      ...f,
      surface_polygon: f.surface_polygon.map((p, i) => (i === dragIdx ? next : p)),
    }));
  };
  const onPointerUp = () => setDragIdx(null);

  useEffect(() => {
    if (dragIdx === null) return;
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    return () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dragIdx]);

  // ── Image source actions ──────────────────────────────────────────
  const applyPastedUrl = () => {
    const u = pasteUrl.trim();
    if (!u || !u.startsWith('http')) {
      toast.error('Paste a valid image URL');
      return;
    }
    update('image_url', u);
    setPasteUrl('');
  };

  const onFileChosen = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 12 * 1024 * 1024) {
      toast.error('Image too large — max 12 MB');
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await axios.post(`${API}/api/admin/visualizer/upload-image`, fd, {
        headers: { 'Content-Type': 'multipart/form-data', ...tokenHdr() },
        timeout: 45000,
      });
      update('image_url', r.data.url);
      toast.success('Image uploaded — drag the handles to mark the surface');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  // ── Save ──────────────────────────────────────────────────────────
  const save = async () => {
    if (!form.label?.trim() || !form.image_url) {
      toast.error('Label and image URL are required');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...form,
        id: form.id || undefined,
        default_surface_m2: Number(form.default_surface_m2),
        tile_repeat_size_px: Number(form.tile_repeat_size_px),
        display_order: Number(form.display_order),
      };
      const r = await axios.post(`${API}/api/admin/visualizer/sample-rooms`, payload, { headers: tokenHdr() });
      toast.success(isNew ? 'Room created' : 'Room saved');
      onSaved?.(r.data?.id || form.id);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────
  const polyPoints = form.surface_polygon.map(toDisplay);
  const polyAttr = polyPoints.map(([x, y]) => `${x},${y}`).join(' ');

  return (
    <div
      className="fixed inset-0 z-[10000] bg-black/60 backdrop-blur-sm flex items-start justify-center p-4 overflow-y-auto"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      data-testid="sample-room-editor-modal"
    >
      <div className="bg-white rounded-xl shadow-2xl max-w-5xl w-full my-6 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200">
          <h3 className="text-lg font-bold text-slate-900">
            {isNew ? 'Add new sample room' : `Edit "${form.label}"`}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-slate-100 text-slate-500"
            data-testid="sample-room-editor-close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 grid lg:grid-cols-12 gap-5">
          {/* LEFT — image + polygon editor */}
          <div className="lg:col-span-8">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
              Surface polygon · drag the 4 handles to outline the {form.surface_kind}
            </div>
            <div
              ref={containerRef}
              className="relative inline-block bg-slate-100 rounded-lg overflow-hidden select-none"
              style={{ width: DISPLAY_WIDTH, maxWidth: '100%' }}
              data-testid="sample-room-polygon-canvas"
            >
              {form.image_url ? (
                <>
                  <img
                    ref={imgRef}
                    src={form.image_url}
                    alt={form.label}
                    onLoad={onImgLoad}
                    onError={() => toast.error('Image failed to load — paste a different URL or upload a file')}
                    className="block w-full h-auto"
                    crossOrigin="anonymous"
                  />
                  <svg
                    className="absolute inset-0 w-full h-full pointer-events-none"
                    viewBox={`0 0 ${imgDims.display.w} ${imgDims.display.h}`}
                    preserveAspectRatio="none"
                  >
                    <polygon
                      points={polyAttr}
                      fill={form.surface_kind === 'floor' ? 'rgba(250,204,21,0.30)' : 'rgba(56,189,248,0.30)'}
                      stroke={form.surface_kind === 'floor' ? '#facc15' : '#38bdf8'}
                      strokeWidth="2"
                    />
                    {polyPoints.map(([x, y], i) => (
                      <circle
                        key={i}
                        cx={x}
                        cy={y}
                        r="10"
                        fill="#fff"
                        stroke="#0f172a"
                        strokeWidth="2"
                        style={{ cursor: 'grab', pointerEvents: 'all', touchAction: 'none' }}
                        onPointerDown={(e) => onPointerDown(i, e)}
                        data-testid={`sample-room-polygon-handle-${i}`}
                      />
                    ))}
                  </svg>
                </>
              ) : (
                <div className="aspect-[3/2] flex items-center justify-center text-slate-400 text-sm">
                  No image yet — paste a URL or upload below
                </div>
              )}
            </div>

            {/* Image source row */}
            <div className="mt-3 grid sm:grid-cols-2 gap-2">
              <div className="flex gap-1">
                <Input
                  type="url"
                  value={pasteUrl}
                  onChange={(e) => setPasteUrl(e.target.value)}
                  placeholder="Paste image URL (https://…)"
                  data-testid="sample-room-editor-url-input"
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={applyPastedUrl}
                  className="border-slate-300"
                  data-testid="sample-room-editor-url-apply"
                >
                  <LinkIcon className="w-4 h-4 mr-1" /> Use
                </Button>
              </div>
              <div className="flex gap-1">
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={onFileChosen}
                  className="hidden"
                  data-testid="sample-room-editor-file-input"
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading}
                  className="border-slate-300 w-full"
                  data-testid="sample-room-editor-file-pick"
                >
                  {uploading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Upload className="w-4 h-4 mr-1" />}
                  Upload from your computer
                </Button>
              </div>
            </div>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={resetPolygon}
              className="mt-2 text-xs text-slate-500 hover:text-slate-800"
              data-testid="sample-room-editor-reset-polygon"
            >
              <RotateCcw className="w-3 h-3 mr-1" /> Reset polygon to default
            </Button>
          </div>

          {/* RIGHT — fields */}
          <div className="lg:col-span-4 space-y-3" data-testid="sample-room-editor-fields">
            <Field label="Label">
              <Input value={form.label} onChange={(e) => update('label', e.target.value)} data-testid="sample-room-editor-label" />
            </Field>
            <Field label="Room type">
              <select
                value={form.room_type}
                onChange={(e) => update('room_type', e.target.value)}
                className="w-full h-9 rounded-md border border-slate-300 bg-white px-2 text-sm"
                data-testid="sample-room-editor-room-type"
              >
                {ROOM_TYPES.map((rt) => <option key={rt} value={rt}>{rt}</option>)}
              </select>
            </Field>
            <Field label="Surface">
              <div className="flex gap-1" data-testid="sample-room-editor-surface-kind">
                {['floor', 'wall'].map((k) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => update('surface_kind', k)}
                    className={`flex-1 px-3 py-1.5 rounded text-xs font-bold ${
                      form.surface_kind === k ? 'bg-slate-900 text-yellow-300' : 'bg-white text-slate-700 border border-slate-300'
                    }`}
                    data-testid={`sample-room-editor-surface-${k}`}
                  >
                    {k}
                  </button>
                ))}
              </div>
            </Field>
            <Field label="Default surface m²">
              <Input type="number" step="0.5" value={form.default_surface_m2} onChange={(e) => update('default_surface_m2', e.target.value)} data-testid="sample-room-editor-m2" />
            </Field>
            <Field label="Tile repeat size (px)">
              <Input type="number" step="10" value={form.tile_repeat_size_px} onChange={(e) => update('tile_repeat_size_px', e.target.value)} data-testid="sample-room-editor-repeat" />
            </Field>
            <Field label="Display order">
              <Input type="number" step="10" value={form.display_order} onChange={(e) => update('display_order', e.target.value)} data-testid="sample-room-editor-order" />
            </Field>
            <label className="flex items-center gap-2 text-xs text-slate-700 mt-2">
              <input
                type="checkbox"
                checked={form.active}
                onChange={(e) => update('active', e.target.checked)}
                className="rounded border-slate-300"
                data-testid="sample-room-editor-active"
              />
              <span className="font-semibold">Active (visible on customer-facing /visualizer)</span>
            </label>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-slate-200 bg-slate-50">
          <Button type="button" variant="outline" onClick={onClose} className="border-slate-300" data-testid="sample-room-editor-cancel">
            Cancel
          </Button>
          <Button
            type="button"
            onClick={save}
            disabled={saving || !form.image_url}
            className="bg-slate-900 hover:bg-slate-800 text-yellow-300 font-bold"
            data-testid="sample-room-editor-save"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Save className="w-4 h-4 mr-1" />}
            {isNew ? 'Create room' : 'Save changes'}
          </Button>
        </div>
      </div>
    </div>
  );
};

const Field = ({ label, children }) => (
  <div>
    <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1">{label}</label>
    {children}
  </div>
);

export default SampleRoomEditor;
