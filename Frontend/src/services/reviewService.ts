import { apiRequest } from './apiClient';
export interface Review { id: number; booking_id: number; customer_id: number; customer_name: string; field_id: number; field_name: string; rating: number; comment: string; owner_reply: string | null; replied_at: string | null; created_at: string; }
export interface ReviewSummary { field_id: number; average_rating: number; total_reviews: number; items: Review[]; }
export const getFieldReviews = (fieldId: number) => apiRequest<ReviewSummary>(`/fields/${fieldId}/reviews`);
export const createReview = (bookingId: number, rating: number, comment: string) => apiRequest<Review>('/reviews', { method: 'POST', body: JSON.stringify({ booking_id: bookingId, rating, comment }) });
export const getManagementReviews = () => apiRequest<Review[]>('/management/reviews');
export const replyReview = (reviewId: number, reply: string) => apiRequest<Review>(`/management/reviews/${reviewId}/reply`, { method: 'PUT', body: JSON.stringify({ reply }) });
