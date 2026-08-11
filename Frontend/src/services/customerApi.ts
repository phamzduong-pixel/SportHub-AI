import { apiRequest } from './apiClient';

export type BookingStatus = 'pending_payment' | 'pending_confirmation' | 'confirmed' | 'in_progress' | 'completed' | 'no_show' | 'cancelled' | 'cancelled_by_customer' | 'cancelled_by_owner' | 'expired' | 'rejected' | 'failed';
export type BookingPaymentStatus = 'paid' | 'partial' | 'pending' | 'unpaid' | 'refund_pending' | 'refund_overdue' | 'refunded' | 'disputed';
export interface ApiBooking {
  id: number; booking_code: string; customer_id: number; customer_name: string; customer_email: string; customer_phone: string | null;
  facility_id: number | null; facility_name: string; facility_hotline: string | null; field_id: number; field_name: string; sport_type: string; location: string; time_slot_id: number;
  time_slot_name: string; booking_date: string; start_time_snapshot: string; end_time_snapshot: string;
  price_snapshot: number; total_amount: number; deposit_type: 'percentage' | 'fixed'; deposit_value: number;
  deposit_amount: number; paid_amount: number; additional_paid_amount: number; remaining_amount: number;
  payment_status: BookingPaymentStatus; status: BookingStatus; hold_expires_at: string | null;
  duration_minutes: number; cancellation_policy: string; cancellation_refund_percent: number | null;
  free_cancellation_minutes: number;
  refundable_deposit_amount: number | null; refund_amount: number; credit_amount: number; additional_payment_required: number;
  refund_status: string; cancellation_reason: string | null; cancelled_at: string | null; cancelled_by: number | null; rescheduled_at: string | null;
  reviewed: boolean;
  timeline: BookingActivity[];
  note: string | null; created_at: string; updated_at: string;
}
export interface BookingQuote { field_id: number; time_slot_id: number; booking_date: string; total_amount: number; deposit_amount: number; remaining_amount: number; deposit_type: string; deposit_value: number; hold_minutes: number; free_cancellation_minutes: number; cancellation_policy_summary: string; }
export interface InvoiceInfo { invoice_number: string; transaction_code: string; booking_code: string; customer_name: string; customer_email: string; field_name: string; facility_name: string; booking_date: string; total_amount: number; deposit_amount: number; remaining_payment_amount: number; paid_amount: number; remaining_amount: number; payment_method: string; bank_name: string | null; paid_at: string; }
export interface BookingInvoice { invoice_number: string; booking_id: number; booking_code: string; customer_name: string; customer_email: string; facility_name: string; field_name: string; booking_date: string; start_time: string; end_time: string; total_amount: number; deposit_amount: number; remaining_payment_amount: number; refund_amount: number; net_received_amount: number; payment_methods: string; paid_at: string | null; issued_at: string; }
export interface ApiPayment { id: number; booking_id: number; booking_code: string; customer_id: number; owner_id: number; transaction_code: string; amount: number; total_amount: number; deposit_amount: number; remaining_amount: number; paid_amount: number; payment_status: string; payment_method: string; payment_type: 'deposit' | 'remaining' | 'full' | 'refund'; status: string; escrow_status: 'pending' | 'held' | 'released' | 'refunded' | 'failed'; paid_at: string | null; refunded_at: string | null; failed_reason: string | null; provider: string | null; bank_id: string | null; bank_name: string | null; bank_account_no: string | null; bank_account_name: string | null; transfer_content: string | null; qr_url: string | null; expires_at: string | null; provider_reference: string | null; verification_source: string | null; refund_status: string; payment_mode: 'demo' | 'production'; invoice: InvoiceInfo | null; created_at: string; updated_at: string; }
export interface DepositReceiptData { receipt_number: string; booking_id: number; booking_code: string; customer_name: string; facility_name: string; facility_address: string; field_name: string; sport_type: string; booking_date: string; start_time: string; end_time: string; total_amount: number; deposit_paid: number; remaining_amount: number; transaction_code: string; payment_method: string; bank_name: string | null; paid_at: string; booking_status: string; deposit_status: 'paid' | 'paid_pending_confirmation' | 'refund_pending' | 'refunded'; status_message: string; refund_status: string; refund_amount: number; refunded_at: string | null; }
export interface CancellationQuote { booking_id: number; cancellable: boolean; minutes_before_start: number; refund_percent: number; paid_deposit_amount: number; refund_amount: number; forfeited_deposit_amount: number; free_cancellation_minutes: number; free_cancellation_deadline: string; is_late_cancellation: boolean; warning_message: string | null; reason_required: boolean; }
export interface RescheduleRequest { field_id: number; time_slot_id: number; booking_date: string; }
export interface RescheduleQuote extends RescheduleRequest { booking_id: number; old_total_amount: number; new_total_amount: number; price_difference: number; additional_payment_required: number; credit_amount: number; }
export const confirmManagedBooking = (bookingId: number) => apiRequest<ApiBooking>(`/bookings/${bookingId}/confirm`, { method: 'PATCH', body: JSON.stringify({}) });
export const rejectManagedBooking = (bookingId: number, note?: string) => apiRequest<ApiBooking>(`/bookings/${bookingId}/reject`, { method: 'PATCH', body: JSON.stringify({ note: note || null }) });
export const cancelManagedBooking = (bookingId: number, reason: string) => apiRequest<ApiBooking>(`/bookings/${bookingId}/cancel`, { method: 'PATCH', body: JSON.stringify({ reason }) });
export const startManagedBooking = (bookingId: number) => apiRequest<ApiBooking>(`/bookings/${bookingId}/start`, { method: 'PATCH', body: JSON.stringify({}) });
export const completeManagedBooking = (bookingId: number) => apiRequest<ApiBooking>(`/bookings/${bookingId}/complete`, { method: 'PATCH', body: JSON.stringify({}) });
export const noShowManagedBooking = (bookingId: number) => apiRequest<ApiBooking>(`/bookings/${bookingId}/no-show`, { method: 'PATCH', body: JSON.stringify({}) });
export interface PaymentSummary { booking_id: number; booking_code: string; total_amount: number; deposit_amount: number; additional_paid_amount: number; paid_amount: number; pending_amount: number; remaining_amount: number; payment_status: string; transactions: ApiPayment[]; }
export type RefundStatus = 'refund_pending' | 'refund_overdue' | 'refunded' | 'disputed';
export interface BookingActivity { id: number; actor_id: number | null; actor_name: string | null; actor_role: string | null; action: string; from_status: string | null; to_status: string | null; details: Record<string, unknown>; created_at: string; }
export interface RefundRequest { id: number; booking_id: number; booking_code: string; customer_id: number; customer_name: string; field_name: string; amount: number; status: RefundStatus; reason: string; requested_by: number; requested_by_name: string; processed_by: number | null; processed_by_name: string | null; requested_at: string; due_at: string; refunded_at: string | null; customer_confirmed_at: string | null; disputed_at: string | null; transaction_reference: string | null; evidence_url: string | null; dispute_reason: string | null; is_overdue: boolean; activities: BookingActivity[]; created_at: string; updated_at: string; }
export interface RefundReputation { total_bookings: number; owner_cancelled_bookings: number; owner_cancellation_rate: number; completed_refunds: number; on_time_refunds: number; on_time_refund_rate: number; }
export interface BookingComplaint { id: number; booking_id: number; booking_code: string; customer_id: number; customer_name: string; field_id: number; field_name: string; category: string; description: string; evidence_url: string | null; status: 'open' | 'in_review' | 'resolved' | 'rejected'; resolution: string | null; resolved_by: number | null; resolved_by_name: string | null; resolved_at: string | null; created_at: string; updated_at: string; }

