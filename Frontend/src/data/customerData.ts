import type { CustomerBooking } from '@/types/customer';
import { sportImages } from '@/utils/sportImage';

const { football, badminton, tennis, basketball, pickleball } = sportImages;

export const venueDisplay: Record<number, { name: string; address: string; image: string }> = {
  1: { name: 'SportHub Phú Thọ', address: '219 Lý Thường Kiệt, Quận 11, TP. Hồ Chí Minh', image: football },
  2: { name: 'Cụm sân Cầu Vồng', address: '36 Trần Thái Tông, Cầu Giấy, Hà Nội', image: badminton },
  3: { name: 'Green Court Riverside', address: '12 Nguyễn Văn Hưởng, TP. Thủ Đức', image: tennis },
  4: { name: 'Saigon Hoops Arena', address: '18 Phan Văn Trị, Gò Vấp', image: basketball },
  5: { name: 'Pickleball Sala Club', address: '68 Nguyễn Cơ Thạch, TP. Thủ Đức', image: pickleball },
};

export const seedCustomerBookings: CustomerBooking[] = [
  { id: 'SH-260806-1048', venueId: 1, ...venueDisplay[1], venueName: venueDisplay[1].name, venueAddress: venueDisplay[1].address, venueImage: football, courtId: 'p1', courtName: 'Sân 5 người A1', date: '2026-08-08', startTime: '18:00', duration: 1.5, customerName: 'Nguyễn Minh Anh', phone: '0901 234 567', email: 'minhanh@gmail.com', equipment: ['Áo bib (10 chiếc)'], subtotal: 675000, serviceFee: 13500, discount: 0, total: 688500, status: 'upcoming', paymentStatus: 'paid', paymentMethod: 'wallet', createdAt: '2026-08-05T09:15:00+07:00' },
  { id: 'SH-260810-1122', venueId: 2, venueName: venueDisplay[2].name, venueAddress: venueDisplay[2].address, venueImage: badminton, courtId: 'c1', courtName: 'Sân thảm số 05', date: '2026-08-10', startTime: '19:00', duration: 1, customerName: 'Nguyễn Minh Anh', phone: '0901 234 567', email: 'minhanh@gmail.com', equipment: ['Vợt cầu lông × 2'], subtotal: 120000, serviceFee: 2400, discount: 0, total: 122400, status: 'pending', paymentStatus: 'unpaid', paymentMethod: 'cash', createdAt: '2026-08-06T08:20:00+07:00' },
  { id: 'SH-260722-0896', venueId: 3, venueName: venueDisplay[3].name, venueAddress: venueDisplay[3].address, venueImage: tennis, courtId: 't1', courtName: 'Center Court', date: '2026-07-22', startTime: '17:00', duration: 1, customerName: 'Nguyễn Minh Anh', phone: '0901 234 567', email: 'minhanh@gmail.com', equipment: [], subtotal: 320000, serviceFee: 6400, discount: 30000, total: 296400, status: 'completed', paymentStatus: 'paid', paymentMethod: 'bank', voucher: 'WELCOME30', createdAt: '2026-07-20T14:00:00+07:00' },
  { id: 'SH-260715-0811', venueId: 5, venueName: venueDisplay[5].name, venueAddress: venueDisplay[5].address, venueImage: pickleball, courtId: 'pk1', courtName: 'Court P1', date: '2026-07-15', startTime: '20:30', duration: 1, customerName: 'Nguyễn Minh Anh', phone: '0901 234 567', email: 'minhanh@gmail.com', equipment: [], subtotal: 180000, serviceFee: 3600, discount: 0, total: 183600, status: 'cancelled', paymentStatus: 'refunded', paymentMethod: 'card', createdAt: '2026-07-12T10:45:00+07:00' },
];

export const money = (value: number) => `${value.toLocaleString('vi-VN')}đ`;
export const formatDate = (value: string) => new Intl.DateTimeFormat('vi-VN', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(`${value}T00:00:00`));
export const endTime = (start: string, duration: number) => { const [h, m] = start.split(':').map(Number); const total = h * 60 + m + duration * 60; return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`; };
