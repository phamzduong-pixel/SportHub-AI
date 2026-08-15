import { Check, Download, Eye, Minus, Plus, Printer, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Badge,
  Button,
  EmptyState,
  Input,
  LoadingSkeleton,
  Modal,
  PageHeader,
  useToast,
} from "@/components/common";
import { RefundStatusPanel } from "@/components/refunds/RefundStatusPanel";
import { apiRequest } from "@/services/apiClient";
import {
  addManagedBookingProduct,
  cancelManagedBooking,
  completeManagedBooking,
  confirmManagedBooking,
  deleteManagedBookingProduct,
  getManagedRefunds,
  getPaymentSummary,
  noShowManagedBooking,
  rejectManagedBooking,
  startManagedBooking,
  updateManagedBookingProduct,
  type ApiBooking,
  type PaymentSummary,
  type RefundRequest,
} from "@/services/customerApi";
import { getBookingProductOptions, type FacilityProduct } from "@/services/productService";

const money = (value: number) => `${value.toLocaleString("vi-VN")}đ`;
const statusLabel: Record<string, string> = {
  pending_payment: "Chờ đặt cọc",
  pending_confirmation: "Chờ xác nhận",
  confirmed: "Đã xác nhận",
  in_progress: "Đang diễn ra",
  completed: "Hoàn thành",
  no_show: "Không đến sân",
  cancelled: "Đã hủy",
  cancelled_by_customer: "Khách đã hủy",
  cancelled_by_owner: "Chủ sân đã hủy",
  expired: "Hết hạn",
  rejected: "Đã từ chối",
};
const paymentLabel: Record<string, string> = {
  unpaid: "Chưa thanh toán",
  pending: "Đang xử lý",
  partial: "Đã đặt cọc",
  paid: "Đã thanh toán",
  refund_pending: "Chờ hoàn tiền",
  refund_overdue: "Hoàn tiền quá hạn",
  refunded: "Đã hoàn tiền",
  disputed: "Đang khiếu nại",
  failed: "Không thành công",
  cancelled: "Đã hủy",
};
const listBookings = () =>
  apiRequest<{ items: ApiBooking[]; total: number }>("/bookings?page_size=100");

