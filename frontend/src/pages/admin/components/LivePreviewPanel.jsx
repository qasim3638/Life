import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Eye, Monitor, Tablet, Smartphone, RefreshCw, X, Globe, ExternalLink,
  Loader2, Camera, Columns2, MessageCirclePlus, Trash2, ArrowLeftRight
} from 'lucide-react';
import { toast } from 'sonner';

const DEVICE_SIZES = {
  desktop: { width: '100%', label: 'Desktop', icon: Monitor },
  tablet: { width: '768px', label: 'Tablet', icon: Tablet },
  mobile: { width: '375px', label: 'Mobile', icon: Smartphone },
};

export default function LivePreviewPanel({
  previewUrl, previewDevice, setPreviewDevice, previewKey,
  onRefresh, onClose, iframeRef
}) {
  const [iframeLoading, setIframeLoading] = useState(true);

  // Comparison state
  const [beforeSnapshot, setBeforeSnapshot] = useState(null);
  const [afterSnapshot, setAfterSnapshot] = useState(null);
  const [isComparing, setIsComparing] = useState(false);
  const [sliderPos, setSliderPos] = useState(50);
  const [isCapturing, setIsCapturing] = useState(false);
  const compareRef = useRef(null);

  // Annotation state
  const [annotationMode, setAnnotationMode] = useState(false);
  const [annotations, setAnnotations] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const previewContainerRef = useRef(null);

  const deviceConfig = DEVICE_SIZES[previewDevice];
  const fullUrl = `${window.location.origin}${previewUrl}`;
  const pageName = previewUrl === '/tiles' ? 'Homepage' :
    previewUrl.split('/').filter(Boolean).pop()?.replace(/-/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase()) || 'Page';

  useEffect(() => { setIframeLoading(true); }, [previewUrl, previewKey]);

  // ---- Snapshot Capture ----
  const captureSnapshot = useCallback(async (target = 'before') => {
    setIsCapturing(true);
    try {
      const html2canvas = (await import('html2canvas')).default;
      const iframe = iframeRef.current;
      if (!iframe?.contentDocument?.body) {
        toast.error('Preview not ready — wait for it to load');
        setIsCapturing(false);
        return null;
      }
      const canvas = await html2canvas(iframe.contentDocument.body, {
        allowTaint: true,
        useCORS: true,
        scale: 0.6,
        width: iframe.clientWidth,
        height: iframe.clientHeight,
        x: iframe.contentWindow.scrollX,
        y: iframe.contentWindow.scrollY,
        windowWidth: iframe.clientWidth,
        windowHeight: iframe.clientHeight,
        logging: false,
      });
      const dataUrl = canvas.toDataURL('image/jpeg', 0.75);
      if (target === 'before') {
        setBeforeSnapshot(dataUrl);
        toast.success('Snapshot captured — make your changes, then click Compare');
      } else {
        setAfterSnapshot(dataUrl);
      }
      return dataUrl;
    } catch (err) {
      console.error('Snapshot capture failed:', err);
      toast.error('Capture failed — the page may have restricted content');
      return null;
    } finally {
      setIsCapturing(false);
    }
  }, [iframeRef]);

  const startCompare = useCallback(async () => {
    if (!beforeSnapshot) {
      toast.error('Capture a "Before" snapshot first');
      return;
    }
    const afterImg = await captureSnapshot('after');
    if (afterImg) {
      setIsComparing(true);
      setSliderPos(50);
    }
  }, [beforeSnapshot, captureSnapshot]);

  const exitCompare = () => setIsComparing(false);

  const clearSnapshot = () => {
    setBeforeSnapshot(null);
    setAfterSnapshot(null);
    setIsComparing(false);
  };

  // ---- Slider Drag ----
  const handleSliderMouseDown = useCallback((e) => {
    e.preventDefault();
    const onMove = (ev) => {
      if (!compareRef.current) return;
      const rect = compareRef.current.getBoundingClientRect();
      const pos = ((ev.clientX - rect.left) / rect.width) * 100;
      setSliderPos(Math.max(2, Math.min(98, pos)));
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, []);

  // ---- Annotations ----
  const handleOverlayClick = useCallback((e) => {
    if (!annotationMode) return;
    if (e.target.closest('[data-annotation-pin]')) return;
    // Use the preview container for accurate position calculation
    const container = previewContainerRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const x = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
    const y = Math.max(0, Math.min(100, ((e.clientY - rect.top) / rect.height) * 100));
    const newId = Date.now();
    setAnnotations(prev => [...prev, { id: newId, x, y, text: '' }]);
    setEditingId(newId);
  }, [annotationMode]);

  const updateAnnotationText = useCallback((id, text) => {
    setAnnotations(prev => prev.map(a => a.id === id ? { ...a, text } : a));
  }, []);

  const deleteAnnotation = useCallback((id) => {
    setAnnotations(prev => prev.filter(a => a.id !== id));
    setEditingId(prev => prev === id ? null : prev);
  }, []);

  const clearAnnotations = useCallback(() => {
    setAnnotations([]);
    setEditingId(null);
  }, []);

  return (
    <div className="border-l bg-white flex flex-col min-w-[380px] w-[45%] transition-all duration-300" data-testid="live-preview-panel">
      {/* ---- Header ---- */}
      <div className="border-b px-4 py-2.5 flex items-center gap-2 bg-gray-50/80 flex-shrink-0">
        <Eye className="w-4 h-4 text-indigo-500 flex-shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-gray-900 truncate" data-testid="preview-page-name">{pageName}</p>
          <code className="text-[10px] text-gray-400 truncate block">{previewUrl}</code>
        </div>
        <div className="flex items-center bg-gray-100 rounded-lg p-0.5" data-testid="device-toggles">
          {Object.entries(DEVICE_SIZES).map(([key, config]) => {
            const Icon = config.icon;
            return (
              <button key={key} onClick={() => setPreviewDevice(key)}
                className={`p-1.5 rounded-md transition-colors ${previewDevice === key ? 'bg-white shadow-sm text-indigo-600' : 'text-gray-400 hover:text-gray-600'}`}
                title={config.label} data-testid={`device-${key}`}>
                <Icon className="w-3.5 h-3.5" />
              </button>
            );
          })}
        </div>
        <button onClick={onRefresh} className="p-1.5 rounded-md text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors" title="Refresh" data-testid="refresh-preview">
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
        <button onClick={onClose} className="p-1.5 rounded-md text-gray-400 hover:bg-gray-100 hover:text-red-500 transition-colors" title="Close" data-testid="close-preview">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* ---- Tools Bar ---- */}
      <div className="border-b px-3 py-2 flex items-center gap-1.5 bg-white flex-shrink-0 flex-wrap">
        <button
          onClick={() => captureSnapshot('before')}
          disabled={isCapturing || isComparing}
          className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
            beforeSnapshot
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          } disabled:opacity-50`}
          title={beforeSnapshot ? 'Re-capture snapshot' : 'Capture current state as "Before"'}
          data-testid="capture-before-btn"
        >
          {isCapturing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Camera className="w-3 h-3" />}
          {beforeSnapshot ? 'Re-capture' : 'Capture Before'}
        </button>

        {isComparing ? (
          <button onClick={exitCompare}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
            data-testid="exit-compare-btn">
            <Columns2 className="w-3 h-3" /> Exit Compare
          </button>
        ) : (
          <button onClick={startCompare}
            disabled={!beforeSnapshot || isCapturing}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            title={!beforeSnapshot ? 'Capture a snapshot first' : 'Compare before & after'}
            data-testid="compare-btn">
            <Columns2 className="w-3 h-3" /> Compare
          </button>
        )}

        <div className="w-px h-5 bg-gray-200 mx-0.5" />

        <button
          onClick={() => { setAnnotationMode(m => !m); if (isComparing) exitCompare(); }}
          disabled={isComparing}
          className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
            annotationMode ? 'bg-amber-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          } disabled:opacity-40`}
          title={annotationMode ? 'Exit annotation mode' : 'Click on preview to add notes'}
          data-testid="annotate-toggle-btn"
        >
          <MessageCirclePlus className="w-3 h-3" />
          {annotationMode ? 'Done' : 'Annotate'}
          {annotations.length > 0 && (
            <span className={`ml-0.5 px-1 rounded-full text-[10px] ${annotationMode ? 'bg-white/30' : 'bg-amber-100 text-amber-700'}`}>
              {annotations.length}
            </span>
          )}
        </button>

        {(annotations.length > 0 || beforeSnapshot) && (
          <>
            <div className="w-px h-5 bg-gray-200 mx-0.5" />
            {annotations.length > 0 && (
              <button onClick={clearAnnotations}
                className="flex items-center gap-1 px-2 py-1.5 rounded-md text-xs text-red-500 hover:bg-red-50 transition-colors"
                data-testid="clear-annotations-btn">
                <Trash2 className="w-3 h-3" /> Notes
              </button>
            )}
            {beforeSnapshot && !isComparing && (
              <button onClick={clearSnapshot}
                className="flex items-center gap-1 px-2 py-1.5 rounded-md text-xs text-red-500 hover:bg-red-50 transition-colors"
                data-testid="clear-snapshot-btn">
                <Trash2 className="w-3 h-3" /> Snapshot
              </button>
            )}
          </>
        )}
      </div>

      {/* ---- URL Bar ---- */}
      <div className="px-3 py-1.5 border-b bg-gray-50/50 flex items-center gap-2 flex-shrink-0">
        <div className="flex-1 flex items-center gap-2 bg-white border rounded-md px-3 py-1 text-xs text-gray-500">
          <Globe className="w-3 h-3 text-gray-300 flex-shrink-0" />
          <span className="truncate">{fullUrl}</span>
        </div>
        <a href={fullUrl} target="_blank" rel="noopener noreferrer"
          className="p-1 rounded-md text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors flex-shrink-0" title="Open in new tab">
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>

      {/* ---- Content Area ---- */}
      <div className="flex-1 bg-gray-100 flex items-start justify-center overflow-auto p-2 min-h-0">
        {isComparing && beforeSnapshot && afterSnapshot ? (
          <CompareSlider
            beforeSnapshot={beforeSnapshot}
            afterSnapshot={afterSnapshot}
            sliderPos={sliderPos}
            compareRef={compareRef}
            onMouseDown={handleSliderMouseDown}
          />
        ) : (
          <div
            ref={previewContainerRef}
            className="bg-white shadow-lg rounded-lg overflow-hidden transition-all duration-300 h-full relative"
            style={{ width: deviceConfig.width, maxWidth: '100%' }}
          >
            {iframeLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-white z-10">
                <div className="flex flex-col items-center gap-2">
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
                  <span className="text-xs text-gray-400">Loading preview...</span>
                </div>
              </div>
            )}
            <iframe
              ref={iframeRef}
              key={`${previewUrl}-${previewKey}`}
              src={fullUrl}
              className="w-full h-full border-0"
              style={{ display: 'block' }}
              title="Live Preview"
              onLoad={() => setIframeLoading(false)}
              onError={() => setIframeLoading(false)}
              data-testid="preview-iframe"
            />
            {/* Annotation Overlay - fixed to visible viewport only */}
            {(annotationMode || annotations.length > 0) && (
              <div
                className={`absolute top-0 left-0 right-0 bottom-0 ${annotationMode ? 'cursor-crosshair' : 'pointer-events-none'}`}
                onClick={handleOverlayClick}
                data-testid="annotation-overlay"
                style={{ zIndex: 20, height: '100%', overflow: 'hidden' }}
              >
                {annotations.map((ann, idx) => (
                  <AnnotationPin
                    key={ann.id}
                    annotation={ann}
                    index={idx + 1}
                    isEditing={editingId === ann.id}
                    onEdit={() => setEditingId(editingId === ann.id ? null : ann.id)}
                    onUpdateText={(text) => updateAnnotationText(ann.id, text)}
                    onDelete={() => deleteAnnotation(ann.id)}
                  />
                ))}
              </div>
            )}
            {annotationMode && (
              <div className="absolute bottom-3 left-1/2 -translate-x-1/2 bg-amber-500 text-white text-xs px-3 py-1.5 rounded-full shadow-lg z-30 pointer-events-none animate-pulse">
                Click anywhere to add a note
              </div>
            )}
          </div>
        )}
      </div>

      {/* ---- Annotation List ---- */}
      {annotations.length > 0 && !isComparing && (
        <AnnotationList
          annotations={annotations}
          editingId={editingId}
          setEditingId={setEditingId}
          onUpdateText={updateAnnotationText}
          onDelete={deleteAnnotation}
        />
      )}
    </div>
  );
}

