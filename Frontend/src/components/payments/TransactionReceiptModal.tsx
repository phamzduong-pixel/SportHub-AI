import html2canvas from "html2canvas";
import { Activity, CalendarDays, Clock3, Download, MapPin } from "lucide-react";
import { useRef, useState } from "react";
import { Badge, Button, Modal, useToast } from "@/components/common";
import type { ApiBooking, ApiPayment } from "@/services/customerApi";

interface Props {
  payment?: ApiPayment;
  booking?: ApiBooking;
  loading: boolean;
  error: string;
  onClose: () => void;
}

const money = (value: number) =>
  `${Number(value || 0).toLocaleString("vi-VN")}đ`;

const transactionTime = (payment: ApiPayment) =>
  payment.refunded_at || payment.paid_at || payment.created_at;

function paymentStatus(payment: ApiPayment) {
  if (
    payment.payment_type === "refund" ||
    payment.status === "refunded" ||
    payment.refund_status === "refunded"
  ) {
    return { label: "Đã hoàn tiền", variant: "success" as const };
  }
  if (
    payment.refund_status === "refund_pending" ||
    payment.status === "pending"
  ) {
    return { label: "Đang xử lý", variant: "warning" as const };
  }
  if (payment.status === "paid")
    return { label: "Đã thanh toán", variant: "success" as const };
  return { label: "Không thành công", variant: "danger" as const };
}

