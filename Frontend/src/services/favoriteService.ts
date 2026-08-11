import { apiRequest } from './apiClient';
export interface FavoriteField { field_id: number; field_name: string; sport_type: string; location: string; image_url: string | null; price: number; rating: number; review_count: number; distance_km: number | null; status: string; has_availability: boolean; next_slot: string | null; created_at: string; }
export const getFavorites = () => apiRequest<FavoriteField[]>('/favorites');
export const getFavoriteStatus = (fieldId: number) => apiRequest<{ is_favorite: boolean }>(`/favorites/${fieldId}`);
export const setFavorite = (fieldId: number, favorite: boolean) => apiRequest<{ is_favorite: boolean }>(`/favorites/${fieldId}`, { method: favorite ? 'PUT' : 'DELETE' });