// ============ COMPARE SLIDER ============
function CompareSlider({ beforeSnapshot, afterSnapshot, sliderPos, compareRef, onMouseDown }) {
  return (
    <div
      ref={compareRef}
      className="relative w-full h-full rounded-lg overflow-hidden shadow-lg select-none bg-white"
      data-testid="compare-slider"
    >
      {/* After image (full, behind) */}
      <img src={afterSnapshot} alt="After" className="absolute inset-0 w-full h-full object-contain" draggable={false} />

      {/* Before image (clipped to left of slider) */}
      <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - sliderPos}% 0 0)` }}>
        <img src={beforeSnapshot} alt="Before" className="w-full h-full object-contain" draggable={false} />
      </div>

      {/* Slider handle */}
      <div
        className="absolute top-0 bottom-0 z-10 cursor-col-resize"
        style={{ left: `${sliderPos}%`, transform: 'translateX(-50%)', width: '24px' }}
        onMouseDown={onMouseDown}
        data-testid="compare-slider-handle"
      >
        <div className="absolute left-1/2 -translate-x-1/2 w-0.5 h-full bg-white" style={{ boxShadow: '0 0 6px rgba(0,0,0,0.4)' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-8 bg-white rounded-full shadow-lg flex items-center justify-center">
          <ArrowLeftRight className="w-4 h-4 text-gray-600" />
        </div>
      </div>

      {/* Labels */}
      <div className="absolute top-3 left-3 bg-black/60 backdrop-blur-sm text-white text-[10px] font-bold px-2.5 py-1 rounded-md z-20 pointer-events-none uppercase tracking-wider">
        Before
      </div>
      <div className="absolute top-3 right-3 bg-black/60 backdrop-blur-sm text-white text-[10px] font-bold px-2.5 py-1 rounded-md z-20 pointer-events-none uppercase tracking-wider">
        After
      </div>
    </div>
  );
}

// ============ ANNOTATION PIN ============
function AnnotationPin({ annotation, index, isEditing, onEdit, onUpdateText, onDelete }) {
  const inputRef = useRef(null);

  useEffect(() => {
    if (isEditing && inputRef.current) inputRef.current.focus();
  }, [isEditing]);

  return (
    <div
      data-annotation-pin="true"
      className="absolute group"
      style={{ left: `${annotation.x}%`, top: `${annotation.y}%`, transform: 'translate(-50%, -50%)', zIndex: 25, pointerEvents: 'auto' }}
    >
      <button
        onClick={(e) => { e.stopPropagation(); onEdit(); }}
        className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold shadow-lg transition-all ${
          isEditing
            ? 'bg-amber-500 text-white scale-110 ring-2 ring-amber-300 ring-offset-1'
            : 'bg-amber-400 text-white hover:bg-amber-500 hover:scale-110'
        }`}
        data-testid={`annotation-pin-${index}`}
      >
        {index}
      </button>

      {isEditing && (
        <div
          className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-60 bg-white rounded-lg shadow-xl border p-2.5 z-30"
          onClick={(e) => e.stopPropagation()}
          style={{ pointerEvents: 'auto' }}
          data-testid={`annotation-editor-${index}`}
        >
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Note #{index}</span>
            <button onClick={(e) => { e.stopPropagation(); onDelete(); }}
              className="p-0.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
              data-testid={`delete-annotation-${index}`}>
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
          <textarea
            ref={inputRef}
            value={annotation.text}
            onChange={(e) => onUpdateText(e.target.value)}
            placeholder="Add your note..."
            className="w-full text-xs border rounded-md px-2 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-amber-400 bg-gray-50"
            rows={2}
            onClick={(e) => e.stopPropagation()}
            data-testid={`annotation-text-${index}`}
          />
        </div>
      )}

      {!isEditing && annotation.text && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 max-w-52 bg-gray-900 text-white text-[10px] px-2.5 py-1.5 rounded-md shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-pre-wrap z-30 leading-relaxed">
          {annotation.text}
        </div>
      )}
    </div>
  );
}

