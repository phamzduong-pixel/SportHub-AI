import { Printer } from "lucide-react";
import { Button } from "@/components/common";
import type { DepositReceiptData } from "@/services/customerApi";

interface Props {
  receipt: DepositReceiptData;
  showPrintButton?: boolean;
}

const money = (value: number) => `${value.toLocaleString("vi-VN")}đ`;

const methodLabel: Record<string, string> = {
  bank_transfer: "Chuyển khoản ngân hàng",
  cash: "Tiền mặt",
  mock_online: "Thanh toán trực tuyến",
};

export function DepositReceipt({ receipt, showPrintButton = true }: Props) {
  return (
    <>
      <article className="deposit-receipt-print" aria-label="Biên lai đặt cọc">
        <div className="receipt-brand">SportHub AI</div>
        <h2>BIÊN LAI ĐẶT CỌC</h2>
        <p className="receipt-number">
          Mã biên lai: <b>{receipt.receipt_number}</b>
        </p>

        <div
          className={`receipt-status receipt-status--${receipt.deposit_status}`}
        >
          {receipt.status_message}
        </div>

        <section className="receipt-section">
          <h3>Thông tin đặt sân</h3>
          <div className="receipt-grid">
            <ReceiptItem label="Mã booking" value={receipt.booking_code} />
            <ReceiptItem label="Khách hàng" value={receipt.customer_name} />
            <ReceiptItem label="Cơ sở" value={receipt.facility_name} />
            <ReceiptItem
              label="Sân / môn thể thao"
              value={`${receipt.field_name} · ${receipt.sport_type}`}
            />
            <ReceiptItem
              label="Địa chỉ"
              value={receipt.facility_address}
              wide
            />
            <ReceiptItem
              label="Ngày đặt"
              value={new Date(
                `${receipt.booking_date}T00:00:00`,
              ).toLocaleDateString("vi-VN")}
            />
            <ReceiptItem
              label="Khung giờ"
              value={`${receipt.selected_slots.length} khung · ${receipt.duration_minutes} phút`}
            />
          </div>
          {receipt.selected_slots.length > 0 && (
            <div className="mt-3 text-sm">
              {receipt.selected_slots.map((slot) => (
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
        </section>

        {receipt.product_items.length > 0 && (
          <section className="receipt-section">
            <h3>Sản phẩm & dịch vụ</h3>
            <div className="mt-2 overflow-x-auto text-sm">
              <div className="grid min-w-[520px] grid-cols-[1fr_70px_110px_120px] gap-2 border-b pb-2 text-xs font-semibold text-slate-500">
                <span>Tên</span><span>SL</span><span>Đơn giá</span><span className="text-right">Thành tiền</span>
              </div>
              {receipt.product_items.map((item) => (
                <div
                  key={item.product_id}
                  className="grid min-w-[520px] grid-cols-[1fr_70px_110px_120px] gap-2 border-b py-2"
                >
                  <span>{item.name}</span>
                  <span>{item.quantity} {item.unit}</span>
                  <span>{money(item.unit_price)}</span>
                  <b className="text-right">{money(item.subtotal)}</b>
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="receipt-section receipt-payment">
          <h3>Chi tiết thanh toán</h3>
          <ReceiptMoney label="Tiền sân" value={receipt.court_amount} />
          <ReceiptMoney label="Dịch vụ thêm" value={receipt.service_amount} />
          <ReceiptMoney
            label="Tổng cộng"
            value={receipt.total_amount}
            strong
          />
          <ReceiptMoney
            label="Tiền cọc đã thanh toán"
            value={receipt.deposit_paid}
          />
          <ReceiptMoney
            label="Số tiền còn lại"
            value={receipt.remaining_amount}
          />
          {receipt.refund_status === "refunded" && (
            <ReceiptMoney
              label="Tiền đã hoàn"
              value={receipt.refund_amount || receipt.deposit_paid}
            />
          )}
        </section>

        <section className="receipt-section">
          <h3>Thông tin giao dịch</h3>
          <div className="receipt-grid">
            <ReceiptItem
              label="Mã giao dịch"
              value={receipt.transaction_code}
            />
            <ReceiptItem
              label="Phương thức"
              value={
                methodLabel[receipt.payment_method] || receipt.payment_method
              }
            />
            <ReceiptItem
              label="Ngân hàng"
              value={receipt.bank_name || "Không áp dụng"}
            />
            <ReceiptItem
              label="Thời gian thanh toán"
              value={new Date(receipt.paid_at).toLocaleString("vi-VN")}
            />
            <ReceiptItem
              label="Trạng thái đặt cọc"
              value={receipt.status_message}
              wide
            />
            {receipt.refunded_at && (
              <ReceiptItem
                label="Thời gian hoàn tiền"
                value={new Date(receipt.refunded_at).toLocaleString("vi-VN")}
                wide
              />
            )}
          </div>
        </section>

        <footer className="receipt-footer">
          <p>Biên lai được tạo từ dữ liệu giao dịch của SportHub AI.</p>
          <p>Vui lòng giữ biên lai này để đối chiếu khi cần hỗ trợ.</p>
        </footer>
      </article>
      {showPrintButton && (
        <Button
          className="receipt-print-button print:hidden"
          variant="outline"
          leftIcon={<Printer size={16} />}
          onClick={() => window.print()}
        >
          In biên lai
        </Button>
      )}
    </>
  );
}

function ReceiptItem({
  label,
  value,
  wide = false,
}: {
  label: string;
  value: string;
  wide?: boolean;
}) {
  return (
    <div className={wide ? "receipt-item receipt-item--wide" : "receipt-item"}>
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}

function ReceiptMoney({
  label,
  value,
  strong = false,
}: {
  label: string;
  value: number;
  strong?: boolean;
}) {
  return (
    <div
      className={
        strong ? "receipt-money receipt-money--strong" : "receipt-money"
      }
    >
      <span>{label}</span>
      <b>{money(value)}</b>
    </div>
  );
}
