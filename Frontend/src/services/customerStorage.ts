import type { CustomerBooking, CustomerProfile } from '@/types/customer';

const BOOKING_KEY = 'sporthub_customer_bookings';
const PROFILE_KEY = 'sporthub_customer_profile';
const FAVORITE_KEY = 'sporthub_customer_favorites';

export const defaultProfile: CustomerProfile = {
  fullName: '', phone: '', email: '', birthday: '', gender: '', city: '',
};

export const BOOKING_CONFLICT_MESSAGE = 'Khung giờ này vừa được người khác đặt. Vui lòng chọn thời gian khác.';

function minutes(value: string) {
  const [hours, mins] = value.split(':').map(Number);
  return hours * 60 + mins;
}

function blocksSchedule(booking: CustomerBooking, now = Date.now()) {
  if (booking.status !== 'upcoming' && booking.status !== 'pending') return false;
  return !booking.holdExpiresAt || new Date(booking.holdExpiresAt).getTime() > now;
}

export function hasBookingConflict(
  courtId: string,
  date: string,
  startTime: string,
  duration: number,
  excludeId?: string,
) {
  const newStart = minutes(startTime);
  const newEnd = newStart + duration * 60;
  return readBookings().some((booking) => booking.id !== excludeId
    && booking.courtId === courtId
    && booking.date === date
    && blocksSchedule(booking)
    && newStart < minutes(booking.startTime) + booking.duration * 60
    && newEnd > minutes(booking.startTime));
}

export function readBookings(seed: CustomerBooking[] = []): CustomerBooking[] {
  try {
    const raw = localStorage.getItem(BOOKING_KEY);
    if (raw) {
      const bookings = JSON.parse(raw) as CustomerBooking[];
      const now = Date.now();
      let changed = false;
      const released = bookings.map((booking) => {
        if (booking.status === 'pending' && booking.holdExpiresAt && new Date(booking.holdExpiresAt).getTime() <= now) {
          changed = true;
          return { ...booking, status: 'failed' as const, holdExpiresAt: undefined };
        }
        return booking;
      });
      if (changed) localStorage.setItem(BOOKING_KEY, JSON.stringify(released));
      return released;
    }
    localStorage.setItem(BOOKING_KEY, JSON.stringify(seed));
  } catch { /* Browser privacy mode: use seed data. */ }
  return seed;
}

export function writeBookings(bookings: CustomerBooking[]) {
  localStorage.setItem(BOOKING_KEY, JSON.stringify(bookings));
  window.dispatchEvent(new Event('sporthub-bookings-updated'));
}

export function saveBooking(booking: CustomerBooking) {
  const bookings = readBookings();
  writeBookings([booking, ...bookings.filter((item) => item.id !== booking.id)]);
  sessionStorage.setItem('sporthub_latest_booking', booking.id);
}

/** Mock equivalent of the backend's atomic availability check and hold creation. */
export function tryHoldBooking(booking: CustomerBooking) {
  if (hasBookingConflict(booking.courtId, booking.date, booking.startTime, booking.duration, booking.id)) return false;
  saveBooking(booking);
  return true;
}

export function updateBooking(id: string, patch: Partial<CustomerBooking>) {
  writeBookings(readBookings().map((item) => item.id === id ? { ...item, ...patch } : item));
}

export function readProfile(): CustomerProfile {
  try { return JSON.parse(localStorage.getItem(PROFILE_KEY) || '') as CustomerProfile; } catch { return defaultProfile; }
}
export function writeProfile(profile: CustomerProfile) { localStorage.setItem(PROFILE_KEY, JSON.stringify(profile)); }

export function readFavorites(): number[] {
  try { return JSON.parse(localStorage.getItem(FAVORITE_KEY) || '[1,3,5]') as number[]; } catch { return [1, 3, 5]; }
}
export function writeFavorites(ids: number[]) { localStorage.setItem(FAVORITE_KEY, JSON.stringify(ids)); }
