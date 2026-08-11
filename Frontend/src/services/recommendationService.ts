import { buildApiUrl } from '@/services/apiClient';

export interface CustomerRecommendation {
  field_id: number; field_name: string; sport_type: string; location: string; image_url: string | null;
  price: number; rating: number; review_count: number; distance_km: number | null; score: number; reason: string;
  available_slots: Array<{ id: number; start_time: string; end_time: string; price: number }>;
}

export interface RecommendationResponse {
  strategy: 'booking_history' | 'popular_and_high_rated';
  personalized: boolean;
  items: CustomerRecommendation[];
}

export async function getCustomerRecommendations(): Promise<RecommendationResponse> {
  const token = localStorage.getItem('sporthub_access_token');
  const response = await fetch(buildApiUrl('/ai/customer-recommendations?limit=3'), { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!response.ok) throw new Error(`Recommendation API returned ${response.status}`);
  return response.json() as Promise<RecommendationResponse>;
}
