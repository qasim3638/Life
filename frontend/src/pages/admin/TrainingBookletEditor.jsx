/**
 * Staff Training Booklet — admin editor.
 *
 * Lets a super-admin edit the editable notes that appear inside the
 * generated PDF. All admins/managers can VIEW the current text and download
 * the latest PDF; only super-admins see the textareas + save button.
 *
 * Data flow:
 *   GET    /api/training-booklet/sections          → list with can_edit flag
 *   PUT    /api/training-booklet/sections/{key}    → save one note
 *   POST   /api/training-booklet/regenerate        → rebuild the PDF
 *   GET    /api/training-booklet/download.pdf      → stream the current PDF
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  BookOpen, Save, Download, RefreshCw, Loader2, Lock, CheckCircle2,
  AlertCircle, FileText, Image as ImageIcon, Upload, RotateCcw, Check,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import { Textarea } from '../../components/ui/textarea';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function TrainingBookletEditor() {
  const [sections, setSections] = useState([]);
  const [imageGroups, setImageGroups] = useState([]);
  const [canEdit, setCanEdit] = useState(false);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState(null);
  const [regenerating, setRegenerating] = useState(false);
  const [drafts, setDrafts] = useState({});
  const [lastRegen, setLastRegen] = useState(null);
  const [tab, setTab] = useState('notes'); // 'notes' | 'images'
  const [uploadingSlug, setUploadingSlug] = useState(null);
  const [resettingSlug, setResettingSlug] = useState(null);
  const fileInputs = useRef({});

  const auth = {
    headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
  };

  const fetchSections = useCallback(async () => {
    setLoading(true);
    try {
      const [s, i] = await Promise.all([
        axios.get(`${API_URL}/api/training-booklet/sections`, auth),
        axios.get(`${API_URL}/api/training-booklet/images`, auth),
      ]);
      setSections(s.data?.sections || []);
      setCanEdit(!!s.data?.can_edit);
      const next = {};
      (s.data?.sections || []).forEach((sec) => { next[sec.key] = sec.content; });
      setDrafts(next);
      setImageGroups(i.data?.groups || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not load booklet data');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { fetchSections(); }, [fetchSections]);

  const isDirty = (key) => {
    const original = sections.find((s) => s.key === key)?.content || '';
    return (drafts[key] || '') !== original;
  };

  const saveSection = async (key) => {
    const content = (drafts[key] || '').trim();
    if (!content) { toast.error('Content cannot be empty'); return; }
    setSavingKey(key);
    try {
      await axios.put(
        `${API_URL}/api/training-booklet/sections/${encodeURIComponent(key)}`,
        { content }, auth,
      );
      toast.success('Saved — click "Rebuild PDF" to update the booklet');
      // Update the local cached "saved" content so isDirty turns false
      setSections((prev) => prev.map((s) => s.key === key ? { ...s, content } : s));
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save failed');
    } finally {
      setSavingKey(null);
    }
  };

  const regenerate = async () => {
    setRegenerating(true);
    try {
      const r = await axios.post(`${API_URL}/api/training-booklet/regenerate`, {}, auth);
      const sizeKb = ((r.data?.size_bytes || 0) / 1024).toFixed(0);
      toast.success(`PDF rebuilt — ${sizeKb} KB`);
      setLastRegen(r.data?.regenerated_at);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Rebuild failed');
    } finally {
      setRegenerating(false);
    }
  };

  // Download via fetch+blob to attach the auth header.
  const download = async () => {
    try {
      const res = await fetch(`${API_URL}/api/training-booklet/download.pdf`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'TileStation_Staff_Training_Booklet.pdf';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(`Download failed: ${e.message}`);
    }
  };

  // Image upload — multipart POST. Backend converts to JPEG, stores in DB,
  // and writes to the public preview folder so the thumbnail updates live.
  const uploadImage = async (slug, file) => {
    if (!file) return;
    if (file.size > 4 * 1024 * 1024) {
      toast.error('Image too large — max 4 MB');
      return;
    }
    setUploadingSlug(slug);
    try {
      const fd = new FormData();
      fd.append('file', file);
      await axios.post(
        `${API_URL}/api/training-booklet/images/${encodeURIComponent(slug)}`,
        fd,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'multipart/form-data',
          },
        },
      );
      toast.success('Uploaded — click "Rebuild PDF" to apply');
      await fetchSections();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Upload failed');
    } finally {
      setUploadingSlug(null);
    }
  };

  const resetImage = async (slug) => {
    setResettingSlug(slug);
    try {
      await axios.delete(
        `${API_URL}/api/training-booklet/images/${encodeURIComponent(slug)}`,
        auth,
      );
      toast.success('Reset to original');
      await fetchSections();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Reset failed');
    } finally {
      setResettingSlug(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-6" data-testid="training-booklet-editor">
      <div className="flex items-start justify-between gap-3 mb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-amber-600" /> Staff Training Booklet
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Edit the operational notes that appear inside the booklet PDF.
            Titles, screenshots and step lists are fixed; only the highlighted "tip" and
            "rule" passages below are editable.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={download} data-testid="download-booklet">
            <Download className="w-4 h-4 mr-1" /> Download current PDF
          </Button>
          {canEdit && (
            <Button
              onClick={regenerate}
              disabled={regenerating}
              size="sm"
              className="bg-amber-600 hover:bg-amber-700 text-white"
              data-testid="rebuild-booklet"
            >
              {regenerating
                ? <><Loader2 className="w-4 h-4 mr-1 animate-spin" /> Rebuilding…</>
                : <><RefreshCw className="w-4 h-4 mr-1" /> Rebuild PDF</>}
            </Button>
          )}
        </div>
      </div>

      {!canEdit && (
        <Card className="p-3 mb-4 bg-gray-50 border-gray-200 text-xs text-gray-600 flex items-center gap-2">
          <Lock className="w-4 h-4 text-gray-500" />
          You can read and download the booklet, but only super-admins can edit notes.
        </Card>
      )}

      {lastRegen && (
        <Card className="p-3 mb-4 bg-emerald-50 border-emerald-200 text-xs text-emerald-700 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          PDF rebuilt {new Date(lastRegen).toLocaleString()} — your edits are now in the downloadable PDF.
        </Card>
      )}

      {/* Tab switcher */}
      <div className="flex items-center gap-1 mb-4 border-b border-gray-200">
        <button
          onClick={() => setTab('notes')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ${
            tab === 'notes'
              ? 'border-amber-600 text-amber-700'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
          data-testid="tab-notes"
        >
          <FileText className="w-4 h-4 inline mr-1.5" />
          Notes &amp; rules ({sections.length})
        </button>
        <button
          onClick={() => setTab('images')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ${
            tab === 'images'
              ? 'border-amber-600 text-amber-700'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
          data-testid="tab-images"
        >
          <ImageIcon className="w-4 h-4 inline mr-1.5" />
          Screenshots ({imageGroups.reduce((acc, g) => acc + g.items.length, 0)})
        </button>
      </div>

      {loading ? (
        <Card className="p-8 flex items-center justify-center text-gray-400">
          <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading…
        </Card>
      ) : tab === 'notes' ? (
        <div className="space-y-4">
          {sections.map((s) => (
            <Card key={s.key} className="p-4" data-testid={`booklet-section-${s.key}`}>
              <div className="flex items-start justify-between gap-3 mb-2">
                <div>
                  <h3 className="font-semibold text-sm text-gray-900">{s.label}</h3>
                  <p className="text-[11px] text-gray-500 mt-0.5">{s.description}</p>
                </div>
                {s.updated_by && (
                  <span className="text-[10px] text-gray-400 shrink-0">
                    Last edit: {new Date(s.updated_at).toLocaleDateString()} · {s.updated_by}
                  </span>
                )}
              </div>
              <Textarea
                value={drafts[s.key] ?? s.content}
                onChange={(e) => setDrafts({ ...drafts, [s.key]: e.target.value })}
                disabled={!canEdit || savingKey === s.key}
                rows={Math.max(3, Math.ceil((drafts[s.key] || s.content || '').length / 90))}
                className="text-sm font-mono"
                data-testid={`booklet-textarea-${s.key}`}
                spellCheck
              />
              <div className="flex items-center justify-between mt-2">
                <p className="text-[10px] text-gray-400">
                  HTML allowed: <code>&lt;b&gt;</code>, <code>&lt;i&gt;</code>, <code>&lt;br/&gt;</code>. Use plain text for everything else.
                  {s.key === 'golden_rules' && ' One rule per line.'}
                </p>
                {canEdit && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!isDirty(s.key) || savingKey === s.key}
                    onClick={() => saveSection(s.key)}
                    data-testid={`booklet-save-${s.key}`}
                  >
                    {savingKey === s.key
                      ? <><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Saving…</>
                      : <><Save className="w-3 h-3 mr-1" /> Save</>}
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      ) : (
        /* IMAGES TAB — grid of every screenshot, grouped by section */
        <div className="space-y-6">
          {imageGroups.map((group) => (
            <div key={group.group} data-testid={`booklet-image-group-${group.group}`}>
              <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide mb-2">
                {group.group}
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                {group.items.map((it) => {
                  const cacheBust = it.updated_at ? `?t=${encodeURIComponent(it.updated_at)}` : '';
                  return (
                    <Card
                      key={it.slug}
                      className={`p-2 transition ${it.has_override ? 'border-amber-400 bg-amber-50/40' : 'border-gray-200'}`}
                      data-testid={`booklet-image-${it.slug}`}
                    >
                      <div className="aspect-[16/10] bg-gray-100 rounded overflow-hidden mb-2 relative">
                        <img
                          src={`${it.preview_url}${cacheBust}`}
                          alt={it.label}
                          className="w-full h-full object-cover"
                          loading="lazy"
                          onError={(e) => { e.target.style.opacity = 0.3; }}
                        />
                        {it.has_override && (
                          <span className="absolute top-1 right-1 bg-amber-500 text-white text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wide">
                            <Check className="w-2.5 h-2.5 inline mr-0.5" />Custom
                          </span>
                        )}
                      </div>
                      <h4 className="text-xs font-semibold text-gray-800 truncate" title={it.label}>{it.label}</h4>
                      <p className="text-[10px] text-gray-400 font-mono truncate">{it.slug}</p>
                      {canEdit && (
                        <div className="flex items-center gap-1 mt-2">
                          <input
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            ref={(el) => { fileInputs.current[it.slug] = el; }}
                            onChange={(e) => {
                              const f = e.target.files?.[0];
                              e.target.value = '';
                              if (f) uploadImage(it.slug, f);
                            }}
                            className="hidden"
                            data-testid={`booklet-image-input-${it.slug}`}
                          />
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={uploadingSlug === it.slug}
                            onClick={() => fileInputs.current[it.slug]?.click()}
                            className="flex-1 h-7 text-[11px]"
                            data-testid={`booklet-image-upload-${it.slug}`}
                          >
                            {uploadingSlug === it.slug
                              ? <Loader2 className="w-3 h-3 animate-spin" />
                              : <><Upload className="w-3 h-3 mr-1" /> Upload</>}
                          </Button>
                          {it.has_override && (
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={resettingSlug === it.slug}
                              onClick={() => resetImage(it.slug)}
                              className="h-7 px-2 text-[11px] text-gray-500 hover:text-rose-700"
                              title="Reset to original"
                              data-testid={`booklet-image-reset-${it.slug}`}
                            >
                              {resettingSlug === it.slug
                                ? <Loader2 className="w-3 h-3 animate-spin" />
                                : <RotateCcw className="w-3 h-3" />}
                            </Button>
                          )}
                        </div>
                      )}
                    </Card>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {canEdit && sections.length > 0 && (
        <Card className="mt-6 p-4 bg-amber-50 border-amber-200 text-xs text-amber-800 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-amber-600" />
          <div>
            <strong>Workflow:</strong> Edit a section → click <b>Save</b> → repeat for any
            other sections → click <b>Rebuild PDF</b> at the top to regenerate the
            downloadable booklet. Staff downloads will get the new version immediately.
          </div>
        </Card>
      )}
    </div>
  );
}
