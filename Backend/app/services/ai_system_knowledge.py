"""Static system knowledge base for SportHub AI.

Provides deterministic, grounded answers to general and workflow-oriented questions
without calling an LLM, preventing hallucinations, and ensuring strict role safety.
"""

from dataclasses import dataclass
from typing import Any
import re
import unicodedata


def _plain(text: str) -> str:
    text = re.sub(r'[^\w\s]', ' ', text)
    normalized = unicodedata.normalize('NFD', text.casefold())
    return ' '.join(''.join(c for c in normalized if unicodedata.category(c) != 'Mn').replace('đ', 'd').split())


@dataclass(frozen=True)
class KnowledgeEntry:
    key: str
    category: str
    patterns: tuple[str, ...]
    answer: str
    allowed_roles: tuple[str, ...] | None = None
    role_restricted_message: str | None = None
    suggested_action: dict[str, Any] | None = None


KNOWLEDGE_ENTRIES: list[KnowledgeEntry] = [
    # ----------------------------------------------------
    # 1. GENERAL SYSTEM & PLATFORM
    # ----------------------------------------------------
    KnowledgeEntry(
        key="sporthub_overview",
        category="GENERAL",
        patterns=(
            "sporthub la gi", "he thong sporthub", "gioi thieu sporthub",
            "sporthub ai la gi", "nen tang sporthub", "sporthub la nen tang gi",
        ),
        answer=(
            "SportHub AI là nền tảng quản lý và đặt sân thể thao thông minh, kết nối trực tiếp khách hàng có nhu cầu "
            "với các chủ sân/cơ sở thể thao (bóng đá, cầu lông, pickleball, tennis,...). Hệ thống cung cấp khả năng tìm kiếm "
            "sân theo vị trí và khung giờ thực tế, đặt sân giữ chỗ chống trùng lịch, thanh toán tiện lợi và hỗ trợ quản trị vận hành."
        ),
    ),
    KnowledgeEntry(
        key="sporthub_features",
        category="GENERAL",
        patterns=(
            "sporthub co nhung chuc nang gi", "chuc nang cua sporthub", "sporthub lam duoc gi",
            "sporthub co tinh nang gi", "tinh nang cua sporthub", "he thong co chuc nang gi",
        ),
        answer=(
            "SportHub AI cung cấp các nhóm chức năng chính:\n"
            "1. Dành cho Khách hàng (CUSTOMER): Tìm kiếm sân theo môn/khu vực, kiểm tra lịch trống thực tế, đặt sân giữ slot, "
            "thanh toán cọc/toàn phần, quản lý booking (xem/đổi lịch/hủy booking), đánh giá sân và mua dịch vụ/phụ kiện đi kèm.\n"
            "2. Dành cho Đối tác/Chủ sân (OWNER): Đăng ký hồ sơ đối tác, tạo và quản lý cơ sở thể thao/sân con, cấu hình khung giờ "
            "và bảng giá, quản lý sản phẩm/dịch vụ phụ trợ, quản lý lịch đặt sân và xem báo cáo doanh thu/công suất vận hành.\n"
            "3. Dành cho Quản trị viên (SYSTEM_ADMIN): Phê duyệt hồ sơ đăng ký chủ sân, kiểm duyệt cơ sở thể thao, quản lý tài khoản "
            "toàn hệ thống và giám sát toàn bộ hoạt động của nền tảng.\n"
            "4. Trợ lý SportHub AI: Tra cứu sân trống, hỗ trợ hỏi đáp quy trình và tư vấn thông tin theo dữ liệu thời gian thực."
        ),
    ),
    KnowledgeEntry(
        key="user_roles",
        category="GENERAL",
        patterns=(
            "he thong co nhung vai tro nao", "cac vai tro trong sporthub", "vai tro nguoi dung",
            "phan quyen tai khoan", "co may loai tai khoan", "cac loai tai khoan",
        ),
        answer=(
            "Hệ thống SportHub AI phân chia người dùng thành 3 vai trò (Role) rõ ràng:\n"
            "• CUSTOMER (Khách hàng): Đăng ký tự do, tìm sân, đặt lịch, thanh toán và quản lý đơn đặt của bản thân.\n"
            "• OWNER (Chủ sân / Đối tác): Cần gửi hồ sơ đối tác và được duyệt bởi Quản trị viên; có quyền quản trị cơ sở, sân, khung giờ, bảng giá và doanh thu của mình.\n"
            "• SYSTEM_ADMIN (Quản trị viên nền tảng): Quản lý người dùng, xét duyệt hồ sơ chủ sân OWNER và phê duyệt cơ sở thể thao trước khi hiển thị công khai."
        ),
    ),

    # ----------------------------------------------------
    # 2. CUSTOMER GUIDE
    # ----------------------------------------------------
    KnowledgeEntry(
        key="customer_register",
        category="CUSTOMER",
        patterns=(
            "lam the nao de dang ky tai khoan", "cach dang ky tai khoan", "huong dan dang ky",
            "dang ky tai khoan nhu the nao", "tao tai khoan moi", "dang ky sporthub",
        ),
        answer=(
            "Cách đăng ký tài khoản SportHub AI:\n"
            "1. Nhấn nút 'Đăng ký' ở góc trên bên phải màn hình (hoặc truy cập trang /register).\n"
            "2. Điền đầy đủ thông tin: Họ và tên, Email, Số điện thoại và Mật khẩu.\n"
            "3. Xác nhận mật khẩu và nhấn 'Đăng ký'. Sau khi tạo tài khoản thành công, bạn có thể đăng nhập ngay bằng email và mật khẩu vừa tạo."
        ),
        suggested_action={"label": "Đăng ký tài khoản", "route": "/register", "kind": "link"},
    ),
    KnowledgeEntry(
        key="customer_login",
        category="CUSTOMER",
        patterns=(
            "lam the nao de dang nhap", "cach dang nhap", "huong dan dang nhap",
            "dang nhap nhu the nao", "dang nhap vao he thong",
        ),
        answer=(
            "Cách đăng nhập vào SportHub AI:\n"
            "1. Nhấn vào nút 'Đăng nhập' trên thanh điều hướng (hoặc truy cập trang /login).\n"
            "2. Nhập Email và Mật khẩu tài khoản của bạn.\n"
            "3. Nhấn 'Đăng nhập'. Hệ thống sẽ tự động điều hướng bạn về trang chủ hoặc khu vực quản trị tương ứng với vai trò của bạn."
        ),
        suggested_action={"label": "Đăng nhập", "route": "/login", "kind": "link"},
    ),
    KnowledgeEntry(
        key="customer_search_fields",
        category="CUSTOMER",
        patterns=(
            "lam the nao de tim san", "cach tim san", "huong dan tim san",
            "tim san nhu the nao", "cach kiem tra san trong",
        ),
        answer=(
            "Cách tìm sân và kiểm tra lịch trống trên SportHub AI:\n"
            "1. Tại trang chủ hoặc mục 'Tìm sân', chọn môn thể thao (Bóng đá, Cầu lông, Pickleball, Tennis...).\n"
            "2. Nhập khu vực/quận huyện mong muốn hoặc chọn ngày và khung giờ dự kiến chơi.\n"
            "3. Hệ thống sẽ hiển thị danh sách các sân phù hợp cùng khoảng giá và trạng thái còn trống thực tế.\n"
            "4. Bạn cũng có thể yêu cầu trực tiếp với Trợ lý AI (ví dụ: 'Tìm sân cầu lông tại Cầu Giấy tối mai lúc 19h')."
        ),
        suggested_action={"label": "Tìm kiếm sân", "route": "/venues", "kind": "link"},
    ),
    KnowledgeEntry(
        key="customer_book_field",
        category="CUSTOMER",
        patterns=(
            "lam the nao de dat san", "cach dat san", "huong dan dat san",
            "quy trinh dat san", "dat san nhu the nao", "cac buoc dat san",
        ),
        answer=(
            "Quy trình đặt sân trên SportHub AI:\n"
            "1. Chọn cơ sở và sân thể thao bạn muốn đặt.\n"
            "2. Chọn ngày chơi và tick chọn một hoặc nhiều khung giờ (time slots) còn trống.\n"
            "3. (Tùy chọn) Chọn thêm nước uống, thuê bóng, thuê vợt hoặc phụ kiện đi kèm.\n"
            "4. Kiểm tra tổng số tiền, mức cọc yêu cầu và chính sách hủy/hoàn tiền được snapshot.\n"
            "5. Nhấn xác nhận để tạo booking và thực hiện thanh toán theo thời hạn giữ chỗ (hold window) của hệ thống."
        ),
    ),
    KnowledgeEntry(
        key="customer_payment_workflow",
        category="CUSTOMER",
        patterns=(
            "thanh toan dat san hoat dong nhu the nao", "cach thanh toan dat san", "quy trinh thanh toan",
            "thanh toan nhu the nao", "dat coc nhu the nao", "hinh thuc thanh toan",
        ),
        answer=(
            "Cơ chế thanh toán đặt sân tại SportHub AI:\n"
            "• Khi tạo booking, hệ thống sẽ tạm giữ khung giờ (hold) trong thời gian quy định để bạn thực hiện thanh toán.\n"
            "• Bạn có thể chọn thanh toán tiền cọc (deposit) theo tỷ lệ cơ sở quy định hoặc thanh toán toàn bộ 100%.\n"
            "• Sau khi thanh toán thành công, trạng thái booking sẽ chuyển sang CONFIRMED và khung giờ được khóa chính thức trên hệ thống.\n"
            "• Nếu quá hạn thanh toán mà chưa hoàn tất, đơn sẽ tự động bị hủy và khung giờ được nhả lại cho người khác."
        ),
    ),
    KnowledgeEntry(
        key="customer_view_bookings",
        category="CUSTOMER",
        patterns=(
            "lam the nao de xem booking", "cach xem booking", "xem lich dat cua toi o dau",
            "kiem tra booking cua toi", "lich su dat san o dau", "xem danh sach booking",
        ),
        answer=(
            "Cách xem danh sách và chi tiết booking của bạn:\n"
            "1. Đăng nhập vào tài khoản SportHub AI của bạn.\n"
            "2. Vào mục 'Lịch đặt của tôi' trên menu tài khoản (hoặc truy cập /my-bookings).\n"
            "3. Tại đây hiển thị toàn bộ booking cùng trạng thái (PENDING, CONFIRMED, COMPLETED, CANCELLED).\n"
            "4. Nhấn vào từng mã booking để xem chi tiết giờ chơi, số tiền đã trả, mã QR và thao tác đổi lịch hoặc hủy."
        ),
        suggested_action={"label": "Lịch đặt của tôi", "route": "/my-bookings", "kind": "link"},
    ),
    KnowledgeEntry(
        key="customer_cancel_booking_guide",
        category="CUSTOMER",
        patterns=(
            "lam the nao de huy booking", "cach huy booking", "huong dan huy booking",
            "huy booking nhu the nao", "quy trinh huy booking", "lam sao de huy san",
        ),
        answer=(
            "Hướng dẫn hủy booking:\n"
            "1. Truy cập mục 'Lịch đặt của tôi' (/my-bookings) và chọn booking bạn muốn hủy.\n"
            "2. Kiểm tra chính sách hoàn tiền tại thời điểm hiện tại (dựa trên mốc hủy miễn phí trước giờ chơi snapshot của sân).\n"
            "3. Nhấn 'Hủy booking' và xác nhận lý do.\n"
            "4. Nếu đủ điều kiện hoàn tiền theo chính sách, hệ thống sẽ tạo yêu cầu hoàn cọc tương ứng. Lưu ý: Trợ lý AI không tự động hủy booking giúp bạn mà bạn cần thao tác trực tiếp trên giao diện để xác nhận."
        ),
    ),
    KnowledgeEntry(
        key="customer_reschedule_booking_guide",
        category="CUSTOMER",
        patterns=(
            "lam the nao de doi lich", "cach doi lich booking", "huong dan doi lich",
            "doi gio dat san nhu the nao", "lam sao de doi gio", "doi lich nhu the nao",
        ),
        answer=(
            "Hướng dẫn đổi lịch đặt sân:\n"
            "1. Mở trang chi tiết booking cần dời lịch trong mục 'Lịch đặt của tôi' (/my-bookings).\n"
            "2. Nhấn nút 'Đổi lịch' (Dời lịch).\n"
            "3. Chọn ngày chơi mới và khung giờ mới còn trống tại cơ sở đó.\n"
            "4. Kiểm tra chênh lệch giá (nếu có) và xác nhận. Lưu ý: Thao tác đổi lịch phải được người dùng tự xác nhận trên hệ thống, Trợ lý AI không tự thay đổi lịch trực tiếp."
        ),
    ),
    KnowledgeEntry(
        key="customer_review_field",
        category="CUSTOMER",
        patterns=(
            "lam the nao de danh gia san", "cach danh gia san", "huong dan danh gia san",
            "danh gia san o dau", "viet review san",
        ),
        answer=(
            "Cách đánh giá sân:\n"
            "1. Sau khi hoàn thành buổi chơi (booking chuyển trạng thái COMPLETED), bạn vào chi tiết booking hoặc trang thông tin của sân đó.\n"
            "2. Chọn mục 'Đánh giá' hoặc 'Viết nhận xét'.\n"
            "3. Chấm điểm số sao (1 đến 5 sao) và để lại phản hồi về chất lượng mặt sân, tiện ích, dịch vụ.\n"
            "4. Nhấn 'Gửi đánh giá' để chia sẻ trải nghiệm với cộng đồng."
        ),
    ),
    KnowledgeEntry(
        key="customer_profile_edit",
        category="CUSTOMER",
        patterns=(
            "lam the nao de sua thong tin ca nhan", "cach doi thong tin ca nhan", "chinh sua ho so",
            "doi so dien thoai", "doi ten tai khoan", "sua ho so o dau",
        ),
        answer=(
            "Cách chỉnh sửa thông tin cá nhân:\n"
            "1. Nhấn vào biểu tượng tài khoản ở góc trên bên phải và chọn 'Hồ sơ cá nhân' (hoặc truy cập /profile).\n"
            "2. Tại đây bạn có thể cập nhật Họ và tên, Số điện thoại và ảnh đại diện.\n"
            "3. Nhấn 'Lưu thay đổi' để hoàn tất cập nhật."
        ),
        suggested_action={"label": "Hồ sơ cá nhân", "route": "/profile", "kind": "link"},
    ),

    # ----------------------------------------------------
    # 3. OWNER / PARTNER GUIDE
    # ----------------------------------------------------
    KnowledgeEntry(
        key="owner_apply",
        category="OWNER",
        patterns=(
            "lam the nao de dang ky lam chu san", "cach dang ky lam chu san", "lam sao de tro thanh chu san",
            "huong dan dang ky chu san", "dang ky lam doi tac", "quy trinh dang ky owner",
        ),
        answer=(
            "Quy trình đăng ký trở thành chủ sân (OWNER):\n"
            "1. Đăng nhập vào tài khoản SportHub AI (vai trò CUSTOMER).\n"
            "2. Truy cập trang 'Đăng ký đối tác' (/owner-application).\n"
            "3. Điền thông tin người đại diện (họ tên, email, số điện thoại) và thông tin cơ sở thể thao dự kiến (tên cơ sở, địa chỉ, môn thể thao, mô tả sơ bộ).\n"
            "4. Gửi hồ sơ. Hồ sơ sẽ ở trạng thái PENDING chờ Quản trị viên SYSTEM_ADMIN xét duyệt. Sau khi được duyệt, tài khoản của bạn sẽ tự động nâng cấp lên quyền OWNER."
        ),
        suggested_action={"label": "Đăng ký trở thành chủ sân", "route": "/owner-application", "kind": "link"},
    ),
    KnowledgeEntry(
        key="owner_requirements",
        category="OWNER",
        patterns=(
            "dieu kien dang ky chu san", "yeu cau dang ky owner", "can gi de dang ky lam chu san",
            "ho so chu san can nhung gi", "giay to dang ky chu san",
        ),
        answer=(
            "Điều kiện và yêu cầu khi đăng ký đối tác chủ sân:\n"
            "• Bước gửi hồ sơ ban đầu (/owner-application) chỉ yêu cầu thông tin người đại diện hợp lệ (Họ tên, SĐT, Email) và thông tin dự kiến về cơ sở thể thao.\n"
            "• Hệ thống chưa yêu cầu tải lên ngay giấy phép kinh doanh tại bước xin cấp quyền OWNER.\n"
            "• Sau khi tài khoản được nâng cấp thành OWNER, khi tạo cơ sở thể thao chính thức, bạn sẽ cần cung cấp hình ảnh thực tế, tiện ích và xác thực địa chỉ để được SYSTEM_ADMIN duyệt hiển thị."
        ),
    ),
    KnowledgeEntry(
        key="owner_view_status",
        category="OWNER",
        patterns=(
            "xem trang thai ho so chu san o dau", "kiem tra ho so doi tac o dau", "trang thai ho so owner",
            "xem ket qua duyet ho so",
        ),
        answer=(
            "Cách kiểm tra trạng thái hồ sơ đối tác chủ sân:\n"
            "• Bạn truy cập trang /owner-application/status để xem trạng thái hiện tại (PENDING, APPROVED, hoặc REJECTED).\n"
            "• Ngoài ra bạn có thể hỏi trực tiếp Trợ lý SportHub AI (ví dụ: 'Trạng thái hồ sơ đối tác của tôi thế nào?') khi đã đăng nhập."
        ),
        suggested_action={"label": "Xem trạng thái hồ sơ", "route": "/owner-application/status", "kind": "link"},
    ),
    KnowledgeEntry(
        key="owner_rejection_and_reapply",
        category="OWNER",
        patterns=(
            "ho so bi tu choi thi sao", "ho so chu san bi tu choi", "lam sao de gui lai ho so",
            "bi tu choi co duoc nop lai khong", "nop lai ho so chu san",
        ),
        answer=(
            "Xử lý khi hồ sơ đối tác bị từ chối (REJECTED):\n"
            "• Bạn có thể vào trang /owner-application/status để xem lý do từ chối cụ thể do Quản trị viên (SYSTEM_ADMIN) ghi chú.\n"
            "• Bạn hoàn toàn ĐƯỢC PHÉP chỉnh sửa và cập nhật lại thông tin tại trang /owner-application rồi gửi lại để được xét duyệt lại."
        ),
        suggested_action={"label": "Cập nhật và gửi lại hồ sơ", "route": "/owner-application", "kind": "link"},
    ),
    KnowledgeEntry(
        key="owner_management_overview",
        category="OWNER",
        patterns=(
            "chu san duoc quan ly nhung gi", "owner quan ly nhung gi", "quyen han cua chu san",
            "tinh nang cho chu san", "khu vuc quan ly owner co gi",
        ),
        answer=(
            "Chủ sân (OWNER) có quyền quản trị toàn diện các hoạt động vận hành của cơ sở mình:\n"
            "1. Quản lý cơ sở & sân: Thêm mới cơ sở, tạo các sân con (sân 5, sân 7, sân đơn, đôi), cập nhật tiện ích.\n"
            "2. Quản lý khung giờ & giá: Tạo các khung giờ linh hoạt theo ngày thường/cuối tuần, thiết lập giá giờ vàng/giờ thấp điểm.\n"
            "3. Quản lý dịch vụ/sản phẩm: Bán nước giải khát, cho thuê vợt/bóng/áo pitch và kiểm soát số lượng tồn kho.\n"
            "4. Quản lý đơn đặt: Theo dõi danh sách booking, xác nhận check-in của khách, xử lý đổi/hủy.\n"
            "5. Báo cáo & Phân tích: Xem biểu đồ doanh thu theo ngày/tháng và tỷ lệ lấp đầy công suất sân."
        ),
        allowed_roles=("OWNER", "SYSTEM_ADMIN"),
        role_restricted_message=(
            "Tính năng quản lý dành riêng cho tài khoản Chủ sân (OWNER). Tài khoản hiện tại là Khách hàng (CUSTOMER). "
            "Nếu bạn sở hữu sân thể thao, bạn có thể đăng ký nâng cấp tài khoản tại /owner-application."
        ),
    ),
    KnowledgeEntry(
        key="owner_add_field",
        category="OWNER",
        patterns=(
            "chu san them san moi nhu the nao", "cach tao san moi", "lam sao de them san",
            "huong dan them san", "them co so the thao", "tao co so the thao moi",
        ),
        answer=(
            "Cách thêm cơ sở và sân mới dành cho Chủ sân (OWNER):\n"
            "1. Đăng nhập bằng tài khoản OWNER và vào mục 'Quản lý cơ sở' (/management/facilities).\n"
            "2. Nhấn nút 'Thêm cơ sở mới', điền tên cơ sở, địa chỉ chi tiết, hotline và chọn môn thể thao.\n"
            "3. Thêm các sân con thuộc cơ sở (ví dụ: Sân 1, Sân 2), chọn loại sân (trong nhà, ngoài trời, kích thước).\n"
            "4. Gửi yêu cầu phê duyệt cơ sở để Quản trị viên (SYSTEM_ADMIN) duyệt trước khi mở bán công khai."
        ),
        allowed_roles=("OWNER", "SYSTEM_ADMIN"),
        role_restricted_message=(
            "Chức năng tạo và quản lý sân chỉ dành cho tài khoản Chủ sân (OWNER). "
            "Bạn có thể đăng ký tài khoản OWNER tại mục 'Đăng ký đối tác' (/owner-application)."
        ),
    ),
    KnowledgeEntry(
        key="owner_manage_slots_and_pricing",
        category="OWNER",
        patterns=(
            "chu san quan ly khung gio nhu the nao", "cach cai dat khung gio", "cach tao slot",
            "thiet lap gia san", "cai dat gia gio vang", "quan ly bang gia nhu the nao",
        ),
        answer=(
            "Cách quản lý khung giờ và bảng giá dành cho OWNER:\n"
            "1. Vào phần 'Quản lý khung giờ' (/management/time-slots) trong khu vực chủ sân.\n"
            "2. Chọn sân con cần cấu hình, tạo các khung giờ (ví dụ: 06:00–07:00, 17:00–18:30,...).\n"
            "3. Thiết lập mức giá niêm yết cho từng khung giờ; có thể phân biệt giá ngày thường (Thứ 2 - Thứ 6) và cuối tuần (Thứ 7, CN) hoặc khung giờ cao điểm (giờ vàng).\n"
            "4. Bật hoặc tắt trạng thái hoạt động của khung giờ theo lịch thực tế."
        ),
        allowed_roles=("OWNER", "SYSTEM_ADMIN"),
        role_restricted_message=(
            "Chức năng cấu hình khung giờ và giá chỉ áp dụng cho tài khoản OWNER đang quản lý cơ sở thể thao."
        ),
    ),
    KnowledgeEntry(
        key="owner_manage_products",
        category="OWNER",
        patterns=(
            "chu san quan ly san pham dich vu nhu the nao", "them nuoc uong dich vu", "quan ly thue vot bong",
            "them san pham phu tro", "quan ly dich vu them",
        ),
        answer=(
            "Cách quản lý sản phẩm và dịch vụ phụ trợ (Nước uống, thuê vợt, bóng,...):\n"
            "1. Tại khu vực quản trị OWNER, truy cập mục 'Quản lý dịch vụ/sản phẩm' (/management/inventory hoặc /management/products).\n"
            "2. Nhấn 'Thêm sản phẩm', nhập tên sản phẩm (ví dụ: Nước suối, Nước điện giải, Thuê vợt cầu lông Yonex).\n"
            "3. Nhập đơn giá bán/cho thuê và số lượng tồn kho khả dụng.\n"
            "4. Khách hàng khi đặt sân có thể chọn thêm các sản phẩm này trực tiếp vào đơn đặt."
        ),
        allowed_roles=("OWNER", "SYSTEM_ADMIN"),
        role_restricted_message=(
            "Tính năng quản lý sản phẩm và dịch vụ phụ trợ chỉ dành cho tài khoản Chủ sân (OWNER)."
        ),
    ),
    KnowledgeEntry(
        key="owner_view_bookings_and_revenue",
        category="OWNER",
        patterns=(
            "chu san xem booking va doanh thu o dau", "xem doanh thu chu san", "xem danh sach dat san cua owner",
            "bao cao doanh thu o dau", "theo doi lich dat cua san",
        ),
        answer=(
            "Cách theo dõi booking và doanh thu của chủ sân:\n"
            "1. Truy cập 'Bảng điều khiển' (/management/dashboard) để xem tổng quan doanh thu, số lượt booking trong ngày/tháng.\n"
            "2. Truy cập 'Quản lý đặt sân' (/management/bookings) để xem danh sách khách đặt, trạng thái thanh toán và xác nhận check-in.\n"
            "3. Truy cập 'Báo cáo & Thống kê' (/management/analytics) để phân tích tỷ lệ lấp đầy khung giờ."
        ),
        allowed_roles=("OWNER", "SYSTEM_ADMIN"),
        role_restricted_message=(
            "Báo cáo vận hành và doanh thu thuộc về khu vực quản trị của Chủ sân (OWNER). Tài khoản Khách hàng không có quyền truy cập."
        ),
    ),

    # ----------------------------------------------------
    # 4. SYSTEM_ADMIN GUIDE
    # ----------------------------------------------------
    KnowledgeEntry(
        key="admin_user_management",
        category="ADMIN",
        patterns=(
            "admin quan ly nguoi dung nhu the nao", "cach quan ly tai khoan toan he thong",
            "quan tri vien quan ly nguoi dung", "chuc nang quan ly tai khoan cua admin",
        ),
        answer=(
            "Chức năng quản lý người dùng của SYSTEM_ADMIN:\n"
            "1. Quản trị viên truy cập khu vực Quản trị hệ thống tại /admin/users.\n"
            "2. Xem danh sách toàn bộ tài khoản CUSTOMER, OWNER và SYSTEM_ADMIN trên nền tảng.\n"
            "3. Tìm kiếm theo tên, email, số điện thoại hoặc lọc theo vai trò.\n"
            "4. Khóa/mở khóa hoặc kích hoạt/vô hiệu hóa tài khoản khi có vi phạm chính sách của nền tảng."
        ),
        allowed_roles=("SYSTEM_ADMIN",),
        role_restricted_message=(
            "Chức năng quản lý người dùng toàn hệ thống là quyền hạn riêng biệt của Quản trị viên (SYSTEM_ADMIN)."
        ),
    ),
    KnowledgeEntry(
        key="admin_approve_owner",
        category="ADMIN",
        patterns=(
            "admin duyet ho so chu san nhu the nao", "cach duyet ho so doi tac",
            "quy trinh duyet owner cua admin", "duyet don dang ky chu san",
        ),
        answer=(
            "Quy trình xét duyệt hồ sơ chủ sân của SYSTEM_ADMIN:\n"
            "1. Quản trị viên vào mục 'Duyệt hồ sơ đối tác' tại /admin/owner-applications.\n"
            "2. Kiểm tra danh sách hồ sơ ở trạng thái PENDING.\n"
            "3. Mở chi tiết hồ sơ để thẩm định thông tin người đại diện và mô tả cơ sở thể thao.\n"
            "4. Đưa ra quyết định: Phê duyệt (APPROVED - hệ thống tự đổi quyền tài khoản sang OWNER) hoặc Từ chối (REJECTED - bắt buộc nhập lý do để phản hồi lại người nộp)."
        ),
        allowed_roles=("SYSTEM_ADMIN",),
        role_restricted_message=(
            "Chức năng xét duyệt hồ sơ đối tác thuộc quyền hạn của Quản trị viên (SYSTEM_ADMIN). AI hoặc người dùng thông thường không thể tự duyệt hồ sơ."
        ),
    ),
    KnowledgeEntry(
        key="admin_approve_facility",
        category="ADMIN",
        patterns=(
            "admin duyet co so the thao nhu the nao", "cach duyet san the thao cua admin",
            "phe duyet co so", "kiem duyet san cua chu san",
        ),
        answer=(
            "Quy trình kiểm duyệt cơ sở thể thao của SYSTEM_ADMIN:\n"
            "1. Quản trị viên vào mục 'Kiểm duyệt cơ sở' tại /admin/facilities.\n"
            "2. Xem xét thông tin cơ sở do chủ sân OWNER tạo mới (địa chỉ, hình ảnh thực tế, môn thể thao, danh sách sân con).\n"
            "3. Phê duyệt (APPROVED) để cơ sở xuất hiện trên bản đồ tìm kiếm của khách hàng hoặc Từ chối (REJECTED) kèm ghi chú yêu cầu bổ sung."
        ),
        allowed_roles=("SYSTEM_ADMIN",),
        role_restricted_message=(
            "Chức năng kiểm duyệt và phê duyệt cơ sở thể thao là thẩm quyền độc quyền của Quản trị viên (SYSTEM_ADMIN)."
        ),
    ),

    # ----------------------------------------------------
    # 5. UNKNOWN POLICIES & BOUNDARIES (Anti-Hallucination)
    # ----------------------------------------------------
    KnowledgeEntry(
        key="policy_approval_sla",
        category="POLICY",
        patterns=(
            "bao lau thi duyet ho so", "thoi gian duyet ho so la bao lau", "may ngay thi duyet chu san",
            "thoi gian duyet co so la bao lau", "khi nao ho so duoc duyet",
        ),
        answer=(
            "Thời gian xét duyệt hồ sơ đối tác và cơ sở thể thao phụ thuộc vào tiến độ kiểm tra thực tế của ban quản trị "
            "SYSTEM_ADMIN. Hiện hệ thống SportHub AI chưa quy định cam kết thời gian duyệt cố định (SLA). "
            "Bạn có thể theo dõi tiến độ trực tiếp tại trang /owner-application/status."
        ),
    ),
    KnowledgeEntry(
        key="policy_owner_fee",
        category="POLICY",
        patterns=(
            "phi dang ky chu san la bao nhieu", "co mat phi duy tri khong", "dang ky owner co mat tien khong",
            "phi hoa hong cua chu san", "chi phi tro thanh chu san",
        ),
        answer=(
            "Hiện tại việc đăng ký tài khoản và nộp hồ sơ đối tác chủ sân trên SportHub AI là hoàn toàn miễn phí. "
            "Các chính sách liên quan đến phí duy trì hoặc biểu phí giao dịch (nếu áp dụng trong tương lai) "
            "hiện hệ thống chưa xác định rõ thông tin này và sẽ có thông báo chính thức từ ban quản trị."
        ),
    ),
]