export function TransactionReceiptModal({
  payment,
  booking,
  loading,
  error,
  onClose,
}: Props) {
  const receiptRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);
  const { toast } = useToast();

  const downloadImage = async () => {
    if (!receiptRef.current || !payment) return;
    setExporting(true);
    try {
      const canvas = await html2canvas(receiptRef.current, {
        backgroundColor: "#ffffff",
        scale: Math.max(2, window.devicePixelRatio || 1),
        useCORS: true,
        logging: false,
      });
      const link = document.createElement("a");
      link.download = `sporthub-ai-${payment.transaction_code}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
      toast("Đã tải hóa đơn dạng ảnh PNG.", "success");
    } catch {
      toast("Không thể tạo ảnh hóa đơn. Vui lòng thử lại.", "error");
    } finally {
      setExporting(false);
    }
  };

  const status = payment ? paymentStatus(payment) : undefined;
  const refundAmount =
    payment?.payment_type === "refund" || payment?.status === "refunded"
      ? payment.amount
      : 0;

  return (
    <Modal
      open={Boolean(payment)}
      onClose={onClose}
      title="Chi tiết hóa đơn"
      description={payment?.transaction_code}
    >
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div
              key={index}
              className="h-10 animate-pulse rounded-lg bg-slate-100"
            />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : (
        payment &&
        booking && (
          <div className="space-y-4">
            <div
              ref={receiptRef}
              className="overflow-hidden rounded-2xl border border-slate-200 bg-white text-slate-900"
            >
              <header className="flex items-center justify-between bg-gradient-to-r from-brand-700 to-brand-500 px-5 py-5 text-white">
                <div className="flex items-center gap-3">
                  <span className="grid h-11 w-11 place-items-center rounded-xl bg-white/15">
                    <Activity size={25} strokeWidth={2.5} />
                  </span>
                  <div>
                    <h3 className="text-xl font-extrabold">SportHub AI</h3>
                    <p className="text-xs text-brand-50">
                      Hóa đơn giao dịch điện tử
                    </p>
                  </div>
                </div>
                {status && (
                  <Badge variant={status.variant}>{status.label}</Badge>
                )}
              </header>

              <div className="p-5">
                <dl className="grid gap-3 text-sm sm:grid-cols-2">
                  <ReceiptField
                    label="Mã giao dịch"
                    value={payment.transaction_code}
                    mono
                  />
                  <ReceiptField
                    label="Mã booking"
                    value={payment.booking_code || booking.booking_code}
                    mono
                  />
                  <ReceiptField
                    label="Thời gian giao dịch"
                    value={new Date(transactionTime(payment)).toLocaleString(
                      "vi-VN",
                    )}
                  />
                  <ReceiptField
                    label="Loại giao dịch"
                    value={
                      payment.payment_type === "deposit"
                        ? "Đặt cọc"
                        : payment.payment_type === "refund"
                          ? "Hoàn tiền"
                          : "Thanh toán còn lại"
                    }
                  />
                </dl>

                <section className="mt-5 rounded-xl bg-slate-50 p-4">
                  <h4 className="font-bold">{booking.facility_name}</h4>
                  <p className="mt-1 text-sm font-semibold text-brand-700">
                    {booking.field_name} · {booking.sport_type} · Sân{" "}
                    {booking.field_capacity}
                  </p>
                  <div className="mt-3 space-y-2 text-sm text-slate-600">
                    <p>
                      <MapPin
                        size={15}
                        className="mr-2 inline text-brand-600"
                      />
                      {booking.location}
                    </p>
                    <p>
                      <CalendarDays
                        size={15}
                        className="mr-2 inline text-brand-600"
                      />
                      Ngày đá:{" "}
                      {new Date(
                        `${booking.booking_date}T00:00:00`,
                      ).toLocaleDateString("vi-VN")}
                    </p>
                    <p>
                      <Clock3
                        size={15}
                        className="mr-2 inline text-brand-600"
                      />
                      Khung giờ:{" "}
                      {booking.selected_slots
                        .map(
                          (slot) =>
                            `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`,
                        )
                        .join(", ")}
                    </p>
                  </div>
                </section>

                <section className="mt-5 space-y-3 border-t border-dashed border-slate-300 pt-5 text-sm">
                  {booking.selected_slots.map((slot) => (
                    <AmountRow
                      key={slot.time_slot_id}
                      label={`${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`}
                      value={slot.price}
                    />
                  ))}
                  <AmountRow label="Tiền sân" value={booking.court_amount} />
                  {booking.product_items.map((item) => (
                    <AmountRow
                      key={item.product_id}
                      label={`${item.name} · ${item.quantity} ${item.unit} × ${money(item.unit_price)}`}
                      value={item.subtotal}
                    />
                  ))}
                  <AmountRow label="Dịch vụ thêm" value={booking.service_amount} />
                  <AmountRow
                    label="Tổng cộng"
                    value={payment.total_amount || booking.total_amount}
                  />
                  <AmountRow
                    label={refundAmount ? "Số tiền hoàn" : "Số tiền cọc"}
                    value={
                      refundAmount ||
                      payment.deposit_amount ||
                      booking.deposit_amount
                    }
                    accent={refundAmount ? "refund" : "deposit"}
                  />
                  <AmountRow
                    label="Số tiền giao dịch này"
                    value={payment.amount}
                  />
                  <AmountRow
                    label="Số tiền còn lại"
                    value={payment.remaining_amount}
                    strong
                  />
                </section>

                <footer className="mt-5 border-t pt-4 text-center text-xs text-slate-400">
                  Hóa đơn được tạo tự động bởi SportHub AI
                </footer>
              </div>
            </div>

            <Button
              className="w-full"
              leftIcon={<Download size={17} />}
              loading={exporting}
              onClick={() => void downloadImage()}
            >
              Tải hóa đơn (Ảnh)
            </Button>
          </div>
        )
      )}
    </Modal>
  );
}

function ReceiptField({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd
        className={`mt-1 break-words font-semibold ${mono ? "font-mono text-xs" : ""}`}
      >
        {value}
      </dd>
    </div>
  );
}

function AmountRow({
  label,
  value,
  strong,
  accent,
}: {
  label: string;
  value: number;
  strong?: boolean;
  accent?: "deposit" | "refund";
}) {
  return (
    <div
      className={`flex items-center justify-between gap-4 ${strong ? "border-t pt-3 text-base font-extrabold" : ""}`}
    >
      <span className="text-slate-600">{label}</span>
      <span
        className={
          accent === "refund"
            ? "font-bold text-red-700"
            : accent === "deposit"
              ? "font-bold text-brand-700"
              : strong
                ? "text-slate-900"
                : "font-semibold"
        }
      >
        {money(value)}
      </span>
    </div>
  );
}
