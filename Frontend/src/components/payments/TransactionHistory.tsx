import { CalendarClock, ChevronRight, CreditCard, ReceiptText } from 'lucide-react';
import { useState } from 'react';
import { Badge, LoadingSkeleton, Modal } from '@/components/common';
import { getPayment, type ApiPayment } from '@/services/customerApi';

interface Props {
  transactions: ApiPayment[];
  bookingId: number;
  bookingCode: string;
}

const money = (value: number) => `${Number(value || 0).toLocaleString('vi-VN')}đ`;

const paymentTypeLabel = (payment: ApiPayment) => {
  if (payment.payment_type === 'deposit') return 'Đặt cọc';
  if (payment.payment_type === 'refund') return 'Hoàn tiền';
  if (payment.payment_type === 'remaining') return 'Thanh toán còn lại';
  return payment.amount < payment.total_amount ? 'Thanh toán còn lại' : 'Thanh toán toàn bộ';
};

const paymentMethodLabel = (payment: ApiPayment) => {
  if (payment.payment_method === 'bank_transfer') return payment.bank_name ? `Chuyển khoản · ${payment.bank_name}` : 'Chuyển khoản ngân hàng';
  if (payment.payment_method === 'cash') return 'Tiền mặt';
  if (payment.payment_method === 'mock_online') return 'Thanh toán trực tuyến mô phỏng';
  return 'Thanh toán mô phỏng';
};

const friendlyStatus = (payment: ApiPayment) => {
  if (payment.payment_type === 'refund' || payment.status === 'refunded' || payment.refund_status === 'refunded') return { label: 'Đã hoàn tiền', variant: 'success' as const };
  if (payment.refund_status === 'refund_overdue') return { label: 'Hoàn tiền quá hạn', variant: 'danger' as const };
  if (payment.refund_status === 'refund_pending') return { label: 'Chờ hoàn tiền', variant: 'warning' as const };
  if (payment.refund_status === 'disputed') return { label: 'Đang khiếu nại', variant: 'info' as const };
  if (payment.status === 'paid') return payment.payment_type === 'deposit'
    ? { label: 'Đã đặt cọc', variant: 'success' as const }
    : { label: 'Đã thanh toán', variant: 'success' as const };
  if (payment.status === 'pending') return { label: 'Chờ xác nhận', variant: 'warning' as const };
  if (payment.status === 'cancelled') return { label: 'Đã hủy', variant: 'danger' as const };
  return { label: 'Không thành công', variant: 'danger' as const };
};

const transactionTime = (payment: ApiPayment) => payment.refunded_at || payment.paid_at || payment.created_at;

export function TransactionHistory({ transactions, bookingId, bookingCode }: Props) {
  const ownedTransactions = transactions
    .filter((item) => item.booking_id === bookingId)
    .sort((a, b) => new Date(transactionTime(b)).getTime() - new Date(transactionTime(a)).getTime());
  const [selected, setSelected] = useState<ApiPayment>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const open = async (item: ApiPayment) => {
    setSelected(item);
    setLoading(true);
    setError('');
    try {
      const detail = await getPayment(item.id);
      if (detail.booking_id !== bookingId) throw new Error('Giao dịch không thuộc booking này.');
      setSelected(detail);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Không tải được chi tiết giao dịch.');
    } finally {
      setLoading(false);
    }
  };

  if (!ownedTransactions.length) return <div className="mt-5 rounded-xl border border-dashed border-slate-200 bg-slate-50/70 p-4 text-center text-sm text-slate-500">Chưa có lịch sử giao dịch.</div>;

  return <>
    <section className="mt-5 border-t border-slate-100 pt-5">
      <div className="mb-3 flex items-center gap-2"><ReceiptText size={18} className="text-brand-700" /><h3 className="font-semibold text-slate-800">Lịch sử giao dịch</h3></div>
      <div className="space-y-2">
        {ownedTransactions.map((item) => {
          const status = friendlyStatus(item);
          return <button type="button" key={item.id} onClick={() => void open(item)} className="flex w-full min-w-0 items-center gap-3 rounded-xl border border-slate-200 bg-slate-50/70 p-3 text-left transition hover:border-brand-300 hover:bg-brand-50/60 focus-visible:border-brand-500">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-white text-brand-700 shadow-sm"><CreditCard size={18} /></span>
            <span className="min-w-0 flex-1"><b className="block truncate text-sm text-slate-800">{paymentTypeLabel(item)}</b><span className="block truncate font-mono text-[11px] text-slate-500">{item.transaction_code}</span><span className="mt-1 flex flex-wrap items-center gap-2 min-[375px]:hidden"><b className="text-xs text-slate-700">{money(item.amount)}</b><Badge variant={status.variant}>{status.label}</Badge></span></span>
            <span className="hidden text-right min-[375px]:block"><b className="block text-sm text-slate-800">{money(item.amount)}</b><Badge variant={status.variant} className="mt-1">{status.label}</Badge></span>
            <ChevronRight size={17} className="shrink-0 text-slate-400" />
          </button>;
        })}
      </div>
    </section>

    <Modal open={Boolean(selected)} onClose={() => { setSelected(undefined); setError(''); }} title="Chi tiết giao dịch" description={selected?.transaction_code}>
      {loading ? <LoadingSkeleton lines={6} /> : error ? <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div> : selected && <TransactionDetail payment={selected} bookingCode={bookingCode} />}
    </Modal>
  </>;
}

function TransactionDetail({ payment, bookingCode }: { payment: ApiPayment; bookingCode: string }) {
  const status = friendlyStatus(payment);
  const paidTime = transactionTime(payment);
  return <div className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-brand-50 p-4"><div><p className="text-xs font-medium text-slate-500">Số tiền giao dịch</p><b className="mt-1 block text-2xl text-brand-800">{money(payment.amount)}</b></div><Badge variant={status.variant}>{status.label}</Badge></div>
    <dl className="grid gap-3 text-sm sm:grid-cols-2">
      <Detail label="Mã giao dịch" value={payment.transaction_code} mono />
      <Detail label="Loại thanh toán" value={paymentTypeLabel(payment)} />
      <Detail label="Phương thức" value={paymentMethodLabel(payment)} />
      <Detail label="Mã booking" value={payment.booking_code || bookingCode} mono />
      <Detail label={payment.payment_type === 'refund' ? 'Thời gian hoàn tiền' : 'Ngày giờ thanh toán'} value={paidTime ? new Date(paidTime).toLocaleString('vi-VN') : 'Chưa ghi nhận'} />
      {payment.provider_reference && <Detail label="Mã tham chiếu" value={payment.provider_reference} mono />}
    </dl>
    <div className="flex gap-2 rounded-xl border border-cyan-100 bg-cyan-50 p-3 text-xs leading-5 text-cyan-900"><CalendarClock size={17} className="mt-0.5 shrink-0" /><p>Thông tin được cập nhật trực tiếp từ lịch sử thanh toán của booking.</p></div>
  </div>;
}

function Detail({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return <div className="min-w-0 rounded-lg bg-slate-50 p-3"><dt className="text-xs text-slate-500">{label}</dt><dd className={`mt-1 break-words font-semibold text-slate-800 ${mono ? 'font-mono text-xs' : ''}`}>{value}</dd></div>;
}
