import React, { useState, useEffect, useCallback } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../../../components/ui/dialog';
import { Button } from '../../../../components/ui/button';
import { Clock, Undo2, ChevronDown, ChevronRight, Loader2, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const formatTimeAgo = (isoString) => {
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
};

const formatFieldName = (key) =>
  key.replace(/[_-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

const BulkEditHistory = ({ open, onClose, onUndoComplete, supplier }) => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [undoingId, setUndoingId] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    try {
      const url = supplier
        ? `${API_URL}/api/bulk-edit-tools/history?limit=30&supplier=${supplier}`
        : `${API_URL}/api/bulk-edit-tools/history?limit=30`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (err) {
      console.error('Failed to fetch history:', err);
    } finally {
      setLoading(false);
    }
  }, [supplier]);

  useEffect(() => {
    if (open) fetchHistory();
  }, [open, fetchHistory]);

  const handleUndo = async (entryId) => {
    if (!window.confirm('This will revert all products to their state before this edit. Continue?')) return;

    setUndoingId(entryId);
    try {
      const res = await fetch(`${API_URL}/api/bulk-edit-tools/history/${entryId}/undo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (res.ok) {
        const result = await res.json();
        toast.success(`Undo complete: ${result.restored_count} products restored`);
        fetchHistory();
        if (onUndoComplete) onUndoComplete();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to undo');
      }
    } catch (err) {
      toast.error('Failed to undo edit');
    } finally {
      setUndoingId(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[80vh] flex flex-col" data-testid="bulk-edit-history-dialog">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-blue-600" />
            Bulk Edit History
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-2 py-2 min-h-0">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
            </div>
          ) : history.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Clock className="w-8 h-8 mx-auto mb-2 text-gray-300" />
              <p className="font-medium">No edit history yet</p>
              <p className="text-sm">Your bulk edits will appear here</p>
            </div>
          ) : (
            history.map((entry) => {
              const isExpanded = expandedId === entry.id;
              const changes = entry.changes_summary || {};
              const changeKeys = Object.keys(changes);

              return (
                <div
                  key={entry.id}
                  className={`border rounded-lg transition-colors ${
                    entry.undone ? 'bg-gray-50 border-gray-200 opacity-60' : 'bg-white border-gray-200'
                  }`}
                  data-testid={`history-entry-${entry.id}`}
                >
                  {/* Header */}
                  <div
                    className="flex items-center gap-3 p-3 cursor-pointer"
                    onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                  >
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-gray-400 shrink-0" />
                    )}

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-800">
                          {entry.product_count} product{entry.product_count !== 1 ? 's' : ''}
                        </span>
                        <span className="text-xs text-gray-400">{formatTimeAgo(entry.timestamp)}</span>
                        {entry.undone && (
                          <span className="px-1.5 py-0.5 bg-gray-200 text-gray-600 rounded text-xs">Undone</span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 truncate mt-0.5">
                        {changeKeys.length > 0
                          ? changeKeys.slice(0, 4).map(k => formatFieldName(k)).join(', ')
                          + (changeKeys.length > 4 ? ` +${changeKeys.length - 4} more` : '')
                          : entry.action}
                      </p>
                    </div>

                    {!entry.undone && entry.before_snapshot?.length > 0 && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleUndo(entry.id);
                        }}
                        disabled={undoingId === entry.id}
                        className="h-7 text-xs gap-1 border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700 shrink-0"
                        data-testid={`undo-btn-${entry.id}`}
                      >
                        {undoingId === entry.id ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Undo2 className="w-3 h-3" />
                        )}
                        Undo
                      </Button>
                    )}
                  </div>

                  {/* Expanded Details */}
                  {isExpanded && (
                    <div className="border-t px-3 py-2 space-y-1.5 bg-gray-50">
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                        <div>
                          <span className="text-gray-400">Time:</span>{' '}
                          <span className="text-gray-700">{new Date(entry.timestamp).toLocaleString()}</span>
                        </div>
                        <div>
                          <span className="text-gray-400">User:</span>{' '}
                          <span className="text-gray-700">{entry.user}</span>
                        </div>
                        <div>
                          <span className="text-gray-400">Mode:</span>{' '}
                          <span className="text-gray-700">{entry.mode}</span>
                        </div>
                        <div>
                          <span className="text-gray-400">ID Field:</span>{' '}
                          <span className="text-gray-700">{entry.id_field}</span>
                        </div>
                      </div>

                      {changeKeys.length > 0 && (
                        <div className="mt-2">
                          <p className="text-xs font-medium text-gray-600 mb-1">Changes Applied:</p>
                          <div className="flex flex-wrap gap-1">
                            {changeKeys.map((key) => (
                              <span
                                key={key}
                                className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-xs"
                              >
                                {formatFieldName(key)}: {typeof changes[key] === 'object'
                                  ? (Array.isArray(changes[key]) ? changes[key].join(', ') : JSON.stringify(changes[key]))
                                  : String(changes[key])}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {entry.undone && (
                        <div className="flex items-center gap-1.5 text-xs text-gray-500 mt-1">
                          <CheckCircle className="w-3 h-3 text-green-500" />
                          Undone at {entry.undone_at ? new Date(entry.undone_at).toLocaleString() : 'unknown time'}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default BulkEditHistory;
