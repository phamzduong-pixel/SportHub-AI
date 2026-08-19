import { AlertCircle, ChevronDown, ChevronUp, MessageSquare, Trash2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  EmptyState,
  LoadingSkeleton,
  Modal,
  PageHeader,
  useToast,
} from "@/components/common";
import { type BookingComplaint, cancelComplaint, getMyComplaints } from "@/services/customerApi";

const statusLabel: Record<string, string> = {
  open: "Chờ xử lý",
  in_review: "Đang xử lý",
  resolved: "Đã giải quyết",
  rejected: "Bị từ chối",
  cancelled: "Đã hủy",
};

export function CustomerComplaintsPage() {
  const { toast } = useToast();
  const [complaints, setComplaints] = useState<BookingComplaint[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number>();
  const [expanded, setExpanded] = useState<number>();
  const [cancelTarget, setCancelTarget] = useState<BookingComplaint>();

  const load = () =>
    getMyComplaints()
      .then(setComplaints)
      .catch((e) =>
        toast(e instanceof Error ? e.message : "Không tải được khiếu nại.", "error"),
      )
      .finally(() => setLoading(false));

  useEffect(() => {
    void load();
  }, []);

  const handleCancel = async () => {
    if (!cancelTarget || busy === cancelTarget.id) return;
    setBusy(cancelTarget.id);
    try {
      const updated = await cancelComplaint(cancelTarget.id);
      setComplaints((current) =>
        current.map((c) => (c.id === updated.id ? updated : c)),
      );
      toast("Đã hủy khiếu nại.", "success");
      setCancelTarget(undefined);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Không thể hủy khiếu nại.", "error");
    } finally {
      setBusy(undefined);
    }
  };

  return (
    <>
      <PageHeader
        title="Khiếu nại của tôi"
        description="Lịch sử các yêu cầu hỗ trợ và khiếu nại đã gửi đến chủ cơ sở."
      />

      {loading ? (
        <LoadingSkeleton lines={5} />
      ) : complaints.length ? (
        <div className="space-y-4">
          {complaints.map((item) => (
            <div key={item.id} className="rounded-card border bg-white p-4 sm:p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-slate-900">
                      Mã khiếu nại: #{item.id}
                    </h3>
                    <Badge
                      variant={
                        item.status === "resolved"
                          ? "success"
                          : item.status === "rejected"
                            ? "danger"
                            : item.status === "cancelled"
                              ? "neutral"
                              : "warning"
                      }
                    >
                      {statusLabel[item.status]}
                    </Badge>
                  </div>
                  <p className="mt-1 text-sm text-slate-600">
                    Gửi ngày {new Date(item.created_at).toLocaleDateString("vi-VN")}
                  </p>
                </div>
                {item.status === "open" && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full sm:w-auto"
                    leftIcon={<Trash2 size={16} />}
                    onClick={() => setCancelTarget(item)}
                  >
                    Hủy khiếu nại
                  </Button>
                )}
              </div>

              <div className="mt-4 grid gap-3 rounded-xl bg-slate-50 p-4 text-sm sm:grid-cols-2">
                <div>
                  <span className="block text-slate-500">Booking liên quan</span>
                  <Link
                    to={`/customer/bookings/${item.booking_id}`}
                    className="font-semibold text-brand-700 hover:underline"
                  >
                    {item.booking_code}
                  </Link>
                </div>
                <div>
                  <span className="block text-slate-500">Cơ sở / Sân</span>
                  <span className="font-semibold">{item.field_name}</span>
                </div>
                <div>
                  <span className="block text-slate-500">Loại khiếu nại</span>
                  <span className="font-semibold capitalize">{item.category}</span>
                </div>
              </div>

              <div className="mt-4">
                <button
                  type="button"
                  className="flex w-full items-center justify-between font-semibold text-slate-700 hover:text-brand-700"
                  onClick={() => setExpanded(expanded === item.id ? undefined : item.id)}
                >
                  <span>Chi tiết nội dung</span>
                  {expanded === item.id ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </button>
                {expanded === item.id && (
                  <div className="mt-3 space-y-4 rounded-xl border border-slate-100 p-4">
                    <div>
                      <span className="mb-1 block text-sm font-semibold text-slate-700">
                        Nội dung đã gửi:
                      </span>
                      <p className="whitespace-pre-wrap text-sm text-slate-600">
                        {item.description}
                      </p>
                      {item.evidence_url && (
                        <a
                          href={item.evidence_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-2 inline-flex items-center gap-1.5 text-sm text-brand-700 hover:underline"
                        >
                          Xem bằng chứng đính kèm
                        </a>
                      )}
                    </div>
                    {item.resolution && (
                      <div className="rounded-xl bg-brand-50 p-4">
                        <span className="mb-1 flex items-center gap-2 text-sm font-semibold text-brand-800">
                          <MessageSquare size={16} /> Phản hồi từ chủ sân/Admin:
                        </span>
                        <p className="whitespace-pre-wrap text-sm text-brand-900">
                          {item.resolution}
                        </p>
                        {item.resolved_at && (
                          <small className="mt-2 block text-brand-700">
                            Lúc {new Date(item.resolved_at).toLocaleString("vi-VN")}
                          </small>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<AlertCircle className="mx-auto text-slate-400" size={48} />}
          title="Không có khiếu nại"
          description="Bạn chưa có khiếu nại nào được ghi nhận."
        />
      )}

      <Modal
        open={Boolean(cancelTarget)}
        onClose={() => !busy && setCancelTarget(undefined)}
        title="Hủy khiếu nại"
      >
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            Bạn có chắc chắn muốn hủy yêu cầu khiếu nại <b>#{cancelTarget?.id}</b>? 
            Hành động này không thể hoàn tác.
          </p>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              disabled={Boolean(busy)}
              onClick={() => setCancelTarget(undefined)}
            >
              Quay lại
            </Button>
            <Button
              variant="danger"
              loading={Boolean(busy)}
              leftIcon={<XCircle size={16} />}
              onClick={() => void handleCancel()}
            >
              Xác nhận hủy
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
