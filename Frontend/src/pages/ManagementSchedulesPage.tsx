import { Clock3, Pencil, Plus, Power, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Badge, Button, ConfirmDialog, EmptyState, Input, LoadingSkeleton, Modal, PageHeader, useToast } from '@/components/common';
import { apiRequest } from '@/services/apiClient';

interface Field {
  id: number;
  facility_id: number | null;
  name: string;
  sport_type: string;
  base_price: number;
}
interface Facility { id: number; name: string; }
interface Slot {
  id: number;
  field_id: number;
  name: string;
  start_time: string;
  end_time: string;
  price: number;
  weekday_price: number | null;
  weekend_price: number | null;
  is_active: boolean;
}
interface SlotForm { field_id: number; name: string; start_time: string; end_time: string; is_active: boolean; }
interface DeleteResult { message: string; action: 'deleted' | 'deactivated'; time_slot: Slot | null; }

const emptyForm: SlotForm = { field_id: 0, name: '', start_time: '08:00', end_time: '09:00', is_active: true };
const money = (value: number) => `${Number(value).toLocaleString('vi-VN')}đ`;

export function ManagementSchedulesPage() {
  const { toast } = useToast();
  const [fields, setFields] = useState<Field[]>([]);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Slot>();
  const [form, setForm] = useState<SlotForm>(emptyForm);
  const [confirm, setConfirm] = useState<{ kind: 'delete' | 'toggle'; slot: Slot }>();
  const [facilityFilter, setFacilityFilter] = useState('all');
  const [fieldFilter, setFieldFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  const load = async () => {
    setLoading(true);
    try {
      const [fieldResult, facilityResult, slotResult] = await Promise.all([
        apiRequest<{ items: Field[] }>('/fields?page_size=100'),
        apiRequest<Facility[]>('/facilities'),
        apiRequest<Slot[]>('/time-slots'),
      ]);
      setFields(fieldResult.items);
      setFacilities(facilityResult);
      setSlots(slotResult);
      setForm((current) => ({ ...current, field_id: current.field_id || fieldResult.items[0]?.id || 0 }));
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Không tải được dữ liệu khung giờ.', 'error');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);

  const fieldById = useMemo(() => new Map(fields.map((field) => [field.id, field])), [fields]);
  const facilityById = useMemo(() => new Map(facilities.map((facility) => [facility.id, facility])), [facilities]);
  const filteredFields = fields.filter((field) => facilityFilter === 'all' || String(field.facility_id) === facilityFilter);
  const shown = slots.filter((slot) => {
    const field = fieldById.get(slot.field_id);
    return (facilityFilter === 'all' || String(field?.facility_id) === facilityFilter)
      && (fieldFilter === 'all' || String(slot.field_id) === fieldFilter)
      && (statusFilter === 'all' || (statusFilter === 'active') === slot.is_active);
  });

  const openCreate = () => {
    setEditing(undefined);
    setForm({ ...emptyForm, field_id: fields[0]?.id || 0 });
    setFormOpen(true);
  };
  const openEdit = (slot: Slot) => {
    setEditing(slot);
    setForm({ field_id: slot.field_id, name: slot.name, start_time: slot.start_time.slice(0, 5), end_time: slot.end_time.slice(0, 5), is_active: slot.is_active });
    setFormOpen(true);
  };
  const closeForm = () => { setFormOpen(false); setEditing(undefined); setForm(emptyForm); };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (form.start_time >= form.end_time) {
      toast('Giờ bắt đầu phải nhỏ hơn giờ kết thúc.', 'error');
      return;
    }
    const field = fieldById.get(form.field_id);
    const current = editing;
    if (!field) return;
    setSaving(true);
    try {
      const payload = {
        ...form,
        price: current?.price ?? field.base_price,
        weekday_price: current?.weekday_price ?? null,
        weekend_price: current?.weekend_price ?? null,
      };
      const saved = await apiRequest<Slot>(current ? `/time-slots/${current.id}` : '/time-slots', {
        method: current ? 'PUT' : 'POST',
        body: JSON.stringify(payload),
      });
      setSlots((items) => current ? items.map((item) => item.id === saved.id ? saved : item) : [...items, saved].sort((a, b) => a.start_time.localeCompare(b.start_time)));
      closeForm();
      toast(current ? 'Đã cập nhật khung giờ.' : 'Đã thêm khung giờ.', 'success');
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Không thể lưu khung giờ.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const performConfirmedAction = async () => {
    if (!confirm) return;
    const { slot, kind } = confirm;
    setSaving(true);
    try {
      if (kind === 'toggle') {
        const updated = await apiRequest<Slot>(`/time-slots/${slot.id}/status`, { method: 'PATCH', body: JSON.stringify({ is_active: !slot.is_active }) });
        setSlots((items) => items.map((item) => item.id === updated.id ? updated : item));
        toast(updated.is_active ? 'Đã mở khung giờ cho CUSTOMER.' : 'Đã khóa khung giờ; CUSTOMER sẽ không còn thấy slot này.', 'success');
      } else {
        const result = await apiRequest<DeleteResult>(`/time-slots/${slot.id}`, { method: 'DELETE' });
        if (result.action === 'deleted') setSlots((items) => items.filter((item) => item.id !== slot.id));
        else if (result.time_slot) setSlots((items) => items.map((item) => item.id === result.time_slot?.id ? result.time_slot : item));
        toast(result.message, result.action === 'deactivated' ? 'info' : 'success');
      }
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Không thể cập nhật khung giờ.', 'error');
    } finally {
      setSaving(false);
      setConfirm(undefined);
    }
  };

  return <>
    <PageHeader title='Khung giờ' description='Quản lý thời gian hoạt động của slot. Giá chỉ hiển thị để đối chiếu và được quản lý tại Bảng giá; backend luôn xác nhận giá khi đặt sân.' actions={<Button leftIcon={<Plus size={16} />} disabled={!fields.length} onClick={openCreate}>Thêm khung giờ</Button>} />
    <div className='mb-4 grid gap-3 rounded-card border bg-white p-4 sm:grid-cols-3'>
      <Filter label='Cơ sở' value={facilityFilter} onChange={(value) => { setFacilityFilter(value); setFieldFilter('all'); }} options={[['all', 'Tất cả cơ sở'], ...facilities.map((item) => [String(item.id), item.name])]} />
      <Filter label='Sân' value={fieldFilter} onChange={setFieldFilter} options={[['all', 'Tất cả sân'], ...filteredFields.map((item) => [String(item.id), item.name])]} />
      <Filter label='Trạng thái' value={statusFilter} onChange={setStatusFilter} options={[['all', 'Tất cả trạng thái'], ['active', 'Đang mở'], ['inactive', 'Đang khóa']]} />
    </div>
    {loading ? <LoadingSkeleton lines={8} /> : shown.length ? <div className='overflow-x-auto rounded-card border bg-white'>
      <table className='w-full min-w-[760px] text-left text-sm'>
        <thead className='bg-slate-50'><tr>{['Cơ sở / sân', 'Tên ca', 'Thời gian', 'Giá áp dụng', 'Trạng thái', 'Thao tác'].map((label) => <th key={label} className='px-4 py-3'>{label}</th>)}</tr></thead>
        <tbody>{shown.map((slot) => {
          const field = fieldById.get(slot.field_id);
          return <tr key={slot.id} className='border-t'>
            <td className='px-4 py-3'><b>{field?.name}</b><small className='block text-slate-500'>{field?.facility_id ? facilityById.get(field.facility_id)?.name : 'Cơ sở độc lập'} · {field?.sport_type}</small></td>
            <td className='px-4 py-3 font-semibold'>{slot.name}</td>
            <td className='whitespace-nowrap px-4 py-3'><Clock3 size={15} className='mr-1 inline text-brand-600' />{slot.start_time.slice(0, 5)}–{slot.end_time.slice(0, 5)}</td>
            <td className='px-4 py-3'><b>{money(slot.price)}</b><small className='block text-slate-500'>Ngày thường {money(slot.weekday_price ?? slot.price)} · Cuối tuần {money(slot.weekend_price ?? slot.price)}</small></td>
            <td className='px-4 py-3'><Badge variant={slot.is_active ? 'success' : 'neutral'}>{slot.is_active ? 'Đang mở' : 'Đang khóa'}</Badge></td>
            <td className='px-4 py-3'><div className='flex flex-wrap gap-1.5'>
              <Button size='sm' variant='outline' leftIcon={<Pencil size={14} />} onClick={() => openEdit(slot)}>Chỉnh sửa</Button>
              <Button size='sm' variant='outline' leftIcon={<Power size={14} />} onClick={() => setConfirm({ kind: 'toggle', slot })}>{slot.is_active ? 'Khóa' : 'Mở'}</Button>
              <Button size='sm' variant='danger' leftIcon={<Trash2 size={14} />} onClick={() => setConfirm({ kind: 'delete', slot })}>Xóa</Button>
            </div></td>
          </tr>;
        })}</tbody>
      </table>
    </div> : <EmptyState title='Không có khung giờ phù hợp' description='Thay đổi bộ lọc hoặc tạo khung giờ mới cho sân.' />}

    <Modal open={formOpen} onClose={closeForm} title={editing ? 'Chỉnh sửa khung giờ' : 'Thêm khung giờ'}>
      <form onSubmit={save} className='space-y-4'>
        <label className='block text-sm font-medium'>Sân<select className='field mt-2' disabled={Boolean(editing)} value={form.field_id} onChange={(event) => setForm({ ...form, field_id: Number(event.target.value) })}>{fields.map((field) => <option key={field.id} value={field.id}>{field.name} · {field.sport_type}</option>)}</select></label>
        <Input required label='Tên ca' value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        <div className='grid grid-cols-2 gap-3'><Input required type='time' label='Bắt đầu' value={form.start_time} onChange={(event) => setForm({ ...form, start_time: event.target.value })} /><Input required type='time' label='Kết thúc' value={form.end_time} onChange={(event) => setForm({ ...form, end_time: event.target.value })} /></div>
        <p className='rounded-lg bg-blue-50 p-3 text-xs text-blue-800'>Giá không sửa tại đây để tránh lệch dữ liệu. Slot mới dùng giá cơ bản của sân; hãy dùng trang Bảng giá để điều chỉnh.</p>
        <Button type='submit' className='w-full' loading={saving}>{editing ? 'Lưu thay đổi' : 'Tạo khung giờ'}</Button>
      </form>
    </Modal>
    <ConfirmDialog open={Boolean(confirm)} onClose={() => setConfirm(undefined)} onConfirm={() => void performConfirmedAction()} danger={confirm?.kind === 'delete' || (confirm?.kind === 'toggle' && confirm.slot.is_active)} title={confirm?.kind === 'delete' ? 'Xóa khung giờ?' : confirm?.slot.is_active ? 'Khóa khung giờ?' : 'Mở lại khung giờ?'} description={confirm?.kind === 'delete' ? 'Nếu slot đã có booking, hệ thống chỉ chuyển sang inactive để bảo toàn lịch sử. Slot chưa từng được dùng sẽ được xóa.' : confirm?.slot.is_active ? 'CUSTOMER sẽ không còn thấy hoặc chọn slot này. Booking cũ vẫn được giữ nguyên.' : 'Slot sẽ xuất hiện lại trong availability nếu không chồng lấn slot đang mở.'} confirmLabel={confirm?.kind === 'delete' ? 'Xác nhận xóa' : confirm?.slot.is_active ? 'Xác nhận khóa' : 'Xác nhận mở'} />
  </>;
}

function Filter({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[][] }) {
  return <label className='text-sm font-medium'>{label}<select className='field mt-1.5' value={value} onChange={(event) => onChange(event.target.value)}>{options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></label>;
}
