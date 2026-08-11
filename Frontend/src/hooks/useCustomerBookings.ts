import { useEffect, useState } from 'react';
import { seedCustomerBookings } from '@/data/customerData';
import { readBookings } from '@/services/customerStorage';

export function useCustomerBookings() {
  const [bookings, setBookings] = useState(() => readBookings(seedCustomerBookings));
  useEffect(() => { const refresh = () => setBookings(readBookings(seedCustomerBookings)); window.addEventListener('storage', refresh); window.addEventListener('sporthub-bookings-updated', refresh); return () => { window.removeEventListener('storage', refresh); window.removeEventListener('sporthub-bookings-updated', refresh); }; }, []);
  return bookings;
}
