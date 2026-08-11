import { Building2, CalendarClock, Clock, Clock3, Edit3, Image, LockKeyhole, MapPin, Plus, Search, ShieldCheck, Trash2, UnlockKeyhole, Wrench } from 'lucide-react';
import { useState } from 'react';
import { Badge, Button, ConfirmDialog, Input, Modal, PageHeader, useToast } from '@/components/common';
import { PermissionGuard, usePermission } from '@/contexts/PermissionContext';
import { courtTimeSlots, managedCourts, managedVenues, type CourtTimeSlot, type ManagedCourt, type ManagedVenue } from '@/data/operationsData';
import { managementMoney } from '@/data/managementData';

/* ─── Venue management (unchanged) ─────────────────────────────────────────── */
const amenities = ['Bãi đỗ xe', 'Phòng thay đồ', 'Phòng tắm', 'Căng tin', 'Wifi', 'Cho thuê dụng cụ', 'Tủ đồ', 'Điều hòa'];
const emptyVenue: ManagedVenue = { id: '', name: '', address: '', city: 'TP. Hồ Chí Minh', open: '06:00', close: '22:00', image: '', amenities: [], policies: '', status: 'active', courts: 0 };
export function ManagementVenuesPage() {
  const { toast } = useToast(); const { user } = usePermission(); const [items, setItems] = useState(managedVenues); const [editing, setEditing] = useState<ManagedVenue>(); const [form, setForm] = useState(emptyVenue); const [error, setError] = useState<Record<string, string>>({}); const [danger, setDanger] = useState<ManagedVenue>();
  const openForm = (venue?: ManagedVenue) => { setEditing(venue); setForm(venue ? { ...venue, amenities: [...venue.amenities] } : { ...emptyVenue, id: `v${items.length + 1}` }); setError({}); };
  const save = () => { const next: Record<string, string> = {}; if (form.name.trim().length < 3) next.name = 'Tên cơ sở cần ít nhất 3 ký tự.'; if (form.address.trim().length < 8) next.address = 'Vui lòng nhập địa chỉ đầy đủ.'; if (!form.image.startsWith('http')) next.image = 'Nhập URL hình ảnh hợp lệ.'; if (form.open >= form.close) next.hours = 'Giờ đóng cửa phải sau giờ mở cửa.'; setError(next); if (Object.keys(next).length) { toast('Vui lòng kiểm tra biểu mẫu.', 'error'); return; } setItems(editing ? items.map((item) => item.id === form.id ? form : item) : [...items, form]); setEditing(undefined); toast(editing ? 'Đã cập nhật cơ sở.' : 'Đã thêm cơ sở mới.', 'success'); };
  const toggleStatus = () => { if (!danger) return; setItems(items.map((item) => item.id === danger.id ? { ...item, status: item.status === 'inactive' ? 'active' : 'inactive' } : item)); toast(danger.status === 'inactive' ? 'Đã kích hoạt cơ sở.' : 'Đã ngừng hoạt động cơ sở.', 'success'); };
  const visible = items.filter((item) => user.role === 'OWNER' || user.venueIds.includes(item.id));
  return <><PageHeader title="Quản lý cơ sở" description="Quản lý thông tin, hình ảnh và trạng thái các địa điểm kinh doanh." actions={<PermissionGuard module="venues" action="create"><Button leftIcon={<Plus size={16} />} onClick={() => openForm()}>Thêm cơ sở</Button></PermissionGuard>} /><div className="grid gap-5 lg:grid-cols-2 2xl:grid-cols-3">{visible.map((venue) => <article key={venue.id} className="overflow-hidden rounded-card border border-slate-200 bg-white shadow-sm"><div className="relative h-44 bg-slate-100"><img src={venue.image} alt={venue.name} className="h-full w-full object-cover" /><Badge className="absolute left-3 top-3" variant={venue.status === 'active' ? 'success' : venue.status === 'maintenance' ? 'warning' : 'neutral'}>{venue.status === 'active' ? 'Đang hoạt động' : venue.status === 'maintenance' ? 'Bảo trì' : 'Ngừng hoạt động'}</Badge></div><div className="p-5"><div className="flex items-start justify-between gap-3"><div><h2 className="font-bold text-slate-950">{venue.name}</h2><p className="mt-1 flex gap-1.5 text-xs text-slate-500"><MapPin size={14} className="shrink-0" />{venue.address}, {venue.city}</p></div><span className="rounded-lg bg-brand-50 px-2 py-1 text-xs font-bold text-brand-700">{venue.courts} sân</span></div><p className="mt-4 flex items-center gap-2 text-sm text-slate-600"><Clock3 size={16} className="text-brand-600" />{venue.open}–{venue.close} · Hàng ngày</p><div className="mt-3 flex flex-wrap gap-1.5">{venue.amenities.map((item) => <span key={item} className="rounded-md bg-slate-100 px-2 py-1 text-[11px] text-slate-600">{item}</span>)}</div><p className="mt-4 line-clamp-2 rounded-lg bg-slate-50 p-3 text-xs text-slate-500"><ShieldCheck size={14} className="mr-1 inline text-brand-600" />{venue.policies}</p><div className="mt-4 flex justify-end gap-2 border-t border-slate-100 pt-4"><PermissionGuard module="venues" action="update"><Button size="sm" variant="outline" leftIcon={<Edit3 size={15} />} onClick={() => openForm(venue)}>Chỉnh sửa</Button><Button size="sm" variant={venue.status === 'inactive' ? 'primary' : 'danger'} onClick={() => setDanger(venue)}>{venue.status === 'inactive' ? 'Kích hoạt' : 'Ngừng hoạt động'}</Button></PermissionGuard></div></div></article>)}</div>
    <Modal open={Boolean(editing) || Boolean(form.id && !items.some((item) => item.id === form.id))} onClose={() => { setEditing(undefined); setForm(emptyVenue); }} title={editing ? 'Chỉnh sửa cơ sở' : 'Thêm cơ sở mới'}><div className="max-h-[70vh] space-y-4 overflow-y-auto pr-1"><Input label="Tên cơ sở *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} error={error.name} /><Input label="Địa chỉ *" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} error={error.address} /><label className="block text-sm font-medium">Tỉnh / Thành phố<select className="field mt-1.5" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })}><option>TP. Hồ Chí Minh</option><option>Hà Nội</option><option>Đà Nẵng</option></select></label><div className="grid grid-cols-2 gap-3"><Input label="Giờ mở cửa" type="time" value={form.open} onChange={(e) => setForm({ ...form, open: e.target.value })} /><Input label="Giờ đóng cửa" type="time" value={form.close} onChange={(e) => setForm({ ...form, close: e.target.value })} /></div>{error.hours && <p className="text-xs text-red-600">{error.hours}</p>}<Input label="URL hình ảnh *" value={form.image} onChange={(e) => setForm({ ...form, image: e.target.value })} error={error.image} leftIcon={<Image size={16} />} /><fieldset><legend className="mb-2 text-sm font-medium">Tiện ích</legend><div className="grid grid-cols-2 gap-2">{amenities.map((item) => <label key={item} className="flex items-center gap-2 rounded-lg border border-slate-200 p-2 text-xs"><input type="checkbox" checked={form.amenities.includes(item)} onChange={() => setForm({ ...form, amenities: form.amenities.includes(item) ? form.amenities.filter((entry) => entry !== item) : [...form.amenities, item] })} className="accent-emerald-600" />{item}</label>)}</div></fieldset><label className="block text-sm font-medium">Chính sách<textarea className="field mt-1.5 min-h-20 py-2" value={form.policies} onChange={(e) => setForm({ ...form, policies: e.target.value })} /></label><div className="flex justify-end gap-2 pt-2"><Button variant="ghost" onClick={() => { setEditing(undefined); setForm(emptyVenue); }}>Hủy</Button><Button onClick={save}>Lưu cơ sở</Button></div></div></Modal><ConfirmDialog open={Boolean(danger)} onClose={() => setDanger(undefined)} onConfirm={toggleStatus} danger={danger?.status !== 'inactive'} title={danger?.status === 'inactive' ? 'Kích hoạt cơ sở?' : 'Ngừng hoạt động cơ sở?'} description="Trạng thái cơ sở và khả năng nhận booking sẽ được cập nhật ngay." confirmLabel="Xác nhận" /></>;
}

