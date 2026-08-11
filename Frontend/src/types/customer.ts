export type CustomerBookingStatus = 'upcoming' | 'pending' | 'completed' | 'cancelled' | 'failed';
export type PaymentStatus = 'paid' | 'unpaid' | 'refunded';
export type PaymentMethod = 'bank' | 'wallet' | 'cash' | 'card';

export interface CustomerBooking {
  id: string;
  venueId: number;
  venueName: string;
  venueAddress: string;
  venueImage: string;
  courtId: string;
  courtName: string;
  date: string;
  startTime: string;
  duration: number;
  customerName: string;
  phone: string;
  email: string;
  note?: string;
  equipment: string[];
  voucher?: string;
  subtotal: number;
  serviceFee: number;
  discount: number;
  total: number;
  status: CustomerBookingStatus;
  paymentStatus: PaymentStatus;
  paymentMethod: PaymentMethod;
  createdAt: string;
  /** Only pending payment bookings have a temporary ten-minute hold. */
  holdExpiresAt?: string;
}

export interface CustomerProfile {
  fullName: string;
  phone: string;
  email: string;
  birthday: string;
  gender: string;
  city: string;
}
