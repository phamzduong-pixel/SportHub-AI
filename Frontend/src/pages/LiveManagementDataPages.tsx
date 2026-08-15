import {
  Bot,
  Building2,
  CalendarDays,
  Phone,
  PackageOpen,
  Plus,
  RefreshCw,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
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
import { useAuth } from "@/contexts/AuthContext";
import { apiRequest } from "@/services/apiClient";
import {
  confirmManagedBooking,
  rejectManagedBooking,
  type ApiBooking,
} from "@/services/customerApi";
import { FieldServicesModal } from "@/components/management/FieldServicesModal";

interface Field {
  id: number;
  facility_id: number | null;
  name: string;
  sport_type: string;
  description: string | null;
  location: string;
  capacity: number;
  base_price: number;
  status: string;
  image_url: string | null;
  amenities: string[];
  rating: number;
  review_count: number;
  distance_km: number | null;
  deposit_type: string;
  deposit_value: number;
  cancellation_policy: string;
  cancellation_refund_percent: number | null;
}
interface FacilityOption {
  id: number;
  name: string;
  location: string;
  contact_phone: string | null;
}
interface Slot {
  id: number;
  field_id: number;
  name: string;
  start_time: string;
  end_time: string;
  price: number;
  is_active: boolean;
}
interface Summary {
  total_fields: number;
  active_fields: number;
  total_bookings: number;
  pending_bookings: number;
  confirmed_bookings: number;
  paid_revenue: number;
  date_from: string;
  date_to: string;
}
interface Revenue {
  total: number;
  items: Array<{ period: string; revenue: number }>;
}
interface FieldPerformance {
  items: Array<{
    field_id: number;
    field_name: string;
    sport_type: string;
    booking_count: number;
    confirmed_count: number;
    completed_count: number;
    paid_revenue: number;
    utilization_rate: number;
  }>;
}
const money = (value: number) => `${value.toLocaleString("vi-VN")}đ`;
const today = () => {
  const value = new Date();
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
};

function useFields() {
  const [items, setItems] = useState<Field[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();
  const load = () => {
    setLoading(true);
    apiRequest<{ items: Field[] }>("/fields?page_size=100")
      .then((result) => setItems(result.items))
      .catch((error) =>
        toast(
          error instanceof Error ? error.message : "Không tải được sân.",
          "error",
        ),
      )
      .finally(() => setLoading(false));
  };
  useEffect(load, []);
  return { items, loading, load, toast };
}

export function ManagementVenuesPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [items, setItems] = useState<FacilityOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<FacilityOption>();
  const [hotline, setHotline] = useState("");
  const [saving, setSaving] = useState(false);

  const load = () => {
    if (user?.role !== "OWNER") {
      setLoading(false);
      return;
    }
    setLoading(true);
    apiRequest<FacilityOption[]>("/facilities")
      .then(setItems)
      .catch((error) =>
        toast(
          error instanceof Error ? error.message : "Không tải được cơ sở.",
          "error",
        ),
      )
      .finally(() => setLoading(false));
  };
  useEffect(load, [user?.role]);

  const openHotline = (facility: FacilityOption) => {
    setEditing(facility);
    setHotline(facility.contact_phone || "");
  };
  const saveHotline = async (event: FormEvent) => {
    event.preventDefault();
    if (!editing) return;
    const value = hotline.trim();
    const digitCount = value.replace(/\D/g, "").length;
    if (
      value &&
      (!/^\+?[0-9\s().-]+$/.test(value) || digitCount < 9 || digitCount > 15)
    ) {
      toast(
        "Hotline phải có từ 9 đến 15 chữ số và đúng định dạng số điện thoại.",
        "error",
      );
      return;
    }
    setSaving(true);
    try {
      const updated = await apiRequest<FacilityOption>(
        `/facilities/${editing.id}/hotline`,
        {
          method: "PATCH",
          body: JSON.stringify({ contact_phone: value || null }),
        },
      );
      setItems((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setEditing(undefined);
      toast(
        value ? "Đã cập nhật hotline cơ sở." : "Đã xóa hotline cơ sở.",
        "success",
      );
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không cập nhật được hotline.",
        "error",
      );
    } finally {
      setSaving(false);
    }
  };

  if (user?.role !== "OWNER")
    return (
      <EmptyState
        icon={<Building2 />}
        title="Quản lý cơ sở dành cho OWNER"
        description="Người quản lý vẫn có thể thao tác các sân theo quyền được cấp."
      />
    );
  return (
    <>
      <PageHeader
        title="Cơ sở"
        description="Quản lý thông tin liên hệ để khách hàng có thể gọi trực tiếp khi cần hỗ trợ."
      />
      {loading ? (
        <LoadingSkeleton lines={6} />
      ) : items.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((facility) => (
            <article
              key={facility.id}
              className="rounded-card border bg-white p-5 shadow-sm"
            >
              <div className="flex items-start gap-3">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-700">
                  <Building2 size={20} />
                </span>
                <div className="min-w-0">
                  <h2 className="font-bold text-slate-900">{facility.name}</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {facility.location}
                  </p>
                </div>
              </div>
              {facility.contact_phone ? (
                <div className="mt-5 flex items-center gap-2 rounded-xl bg-slate-50 p-3 text-sm">
                  <Phone size={17} className="text-brand-700" />
                  <span className="text-slate-500">Hotline</span>
                  <b className="ml-auto">{facility.contact_phone}</b>
                </div>
              ) : (
                <p className="mt-5 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">
                  Chưa cấu hình hotline cho cơ sở này.
                </p>
              )}
              <Button
                className="mt-4 w-full"
                size="sm"
                variant="outline"
                onClick={() => openHotline(facility)}
              >
                {facility.contact_phone ? "Cập nhật hotline" : "Thêm hotline"}
              </Button>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Building2 />}
          title="Chưa có cơ sở"
          description="Tạo cơ sở trước khi cấu hình hotline liên hệ."
        />
      )}
      <Modal
        open={Boolean(editing)}
        onClose={() => setEditing(undefined)}
        title={`Hotline · ${editing?.name || ""}`}
      >
        <form onSubmit={saveHotline} className="space-y-4">
          <Input
            type="tel"
            inputMode="tel"
            maxLength={20}
            label="Số điện thoại liên hệ"
            value={hotline}
            onChange={(event) => setHotline(event.target.value)}
            placeholder="Ví dụ: 0901 234 567"
            leftIcon={<Phone size={16} />}
          />
          <p className="text-xs leading-5 text-slate-500">
            Để trống và lưu nếu bạn muốn ẩn số liên hệ khỏi trang khách hàng.
          </p>
          <Button type="submit" loading={saving} className="w-full">
            Lưu hotline
          </Button>
        </form>
      </Modal>
    </>
  );
}
export function ManagementCourtsPage() {
  return <LiveFieldsPage title="Danh sách sân" />;
}
function LiveFieldsPage({ title }: { title: string }) {
  const { user } = useAuth();
  const { items, loading, load, toast } = useFields();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [facilities, setFacilities] = useState<FacilityOption[]>([]);
  const [serviceField, setServiceField] = useState<Field>();
  const [form, setForm] = useState({
    facility_id: null as number | null,
    name: "",
    sport_type: "",
    description: "",
    location: "",
    capacity: 10,
    base_price: 0,
    status: "available",
    image_url: "",
    amenities: "",
    deposit_type: "percentage",
    deposit_value: 30,
    cancellation_policy: "manual_review",
    cancellation_refund_percent: null as number | null,
  });
  useEffect(() => {
    if (user?.role === "OWNER")
      apiRequest<FacilityOption[]>("/facilities")
        .then((result) => {
          setFacilities(result);
          if (result[0])
            setForm((current) => ({
              ...current,
              facility_id: result[0].id,
              location: result[0].location,
            }));
        })
        .catch(() => undefined);
  }, [user?.role]);
  const canCreate = user?.role === "OWNER";
  const canUpdate = user?.role === "OWNER";
  const create = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await apiRequest("/fields", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          description: form.description || null,
          image_url: form.image_url || null,
          amenities: form.amenities
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean),
          rating: 0,
          review_count: 0,
          distance_km: null,
        }),
      });
      setOpen(false);
      toast("Đã tạo sân trong database.", "success");
      load();
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không tạo được sân.",
        "error",
      );
    } finally {
      setSaving(false);
    }
  };
  const setStatus = async (field: Field, status: string) => {
    try {
      await apiRequest(`/fields/${field.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      toast("Đã cập nhật trạng thái sân.", "success");
      load();
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không cập nhật được sân.",
        "error",
      );
    }
  };
  return (
    <>
      <PageHeader
        title={title}
        description="Dữ liệu thật, đã giới hạn theo OWNER của tài khoản hiện tại."
        actions={
          canCreate ? (
            <Button leftIcon={<Plus size={16} />} onClick={() => setOpen(true)}>
              Thêm sân
            </Button>
          ) : undefined
        }
      />
      {loading ? (
        <LoadingSkeleton lines={8} />
      ) : items.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((field) => (
            <article
              key={field.id}
              className="rounded-card border bg-white p-5"
            >
              <div className="flex justify-between gap-3">
                <div>
                  <span className="text-xs font-bold uppercase text-brand-700">
                    {field.sport_type}
                  </span>
                  <h2 className="mt-1 text-lg font-bold">{field.name}</h2>
                </div>
                <Badge
                  variant={
                    field.status === "available"
                      ? "success"
                      : field.status === "maintenance"
                        ? "warning"
                        : "neutral"
                  }
                >
                  {field.status}
                </Badge>
              </div>
              <p className="mt-2 text-sm text-slate-500">{field.location}</p>
              <p className="mt-4 text-xl font-bold text-brand-700">
                {money(field.base_price)}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Cọc{" "}
                {field.deposit_type === "percentage"
                  ? `${field.deposit_value}%`
                  : money(field.deposit_value)}
              </p>
              {canUpdate && (
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    leftIcon={<PackageOpen size={15} />}
                    disabled={!field.facility_id}
                    onClick={() => setServiceField(field)}
                  >
                    Dịch vụ
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={field.status === "available"}
                    onClick={() => void setStatus(field, "available")}
                  >
                    Mở
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={field.status === "maintenance"}
                    onClick={() => void setStatus(field, "maintenance")}
                  >
                    Bảo trì
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    disabled={field.status === "inactive"}
                    onClick={() => void setStatus(field, "inactive")}
                  >
                    Ngưng
                  </Button>
                </div>
              )}
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title="Chưa có sân"
          description="OWNER có thể tạo sân đầu tiên tại đây."
        />
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Thêm sân">
        <form onSubmit={create} className="grid gap-4 sm:grid-cols-2">
          {facilities.length > 0 && (
            <label className="sm:col-span-2 text-sm font-medium">
              Cơ sở
              <select
                className="field mt-2"
                value={form.facility_id || ""}
                onChange={(event) => {
                  const facility = facilities.find(
                    (item) => item.id === Number(event.target.value),
                  );
                  setForm({
                    ...form,
                    facility_id: facility?.id || null,
                    location: facility?.location || form.location,
                  });
                }}
              >
                {facilities.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {item.location}
                  </option>
                ))}
              </select>
            </label>
          )}
          <Input
            required
            label="Tên sân"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
          <Input
            required
            label="Môn thể thao"
            value={form.sport_type}
            onChange={(event) =>
              setForm({ ...form, sport_type: event.target.value })
            }
          />
          <Input
            required
            label="Địa chỉ"
            value={form.location}
            onChange={(event) =>
              setForm({ ...form, location: event.target.value })
            }
          />
          <Input
            required
            type="number"
            min={1}
            label="Sức chứa"
            value={form.capacity}
            onChange={(event) =>
              setForm({ ...form, capacity: Number(event.target.value) })
            }
          />
          <Input
            required
            type="number"
            min={0}
            label="Giá cơ bản"
            value={form.base_price}
            onChange={(event) =>
              setForm({ ...form, base_price: Number(event.target.value) })
            }
          />
          <Input
            label="Tiện ích (phân cách dấu phẩy)"
            value={form.amenities}
            onChange={(event) =>
              setForm({ ...form, amenities: event.target.value })
            }
          />
          <label className="sm:col-span-2 text-sm font-medium">
            Mô tả
            <textarea
              className="field mt-2 min-h-20"
              value={form.description}
              onChange={(event) =>
                setForm({ ...form, description: event.target.value })
              }
            />
          </label>
          <Button type="submit" loading={saving} className="sm:col-span-2">
            Tạo sân
          </Button>
        </form>
      </Modal>
      <FieldServicesModal field={serviceField} onClose={() => setServiceField(undefined)} />
    </>
  );
}

export function ManagementSchedulesPage() {
  const { items: fields, loading: fieldsLoading } = useFields();
  const { toast } = useToast();
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    field_id: 0,
    name: "",
    start_time: "08:00",
    end_time: "09:00",
    price: 0,
    is_active: true,
  });
  const load = () => {
    setLoading(true);
    apiRequest<Slot[]>("/time-slots")
      .then(setSlots)
      .catch((error) =>
        toast(
          error instanceof Error ? error.message : "Không tải được khung giờ.",
          "error",
        ),
      )
      .finally(() => setLoading(false));
  };
  useEffect(load, []);
  useEffect(() => {
    if (!form.field_id && fields[0])
      setForm((value) => ({ ...value, field_id: fields[0].id }));
  }, [fields]);
  const create = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await apiRequest("/time-slots", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setOpen(false);
      toast("Đã tạo khung giờ.", "success");
      load();
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không tạo được khung giờ.",
        "error",
      );
    }
  };
  const toggle = async (slot: Slot) => {
    try {
      await apiRequest(`/time-slots/${slot.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !slot.is_active }),
      });
      load();
    } catch (error) {
      toast(
        error instanceof Error
          ? error.message
          : "Không cập nhật được khung giờ.",
        "error",
      );
    }
  };
  const names = new Map(fields.map((field) => [field.id, field.name]));
  return (
    <>
      <PageHeader
        title="Khung giờ và giá"
        description="Lịch hoạt động thật của các sân thuộc OWNER hiện tại."
        actions={
          <Button
            leftIcon={<Plus size={16} />}
            disabled={!fields.length}
            onClick={() => setOpen(true)}
          >
            Thêm khung giờ
          </Button>
        }
      />
      {loading || fieldsLoading ? (
        <LoadingSkeleton lines={8} />
      ) : slots.length ? (
        <div className="overflow-x-auto rounded-card border bg-white">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-slate-50">
              <tr>
                {[
                  "Sân",
                  "Tên ca",
                  "Bắt đầu",
                  "Kết thúc",
                  "Giá",
                  "Trạng thái",
                ].map((label) => (
                  <th key={label} className="px-4 py-3">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {slots.map((slot) => (
                <tr key={slot.id} className="border-t">
                  <td className="px-4 py-3 font-semibold">
                    {names.get(slot.field_id)}
                  </td>
                  <td className="px-4 py-3">{slot.name}</td>
                  <td className="px-4 py-3">{slot.start_time.slice(0, 5)}</td>
                  <td className="px-4 py-3">{slot.end_time.slice(0, 5)}</td>
                  <td className="px-4 py-3">{money(slot.price)}</td>
                  <td className="px-4 py-3">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void toggle(slot)}
                    >
                      {slot.is_active ? "Đang mở" : "Đang khóa"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          title="Chưa có khung giờ"
          description="Tạo khung giờ sau khi đã có sân."
        />
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Thêm khung giờ">
        <form onSubmit={create} className="space-y-4">
          <label className="text-sm font-medium">
            Sân
            <select
              className="field mt-2"
              value={form.field_id}
              onChange={(event) =>
                setForm({ ...form, field_id: Number(event.target.value) })
              }
            >
              {fields.map((field) => (
                <option key={field.id} value={field.id}>
                  {field.name}
                </option>
              ))}
            </select>
          </label>
          <Input
            required
            label="Tên ca"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
          <div className="grid grid-cols-2 gap-3">
            <Input
              required
              type="time"
              label="Bắt đầu"
              value={form.start_time}
              onChange={(event) =>
                setForm({ ...form, start_time: event.target.value })
              }
            />
            <Input
              required
              type="time"
              label="Kết thúc"
              value={form.end_time}
              onChange={(event) =>
                setForm({ ...form, end_time: event.target.value })
              }
            />
          </div>
          <Input
            required
            type="number"
            min={0}
            label="Giá"
            value={form.price}
            onChange={(event) =>
              setForm({ ...form, price: Number(event.target.value) })
            }
          />
          <Button type="submit" className="w-full">
            Tạo khung giờ
          </Button>
        </form>
      </Modal>
    </>
  );
}

function useManagedBookings() {
  const [items, setItems] = useState<ApiBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();
  const load = () => {
    setLoading(true);
    apiRequest<{ items: ApiBooking[] }>("/bookings?page_size=100")
      .then((result) => setItems(result.items))
      .catch((error) =>
        toast(
          error instanceof Error ? error.message : "Không tải được booking.",
          "error",
        ),
      )
      .finally(() => setLoading(false));
  };
  useEffect(load, []);
  return { items, loading, load, toast };
}
export function ManagementCalendarPage() {
  const { items, loading } = useManagedBookings();
  const { items: fields, loading: fieldsLoading } = useFields();
  const [date, setDate] = useState(today());
  const [view, setView] = useState<"day" | "week">("day");
  const hours = Array.from({ length: 19 }, (_, index) => index + 5);
  const minuteOf = (value: string) => {
    const [hour, minute] = value.split(":").map(Number);
    return hour * 60 + minute;
  };
  const start = new Date(`${date}T00:00:00`);
  const weekDates = Array.from({ length: 7 }, (_, index) => {
    const value = new Date(start);
    value.setDate(start.getDate() - ((start.getDay() + 6) % 7) + index);
    return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
  });
  const statusStyle: Record<string, string> = {
    pending_payment: "bg-amber-100 border-amber-300",
    pending_confirmation: "bg-orange-100 border-orange-300",
    confirmed: "bg-blue-100 border-blue-300",
    in_progress: "bg-violet-100 border-violet-300",
    completed: "bg-emerald-100 border-emerald-300",
    cancelled: "bg-slate-100 border-slate-300",
    expired: "bg-slate-100 border-slate-300",
    no_show: "bg-red-100 border-red-300",
  };
  const shown = items.filter((item) =>
    view === "day"
      ? item.booking_date === date
      : weekDates.includes(item.booking_date),
  );
  return (
    <>
      <PageHeader
        title="Lịch sân trực quan"
        description="Mỗi sân là một hàng; booking lấy trực tiếp từ backend và click để xem chi tiết."
      />
      <div className="mb-4 flex flex-wrap gap-2">
        <Input
          className="max-w-xs"
          type="date"
          value={date}
          onChange={(event) => setDate(event.target.value)}
          leftIcon={<CalendarDays size={16} />}
        />
        <Button
          size="sm"
          variant={view === "day" ? "primary" : "outline"}
          onClick={() => setView("day")}
        >
          Ngày
        </Button>
        <Button
          size="sm"
          variant={view === "week" ? "primary" : "outline"}
          onClick={() => setView("week")}
        >
          Tuần
        </Button>
      </div>
      <div className="mb-4 flex flex-wrap gap-3 text-xs">
        <span className="rounded bg-amber-100 px-2 py-1">Giữ chỗ</span>
        <span className="rounded bg-orange-100 px-2 py-1">Chờ xác nhận</span>
        <span className="rounded bg-blue-100 px-2 py-1">Đã xác nhận</span>
        <span className="rounded bg-violet-100 px-2 py-1">Đang sử dụng</span>
        <span className="rounded bg-emerald-100 px-2 py-1">Hoàn thành</span>
        <span className="rounded bg-slate-200 px-2 py-1">Đã khóa</span>
      </div>
      {loading || fieldsLoading ? (
        <LoadingSkeleton lines={8} />
      ) : view === "day" ? (
        <div className="overflow-x-auto rounded-card border bg-white">
          <div className="min-w-[1500px]">
            <div
              className="grid bg-slate-50 text-xs font-semibold"
              style={{
                gridTemplateColumns: `180px repeat(${hours.length}, 1fr)`,
              }}
            >
              <div className="p-3">Sân</div>
              {hours.map((hour) => (
                <div key={hour} className="border-l p-3 text-center">
                  {String(hour).padStart(2, "0")}:00
                </div>
              ))}
            </div>
            {fields.map((field) => (
              <div
                key={field.id}
                className="grid min-h-20 border-t"
                style={{
                  gridTemplateColumns: `180px repeat(${hours.length}, 1fr)`,
                }}
              >
                <div className="p-3">
                  <b>{field.name}</b>
                  <small className="block text-slate-500">
                    {field.sport_type}
                  </small>
                </div>
                {hours.map((hour) => {
                  const occurrence = shown
                    .filter((item) => item.field_id === field.id)
                    .flatMap((booking) =>
                      booking.selected_slots.map((slot) => ({ booking, slot })),
                    )
                    .find(
                      ({ slot }) =>
                        minuteOf(slot.start_time) < (hour + 1) * 60 &&
                        minuteOf(slot.end_time) > hour * 60,
                    );
                  return (
                    <div
                      key={hour}
                      className={`border-l p-1 ${field.status !== "available" ? "bg-slate-200" : ""}`}
                    >
                      {occurrence &&
                        Math.floor(minuteOf(occurrence.slot.start_time) / 60) ===
                          hour && (
                          <Link
                            to={`/management/bookings/${occurrence.booking.id}`}
                            className={`block h-full min-w-24 rounded border p-2 text-xs ${statusStyle[occurrence.booking.status] || "bg-slate-100"}`}
                          >
                            <b className="block truncate">
                              {occurrence.booking.customer_name}
                            </b>
                            <span>
                              {occurrence.slot.start_time.slice(0, 5)}–
                              {occurrence.slot.end_time.slice(0, 5)}
                            </span>
                          </Link>
                        )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="grid gap-3 overflow-x-auto md:grid-cols-7">
          {weekDates.map((day) => (
            <section
              key={day}
              className="min-h-72 rounded-card border bg-white p-3"
            >
              <b className="text-sm">
                {new Date(`${day}T00:00`).toLocaleDateString("vi-VN", {
                  weekday: "short",
                  day: "2-digit",
                  month: "2-digit",
                })}
              </b>
              <div className="mt-3 space-y-2">
                {shown
                  .filter((item) => item.booking_date === day)
                  .sort((a, b) =>
                    a.start_time_snapshot.localeCompare(b.start_time_snapshot),
                  )
                  .map((booking) => (
                    <Link
                      key={booking.id}
                      to={`/management/bookings/${booking.id}`}
                      className={`block rounded border p-2 text-xs ${statusStyle[booking.status] || "bg-slate-100"}`}
                    >
                      <b>
                        {booking.selected_slots
                          .map(
                            (slot) =>
                              `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`,
                          )
                          .join(", ")}{" "}
                        · {booking.field_name}
                      </b>
                      <span className="block truncate">
                        {booking.customer_name}
                      </span>
                    </Link>
                  ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  );
}

function useReports() {
  const [data, setData] = useState<{
    summary?: Summary;
    revenue?: Revenue;
    performance?: FieldPerformance;
  }>({});
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();
  const load = () => {
    setLoading(true);
    Promise.all([
      apiRequest<Summary>("/dashboard/summary"),
      apiRequest<Revenue>("/dashboard/revenue"),
      apiRequest<FieldPerformance>("/dashboard/field-performance"),
    ])
      .then(([summary, revenue, performance]) =>
        setData({ summary, revenue, performance }),
      )
      .catch((error) =>
        toast(
          error instanceof Error ? error.message : "Không tải được báo cáo.",
          "error",
        ),
      )
      .finally(() => setLoading(false));
  };
  useEffect(load, []);
  return { ...data, loading, load };
}
export function ManagementDashboardPage() {
  const { summary, revenue, performance, loading, load } = useReports();
  if (loading) return <LoadingSkeleton lines={10} />;
  if (!summary || !revenue || !performance)
    return (
      <EmptyState
        title="Không tải được tổng quan"
        description="Hãy kiểm tra quyền báo cáo và thử lại."
        action={<Button onClick={load}>Thử lại</Button>}
      />
    );
  return (
    <>
      <PageHeader
        title="Tổng quan vận hành"
        description={`Dữ liệu ${summary.date_from} – ${summary.date_to} của OWNER hiện tại.`}
        actions={
          <Button
            variant="outline"
            leftIcon={<RefreshCw size={16} />}
            onClick={load}
          >
            Làm mới
          </Button>
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="Tổng sân" value={String(summary.total_fields)} />
        <Metric label="Sân hoạt động" value={String(summary.active_fields)} />
        <Metric label="Booking" value={String(summary.total_bookings)} />
        <Metric label="Chờ xử lý" value={String(summary.pending_bookings)} />
        <Metric label="Doanh thu đã thu" value={money(summary.paid_revenue)} />
      </div>
      <section className="mt-6 rounded-card border bg-white p-5">
        <h2 className="font-bold">Hiệu suất sân</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {performance.items.map((field) => (
            <div key={field.field_id} className="rounded-xl bg-slate-50 p-4">
              <b>{field.field_name}</b>
              <p className="mt-1 text-sm text-slate-500">
                {field.booking_count} booking · Lấp đầy {field.utilization_rate}
                %
              </p>
              <p className="mt-2 font-semibold text-brand-700">
                {money(field.paid_revenue)}
              </p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
export function ManagementReportsPage() {
  const { summary, revenue, performance, loading } = useReports();
  return (
    <>
      <PageHeader
        title="Báo cáo"
        description="Số liệu thật từ booking và payment đã thanh toán."
      />
      {loading ? (
        <LoadingSkeleton lines={10} />
      ) : summary && revenue && performance ? (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <Metric
              label="Tổng booking"
              value={String(summary.total_bookings)}
            />
            <Metric
              label="Booking đã xác nhận"
              value={String(summary.confirmed_bookings)}
            />
            <Metric label="Doanh thu" value={money(revenue.total)} />
          </div>
          <div className="overflow-x-auto rounded-card border bg-white">
            <table className="w-full min-w-[700px] text-left text-sm">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    "Sân",
                    "Môn",
                    "Booking",
                    "Hoàn thành",
                    "Lấp đầy",
                    "Doanh thu",
                  ].map((label) => (
                    <th key={label} className="px-4 py-3">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {performance.items.map((field) => (
                  <tr key={field.field_id} className="border-t">
                    <td className="px-4 py-3 font-semibold">
                      {field.field_name}
                    </td>
                    <td className="px-4 py-3">{field.sport_type}</td>
                    <td className="px-4 py-3">{field.booking_count}</td>
                    <td className="px-4 py-3">{field.completed_count}</td>
                    <td className="px-4 py-3">{field.utilization_rate}%</td>
                    <td className="px-4 py-3">{money(field.paid_revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <EmptyState
          title="Không có dữ liệu báo cáo"
          description="Chưa có booking hoặc payment phù hợp."
        />
      )}
    </>
  );
}
interface OccupancySummary {
  label: string;
  summary: string;
  promotion_suggestions: string[];
  source: string;
  analytics: {
    date_from: string;
    date_to: string;
    total_operating_hours: number;
    total_available_hours: number;
    booked_hours: number;
    occupancy_rate: number;
    booking_count: number;
    revenue: number;
    cancellation_rate: number;
    peak_hours: Array<{
      slot_id: number;
      field_name: string;
      start_time: string;
      end_time: string;
      occupancy_rate: number;
    }>;
    low_demand_hours: Array<{
      slot_id: number;
      field_name: string;
      start_time: string;
      end_time: string;
      occupancy_rate: number;
    }>;
    low_peak_hours: Array<{
      slot_id: number;
      field_name: string;
      start_time: string;
      end_time: string;
      occupancy_rate: number;
    }>;
    occupancy_by_court: Array<{
      field_id: number;
      field_name: string;
      total_available_hours: number;
      booked_hours: number;
      booking_count: number;
      occupancy_rate: number;
    }>;
    occupancy_by_day: Array<{
      date: string;
      total_available_hours: number;
      booked_hours: number;
      booking_count: number;
      occupancy_rate: number;
    }>;
    occupancy_by_time: Array<{
      start_time: string;
      end_time: string;
      total_available_hours: number;
      booked_hours: number;
      booking_count: number;
      occupancy_rate: number;
    }>;
  };
}

export function ManagementAIInsightsPage() {
  const [report, setReport] = useState<OccupancySummary>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = () => {
    setLoading(true);
    setError("");
    apiRequest<OccupancySummary>("/ai/occupancy-summary")
      .then(setReport)
      .catch((reason) =>
        setError(
          reason instanceof Error
            ? reason.message
            : "Không tải được phân tích công suất.",
        ),
      )
      .finally(() => setLoading(false));
  };
  useEffect(load, []);
  if (loading) return <LoadingSkeleton lines={9} />;
  if (error)
    return (
      <EmptyState
        title="Không tải được Gợi ý AI"
        description={error}
        action={<Button onClick={load}>Thử lại</Button>}
      />
    );
  if (!report || report.analytics.total_operating_hours === 0)
    return (
      <EmptyState
        title="Chưa có dữ liệu công suất"
        description="Hãy cấu hình sân và khung giờ hoạt động trước khi yêu cầu AI phân tích."
        action={<Button onClick={load}>Làm mới</Button>}
      />
    );
  const data = report.analytics;
  return (
    <>
      <PageHeader
        title="AI phân tích công suất"
        description={`Số liệu thật ${data.date_from} – ${data.date_to}; AI chỉ tóm tắt và đề xuất, không tự sửa giá.`}
        actions={
          <Button
            variant="outline"
            leftIcon={<RefreshCw size={16} />}
            onClick={load}
          >
            Làm mới
          </Button>
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Metric
          label="Giờ khả dụng"
          value={`${data.total_available_hours} giờ`}
        />
        <Metric label="Giờ đã đặt" value={`${data.booked_hours} giờ`} />
        <Metric label="Công suất" value={`${data.occupancy_rate}%`} />
        <Metric label="Booking" value={String(data.booking_count)} />
        <Metric label="Doanh thu" value={money(data.revenue)} />
      </div>
      <section className="mt-5 rounded-card border border-ai-500/20 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="ai">
            <Bot size={14} /> {report.label}
          </Badge>
          <span className="text-xs text-slate-400">
            {report.source === "fallback"
              ? "Template dự phòng"
              : "Đã kiểm tra với analytics backend"}
          </span>
        </div>
        <p className="mt-3 text-sm leading-6 text-slate-700">
          {report.summary}
        </p>
        <div className="mt-4 space-y-2">
          {report.promotion_suggestions.length ? (
            report.promotion_suggestions.map((item) => (
              <div
                key={item}
                className="rounded-xl bg-ai-50 p-3 text-sm text-ai-900"
              >
                {item}
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500">
              Chưa xác định được giờ thấp điểm để đề xuất.
            </p>
          )}
        </div>
        <p className="mt-4 text-xs text-slate-500">
          Tỷ lệ hủy: {data.cancellation_rate}%. Các đề xuất không tạo hoặc cập
          nhật chương trình khuyến mại trong hệ thống.
        </p>
      </section>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <SlotInsight title="Giờ cao điểm" items={data.peak_hours} />
        <SlotInsight title="Giờ thấp điểm" items={data.low_demand_hours} />
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <section className="rounded-card border bg-white p-5">
          <h2 className="font-bold">Công suất theo sân</h2>
          <div className="mt-3 space-y-2">
            {data.occupancy_by_court.length ? (
              data.occupancy_by_court.map((item) => (
                <div
                  key={item.field_id}
                  className="flex items-center justify-between rounded-xl bg-slate-50 p-3 text-sm"
                >
                  <span>
                    <b>{item.field_name}</b>
                    <small className="block text-slate-500">
                      {item.booking_count} booking · {item.booked_hours}/
                      {item.total_available_hours} giờ
                    </small>
                  </span>
                  <b className="text-brand-700">{item.occupancy_rate}%</b>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">
                Chưa có dữ liệu theo sân.
              </p>
            )}
          </div>
        </section>
        <section className="rounded-card border bg-white p-5">
          <h2 className="font-bold">Công suất theo ngày</h2>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {data.occupancy_by_day.length ? (
              data.occupancy_by_day.map((item) => (
                <div
                  key={item.date}
                  className="rounded-xl bg-slate-50 p-3 text-sm"
                >
                  <b>
                    {new Date(`${item.date}T00:00`).toLocaleDateString("vi-VN")}
                  </b>
                  <p className="mt-1 text-xs text-slate-500">
                    {item.booking_count} booking · {item.occupancy_rate}%
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">
                Chưa có dữ liệu theo ngày.
              </p>
            )}
          </div>
        </section>
      </div>
    </>
  );
}

function SlotInsight({
  title,
  items,
}: {
  title: string;
  items: OccupancySummary["analytics"]["peak_hours"];
}) {
  return (
    <section className="rounded-card border bg-white p-5">
      <h2 className="font-bold">{title}</h2>
      <div className="mt-3 space-y-2">
        {items.length ? (
          items.map((item) => (
            <div
              key={item.slot_id}
              className="flex items-center justify-between rounded-xl bg-slate-50 p-3 text-sm"
            >
              <span>
                <b>{item.field_name}</b>
                <small className="ml-2 text-slate-500">
                  {item.start_time}–{item.end_time}
                </small>
              </span>
              <b className="text-brand-700">{item.occupancy_rate}%</b>
            </div>
          ))
        ) : (
          <p className="text-sm text-slate-500">Chưa đủ dữ liệu để xác định.</p>
        )}
      </div>
    </section>
  );
}
function Metric({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-card border bg-white p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <b className="mt-2 block text-xl">{value}</b>
    </article>
  );
}