export const getMyBookings = () => apiRequest<{ items: ApiBooking[]; total: number }>('/bookings/my?page_size=100');
export const getMyBooking = (id: string | number) => apiRequest<ApiBooking>(`/bookings/${id}`);
export const getBookingQuote = (fieldId: number, slotId: number, date: string) => apiRequest<BookingQuote>(`/bookings/quote?field_id=${fieldId}&time_slot_id=${slotId}&date=${date}`);
export const getCancellationQuote = (id: number) => apiRequest<CancellationQuote>(`/bookings/${id}/cancellation-quote`);
export const cancelMyBooking = (id: number, reason: string) => apiRequest<ApiBooking>(`/bookings/${id}/cancel`, { method: 'PATCH', body: JSON.stringify({ reason }) });
export const getRescheduleQuote = (id: number, payload: RescheduleRequest) => apiRequest<RescheduleQuote>(`/bookings/${id}/reschedule/quote`, { method: 'POST', body: JSON.stringify(payload) });
export const rescheduleBooking = (id: number, payload: RescheduleRequest) => apiRequest<ApiBooking>(`/bookings/${id}/reschedule`, { method: 'PATCH', body: JSON.stringify(payload) });
export const getBookingInvoice = (id: number) => apiRequest<BookingInvoice>(`/bookings/${id}/invoice`);
export const getPaymentSummary = (bookingId: number) => apiRequest<PaymentSummary>(`/bookings/${bookingId}/payment-summary`);
export const createBankIntent = (bookingId: number, paymentType: 'deposit' | 'remaining' = 'deposit') => apiRequest<ApiPayment>('/payments/bank-intents', { method: 'POST', body: JSON.stringify({ booking_id: bookingId, payment_type: paymentType }) });
export const getPayment = (paymentId: number | string) => apiRequest<ApiPayment>(`/payments/${paymentId}`);
export const getDepositReceipt = (paymentId: number | string) => apiRequest<DepositReceiptData>(`/payments/${paymentId}/deposit-receipt`);
export const getMyPayments = () => apiRequest<{ items: ApiPayment[]; total: number }>('/payments/my?page_size=100');
export const getMyRefunds = () => apiRequest<{ items: RefundRequest[]; total: number }>('/refunds/my?page_size=100');
export const getManagedRefunds = () => apiRequest<{ items: RefundRequest[]; total: number }>('/refunds?page_size=100');
export const getRefundReputation = () => apiRequest<RefundReputation>('/refunds/reputation');
export const markRefunded = (id: number, transactionReference: string, evidenceUrl?: string) => apiRequest<RefundRequest>(`/refunds/${id}/mark-refunded`, { method: 'PATCH', body: JSON.stringify({ transaction_reference: transactionReference, evidence_url: evidenceUrl || null }) });
export const confirmRefundReceived = (id: number) => apiRequest<RefundRequest>(`/refunds/${id}/confirm-received`, { method: 'PATCH', body: JSON.stringify({}) });
export const disputeRefund = (id: number, reason: string) => apiRequest<RefundRequest>(`/refunds/${id}/dispute`, { method: 'PATCH', body: JSON.stringify({ reason }) });
export const getMyComplaints = () => apiRequest<BookingComplaint[]>('/complaints/my');
export const getManagedComplaints = () => apiRequest<BookingComplaint[]>('/complaints');
export const createComplaint = (bookingId: number, category: string, description: string, evidenceUrl?: string) => apiRequest<BookingComplaint>('/complaints', { method: 'POST', body: JSON.stringify({ booking_id: bookingId, category, description, evidence_url: evidenceUrl || null }) });
export const updateComplaint = (id: number, status: 'in_review' | 'resolved' | 'rejected', resolution: string) => apiRequest<BookingComplaint>(`/complaints/${id}`, { method: 'PATCH', body: JSON.stringify({ status, resolution }) });
export const demoConfirmPayment = (paymentId: number) => apiRequest<ApiPayment>(`/payments/${paymentId}/demo-confirm`, { method: 'POST' });
export async function payBooking(booking: ApiBooking): Promise<{ booking: ApiBooking; payment: ApiPayment }> {
  const payment = await apiRequest<ApiPayment>('/payments', { method: 'POST', body: JSON.stringify({ booking_id: booking.id, payment_method: 'mock_online', payment_type: booking.paid_amount < booking.deposit_amount && !booking.additional_payment_required ? 'deposit' : 'remaining' }) });
  const confirmed = await apiRequest<ApiPayment>(`/payments/${payment.id}/confirm`, { method: 'PATCH', body: JSON.stringify({}) });
  return { booking: await getMyBooking(booking.id), payment: confirmed };
}
