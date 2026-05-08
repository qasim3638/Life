import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../../../../components/ui/dialog';
import { Button } from '../../../../components/ui/button';
import { Input } from '../../../../components/ui/input';
import { FileText, Upload, Trash2, Download, Loader2, X, CheckSquare, File, GripVertical } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../../../../lib/api';

const DOCUMENT_TYPES = [
  "Technical Datasheet",
  "Safety Datasheet",
  "Installation Guide",
  "Product Brochure",
  "Warranty Information",
  "Care & Maintenance",
  "Certificate",
  "Other",
];

const API_URL = process.env.REACT_APP_BACKEND_URL;

const formatFileSize = (bytes) => {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const ProductDocumentsModal = ({ open, onOpenChange, products, selectedProducts }) => {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({}); // { fileIndex: 'pending'|'uploading'|'done'|'error' }
  const [pendingFiles, setPendingFiles] = useState([]); // Array of { file, displayName, documentType }
  const [applyToAll, setApplyToAll] = useState(true);
  const [deleting, setDeleting] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const dropZoneRef = useRef(null);
  const fileInputRef = useRef(null);

  const productList = products || [];
  const productKeys = productList.map(p => `${p.supplier || 'unknown'}|||${p.sku || p.supplier_code || p._id}`);
  const isBulk = productList.length > 1;

  const fetchDocuments = useCallback(async () => {
    if (!productKeys.length) return;
    setLoading(true);
    try {
      const res = await api.getProductDocumentsBulk(productKeys);
      setDocuments(res.data || []);
    } catch (err) {
      console.error('Failed to fetch documents:', err);
    } finally {
      setLoading(false);
    }
  }, [productKeys.join(',')]);

  useEffect(() => {
    if (open) {
      fetchDocuments();
      setPendingFiles([]);
      setApplyToAll(true);
      setUploadProgress({});
    }
  }, [open, fetchDocuments]);

  // Process files (from input or drag)
  const processFiles = (fileList) => {
    const newFiles = [];
    for (const file of fileList) {
      if (file.type !== 'application/pdf') {
        toast.error(`"${file.name}" is not a PDF — skipped`);
        continue;
      }
      if (file.size > 100 * 1024 * 1024) {
        toast.error(`"${file.name}" is too large (max 100MB) — skipped`);
        continue;
      }
      // Check for duplicates
      const alreadyAdded = pendingFiles.some(pf => pf.file.name === file.name && pf.file.size === file.size);
      if (alreadyAdded) continue;

      newFiles.push({
        file,
        displayName: file.name.replace(/\.pdf$/i, ''),
        documentType: 'Technical Datasheet',
      });
    }
    if (newFiles.length > 0) {
      setPendingFiles(prev => [...prev, ...newFiles]);
    }
  };

  // File input change handler
  const handleFileInputChange = (e) => {
    if (e.target.files?.length) {
      processFiles(Array.from(e.target.files));
      e.target.value = ''; // Reset so same file can be re-selected
    }
  };

  // Drag & Drop handlers
  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    // Only set to false if we're actually leaving the drop zone
    if (dropZoneRef.current && !dropZoneRef.current.contains(e.relatedTarget)) {
      setIsDragOver(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files?.length) {
      processFiles(Array.from(e.dataTransfer.files));
    }
  };

  // Remove a pending file
  const removePendingFile = (index) => {
    setPendingFiles(prev => prev.filter((_, i) => i !== index));
    setUploadProgress(prev => {
      const updated = { ...prev };
      delete updated[index];
      return updated;
    });
  };

  // Update pending file metadata
  const updatePendingFile = (index, field, value) => {
    setPendingFiles(prev => prev.map((f, i) => i === index ? { ...f, [field]: value } : f));
  };

  // Upload all pending files
  const handleUploadAll = async () => {
    if (pendingFiles.length === 0) {
      toast.error('No files to upload');
      return;
    }

    // Validate all have display names
    const invalid = pendingFiles.findIndex(f => !f.displayName.trim());
    if (invalid >= 0) {
      toast.error(`Please enter a display name for "${pendingFiles[invalid].file.name}"`);
      return;
    }

    const keys = applyToAll ? productKeys : [productKeys[0]];
    if (!keys.length) return;

    setUploading(true);
    const progress = {};
    pendingFiles.forEach((_, i) => { progress[i] = 'pending'; });
    setUploadProgress(progress);

    let successCount = 0;
    let failCount = 0;
    const fileResults = []; // Track per-file success/failure

    for (let i = 0; i < pendingFiles.length; i++) {
      const pf = pendingFiles[i];
      setUploadProgress(prev => ({ ...prev, [i]: 'uploading' }));

      try {
        const formData = new FormData();
        formData.append('file', pf.file);
        formData.append('display_name', pf.displayName.trim());
        formData.append('document_type', pf.documentType);
        formData.append('product_keys', JSON.stringify(keys));

        await api.uploadProductDocument(formData);
        setUploadProgress(prev => ({ ...prev, [i]: 'done' }));
        fileResults.push('done');
        successCount++;
      } catch (err) {
        console.error(`Upload error for ${pf.file.name}:`, err);
        const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
        toast.error(`Failed: ${pf.file.name} — ${errorMsg}`);
        setUploadProgress(prev => ({ ...prev, [i]: 'error' }));
        fileResults.push('error');
        failCount++;
      }
    }

    if (successCount > 0) {
      toast.success(`Uploaded ${successCount} PDF${successCount > 1 ? 's' : ''} to ${keys.length} product${keys.length > 1 ? 's' : ''}`);
      fetchDocuments();
    }

    // Clear all if everything succeeded, otherwise keep failed ones
    if (failCount === 0) {
      setPendingFiles([]);
      setUploadProgress({});
    } else {
      // Keep only failed files
      setPendingFiles(prev => prev.filter((_, i) => fileResults[i] === 'error'));
      setUploadProgress({});
    }

    setUploading(false);
  };

  const handleDelete = async (doc) => {
    setDeleting(doc.id);
    try {
      await api.deleteProductDocument(doc.id);
      toast.success(`Deleted "${doc.display_name}"`);
      fetchDocuments();
    } catch (err) {
      toast.error('Failed to delete document');
    } finally {
      setDeleting(null);
    }
  };

  const handleDetach = async (doc) => {
    try {
      await api.detachProductDocument(doc.id, productKeys);
      toast.success(`Removed "${doc.display_name}" from selected product${isBulk ? 's' : ''}`);
      fetchDocuments();
    } catch (err) {
      toast.error('Failed to remove document');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-red-600" />
            Product Documents
          </DialogTitle>
          <DialogDescription>
            {isBulk
              ? `Upload and manage PDFs for ${productList.length} selected products`
              : `Manage PDFs for: ${productList[0]?.product_name || productList[0]?.name || productList[0]?.sku}`}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-5 py-2">
          {/* === DRAG & DROP UPLOAD ZONE === */}
          <div
            ref={dropZoneRef}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => !uploading && fileInputRef.current?.click()}
            className={`relative border-2 border-dashed rounded-lg p-5 transition-all cursor-pointer ${
              isDragOver
                ? 'border-blue-500 bg-blue-50 scale-[1.01]'
                : pendingFiles.length > 0
                  ? 'border-green-300 bg-green-50/50'
                  : 'border-gray-300 bg-gray-50 hover:border-gray-400 hover:bg-gray-100'
            }`}
            data-testid="pdf-drop-zone"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              multiple
              onChange={handleFileInputChange}
              className="hidden"
              data-testid="pdf-file-input"
            />

            <div className="text-center">
              <Upload className={`w-8 h-8 mx-auto mb-2 ${isDragOver ? 'text-blue-500 animate-bounce' : 'text-gray-400'}`} />
              <p className={`text-sm font-medium ${isDragOver ? 'text-blue-600' : 'text-gray-600'}`}>
                {isDragOver ? 'Drop PDFs here...' : 'Drag & drop PDF files here'}
              </p>
              <p className="text-xs text-gray-400 mt-1">or click to browse &middot; Multiple files supported &middot; Max 100MB each</p>
            </div>
          </div>

          {/* === PENDING FILES LIST === */}
          {pendingFiles.length > 0 && (
            <div className="space-y-3" data-testid="pending-files-list">
              <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                <File className="w-4 h-4" />
                Ready to Upload
                <span className="text-xs font-normal text-gray-500">({pendingFiles.length} file{pendingFiles.length > 1 ? 's' : ''})</span>
              </h3>

              <div className="space-y-2 max-h-60 overflow-y-auto">
                {pendingFiles.map((pf, idx) => {
                  const status = uploadProgress[idx];
                  return (
                    <div
                      key={`${pf.file.name}-${idx}`}
                      className={`flex items-start gap-2 p-2.5 border rounded-lg transition-all ${
                        status === 'done' ? 'bg-green-50 border-green-200' :
                        status === 'error' ? 'bg-red-50 border-red-200' :
                        status === 'uploading' ? 'bg-blue-50 border-blue-200' :
                        'bg-white border-gray-200'
                      }`}
                      data-testid={`pending-file-${idx}`}
                    >
                      {/* Status icon */}
                      <div className="pt-1.5 flex-shrink-0">
                        {status === 'done' ? (
                          <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
                            <svg className="w-3 h-3 text-white" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                          </div>
                        ) : status === 'uploading' ? (
                          <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                        ) : status === 'error' ? (
                          <div className="w-5 h-5 rounded-full bg-red-500 flex items-center justify-center">
                            <X className="w-3 h-3 text-white" />
                          </div>
                        ) : (
                          <FileText className="w-5 h-5 text-red-400" />
                        )}
                      </div>

                      {/* File info and controls */}
                      <div className="flex-1 min-w-0 space-y-1.5">
                        <div className="flex items-center gap-2">
                          <span title={pf.file.name} className="text-xs text-gray-500 truncate flex-1">{pf.file.name} ({formatFileSize(pf.file.size)})</span>
                          {status === 'error' && <span className="text-xs text-red-600 font-medium">Failed</span>}
                        </div>

                        {/* Display name input */}
                        <Input
                          value={pf.displayName}
                          onChange={(e) => updatePendingFile(idx, 'displayName', e.target.value)}
                          placeholder="Display name"
                          className="h-7 text-xs"
                          disabled={uploading}
                          data-testid={`pending-file-name-${idx}`}
                        />

                        {/* Document type selector */}
                        <select
                          value={pf.documentType}
                          onChange={(e) => updatePendingFile(idx, 'documentType', e.target.value)}
                          className="w-full px-2 py-1 border rounded text-xs bg-white"
                          disabled={uploading}
                          data-testid={`pending-file-type-${idx}`}
                        >
                          {DOCUMENT_TYPES.map(type => (
                            <option key={type} value={type}>{type}</option>
                          ))}
                        </select>
                      </div>

                      {/* Remove button */}
                      {!uploading && (
                        <button
                          onClick={(e) => { e.stopPropagation(); removePendingFile(idx); }}
                          className="p-1 text-gray-400 hover:text-red-500 transition flex-shrink-0"
                          data-testid={`remove-pending-file-${idx}`}
                        >
                          <X className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Apply to All checkbox */}
              {isBulk && (
                <label className="flex items-center gap-2 px-2 py-1.5 rounded bg-blue-50 border border-blue-200 cursor-pointer hover:bg-blue-100 transition">
                  <input
                    type="checkbox"
                    checked={applyToAll}
                    onChange={(e) => setApplyToAll(e.target.checked)}
                    className="rounded"
                    data-testid="pdf-apply-all-checkbox"
                  />
                  <CheckSquare className="w-4 h-4 text-blue-600" />
                  <span className="text-sm text-blue-700">
                    Apply to all {productList.length} selected products
                  </span>
                </label>
              )}

              {/* Upload All Button */}
              <Button
                onClick={handleUploadAll}
                disabled={uploading || pendingFiles.length === 0}
                className="w-full bg-red-600 hover:bg-red-700 text-white"
                data-testid="pdf-upload-button"
              >
                {uploading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Uploading {pendingFiles.length} file{pendingFiles.length > 1 ? 's' : ''}...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4 mr-2" /> Upload {pendingFiles.length} PDF{pendingFiles.length > 1 ? 's' : ''}
                  </>
                )}
              </Button>
            </div>
          )}

          {/* === EXISTING DOCUMENTS === */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Attached Documents
              {documents.length > 0 && (
                <span className="text-xs font-normal text-gray-500">({documents.length})</span>
              )}
            </h3>

            {loading ? (
              <div className="flex items-center justify-center py-8 text-gray-400">
                <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading documents...
              </div>
            ) : documents.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <FileText className="w-10 h-10 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No documents attached yet</p>
              </div>
            ) : (
              <div className="space-y-2">
                {documents.map(doc => (
                  <div
                    key={doc.id}
                    className="flex items-center gap-3 p-3 border rounded-lg bg-white hover:bg-gray-50 transition group"
                    data-testid={`doc-item-${doc.id}`}
                  >
                    <div className="w-10 h-10 bg-red-50 border border-red-200 rounded-lg flex items-center justify-center flex-shrink-0">
                      <FileText className="w-5 h-5 text-red-600" />
                    </div>

                    <div className="flex-1 min-w-0">
                      <p title={doc.display_name} className="text-sm font-medium text-gray-800 truncate">{doc.display_name}</p>
                      <div className="flex items-center gap-2 text-xs text-gray-500">
                        <span className="px-1.5 py-0.5 bg-gray-100 rounded text-gray-600">{doc.document_type}</span>
                        <span>{formatFileSize(doc.file_size)}</span>
                        {doc.product_keys && (
                          <span>{doc.product_keys.length} product{doc.product_keys.length > 1 ? 's' : ''}</span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-blue-600 hover:text-blue-700 hover:bg-blue-50"
                        onClick={() => window.open(`${API_URL}/api/product-documents/${doc.id}/download`, '_blank')}
                        title="Download"
                        data-testid={`download-doc-${doc.id}`}
                      >
                        <Download className="w-4 h-4" />
                      </Button>
                      {isBulk ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-orange-600 hover:text-orange-700 hover:bg-orange-50"
                          onClick={() => handleDetach(doc)}
                          title="Remove from selected products"
                          data-testid={`detach-doc-${doc.id}`}
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      ) : null}
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-red-500 hover:text-red-700 hover:bg-red-50"
                        onClick={() => handleDelete(doc)}
                        disabled={deleting === doc.id}
                        title="Delete permanently"
                        data-testid={`delete-doc-${doc.id}`}
                      >
                        {deleting === doc.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ProductDocumentsModal;
