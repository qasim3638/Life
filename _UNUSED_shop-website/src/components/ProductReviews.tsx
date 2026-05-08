'use client';

import { useState, useEffect } from 'react';
import { Star, ThumbsUp, User, CheckCircle, Loader2 } from 'lucide-react';
import api from '@/lib/api';
import { formatDate } from '@/lib/utils';

interface Review {
  id: string;
  product_id: string;
  customer_id: string;
  customer_name: string;
  rating: number;
  title: string;
  comment: string;
  verified_purchase: boolean;
  helpful_count: number;
  created_at: string;
}

interface ReviewsData {
  reviews: Review[];
  total: number;
  page: number;
  avg_rating: number;
  review_count: number;
}

interface ProductReviewsProps {
  productId: string;
  productName: string;
}

export function ProductReviews({ productId, productName }: ProductReviewsProps) {
  const [reviewsData, setReviewsData] = useState<ReviewsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showReviewForm, setShowReviewForm] = useState(false);
  const [helpfulIds, setHelpfulIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  const [newReview, setNewReview] = useState({
    rating: 5,
    title: '',
    comment: ''
  });

  useEffect(() => {
    loadReviews();
  }, [productId]);

  const loadReviews = async () => {
    try {
      const data = await api.getProductReviews(productId);
      setReviewsData(data);
    } catch (err) {
      console.error('Failed to load reviews:', err);
    } finally {
      setLoading(false);
    }
  };

  const submitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const token = localStorage.getItem('shop_token');
    if (!token) {
      setError('Please sign in to leave a review');
      return;
    }
    
    if (newReview.rating < 1 || newReview.rating > 5) {
      setError('Please select a rating');
      return;
    }
    
    setSubmitting(true);
    setError('');
    
    try {
      await api.createProductReview(token, productId, newReview);
      setSuccess('Thank you for your review!');
      setShowReviewForm(false);
      setNewReview({ rating: 5, title: '', comment: '' });
      loadReviews(); // Refresh reviews
    } catch (err: any) {
      console.error('Failed to submit review:', err);
      setError(err.response?.data?.detail || 'Failed to submit review. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const markHelpful = async (reviewId: string) => {
    if (helpfulIds.has(reviewId)) return;
    
    try {
      await api.markReviewHelpful(reviewId);
      setHelpfulIds(prev => new Set(prev).add(reviewId));
      
      // Update the count locally
      setReviewsData(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          reviews: prev.reviews.map(r => 
            r.id === reviewId ? { ...r, helpful_count: r.helpful_count + 1 } : r
          )
        };
      });
    } catch (err) {
      console.error('Failed to mark helpful:', err);
    }
  };

  const renderStars = (rating: number, interactive: boolean = false, onChange?: (rating: number) => void) => {
    return (
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type={interactive ? 'button' : undefined}
            onClick={interactive && onChange ? () => onChange(star) : undefined}
            className={`${interactive ? 'cursor-pointer hover:scale-110 transition-transform' : ''}`}
            disabled={!interactive}
          >
            <Star
              className={`w-5 h-5 ${
                star <= rating
                  ? 'fill-amber-400 text-amber-400'
                  : 'fill-gray-200 text-gray-200'
              }`}
            />
          </button>
        ))}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="py-8">
        <div className="flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
        </div>
      </div>
    );
  }

  return (
    <div className="py-8" data-testid="product-reviews-section">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Customer Reviews</h2>
          {reviewsData && reviewsData.review_count > 0 && (
            <div className="flex items-center gap-2 mt-1">
              {renderStars(Math.round(reviewsData.avg_rating))}
              <span className="font-medium">{reviewsData.avg_rating.toFixed(1)}</span>
              <span className="text-slate-500">({reviewsData.review_count} reviews)</span>
            </div>
          )}
        </div>
        
        <button
          onClick={() => setShowReviewForm(!showReviewForm)}
          className="inline-flex items-center gap-2 bg-amber-500 hover:bg-amber-600 text-slate-900 font-medium px-4 py-2 rounded-lg transition-colors"
          data-testid="write-review-btn"
        >
          <Star className="w-4 h-4" />
          Write a Review
        </button>
      </div>

      {/* Success Message */}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg mb-6">
          {success}
        </div>
      )}

      {/* Review Form */}
      {showReviewForm && (
        <div className="bg-slate-50 rounded-xl p-6 mb-8">
          <h3 className="font-semibold text-slate-900 mb-4">Write Your Review</h3>
          
          <form onSubmit={submitReview} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Your Rating *
              </label>
              {renderStars(newReview.rating, true, (rating) => setNewReview(prev => ({ ...prev, rating })))}
            </div>
            
            <div>
              <label htmlFor="review-title" className="block text-sm font-medium text-slate-700 mb-1">
                Review Title
              </label>
              <input
                id="review-title"
                type="text"
                value={newReview.title}
                onChange={(e) => setNewReview(prev => ({ ...prev, title: e.target.value }))}
                placeholder="Summarize your experience"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none"
                data-testid="review-title-input"
              />
            </div>
            
            <div>
              <label htmlFor="review-comment" className="block text-sm font-medium text-slate-700 mb-1">
                Your Review
              </label>
              <textarea
                id="review-comment"
                value={newReview.comment}
                onChange={(e) => setNewReview(prev => ({ ...prev, comment: e.target.value }))}
                placeholder="Share your experience with this product..."
                rows={4}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-amber-400/20 focus:border-amber-400 outline-none resize-none"
                data-testid="review-comment-input"
              />
            </div>
            
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}
            
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={submitting}
                className="flex items-center gap-2 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-300 text-slate-900 font-medium px-4 py-2 rounded-lg transition-colors"
                data-testid="submit-review-btn"
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Submitting...
                  </>
                ) : (
                  'Submit Review'
                )}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowReviewForm(false);
                  setError('');
                }}
                className="px-4 py-2 text-slate-600 hover:text-slate-900"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Reviews List */}
      {reviewsData && reviewsData.reviews.length > 0 ? (
        <div className="space-y-6">
          {reviewsData.reviews.map((review) => (
            <div key={review.id} className="border-b pb-6 last:border-0">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 bg-slate-200 rounded-full flex items-center justify-center flex-shrink-0">
                    <User className="w-5 h-5 text-slate-500" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-900">{review.customer_name}</span>
                      {review.verified_purchase && (
                        <span className="inline-flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded">
                          <CheckCircle className="w-3 h-3" />
                          Verified Purchase
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      {renderStars(review.rating)}
                      <span className="text-sm text-slate-500">{formatDate(review.created_at)}</span>
                    </div>
                  </div>
                </div>
              </div>
              
              {review.title && (
                <h4 className="font-medium text-slate-900 mt-3">{review.title}</h4>
              )}
              
              {review.comment && (
                <p className="text-slate-600 mt-2">{review.comment}</p>
              )}
              
              <div className="mt-3">
                <button
                  onClick={() => markHelpful(review.id)}
                  disabled={helpfulIds.has(review.id)}
                  className={`inline-flex items-center gap-1.5 text-sm ${
                    helpfulIds.has(review.id)
                      ? 'text-green-600'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <ThumbsUp className="w-4 h-4" />
                  Helpful ({review.helpful_count})
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 bg-slate-50 rounded-xl">
          <Star className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="font-medium text-slate-900 mb-1">No Reviews Yet</h3>
          <p className="text-sm text-slate-500">Be the first to review {productName}</p>
        </div>
      )}
    </div>
  );
}
