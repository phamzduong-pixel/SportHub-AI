import {
  CalendarDays,
  Clock3,
  CreditCard,
  Heart,
  MapPin,
  Search,
  Star,
} from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
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
import {
  createBankIntent,
  getMyBooking,
  getMyBookings,
  getMyPayments,
  getPayment,
  getPaymentSummary,
  type ApiBooking,
  type ApiPayment,
} from "@/services/customerApi";
import {
  getFavorites,
  setFavorite,
  type FavoriteField,
} from "@/services/favoriteService";
import { getSportImage } from "@/utils/sportImage";
import { TransactionReceiptModal } from "@/components/payments/TransactionReceiptModal";

const money = (value: number) => `${value.toLocaleString("vi-VN")}đ`;
const bookingLabel = (status: ApiBooking["status"]) =>
  ({
    pending_payment: "Chờ thanh toán",
    pending_confirmation: "Đã cọc – Chờ xác nhận",
    confirmed: "Đã xác nhận",
    in_progress: "Đang sử dụng",
    completed: "Đã hoàn thành",
    no_show: "Khách vắng mặt",
    cancelled: "Đã hủy",
    cancelled_by_customer: "Khách đã hủy",
    cancelled_by_owner: "Chủ sân hủy",
    expired: "Hết hạn thanh toán",
    rejected: "Chủ sân từ chối",
    failed: "Thất bại",
  })[status];
const paymentLabel = (status: ApiBooking["payment_status"]) =>
  ({
    paid: "Đã thanh toán",
    partial: "Đã đặt cọc",
    pending: "Đang xử lý",
    unpaid: "Chưa thanh toán",
    refund_pending: "Chờ hoàn tiền",
    refund_overdue: "Hoàn tiền quá hạn",
    refunded: "Đã hoàn tiền",
    disputed: "Đang khiếu nại",
  })[status];
const transactionStatusLabel = (payment: ApiPayment) =>
  payment.refund_status === "refunded" || payment.status === "refunded"
    ? "Đã hoàn tiền"
    : payment.refund_status === "refund_pending"
      ? "Chờ hoàn tiền"
      : payment.status === "paid"
        ? "Đã thanh toán"
        : payment.status === "pending"
          ? "Đang xử lý"
          : payment.status === "cancelled"
            ? "Đã hủy"
            : "Không thành công";
type Filter =
  | "upcoming"
  | "payment"
  | "confirmation"
  | "in_progress"
  | "completed"
  | "closed";
const inFilter = (item: ApiBooking, filter: Filter) =>
  (
    ({
      upcoming: ["confirmed"],
      payment: ["pending_payment"],
      confirmation: ["pending_confirmation"],
      in_progress: ["in_progress"],
      completed: ["completed"],
      closed: [
        "cancelled",
        "cancelled_by_customer",
        "cancelled_by_owner",
        "expired",
        "rejected",
        "failed",
        "no_show",
      ],
    })[filter] as string[]
  ).includes(item.status);