/* ─── Time-slot helpers ─────────────────────────────────────────────────────── */
const ALL_DAYS_LIST = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];
const priceTypeConfig = {
  standard: { label: 'Tiêu chuẩn', bg: 'bg-slate-100', text: 'text-slate-600', dot: 'bg-slate-400' },
  peak:     { label: 'Cao điểm',   bg: 'bg-red-50',    text: 'text-red-700',   dot: 'bg-red-500' },
  off_peak: { label: 'Giảm giá',   bg: 'bg-sky-50',    text: 'text-sky-700',   dot: 'bg-sky-400' },
} as const;

const emptySlot = (courtId: string, nextId: string): CourtTimeSlot => ({
  id: nextId, courtId, label: '', start: '06:00', end: '08:00', priceType: 'standard', priceOverride: null, days: [...ALL_DAYS_LIST], active: true,
});

/* ─── Time-slot editor sub-component ───────────────────────────────────────── */
function CourtTimeSlotsEditor({ courtId, basePrice, slots, setSlots }: {
  courtId: string; basePrice: number;
  slots: CourtTimeSlot[]; setSlots: (s: CourtTimeSlot[]) => void;
}) {
  const courtSlots = slots.filter((s) => s.courtId === courtId);
  const [editSlot, setEditSlot] = useState<CourtTimeSlot | null>(null);
  const [slotError, setSlotError] = useState<Record<string, string>>({});
  const [deleteTarget, setDeleteTarget] = useState<CourtTimeSlot | null>(null);

  const openNew = () => {
    const nextId = `ts_new_${Date.now()}`;
    setEditSlot(emptySlot(courtId, nextId));
    setSlotError({});
  };
  const openEdit = (s: CourtTimeSlot) => { setEditSlot({ ...s, days: [...s.days] }); setSlotError({}); };

  const saveSlot = () => {
    if (!editSlot) return;
    const errs: Record<string, string> = {};
    if (!editSlot.label.trim()) errs.label = 'Vui lòng nhập tên khung giờ.';
    if (editSlot.start >= editSlot.end) errs.time = 'Giờ kết thúc phải sau giờ bắt đầu.';
    if (editSlot.days.length === 0) errs.days = 'Chọn ít nhất một ngày trong tuần.';
    if (editSlot.priceOverride !== null && editSlot.priceOverride <= 0) errs.price = 'Giá ghi đè phải lớn hơn 0.';
    setSlotError(errs);
    if (Object.keys(errs).length) return;
    const exists = slots.some((s) => s.id === editSlot.id);
    setSlots(exists ? slots.map((s) => s.id === editSlot.id ? editSlot : s) : [...slots, editSlot]);
    setEditSlot(null);
  };

  const toggleSlotActive = (s: CourtTimeSlot) => setSlots(slots.map((x) => x.id === s.id ? { ...x, active: !x.active } : x));
  const deleteSlot = () => { if (!deleteTarget) return; setSlots(slots.filter((s) => s.id !== deleteTarget.id)); setDeleteTarget(null); };
  const toggleDay = (day: string) => {
    if (!editSlot) return;
    setEditSlot({ ...editSlot, days: editSlot.days.includes(day) ? editSlot.days.filter((d) => d !== day) : [...editSlot.days, day] });
  };

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">
          {courtSlots.length} khung giờ · Giá cơ bản:{' '}
          <span className="font-semibold text-brand-700">{managementMoney(basePrice)}/giờ</span>
        </p>
        <Button size="sm" leftIcon={<Plus size={14} />} onClick={openNew}>Thêm khung giờ</Button>
      </div>

      {/* Empty state */}
      {courtSlots.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 py-10 text-center text-sm text-slate-400">
          <Clock size={28} className="mx-auto mb-2 opacity-40" />
          Chưa có khung giờ nào. Nhấn <b>Thêm khung giờ</b> để bắt đầu.
        </div>
      )}

      {/* Slot list */}
      <div className="space-y-2">
        {courtSlots.map((slot) => {
          const cfg = priceTypeConfig[slot.priceType];
          return (
            <div key={slot.id} className={`flex items-start gap-3 rounded-xl border p-3 transition-all ${slot.active ? 'border-slate-200 bg-white' : 'border-slate-100 bg-slate-50 opacity-60'}`}>
              {/* Color dot */}
              <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${cfg.dot}`} />

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-slate-900 text-sm">{slot.label}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${cfg.bg} ${cfg.text}`}>{cfg.label}</span>
                  {!slot.active && <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-bold text-slate-500">Tắt</span>}
                </div>
                <p className="mt-0.5 text-xs text-slate-500">
                  <Clock size={11} className="mr-1 inline" />
                  {slot.start} – {slot.end}
                  &nbsp;·&nbsp;
                  {slot.days.length === ALL_DAYS_LIST.length ? 'Tất cả các ngày' : slot.days.join(', ')}
                </p>
                <p className="mt-1 text-xs font-medium text-brand-700">
                  {slot.priceOverride !== null ? managementMoney(slot.priceOverride) : `Theo giá cơ bản (${managementMoney(basePrice)})`}/giờ
                </p>
              </div>

              {/* Actions */}
              <div className="flex shrink-0 items-center gap-1">
                <button
                  title={slot.active ? 'Tắt khung giờ' : 'Bật khung giờ'}
                  onClick={() => toggleSlotActive(slot)}
                  className={`rounded-lg px-2 py-1 text-[11px] font-semibold transition ${slot.active ? 'bg-brand-50 text-brand-700 hover:bg-brand-100' : 'bg-slate-200 text-slate-500 hover:bg-slate-300'}`}
                >
                  {slot.active ? 'Bật' : 'Tắt'}
                </button>
                <button onClick={() => openEdit(slot)} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700" title="Sửa">
                  <Edit3 size={14} />
                </button>
                <button onClick={() => setDeleteTarget(slot)} className="rounded-lg p-1.5 text-red-400 hover:bg-red-50 hover:text-red-600" title="Xóa">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Edit / Add slot modal */}
      <Modal open={Boolean(editSlot)} onClose={() => setEditSlot(null)} title={editSlot && slots.some((s) => s.id === editSlot.id) ? 'Sửa khung giờ' : 'Thêm khung giờ'}>
        {editSlot && (
          <div className="space-y-4">
            <Input label="Tên khung giờ *" placeholder="VD: Sáng sớm, Giờ cao điểm..." value={editSlot.label} onChange={(e) => setEditSlot({ ...editSlot, label: e.target.value })} error={slotError.label} />

            <div className="grid grid-cols-2 gap-3">
              <Input label="Giờ bắt đầu" type="time" value={editSlot.start} onChange={(e) => setEditSlot({ ...editSlot, start: e.target.value })} />
              <Input label="Giờ kết thúc" type="time" value={editSlot.end} onChange={(e) => setEditSlot({ ...editSlot, end: e.target.value })} />
            </div>
            {slotError.time && <p className="text-xs text-red-600">{slotError.time}</p>}

            {/* Day of week */}
            <fieldset>
              <legend className="mb-2 text-sm font-medium">Áp dụng cho các ngày *</legend>
              <div className="flex flex-wrap gap-2">
                {ALL_DAYS_LIST.map((day) => (
                  <button
                    key={day} type="button"
                    onClick={() => toggleDay(day)}
                    className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${editSlot.days.includes(day) ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-slate-200 text-slate-400 hover:border-slate-300'}`}
                  >{day}</button>
                ))}
              </div>
              {slotError.days && <p className="mt-1 text-xs text-red-600">{slotError.days}</p>}
            </fieldset>

            {/* Price type */}
            <div>
              <label className="mb-2 block text-sm font-medium">Loại giá</label>
              <div className="grid grid-cols-3 gap-2">
                {(['standard', 'peak', 'off_peak'] as const).map((pt) => {
                  const cfg = priceTypeConfig[pt];
                  return (
                    <button key={pt} type="button" onClick={() => setEditSlot({ ...editSlot, priceType: pt })}
                      className={`rounded-xl border p-3 text-center text-xs font-semibold transition ${editSlot.priceType === pt ? `border-brand-500 ring-2 ring-brand-100 ${cfg.bg} ${cfg.text}` : 'border-slate-200 text-slate-500 hover:border-slate-300'}`}>
                      <span className={`mb-1 block h-2.5 w-2.5 rounded-full mx-auto ${cfg.dot}`} />
                      {cfg.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Price override */}
            <div>
              <label className="mb-1.5 block text-sm font-medium">Giá riêng cho khung này (VND/giờ)</label>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="price-override-toggle"
                  className="accent-emerald-600"
                  checked={editSlot.priceOverride !== null}
                  onChange={(e) => setEditSlot({ ...editSlot, priceOverride: e.target.checked ? basePrice : null })}
                />
                <label htmlFor="price-override-toggle" className="text-xs text-slate-600">Ghi đè giá cơ bản</label>
              </div>
              {editSlot.priceOverride !== null && (
                <div className="mt-2">
                  <Input
                    type="number" placeholder={`Giá cơ bản: ${basePrice}`}
                    value={editSlot.priceOverride}
                    onChange={(e) => setEditSlot({ ...editSlot, priceOverride: Number(e.target.value) })}
                    error={slotError.price}
                  />
                </div>
              )}
              {editSlot.priceOverride === null && (
                <p className="mt-1.5 text-xs text-slate-400">Sẽ dùng giá cơ bản của sân: <b className="text-brand-700">{managementMoney(basePrice)}/giờ</b></p>
              )}
            </div>

            {/* Active toggle */}
            <div className="flex items-center gap-2 rounded-lg border border-slate-200 p-3">
              <input type="checkbox" id="slot-active" className="accent-emerald-600" checked={editSlot.active} onChange={(e) => setEditSlot({ ...editSlot, active: e.target.checked })} />
              <label htmlFor="slot-active" className="text-sm text-slate-700">Kích hoạt khung giờ này (khách hàng có thể đặt)</label>
            </div>

            <div className="flex justify-end gap-2 border-t border-slate-100 pt-3">
              <Button variant="ghost" onClick={() => setEditSlot(null)}>Hủy</Button>
              <Button onClick={saveSlot}>Lưu khung giờ</Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Delete confirm */}
      <ConfirmDialog
        open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} onConfirm={deleteSlot}
        danger title="Xóa khung giờ?" confirmLabel="Xóa"
        description={`Khung giờ "${deleteTarget?.label}" sẽ bị xóa vĩnh viễn. Các booking hiện tại không bị ảnh hưởng.`}
      />
    </div>
  );
}

/* ─── Court management ──────────────────────────────────────────────────────── */
const emptyCourt: ManagedCourt = { id: '', venueId: 'v1', name: '', sport: 'Bóng đá', type: 'Sân 5 người · Ngoài trời', price: 0, status: 'active', maintenance: 'Không có lịch bảo trì' };
export function ManagementCourtsPage() {
  const { toast } = useToast();
  const { user } = usePermission();
  const [items, setItems] = useState(managedCourts);
  const [slots, setSlots] = useState(courtTimeSlots);
  const [query, setQuery] = useState('');
  const [venue, setVenue] = useState('all');
  const [form, setForm] = useState<ManagedCourt>();
  const [activeTab, setActiveTab] = useState<'info' | 'slots'>('info');
  const [error, setError] = useState<Record<string, string>>({});
  const [lock, setLock] = useState<ManagedCourt>();

  const visibleVenues = managedVenues.filter((item) => user.role === 'OWNER' || user.venueIds.includes(item.id));
  const filtered = items.filter(
    (item) => visibleVenues.some((v) => v.id === item.venueId)
      && (venue === 'all' || item.venueId === venue)
      && `${item.name} ${item.sport}`.toLowerCase().includes(query.toLowerCase()),
  );

  const openForm = (court: ManagedCourt) => { setForm({ ...court }); setError({}); setActiveTab('info'); };

  const save = () => {
    if (!form) return;
    const next: Record<string, string> = {};
    if (form.name.trim().length < 2) next.name = 'Vui lòng nhập tên sân.';
    if (form.price <= 0) next.price = 'Giá cơ bản phải lớn hơn 0.';
    setError(next);
    if (Object.keys(next).length) { toast('Vui lòng kiểm tra biểu mẫu.', 'error'); return; }
    setItems(items.some((item) => item.id === form.id) ? items.map((item) => item.id === form.id ? form : item) : [...items, form]);
    setForm(undefined);
    toast('Đã lưu thông tin sân.', 'success');
  };

  const toggle = () => {
    if (!lock) return;
    setItems(items.map((item) => item.id === lock.id ? { ...item, status: item.status === 'locked' ? 'active' : 'locked' } : item));
    toast(lock.status === 'locked' ? 'Đã mở lại sân.' : 'Đã tạm khóa sân.', 'success');
  };

  const isEditing = Boolean(form) && items.some((item) => item.id === form?.id);

  return (
    <>
      <PageHeader
        title="Quản lý sân"
        description="Cấu hình sân con, giá cơ bản và kế hoạch bảo trì."
        actions={
          <PermissionGuard module="courts" action="create">
            <Button leftIcon={<Plus size={16} />} onClick={() => { setForm({ ...emptyCourt, id: `c${items.length + 1}`, venueId: visibleVenues[0]?.id ?? 'v1' }); setActiveTab('info'); setError({}); }}>Thêm sân</Button>
          </PermissionGuard>
        }
      />

      {/* Filter bar */}
      <section className="rounded-card border border-slate-200 bg-white">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input className="field pl-9 text-sm" placeholder="Tìm tên sân, môn thể thao..." value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          <select className="field sm:w-56" value={venue} onChange={(e) => setVenue(e.target.value)}>
            <option value="all">Tất cả cơ sở</option>
            {visibleVenues.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </div>

        {/* Court cards */}
        <div className="grid gap-4 p-4 lg:grid-cols-2 2xl:grid-cols-3">
          {filtered.map((court) => {
            const courtSlotCount = slots.filter((s) => s.courtId === court.id && s.active).length;
            return (
              <article key={court.id} className="rounded-xl border border-slate-200 p-4">
                <div className="flex items-start justify-between">
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-700"><CalendarClock size={20} /></span>
                  <Badge variant={court.status === 'active' ? 'success' : court.status === 'locked' ? 'danger' : 'warning'}>
                    {court.status === 'active' ? 'Hoạt động' : court.status === 'locked' ? 'Tạm khóa' : 'Bảo trì'}
                  </Badge>
                </div>
                <h2 className="mt-4 font-bold">{court.name}</h2>
                <p className="text-xs text-slate-500">{managedVenues.find((item) => item.id === court.venueId)?.name}</p>
                <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div><span className="block text-xs text-slate-400">Môn thể thao</span><b>{court.sport}</b></div>
                  <div><span className="block text-xs text-slate-400">Loại sân</span><b>{court.type}</b></div>
                  <div className="col-span-2 flex items-end justify-between">
                    <div><span className="block text-xs text-slate-400">Giá cơ bản</span><b className="text-lg text-brand-700">{managementMoney(court.price)}/giờ</b></div>
                    {/* Slot count badge */}
                    <span className={`flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-semibold ${courtSlotCount > 0 ? 'bg-sky-50 text-sky-700' : 'bg-slate-100 text-slate-400'}`}>
                      <Clock size={11} />{courtSlotCount} khung giờ
                    </span>
                  </div>
                </div>
                <p className="mt-4 flex gap-2 rounded-lg bg-amber-50 p-3 text-xs text-amber-800"><Wrench size={15} className="shrink-0" />{court.maintenance}</p>
                <div className="mt-4 flex justify-end gap-2">
                  <PermissionGuard module="courts" action="update">
                    <Button size="sm" variant="outline" leftIcon={<Edit3 size={15} />} onClick={() => openForm(court)}>Sửa</Button>
                    <Button size="sm" variant={court.status === 'locked' ? 'primary' : 'danger'} leftIcon={court.status === 'locked' ? <UnlockKeyhole size={15} /> : <LockKeyhole size={15} />} onClick={() => setLock(court)}>
                      {court.status === 'locked' ? 'Mở sân' : 'Tạm khóa'}
                    </Button>
                  </PermissionGuard>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {/* Court edit modal — tabbed */}
      <Modal
        open={Boolean(form)}
        onClose={() => setForm(undefined)}
        title={isEditing ? `Chỉnh sửa: ${form?.name}` : 'Thêm sân mới'}
      >
        {form && (
          <div>
            {/* Tab navigation */}
            <div className="mb-5 flex gap-1 rounded-xl bg-slate-100 p-1">
              <button
                onClick={() => setActiveTab('info')}
                className={`flex-1 rounded-lg py-2 text-sm font-semibold transition ${activeTab === 'info' ? 'bg-white shadow-sm text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
              >
                Thông tin sân
              </button>
              <button
                onClick={() => setActiveTab('slots')}
                className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2 text-sm font-semibold transition ${activeTab === 'slots' ? 'bg-white shadow-sm text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
              >
                <Clock size={14} />
                Khung giờ
                {(() => { const n = slots.filter((s) => s.courtId === form.id && s.active).length; return n > 0 ? <span className="ml-1 rounded-full bg-brand-100 px-1.5 py-0.5 text-[10px] font-bold text-brand-700">{n}</span> : null; })()}
              </button>
            </div>

            {/* Tab: Info */}
            {activeTab === 'info' && (
              <div className="space-y-4">
                <Input label="Tên sân *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} error={error.name} />
                <div className="grid grid-cols-2 gap-3">
                  <label className="text-sm font-medium">Cơ sở
                    <select className="field mt-1.5" value={form.venueId} onChange={(e) => setForm({ ...form, venueId: e.target.value })}>
                      {visibleVenues.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                    </select>
                  </label>
                  <label className="text-sm font-medium">Môn thể thao
                    <select className="field mt-1.5" value={form.sport} onChange={(e) => setForm({ ...form, sport: e.target.value })}>
                      <option>Bóng đá</option><option>Cầu lông</option><option>Pickleball</option><option>Tennis</option>
                    </select>
                  </label>
                </div>
                <Input label="Loại sân" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} />
                <Input label="Giá cơ bản (VND/giờ)" type="number" value={form.price} onChange={(e) => setForm({ ...form, price: Number(e.target.value) })} error={error.price} />
                <Input label="Lịch bảo trì" value={form.maintenance} onChange={(e) => setForm({ ...form, maintenance: e.target.value })} />
                <div className="flex justify-end gap-2 border-t border-slate-100 pt-3">
                  <Button variant="ghost" onClick={() => setForm(undefined)}>Hủy</Button>
                  <Button onClick={save}>Lưu sân</Button>
                </div>
              </div>
            )}

            {/* Tab: Slots */}
            {activeTab === 'slots' && (
              <div>
                <CourtTimeSlotsEditor courtId={form.id} basePrice={form.price} slots={slots} setSlots={setSlots} />
                <div className="mt-4 flex justify-end border-t border-slate-100 pt-3">
                  <Button variant="ghost" onClick={() => setForm(undefined)}>Đóng</Button>
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* Lock / Unlock confirm */}
      <ConfirmDialog
        open={Boolean(lock)} onClose={() => setLock(undefined)} onConfirm={toggle}
        danger={lock?.status !== 'locked'}
        title={lock?.status === 'locked' ? 'Mở lại sân?' : 'Tạm khóa sân?'}
        description="Khi tạm khóa, sân sẽ không nhận booking mới cho đến khi được mở lại."
        confirmLabel="Xác nhận"
      />
    </>
  );
}