export function ManagementBookingsPage() {
  const { toast } = useToast();
  const [items, setItems] = useState<ApiBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("today");
  const [busy, setBusy] = useState<number>();
  const load = () => listBookings().then((result) => setItems(result.items));
  useEffect(() => {
    load()
      .catch((e) =>
        toast(
          e instanceof Error ? e.message : "Không tải được booking.",
          "error",
        ),
      )
      .finally(() => setLoading(false));
  }, []);
  const rows = useMemo(
    () =>
      items.filter((item) => {
        const today = new Date().toISOString().slice(0, 10);
        const grouped =
          group === "today"
            ? item.booking_date === today
            : group === "upcoming"
              ? item.booking_date > today &&
                ![
                  "cancelled",
                  "cancelled_by_customer",
                  "cancelled_by_owner",
                  "expired",
                  "completed",
                  "no_show",
                ].includes(item.status)
              : group === "cancelled"
                ? [
                    "cancelled",
                    "cancelled_by_customer",
                    "cancelled_by_owner",
                    "expired",
                    "rejected",
                  ].includes(item.status)
                : item.status === group;
        return (
          grouped &&
          `${item.booking_code} ${item.customer_name} ${item.customer_phone || ""} ${item.field_name} ${item.booking_date}`
            .toLowerCase()
            .includes(query.toLowerCase())
        );
      }),
    [items, query, group],
  );
  const counts = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10);
    const result: Record<string, number> = {
      today: 0,
      upcoming: 0,
      pending_confirmation: 0,
      in_progress: 0,
      completed: 0,
      cancelled: 0,
      no_show: 0,
    };
    for (const item of items) {
      if (item.booking_date === today) result.today++;
      if (item.booking_date > today && !["cancelled", "cancelled_by_customer", "cancelled_by_owner", "expired", "completed", "no_show"].includes(item.status)) result.upcoming++;
      if (item.status === "pending_confirmation") result.pending_confirmation++;
      if (item.status === "in_progress") result.in_progress++;
      if (item.status === "completed") result.completed++;
      if (["cancelled", "cancelled_by_customer", "cancelled_by_owner", "expired", "rejected"].includes(item.status)) result.cancelled++;
      if (item.status === "no_show") result.no_show++;
    }
    return result;
  }, [items]);

  const decide = async (item: ApiBooking, accept: boolean) => {
    const reason = accept
      ? undefined
      : window.prompt("Nhập lý do từ chối booking (bắt buộc):")?.trim();
    if (!accept && (!reason || reason.length < 3))
      return toast("Phải nhập lý do từ chối ít nhất 3 ký tự.", "error");
    setBusy(item.id);
    try {
      const updated = accept
        ? await confirmManagedBooking(item.id)
        : await rejectManagedBooking(item.id, reason);
      setItems(items.map((x) => (x.id === updated.id ? updated : x)));
      toast(
        accept
          ? "Đã xác nhận booking."
          : "Đã từ chối; tiền cọc chuyển sang chờ hoàn.",
        "success",
      );
    } catch (e) {
      toast(
        e instanceof Error ? e.message : "Không thể cập nhật booking.",
        "error",
      );
    } finally {
      setBusy(undefined);
    }
  };
  const transition = async (
    item: ApiBooking,
    action: "start" | "complete" | "no_show",
  ) => {
    setBusy(item.id);
    try {
      const updated =
        action === "start"
          ? await startManagedBooking(item.id)
          : action === "complete"
            ? await completeManagedBooking(item.id)
            : await noShowManagedBooking(item.id);
      setItems((current) =>
        current.map((entry) => (entry.id === updated.id ? updated : entry)),
      );
      toast("Đã cập nhật trạng thái booking.", "success");
    } catch (error) {
      toast(
        error instanceof Error
          ? error.message
          : "Chuyển trạng thái không hợp lệ.",
        "error",
      );
    } finally {
      setBusy(undefined);
    }
  };
  const exportCsv = () => {
    const content = [
      "Mã,Khách hàng,Sân,Tổng tiền,Đã cọc,Còn lại,Thanh toán,Booking",
      ...rows.map((x) =>
        [
          x.booking_code,
          x.customer_name,
          x.field_name,
          x.total_amount,
          Math.min(x.paid_amount, x.deposit_amount),
          x.remaining_amount,
          paymentLabel[x.payment_status],
          statusLabel[x.status],
        ].join(","),
      ),
    ].join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["\ufeff", content]));
    a.download = "bookings.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const groups = [
    ["today", "Hôm nay"],
    ["upcoming", "Sắp tới"],
    ["pending_confirmation", "Chờ xác nhận"],
    ["in_progress", "Đang diễn ra"],
    ["completed", "Đã hoàn thành"],
    ["cancelled", "Đã hủy"],
    ["no_show", "No-show"],
  ];
  return (
    <>
      <PageHeader
        title="Quản lý booking"
        description="Dữ liệu thật của các sân thuộc OWNER, được lọc theo đúng quyền OWNER."
        actions={
          <Button
            variant="outline"
            leftIcon={<Download size={16} />}
            onClick={exportCsv}
          >
            Xuất CSV
          </Button>
        }
      />
      <div className="mb-4 flex gap-1 overflow-x-auto pb-2">
        {groups.map(([value, label]) => (
          <button
            key={value}
            className={`shrink-0 flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${group === value ? "bg-brand-50 text-brand-700" : "text-slate-500 hover:bg-slate-50"}`}
            onClick={() => setGroup(value)}
          >
            <span>{label}</span>
            <span className={`flex h-5 items-center justify-center rounded-full px-2 text-xs ${group === value ? "bg-brand-100 text-brand-700" : "bg-slate-100 text-slate-500"}`}>
              {counts[value as keyof typeof counts] || 0}
            </span>
          </button>
        ))}
      </div>
      <input
        className="field mb-4"
        placeholder="Tìm mã, tên khách, số điện thoại, sân hoặc ngày"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {loading ? (
        <LoadingSkeleton lines={8} />
      ) : rows.length ? (
        <div className="overflow-x-auto rounded-card border bg-white">
          <table className="w-full min-w-[1200px] text-left text-sm">
            <thead className="bg-slate-50">
              <tr>
                {[
                  "Mã booking",
                  "Khách hàng",
                  "Sân / lịch",
                  "Tổng tiền",
                  "Đã cọc",
                  "Còn lại",
                  "Thanh toán",
                  "Trạng thái",
                  "Hành động",
                ].map((x) => (
                  <th className="px-4 py-3" key={x}>
                    {x}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((item) => (
                <tr className="border-t" key={item.id}>
                  <td className="px-4 py-3 font-bold text-brand-700">
                    {item.booking_code}
                  </td>
                  <td className="px-4 py-3">
                    {item.customer_name}
                    <small className="block text-slate-500">
                      {item.customer_phone || item.customer_email}
                    </small>
                  </td>
                  <td className="px-4 py-3">
                    {item.field_name}
                    <small className="block">
                      {item.booking_date} ·{" "}
                      {item.selected_slots
                        .map(
                          (slot) =>
                            `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`,
                        )
                        .join(", ")}
                    </small>
                  </td>
                  <td className="px-4 py-3 font-semibold">
                    {money(item.total_amount)}
                  </td>
                  <td className="px-4 py-3">
                    {money(Math.min(item.paid_amount, item.deposit_amount))}
                  </td>
                  <td className="px-4 py-3">{money(item.remaining_amount)}</td>
                  <td className="px-4 py-3">
                    <Badge>{paymentLabel[item.payment_status]}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge>{statusLabel[item.status] || item.status}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      {item.status === "pending_confirmation" && (
                        <>
                          <Button
                            size="sm"
                            loading={busy === item.id}
                            leftIcon={<Check size={15} />}
                            onClick={() => void decide(item, true)}
                          >
                            Xác nhận
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            disabled={busy === item.id}
                            leftIcon={<X size={15} />}
                            onClick={() => void decide(item, false)}
                          >
                            Từ chối
                          </Button>
                        </>
                      )}
                      {item.status === "confirmed" && (
                        <>
                          <Button
                            size="sm"
                            loading={busy === item.id}
                            onClick={() => void transition(item, "start")}
                          >
                            Bắt đầu
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            disabled={busy === item.id}
                            onClick={() => void transition(item, "no_show")}
                          >
                            No-show
                          </Button>
                        </>
                      )}
                      {item.status === "in_progress" && (
                        <>
                          <Link to={`/management/bookings/${item.id}?addService=1`}>
                            <Button size="sm" variant="outline" leftIcon={<Plus size={15} />}>
                              Dịch vụ
                            </Button>
                          </Link>
                          <Button
                            size="sm"
                            loading={busy === item.id}
                            onClick={() => void transition(item, "complete")}
                          >
                            Hoàn tất
                          </Button>
                        </>
                      )}
                      <Link to={`/management/bookings/${item.id}`}>
                        <Button
                          size="sm"
                          variant="outline"
                          leftIcon={<Eye size={15} />}
                        >
                          Chi tiết
                        </Button>
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          title="Không có booking"
          description="Không tìm thấy dữ liệu phù hợp trong nhóm này."
        />
      )}
    </>
  );
}

export function ManagementBookingDetailPage() {
  const { bookingId = "" } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { toast } = useToast();
  const [booking, setBooking] = useState<ApiBooking>();
  const [summary, setSummary] = useState<PaymentSummary>();
  const [refund, setRefund] = useState<RefundRequest>();
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [productOpen, setProductOpen] = useState(searchParams.get("addService") === "1");
  const [products, setProducts] = useState<FacilityProduct[]>([]);
  const [productQuery, setProductQuery] = useState("");
  const [selectedProductId, setSelectedProductId] = useState<number>();
  const [productQuantity, setProductQuantity] = useState(1);
  const [productLoading, setProductLoading] = useState(false);
  const load = () =>
    Promise.all([
      apiRequest<ApiBooking>(`/bookings/${bookingId}`),
      getPaymentSummary(Number(bookingId)),
      getManagedRefunds(),
    ]).then(([b, s, r]) => {
      setBooking(b);
      setSummary(s);
      setRefund(r.items.find((item) => item.booking_id === b.id));
    });
  useEffect(() => {
    load()
      .catch((e) =>
        toast(
          e instanceof Error ? e.message : "Không tải được booking.",
          "error",
        ),
      )
      .finally(() => setLoading(false));
  }, [bookingId]);
  const openProducts = async () => {
    if (!booking) return;
    setProductOpen(true);
    setProductLoading(true);
    try {
      const options = await getBookingProductOptions(booking.id);
      setProducts(options);
      setSelectedProductId(options.find((item) => item.is_available)?.id);
      setProductQuantity(1);
    } catch (error) {
      toast(error instanceof Error ? error.message : "Không tải được dịch vụ khả dụng.", "error");
    } finally {
      setProductLoading(false);
    }
  };
  useEffect(() => {
    if (booking && searchParams.get("addService") === "1") void openProducts();
  }, [booking?.id]);
  const closeProducts = () => {
    setProductOpen(false);
    if (searchParams.has("addService")) {
      const next = new URLSearchParams(searchParams);
      next.delete("addService");
      setSearchParams(next, { replace: true });
    }
  };
  const addProduct = async () => {
    if (!booking || !selectedProductId) return;
    const selected = products.find((item) => item.id === selectedProductId);
    if (!selected?.is_available)
      return toast("Sản phẩm này hiện đã hết hàng.", "error");
    if (selected.track_inventory && productQuantity > selected.available_quantity)
      return toast(`Chỉ còn ${selected.available_quantity} ${selected.unit}.`, "error");
    setBusy(true);
    try {
      const updated = await addManagedBookingProduct(booking.id, selectedProductId, productQuantity);
      setBooking(updated);
      setSummary(await getPaymentSummary(updated.id));
      closeProducts();
      toast("Đã thêm dịch vụ phát sinh. Tiền cọc không thay đổi.", "success");
    } catch (error) {
      toast(error instanceof Error ? error.message : "Không thể thêm dịch vụ.", "error");
    } finally {
      setBusy(false);
    }
  };
  const changeProductQuantity = async (itemId: number | null, quantity: number) => {
    if (!booking || !itemId || quantity < 1) return;
    setBusy(true);
    try {
      const updated = await updateManagedBookingProduct(booking.id, itemId, quantity);
      setBooking(updated);
      setSummary(await getPaymentSummary(updated.id));
    } catch (error) {
      toast(error instanceof Error ? error.message : "Không thể đổi số lượng.", "error");
    } finally {
      setBusy(false);
    }
  };
  const removeProduct = async (itemId: number | null) => {
    if (!booking || !itemId || !window.confirm("Xóa dịch vụ phát sinh này khỏi booking?")) return;
    setBusy(true);
    try {
      const updated = await deleteManagedBookingProduct(booking.id, itemId);
      setBooking(updated);
      setSummary(await getPaymentSummary(updated.id));
      toast("Đã xóa dịch vụ phát sinh.", "success");
    } catch (error) {
      toast(error instanceof Error ? error.message : "Không thể xóa dịch vụ.", "error");
    } finally {
      setBusy(false);
    }
  };
  const decide = async (accept: boolean) => {
    if (!booking) return;
    if (!accept && reason.trim().length < 3)
      return toast("Phải nhập lý do từ chối.", "error");
    setBusy(true);
    try {
      setBooking(
        accept
          ? await confirmManagedBooking(booking.id)
          : await rejectManagedBooking(booking.id, reason.trim()),
      );
      toast(
        accept
          ? "Đã xác nhận booking."
          : "Đã từ chối và tạo yêu cầu hoàn tiền.",
        "success",
      );
      if (!accept) await load();
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không thể xử lý booking.",
        "error",
      );
    } finally {
      setBusy(false);
    }
  };
  const ownerCancel = async () => {
    if (!booking || reason.trim().length < 3)
      return toast("Phải nhập lý do hủy.", "error");
    setBusy(true);
    try {
      setBooking(await cancelManagedBooking(booking.id, reason.trim()));
      toast("Đã hủy booking và tạo yêu cầu hoàn tiền.", "success");
      await load();
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không thể hủy booking.",
        "error",
      );
    } finally {
      setBusy(false);
    }
  };
  if (loading) return <LoadingSkeleton lines={8} />;
  if (!booking)
    return (
      <EmptyState
        title="Không tìm thấy booking"
        description="Booking không tồn tại."
      />
    );
  return (
    <>
      <button
        onClick={() => navigate(-1)}
        className="mb-4 text-sm text-brand-700"
      >
        ← Quay lại
      </button>
      <PageHeader
        title={booking.booking_code}
        description={`${booking.customer_name} · ${booking.customer_email}`}
        actions={
          <>
            <Badge>{statusLabel[booking.status]}</Badge>
            <Badge>{paymentLabel[booking.payment_status]}</Badge>
          </>
        }
      />
      {["pending_confirmation", "confirmed"].includes(booking.status) && (
        <div className="mb-5 rounded-card border border-amber-200 bg-amber-50 p-4">
          <div>
            <b>
              {booking.status === "pending_confirmation"
                ? `Khách đã thanh toán đủ tiền cọc ${money(booking.deposit_amount)}`
                : "Chủ sân có thể chủ động hủy khi không thể phục vụ"}
            </b>
            <p className="text-sm text-amber-800">
              Nếu từ chối/hủy, hệ thống hoàn toàn bộ số tiền khách đã trả và
              khóa thanh toán còn lại.
            </p>
          </div>
          <Input
            className="mt-3"
            label="Lý do từ chối / hủy *"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Nhập ít nhất 3 ký tự"
          />
          <div className="mt-3 flex gap-2">
            {booking.status === "pending_confirmation" && (
              <Button loading={busy} onClick={() => void decide(true)}>
                Xác nhận
              </Button>
            )}
            <Button
              variant="danger"
              disabled={busy}
              onClick={() =>
                void (booking.status === "pending_confirmation"
                  ? decide(false)
                  : ownerCancel())
              }
            >
              {booking.status === "pending_confirmation"
                ? "Từ chối"
                : "Chủ động hủy"}
            </Button>
          </div>
        </div>
      )}
      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-card border bg-white p-5">
          <h2 className="font-bold">Thông tin lịch chơi</h2>
          <p className="mt-4">
            <b>Cơ sở:</b> {booking.location}
          </p>
          <p>
            <b>Sân:</b> {booking.field_name} · {booking.sport_type}
          </p>
          <p>
            <b>Ngày:</b> {booking.booking_date}
          </p>
          <p>
            <b>Khung giờ:</b> {booking.selected_slots.length} khung ·{" "}
            {booking.duration_minutes} phút
          </p>
          <div className="mt-2 space-y-1 text-sm text-slate-600">
            {booking.selected_slots.map((slot) => (
              <div key={slot.time_slot_id} className="flex justify-between">
                <span>
                  {slot.start_time.slice(0, 5)}–{slot.end_time.slice(0, 5)}
                </span>
                <b>{money(slot.price)}</b>
              </div>
            ))}
          </div>
          <div className="mt-5 border-t pt-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-bold">Sản phẩm & dịch vụ đi kèm</h3>
              {booking.status === "in_progress" && (
                <Button size="sm" leftIcon={<Plus size={14} />} onClick={() => void openProducts()}>
                  Thêm dịch vụ
                </Button>
              )}
            </div>
            {booking.product_items.length ? (
              <div className="mt-2 space-y-2 text-sm">
                {booking.product_items.map((item) => (
                  <div key={item.item_id || item.product_id} className="flex items-center justify-between gap-3 rounded-lg border p-2">
                    <span>
                      {item.name} · {item.quantity} {item.unit} × {money(item.unit_price)}
                      {item.source === "OWNER_DURING_USAGE" && (
                        <small className="block text-brand-700">Phát sinh tại sân · {item.added_by_name || "OWNER"}{item.added_at ? ` · ${new Date(item.added_at).toLocaleString("vi-VN")}` : ""}</small>
                      )}
                    </span>
                    <div className="flex items-center gap-2">
                      <b>{money(item.subtotal)}</b>
                      {booking.status === "in_progress" && item.source === "OWNER_DURING_USAGE" && (
                        <>
                          <Button size="sm" variant="outline" aria-label="Giảm số lượng" disabled={busy || item.quantity <= 1} onClick={() => void changeProductQuantity(item.item_id, item.quantity - 1)}><Minus size={13} /></Button>
                          <Button size="sm" variant="outline" aria-label="Tăng số lượng" disabled={busy} onClick={() => void changeProductQuantity(item.item_id, item.quantity + 1)}><Plus size={13} /></Button>
                          <Button size="sm" variant="danger" aria-label="Xóa dịch vụ" disabled={busy} onClick={() => void removeProduct(item.item_id)}><Trash2 size={13} /></Button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-500">Không có dịch vụ thêm.</p>
            )}
          </div>
        </section>
        <section className="rounded-card border bg-white p-5">
          <h2 className="font-bold">Tóm tắt thanh toán</h2>
          <div className="mt-4 space-y-2">
            <Row label="Tiền sân" value={booking.court_amount} />
            <Row label="Dịch vụ thêm" value={booking.service_amount} />
            <Row label="TỔNG CỘNG" value={booking.total_amount} />
            <Row
              label="Đã cọc"
              value={Math.min(booking.paid_amount, booking.deposit_amount)}
            />
            <Row label="Còn lại" value={booking.remaining_amount} />
            {booking.refund_status === "refund_pending" && (
              <Row
                label="Chờ hoàn cọc"
                value={
                  booking.refundable_deposit_amount || booking.deposit_amount
                }
              />
            )}
          </div>
          <Button
            className="mt-5 print:hidden"
            variant="outline"
            leftIcon={<Printer size={16} />}
            onClick={() => window.print()}
          >
            In phiếu
          </Button>
        </section>
      </div>
      {refund && (
        <RefundStatusPanel
          initial={refund}
          mode="owner"
          onChanged={setRefund}
        />
      )}
      <section className="mt-5 rounded-card border bg-white p-5">
        <h2 className="font-bold">Giao dịch</h2>
        {summary?.transactions.map((tx) => (
          <div
            key={tx.id}
            className="mt-3 flex justify-between border-t pt-3 text-sm"
          >
            <span>
              {tx.transaction_code} ·{" "}
              {tx.payment_type === "deposit"
                ? "Đặt cọc"
                : tx.payment_type === "refund"
                  ? "Hoàn tiền"
                  : "Thanh toán còn lại"}
            </span>
            <b>
              {money(tx.amount)} ·{" "}
              {paymentLabel[tx.refund_status] ||
                paymentLabel[tx.status] ||
                "Đang xử lý"}
            </b>
          </div>
        ))}
      </section>
      <Modal open={productOpen} onClose={closeProducts} title="Thêm dịch vụ phát sinh">
        <div className="space-y-4">
          <p className="text-sm text-slate-600">Giá được chốt tại thời điểm thêm. Khoản cọc ban đầu không thay đổi; phần phát sinh được cộng vào số tiền còn lại.</p>
          <Input label="Tìm dịch vụ / sản phẩm" value={productQuery} onChange={(event) => setProductQuery(event.target.value)} />
          {productLoading ? <LoadingSkeleton lines={5} /> : <div className="max-h-80 space-y-2 overflow-y-auto">
            {products.filter((item) => item.name.toLocaleLowerCase("vi").includes(productQuery.toLocaleLowerCase("vi"))).map((item) => (
              <button key={item.id} type="button" disabled={!item.is_available} onClick={() => { setSelectedProductId(item.id); setProductQuantity(1); }} className={`w-full rounded-xl border p-3 text-left transition ${!item.is_available ? "cursor-not-allowed bg-slate-50 opacity-60" : selectedProductId === item.id ? "border-brand-500 bg-brand-50" : "border-slate-200 hover:border-brand-300"}`}>
                <span className="grid gap-1 sm:grid-cols-[1fr_90px_120px] sm:items-center">
                  <span><b className="block">{item.name}</b><small className="text-slate-500">{item.product_type} · {item.unit}</small></span>
                  <b className="text-brand-700">{money(item.price)}</b>
                  <small className={item.is_available ? "font-semibold text-emerald-700" : "font-semibold text-red-600"}>{item.track_inventory ? item.is_available ? `Còn ${item.available_quantity}` : "Hết hàng" : "Không giới hạn"}</small>
                </span>
              </button>
            ))}
            {!products.length && <div className="rounded-xl border border-dashed p-5 text-center"><p className="text-sm text-slate-600">Cơ sở chưa cấu hình dịch vụ phù hợp với môn thể thao này.</p><Button className="mt-3" variant="outline" onClick={() => navigate("/management/products")}>Đi tới quản lý dịch vụ</Button></div>}
          </div>}
          {selectedProductId && (() => {
            const selected = products.find((item) => item.id === selectedProductId);
            if (!selected) return null;
            return <div className="rounded-xl bg-slate-50 p-4"><div className="mb-3 grid grid-cols-2 gap-2 text-sm"><span>Đơn giá</span><b className="text-right">{money(selected.price)} / {selected.unit}</b><span>Khả dụng</span><b className="text-right">{selected.track_inventory ? selected.available_quantity : "Không giới hạn"}</b><span>Tạm tính</span><b className="text-right text-brand-700">{money(selected.price * productQuantity)}</b></div><Input type="number" min="1" max={selected.track_inventory ? selected.available_quantity : 1000} label="Số lượng" value={productQuantity} onChange={(event) => setProductQuantity(Math.min(selected.track_inventory ? selected.available_quantity : 1000, Math.max(1, Number(event.target.value))))} /></div>;
          })()}
          <Button className="w-full" loading={busy} disabled={!selectedProductId || productLoading} onClick={() => void addProduct()}>Thêm vào hóa đơn</Button>
        </div>
      </Modal>
    </>
  );
}
function Row({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between border-b pb-2">
      <span>{label}</span>
      <b>{money(value)}</b>
    </div>
  );
}