export function CustomerBookingsPage() {
  const [items, setItems] = useState<ApiBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("upcoming");
  const [query, setQuery] = useState("");
  const { toast } = useToast();
  const load = () => {
    setLoading(true);
    getMyBookings()
      .then((result) => setItems(result.items))
      .catch((error) =>
        toast(
          error instanceof Error ? error.message : "Không tải được lịch đặt.",
          "error",
        ),
      )
      .finally(() => setLoading(false));
  };
  useEffect(load, []);
  const shown = useMemo(
    () =>
      items.filter(
        (item) =>
          inFilter(item, filter) &&
          `${item.field_name} ${item.booking_code}`
            .toLowerCase()
            .includes(query.toLowerCase()),
      ),
    [items, filter, query],
  );
  const tabs: [Filter, string][] = [
    ["upcoming", "Sắp tới"],
    ["payment", "Chờ thanh toán"],
    ["confirmation", "Chờ xác nhận"],
    ["in_progress", "Đang sử dụng"],
    ["completed", "Đã hoàn thành"],
    ["closed", "Đã hủy / hết hạn"],
  ];
  return (
    <>
      <PageHeader
        title="Đặt sân của tôi"
        description="Theo dõi toàn bộ vòng đời booking của tài khoản hiện tại."
        action={
          <Link to="/venues">
            <Button>+ Đặt sân mới</Button>
          </Link>
        }
      />
      <div className="rounded-card border bg-white">
        <div className="flex flex-col gap-3 border-b p-4">
          <div className="flex gap-1 overflow-x-auto pb-1">
            {tabs.map(([value, label]) => (
              <button
                key={value}
                onClick={() => setFilter(value)}
                className={`shrink-0 rounded-lg px-3 py-2 text-sm font-semibold ${filter === value ? "bg-brand-50 text-brand-700" : "text-slate-500"}`}
              >
                {label}
                <span className="ml-1 text-xs">
                  ({items.filter((item) => inFilter(item, value)).length})
                </span>
              </button>
            ))}
          </div>
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            leftIcon={<Search size={16} />}
            placeholder="Tên sân, cơ sở hoặc mã booking"
          />
        </div>
        <div className="space-y-3 p-4">
          {loading ? (
            <LoadingSkeleton lines={6} />
          ) : shown.length ? (
            shown.map((item) => <BookingCard key={item.id} item={item} />)
          ) : (
            <EmptyState
              title="Không có lịch đặt"
              description="Không tìm thấy booking trong nhóm này."
            />
          )}
        </div>
      </div>
    </>
  );
}
function BookingCard({ item }: { item: ApiBooking }) {
  return (
    <article className="rounded-xl border border-slate-200 p-4">
      <div className="flex flex-col justify-between gap-4 sm:flex-row">
        <div>
          <p className="text-xs font-semibold text-slate-400">
            {item.booking_code}
          </p>
          <h2 className="mt-1 font-bold">{item.field_name}</h2>
          <p className="text-sm text-brand-700">
            {item.facility_name} · {item.sport_type}
          </p>
          <div className="mt-3 flex flex-wrap gap-4 text-sm text-slate-600">
            <span>
              <CalendarDays size={15} className="mr-1 inline" />
              {new Date(`${item.booking_date}T00:00:00`).toLocaleDateString(
                "vi-VN",
              )}
            </span>
            <span>
              <Clock3 size={15} className="mr-1 inline" />
              {item.selected_slots
                .map(
                  (slot) =>
                    `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`,
                )
                .join(", ")}
            </span>
            <span>
              Tổng <b>{money(item.total_amount)}</b>
            </span>
            <span>
              Đã cọc{" "}
              <b>{money(Math.min(item.paid_amount, item.deposit_amount))}</b>
            </span>
            <span>
              Còn lại <b>{money(item.remaining_amount)}</b>
            </span>
          </div>
          {item.product_items.length > 0 && (
            <p className="mt-2 text-sm text-slate-500">
              Dịch vụ: {item.product_items.map((product) => `${product.name} × ${product.quantity}`).join(", ")}
              {" · "}<b>{money(item.service_amount)}</b>
            </p>
          )}
        </div>
        <div className="flex flex-col items-start gap-2 sm:items-end">
          <div className="flex flex-wrap gap-2">
            <Badge
              variant={
                ["confirmed", "in_progress", "completed"].includes(item.status)
                  ? "success"
                  : ["cancelled", "failed", "expired", "no_show"].includes(
                        item.status,
                      )
                    ? "danger"
                    : "warning"
              }
            >
              {bookingLabel(item.status)}
            </Badge>
            <Badge
              variant={item.payment_status === "paid" ? "success" : "warning"}
            >
              {paymentLabel(item.payment_status)}
            </Badge>
          </div>
          <div className="mt-auto flex flex-wrap gap-2">
            {item.status === "completed" && !item.reviewed && (
              <Link to={`/customer/reviews?booking=${item.id}`}>
                <Button size="sm" leftIcon={<Star size={15} />}>
                  Đánh giá sân
                </Button>
              </Link>
            )}
            <Link to={`/customer/bookings/${item.id}`}>
              <Button size="sm" variant="outline">
                Xem chi tiết
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </article>
  );
}

