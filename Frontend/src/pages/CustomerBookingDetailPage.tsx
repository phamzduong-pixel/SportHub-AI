import {
  CalendarDays,
  Clock3,
  MapPin,
  Phone,
  Printer,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Badge,
  Button,
  EmptyState,
  Input,
  LoadingSkeleton,
  PageHeader,
  useToast,
} from "@/components/common";
import { RefundStatusPanel } from "@/components/refunds/RefundStatusPanel";
import { TransactionHistory } from "@/components/payments/TransactionHistory";
import { apiRequest } from "@/services/apiClient";
import {
  cancelMyBooking,
  createComplaint,
  getBookingInvoice,
  getCancellationQuote,
  getMyBooking,
  getMyComplaints,
  getMyRefunds,
  getPaymentSummary,
  getRescheduleQuote,
  payBooking,
  rescheduleBooking,
  type ApiBooking,
  type BookingInvoice,
  type CancellationQuote,
  type BookingComplaint,
  type PaymentSummary,
  type RefundRequest,
  type RescheduleQuote,
} from "@/services/customerApi";

interface AvailableSlot {
  id: number;
  name: string;
  start_time: string;
  end_time: string;
  price: number;
}
interface AvailableField {
  field: {
    id: number;
    facility_id: number | null;
    name: string;
    sport_type: string;
    location: string;
  };
  available_slots: AvailableSlot[];
}
const money = (value: number) =>
  `${Number(value || 0).toLocaleString("vi-VN")}đ`;
const bookingLabels: Record<string, string> = {
  pending_payment: "Chờ thanh toán cọc",
  pending_confirmation: "Đã cọc – Chờ xác nhận",
  confirmed: "Đã xác nhận",
  in_progress: "Đang sử dụng",
  completed: "Hoàn thành",
  no_show: "Không đến sân",
  cancelled: "Đã hủy",
  cancelled_by_customer: "Khách đã hủy",
  cancelled_by_owner: "Chủ sân đã hủy",
  expired: "Hết hạn thanh toán",
  rejected: "Chủ sân từ chối",
  failed: "Thất bại",
};
const paymentLabels: Record<string, string> = {
  unpaid: "Chưa thanh toán",
  pending: "Đang xử lý",
  partial: "Đã đặt cọc",
  paid: "Đã thanh toán đủ",
  refund_pending: "Chờ hoàn tiền",
  refund_overdue: "Hoàn tiền quá hạn",
  refunded: "Đã hoàn tiền",
  disputed: "Đang khiếu nại",
};
const activityLabels: Record<string, string> = {
  booking_created: "Đã tạo booking",
  deposit_held: "Đã thanh toán tiền cọc",
  booking_confirmed: "Chủ sân đã xác nhận",
  remaining_payment_held: "Đã thanh toán số tiền còn lại",
  booking_in_progress: "Đã bắt đầu sử dụng sân",
  booking_completed_funds_released: "Booking đã hoàn thành",
  owner_added_booking_product: "Chủ sân đã thêm dịch vụ phát sinh",
  owner_updated_booking_product: "Chủ sân đã đổi số lượng dịch vụ phát sinh",
  owner_removed_booking_product: "Chủ sân đã xóa dịch vụ phát sinh",
  customer_cancelled_booking: "Khách hàng đã hủy booking",
  owner_cancelled_booking: "Chủ sân đã hủy booking",
  owner_rejected_booking: "Chủ sân đã từ chối booking",
  refund_completed: "Đã hoàn tiền",
};

