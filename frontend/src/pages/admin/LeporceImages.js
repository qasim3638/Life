import React, { useState, useEffect, useCallback, useRef } from 'react';
import { X, Upload, Image, Trash2, RefreshCw, Plus, Check, ZoomIn, Package } from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function LeporceImages() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({ total: 0, withImages: 0, totalImages: 0 });
  const [productsBySize, setProductsBySize] = useState({});
  const [selectedSize, setSelectedSize] = useState('all');
  const [dragOverProduct, setDragOverProduct] = useState(null);
  const [hoveredImage, setHoveredImage] = useState(null);
  const [zoomedImage, setZoomedImage] = useState(null);
  const [uploadingFor, setUploadingFor] = useState(null);
  const bulkInputRef = useRef(null);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/supplier-sync/products?supplier=LEPORCE&limit=500`, {
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
      formData.append('supplier', 'LEPORCE');

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
    fetchProducts();
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

  const handleDeleteImage = async (productId, imageUrl, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this image?')) return;

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
        fetchProducts();
      } else {
        toast.error('Failed to delete image');
      }
    } catch (error) {
      toast.error('Failed to delete image');
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
        // Update local state
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
            <Package className="w-6 h-6 text-blue-600" />
            <div>
              <h1 className="text-xl font-bold text-gray-900">LEPORCE Tiles</h1>
              <p className="text-sm text-gray-500">
                {stats.withImages} of {stats.total} products have images ({stats.totalImages} total images)
              </p>
            </div>
          </div>
          <button onClick={goBack} className="p-2 hover:bg-gray-100 rounded-full">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Left Sidebar - Products by Size */}
          <div className="w-64 border-r bg-gray-50 p-4 overflow-y-auto">
            <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <h3 className="font-semibold text-amber-800 text-sm mb-1">Image Naming Tips</h3>
              <p className="text-xs text-amber-700">
                For best auto-matching, name files like: <br/>
                <code className="bg-amber-100 px-1 rounded">Carrara_White_60x120.jpg</code>
              </p>
            </div>

            <h3 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <Package className="w-4 h-4" />
              Products by Size
            </h3>
            
            <button
              onClick={() => setSelectedSize('all')}
              className={`w-full text-left p-2 rounded-lg mb-2 ${selectedSize === 'all' ? 'bg-blue-100 text-blue-700' : 'hover:bg-gray-100'}`}
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
                  className={`w-full text-left p-3 rounded-lg mb-2 ${selectedSize === size ? 'bg-blue-100 border border-blue-300' : 'hover:bg-gray-100 border border-transparent'}`}
                >
                  <div className="font-medium text-sm">{size}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    <span>📦 Products: {data.products.length}</span>
                    <br />
                    <span>🖼️ Images: {data.totalImages}</span>
                  </div>
                  <div className="mt-2 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div 
                      className={`h-full ${isComplete ? 'bg-green-500' : 'bg-blue-500'}`}
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  {isComplete ? (
                    <span className="text-xs text-green-600 mt-1 inline-block">Complete</span>
                  ) : missing > 0 ? (
                    <span className="text-xs text-orange-600 mt-1 inline-block">{missing} missing</span>
                  ) : null}
                </button>
              );
            })}
          </div>

          {/* Center - Products List */}
          <div className="flex-1 overflow-y-auto p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-700 flex items-center gap-2">
                <Package className="w-4 h-4" />
                Products ({filteredProducts.length})
              </h2>
              <button 
                onClick={fetchProducts}
                disabled={loading}
                className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>
            <p className="text-sm text-gray-500 mb-4">Click a product or drag & drop images directly onto it</p>

            {loading ? (
              <div className="flex justify-center py-12">
                <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
              </div>
            ) : (
              <div className="space-y-3">
                {filteredProducts.map(product => (
                  <div
                    key={product._id || product.sku}
                    className={`border rounded-xl p-4 transition-all ${
                      dragOverProduct === product._id 
                        ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200' 
                        : 'border-gray-200 hover:border-gray-300 hover:shadow-sm'
                    }`}
                    onDragOver={(e) => { e.preventDefault(); setDragOverProduct(product._id); }}
                    onDragLeave={() => setDragOverProduct(null)}
                    onDrop={(e) => handleDrop(e, product._id)}
                  >
                    <div className="flex gap-4">
                      {/* Images */}
                      <div className="flex gap-2 flex-shrink-0">
                        {product.images && product.images.length > 0 ? (
                          product.images.slice(0, 4).map((img, idx) => (
                            <div
                              key={idx}
                              className="relative group"
                              onMouseEnter={() => setHoveredImage({ img, product })}
                              onMouseLeave={() => setHoveredImage(null)}
                              onClick={() => setZoomedImage(img)}
                            >
                              <img
                                src={img}
                                alt=""
                                className="w-16 h-16 object-cover rounded-lg border cursor-pointer hover:ring-2 hover:ring-blue-400"
                              />
                              <button
                                onClick={(e) => handleDeleteImage(product._id, img, e)}
                                className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                              >
                                <X className="w-3 h-3" />
                              </button>
                              {idx === 0 && product.images.length > 4 && (
                                <div className="absolute bottom-0 right-0 bg-black/70 text-white text-xs px-1 rounded">
                                  +{product.images.length - 4}
                                </div>
                              )}
                            </div>
                          ))
                        ) : (
                          <div className="w-16 h-16 bg-gray-100 rounded-lg flex items-center justify-center border-2 border-dashed border-gray-300">
                            <Plus className="w-6 h-6 text-gray-400" />
                          </div>
                        )}
                      </div>

                      {/* Product Info */}
                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold text-gray-900 truncate">
                          {product.product_name || product.name || 'Unnamed Product'}
                        </h3>
                        {product.supplier_product_name && (
                          <p className="text-sm text-gray-500 truncate">
                            Supplier: {product.supplier_product_name} {product.size && product.finish ? `${product.size} ${product.finish}` : ''}
                          </p>
                        )}
                        <p className="text-sm text-gray-500">
                          {product.size || extractSize(product.name || product.product_name || '') || 'Size N/A'}
                          {product.finish && ` • ${product.finish}`}
                        </p>
                        
                        <div className="flex items-center gap-3 mt-2">
                          {product.images && product.images.length > 0 && (
                            <span className="flex items-center gap-1 text-sm bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                              <Check className="w-3 h-3" />
                              {product.images.length}
                            </span>
                          )}
                          
                          {/* Stock Status Dropdown */}
                          <select
                            className="text-xs border rounded px-2 py-1 bg-green-500 text-white font-medium"
                            value={product.stock_status || (product.in_stock ? 'in_stock' : 'out_of_stock')}
                            onChange={(e) => handleStockStatusChange(product._id, e.target.value)}
                          >
                            <option value="in_stock">In Stock</option>
                            <option value="always_in_stock">Always In Stock</option>
                            <option value="out_of_stock">Out of Stock</option>
                            <option value="special_order">Special Order</option>
                          </select>
                          
                          <label className="cursor-pointer">
                            <span className="text-sm text-orange-500 hover:text-orange-600 hover:underline flex items-center gap-1 font-medium">
                              {uploadingFor === product._id ? (
                                <RefreshCw className="w-3 h-3 animate-spin" />
                              ) : (
                                <Plus className="w-3 h-3" />
                              )}
                              {product.images?.length ? '+ Add more' : 'Click or drop'}
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
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right Sidebar - Bulk Upload */}
          <div className="w-72 border-l bg-gray-50 p-4">
            <h3 className="font-semibold text-gray-700 flex items-center gap-2 mb-4">
              <Upload className="w-4 h-4" />
              Bulk Upload (Auto-match)
            </h3>

            <div
              className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-blue-400 hover:bg-blue-50 transition-colors cursor-pointer"
              onClick={() => bulkInputRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                handleBulkUpload(e.dataTransfer.files);
              }}
            >
              <Upload className="w-12 h-12 mx-auto text-gray-400 mb-3" />
              <p className="font-medium text-gray-700">Drag & drop images</p>
              <p className="text-sm text-gray-500">or click to select</p>
              <input
                ref={bulkInputRef}
                type="file"
                multiple
                accept="image/*"
                className="hidden"
                onChange={(e) => handleBulkUpload(e.target.files)}
              />
            </div>

            <div className="mt-4 p-3 bg-gray-100 rounded-lg">
              <p className="text-xs text-gray-600">
                <strong>Tip:</strong> Name files like "<code className="bg-gray-200 px-1 rounded">Carrara_White_60x120.jpg</code>" for auto-matching
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

      {/* Hover Preview */}
      {hoveredImage && !zoomedImage && (
        <div 
          className="fixed z-[55] pointer-events-none"
          style={{
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)'
          }}
        >
          <div className="bg-white rounded-xl shadow-2xl p-2 border">
            <img 
              src={hoveredImage.img} 
              alt="Preview" 
              className="w-64 h-64 object-cover rounded-lg"
            />
            <p className="text-sm text-center mt-2 text-gray-600 truncate max-w-64">
              {hoveredImage.product.name || hoveredImage.product.product_name}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