def match_system_knowledge(query: str, current_role: str | None = None) -> tuple[KnowledgeEntry | None, str | None, dict[str, Any] | None]:
    """Matches a user query against static system knowledge entries.

    Returns:
        (entry, reply_message, action_dict)
        If no entry matches, returns (None, None, None).
    """
    clean = _plain(query)

    # Dynamic data guards: Queries containing specific dates, times, court codes, prices,
    # or private tokens should NOT be intercepted by general knowledge.
    dynamic_guards = (
        "sh-", "sh -", "thang nay", "hom nay", "ngay mai",
        "con san", "con gio", "con trong", "con slot", "luc nao con",
        "gia bao nhieu", "co dat hon", "re hon", "dat hon",
    )
    # If the query contains explicit dynamic markers and isn't asking about how a feature works
    if any(guard in clean for guard in dynamic_guards) and not any(
        term in clean for term in ("la gi", "nhu the nao", "huong dan", "cach", "quy trinh", "co nhung chuc nang", "lam the nao")
    ):
        return None, None, None

    for entry in KNOWLEDGE_ENTRIES:
        for pattern in entry.patterns:
            pattern_clean = _plain(pattern)
            if pattern_clean in clean:
                # Check role restrictions
                if entry.allowed_roles and current_role not in entry.allowed_roles:
                    reply = entry.role_restricted_message or "Bạn không có quyền truy cập hoặc thực hiện chức năng này."
                    return entry, reply, None
                return entry, entry.answer, entry.suggested_action

    return None, None, None
