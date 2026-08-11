import { useEffect, useState } from 'react';
import { EmptyState, LoadingSkeleton, PageHeader, useToast } from '@/components/common';
import { ComplaintPanel } from '@/components/management/ComplaintPanel';
import { getManagedComplaints, type BookingComplaint } from '@/services/customerApi';

export function ManagementComplaintsPage() {
  const { toast } = useToast(); const [items, setItems] = useState<BookingComplaint[]>([]); const [loading, setLoading] = useState(true);
  useEffect(() => { getManagedComplaints().then(setItems).catch((error) => toast(error instanceof Error ? error.message : 'Không tải được khiếu nại.', 'error')).finally(() => setLoading(false)); }, []);
  return <><PageHeader title="Khiếu nại booking" description="Tiếp nhận, phản hồi và lưu lịch sử xử lý vấn đề của khách hàng." />{loading ? <LoadingSkeleton lines={7} /> : items.length ? items.map((item) => <ComplaintPanel key={`${item.id}:${item.updated_at}`} initial={item} />) : <EmptyState title="Không có khiếu nại" description="Các báo cáo booking của khách hàng sẽ xuất hiện tại đây." />}</>;
}