export function CustomerBookingDetailPage() {
  const { bookingId = "" } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [booking, setBooking] = useState<ApiBooking>();
  const [summary, setSummary] = useState<PaymentSummary>();
  const [refund, setRefund] = useState<RefundRequest>();
  const [complaint, setComplaint] = useState<BookingComplaint>();
  const [complaintText, setComplaintText] = useState("");
  const [complaintCategory, setComplaintCategory] = useState("service");
  const [invoice, setInvoice] = useState<BookingInvoice>();
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [cancelQuote, setCancelQuote] = useState<CancellationQuote>();
  const [cancelReason, setCancelReason] = useState("");
  const [showReschedule, setShowReschedule] = useState(false);
  const [newDate, setNewDate] = useState("");
  const [availability, setAvailability] = useState<AvailableField[]>([]);
  const [newFieldId, setNewFieldId] = useState<number>();
  const [newSlotIds, setNewSlotIds] = useState<number[]>([]);
  const [rescheduleQuote, setRescheduleQuote] = useState<RescheduleQuote>();
  const load = async () => {
    const next = await getMyBooking(bookingId);
    setBooking(next);
    const [paymentSummary, refunds, complaints] = await Promise.all([
      getPaymentSummary(next.id),
      getMyRefunds(),
      getMyComplaints(),
    ]);
    setSummary(paymentSummary);
    setRefund(refunds.items.find((item) => item.booking_id === next.id));
    setComplaint(complaints.find((item) => item.booking_id === next.id));
    if (next.status === "completed")
      setInvoice(await getBookingInvoice(next.id));
  };
  useEffect(() => {
    load()
      .catch((error) =>
        toast(
          error instanceof Error ? error.message : "Không tải được booking.",
          "error",
        ),
      )
      .finally(() => setLoading(false));
  }, [bookingId]);
  useEffect(() => {
    if (!booking || !["confirmed", "in_progress"].includes(booking.status)) return;
    const timer = window.setInterval(() => {
      getMyBooking(bookingId).then(setBooking).catch(() => undefined);
    }, 10000);
    return () => window.clearInterval(timer);
  }, [bookingId, booking?.status]);
  const pay = async () => {
    if (!booking) return;
    setBusy(true);
    try {
      const result = await payBooking(booking);
      setBooking(result.booking);
      setSummary(await getPaymentSummary(booking.id));
      toast(
        result.payment.payment_type === "deposit"
          ? "Đặt cọc thành công."
          : "Thanh toán thành công",
        "success",
      );
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Thanh toán thất bại.",
        "error",
      );
    } finally {
      setBusy(false);
    }
  };
  const prepareCancel = async () => {
    if (!booking) return;
    setBusy(true);
    try {
      setCancelQuote(await getCancellationQuote(booking.id));
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không thể tính khoản hoàn.",
        "error",
      );
    } finally {
      setBusy(false);
    }
  };
  const cancel = async () => {
    if (!booking || !cancelQuote || cancelReason.trim().length < 3)
      return toast("Vui lòng nhập lý do hủy.", "error");
    const late = cancelQuote.is_late_cancellation;
    setBusy(true);
    try {
      await cancelMyBooking(booking.id, cancelReason.trim());
      setCancelQuote(undefined);
      await load();
      toast(
        late
          ? "Đã hủy booking. Tiền đặt cọc không được hoàn lại."
          : "Đã hủy booking và hoàn 100% tiền đặt cọc.",
        "success",
      );
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không thể hủy booking.",
        "error",
      );
    } finally {
      setBusy(false);
    }
  };
  const findSlots = async () => {
    if (!booking || !newDate) return;
    setBusy(true);
    setRescheduleQuote(undefined);
    setNewFieldId(undefined);
    setNewSlotIds([]);
    try {
      const result = await apiRequest<AvailableField[]>(
        `/availability?date=${newDate}`,
      );
      setAvailability(
        result.filter((entry) =>
          booking.facility_id
            ? entry.field.facility_id === booking.facility_id
            : entry.field.id === booking.field_id,
        ),
      );
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không tải được lịch trống.",
        "error",
      );
    } finally {
      setBusy(false);
    }
  };
  const selectedEntry = useMemo(
    () => availability.find((entry) => entry.field.id === newFieldId),
    [availability, newFieldId],
  );
  const selectedSlots = useMemo(
    () =>
      (selectedEntry?.available_slots || [])
        .filter((slot) => newSlotIds.includes(slot.id))
        .sort((a, b) => a.start_time.localeCompare(b.start_time)),
    [newSlotIds, selectedEntry],
  );
  const toggleNewSlot = (field: AvailableField, slot: AvailableSlot) => {
    setRescheduleQuote(undefined);
    if (newFieldId !== field.field.id) {
      setNewFieldId(field.field.id);
      setNewSlotIds([slot.id]);
      return;
    }
    setNewSlotIds((current) =>
      current.includes(slot.id)
        ? current.filter((slotId) => slotId !== slot.id)
        : [...current, slot.id],
    );
  };
  const reschedulePayload = () =>
    selectedEntry && selectedSlots.length
      ? {
          field_id: selectedEntry.field.id,
          time_slot_id: selectedSlots[0].id,
          time_slot_ids: selectedSlots.map((slot) => slot.id),
          booking_date: newDate,
        }
      : undefined;
  const quoteReschedule = async () => {
    const payload = reschedulePayload();
    if (!booking || !payload) return;
    setBusy(true);
    try {
      setRescheduleQuote(await getRescheduleQuote(booking.id, payload));
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Lịch mới không còn hợp lệ.",
        "error",
      );
    } finally {
      setBusy(false);
    }
  };
  const confirmReschedule = async () => {
    const payload = reschedulePayload();
    if (!booking || !payload || !rescheduleQuote) return;
    const schedule = selectedSlots
      .map(
        (slot) => `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`,
      )
      .join(", ");
    if (!window.confirm(`Xác nhận đổi sang ${newDate}: ${schedule}?`)) return;
    setBusy(true);
    try {
      await rescheduleBooking(booking.id, payload);
      setShowReschedule(false);
      setRescheduleQuote(undefined);
      setAvailability([]);
      setNewFieldId(undefined);
      setNewSlotIds([]);
      await load();
      toast(
        "Đã đổi lịch và làm mới booking, lịch sân cùng giao dịch liên quan.",
        "success",
      );
    } catch (error) {
      toast(
        error instanceof Error
          ? error.message
          : "Một hoặc nhiều khung giờ vừa được người khác đặt. Vui lòng tải lại lịch trống.",
        "error",
      );
      await findSlots();
    } finally {
      setBusy(false);
    }
  };
  const complain = async () => {
    if (!booking || complaintText.trim().length < 5)
      return toast("Vui lòng mô tả vấn đề ít nhất 5 ký tự.", "error");
    setBusy(true);
    try {
      setComplaint(
        await createComplaint(
          booking.id,
          complaintCategory,
          complaintText.trim(),
        ),
      );
      toast("Đã gửi khiếu nại đến bộ phận quản lý.", "success");
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không thể gửi khiếu nại.",
        "error",
      );
    } finally {
      setBusy(false);
    }
  };
  if (loading) return <LoadingSkeleton lines={9} />;
  if (!booking)
    return (
      <EmptyState
        title="Không tìm thấy booking"
        description="Booking không tồn tại hoặc không thuộc tài khoản của bạn."
      />
    );
  const canPay =
    booking.status === "pending_payment" ||
    (["confirmed", "in_progress"].includes(booking.status) &&
      booking.remaining_amount > 0);
  const cancellable = [
    "pending_payment",
    "pending_confirmation",
    "confirmed",
  ].includes(booking.status);
  const minutesUntilStart =
    (new Date(
      `${booking.booking_date}T${booking.start_time_snapshot}`,
    ).getTime() -
      Date.now()) /
    60000;
  const reschedulable =
    ["pending_confirmation", "confirmed"].includes(booking.status) &&
    minutesUntilStart >= booking.free_cancellation_minutes;
  return (
    <>
      <button
        onClick={() => navigate(-1)}
        className="mb-4 text-sm font-semibold text-brand-700"
      >
        ← Quay lại
      </button>
      <PageHeader
        title={`Chi tiết ${booking.booking_code}`}
        description={`Đặt lúc ${new Date(booking.created_at).toLocaleString("vi-VN")}`}
      />
      {booking.status === "pending_payment" && booking.hold_expires_at && (
        <Countdown expiresAt={booking.hold_expires_at} />
      )}
      <div className="grid gap-5 lg:grid-cols-[1fr_420px]">
        <section className="rounded-card border bg-white p-5">
          <Link
            to={`/courts/${booking.field_id}`}
            className="text-xl font-bold hover:text-brand-700 hover:underline"
          >
            {booking.field_name}
          </Link>
          <p className="text-brand-700">
            {booking.facility_name} · {booking.sport_type}
          </p>
          <div className="mt-5 space-y-3 text-sm">
            <p>
              <MapPin size={16} className="mr-2 inline" />
              <b>Cơ sở:</b> {booking.location}
            </p>
            <p>
              <CalendarDays size={16} className="mr-2 inline" />
              <b>Ngày chơi:</b>{" "}
              {new Date(`${booking.booking_date}T00:00`).toLocaleDateString(
                "vi-VN",
              )}
            </p>
            <p>
              <Clock3 size={16} className="mr-2 inline" />
              <b>Khung giờ:</b> {booking.selected_slots.length} khung ·{" "}
              {booking.duration_minutes} phút
            </p>
            <p className="pl-6 text-slate-600">
              {booking.selected_slots
                .map(
                  (slot) =>
                    `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`,
                )
                .join(", ")}
            </p>
          </div>
          {booking.facility_hotline && (
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand-100 bg-brand-50 p-3 text-sm">
              <span>
                <Phone size={16} className="mr-2 inline text-brand-700" />
                <span className="text-slate-600">Hotline cơ sở:</span>{" "}
                <a
                  href={`tel:${booking.facility_hotline.replace(/[^\d+]/g, "")}`}
                  className="font-normal text-brand-800 hover:underline"
                >
                  {booking.facility_hotline}
                </a>
              </span>
              <a
                href={`tel:${booking.facility_hotline.replace(/[^\d+]/g, "")}`}
                className="inline-flex min-h-10 items-center rounded-lg bg-brand-600 px-4 font-bold text-white hover:bg-brand-700"
              >
                Gọi chủ sân
              </a>
            </div>
          )}
          <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
            <b>Chính sách hủy:</b> Hủy trước giờ chơi ít nhất{" "}
            {booking.free_cancellation_minutes / 60} giờ được hoàn 100% tiền
            cọc; hủy muộn hơn sẽ mất tiền cọc.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Badge>{bookingLabels[booking.status] || booking.status}</Badge>
            <Badge>
              {paymentLabels[booking.payment_status] || booking.payment_status}
            </Badge>
          </div>
          {booking.cancellation_reason && (
            <p className="mt-4 rounded-lg bg-slate-50 p-3 text-sm">
              <b>Lý do hủy:</b> {booking.cancellation_reason}
            </p>
          )}
          <div className="mt-5 border-t pt-4">
            <h2 className="font-bold">Sản phẩm & dịch vụ đi kèm</h2>
            {booking.product_items.length ? (
              <div className="mt-3 space-y-2 text-sm">
                {booking.product_items.map((item) => (
                  <div key={item.item_id || item.product_id} className="flex justify-between gap-3 border-b pb-2">
                    <span>
                      {item.name} · {item.quantity} {item.unit} × {money(item.unit_price)}
                      {item.source === "OWNER_DURING_USAGE" && (
                        <small className="block text-brand-700">Phát sinh tại sân{item.added_at ? ` · ${new Date(item.added_at).toLocaleString("vi-VN")}` : ""}</small>
                      )}
                    </span>
                    <b>{money(item.subtotal)}</b>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-500">Booking không có dịch vụ thêm.</p>
            )}
          </div>
        </section>
        <section className="rounded-card border bg-white p-5">
          <h2 className="font-bold">Thanh toán</h2>
          <p className="mt-1 rounded-lg bg-blue-50 p-2 text-xs text-blue-700">
            Theo dõi tiền đặt cọc, số tiền đã thanh toán và khoản còn lại của
            booking.
          </p>
          <div className="mt-4 space-y-3 text-sm">
            <Row label="Tiền sân" value={booking.court_amount} />
            <Row label="Dịch vụ thêm" value={booking.service_amount} />
            <Row label="Tổng tiền" value={booking.total_amount} strong />
            <Row
              label="Đã cọc"
              value={Math.min(booking.paid_amount, booking.deposit_amount)}
            />
            <Row label="Đã thanh toán" value={booking.paid_amount} />
            <Row label="Còn lại" value={booking.remaining_amount} strong />
            {booking.refund_amount > 0 && (
              <Row label="Khoản hoàn" value={booking.refund_amount} />
            )}
            {booking.credit_amount > 0 && (
              <Row label="Số dư do đổi lịch" value={booking.credit_amount} />
            )}
          </div>
          {canPay && (
            <Button
              className="mt-5 w-full"
              loading={busy}
              onClick={() => void pay()}
            >
              {booking.additional_payment_required > 0
                ? `Thanh toán thêm ${money(booking.additional_payment_required)}`
                : booking.paid_amount < booking.deposit_amount
                  ? "Thanh toán tiền cọc"
                  : `Thanh toán còn lại ${money(booking.remaining_amount)}`}
            </Button>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            {booking.status === "completed" && !booking.reviewed && (
              <Link to={`/customer/reviews?booking=${booking.id}`}>
                <Button size="sm">Đánh giá sân</Button>
              </Link>
            )}
            {cancellable && (
              <Button
                variant="danger"
                size="sm"
                loading={busy}
                leftIcon={<XCircle size={15} />}
                onClick={() => void prepareCancel()}
              >
                Hủy lịch
              </Button>
            )}
            {reschedulable && (
              <Button
                variant="outline"
                size="sm"
                leftIcon={<RefreshCw size={15} />}
                onClick={() => setShowReschedule(!showReschedule)}
              >
                Đổi lịch
              </Button>
            )}
          </div>
          <TransactionHistory
            transactions={summary?.transactions ?? []}
            bookingId={booking.id}
            bookingCode={booking.booking_code}
          />
        </section>
      </div>
      {cancelQuote && (
        <section
          className={`mt-5 rounded-card border p-5 ${cancelQuote.is_late_cancellation ? "border-red-300 bg-red-50" : "border-brand-200 bg-brand-50"}`}
        >
          <h2 className="font-bold">Xác nhận hủy booking</h2>
          <p className="mt-2 text-sm">
            Còn {Math.floor(cancelQuote.minutes_before_start / 60)} giờ trước
            giờ chơi. Mốc hủy miễn phí là trước ít nhất{" "}
            <b>{cancelQuote.free_cancellation_minutes / 60} giờ</b>.
          </p>
          {cancelQuote.is_late_cancellation ? (
            <div className="mt-3 rounded-lg border border-red-300 bg-white p-3 text-sm font-semibold text-red-700">
              Bạn đã quá thời hạn hủy miễn phí. Nếu tiếp tục hủy, tiền đặt cọc
              sẽ không được hoàn lại.
            </div>
          ) : (
            <div className="mt-3 rounded-lg bg-white p-3 text-sm text-brand-800">
              Bạn đang hủy đúng hạn và sẽ được hoàn 100% tiền đặt cọc:{" "}
              <b>{money(cancelQuote.refund_amount)}</b>.
            </div>
          )}
          <Input
            className="mt-4"
            label="Lý do hủy *"
            value={cancelReason}
            onChange={(event) => setCancelReason(event.target.value)}
            placeholder="Nhập ít nhất 3 ký tự"
          />
          <div className="mt-4 flex gap-2">
            <Button
              variant="danger"
              loading={busy}
              onClick={() => void cancel()}
            >
              {cancelQuote.is_late_cancellation
                ? "Vẫn hủy và chấp nhận mất cọc"
                : "Xác nhận hủy"}
            </Button>
            <Button variant="ghost" onClick={() => setCancelQuote(undefined)}>
              Giữ booking
            </Button>
          </div>
        </section>
      )}
      {showReschedule && (
        <section className="mt-5 rounded-card border bg-white p-5">
          <h2 className="font-bold">
            Đổi ngày / sân / nhiều khung giờ trong cùng cơ sở
          </h2>
          <div className="mt-3 rounded-xl bg-slate-50 p-4 text-sm">
            <b>Lịch hiện tại</b>
            <p>
              {booking.field_name} ·{" "}
              {new Date(`${booking.booking_date}T00:00`).toLocaleDateString(
                "vi-VN",
              )}{" "}
              ·{" "}
              {booking.selected_slots
                .map(
                  (slot) =>
                    `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`,
                )
                .join(", ")}
            </p>
          </div>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <Input
              type="date"
              min={new Date().toISOString().slice(0, 10)}
              value={newDate}
              onChange={(event) => {
                setNewDate(event.target.value);
                setNewFieldId(undefined);
                setNewSlotIds([]);
                setAvailability([]);
                setRescheduleQuote(undefined);
              }}
            />
            <Button
              variant="outline"
              loading={busy}
              onClick={() => void findSlots()}
            >
              Kiểm tra lịch trống
            </Button>
          </div>
          {availability.length > 0 ? (
            <div className="mt-4 space-y-4">
              {availability.map((entry) => (
                <div key={entry.field.id}>
                  <p className="mb-2 text-sm font-semibold">
                    {entry.field.name}
                  </p>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {entry.available_slots.map((slot) => (
                      <button
                        type="button"
                        key={slot.id}
                        onClick={() => toggleNewSlot(entry, slot)}
                        className={`rounded-lg border px-3 py-2 text-left text-xs ${newFieldId === entry.field.id && newSlotIds.includes(slot.id) ? "border-brand-600 bg-brand-50 text-brand-700 ring-2 ring-brand-100" : "border-slate-200 hover:border-brand-400"}`}
                      >
                        <b>
                          {slot.start_time.slice(0, 5)}–
                          {slot.end_time.slice(0, 5)}
                        </b>
                        <span className="mt-1 block">{money(slot.price)}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            newDate && (
              <p className="mt-4 text-sm text-slate-500">
                Không có khung giờ trống phù hợp trong cơ sở.
              </p>
            )
          )}
          {selectedSlots.length > 0 && !rescheduleQuote && (
            <div className="mt-4">
              <p className="mb-2 text-sm">
                Đã chọn <b>{selectedSlots.length} khung giờ</b>:{" "}
                {selectedSlots
                  .map(
                    (slot) =>
                      `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`,
                  )
                  .join(", ")}
              </p>
              <Button loading={busy} onClick={() => void quoteReschedule()}>
                Xem chênh lệch giá
              </Button>
            </div>
          )}
          {rescheduleQuote && (
            <div className="mt-4 rounded-xl bg-brand-50 p-4 text-sm">
              <p className="mb-3">
                <b>Lịch mới:</b> {selectedEntry?.field.name} ·{" "}
                {new Date(`${newDate}T00:00`).toLocaleDateString("vi-VN")} ·{" "}
                {selectedSlots
                  .map(
                    (slot) =>
                      `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`,
                  )
                  .join(", ")}{" "}
                ({selectedSlots.length} khung)
              </p>
              <Row
                label="Giá lịch cũ"
                value={rescheduleQuote.old_total_amount}
              />
              <Row
                label="Giá lịch mới"
                value={rescheduleQuote.new_total_amount}
              />
              <Row
                label="Đã đặt cọc / thanh toán"
                value={booking.paid_amount}
              />
              <Row
                label="Cần thanh toán thêm"
                value={rescheduleQuote.additional_payment_required}
              />
              <Row
                label="Chênh lệch ghi nhận"
                value={rescheduleQuote.credit_amount}
              />
              <p className="mt-3 text-xs text-slate-600">
                Khoản chênh lệch giảm giá chỉ được ghi nhận để xử lý theo chính
                sách, không tự động hoàn tiền.
              </p>
              <Button
                className="mt-4"
                loading={busy}
                onClick={() => void confirmReschedule()}
              >
                Xác nhận đổi lịch
              </Button>
            </div>
          )}
        </section>
      )}
      {refund && (
        <RefundStatusPanel
          initial={refund}
          mode="customer"
          onChanged={setRefund}
        />
      )}
      <section className="mt-5 rounded-card border bg-white p-5">
        <h2 className="font-bold">Lịch sử booking</h2>
        <div className="mt-4 space-y-3">
          {booking.timeline.length ? (
            booking.timeline.map((event) => (
              <div
                key={event.id}
                className="border-l-2 border-brand-200 pl-3 text-sm"
              >
                <b>{activityLabels[event.action] || "Đã cập nhật booking"}</b>
                <p className="text-slate-500">
                  {event.actor_name || "Hệ thống"} ·{" "}
                  {new Date(event.created_at).toLocaleString("vi-VN")}
                </p>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500">
              Booking cũ chưa có dữ liệu timeline.
            </p>
          )}
        </div>
      </section>
      {booking.status !== "pending_payment" && (
        <section className="mt-5 rounded-card border bg-white p-5">
          <h2 className="font-bold">Báo cáo vấn đề booking</h2>
          {complaint ? (
            <div className="mt-3 rounded-lg bg-slate-50 p-4 text-sm">
              <p>
                <b>Trạng thái:</b> {complaint.status}
              </p>
              <p>
                <b>Nội dung:</b> {complaint.description}
              </p>
              {complaint.resolution && (
                <p>
                  <b>Phản hồi:</b> {complaint.resolution}
                </p>
              )}
            </div>
          ) : (
            <div className="mt-3 grid gap-3">
              <select
                className="field"
                value={complaintCategory}
                onChange={(event) => setComplaintCategory(event.target.value)}
              >
                <option value="service">Dịch vụ</option>
                <option value="facility">Cơ sở vật chất</option>
                <option value="payment">Thanh toán</option>
                <option value="safety">An toàn</option>
                <option value="other">Khác</option>
              </select>
              <Input
                value={complaintText}
                onChange={(event) => setComplaintText(event.target.value)}
                placeholder="Mô tả vấn đề cần hỗ trợ..."
              />
              <Button
                className="w-fit"
                variant="outline"
                loading={busy}
                onClick={() => void complain()}
              >
                Gửi khiếu nại
              </Button>
            </div>
          )}
        </section>
      )}
      {invoice && <CompletedInvoice invoice={invoice} />}
    </>
  );
}
function Countdown({ expiresAt }: { expiresAt: string }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const seconds = Math.max(
    0,
    Math.floor((new Date(expiresAt).getTime() - now) / 1000),
  );
  return (
    <div className="mb-5 rounded-card border border-amber-200 bg-amber-50 p-4 text-sm">
      <b>
        Thời gian giữ sân còn{" "}
        {String(Math.floor(seconds / 60)).padStart(2, "0")}:
        {String(seconds % 60).padStart(2, "0")}
      </b>
      <p className="text-amber-800">
        Vui lòng hoàn tất thanh toán trước khi thời gian giữ sân kết thúc.
      </p>
    </div>
  );
}
function Row({
  label,
  value,
  strong,
}: {
  label: string;
  value: number;
  strong?: boolean;
}) {
  return (
    <div
      className={`flex justify-between border-b pb-2 ${strong ? "font-bold text-brand-700" : ""}`}
    >
      <span>{label}</span>
      <span>{money(value)}</span>
    </div>
  );
}
function CompletedInvoice({ invoice }: { invoice: BookingInvoice }) {
  return (
    <section className="mt-5 rounded-card border bg-white p-6">
      <h2 className="text-xl font-bold">HÓA ĐƠN {invoice.invoice_number}</h2>
      <p className="text-sm text-slate-500">
        Booking {invoice.booking_code} · xuất{" "}
        {new Date(invoice.issued_at).toLocaleString("vi-VN")}
      </p>
      <div className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
        <p>
          <b>Khách:</b> {invoice.customer_name}
        </p>
        <p>
          <b>Cơ sở:</b> {invoice.facility_name}
        </p>
        <p>
          <b>Sân:</b> {invoice.field_name}
        </p>
        <p>
          <b>Ngày giờ:</b> {invoice.booking_date} ·{" "}
          {invoice.selected_slots.length} khung · {invoice.duration_minutes} phút
        </p>
      </div>
      {invoice.selected_slots.length > 0 && (
        <div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm">
          {invoice.selected_slots.map((slot) => (
            <div
              key={slot.time_slot_id}
              className="flex justify-between border-t py-2"
            >
              <span>
                {slot.start_time.slice(0, 5)}–{slot.end_time.slice(0, 5)}
              </span>
              <b>{money(slot.price)}</b>
            </div>
          ))}
        </div>
      )}
      {invoice.product_items.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-xl border p-3 text-sm">
          <div className="grid min-w-[520px] grid-cols-[1fr_70px_110px_120px] gap-2 border-b pb-2 text-xs font-semibold text-slate-500">
            <span>Sản phẩm / dịch vụ</span><span>SL</span><span>Đơn giá</span><span className="text-right">Thành tiền</span>
          </div>
          {invoice.product_items.map((item) => (
            <div key={item.product_id} className="grid min-w-[520px] grid-cols-[1fr_70px_110px_120px] gap-2 border-b py-2">
              <span>{item.name}</span>
              <span>{item.quantity} {item.unit}</span>
              <span>{money(item.unit_price)}</span>
              <b className="text-right">{money(item.subtotal)}</b>
            </div>
          ))}
        </div>
      )}
      <div className="mt-4 space-y-2 text-sm">
        <Row label="Tiền sân" value={invoice.court_amount} />
        <Row label="Dịch vụ thêm" value={invoice.service_amount} />
        <Row label="Tổng cộng" value={invoice.total_amount} />
        <Row label="Tiền cọc" value={invoice.deposit_amount} />
        <Row
          label="Thanh toán còn lại"
          value={invoice.remaining_payment_amount}
        />
        <Row label="Giảm / hoàn" value={invoice.refund_amount} />
        <Row label="Thực nhận" value={invoice.net_received_amount} strong />
      </div>
      <p className="mt-3 text-sm">
        Phương thức: <b>{invoice.payment_methods}</b> · Thanh toán:{" "}
        <b>
          {invoice.paid_at
            ? new Date(invoice.paid_at).toLocaleString("vi-VN")
            : "Dữ liệu lịch sử"}
        </b>
      </p>
      <Button
        className="mt-4 print:hidden"
        variant="outline"
        leftIcon={<Printer size={16} />}
        onClick={() => window.print()}
      >
        In hóa đơn
      </Button>
    </section>
  );
}
