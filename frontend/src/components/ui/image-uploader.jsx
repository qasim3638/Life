import React, { useState, useCallback, useRef } from 'react';
import { Upload, X, Check, Cloud, AlertCircle, Loader2, Image as ImageIcon, Trash2 } from 'lucide-react';
import { cn } from '../../lib/utils';

/**
 * ImageUploader - A reusable image upload component with:
 * - Drag and drop support
 * - Upload progress indicator
 * - Preview thumbnails
 * - R2 cloud storage confirmation
 * - Multiple file support
 */
export function ImageUploader({
  onUpload,
  onRemove,
  images = [],
  maxFiles = 10,
  maxSizeMB = 10,
  acceptedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'],
  uploadEndpoint,
  authToken,
  className,
  showStorageIndicator = true,
  allowMultiple = true,
  compact = false,
  disabled = false,
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({});
  const [uploadStatus, setUploadStatus] = useState({}); // 'uploading' | 'success' | 'error'
  const [previewUrls, setPreviewUrls] = useState({});
  const fileInputRef = useRef(null);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) setIsDragging(true);
  }, [disabled]);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const validateFile = (file) => {
    if (!acceptedTypes.includes(file.type)) {
      return { valid: false, error: `Invalid file type. Allowed: ${acceptedTypes.join(', ')}` };
    }
    if (file.size > maxSizeMB * 1024 * 1024) {
      return { valid: false, error: `File too large. Maximum size is ${maxSizeMB}MB` };
    }
    return { valid: true };
  };

  const createPreview = (file) => {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.readAsDataURL(file);
    });
  };

  const uploadFile = async (file, fileId) => {
    const formData = new FormData();
    formData.append('file', file);

    // Set initial status
    setUploadStatus(prev => ({ ...prev, [fileId]: 'uploading' }));
    setUploadProgress(prev => ({ ...prev, [fileId]: 0 }));

    try {
      const xhr = new XMLHttpRequest();
      
      // Track upload progress
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const progress = Math.round((e.loaded / e.total) * 100);
          setUploadProgress(prev => ({ ...prev, [fileId]: progress }));
        }
      });

      return new Promise((resolve, reject) => {
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const response = JSON.parse(xhr.responseText);
              setUploadStatus(prev => ({ ...prev, [fileId]: 'success' }));
              setUploadProgress(prev => ({ ...prev, [fileId]: 100 }));
              resolve(response);
            } catch (e) {
              reject(new Error('Invalid response'));
            }
          } else {
            reject(new Error(`Upload failed: ${xhr.status}`));
          }
        };
        
        xhr.onerror = () => {
          setUploadStatus(prev => ({ ...prev, [fileId]: 'error' }));
          reject(new Error('Network error'));
        };

        xhr.open('POST', uploadEndpoint);
        if (authToken) {
          xhr.setRequestHeader('Authorization', `Bearer ${authToken}`);
        }
        xhr.send(formData);
      });
    } catch (error) {
      setUploadStatus(prev => ({ ...prev, [fileId]: 'error' }));
      throw error;
    }
  };

  const handleFiles = async (files) => {
    if (disabled) return;
    
    const fileArray = Array.from(files).slice(0, maxFiles - images.length);
    const results = [];

    for (const file of fileArray) {
      const validation = validateFile(file);
      if (!validation.valid) {
        console.error(validation.error);
        continue;
      }

      const fileId = `${file.name}-${Date.now()}`;
      
      // Create preview immediately
      const preview = await createPreview(file);
      setPreviewUrls(prev => ({ ...prev, [fileId]: preview }));

      try {
        const result = await uploadFile(file, fileId);
        results.push({
          url: result.url || result.image_url,
          filename: result.filename,
          storage: result.storage,
          fileId,
        });
        
        // Clear preview after successful upload (the actual image URL will be used)
        setTimeout(() => {
          setPreviewUrls(prev => {
            const newPreviews = { ...prev };
            delete newPreviews[fileId];
            return newPreviews;
          });
        }, 2000);
      } catch (error) {
        console.error('Upload error:', error);
        // Keep preview for error state
      }
    }

    if (results.length > 0 && onUpload) {
      onUpload(results);
    }
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    if (disabled) return;
    
    const files = e.dataTransfer?.files;
    if (files?.length) {
      handleFiles(files);
    }
  }, [disabled]);

  const handleFileSelect = (e) => {
    const files = e.target.files;
    if (files?.length) {
      handleFiles(files);
    }
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleRemove = (index, imageUrl) => {
    if (onRemove) {
      onRemove(index, imageUrl);
    }
  };

  const isR2Url = (url) => {
    return url && (
      url.includes('images.tilestation.co.uk') ||
      url.includes('r2.dev') ||
      url.includes('r2.cloudflarestorage.com')
    );
  };

  // Render uploading items (in progress)
  const renderUploadingItems = () => {
    return Object.entries(previewUrls).map(([fileId, preview]) => {
      const progress = uploadProgress[fileId] || 0;
      const status = uploadStatus[fileId] || 'uploading';
      
      return (
        <div 
          key={fileId}
          className={cn(
            "relative rounded-lg overflow-hidden border-2",
            status === 'uploading' && "border-blue-400",
            status === 'success' && "border-green-400",
            status === 'error' && "border-red-400",
            compact ? "w-16 h-16" : "w-24 h-24"
          )}
        >
          <img 
            src={preview} 
            alt="Uploading" 
            className="w-full h-full object-cover opacity-70"
          />
          
          {/* Progress overlay */}
          <div className="absolute inset-0 bg-black/40 flex flex-col items-center justify-center">
            {status === 'uploading' && (
              <>
                <Loader2 className={cn("animate-spin text-white", compact ? "w-4 h-4" : "w-6 h-6")} />
                <span className={cn("text-white font-medium mt-1", compact ? "text-xs" : "text-sm")}>
                  {progress}%
                </span>
              </>
            )}
            {status === 'success' && (
              <div className="flex flex-col items-center">
                <Check className={cn("text-green-400", compact ? "w-4 h-4" : "w-6 h-6")} />
                <Cloud className={cn("text-green-400 mt-1", compact ? "w-3 h-3" : "w-4 h-4")} />
              </div>
            )}
            {status === 'error' && (
              <AlertCircle className={cn("text-red-400", compact ? "w-4 h-4" : "w-6 h-6")} />
            )}
          </div>
          
          {/* Progress bar */}
          {status === 'uploading' && (
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-gray-600">
              <div 
                className="h-full bg-blue-500 transition-all duration-200"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}
        </div>
      );
    });
  };

  // Render existing images
  const renderExistingImages = () => {
    return images.map((imageUrl, index) => (
      <div 
        key={`${imageUrl}-${index}`}
        className={cn(
          "relative rounded-lg overflow-hidden border-2 group",
          isR2Url(imageUrl) ? "border-green-400" : "border-gray-300",
          compact ? "w-16 h-16" : "w-24 h-24"
        )}
      >
        <img 
          src={imageUrl} 
          alt={`Image ${index + 1}`} 
          className="w-full h-full object-cover"
          onError={(e) => {
            e.target.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="%23f3f4f6" width="100" height="100"/><text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="%239ca3af" font-size="14">No Image</text></svg>';
          }}
        />
        
        {/* R2 indicator */}
        {showStorageIndicator && isR2Url(imageUrl) && (
          <div className={cn(
            "absolute top-1 left-1 bg-green-500 text-white rounded-full flex items-center gap-0.5 px-1",
            compact ? "text-[8px]" : "text-[10px]"
          )}>
            <Cloud className={compact ? "w-2 h-2" : "w-3 h-3"} />
            <span>R2</span>
          </div>
        )}
        
        {/* Primary badge */}
        {index === 0 && (
          <div className={cn(
            "absolute top-1 right-1 bg-blue-500 text-white rounded text-[10px] px-1",
            compact && "text-[8px]"
          )}>
            Primary
          </div>
        )}
        
        {/* Remove button */}
        {onRemove && (
          <button
            onClick={() => handleRemove(index, imageUrl)}
            className="absolute bottom-1 right-1 bg-red-500 hover:bg-red-600 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <Trash2 className={compact ? "w-3 h-3" : "w-4 h-4"} />
          </button>
        )}
      </div>
    ));
  };

  return (
    <div className={cn("space-y-3", className)}>
      {/* Existing images + uploading items */}
      {(images.length > 0 || Object.keys(previewUrls).length > 0) && (
        <div className="flex flex-wrap gap-2">
          {renderExistingImages()}
          {renderUploadingItems()}
        </div>
      )}
      
      {/* Upload area */}
      {images.length < maxFiles && (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !disabled && fileInputRef.current?.click()}
          className={cn(
            "border-2 border-dashed rounded-lg transition-all cursor-pointer",
            isDragging ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-gray-400",
            disabled && "opacity-50 cursor-not-allowed",
            compact ? "p-3" : "p-6"
          )}
        >
          <div className="flex flex-col items-center justify-center text-center">
            <Upload className={cn(
              "text-gray-400 mb-2",
              compact ? "w-6 h-6" : "w-10 h-10"
            )} />
            <p className={cn("text-gray-600", compact ? "text-xs" : "text-sm")}>
              {isDragging ? 'Drop images here' : 'Drag & drop images or click to browse'}
            </p>
            <p className={cn("text-gray-400 mt-1", compact ? "text-[10px]" : "text-xs")}>
              {allowMultiple ? `Up to ${maxFiles - images.length} more images` : 'Single image'} • Max {maxSizeMB}MB each
            </p>
            {showStorageIndicator && (
              <div className={cn(
                "flex items-center gap-1 mt-2 text-green-600",
                compact ? "text-[10px]" : "text-xs"
              )}>
                <Cloud className={compact ? "w-3 h-3" : "w-4 h-4"} />
                <span>Uploads to R2 Cloud Storage</span>
              </div>
            )}
          </div>
          
          <input
            ref={fileInputRef}
            type="file"
            accept={acceptedTypes.join(',')}
            multiple={allowMultiple}
            onChange={handleFileSelect}
            className="hidden"
            disabled={disabled}
          />
        </div>
      )}
    </div>
  );
}

/**
 * Compact version for inline use
 */
export function ImageUploaderCompact(props) {
  return <ImageUploader {...props} compact={true} />;
}

export default ImageUploader;
