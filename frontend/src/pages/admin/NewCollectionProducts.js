import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { 
  Sparkles, Search, ArrowLeft, Package, RefreshCw, 
  Building2, DollarSign, Box, Filter, Eye,
  ChevronDown, ChevronUp
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Supplier list
const SUPPLIERS = [
  { id: 'all', name: 'All Suppliers' },
  { id: 'Verona', name: 'Verona' },
  { id: 'Splendour', name: 'Splendour' },
  { id: 'Ceramica Impex', name: 'Ceramica Impex' },
  { id: 'Wallcano', name: 'Wallcano' },
  { id: 'Tile Rite', name: 'Tile Rite' },
  { id: 'Ultra Tile', name: 'Ultra Tile' },
];

export const NewCollectionProducts = () => {
  const navigate = useNavigate();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSupplier, setSelectedSupplier] = useState('all');
  const [stats, setStats] = useState({ total: 0, by_supplier: {} });
  const [expandedProduct, setExpandedProduct] = useState(null);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedSupplier !== 'all') {
        params.append('supplier', selectedSupplier);
      }
      if (searchTerm) {
        params.append('search', searchTerm);
      }
      
      const response = await fetch(`${API_URL}/api/sync-staging/special-products/new-collection?${params}`);
      if (response.ok) {
        const data = await response.json();
        setProducts(data.products || []);
        setStats({ total: data.total, by_supplier: data.by_supplier || {} });
      } else {
        toast.error('Failed to fetch new collection products');
      }
    } catch (error) {
      console.error('Error fetching new collection products:', error);
      toast.error('Failed to load new collection products');
    } finally {
      setLoading(false);
    }
  }, [selectedSupplier, searchTerm]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchProducts();
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  return (
    <div className="p-6 space-y-6" data-testid="new-collection-products-page">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/admin/epos')}>
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to EPOS
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Sparkles className="w-7 h-7 text-green-600" />
              New Collection Products
            </h1>
            <p className="text-gray-500">New products added from supplier syncs</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button 
            variant="outline" 
            onClick={fetchProducts}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="border-green-200 bg-green-50">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-green-700">Total New Products</p>
                <p className="text-2xl font-bold text-green-800">{stats.total}</p>
              </div>
              <Sparkles className="h-8 w-8 text-green-500/40" />
            </div>
          </CardContent>
        </Card>
        
        {Object.entries(stats.by_supplier).slice(0, 3).map(([supplier, count]) => (
          <Card key={supplier}>
            <CardContent className="pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{supplier}</p>
                  <p className="text-2xl font-bold">{count}</p>
                </div>
                <Building2 className="h-8 w-8 text-muted-foreground/20" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by product name or SKU..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
                data-testid="new-collection-search-input"
              />
            </div>
            <div className="w-full md:w-64">
              <Select value={selectedSupplier} onValueChange={setSelectedSupplier}>
                <SelectTrigger data-testid="supplier-filter">
                  <Filter className="w-4 h-4 mr-2" />
                  <SelectValue placeholder="Filter by supplier" />
                </SelectTrigger>
                <SelectContent>
                  {SUPPLIERS.map(supplier => (
                    <SelectItem key={supplier.id} value={supplier.id}>
                      {supplier.name}
                      {stats.by_supplier[supplier.id] && ` (${stats.by_supplier[supplier.id]})`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Products List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Package className="h-5 w-5" />
            New Collection Items ({products.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
            </div>
          ) : products.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Sparkles className="h-12 w-12 mx-auto mb-4 opacity-20" />
              <p>No new collection products found</p>
              <p className="text-sm mt-1">Add new products from the Sync Hub (without marking as Clearance)</p>
            </div>
          ) : (
            <div className="space-y-3">
              {products.map((product) => (
                <div 
                  key={product.sku}
                  className="border rounded-lg p-4 bg-green-50/50 border-green-200 hover:shadow-md transition-shadow"
                  data-testid={`new-collection-product-${product.sku}`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="inline-flex items-center gap-1 bg-green-500 text-white text-xs px-2 py-0.5 rounded-full font-medium">
                          NEW
                        </span>
                        <span className="inline-flex items-center gap-1 bg-gray-100 text-gray-700 text-xs px-2 py-0.5 rounded font-mono">
                          {product.supplier}
                        </span>
                        <span className="font-mono text-sm text-gray-500">{product.sku}</span>
                      </div>
                      <h3 className="font-semibold text-gray-900">{product.name || product.product_name}</h3>
                      
                      {/* Quick Info */}
                      <div className="flex gap-4 mt-2 text-sm">
                        <span className="flex items-center gap-1">
                          <Box className="w-4 h-4 text-gray-400" />
                          Stock: {product.stock_quantity || product.stock_m2 || 0} {product.stock_m2 ? 'm²' : ''}
                        </span>
                        {product.price && (
                          <span className="flex items-center gap-1">
                            <DollarSign className="w-4 h-4 text-gray-400" />
                            £{product.price?.toFixed(2)}
                          </span>
                        )}
                        {product.cost_price && (
                          <span className="flex items-center gap-1 text-red-600">
                            Cost: £{product.cost_price?.toFixed(2)}
                          </span>
                        )}
                      </div>
                      
                      <button
                        onClick={() => setExpandedProduct(expandedProduct === product.sku ? null : product.sku)}
                        className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1 mt-2"
                      >
                        <Eye className="w-4 h-4" />
                        {expandedProduct === product.sku ? 'Hide Details' : 'View Details'}
                        {expandedProduct === product.sku ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                      
                      {expandedProduct === product.sku && (
                        <div className="mt-3 p-3 bg-white rounded border text-sm space-y-1">
                          {product.category && <p><span className="text-gray-500">Category:</span> {product.category}</p>}
                          {product.size && <p><span className="text-gray-500">Size:</span> {product.size}</p>}
                          {product.material && <p><span className="text-gray-500">Material:</span> {product.material}</p>}
                          {product.finish && <p><span className="text-gray-500">Finish:</span> {product.finish}</p>}
                          {product.description && <p><span className="text-gray-500">Description:</span> {product.description}</p>}
                          {product.created_at && (
                            <p className="text-gray-400 text-xs">
                              Added: {new Date(product.created_at).toLocaleDateString('en-GB')}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                    
                    {product.image && (
                      <div className="ml-4 w-20 h-20 rounded-lg overflow-hidden border bg-white flex-shrink-0">
                        <img 
                          src={product.image} 
                          alt={product.name} 
                          className="w-full h-full object-cover"
                          onError={(e) => e.target.style.display = 'none'}
                        />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default NewCollectionProducts;
