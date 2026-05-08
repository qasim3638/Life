/**
 * LabelManager - Inline label management within the Bulk Category Editor
 * Allows add/edit/delete of product labels with custom colors
 */
import React, { useState } from 'react';
import { Button } from '../../../../components/ui/button';
import { Input } from '../../../../components/ui/input';
import {
  Plus,
  X,
  Pencil,
  Trash2,
  Check,
  Tag,
} from 'lucide-react';

const PRESET_COLORS = [
  { color: '#ef4444', bg: '#fef2f2', text: '#b91c1c', name: 'Red' },
  { color: '#f97316', bg: '#fff7ed', text: '#c2410c', name: 'Orange' },
  { color: '#eab308', bg: '#fefce8', text: '#a16207', name: 'Yellow' },
  { color: '#22c55e', bg: '#f0fdf4', text: '#15803d', name: 'Green' },
  { color: '#3b82f6', bg: '#eff6ff', text: '#1d4ed8', name: 'Blue' },
  { color: '#a855f7', bg: '#faf5ff', text: '#7e22ce', name: 'Purple' },
  { color: '#ec4899', bg: '#fdf2f8', text: '#be185d', name: 'Pink' },
  { color: '#14b8a6', bg: '#f0fdfa', text: '#0f766e', name: 'Teal' },
  { color: '#6b7280', bg: '#f3f4f6', text: '#374151', name: 'Gray' },
];

