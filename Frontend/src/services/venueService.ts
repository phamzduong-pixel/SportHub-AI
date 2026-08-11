import { apiRequest } from './apiClient';
import type { Venue, VenueCourt } from '@/types';
import { getSportImage } from '@/utils/sportImage';

interface ApiField {
  id: number; name: string; sport_type: string; description: string | null; location: string;
  capacity: number; base_price: number; status: 'available' | 'inactive' | 'maintenance';
  image_url: string | null; amenities: string[]; rating: number; review_count: number;
  distance_km: number | null; cancellation_policy: string; cancellation_refund_percent: number | null;
}
interface ApiSlot { id: number; field_id: number; name: string; start_time: string; end_time: string; price: number; is_active: boolean; }
interface Availability { field: ApiField; available_slots: ApiSlot[]; }
interface PublicCourtDetail {
  court: ApiField;
  facility: { id: number; name: string; location: string; description: string | null; contact_phone: string | null } | null;
  time_slots: ApiSlot[];
  images: string[];
  min_price: number;
  max_price: number;
}

const cancellationLabel: Record<string, string> = {
  manual_review: 'Yêu cầu hủy được chủ sân xem xét thủ công.',
  full_refund: 'Hoàn toàn bộ tiền cọc theo chính sách sân.',
  partial_refund: 'Hoàn một phần tiền cọc theo chính sách sân.',
  non_refundable: 'Tiền cọc không được hoàn khi hủy.',
};

function toVenue(field: ApiField, slots: ApiSlot[], facility?: PublicCourtDetail['facility'], images: string[] = []): Venue {
  const fallbackImage = getSportImage(field.sport_type);
  const active = slots.filter((slot) => slot.is_active);
  const prices = active.map((slot) => slot.price);
  const court: VenueCourt = {
    id: String(field.id), name: field.name, type: field.sport_type, surface: 'Theo thông tin cơ sở', indoor: false,
    price: prices.length ? Math.min(...prices) : field.base_price,
    availableSlots: active.map((slot) => slot.start_time.slice(0, 5)),
  };
  const parts = field.location.split(',').map((part) => part.trim()).filter(Boolean);
  const hours = active.length ? `${active[0].start_time.slice(0, 5)} – ${active[active.length - 1].end_time.slice(0, 5)}` : 'Chưa có lịch hoạt động';
  return {
    id: field.id, facilityId: facility?.id ?? null, facilityName: facility?.name ?? field.name,
    hotline: facility?.contact_phone ?? null,
    name: field.name, sport: field.sport_type, sports: [field.sport_type],
    address: field.location, district: parts[0] || field.location, city: parts.at(-1) || field.location,
    distance: field.distance_km ?? 0, price: prices.length ? Math.min(...prices) : field.base_price,
    rating: field.rating, reviewCount: field.review_count,
    status: field.status === 'available' && active.length ? 'Còn sân' : field.status === 'available' ? 'Sắp hết chỗ' : 'Tạm ngưng',
    available: field.status === 'available' && active.length > 0,
    image: images[0] || field.image_url || fallbackImage,
    gallery: images.length ? images : [field.image_url || fallbackImage],
    amenities: field.amenities || [], description: field.description || facility?.description || 'Chưa có mô tả từ chủ sân.', hours,
    courts: [court], policies: [cancellationLabel[field.cancellation_policy] || 'Vui lòng liên hệ chủ sân để biết chính sách hủy.'],
  };
}

export async function listVenues(input: { date?: string; search?: string; sportType?: string } = {}): Promise<Venue[]> {
  if (input.date) {
    const params = new URLSearchParams({ date: input.date });
    if (input.search?.trim()) params.set('search', input.search.trim());
    if (input.sportType) params.set('sport_type', input.sportType);
    const rows = await apiRequest<Availability[]>(`/availability?${params}`);
    return rows.map((row) => toVenue(row.field, row.available_slots));
  }
  const params = new URLSearchParams({ page_size: '100', status: 'available' });
  if (input.search?.trim()) params.set('search', input.search.trim());
  if (input.sportType) params.set('sport_type', input.sportType);
  const response = await apiRequest<{ items: ApiField[] }>(`/fields?${params}`);
  return Promise.all(response.items.map(async (field) => {
    const slots = await apiRequest<ApiSlot[]>(`/fields/${field.id}/time-slots`);
    return toVenue(field, slots);
  }));
}

export async function getVenue(fieldId: number): Promise<Venue> {
  const response = await apiRequest<PublicCourtDetail>(`/public/courts/${fieldId}`);
  return toVenue(response.court, response.time_slots, response.facility, response.images);
}
