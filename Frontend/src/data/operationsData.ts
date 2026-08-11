import { sportImages } from '@/utils/sportImage';
export interface ManagedVenue { id: string; name: string; address: string; city: string; open: string; close: string; image: string; amenities: string[]; policies: string; status: 'active' | 'maintenance' | 'inactive'; courts: number; }
export interface ManagedCourt { id: string; venueId: string; name: string; sport: string; type: string; price: number; status: 'active' | 'locked' | 'maintenance'; maintenance: string; }
export interface CourtTimeSlot { id: string; courtId: string; label: string; start: string; end: string; priceType: 'standard' | 'peak' | 'off_peak'; priceOverride: number | null; days: string[]; active: boolean; }
export const managedVenues: ManagedVenue[] = [
  { id: 'v1', name: 'SportHub Phú Thọ', address: '219 Lý Thường Kiệt, Quận 11', city: 'TP. Hồ Chí Minh', open: '05:30', close: '23:00', image: sportImages.football, amenities: ['Bãi đỗ xe', 'Phòng thay đồ', 'Wifi'], policies: 'Hủy miễn phí trước 24 giờ.', status: 'active', courts: 2 },
  { id: 'v2', name: 'Cụm sân Cầu Vồng', address: '36 Trần Thái Tông, Cầu Giấy', city: 'Hà Nội', open: '06:00', close: '22:30', image: sportImages.badminton, amenities: ['Điều hòa', 'Cho thuê vợt'], policies: 'Đổi lịch miễn phí trước 6 giờ.', status: 'active', courts: 1 },
];
export const managedCourts: ManagedCourt[] = [
  { id: 'c1', venueId: 'v1', name: 'Sân A1', sport: 'Bóng đá', type: 'Sân 5 người', price: 450000, status: 'active', maintenance: 'Không có lịch bảo trì' },
  { id: 'c2', venueId: 'v1', name: 'Sân A2', sport: 'Bóng đá', type: 'Sân 5 người', price: 480000, status: 'active', maintenance: 'Kiểm tra đèn định kỳ' },
  { id: 'c3', venueId: 'v2', name: 'Sân thảm 05', sport: 'Cầu lông', type: 'Sân đôi trong nhà', price: 120000, status: 'active', maintenance: 'Không có lịch bảo trì' },
];
const DAYS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];
export const courtTimeSlots: CourtTimeSlot[] = [
  { id: 'ts1', courtId: 'c1', label: 'Sáng', start: '06:00', end: '11:00', priceType: 'standard', priceOverride: null, days: DAYS, active: true },
  { id: 'ts2', courtId: 'c1', label: 'Cao điểm', start: '17:00', end: '22:00', priceType: 'peak', priceOverride: 600000, days: DAYS, active: true },
  { id: 'ts3', courtId: 'c3', label: 'Trong ngày', start: '06:00', end: '22:00', priceType: 'standard', priceOverride: null, days: DAYS, active: true },
];
