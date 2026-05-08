import React, { useState } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Card } from './ui/card';
import { MessageSquare, Package, X, Send, CheckCircle } from 'lucide-react';

export const BulkInquiryModal = ({ 
  product, 
  onSubmit, 
  onClose, 
  loading = false,
  userEmail = '',
  userName = ''
}) => {
  const [formData, setFormData] = useState({
    quantity_needed: product.pallet_quantity ? product.pallet_quantity * 2 : 100,
    phone: '',
    message: ''
  });
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const success = await onSubmit({
      product_id: product.id,
      quantity_needed: parseInt(formData.quantity_needed),
      phone: formData.phone || null,
      message: formData.message || null
    });
    if (success) {
      setSubmitted(true);
    }
  };

  if (submitted) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <Card className="p-8 w-full max-w-md text-center">
          <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
            <CheckCircle className="h-8 w-8 text-green-600" />
          </div>
          <h2 className="text-2xl font-heading font-bold tracking-tightest mb-2">
            Inquiry Submitted!
          </h2>
          <p className="text-muted-foreground mb-6">
            Thank you for your interest. Our team will contact you shortly with a custom quote for your bulk order.
          </p>
          <Button onClick={onClose} className="w-full bg-accent hover:bg-accent/90">
            Close
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="p-6 w-full max-w-lg relative" data-testid="bulk-inquiry-modal">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-muted-foreground hover:text-foreground"
          data-testid="close-inquiry-modal"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-accent/10 rounded-lg">
              <MessageSquare className="h-6 w-6 text-accent" />
            </div>
            <div>
              <h2 className="text-xl font-heading font-bold tracking-tightest">
                Bulk Order Inquiry
              </h2>
              <p className="text-sm text-muted-foreground">
                Request a custom quote for large orders
              </p>
            </div>
          </div>

          {/* Product Summary */}
          <div className="bg-secondary rounded-lg p-4 flex items-center gap-4">
            {product.images && product.images[0] && (
              <img 
                src={product.images[0]} 
                alt={product.name}
                className="w-16 h-16 object-cover rounded-md"
              />
            )}
            <div className="flex-1">
              <p className="font-semibold">{product.name}</p>
              <p className="text-xs text-muted-foreground font-mono">{product.sku}</p>
              <p className="text-sm text-accent font-medium">
                Current best price: £{(product.pallet_price || product.room_lot_price || product.price).toFixed(2)}/m²
              </p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="customer_name">Your Name</Label>
              <Input
                id="customer_name"
                value={userName}
                disabled
                className="bg-secondary"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="customer_email">Email</Label>
              <Input
                id="customer_email"
                value={userEmail}
                disabled
                className="bg-secondary"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="quantity_needed">Quantity Needed (pieces) *</Label>
              <Input
                id="quantity_needed"
                data-testid="inquiry-quantity-input"
                type="number"
                value={formData.quantity_needed}
                onChange={(e) => setFormData({ ...formData, quantity_needed: e.target.value })}
                required
                min="1"
                placeholder="e.g., 200"
              />
              {product.m2_quantity && formData.quantity_needed && (
                <p className="text-xs text-muted-foreground">
                  ≈ {(product.m2_quantity * parseInt(formData.quantity_needed || 0)).toFixed(1)} m² total
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Phone Number</Label>
              <Input
                id="phone"
                data-testid="inquiry-phone-input"
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                placeholder="+44 7XXX XXXXXX"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="message">Additional Notes</Label>
            <textarea
              id="message"
              data-testid="inquiry-message-input"
              value={formData.message}
              onChange={(e) => setFormData({ ...formData, message: e.target.value })}
              placeholder="Tell us about your project, delivery requirements, or any other details..."
              className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <p className="text-sm text-blue-800">
              <strong>What happens next?</strong>
            </p>
            <ul className="text-xs text-blue-700 mt-1 space-y-1">
              <li>• Our team will review your inquiry within 24 hours</li>
              <li>• We&apos;ll contact you with a custom quote</li>
              <li>• Bulk orders may include additional discounts and delivery options</li>
            </ul>
          </div>

          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="flex-1"
              disabled={loading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="flex-1 bg-accent hover:bg-accent/90"
              disabled={loading || !formData.quantity_needed}
              data-testid="submit-inquiry-btn"
            >
              {loading ? 'Submitting...' : (
                <>
                  <Send className="h-4 w-4 mr-2" />
                  Submit Inquiry
                </>
              )}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};
