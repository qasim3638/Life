import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Heart, Trash2, ShoppingBag } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { useWishlist } from '../../contexts/WishlistContext';
import { useCart } from '../../contexts/TileCartContext';
import { ShopHeader, ShopFooter } from './TileStationHome';
import { useTradeUser } from '../../hooks/useTradeUser';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const TileWishlistPage = () => {
  const { isTrade, getTradePrice } = useTradeUser();
  const { wishlist, removeFromWishlist } = useWishlist();
  const { addToCart } = useCart();
  const navigate = useNavigate();

  const handleAddToCart = async (item) => {
    try {
      // Fetch full tile data to get price
      const res = await fetch(`${API_URL}/api/tiles/products/${item.slug}`);
      const tile = await res.json();
      addToCart(tile, 1, 'room_lot');
    } catch (e) {
      console.error('Error adding to cart:', e);
      toast.error('Failed to add to cart');
    }
  };

  if (wishlist.length === 0) {
    return (
      <div className="min-h-screen bg-white">
        <ShopHeader />
        <div className="container mx-auto px-4 py-16">
          <div className="text-center max-w-md mx-auto">
            <Heart className="h-16 w-16 mx-auto text-gray-300 mb-4" />
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Your wishlist is empty</h1>
            <p className="text-gray-500 mb-6">
              Save your favourite tiles to compare them later.
            </p>
            <Button 
              onClick={() => navigate('/tiles')}
              className="bg-[#333333] hover:bg-[#444444] text-[#F7EA1C] font-semibold"
              data-testid="browse-tiles-btn"
            >
              Browse Tiles
            </Button>
          </div>
        </div>
        <ShopFooter />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white" data-testid="wishlist-page">
      <ShopHeader />

      <div className="container mx-auto px-4 py-8">
        {/* Breadcrumb */}
        <nav className="text-sm text-gray-500 mb-6">
          <Link to="/tiles" className="hover:text-amber-500">Home</Link>
          <span className="mx-2">/</span>
          <span className="text-gray-900">Wishlist</span>
        </nav>

        <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-8">
          My Wishlist ({wishlist.length} items)
        </h1>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {wishlist.map((item) => (
            <div key={item.id} className="group relative">
              <Link to={`/tiles/${item.slug}`}>
                <div className="aspect-square bg-gray-100 rounded-lg overflow-hidden mb-3">
                  {item.image ? (
                    <img
                      src={item.image}
                      alt={item.display_name}
                      className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-gray-400">
                      No Image
                    </div>
                  )}
                </div>
                <h3 className="font-medium text-gray-900 group-hover:text-amber-500 transition line-clamp-2">
                  {item.display_name}
                </h3>
                <p className="text-amber-500 font-semibold mt-1">
                  £{(isTrade ? getTradePrice(item.price) : item.price)?.toFixed(2)}{item.is_surface_product !== false ? '/m²' : '/each'}
                  {isTrade && <span className="text-[10px] text-gray-400 font-normal ml-1">ex. VAT</span>}
                </p>
                {item.size && (
                  <p className="text-sm text-gray-500">{item.size}</p>
                )}
              </Link>

              {/* Actions */}
              <div className="mt-3 flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1"
                  onClick={() => handleAddToCart(item)}
                >
                  <ShoppingBag className="h-4 w-4 mr-1" />
                  Add to Cart
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-red-500 hover:text-red-600 hover:bg-red-50"
                  onClick={() => removeFromWishlist(item.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <ShopFooter />
    </div>
  );
};

export default TileWishlistPage;
