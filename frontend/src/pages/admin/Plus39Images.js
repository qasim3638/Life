import React, { useState, useEffect, useCallback, useRef } from 'react';
import { X, Upload, Image, Trash2, RefreshCw, Plus, Check, ZoomIn, Package, CheckSquare, Square, Star, GripVertical } from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function Plus39Images() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({ total: 0, withImages: 0, totalImages: 0 });
  const [productsBySize, setProductsBySize] = useState({});
  const [selectedSize, setSelectedSize] = useState('all');
  const [dragOverProduct, setDragOverProduct] = useState(null);
  const [zoomedImage, setZoomedImage] = useState(null);
  const [uploadingFor, setUploadingFor] = useState(null);
  const [deletingImages, setDeletingImages] = useState(new Set());
  
  // Bulk delete state for images
  const [selectedImages, setSelectedImages] = useState({}); // { productId: [imageUrl, imageUrl] }
  const [bulkDeleteMode, setBulkDeleteMode] = useState(false);
  
  // Image reorder state
  const [draggedImage, setDraggedImage] = useState(null); // { productId, index }
  
  const bulkInputRef = useRef(null);
  const scrollContainerRef = useRef(null);

  const fetchProducts = useCallback(async (preserveScroll = false) => {
    const scrollPosition = scrollContainerRef.current?.scrollTop || 0;
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/supplier-sync/products?supplier=Plus39&limit=500`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        const productList = data.products || [];
        setProducts(productList);
        
        // Calculate stats
        const withImages = productList.filter(p => p.images && p.images.length > 0).length;
        const totalImages = productList.reduce((sum, p) => sum + (p.images?.length || 0), 0);
        setStats({ total: productList.length, withImages, totalImages });
        
        // Group by size
        const bySize = {};
        productList.forEach(p => {
          const size = extractSize(p.name || p.product_name || '') || 'Other';
          if (!bySize[size]) {
            bySize[size] = { products: [], withImages: 0, totalImages: 0 };
          }
          bySize[size].products.push(p);
          if (p.images && p.images.length > 0) {
            bySize[size].withImages++;
            bySize[size].totalImages += p.images.length;
          }
        });
        setProductsBySize(bySize);
        
        // Restore scroll position
        if (preserveScroll && scrollContainerRef.current) {
          setTimeout(() => {
            scrollContainerRef.current.scrollTop = scrollPosition;
          }, 50);
        }
      }
    } catch (error) {
      console.error('Failed to fetch products:', error);
      toast.error('Failed to fetch products');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const extractSize = (name) => {
    const sizeMatch = name.match(/(\d+)\s*x\s*(\d+)\s*(cm)?/i);
    if (sizeMatch) {
      return `${sizeMatch[1]}x${sizeMatch[2]}cm`;
    }
    return null;
  };

  const handleDrop = async (e, productId) => {
    e.preventDefault();
    setDragOverProduct(null);
    
    const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
    if (files.length === 0) return;
    
    await uploadImages(productId, files);
  };

  const handleFileSelect = async (productId, files) => {
    const imageFiles = Array.from(files).filter(f => f.type.startsWith('image/'));
    if (imageFiles.length === 0) return;
    
    await uploadImages(productId, imageFiles);
  };

  const uploadImages = async (productId, files) => {
    setUploadingFor(productId);
    
    for (const file of files) {
      const formData = new FormData();
      formData.append('image', file);
      formData.append('product_id', productId);
      formData.append('supplier', 'Plus39');

      try {
        const token = localStorage.getItem('token');
        const response = await fetch(`${API_URL}/api/supplier-sync/upload-product-image`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
          body: formData
        });

        if (!response.ok) {
          const error = await response.json();
          toast.error(error.detail || 'Failed to upload image');
        }
      } catch (error) {
        console.error('Upload failed:', error);
        toast.error('Failed to upload image');
      }
    }
    
    setUploadingFor(null);
    toast.success(`${files.length} image(s) uploaded`);
    fetchProducts(true); // Preserve scroll
  };

  const handleBulkUpload = async (files) => {
    const imageFiles = Array.from(files).filter(f => f.type.startsWith('image/'));
    if (imageFiles.length === 0) return;

    toast.info(`Processing ${imageFiles.length} images for auto-matching...`);
    
    // Try to auto-match based on filename
    for (const file of imageFiles) {
      const filename = file.name.toLowerCase().replace(/\.[^/.]+$/, '');
      const matchedProduct = products.find(p => {
        const productName = (p.name || p.product_name || '').toLowerCase();
        const sku = (p.sku || '').toLowerCase();
        return productName.includes(filename) || sku.includes(filename) || filename.includes(sku);
      });

      if (matchedProduct) {
        await uploadImages(matchedProduct._id, [file]);
      } else {
        toast.warning(`No match found for: ${file.name}`);
      }
    }
  };

  // Single image delete - optimistic update, no full refresh
  const handleDeleteImage = async (productId, imageUrl, e) => {
    e?.stopPropagation();
    
    // Mark as deleting
    setDeletingImages(prev => new Set([...prev, imageUrl]));
    
    // Optimistic update - remove from UI immediately
    setProducts(prev => prev.map(p => {
      if (p._id === productId) {
        return { ...p, images: (p.images || []).filter(img => img !== imageUrl) };
      }
      return p;
    }));

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/supplier-sync/delete-product-image`, {
        method: 'DELETE',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ product_id: productId, image_url: imageUrl })
      });

      if (response.ok) {
        toast.success('Image deleted');
        // Update stats
        setStats(prev => ({ ...prev, totalImages: prev.totalImages - 1 }));
      } else {
        // Revert on failure
        toast.error('Failed to delete image');
        fetchProducts(true);
      }
    } catch (error) {
      toast.error('Failed to delete image');
      fetchProducts(true);
    } finally {
      setDeletingImages(prev => {
        const next = new Set(prev);
        next.delete(imageUrl);
        return next;
      });
    }
  };

  // Image reorder handlers
  const handleImageDragStart = (e, productId, index) => {
    setDraggedImage({ productId, index });
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', e.target.outerHTML);
  };

  const handleImageDragEnd = () => {
    setDraggedImage(null);
  };

  const handleImageDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleImageDrop = async (e, productId, dropIndex) => {
    e.preventDefault();
    if (!draggedImage || draggedImage.productId !== productId || draggedImage.index === dropIndex) {
      setDraggedImage(null);
      return;
    }

    // Get the product
    const product = products.find(p => p._id === productId);
    if (!product || !product.images) return;

    // Reorder images locally
    const newImages = [...product.images];
    const [draggedImg] = newImages.splice(draggedImage.index, 1);
    newImages.splice(dropIndex, 0, draggedImg);

    // Optimistic update
    setProducts(prev => prev.map(p => {
      if (p._id === productId) {
        return { ...p, images: newImages };
      }
      return p;
    }));

    // Save to backend
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/supplier-sync/reorder-images`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ product_id: productId, images: newImages })
      });

      if (response.ok) {
        toast.success(dropIndex === 0 ? 'Primary image updated' : 'Image order updated');
      } else {
        toast.error('Failed to save image order');
        fetchProducts(true);
      }
    } catch (error) {
      toast.error('Failed to save image order');
      fetchProducts(true);
    }

    setDraggedImage(null);
  };

  const handleSetPrimaryImage = async (productId, index) => {
    if (index === 0) return;

    const product = products.find(p => p._id === productId);
    if (!product || !product.images) return;

    const newImages = [...product.images];
    const [primaryImg] = newImages.splice(index, 1);
    newImages.unshift(primaryImg);

    // Optimistic update
    setProducts(prev => prev.map(p => {
      if (p._id === productId) {
        return { ...p, images: newImages };
      }
      return p;
    }));

    // Save to backend
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/supplier-sync/reorder-images`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ product_id: productId, images: newImages })
      });

      if (response.ok) {
        toast.success('Primary image updated');
      } else {
        toast.error('Failed to update primary image');
        fetchProducts(true);
      }
    } catch (error) {
      toast.error('Failed to update primary image');
      fetchProducts(true);
    }
  };

  // Toggle image selection for bulk delete
  const toggleImageSelection = (productId, imageUrl) => {
    setSelectedImages(prev => {
      const productImages = prev[productId] || [];
      if (productImages.includes(imageUrl)) {
        const updated = productImages.filter(img => img !== imageUrl);
        if (updated.length === 0) {
          const { [productId]: _, ...rest } = prev;
          return rest;
        }
        return { ...prev, [productId]: updated };
      } else {
        return { ...prev, [productId]: [...productImages, imageUrl] };
      }
    });
  };

  // Select all images for a product
  const selectAllProductImages = (productId, images) => {
    setSelectedImages(prev => ({
      ...prev,
      [productId]: [...images]
    }));
  };

  // Deselect all images for a product
  const deselectAllProductImages = (productId) => {
    setSelectedImages(prev => {
      const { [productId]: _, ...rest } = prev;
      return rest;
    });
  };

  // Get total selected count
  const getTotalSelectedCount = () => {
    return Object.values(selectedImages).reduce((sum, imgs) => sum + imgs.length, 0);
  };

  // Bulk delete selected images
  const handleBulkDelete = async () => {
    const totalCount = getTotalSelectedCount();
    if (totalCount === 0) return;
    
    if (!window.confirm(`Delete ${totalCount} selected image(s)?`)) return;

    // Get all images to delete
    const deletePromises = [];
    const imagesToDelete = [];
    
    Object.entries(selectedImages).forEach(([productId, images]) => {
      images.forEach(imageUrl => {
        imagesToDelete.push({ productId, imageUrl });
      });
    });

    // Optimistic update - remove all from UI immediately
    setProducts(prev => prev.map(p => {
      const imagesToRemove = selectedImages[p._id] || [];
      if (imagesToRemove.length > 0) {
        return { ...p, images: (p.images || []).filter(img => !imagesToRemove.includes(img)) };
      }
      return p;
    }));

    // Clear selections
    setSelectedImages({});
    setBulkDeleteMode(false);

    // Delete all in parallel
    const token = localStorage.getItem('token');
    let successCount = 0;
    let failCount = 0;

    await Promise.all(imagesToDelete.map(async ({ productId, imageUrl }) => {
      try {
        const response = await fetch(`${API_URL}/api/supplier-sync/delete-product-image`, {
          method: 'DELETE',
          headers: { 
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ product_id: productId, image_url: imageUrl })
        });
        if (response.ok) {
          successCount++;
        } else {
          failCount++;
        }
      } catch (error) {
        failCount++;
      }
    }));

    // Update stats
    setStats(prev => ({ ...prev, totalImages: prev.totalImages - successCount }));

    if (failCount === 0) {
      toast.success(`Deleted ${successCount} image(s)`);
    } else {
      toast.warning(`Deleted ${successCount}, failed ${failCount}`);
      fetchProducts(true); // Refresh to get accurate state
    }
  };

  const handleStockStatusChange = async (productId, status) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/supplier-sync/update-product-stock-status`, {
        method: 'PUT',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          product_id: productId, 
          stock_status: status,
          in_stock: status === 'in_stock' || status === 'always_in_stock'
        })
      });

      if (response.ok) {
        toast.success('Stock status updated');
        setProducts(prev => prev.map(p => 
          p._id === productId ? { ...p, stock_status: status, in_stock: status === 'in_stock' || status === 'always_in_stock' } : p
        ));
      } else {
        toast.error('Failed to update stock status');
      }
    } catch (error) {
      toast.error('Failed to update stock status');
    }
  };

  const filteredProducts = selectedSize === 'all' 
    ? products 
    : (productsBySize[selectedSize]?.products || []);

  const goBack = () => {
    window.history.back();
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-6xl h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-3">
            <Package className="w-6 h-6 text-emerald-600" />
            <div>
              <h1 className="text-xl font-bold text-gray-900">Plus39 Tiles</h1>
              <p className="text-sm text-gray-500">
                {stats.withImages} of {stats.total} products have images ({stats.totalImages} total images)
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Bulk Delete Toggle */}
            <button
              onClick={() => {
                setBulkDeleteMode(!bulkDeleteMode);
                if (bulkDeleteMode) setSelectedImages({});
              }}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-2 ${
                bulkDeleteMode 
                  ? 'bg-red-100 text-red-700 border border-red-300' 
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <Trash2 className="w-4 h-4" />
              {bulkDeleteMode ? 'Cancel Selection' : 'Bulk Delete'}
            </button>
            
            {/* Bulk Delete Action */}
            {bulkDeleteMode && getTotalSelectedCount() > 0 && (
              <button
                onClick={handleBulkDelete}
                className="px-3 py-1.5 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 flex items-center gap-2"
              >
                <Trash2 className="w-4 h-4" />
                Delete {getTotalSelectedCount()} Selected
              </button>
            )}
            
            <button onClick={goBack} className="p-2 hover:bg-gray-100 rounded-full">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Left Sidebar - Products by Size */}
          <div className="w-64 border-r bg-gray-50 p-4 overflow-y-auto">
            <h3 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <Package className="w-4 h-4" />
              Products by Size
            </h3>
            
            <button
              onClick={() => setSelectedSize('all')}
              className={`w-full text-left p-2 rounded-lg mb-2 ${selectedSize === 'all' ? 'bg-emerald-100 text-emerald-700' : 'hover:bg-gray-100'}`}
            >
              All Sizes ({products.length})
            </button>

            {Object.entries(productsBySize).sort().map(([size, data]) => {
              const progress = data.products.length > 0 ? (data.withImages / data.products.length) * 100 : 0;
              const isComplete = progress === 100;
              const missing = data.products.length - data.withImages;
              
              return (
                <button
                  key={size}
                  onClick={() => setSelectedSize(size)}
                  className={`w-full text-left p-3 rounded-lg mb-2 ${selectedSize === size ? 'bg-emerald-100 border border-emerald-300' : 'hover:bg-gray-100 border border-transparent'}`}
                >
                  <div className="font-medium text-sm">{size}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {data.products.length} products • {data.totalImages} images
                  </div>
                  <div className="mt-2 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div 
                      className={`h-full ${isComplete ? 'bg-green-500' : 'bg-emerald-500'}`}
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  {missing > 0 && (
                    <span className="text-xs text-orange-600 mt-1 inline-block">{missing} missing</span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Center - Products List */}
          <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-700 flex items-center gap-2">
                <Package className="w-4 h-4" />
                Products ({filteredProducts.length})
              </h2>
              <button 
                onClick={() => fetchProducts()}
                disabled={loading}
                className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>

            {bulkDeleteMode && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                Click on images to select them for bulk deletion. Click "Delete Selected" when ready.
              </div>
            )}

            {loading ? (
              <div className="flex justify-center py-12">
                <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
              </div>
            ) : (
              <div className="space-y-3">
                {filteredProducts.map(product => {
                  const productSelectedImages = selectedImages[product._id] || [];
                  const allSelected = product.images?.length > 0 && productSelectedImages.length === product.images.length;
                  
                  return (
                    <div
                      key={product._id || product.sku}
                      className={`border rounded-xl p-4 transition-all ${
                        dragOverProduct === product._id 
                          ? 'border-emerald-500 bg-emerald-50 ring-2 ring-emerald-200' 
                          : 'border-gray-200 hover:border-gray-300 hover:shadow-sm'
                      }`}
                      onDragOver={(e) => { e.preventDefault(); setDragOverProduct(product._id); }}
                      onDragLeave={() => setDragOverProduct(null)}
                      onDrop={(e) => handleDrop(e, product._id)}
                    >
                      {/* Product Header */}
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <h3 className="font-semibold text-gray-900">
                            {product.product_name || product.name || 'Unnamed Product'}
                          </h3>
                          <p className="text-sm text-gray-500">
                            <span className="inline-flex items-center gap-1">
                              <span className="bg-emerald-100 text-emerald-700 text-xs font-medium px-1.5 py-0.5 rounded">
                                {product.supplier || 'Plus39'}
                              </span>
                              <span className="text-gray-400">:</span>
                              <span className="text-gray-600 truncate max-w-[200px]" title={product.supplier_product_name || product.name || ''}>
                                {product.supplier_product_name || product.name || 'N/A'}
                              </span>
                            </span>
                          </p>
                          <p className="text-xs text-gray-400 mt-0.5">
                            {product.size || extractSize(product.name || product.product_name || '') || 'Size N/A'}
                            {product.finish && ` • ${product.finish}`}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          {/* Select All / Deselect All for bulk delete */}
                          {bulkDeleteMode && product.images?.length > 0 && (
                            <button
                              onClick={() => allSelected ? deselectAllProductImages(product._id) : selectAllProductImages(product._id, product.images)}
                              className="text-xs px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 text-gray-600"
                            >
                              {allSelected ? 'Deselect All' : 'Select All'}
                            </button>
                          )}
                          
                          {/* Stock Status */}
                          <select
                            className="text-xs border rounded px-2 py-1 bg-green-500 text-white font-medium"
                            value={product.stock_status || (product.in_stock ? 'in_stock' : 'out_of_stock')}
                            onChange={(e) => handleStockStatusChange(product._id, e.target.value)}
                          >
                            <option value="in_stock">In Stock</option>
                            <option value="always_in_stock">Always In Stock</option>
                            <option value="out_of_stock">Out of Stock</option>
                          </select>
                          
                          {/* Add Images */}
                          <label className="cursor-pointer">
                            <span className="text-sm text-emerald-600 hover:text-emerald-700 hover:underline flex items-center gap-1 font-medium bg-emerald-50 px-2 py-1 rounded">
                              {uploadingFor === product._id ? (
                                <RefreshCw className="w-3 h-3 animate-spin" />
                              ) : (
                                <Plus className="w-3 h-3" />
                              )}
                              Add Images
                            </span>
                            <input
                              type="file"
                              multiple
                              accept="image/*"
                              className="hidden"
                              onChange={(e) => handleFileSelect(product._id, e.target.files)}
                              disabled={uploadingFor === product._id}
                            />
                          </label>
                        </div>
                      </div>

                      {/* Images Grid */}
                      <div className="flex flex-wrap gap-2">
                        {product.images && product.images.length > 0 ? (
                          product.images.map((img, idx) => {
                            const isSelected = productSelectedImages.includes(img);
                            const isDeleting = deletingImages.has(img);
                            const isDragging = draggedImage?.productId === product._id && draggedImage?.index === idx;
                            const isDropTarget = draggedImage?.productId === product._id && draggedImage?.index !== idx;
                            
                            return (
                              <div
                                key={idx}
                                className={`relative group ${isDeleting ? 'opacity-50' : ''} ${
                                  isDragging ? 'opacity-50 scale-95' : ''
                                } ${isDropTarget ? 'ring-2 ring-blue-400 ring-dashed' : ''}`}
                                draggable={!bulkDeleteMode}
                                onDragStart={(e) => !bulkDeleteMode && handleImageDragStart(e, product._id, idx)}
                                onDragEnd={handleImageDragEnd}
                                onDragOver={handleImageDragOver}
                                onDrop={(e) => handleImageDrop(e, product._id, idx)}
                              >
                                <img
                                  src={img}
                                  alt=""
                                  className={`w-20 h-20 object-cover rounded-lg border-2 cursor-grab active:cursor-grabbing transition-all ${
                                    isSelected 
                                      ? 'border-red-500 ring-2 ring-red-300' 
                                      : idx === 0 
                                        ? 'border-green-500 ring-2 ring-green-200'
                                        : 'border-gray-200 hover:border-emerald-400'
                                  }`}
                                  onError={(e) => { e.target.src = '/placeholder-image.png'; }}
                                  onClick={(e) => {
                                    if (bulkDeleteMode) {
                                      toggleImageSelection(product._id, img);
                                    } else {
                                      setZoomedImage(img);
                                    }
                                  }}
                                />
                                
                                {/* Primary badge */}
                                {idx === 0 && !bulkDeleteMode && (
                                  <span className="absolute -top-1 -left-1 bg-green-500 text-white text-[10px] px-1.5 py-0.5 rounded font-bold">
                                    Primary
                                  </span>
                                )}
                                
                                {/* Position number for non-primary */}
                                {idx > 0 && !bulkDeleteMode && (
                                  <span className="absolute -top-1 -left-1 bg-gray-500 text-white text-[10px] px-1.5 py-0.5 rounded font-bold">
                                    {idx + 1}
                                  </span>
                                )}
                                
                                {/* Selection checkbox in bulk mode */}
                                {bulkDeleteMode && (
                                  <div className={`absolute top-1 left-1 w-5 h-5 rounded flex items-center justify-center ${
                                    isSelected ? 'bg-red-500' : 'bg-white/80'
                                  }`}>
                                    {isSelected ? (
                                      <Check className="w-3 h-3 text-white" />
                                    ) : (
                                      <Square className="w-3 h-3 text-gray-400" />
                                    )}
                                  </div>
                                )}
                                
                                {/* Hover actions (non-bulk mode) */}
                                {!bulkDeleteMode && (
                                  <div className="absolute inset-0 bg-black/0 hover:bg-black/40 transition-opacity flex items-center justify-center gap-1 opacity-0 hover:opacity-100 rounded-lg">
                                    {/* Set as primary button */}
                                    {idx !== 0 && (
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleSetPrimaryImage(product._id, idx);
                                        }}
                                        className="p-1.5 bg-green-500 text-white rounded hover:bg-green-600"
                                        title="Set as primary"
                                      >
                                        <Star className="w-3 h-3" />
                                      </button>
                                    )}
                                    {/* Delete button */}
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleDeleteImage(product._id, img, e);
                                      }}
                                      disabled={isDeleting}
                                      className="p-1.5 bg-red-500 text-white rounded hover:bg-red-600"
                                      title="Delete image"
                                    >
                                      <Trash2 className="w-3 h-3" />
                                    </button>
                                  </div>
                                )}
                              </div>
                            );
                          })
                        ) : (
                          <div className="w-20 h-20 bg-gray-100 rounded-lg flex items-center justify-center border-2 border-dashed border-gray-300">
                            <span className="text-xs text-gray-400">No images</span>
                          </div>
                        )}
                      </div>
                      
                      {/* Drag hint */}
                      {product.images && product.images.length > 1 && !bulkDeleteMode && (
                        <p className="text-xs text-gray-400 mt-2 flex items-center gap-1">
                          <GripVertical className="w-3 h-3" />
                          Drag to reorder • First image = Primary
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Right Sidebar - Bulk Upload */}
          <div className="w-64 border-l bg-gray-50 p-4">
            <h3 className="font-semibold text-gray-700 flex items-center gap-2 mb-4">
              <Upload className="w-4 h-4" />
              Bulk Upload
            </h3>

            <div
              className="border-2 border-dashed border-gray-300 rounded-xl p-6 text-center hover:border-emerald-400 hover:bg-emerald-50 transition-colors cursor-pointer"
              onClick={() => bulkInputRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                handleBulkUpload(e.dataTransfer.files);
              }}
            >
              <Upload className="w-10 h-10 mx-auto text-gray-400 mb-2" />
              <p className="font-medium text-gray-700 text-sm">Drag & drop</p>
              <p className="text-xs text-gray-500">or click to select</p>
              <input
                ref={bulkInputRef}
                type="file"
                multiple
                accept="image/*"
                className="hidden"
                onChange={(e) => handleBulkUpload(e.target.files)}
              />
            </div>

            <div className="mt-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
              <p className="text-xs text-emerald-700">
                <strong>Tip:</strong> Name files like<br/>
                <code className="bg-emerald-100 px-1 rounded">Carrara_White.jpg</code><br/>
                for auto-matching
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Image Zoom Modal */}
      {zoomedImage && (
        <div 
          className="fixed inset-0 bg-black/90 flex items-center justify-center z-[60]"
          onClick={() => setZoomedImage(null)}
        >
          <button 
            className="absolute top-4 right-4 text-white hover:text-gray-300"
            onClick={() => setZoomedImage(null)}
          >
            <X className="w-8 h-8" />
          </button>
          <img 
            src={zoomedImage} 
            alt="Zoomed" 
            className="max-w-[90vw] max-h-[90vh] object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}