export function BookingDetailPage() {
  const { bookingId = "" } = useParams();
  const [item, setItem] = useState<ApiBooking>();
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();
  useEffect(() => {
    getMyBooking(bookingId)
      .then(setItem)
      .catch((error) =>
        toast(
          error instanceof Error ? error.message : "Không tải được booking.",
          "error",
        ),
      )
      .finally(() => setLoading(false));
  }, [bookingId]);
  const pay = async () => {
    if (!item) return;
    setPaying(true);
    try {
      const summary = await getPaymentSummary(item.id);
      const pending = summary.transactions.find(
        (payment) => payment.status === "pending",
      );
      const payment =
        pending ||
        (await createBankIntent(
          item.id,
          item.paid_amount >= item.deposit_amount ? "remaining" : "deposit",
        ));
      navigate(`/booking/payment/${payment.id}`, {
        state: { booking: item, payment },
      });
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không thể mở thanh toán.",
        "error",
      );
    } finally {
      setPaying(false);
    }
  };
  if (loading) return <LoadingSkeleton lines={8} />;
  if (!item)
    return (
      <EmptyState
        title="Không tìm thấy booking"
        description="Booking không tồn tại hoặc không thuộc tài khoản của bạn."
      />
    );
  const canPay =
    item.status === "pending_payment" ||
    (item.status === "confirmed" && item.remaining_amount > 0);
  return (
    <>
      <button
        onClick={() => navigate(-1)}
        className="mb-4 text-sm font-semibold text-brand-700"
      >
        ← Quay lại
      </button>
      <PageHeader
        title={`Chi tiết ${item.booking_code}`}
        description={`Đặt lúc ${new Date(item.created_at).toLocaleString("vi-VN")}`}
      />
      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-card border bg-white p-5">
          <h2 className="text-xl font-bold">{item.field_name}</h2>
          <p className="mt-1 text-brand-700">
            {item.sport_type} · {item.time_slot_name}
          </p>
          <div className="mt-5 space-y-3 text-sm">
            <p>
              <MapPin size={16} className="mr-2 inline text-brand-600" />
              {item.location}
            </p>
            <p>
              <CalendarDays size={16} className="mr-2 inline text-brand-600" />
              {item.booking_date}
            </p>
            <p>
              <Clock3 size={16} className="mr-2 inline text-brand-600" />
              {item.selected_slots
                .map(
                  (slot) =>
                    `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`,
                )
                .join(", ")}
            </p>
          </div>
        </section>
        <section className="rounded-card border bg-white p-5">
          <h2 className="font-bold">Thanh toán và trạng thái</h2>
          <p className="mt-5 text-3xl font-extrabold text-brand-700">
            {money(item.total_amount)}
          </p>
          <div className="mt-4 flex gap-2">
            <Badge>{bookingLabel(item.status)}</Badge>
            <Badge>{paymentLabel(item.payment_status)}</Badge>
          </div>
          <div className="mt-4 space-y-1 text-sm">
            <p>
              Đã thanh toán: <b>{money(item.paid_amount)}</b>
            </p>
            <p>
              Còn lại: <b>{money(item.remaining_amount)}</b>
            </p>
          </div>
          {canPay && (
            <Button
              className="mt-5 w-full"
              loading={paying}
              onClick={() => void pay()}
            >
              {item.status === "pending_payment"
                ? "Thanh toán tiền cọc"
                : `Thanh toán còn lại ${money(item.remaining_amount)}`}
            </Button>
          )}
          <p className="mt-5 text-sm text-slate-500">
            Người đặt: {item.customer_name}
            <br />
            {item.customer_email}
          </p>
        </section>
      </div>
    </>
  );
}

