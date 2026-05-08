import React from 'react';
import { Share2, MessageCircle, Mail, Link as LinkIcon, Facebook, Twitter } from 'lucide-react';
import { toast } from 'sonner';

/**
 * ShareProduct - Social sharing buttons for products
 */
export const ShareProduct = ({ productName, productUrl, productImage }) => {
  const shareUrl = productUrl || window.location.href;
  const shareText = `Check out ${productName} at Tile Station!`;
  
  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      toast.success('Link copied to clipboard!');
    } catch {
      toast.error('Failed to copy link');
    }
  };
  
  const handleWhatsAppShare = () => {
    const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(`${shareText}\n${shareUrl}`)}`;
    window.open(whatsappUrl, '_blank');
  };
  
  const handleEmailShare = () => {
    const subject = encodeURIComponent(`Check out this tile: ${productName}`);
    const body = encodeURIComponent(`I found this amazing tile at Tile Station!\n\n${productName}\n\n${shareUrl}`);
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  };
  
  const handleFacebookShare = () => {
    const fbUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`;
    window.open(fbUrl, '_blank', 'width=600,height=400');
  };
  
  const handleTwitterShare = () => {
    const twitterUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(shareUrl)}`;
    window.open(twitterUrl, '_blank', 'width=600,height=400');
  };

  return (
    <div className="flex items-center gap-2" data-testid="share-product">
      <span className="text-sm text-gray-500 mr-1">Share:</span>
      
      {/* WhatsApp */}
      <button
        onClick={handleWhatsAppShare}
        className="p-2 rounded-full bg-green-500 text-white hover:bg-green-600 transition"
        title="Share on WhatsApp"
        data-testid="share-whatsapp"
      >
        <MessageCircle className="h-4 w-4" />
      </button>
      
      {/* Email */}
      <button
        onClick={handleEmailShare}
        className="p-2 rounded-full bg-gray-600 text-white hover:bg-gray-700 transition"
        title="Share via Email"
        data-testid="share-email"
      >
        <Mail className="h-4 w-4" />
      </button>
      
      {/* Facebook */}
      <button
        onClick={handleFacebookShare}
        className="p-2 rounded-full bg-blue-600 text-white hover:bg-blue-700 transition"
        title="Share on Facebook"
        data-testid="share-facebook"
      >
        <Facebook className="h-4 w-4" />
      </button>
      
      {/* Twitter/X */}
      <button
        onClick={handleTwitterShare}
        className="p-2 rounded-full bg-gray-900 text-white hover:bg-black transition"
        title="Share on X (Twitter)"
        data-testid="share-twitter"
      >
        <Twitter className="h-4 w-4" />
      </button>
      
      {/* Copy Link */}
      <button
        onClick={handleCopyLink}
        className="p-2 rounded-full bg-amber-500 text-white hover:bg-amber-600 transition"
        title="Copy Link"
        data-testid="share-copy-link"
      >
        <LinkIcon className="h-4 w-4" />
      </button>
    </div>
  );
};

export default ShareProduct;
