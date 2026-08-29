import { useEffect, useState } from 'react';
import { Badge, EmptyState, LoadingSkeleton, PageHeader, useToast } from '@/components/common';
import { DepositReceipt } from '@/components/payments/DepositReceipt';
import { RefundStatusPanel } from '@/components/refunds/RefundStatusPanel';
import { apiRequest } from '@/services/apiClient';
import {
  getDepositReceipt,
  getManagedRefunds,
  getRefundReputation,
  type ApiPayment,
  type DepositReceiptData,
  type RefundReputation,
  type RefundRequest,
} from '@/services/customerApi';

const money = (value: number) => `${value.toLocaleString('vi-VN')}đ`;
const paymentStatusLabels: Record<string, string> = {
  unpaid: 'Chưa thanh toán',
  pending: 'Đang xử lý',
  partial: 'Đã đặt cọc',
  paid: 'Đã thanh toán',
  refund_pending: 'Chờ hoàn tiền',
  refund_overdue: 'Hoàn tiền quá hạn',
  refunded: 'Đã hoàn tiền',
  disputed: 'Đang khiếu nại',
  failed: 'Thất bại',
  cancelled: 'Đã hủy',
};

const refundStatusLabels: Record<string, string> = {
  pending: 'Chờ hoàn tiền',
  completed: 'Đã hoàn tiền',
  rejected: 'Từ chối hoàn',
  cancelled: 'Đã hủy hoàn',
};

const getPaymentDisplayStatus = (item: ManagedPayment) => {
  if (item.refund_status && item.refund_status !== 'not_requested') {
    return refundStatusLabels[item.refund_status] || paymentStatusLabels[item.refund_status] || item.refund_status;
  }
  return paymentStatusLabels[item.status] || item.status;
};

interface ManagedPayment extends ApiPayment { booking_code: string; customer_name: string; field_name: string; booking_date: string; }


export function ManagementPaymentsPage() {
  const { toast } = useToast();
  const [items, setItems] = useState<ManagedPayment[]>([]);
  const [refunds, setRefunds] = useState<RefundRequest[]>([]);
  const [reputation, setReputation] = useState<RefundReputation>();
  const [receipt, setReceipt] = useState<DepositReceiptData>();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([apiRequest<{ items: ManagedPayment[] }>('/payments?page_size=100'), getManagedRefunds(), getRefundReputation()])
      .then(([payments, refundResult, metrics]) => { setItems(payments.items); setRefunds(refundResult.items); setReputation(metrics); })
      .catch((error) => toast(error instanceof Error ? error.message : 'Không tải được thanh toán.', 'error'))
      .finally(() => setLoading(false));
  }, []);

  const openReceipt = async (paymentId: number) => {
    try { setReceipt(await getDepositReceipt(paymentId)); }
    catch (error) { toast(error instanceof Error ? error.message : 'Không tải được biên lai.', 'error'); }
  };

  return <>
    <PageHeader title="Thanh toán, hoàn tiền và đối soát" description="Theo dõi giao dịch, xử lý yêu cầu hoàn tiền và khiếu nại trong cùng một nơi." />
    {reputation && <div className="mb-5 grid gap-3 sm:grid-cols-2">
      <section className="rounded-card border bg-white p-4"><p className="text-sm text-slate-500">Tỷ lệ chủ sân hủy</p><b className="text-2xl">{reputation.owner_cancellation_rate}%</b><small className="ml-2 text-slate-500">{reputation.owner_cancelled_bookings}/{reputation.total_bookings} booking</small></section>
      <section className="rounded-card border bg-white p-4"><p className="text-sm text-slate-500">Hoàn tiền đúng hạn</p><b className="text-2xl">{reputation.on_time_refund_rate}%</b><small className="ml-2 text-slate-500">{reputation.on_time_refunds}/{reputation.completed_refunds} yêu cầu</small></section>
    </div>}
    {refunds.length > 0 && <section className="mb-7"><h2 className="text-lg font-bold">Yêu cầu hoàn tiền / khiếu nại</h2>{refunds.map((item) => <RefundStatusPanel key={`${item.id}:${item.updated_at}`} initial={item} mode="owner" onChanged={(next) => setRefunds((current) => current.map((entry) => entry.id === next.id ? next : entry))} />)}</section>}
    {loading ? <LoadingSkeleton lines={8} /> : items.length ? <div className="overflow-x-auto rounded-card border bg-white">
      <table className="w-full min-w-[1000px] text-left text-sm"><thead className="bg-slate-50"><tr>{['Mã giao dịch', 'Booking', 'Khách hàng', 'Loại', 'Số tiền', 'Tổng booking', 'Đã trả sau giao dịch', 'Còn lại', 'Trạng thái', ''].map((label) => <th key={label} className="px-4 py-3">{label}</th>)}</tr></thead>
        <tbody>{items.map((item) => <tr key={item.id} className="border-t">
          <td className="px-4 py-3 font-mono">{item.transaction_code}</td><td className="px-4 py-3">{item.booking_code}<small className="block">{item.field_name}</small></td><td className="px-4 py-3">{item.customer_name}</td>
          <td className="px-4 py-3">{item.payment_type === 'deposit' ? 'Đặt cọc' : item.payment_type === 'refund' ? 'Hoàn tiền' : 'Còn lại'}</td><td className="px-4 py-3 font-semibold">{money(item.amount)}</td><td className="px-4 py-3">{money(item.total_amount)}</td><td className="px-4 py-3">{money(item.paid_amount)}</td><td className="px-4 py-3">{money(item.remaining_amount)}</td>
          <td className="px-4 py-3"><Badge>{getPaymentDisplayStatus(item)}</Badge></td><td className="px-4 py-3">{item.payment_type === 'deposit' && item.status === 'paid' && <button className="font-semibold text-brand-700 hover:underline" onClick={() => void openReceipt(item.id)}>Biên lai</button>}</td>
        </tr>)}</tbody></table>
    </div> : <EmptyState title="Chưa có giao dịch" description="Giao dịch sẽ xuất hiện sau khi khách bắt đầu thanh toán." />}
    {receipt && <section className="mt-5"><DepositReceipt receipt={receipt} /></section>}
  </>;
}