export function CustomerFavoritesPage() {
  const [items, setItems] = useState<FavoriteField[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();
  const load = () => {
    setLoading(true);
    getFavorites()
      .then(setItems)
      .catch((error) =>
        toast(
          error instanceof Error
            ? error.message
            : "Không tải được sân yêu thích.",
          "error",
        ),
      )
      .finally(() => setLoading(false));
  };
  useEffect(load, []);
  const remove = async (fieldId: number) => {
    try {
      await setFavorite(fieldId, false);
      setItems((current) =>
        current.filter((item) => item.field_id !== fieldId),
      );
      toast("Đã bỏ sân khỏi yêu thích.", "success");
    } catch {
      toast("Không thể bỏ sân yêu thích.", "error");
    }
  };
  return (
    <>
      <PageHeader
        title="Sân yêu thích"
        description="Các sân được lưu riêng cho tài khoản đang đăng nhập."
      />
      {loading ? (
        <LoadingSkeleton lines={8} />
      ) : items.length ? (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((item) => (
            <article
              key={item.field_id}
              className="overflow-hidden rounded-card border bg-white shadow-sm"
            >
              <div className="relative h-40 bg-slate-100">
                <img
                  src={item.image_url || getSportImage(item.sport_type)}
                  alt={item.field_name}
                  className="h-full w-full object-cover"
                />
                <button
                  onClick={() => void remove(item.field_id)}
                  className="absolute right-3 top-3 rounded-full bg-white p-2 text-red-500 shadow"
                  aria-label="Bỏ yêu thích"
                >
                  <Heart size={18} className="fill-current" />
                </button>
                <Badge
                  className="absolute left-3 top-3"
                  variant={item.has_availability ? "success" : "neutral"}
                >
                  {item.has_availability
                    ? `Còn lịch${item.next_slot ? ` · ${item.next_slot}` : ""}`
                    : "Chưa có lịch trống"}
                </Badge>
              </div>
              <div className="p-5">
                <div className="flex justify-between gap-2">
                  <span className="text-xs font-bold uppercase text-brand-700">
                    {item.sport_type}
                  </span>
                  <span className="text-sm font-semibold">
                    <Star
                      size={14}
                      className="mr-1 inline fill-amber-400 text-amber-400"
                    />
                    {item.rating.toFixed(1)}{" "}
                    <small className="text-slate-400">
                      ({item.review_count})
                    </small>
                  </span>
                </div>
                <h2 className="mt-2 font-bold">{item.field_name}</h2>
                <p className="mt-2 flex gap-1.5 text-sm text-slate-500">
                  <MapPin size={15} className="mt-0.5 shrink-0" />
                  {item.location}
                </p>
                <p className="mt-4 text-lg font-bold text-brand-700">
                  {money(item.price)}
                  <small className="font-normal text-slate-500"> / giờ</small>
                </p>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <Link to={`/courts/${item.field_id}`}>
                    <Button variant="outline" className="w-full">
                      Xem chi tiết
                    </Button>
                  </Link>
                  <Link to={`/booking/${item.field_id}`}>
                    <Button
                      className="w-full"
                      disabled={!item.has_availability}
                    >
                      Đặt sân
                    </Button>
                  </Link>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Heart />}
          title="Chưa có sân yêu thích"
          description="Nhấn biểu tượng trái tim trên sân để lưu vào đây."
          action={
            <Link to="/venues">
              <Button>Khám phá sân</Button>
            </Link>
          }
        />
      )}
    </>
  );
}
export function CustomerTransactionsPage() {
  const [items, setItems] = useState<ApiPayment[]>([]);
  const [selected, setSelected] = useState<ApiPayment>();
  const [booking, setBooking] = useState<ApiBooking>();
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const { toast } = useToast();
  useEffect(() => {
    getMyPayments()
      .then((result) => setItems(result.items))
      .catch((error) =>
        toast(
          error instanceof Error ? error.message : "Không tải được giao dịch.",
          "error",
        ),
      )
      .finally(() => setLoading(false));
  }, []);
  const open = async (payment: ApiPayment) => {
    setSelected(payment);
    setBooking(undefined);
    setDetailError("");
    setDetailLoading(true);
    try {
      const [paymentDetail, bookingDetail] = await Promise.all([
        getPayment(payment.id),
        getMyBooking(payment.booking_id),
      ]);
      if (paymentDetail.booking_id !== bookingDetail.id)
        throw new Error("Giao dịch không khớp với booking.");
      setSelected(paymentDetail);
      setBooking(bookingDetail);
    } catch (error) {
      setDetailError(
        error instanceof Error
          ? error.message
          : "Không tải được chi tiết hóa đơn.",
      );
    } finally {
      setDetailLoading(false);
    }
  };
  const close = () => {
    setSelected(undefined);
    setBooking(undefined);
    setDetailError("");
  };
  return (
    <>
      <PageHeader
        title="Giao dịch"
        description="Lịch sử thanh toán và hoàn tiền của tài khoản."
      />
      {loading ? (
        <LoadingSkeleton lines={7} />
      ) : items.length ? (
        <div className="overflow-x-auto rounded-card border bg-white">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-slate-50">
              <tr>
                {[
                  "Mã giao dịch",
                  "Booking",
                  "Loại",
                  "Số tiền",
                  "Trạng thái",
                  "Thời gian",
                ].map((label) => (
                  <th key={label} className="px-4 py-3">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((payment) => (
                <tr
                  key={payment.id}
                  tabIndex={0}
                  role="button"
                  aria-label={`Xem hóa đơn ${payment.transaction_code}`}
                  onClick={() => void open(payment)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      void open(payment);
                    }
                  }}
                  className="cursor-pointer border-t transition-colors hover:bg-slate-50 focus:bg-brand-50 focus:outline-none"
                >
                  <td className="px-4 py-3 font-mono">
                    {payment.transaction_code}
                  </td>
                  <td className="px-4 py-3">{payment.booking_code}</td>
                  <td className="px-4 py-3">
                    {payment.payment_type === "deposit"
                      ? "Đặt cọc"
                      : payment.payment_type === "refund"
                        ? "Hoàn tiền"
                        : "Thanh toán còn lại"}
                  </td>
                  <td className="px-4 py-3 font-semibold">
                    {money(payment.amount)}
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant={
                        payment.status === "paid"
                          ? "success"
                          : payment.status === "pending"
                            ? "warning"
                            : "danger"
                      }
                    >
                      {transactionStatusLabel(payment)}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    {payment.refunded_at || payment.paid_at
                      ? new Date(
                          payment.refunded_at ||
                            payment.paid_at ||
                            payment.created_at,
                        ).toLocaleString("vi-VN")
                      : "Đang chờ"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          icon={<CreditCard />}
          title="Chưa có giao dịch"
          description="Giao dịch sẽ xuất hiện sau khi bạn bắt đầu thanh toán."
        />
      )}
      <TransactionReceiptModal
        payment={selected}
        booking={booking}
        loading={detailLoading}
        error={detailError}
        onClose={close}
      />
    </>
  );
}
export function CustomerSettingsPage() {
  return (
    <>
      <PageHeader
        title="Cài đặt"
        description="Thiết lập tài khoản và bảo mật."
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-card border bg-white p-5 text-sm text-slate-600">
          Bạn có thể cập nhật thông tin tại trang Hồ sơ cá nhân.
        </div>
        <div className="rounded-card border border-brand-200 bg-brand-50 p-5">
          <h2 className="font-bold text-slate-900">
            Trở thành đối tác SportHub
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Đăng ký hồ sơ chủ sân, theo dõi xét duyệt và bổ sung thông tin tại
            đây.
          </p>
          <Link to="/owner-application">
            <Button className="mt-4">Gửi hồ sơ đăng ký</Button>
          </Link>
        </div>
      </div>
    </>
  );
}
