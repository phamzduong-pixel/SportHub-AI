import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ExternalLink,
} from "lucide-react";
import { useState } from "react";
import { Button, Input, useToast } from "@/components/common";
import {
  confirmRefundReceived,
  disputeRefund,
  markRefunded,
  type RefundRequest,
} from "@/services/customerApi";

const money = (value: number) =>
  `${Number(value || 0).toLocaleString("vi-VN")}đ`;
const labels: Record<string, string> = {
  refund_pending: "Chờ chủ sân hoàn tiền",
  refund_overdue: "Đã quá hạn hoàn tiền",
  refunded: "Chủ sân đã xác nhận hoàn tiền",
  disputed: "Đang xử lý khiếu nại",
};
const actionLabels: Record<string, string> = {
  owner_rejected_booking: "Chủ sân từ chối booking",
  owner_cancelled_booking: "Chủ sân hủy booking",
  customer_cancelled_booking: "Khách hàng hủy booking",
  refund_marked_paid: "Chủ sân xác nhận đã hoàn tiền",
  customer_confirmed_refund: "Khách xác nhận đã nhận tiền",
  refund_disputed: "Khách gửi khiếu nại",
};

export function RefundStatusPanel({
  initial,
  mode,
  onChanged,
}: {
  initial: RefundRequest;
  mode: "customer" | "owner";
  onChanged?: (item: RefundRequest) => void;
}) {
  const { toast } = useToast();
  const [item, setItem] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [reference, setReference] = useState("");
  const [evidence, setEvidence] = useState("");
  const [disputeReason, setDisputeReason] = useState("");
  const update = (next: RefundRequest) => {
    setItem(next);
    onChanged?.(next);
  };
  const submitPaid = async () => {
    if (reference.trim().length < 3)
      return toast("Vui lòng nhập mã giao dịch hoàn tiền.", "error");
    setBusy(true);
    try {
      update(await markRefunded(item.id, reference.trim(), evidence.trim()));
      toast("Đã ghi nhận hoàn tiền thành công.", "success");
    } catch (error) {
      toast(
        error instanceof Error
          ? error.message
          : "Không thể xác nhận hoàn tiền.",
        "error",
      );
    } finally {
      setBusy(false);
    }
  };
  const confirmReceived = async () => {
    setBusy(true);
    try {
      update(await confirmRefundReceived(item.id));
      toast("Cảm ơn bạn đã xác nhận nhận tiền.", "success");
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không thể xác nhận.",
        "error",
      );
    } finally {
      setBusy(false);
    }
  };
  const dispute = async () => {
    if (disputeReason.trim().length < 3)
      return toast("Vui lòng mô tả lý do khiếu nại.", "error");
    setBusy(true);
    try {
      update(await disputeRefund(item.id, disputeReason.trim()));
      toast("Đã gửi khiếu nại đến chủ sân.", "success");
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không thể gửi khiếu nại.",
        "error",
      );
    } finally {
      setBusy(false);
    }
  };
  const urgent = item.status === "refund_overdue" || item.status === "disputed";
  return (
    <section
      className={`mt-5 rounded-card border p-5 ${urgent ? "border-red-200 bg-red-50" : "border-emerald-200 bg-emerald-50/50"}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-bold">
            {urgent ? (
              <AlertTriangle size={19} className="text-red-600" />
            ) : item.status === "refunded" ? (
              <CheckCircle2 size={19} className="text-emerald-600" />
            ) : (
              <Clock3 size={19} className="text-amber-600" />
            )}
            Hoàn tiền {item.booking_code}
          </h2>
          <p className="mt-1 text-sm font-semibold">{labels[item.status]}</p>
        </div>
        <b className="text-lg text-brand-700">{money(item.amount)}</b>
      </div>
      <div className="mt-4 grid gap-2 text-sm md:grid-cols-2">
        <p>
          <b>Lý do:</b> {item.reason}
        </p>
        <p>
          <b>Tạo yêu cầu:</b>{" "}
          {new Date(item.requested_at).toLocaleString("vi-VN")}
        </p>
        <p>
          <b>Hạn hoàn:</b> {new Date(item.due_at).toLocaleString("vi-VN")}
        </p>
        <p>
          <b>Người tạo:</b> {item.requested_by_name}
        </p>
        {item.refunded_at && (
          <p>
            <b>Hoàn lúc:</b>{" "}
            {new Date(item.refunded_at).toLocaleString("vi-VN")}
          </p>
        )}
        {item.processed_by_name && (
          <p>
            <b>Người xác nhận:</b> {item.processed_by_name}
          </p>
        )}
        {item.transaction_reference && (
          <p>
            <b>Mã giao dịch:</b> {item.transaction_reference}
          </p>
        )}
        {item.evidence_url && (
          <a
            className="flex items-center gap-1 font-semibold text-brand-700"
            href={item.evidence_url}
            target="_blank"
            rel="noreferrer"
          >
            Xem bằng chứng <ExternalLink size={14} />
          </a>
        )}
        {item.dispute_reason && (
          <p className="md:col-span-2">
            <b>Nội dung khiếu nại:</b> {item.dispute_reason}
          </p>
        )}
      </div>
      {mode === "owner" &&
        ["refund_pending", "refund_overdue"].includes(item.status) && (
          <div className="mt-5 grid gap-3 rounded-xl bg-white p-4 md:grid-cols-2">
            <Input
              label="Mã giao dịch hoàn tiền *"
              value={reference}
              onChange={(event) => setReference(event.target.value)}
              placeholder="VD: FT260809001"
            />
            <Input
              label="Đường dẫn bằng chứng (không bắt buộc)"
              value={evidence}
              onChange={(event) => setEvidence(event.target.value)}
              placeholder="https://..."
            />
            <Button loading={busy} onClick={() => void submitPaid()}>
              Xác nhận đã hoàn tiền
            </Button>
          </div>
        )}
      {mode === "customer" &&
        !item.customer_confirmed_at &&
        ["refund_pending", "refund_overdue", "refunded"].includes(
          item.status,
        ) && (
          <div className="mt-5 rounded-xl bg-white p-4">
            <div className="flex flex-wrap gap-2">
              {item.status === "refunded" && (
                <Button loading={busy} onClick={() => void confirmReceived()}>
                  Tôi đã nhận được tiền
                </Button>
              )}
            </div>
            <div className="mt-3 flex flex-col gap-2 sm:flex-row">
              <Input
                className="min-w-72"
                value={disputeReason}
                onChange={(event) => setDisputeReason(event.target.value)}
                placeholder="Chưa nhận tiền hoặc thông tin không đúng..."
              />
              <Button
                variant="danger"
                loading={busy}
                onClick={() => void dispute()}
              >
                Gửi khiếu nại
              </Button>
            </div>
          </div>
        )}
      <details className="mt-5">
        <summary className="cursor-pointer text-sm font-bold">
          Lịch sử thao tác ({item.activities.length})
        </summary>
        <div className="mt-3 space-y-2">
          {item.activities.map((activity) => (
            <div
              key={activity.id}
              className="border-l-2 border-slate-300 pl-3 text-sm"
            >
              <b>{actionLabels[activity.action] || activity.action}</b>
              <p className="text-slate-600">
                {activity.actor_name || "Hệ thống"} ·{" "}
                {new Date(activity.created_at).toLocaleString("vi-VN")}
              </p>
            </div>
          ))}
        </div>
      </details>
    </section>
  );
}
