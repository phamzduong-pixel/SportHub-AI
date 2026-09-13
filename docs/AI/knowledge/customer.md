# Customer Knowledge

---

| ID | Topic | Role | Intent | Question | Answer | Source | Classification |
|----|-------|------|--------|----------|--------|--------|----------------|
| CUST-001 | SportHub Overview | Customer | SYSTEM_GUIDE | SportHub là gì? | SportHub là nền tảng đặt sân thể thao trực tuyến, cho phép người dùng tìm kiếm, đặt và quản lý các sân thể thao một cách nhanh chóng. | `ai_intent_router.py` (SYSTEM_GUIDE) | static |
| CUST-002 | Đăng ký tài khoản | Customer | ACCOUNT_SUPPORT | Làm thế nào để đăng ký tài khoản? | Người dùng có thể đăng ký tài khoản bằng cách nhấn nút “Đăng ký” trên giao diện, nhập email, mật khẩu và thông tin cá nhân, sau đó xác nhận qua email. | `ai_intent_router.py` (ACCOUNT_SUPPORT) | static |
| CUST-003 | Đăng nhập | Customer | ACCOUNT_SUPPORT | Làm thế nào để đăng nhập? | Đăng nhập bằng cách nhập email và mật khẩu đã đăng ký trên trang đăng nhập, hoặc sử dụng đăng nhập qua Google/Facebook nếu được bật. | `ai_intent_router.py` (ACCOUNT_SUPPORT) | static |
| CUST-004 | Tìm sân | Customer | SEARCH_VENUE | Làm thế nào để tìm sân? | Người dùng có thể nhập loại thể thao và địa điểm vào ô tìm kiếm, hệ thống sẽ trả về danh sách các sân phù hợp cùng thông tin chi tiết. | `ai_intent_router.py` (SEARCH_VENUE) | static |
| CUST-005 | Đặt sân | Customer | CREATE_BOOKING | Làm thế nào để đặt sân? | Chọn sân mong muốn, chọn ngày và khung giờ, sau đó xác nhận đặt sân và thanh toán. | `ai_intent_router.py` (CREATE_BOOKING) | static |
| CUST-006 | Xem booking | Customer | GET_BOOKING | Làm thế nào để xem booking? | Người dùng vào mục “Đặt sân của tôi” để xem danh sách các đặt sân hiện tại và lịch sử. | `ai_intent_router.py` (GET_BOOKING) | static |
| CUST-007 | Hủy booking | Customer | CANCEL_BOOKING | Làm thế nào để hủy booking? | Trong danh sách đặt sân, nhấn nút “Hủy” bên cạnh booking muốn hủy, xác nhận hủy. | `ai_intent_router.py` (CANCEL_BOOKING) | static |
| CUST-008 | Đổi lịch booking | Customer | RESCHEDULE_BOOKING | Làm thế nào để đổi lịch booking? | Vào chi tiết booking, chọn “Đổi lịch”, chọn ngày/giờ mới và xác nhận. | `ai_intent_router.py` (RESCHEDULE_BOOKING) | static |
| CUST-009 | Thanh toán | Customer | PAYMENT_SUPPORT | Thanh toán đặt sân hoạt động như thế nào? | Hệ thống hỗ trợ thanh toán qua thẻ ngân hàng, ví điện tử hoặc chuyển khoản. Người dùng chọn phương thức, nhập thông tin và xác nhận. | `ai_intent_router.py` (PAYMENT_SUPPORT) | static |
| CUST-010 | Đăng ký làm chủ sân | Customer | SYSTEM_GUIDE | Làm thế nào để đăng ký làm chủ sân? | Người dùng nhấn “Đăng ký làm chủ” trên trang, cung cấp thông tin sân, giấy tờ pháp lý và chờ duyệt. | `ai_intent_router.py` (SYSTEM_GUIDE) | static |

---
