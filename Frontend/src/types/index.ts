export type SportType = string;
export type VenueStatus = 'Còn sân' | 'Sắp hết chỗ' | 'Tạm ngưng';

export interface VenueCourt {
  id: string;
  name: string;
  type: string;
  surface: string;
  indoor: boolean;
  price: number;
  operatingSlots: string[];
}

export interface Venue {
  id: number;
  facilityId?: number | null;
  facilityName?: string;
  hotline?: string | null;
  capacity: number;
  name: string;
  sport: SportType;
  sports: SportType[];
  address: string;
  district: string;
  city: string;
  distance: number;
  price: number;
  rating: number;
  reviewCount: number;
  status: VenueStatus;
  available: boolean;
  image: string;
  gallery: string[];
  amenities: string[];
  description: string;
  hours: string;
  courts: VenueCourt[];
  policies: string[];
}

export interface Booking {
  id: string; customer: string; venue: string; date: string; time: string;
  amount: number; status: 'Đã xác nhận' | 'Chờ xác nhận' | 'Đã hoàn thành' | 'Đã hủy';
}
