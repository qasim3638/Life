import React, { useState, useEffect } from 'react';
import { Star, ThumbsUp, CheckCircle, User } from 'lucide-react';
import { Button } from '../ui/button';
import { Textarea } from '../ui/textarea';
import { Input } from '../ui/input';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export const ReviewSection = ({ productId, productName }) => {
  const [reviews, setReviews] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [canReview, setCanReview] = useState(false);
  const [isVerifiedPurchase, setIsVerifiedPurchase] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  
  // Form state
  const [rating, setRating] = useState(0);
  const [title, setTitle] = useState('');
  const [comment, setComment] = useState('');
  const [hoverRating, setHoverRating] = useState(0);

  useEffect(() => {
    if (productId) {
      fetchReviews();
      checkCanReview();
    }
  }, [productId]);

  const fetchReviews = async () => {
    try {
      const [reviewsRes, summaryRes] = await Promise.all([
        fetch(`${API_URL}/api/reviews/product/${productId}?limit=5`),
        fetch(`${API_URL}/api/reviews/summary/${productId}`)
      ]);
      
      if (reviewsRes.ok) {
        const data = await reviewsRes.json();
        setReviews(data.reviews || []);
      }
      
      if (summaryRes.ok) {
        const data = await summaryRes.json();
        setSummary(data);
      }
    } catch (e) {
      console.error('Error fetching reviews:', e);
    } finally {
      setLoading(false);
    }
  };

  const checkCanReview = async () => {
    const token = localStorage.getItem('tileStationToken') || localStorage.getItem('token');
    if (!token) {
      setCanReview(false);
      return;
    }
    
    try {
      const res = await fetch(`${API_URL}/api/reviews/can-review/${productId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setCanReview(data.can_review);
        setIsVerifiedPurchase(data.verified_purchase);
      }
    } catch (e) {
      console.log('Cannot check review eligibility');
    }
  };

  const handleSubmitReview = async (e) => {
    e.preventDefault();
    if (rating === 0) {
      toast.error('Please select a rating');
      return;
    }
    if (!comment.trim()) {
      toast.error('Please write a review');
      return;
    }

    setSubmitting(true);
    try {
      const token = localStorage.getItem('tileStationToken') || localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/reviews/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          product_id: productId,
          rating,
          title,
          comment
        })
      });
      
      if (res.ok) {
        toast.success('Review submitted successfully!');
        setShowForm(false);
        setRating(0);
        setTitle('');
        setComment('');
        fetchReviews();
        setCanReview(false);
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to submit review');
      }
    } catch (e) {
      toast.error('Failed to submit review');
    } finally {
      setSubmitting(false);
    }
  };

  const handleMarkHelpful = async (reviewId) => {
    try {
      const res = await fetch(`${API_URL}/api/reviews/${reviewId}/helpful`, {
        method: 'POST'
      });
      if (res.ok) {
        toast.success('Marked as helpful');
        fetchReviews();
      }
    } catch (e) {
      console.error('Error marking helpful');
    }
  };

  const renderStars = (count, interactive = false, size = 'h-5 w-5') => {
    return (
      <div className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type={interactive ? 'button' : undefined}
            onClick={interactive ? () => setRating(star) : undefined}
            onMouseEnter={interactive ? () => setHoverRating(star) : undefined}
            onMouseLeave={interactive ? () => setHoverRating(0) : undefined}
            className={interactive ? 'focus:outline-none' : ''}
            disabled={!interactive}
          >
            <Star
              className={`${size} ${
                star <= (interactive ? (hoverRating || rating) : count)
                  ? 'fill-amber-400 text-amber-400'
                  : 'text-gray-300'
              }`}
            />
          </button>
        ))}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="animate-pulse">
        <div className="h-8 bg-gray-200 rounded w-48 mb-4"></div>
        <div className="h-24 bg-gray-200 rounded"></div>
      </div>
    );
  }

  return (
    <section className="mt-12 pt-8 border-t" data-testid="review-section">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Customer Reviews</h2>
      
      {/* Summary */}
      <div className="flex flex-col md:flex-row gap-8 mb-8">
        <div className="text-center p-6 bg-gray-50 rounded-lg">
          <div className="text-4xl font-bold text-gray-900 mb-2">
            {summary?.average_rating?.toFixed(1) || '0.0'}
          </div>
          {renderStars(summary?.average_rating || 0)}
          <p className="text-sm text-gray-500 mt-2">
            Based on {summary?.total_reviews || 0} reviews
          </p>
          {summary?.verified_count > 0 && (
            <p className="text-xs text-green-600 mt-1">
              {summary.verified_count} verified purchase{summary.verified_count > 1 ? 's' : ''}
            </p>
          )}
        </div>
        
        {canReview && !showForm && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <p className="text-gray-600 mb-3">
                {isVerifiedPurchase 
                  ? 'You purchased this product - share your experience!' 
                  : 'Have you used this product? Share your thoughts!'}
              </p>
              <Button 
                onClick={() => setShowForm(true)}
                className="bg-[#333333] hover:bg-[#444444] text-[#F7EA1C]"
              >
                Write a Review
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Review Form */}
      {showForm && (
        <form onSubmit={handleSubmitReview} className="mb-8 p-6 bg-amber-50 rounded-lg border border-amber-200">
          <h3 className="font-semibold text-lg mb-4">Write Your Review</h3>
          
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">Rating *</label>
            {renderStars(rating, true, 'h-8 w-8')}
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">Title (optional)</label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Summarize your review"
              maxLength={100}
            />
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">Your Review *</label>
            <Textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="What did you like or dislike about this product?"
              rows={4}
              maxLength={1000}
            />
            <p className="text-xs text-gray-500 mt-1">{comment.length}/1000 characters</p>
          </div>
          
          {isVerifiedPurchase && (
            <div className="flex items-center gap-2 mb-4 text-green-600 text-sm">
              <CheckCircle className="h-4 w-4" />
              <span>Your review will be marked as "Verified Purchase"</span>
            </div>
          )}
          
          <div className="flex gap-3">
            <Button type="submit" disabled={submitting} className="bg-[#333333] hover:bg-[#444444] text-[#F7EA1C]">
              {submitting ? 'Submitting...' : 'Submit Review'}
            </Button>
            <Button type="button" variant="outline" onClick={() => setShowForm(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      {/* Reviews List */}
      {reviews.length > 0 ? (
        <div className="space-y-6">
          {reviews.map((review) => (
            <div key={review.id} className="border-b pb-6" data-testid="review-item">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    {renderStars(review.rating, false, 'h-4 w-4')}
                    {review.verified_purchase && (
                      <span className="inline-flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded">
                        <CheckCircle className="h-3 w-3" />
                        Verified Purchase
                      </span>
                    )}
                  </div>
                  {review.title && (
                    <h4 className="font-semibold text-gray-900">{review.title}</h4>
                  )}
                </div>
              </div>
              
              <p className="text-gray-700 mb-3">{review.comment}</p>
              
              <div className="flex items-center justify-between text-sm text-gray-500">
                <div className="flex items-center gap-2">
                  <User className="h-4 w-4" />
                  <span>{review.customer_name}</span>
                  <span>•</span>
                  <span>{new Date(review.created_at).toLocaleDateString()}</span>
                </div>
                <button
                  onClick={() => handleMarkHelpful(review.id)}
                  className="flex items-center gap-1 hover:text-amber-600 transition"
                >
                  <ThumbsUp className="h-4 w-4" />
                  Helpful ({review.helpful_votes || 0})
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          <p>No reviews yet. Be the first to review this product!</p>
        </div>
      )}
    </section>
  );
};

export default ReviewSection;