const LabelManager = ({ labels, onAdd, onEdit, onDelete, loading }) => {
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingLabel, setEditingLabel] = useState(null);
  const [newName, setNewName] = useState('');
  const [selectedColor, setSelectedColor] = useState(PRESET_COLORS[0]);
  const [editName, setEditName] = useState('');
  const [editColor, setEditColor] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const handleAdd = () => {
    if (!newName.trim()) return;
    onAdd({
      name: newName.trim(),
      color: selectedColor.color,
      bg_color: selectedColor.bg,
      text_color: selectedColor.text,
    });
    setNewName('');
    setSelectedColor(PRESET_COLORS[0]);
    setShowAddForm(false);
  };

  const handleEdit = (label) => {
    if (!editName.trim()) return;
    onEdit(label.name, {
      name: editName.trim(),
      color: editColor?.color || label.color,
      bg_color: editColor?.bg || label.bg_color,
      text_color: editColor?.text || label.text_color,
    });
    setEditingLabel(null);
    setEditName('');
    setEditColor(null);
  };

  const handleDelete = (label) => {
    onDelete(label.name);
    setConfirmDelete(null);
  };

  const startEdit = (label) => {
    setEditingLabel(label.name);
    setEditName(label.name);
    const matchColor = PRESET_COLORS.find(c => c.color === label.color);
    setEditColor(matchColor || PRESET_COLORS[0]);
    setShowAddForm(false);
  };

  return (
    <div className="space-y-2" data-testid="label-manager">
      {/* Existing Labels */}
      <div className="flex flex-wrap gap-1.5">
        {labels.map(label => (
          <div key={label.name} className="group relative">
            {editingLabel === label.name ? (
              <div className="flex items-center gap-1 p-1.5 border border-blue-300 rounded-lg bg-blue-50">
                <Input
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  className="h-6 w-24 text-xs px-1.5"
                  onKeyDown={e => {
                    if (e.key === 'Enter') { e.preventDefault(); handleEdit(label); }
                    if (e.key === 'Escape') setEditingLabel(null);
                  }}
                  autoFocus
                  data-testid={`edit-label-input-${label.name}`}
                />
                <div className="flex gap-0.5">
                  {PRESET_COLORS.map(c => (
                    <button
                      key={c.name}
                      onClick={() => setEditColor(c)}
                      className={`w-4 h-4 rounded-full border-2 transition-all ${
                        (editColor?.color || label.color) === c.color ? 'border-gray-800 scale-125' : 'border-transparent'
                      }`}
                      style={{ backgroundColor: c.color }}
                      title={c.name}
                    />
                  ))}
                </div>
                <button
                  onClick={() => handleEdit(label)}
                  className="p-0.5 text-green-600 hover:text-green-800"
                  data-testid={`save-edit-label-${label.name}`}
                >
                  <Check className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setEditingLabel(null)}
                  className="p-0.5 text-gray-400 hover:text-gray-600"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : confirmDelete === label.name ? (
              <div className="flex items-center gap-1 p-1 border border-red-300 rounded-lg bg-red-50">
                <span className="text-[10px] text-red-700 px-1">Delete "{label.name}"?</span>
                <button
                  onClick={() => handleDelete(label)}
                  className="px-1.5 py-0.5 bg-red-600 text-white text-[10px] rounded hover:bg-red-700"
                  data-testid={`confirm-delete-label-${label.name}`}
                >
                  Yes
                </button>
                <button
                  onClick={() => setConfirmDelete(null)}
                  className="px-1.5 py-0.5 bg-gray-200 text-gray-700 text-[10px] rounded hover:bg-gray-300"
                >
                  No
                </button>
              </div>
            ) : (
              <span
                className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium cursor-default"
                style={{ backgroundColor: label.bg_color || '#f3f4f6', color: label.text_color || '#374151' }}
              >
                <Tag className="w-3 h-3" />
                {label.name}
                <button
                  onClick={() => startEdit(label)}
                  className="opacity-0 group-hover:opacity-100 ml-0.5 p-0.5 rounded hover:bg-black/10 transition-opacity"
                  title="Edit label"
                  data-testid={`edit-label-${label.name}`}
                >
                  <Pencil className="w-2.5 h-2.5" />
                </button>
                <button
                  onClick={() => setConfirmDelete(label.name)}
                  className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-black/10 transition-opacity"
                  title="Delete label"
                  data-testid={`delete-label-${label.name}`}
                >
                  <Trash2 className="w-2.5 h-2.5" />
                </button>
              </span>
            )}
          </div>
        ))}

        {/* Add New Button */}
        {!showAddForm && (
          <button
            onClick={() => { setShowAddForm(true); setEditingLabel(null); }}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 border border-dashed border-gray-300 transition-all"
            data-testid="add-new-label-btn"
          >
            <Plus className="w-3 h-3" />
            Add Label
          </button>
        )}
      </div>

      {/* Add New Label Form */}
      {showAddForm && (
        <div className="p-2.5 border border-green-300 rounded-lg bg-green-50/50 space-y-2">
          <div className="flex items-center gap-1.5">
            <Input
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="Label name..."
              className="h-7 text-xs flex-1"
              onKeyDown={e => {
                if (e.key === 'Enter') { e.preventDefault(); handleAdd(); }
                if (e.key === 'Escape') setShowAddForm(false);
              }}
              autoFocus
              data-testid="new-label-name-input"
            />
            <Button
              onClick={handleAdd}
              disabled={!newName.trim() || loading}
              size="sm"
              className="h-7 px-2 text-xs bg-green-600 hover:bg-green-700"
              data-testid="save-new-label-btn"
            >
              <Check className="w-3 h-3 mr-1" />
              Add
            </Button>
            <button onClick={() => setShowAddForm(false)} className="p-1 text-gray-400 hover:text-gray-600">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-[10px] text-gray-500 mr-1">Color:</span>
            {PRESET_COLORS.map(c => (
              <button
                key={c.name}
                onClick={() => setSelectedColor(c)}
                className={`w-5 h-5 rounded-full border-2 transition-all ${
                  selectedColor.color === c.color ? 'border-gray-800 scale-110' : 'border-gray-200'
                }`}
                style={{ backgroundColor: c.color }}
                title={c.name}
              />
            ))}
          </div>
          {newName.trim() && (
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-gray-500">Preview:</span>
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                style={{ backgroundColor: selectedColor.bg, color: selectedColor.text }}
              >
                <Tag className="w-3 h-3" />
                {newName.trim()}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default LabelManager;
