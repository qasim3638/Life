import React, { useState, useEffect, useCallback } from 'react';
import { Button } from '../../../../components/ui/button';
import { Input } from '../../../../components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../../components/ui/dialog';
import { Save, FolderOpen, Trash2, Loader2, ChevronDown, X } from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const BulkEditPresets = ({ selections, onLoadPreset, productGroup }) => {
  const [presets, setPresets] = useState([]);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [showLoadDropdown, setShowLoadDropdown] = useState(false);
  const [presetName, setPresetName] = useState('');
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);

  const fetchPresets = useCallback(async () => {
    try {
      const url = productGroup
        ? `${API_URL}/api/bulk-edit-tools/presets?product_group=${productGroup}`
        : `${API_URL}/api/bulk-edit-tools/presets`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setPresets(data);
      }
    } catch (err) {
      console.error('Failed to fetch presets:', err);
    }
  }, [productGroup]);

  useEffect(() => {
    fetchPresets();
  }, [fetchPresets]);

  const handleSave = async () => {
    if (!presetName.trim()) {
      toast.error('Please enter a preset name');
      return;
    }

    // Filter out empty values from selections
    const cleanSelections = {};
    for (const [key, value] of Object.entries(selections)) {
      if (value && (typeof value === 'string' ? value.trim() : true)) {
        if (Array.isArray(value) && value.length === 0) continue;
        cleanSelections[key] = value;
      }
    }

    if (Object.keys(cleanSelections).length === 0) {
      toast.error('No attributes selected to save as preset');
      return;
    }

    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/bulk-edit-tools/presets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: presetName.trim(),
          selections: cleanSelections,
          product_group: productGroup || '',
        }),
      });

      if (res.ok) {
        toast.success(`Preset "${presetName}" saved`);
        setShowSaveDialog(false);
        setPresetName('');
        fetchPresets();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to save preset');
      }
    } catch (err) {
      toast.error('Failed to save preset');
    } finally {
      setSaving(false);
    }
  };

  const handleLoad = async (preset) => {
    setLoading(true);
    try {
      onLoadPreset(preset.selections);
      toast.success(`Loaded preset "${preset.name}"`);
      setShowLoadDropdown(false);
    } catch (err) {
      toast.error('Failed to load preset');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e, presetId, presetName) => {
    e.stopPropagation();
    if (!window.confirm(`Delete preset "${presetName}"?`)) return;

    try {
      const res = await fetch(`${API_URL}/api/bulk-edit-tools/presets/${presetId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        toast.success('Preset deleted');
        fetchPresets();
      }
    } catch (err) {
      toast.error('Failed to delete preset');
    }
  };

  return (
    <div className="flex items-center gap-1.5" data-testid="bulk-edit-presets">
      {/* Load Preset */}
      <div className="relative">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowLoadDropdown(!showLoadDropdown)}
          className="h-7 text-xs gap-1 px-2"
          disabled={loading}
          data-testid="load-preset-btn"
        >
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <FolderOpen className="w-3 h-3" />}
          Presets
          <ChevronDown className="w-3 h-3" />
        </Button>

        {showLoadDropdown && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setShowLoadDropdown(false)} />
            <div className="absolute top-full left-0 mt-1 w-64 bg-white border rounded-lg shadow-lg z-50 max-h-60 overflow-y-auto" data-testid="presets-dropdown">
              {presets.length === 0 ? (
                <div className="p-3 text-xs text-gray-500 text-center">
                  No presets saved yet
                </div>
              ) : (
                presets.map((preset) => (
                  <div
                    key={preset.id}
                    onClick={() => handleLoad(preset)}
                    className="flex items-center justify-between px-3 py-2 hover:bg-gray-50 cursor-pointer border-b last:border-0 group"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-800 truncate">{preset.name}</p>
                      <p className="text-xs text-gray-400">
                        {Object.keys(preset.selections || {}).length} attributes
                        {preset.product_group ? ` · ${preset.product_group}` : ''}
                      </p>
                    </div>
                    <button
                      onClick={(e) => handleDelete(e, preset.id, preset.name)}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-50 rounded text-red-400 hover:text-red-600 transition-opacity"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>

      {/* Save Preset */}
      <Button
        variant="outline"
        size="sm"
        onClick={() => setShowSaveDialog(true)}
        className="h-7 text-xs gap-1 px-2"
        data-testid="save-preset-btn"
      >
        <Save className="w-3 h-3" />
        Save Preset
      </Button>

      {/* Save Dialog */}
      <Dialog open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <DialogContent className="max-w-sm" data-testid="save-preset-dialog">
          <DialogHeader>
            <DialogTitle className="text-base">Save Attribute Preset</DialogTitle>
          </DialogHeader>
          <div className="py-2">
            <label className="text-sm text-gray-600 mb-1 block">Preset Name</label>
            <Input
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              placeholder="e.g., Standard Wall Tile Setup"
              autoFocus
              data-testid="preset-name-input"
              onKeyDown={(e) => e.key === 'Enter' && handleSave()}
            />
            <p className="text-xs text-gray-400 mt-1.5">
              Saves all current attribute selections as a reusable template
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setShowSaveDialog(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={saving || !presetName.trim()}
              className="bg-blue-600 hover:bg-blue-700"
              data-testid="confirm-save-preset-btn"
            >
              {saving ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Save className="w-3 h-3 mr-1" />}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default BulkEditPresets;