// ============ ANNOTATION LIST ============
function AnnotationList({ annotations, editingId, setEditingId, onUpdateText, onDelete }) {
  return (
    <div className="border-t max-h-40 overflow-auto flex-shrink-0" data-testid="annotation-list">
      <div className="px-3 py-1.5 bg-gray-50/80 sticky top-0">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Notes ({annotations.length})</p>
      </div>
      <div className="divide-y">
        {annotations.map((ann, idx) => (
          <div
            key={ann.id}
            className={`flex items-start gap-2 px-3 py-2 text-xs cursor-pointer hover:bg-gray-50 transition-colors ${editingId === ann.id ? 'bg-amber-50' : ''}`}
            onClick={() => setEditingId(editingId === ann.id ? null : ann.id)}
            data-testid={`annotation-list-item-${idx + 1}`}
          >
            <span className="w-5 h-5 rounded-full bg-amber-400 text-white flex items-center justify-center text-[10px] font-bold flex-shrink-0 mt-0.5">
              {idx + 1}
            </span>
            <span className="flex-1 text-gray-600 min-w-0 truncate">
              {ann.text || <span className="italic text-gray-300">No note yet</span>}
            </span>
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(ann.id); }}
              className="p-0.5 rounded hover:bg-red-50 text-gray-300 hover:text-red-500 flex-shrink-0 transition-colors"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
