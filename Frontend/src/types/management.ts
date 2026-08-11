export type ManagementBookingStatus = 'pending' | 'confirmed' | 'playing' | 'completed' | 'cancelled';
export type ManagementPaymentStatus = 'paid' | 'partial' | 'unpaid' | 'refunded';
export type BookingSource = 'Website' | 'Ứng dụng' | 'Tại quầy' | 'Điện thoại';

export interface ManagementBooking {
  id: string;
  customer: string;
  phone: string;
  email: string;
  venue: string;
  court: string;
  courtId: string;
  sport: 'Bóng đá' | 'Cầu lông' | 'Pickleball';
  date: string;
  startTime: string;
  endTime: string;
  total: number;
  payment: ManagementPaymentStatus;
  status: ManagementBookingStatus;
  source: BookingSource;
  note?: string;
  createdAt: string;
}
