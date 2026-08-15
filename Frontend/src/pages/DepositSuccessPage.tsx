import { CheckCircle2, Clock3, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Button, EmptyState, LoadingSkeleton } from "@/components/common";
import { DepositReceipt } from "@/components/payments/DepositReceipt";
import {
  getDepositReceipt,
  getMyBooking,
  getPaymentSummary,
  type ApiBooking,
  type ApiPayment,
  type DepositReceiptData,
} from "@/services/customerApi";

const money = (value: number) => `${value.toLocaleString("vi-VN")}đ`;

export function DepositSuccessPage() {
  const location = useLocation();
  const state = location.state as {
    booking?: ApiBooking;
    payment?: ApiPayment;
  } | null;
  const [booking, setBooking] = useState(state?.booking);
  const [payment, setPayment] = useState(state?.payment);
  const [receipt, setReceipt] = useState<DepositReceiptData>();
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const bookingId =
      booking?.id ||
      state?.booking?.id ||
      Number(sessionStorage.getItem("sporthub_latest_booking"));
    if (!bookingId) return;
    const nextBooking = await getMyBooking(bookingId);
    setBooking(nextBooking);
    let depositPayment = payment;
    if (!depositPayment || depositPayment.payment_type !== "deposit") {
      const summary = await getPaymentSummary(nextBooking.id);
      depositPayment = summary.transactions.find(
        (item) => item.payment_type === "deposit" && item.status === "paid",
      );
      setPayment(depositPayment);
    }
    if (depositPayment) setReceipt(await getDepositReceipt(depositPayment.id));
  }, [booking?.id, payment?.id, state?.booking?.id]);

  useEffect(() => {
    void load().finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    const shouldPoll =
      booking?.status === "pending_confirmation" ||
      ["refund_pending", "refund_overdue"].includes(
        booking?.refund_status || "",
      );
    if (!shouldPoll) return;
    const poll = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(poll);
  }, [booking?.status, booking?.refund_status, load]);

  if (loading)
    return (
      <div className="mx-auto max-w-3xl p-8">
        <LoadingSkeleton lines={9} />
      </div>
    );
  if (!booking)
    return (
      <div className="mx-auto max-w-2xl p-8">
        <EmptyState
          title="Không tìm thấy booking"
          description="Không thể tải yêu cầu đặt sân."
        />
      </div>
    );

  const waiting = booking.status === "pending_confirmation";
  const rejected = ["rejected", "cancelled_by_owner"].includes(booking.status);
  const refunded = booking.refund_status === "refunded";

  return (
    <main className="receipt-page mx-auto max-w-3xl px-4 py-10">
      <section className="receipt-web-summary overflow-hidden rounded-2xl border bg-white shadow-card">
        <header
          className={`p-7 text-center text-white ${waiting ? "bg-amber-500" : rejected ? "bg-red-600" : "bg-emerald-600"}`}
        >
          {waiting ? (
            <Clock3 className="mx-auto" size={54} />
          ) : rejected ? (
            <XCircle className="mx-auto" size={54} />
          ) : (
            <CheckCircle2 className="mx-auto" size={54} />
          )}
          <h1 className="mt-3 text-2xl font-black">
            {waiting
              ? "ĐÃ THANH TOÁN CỌC"
              : rejected
                ? "YÊU CẦU ĐẶT SÂN BỊ TỪ CHỐI"
                : "ĐẶT SÂN THÀNH CÔNG"}
          </h1>
          <p className="mt-1">
            {waiting
              ? "Đang chờ chủ sân xác nhận. Khung giờ vẫn được khóa cho bạn."
              : refunded
                ? "Tiền cọc đã được hoàn cho bạn."
                : rejected
                  ? "Tiền cọc đã được ghi nhận chờ hoàn."
                  : "Chủ sân đã xác nhận và sân được giữ chính thức."}
          </p>
        </header>
        <div className="p-6">
          <div className="grid gap-3 sm:grid-cols-2">
            <Info label="Mã đặt sân" value={booking.booking_code} />
            <Info
              label="Trạng thái"
              value={receipt?.status_message || "Đã thanh toán cọc"}
            />
            <Info label="Sân" value={booking.field_name} />
            <Info
              label="Ngày và giờ"
              value={`${booking.booking_date} · ${booking.selected_slots
                .map(
                  (slot) =>
                    `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`,
                )
                .join(", ")}`}
            />
          </div>
          <div className="mt-5 rounded-xl bg-slate-50 p-4">
            <Money label="Tiền sân" value={booking.court_amount} />
            <Money label="Dịch vụ thêm" value={booking.service_amount} />
            {booking.product_items.map((item) => (
              <Money
                key={item.product_id}
                label={`${item.name} × ${item.quantity}`}
                value={item.subtotal}
              />
            ))}
            <Money label="Tổng cộng" value={booking.total_amount} strong />
            <Money
              label="Đã đặt cọc"
              value={receipt?.deposit_paid ?? booking.deposit_amount}
            />
            <Money
              label="Còn phải thanh toán"
              value={receipt?.remaining_amount ?? booking.remaining_amount}
            />
            {rejected && (
              <Money
                label={refunded ? "Tiền cọc đã hoàn" : "Tiền cọc chờ hoàn"}
                value={
                  booking.refund_amount ||
                  booking.refundable_deposit_amount ||
                  booking.deposit_amount
                }
              />
            )}
          </div>
          {waiting && (
            <div className="mt-5 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
              Trang tự động kiểm tra kết quả xác nhận mỗi 5 giây. Bạn có thể
              đóng trang và xem lại trong lịch đặt sân.
            </div>
          )}
          <div className="mt-6 grid gap-3 sm:grid-cols-2 print:hidden">
            <Link to={`/customer/bookings/${booking.id}`}>
              <Button className="w-full">Xem chi tiết</Button>
            </Link>
            <Link to="/customer/bookings">
              <Button className="w-full" variant="outline">
                Lịch đặt sân của tôi
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {receipt ? (
        <section className="mt-7">
          <DepositReceipt receipt={receipt} />
        </section>
      ) : (
        <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          Biên lai sẽ hiển thị sau khi backend xác nhận giao dịch đặt cọc.
        </div>
      )}
    </main>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="block text-xs text-slate-500">{label}</span>
      <b>{value}</b>
    </div>
  );
}

function Money({
  label,
  value,
  strong = false,
}: {
  label: string;
  value: number;
  strong?: boolean;
}) {
  return (
    <div
      className={`flex justify-between py-1 ${strong ? "font-bold text-brand-700" : ""}`}
    >
      <span>{label}</span>
      <span>{money(value)}</span>
    </div>
  );
}
