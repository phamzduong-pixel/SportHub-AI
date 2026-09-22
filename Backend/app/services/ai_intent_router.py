import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any

from .location_utils import extract_location


class AssistantIntent(str, Enum):
    SEARCH_VENUE = 'SEARCH_VENUE'
    RECOMMEND_VENUE = 'RECOMMEND_VENUE'
    CHECK_AVAILABILITY = 'CHECK_AVAILABILITY'
    RECOMMEND_SLOT = 'RECOMMEND_SLOT'
    OCCUPANCY_INSIGHT = 'OCCUPANCY_INSIGHT'
    PARTNER_APPLICATION_SUPPORT = 'PARTNER_APPLICATION_SUPPORT'
    GET_VENUE_DETAIL = 'GET_VENUE_DETAIL'
    GET_PRODUCTS = 'GET_PRODUCTS'
    CREATE_BOOKING = 'CREATE_BOOKING'
    GET_BOOKING = 'GET_BOOKING'
    CANCEL_BOOKING = 'CANCEL_BOOKING'
    RESCHEDULE_BOOKING = 'RESCHEDULE_BOOKING'
    PAYMENT_SUPPORT = 'PAYMENT_SUPPORT'
    ACCOUNT_SUPPORT = 'ACCOUNT_SUPPORT'
    SYSTEM_GUIDE = 'SYSTEM_GUIDE'
    GREETING = 'GREETING'
    FOLLOW_UP = 'FOLLOW_UP'
    UNCLEAR = 'UNCLEAR'
    OUT_OF_SCOPE = 'OUT_OF_SCOPE'
    SPORTS_KNOWLEDGE = 'SPORTS_KNOWLEDGE'
    AI_IDENTITY = 'AI_IDENTITY'
    AI_CAPABILITY = 'AI_CAPABILITY'
    THANKS = 'THANKS'
    GOODBYE = 'GOODBYE'
    CASUAL = 'CASUAL'
    ABUSIVE = 'ABUSIVE'
    NONSENSE = 'NONSENSE'


SPORT_ALIASES = {
    'bong da': 'bóng đá', 'da bong': 'bóng đá', 'san bong': 'bóng đá', 'football': 'bóng đá', 'soccer': 'bóng đá',
    'cau long': 'cầu lông', 'badminton': 'cầu lông', 'danh cau long': 'cầu lông', 'choi cau long': 'cầu lông',
    'pickleball': 'pickleball', 'pickle ball': 'pickleball', 'danh pickleball': 'pickleball', 'choi pickleball': 'pickleball',
    'tennis': 'tennis', 'quan vot': 'tennis', 'danh tennis': 'tennis', 'choi tennis': 'tennis',
    'bong ro': 'bóng rổ', 'choi bong ro': 'bóng rổ', 'basketball': 'bóng rổ',
    'bong chuyen': 'bóng chuyền', 'choi bong chuyen': 'bóng chuyền', 'volleyball': 'bóng chuyền',
}
SUPPORTED_SPORTS = {'bóng đá', 'cầu lông', 'pickleball', 'tennis', 'bóng rổ', 'bóng chuyền'}

BUSINESS_INTENTS = {
    AssistantIntent.SEARCH_VENUE,
    AssistantIntent.RECOMMEND_VENUE,
    AssistantIntent.CHECK_AVAILABILITY,
    AssistantIntent.RECOMMEND_SLOT,
    AssistantIntent.GET_VENUE_DETAIL,
    AssistantIntent.CREATE_BOOKING,
    AssistantIntent.GET_BOOKING,
    AssistantIntent.CANCEL_BOOKING,
    AssistantIntent.RESCHEDULE_BOOKING,
    AssistantIntent.PAYMENT_SUPPORT,
    AssistantIntent.ACCOUNT_SUPPORT,
    AssistantIntent.PARTNER_APPLICATION_SUPPORT,
    AssistantIntent.OCCUPANCY_INSIGHT,
    AssistantIntent.GET_PRODUCTS,
    AssistantIntent.SYSTEM_GUIDE,
}


def is_business_intent(intent: AssistantIntent | None) -> bool:
    return intent in BUSINESS_INTENTS


def is_supported_sport(sport: str | None) -> bool:
    if not sport:
        return False
    norm = normalize_text(sport)
    resolved = SPORT_ALIASES.get(norm, norm)
    return resolved in SUPPORTED_SPORTS or any(
        norm == s or norm in s or s in norm
        for s in ('bong da', 'cau long', 'pickleball', 'tennis', 'bong ro', 'bong chuyen', 'football', 'soccer', 'badminton', 'basketball', 'volleyball', 'quan vot')
    )


UNSUPPORTED_SPORTS_TERMS = (
    'golf', 'bong chay', 'baseball', 'boi loi', 'boi', 'dua xe', 'f1', 'formula 1',
    'bi a', 'bi-a', 'billiards', 'bida', 'vo thuat', 'boxing', 'mma', 'bong ban', 'table tennis',
    'dien kinh', 'cu ta', 'co vua', 'co tuong', 'dua thuyen', 'cheo thuyen', 'rugby', 'bong bau duc',
    'faker', 't1', 'chovy', 'valorant', 'esport', 'esports', 'e-sport', 'e-sports', 'lien minh',
    'lien minh huyen thoai', 'lol', 'csgo', 'cs:go', 'cs2', 'dota', 'dota 2', 'pubg', 'free fire',
    'lien quan', 'arena of valor',
)

KNOWN_SPORTS_ENTITIES = {
    # 1. Thái Nguyên Scope (Bóng đá, Cầu lông, Pickleball, Tennis, Bóng rổ, Bóng chuyền)
    'thai nguyen t&t': ('bóng đá', 'Thái Nguyên T&T'),
    'thai nguyen tt': ('bóng đá', 'Thái Nguyên T&T'),
    'clb nu thai nguyen': ('bóng đá', 'Thái Nguyên T&T'),
    'doi nu thai nguyen': ('bóng đá', 'Thái Nguyên T&T'),
    'bong da nu thai nguyen': ('bóng đá', 'Thái Nguyên T&T'),
    'doi bong nu thai nguyen': ('bóng đá', 'Thái Nguyên T&T'),
    'doi bong da nu thai nguyen': ('bóng đá', 'Thái Nguyên T&T'),
    'clb bong da nu thai nguyen': ('bóng đá', 'Thái Nguyên T&T'),

    'bong da nam thai nguyen': ('bóng đá', 'Bóng đá nam Thái Nguyên'),
    'doi bong nam thai nguyen': ('bóng đá', 'Bóng đá nam Thái Nguyên'),
    'doi bong da nam thai nguyen': ('bóng đá', 'Bóng đá nam Thái Nguyên'),
    'doi nam thai nguyen': ('bóng đá', 'Bóng đá nam Thái Nguyên'),
    'clb bong da nam thai nguyen': ('bóng đá', 'Bóng đá nam Thái Nguyên'),
    'cau lac bo bong da nam thai nguyen': ('bóng đá', 'Bóng đá nam Thái Nguyên'),
    'fc thai nguyen': ('bóng đá', 'Bóng đá nam Thái Nguyên'),

    'bong da thai nguyen': ('bóng đá', 'Bóng đá Thái Nguyên'),
    'doi thai nguyen': ('bóng đá', 'Bóng đá Thái Nguyên'),
    'doi bong thai nguyen': ('bóng đá', 'Bóng đá Thái Nguyên'),
    'clb bong da thai nguyen': ('bóng đá', 'Bóng đá Thái Nguyên'),
    'cau lac bo bong da thai nguyen': ('bóng đá', 'Bóng đá Thái Nguyên'),
    'clb thai nguyen': ('bóng đá', 'Bóng đá Thái Nguyên'),
    'cau lac bo thai nguyen': ('bóng đá', 'Bóng đá Thái Nguyên'),
    'san van dong thai nguyen': ('bóng đá', 'Sân vận động Thái Nguyên'),
    'svd thai nguyen': ('bóng đá', 'Sân vận động Thái Nguyên'),
    'clb cau long thai nguyen': ('cầu lông', 'CLB Cầu lông Thái Nguyên'),
    'phong trao cau long thai nguyen': ('cầu lông', 'Cầu lông Thái Nguyên'),
    'cau long thai nguyen': ('cầu lông', 'Cầu lông Thái Nguyên'),
    'clb pickleball thai nguyen': ('pickleball', 'CLB Pickleball Thái Nguyên'),
    'pickleball thai nguyen': ('pickleball', 'Pickleball Thái Nguyên'),
    'clb tennis thai nguyen': ('tennis', 'CLB Tennis Thái Nguyên'),
    'tennis thai nguyen': ('tennis', 'Tennis Thái Nguyên'),
    'clb bong ro thai nguyen': ('bóng rổ', 'CLB Bóng rổ Thái Nguyên'),
    'bong ro thai nguyen': ('bóng rổ', 'Bóng rổ Thái Nguyên'),
    'clb bong chuyen thai nguyen': ('bóng chuyền', 'CLB Bóng chuyền Thái Nguyên'),
    'bong chuyen thai nguyen': ('bóng chuyền', 'Bóng chuyền Thái Nguyên'),

    # ICTU (Trường Đại học CNTT & TT Thái Nguyên)
    'truong dai hoc cong nghe thong tin va truyen thong': ('bóng đá', 'Bóng đá ICTU'),
    'dai hoc cong nghe thong tin va truyen thong': ('bóng đá', 'Bóng đá ICTU'),
    'truong cntt va truyen thong thai nguyen': ('bóng đá', 'Bóng đá ICTU'),
    'cntt va truyen thong thai nguyen': ('bóng đá', 'Bóng đá ICTU'),
    'truong dh cntt&tt': ('bóng đá', 'Bóng đá ICTU'),
    'truong dh cntt va tt': ('bóng đá', 'Bóng đá ICTU'),
    'dh cntt&tt thai nguyen': ('bóng đá', 'Bóng đá ICTU'),
    'dh cntt va tt thai nguyen': ('bóng đá', 'Bóng đá ICTU'),
    'dh cntt&tt': ('bóng đá', 'Bóng đá ICTU'),
    'dh cntt va tt': ('bóng đá', 'Bóng đá ICTU'),
    'doi tuyen bong da nam sinh vien ictu': ('bóng đá', 'Bóng đá ICTU'),
    'doi bong sinh vien ictu': ('bóng đá', 'Bóng đá ICTU'),
    'bong da sinh vien ictu': ('bóng đá', 'Bóng đá ICTU'),
    'doi bong ictu': ('bóng đá', 'Bóng đá ICTU'),
    'bong da ictu': ('bóng đá', 'Bóng đá ICTU'),
    'giai bong da sinh vien ictu cup': ('bóng đá', 'ICTU CUP'),
    'ictu cup': ('bóng đá', 'ICTU CUP'),
    'doi bong khoa cntt ictu': ('bóng đá', 'Khoa CNTT ICTU'),
    'bong da khoa cntt ictu': ('bóng đá', 'Khoa CNTT ICTU'),
    'khoa cntt ictu': ('bóng đá', 'Khoa CNTT ICTU'),
    'khoa ky thuat va cong nghe ictu': ('bóng đá', 'Khoa Kỹ thuật và Công nghệ ICTU'),
    'fit ictu': ('bóng đá', 'Khoa CNTT ICTU'),
    'fet ictu': ('bóng đá', 'Khoa Kỹ thuật và Công nghệ ICTU'),
    'ictu': (None, 'ICTU'),
    'truong ictu': (None, 'ICTU'),
    'doi bong ictu': ('bóng đá', 'Bóng đá ICTU'),
    'doi bong sinh vien thai nguyen': ('bóng đá', 'Bóng đá ICTU'),
    'doi bong sinh vien o thai nguyen': ('bóng đá', 'Bóng đá ICTU'),
    'bong da sinh vien thai nguyen': ('bóng đá', 'Bóng đá ICTU'),
    'bong da sinh vien o thai nguyen': ('bóng đá', 'Bóng đá ICTU'),
    'cac doi bong sinh vien thai nguyen': ('bóng đá', 'Bóng đá ICTU'),
    'cac doi bong sinh vien o thai nguyen': ('bóng đá', 'Bóng đá ICTU'),

    # ICTU Multi-sports
    'cau long ictu': ('cầu lông', 'Cầu lông ICTU'),
    'clb cau long ictu': ('cầu lông', 'Cầu lông ICTU'),
    'phong trao cau long ictu': ('cầu lông', 'Cầu lông ICTU'),
    'cau long truong cntt thai nguyen': ('cầu lông', 'Cầu lông ICTU'),
    'cau long truong dh cntt&tt': ('cầu lông', 'Cầu lông ICTU'),
    'cau long truong dh cntt va tt': ('cầu lông', 'Cầu lông ICTU'),

    'bong chuyen ictu': ('bóng chuyền', 'Bóng chuyền ICTU'),
    'bong chuyen hoi ictu': ('bóng chuyền', 'Bóng chuyền ICTU'),
    'doi bong chuyen ictu': ('bóng chuyền', 'Bóng chuyền ICTU'),
    'clb bong chuyen ictu': ('bóng chuyền', 'Bóng chuyền ICTU'),
    'phong trao bong chuyen ictu': ('bóng chuyền', 'Bóng chuyền ICTU'),
    'bong chuyen truong cntt thai nguyen': ('bóng chuyền', 'Bóng chuyền ICTU'),
    'bong chuyen truong cntt va truyen thong': ('bóng chuyền', 'Bóng chuyền ICTU'),
    'bong chuyen truong dh cntt&tt': ('bóng chuyền', 'Bóng chuyền ICTU'),

    'bong ban ictu': ('bóng bàn', 'Bóng bàn ICTU'),
    'clb bong ban ictu': ('bóng bàn', 'Bóng bàn ICTU'),
    'phong trao bong ban ictu': ('bóng bàn', 'Bóng bàn ICTU'),
    'bong ban truong cntt thai nguyen': ('bóng bàn', 'Bóng bàn ICTU'),
    'bong ban truong dh cntt&tt': ('bóng bàn', 'Bóng bàn ICTU'),

    'pickleball ictu': ('pickleball', 'Pickleball ICTU'),
    'pickle ball ictu': ('pickleball', 'Pickleball ICTU'),
    'clb pickleball ictu': ('pickleball', 'Pickleball ICTU'),
    'san pickleball ictu': ('pickleball', 'Pickleball ICTU'),
    'pickleball truong cntt thai nguyen': ('pickleball', 'Pickleball ICTU'),
    'pickleball truong dh cntt&tt': ('pickleball', 'Pickleball ICTU'),

    'the thao ictu': (None, 'Thể thao ICTU'),
    'phong trao the thao ictu': (None, 'Thể thao ICTU'),
    'clb the thao ictu': (None, 'Thể thao ICTU'),
    'clb the thao o ictu': (None, 'Thể thao ICTU'),
    'cac mon the thao ictu': (None, 'Thể thao ICTU'),
    'mon the thao ictu': (None, 'Thể thao ICTU'),
    'the thao truong cntt thai nguyen': (None, 'Thể thao ICTU'),
    'the thao truong dh cntt&tt': (None, 'Thể thao ICTU'),
    'the thao truong dai hoc cong nghe thong tin va truyen thong': (None, 'Thể thao ICTU'),
    'the thao thai nguyen': (None, 'Thể thao Thái Nguyên'),
    'phong trao the thao thai nguyen': (None, 'Thể thao Thái Nguyên'),
    'cac mon the thao thai nguyen': (None, 'Thể thao Thái Nguyên'),
    'cac doi the thao thai nguyen': (None, 'Thể thao Thái Nguyên'),

    # 2. Hà Nội Scope
    'ha noi fc': ('bóng đá', 'Hà Nội FC'),
    'clb ha noi': ('bóng đá', 'Hà Nội FC'),
    'the cong viettel': ('bóng đá', 'Thể Công Viettel'),
    'viettel fc': ('bóng đá', 'Thể Công Viettel'),
    'clb the cong': ('bóng đá', 'Thể Công Viettel'),
    'cong an ha noi': ('bóng đá', 'Công an Hà Nội'),
    'clb cong an ha noi': ('bóng đá', 'Công an Hà Nội'),
    'cahn': ('bóng đá', 'Công an Hà Nội'),
    'hanoi buffaloes': ('bóng rổ', 'Hanoi Buffaloes'),
    'thang long warriors': ('bóng rổ', 'Thang Long Warriors'),
    'bong da ha noi': ('bóng đá', 'Bóng đá Hà Nội'),
    'clb bong da ha noi': ('bóng đá', 'Bóng đá Hà Nội'),
    'doi bong da ha noi': ('bóng đá', 'Bóng đá Hà Nội'),
    'doi bong ha noi': ('bóng đá', 'Bóng đá Hà Nội'),
    'bong ro ha noi': ('bóng rổ', 'Bóng rổ Hà Nội'),
    'clb bong ro ha noi': ('bóng rổ', 'Bóng rổ Hà Nội'),
    'bong chuyen ha noi': ('bóng chuyền', 'Bóng chuyền Hà Nội'),
    'doi bong chuyen ha noi': ('bóng chuyền', 'Bóng chuyền Hà Nội'),
    'cau long ha noi': ('cầu lông', 'Cầu lông Hà Nội'),
    'clb cau long ha noi': ('cầu lông', 'Cầu lông Hà Nội'),
    'dien kinh ha noi': ('điền kinh', 'Điền kinh Hà Nội'),
    'vo thuat ha noi': ('võ thuật', 'Võ thuật Hà Nội'),
    'the thao ha noi': (None, 'Thể thao Hà Nội'),
    'phong trao the thao ha noi': (None, 'Thể thao Hà Nội'),
    'the thao thu do': (None, 'Thể thao Hà Nội'),
    'the thao dai hoc ha noi': (None, 'Thể thao Đại học Hà Nội'),
    'the thao sinh vien ha noi': (None, 'Thể thao Đại học Hà Nội'),
    'cac truong dai hoc ha noi': (None, 'Thể thao Đại học Hà Nội'),

    # 3. TP. Hồ Chí Minh Scope
    'clb tp.hcm': ('bóng đá', 'Bóng đá TP.HCM'),
    'clb tphcm': ('bóng đá', 'Bóng đá TP.HCM'),
    'clb bong da tp.hcm': ('bóng đá', 'Bóng đá TP.HCM'),
    'clb bong da tphcm': ('bóng đá', 'Bóng đá TP.HCM'),
    'clb bong da thanh pho ho chi minh': ('bóng đá', 'Bóng đá TP.HCM'),
    'clb nu tp.hcm': ('bóng đá', 'Bóng đá TP.HCM'),
    'clb nu tphcm': ('bóng đá', 'Bóng đá TP.HCM'),
    'bong da tp.hcm': ('bóng đá', 'Bóng đá TP.HCM'),
    'bong da tphcm': ('bóng đá', 'Bóng đá TP.HCM'),
    'bong da sai gon': ('bóng đá', 'Bóng đá TP.HCM'),
    'saigon heat': ('bóng rổ', 'Saigon Heat'),
    'ho chi minh city wings': ('bóng rổ', 'Ho Chi Minh City Wings'),
    'hcmc wings': ('bóng rổ', 'Ho Chi Minh City Wings'),
    'city wings': ('bóng rổ', 'Ho Chi Minh City Wings'),
    'bong ro tp.hcm': ('bóng rổ', 'Bóng rổ TP.HCM'),
    'bong ro tphcm': ('bóng rổ', 'Bóng rổ TP.HCM'),
    'bong ro sai gon': ('bóng rổ', 'Bóng rổ TP.HCM'),
    'clb bong ro tp.hcm': ('bóng rổ', 'Bóng rổ TP.HCM'),
    'clb bong ro tphcm': ('bóng rổ', 'Bóng rổ TP.HCM'),
    'cau long tp.hcm': ('cầu lông', 'Cầu lông TP.HCM'),
    'cau long tphcm': ('cầu lông', 'Cầu lông TP.HCM'),
    'clb cau long tp.hcm': ('cầu lông', 'Cầu lông TP.HCM'),
    'clb cau long tphcm': ('cầu lông', 'Cầu lông TP.HCM'),
    'bong ban tp.hcm': ('bóng bàn', 'Bóng bàn TP.HCM'),
    'bong ban tphcm': ('bóng bàn', 'Bóng bàn TP.HCM'),
    'bong chuyen tp.hcm': ('bóng chuyền', 'Bóng chuyền TP.HCM'),
    'bong chuyen tphcm': ('bóng chuyền', 'Bóng chuyền TP.HCM'),
    'maseco tp.hcm': ('bóng chuyền', 'Bóng chuyền TP.HCM'),
    'the thao tp.hcm': (None, 'Thể thao TP.HCM'),
    'the thao tphcm': (None, 'Thể thao TP.HCM'),
    'the thao sai gon': (None, 'Thể thao TP.HCM'),
    'the thao thanh pho ho chi minh': (None, 'Thể thao TP.HCM'),

    # 4. Việt Nam Scope
    'doi tuyen viet nam': ('bóng đá', 'Đội tuyển Việt Nam'),
    'tuyen viet nam': ('bóng đá', 'Đội tuyển Việt Nam'),
    'doi tuyen quoc gia': ('bóng đá', 'Đội tuyển Việt Nam'),
    'doi tuyen bong da nam': ('bóng đá', 'Đội tuyển bóng đá nam Việt Nam'),
    'doi tuyen bong da nu': ('bóng đá', 'Đội tuyển bóng đá nữ Việt Nam'),
    'quang hai': ('bóng đá', 'Nguyễn Quang Hải'),
    'nguyen quang hai': ('bóng đá', 'Nguyễn Quang Hải'),
    'hoang duc': ('bóng đá', 'Nguyễn Hoàng Đức'),
    'nguyen hoang duc': ('bóng đá', 'Nguyễn Hoàng Đức'),
    'cong phuong': ('bóng đá', 'Nguyễn Công Phượng'),
    'van lam': ('bóng đá', 'Đặng Văn Lâm'),
    'tien linh': ('bóng đá', 'Nguyễn Tiến Linh'),
    'nguyen tien linh': ('bóng đá', 'Nguyễn Tiến Linh'),
    'park hang-seo': ('bóng đá', 'Park Hang-seo'),
    'park hang seo': ('bóng đá', 'Park Hang-seo'),
    'v-league': ('bóng đá', 'V-League'),
    'vleague': ('bóng đá', 'V-League'),
    'giai bong da nu quoc gia': ('bóng đá', 'Giải Bóng đá Nữ Quốc gia'),
    'bong da nu quoc gia': ('bóng đá', 'Giải Bóng đá Nữ Quốc gia'),
    'giai bong da nu': ('bóng đá', 'Giải Bóng đá Nữ Quốc gia'),
    'thuy linh': ('cầu lông', 'Nguyễn Thùy Linh'),
    'nguyen thuy linh': ('cầu lông', 'Nguyễn Thùy Linh'),
    'tien minh': ('cầu lông', 'Nguyễn Tiến Minh'),
    'nguyen tien minh': ('cầu lông', 'Nguyễn Tiến Minh'),
    'le duc phat': ('cầu lông', 'Lê Đức Phát'),
    'doi tuyen cau long': ('cầu lông', 'Đội tuyển cầu lông Việt Nam'),
    'trinh linh giang': ('pickleball', 'Trịnh Linh Giang'),
    'doi tuyen pickleball viet nam': ('pickleball', 'Đội tuyển Pickleball Việt Nam'),
    'pickleball viet nam': ('pickleball', 'Pickleball Việt Nam'),
    'ly hoang nam': ('tennis', 'Lý Hoàng Nam'),
    'doi tuyen tennis viet nam': ('tennis', 'Đội tuyển Tennis Việt Nam'),
    'davis cup viet nam': ('tennis', 'Davis Cup Việt Nam'),
    'saigon heat': ('bóng rổ', 'Saigon Heat'),
    'thang long warriors': ('bóng rổ', 'Thang Long Warriors'),
    'hanoi buffaloes': ('bóng rổ', 'Hanoi Buffaloes'),
    'vba': ('bóng rổ', 'VBA'),
    'doi tuyen bong ro': ('bóng rổ', 'Đội tuyển bóng rổ Việt Nam'),
    'doi tuyen bong chuyen nu viet nam': ('bóng chuyền', 'Đội tuyển bóng chuyền nữ Việt Nam'),
    'doi tuyen bong chuyen nam viet nam': ('bóng chuyền', 'Đội tuyển bóng chuyền nam Việt Nam'),
    'doi tuyen bong chuyen nu': ('bóng chuyền', 'Đội tuyển bóng chuyền nữ Việt Nam'),
    'doi tuyen bong chuyen': ('bóng chuyền', 'Đội tuyển bóng chuyền Việt Nam'),
    'thanh thuy': ('bóng chuyền', 'Trần Thị Thanh Thúy'),
    'tran thi thanh thuy': ('bóng chuyền', 'Trần Thị Thanh Thúy'),
    'bich tuyen': ('bóng chuyền', 'Nguyễn Thị Bích Tuyền'),
    'nguyen thi bich tuyen': ('bóng chuyền', 'Nguyễn Thị Bích Tuyền'),
    'kieu trinh': ('bóng chuyền', 'Hoàng Thị Kiều Trinh'),
    'vtv cup': ('bóng chuyền', 'VTV Cup'),

    # 3. Quốc tế Scope
    'messi': ('bóng đá', 'Lionel Messi'),
    'lionel messi': ('bóng đá', 'Lionel Messi'),
    'leo messi': ('bóng đá', 'Lionel Messi'),
    'leo': ('bóng đá', 'Lionel Messi'),
    'la pulga': ('bóng đá', 'Lionel Messi'),
    'ronaldo': ('bóng đá', 'Cristiano Ronaldo'),
    'cristiano ronaldo': ('bóng đá', 'Cristiano Ronaldo'),
    'cristiano': ('bóng đá', 'Cristiano Ronaldo'),
    'cr7': ('bóng đá', 'Cristiano Ronaldo'),
    'c ronaldo': ('bóng đá', 'Cristiano Ronaldo'),
    'erling haaland': ('bóng đá', 'Erling Haaland'),
    'haaland': ('bóng đá', 'Erling Haaland'),
    'kylian mbappe': ('bóng đá', 'Kylian Mbappé'),
    'mbappe': ('bóng đá', 'Kylian Mbappé'),
    'neymar': ('bóng đá', 'Neymar'),
    'premier league': ('bóng đá', 'Premier League'),
    'ngoai hang anh': ('bóng đá', 'Ngoại Hạng Anh'),
    'champions league': ('bóng đá', 'UEFA Champions League'),
    'world cup': ('bóng đá', 'FIFA World Cup'),
    'inter miami': ('bóng đá', 'Lionel Messi'),
    'al-nassr': ('bóng đá', 'Cristiano Ronaldo'),
    'al nassr': ('bóng đá', 'Cristiano Ronaldo'),
    'axelsen': ('cầu lông', 'Viktor Axelsen'),
    'viktor axelsen': ('cầu lông', 'Viktor Axelsen'),
    'lin dan': ('cầu lông', 'Lin Dan'),
    'lee chong wei': ('cầu lông', 'Lee Chong Wei'),
    'kento momota': ('cầu lông', 'Kento Momota'),
    'an se young': ('cầu lông', 'An Se Young'),
    'bwf': ('cầu lông', 'BWF'),
    'ben johns': ('pickleball', 'Ben Johns'),
    'anna leigh waters': ('pickleball', 'Anna Leigh Waters'),
    'ppa tour': ('pickleball', 'PPA Tour'),
    'novak djokovic': ('tennis', 'Novak Djokovic'),
    'djokovic': ('tennis', 'Novak Djokovic'),
    'rafael nadal': ('tennis', 'Rafael Nadal'),
    'nadal': ('tennis', 'Rafael Nadal'),
    'roger federer': ('tennis', 'Roger Federer'),
    'federer': ('tennis', 'Roger Federer'),
    'carlos alcaraz': ('tennis', 'Carlos Alcaraz'),
    'alcaraz': ('tennis', 'Carlos Alcaraz'),
    'jannik sinner': ('tennis', 'Jannik Sinner'),
    'sinner': ('tennis', 'Jannik Sinner'),
    'wimbledon': ('tennis', 'Wimbledon'),
    'grand slam': ('tennis', 'Grand Slam'),
    'lebron james': ('bóng rổ', 'LeBron James'),
    'lebron': ('bóng rổ', 'LeBron James'),
    'stephen curry': ('bóng rổ', 'Stephen Curry'),
    'curry': ('bóng rổ', 'Stephen Curry'),
    'michael jordan': ('bóng rổ', 'Michael Jordan'),
    'kobe bryant': ('bóng rổ', 'Kobe Bryant'),
    'kobe': ('bóng rổ', 'Kobe Bryant'),
    'nba': ('bóng rổ', 'NBA'),
    'fivb': ('bóng chuyền', 'FIVB'),
}

WEEKDAYS = {
    'thu hai': 0, 'thu ba': 1, 'thu tu': 2, 'thu nam': 3,
    'thu sau': 4, 'thu bay': 5, 'chu nhat': 6,
}
ENTITY_KEYS = (
    'sport_type', 'court_type', 'venue_name', 'location', 'date', 'start_time', 'end_time',
    'preferred_time', 'max_price', 'booking_code', 'sports_entity',
)

OUT_OF_SCOPE_TERMS = (
    'python', 'lap trinh', 'viet code', 'sua code', 'toan hoc', 'giai toan', 'giai bai', 'bai toan',
    'lich su viet', 'chinh tri', 'suc khoe', 'benh', 'thuoc',
    'tai chinh', 'chung khoan', 'bitcoin', 'crypto', 'tien ao', 'phap luat', 'luat su',
    'viet bai', 'bai tho', 'viet cv', 'tao cv', 'dich thuat', 'dich sang', 'dich tieng anh', 'tieng anh',
    'thoi tiet', 'tin tuc', 'thit cho', 'mon an', 'nau an', 'cach nau', 'cong thuc', 'lam banh', 'an gi', 'uong gi',
    'phim', 'am nhac', 'du lich', 'chuyen cuoi', 'ke chuyen',
    'tu van tinh cam', 'tinh yeu', 'sua may tinh', 'cai win', 'sua xe', 'xe may', 'sua xe may', 'cach sua xe', 'sua o to', 'o to',
    'dich doan', 'dich cau', 'tuyen sinh', 'hoc phi', 'diem chuan', 'nganh hoc', 'nhap hoc', 'xet tuyen',
)
DOMAIN_TERMS = (
    'san', 'the thao', 'sporthub', 'co so', 'dia diem', 'tien ich', 'khung gio',
    'lich trong', 'booking', 'ma dat', 'dat lich', 'dat coc', 'thanh toan', 'hoan tien',
    'hoa don', 'bien lai', 'huy', 'doi lich', 'doi gio', 'tai khoan', 'ho so',
    'owner', 'chu san', 'doi tac', 'quan ly', 'gia', 'choi', 'cong suat', 'thap diem', 'cao diem', 'it khach', 'uu dai',
    'san pham', 'dich vu', 'cho thue', 'thue san', 'thue', 'con hang', 'so luong con', 'ton kho', 'tim', 'giup', 'tro ly', 'lap day',
    'admin', 'quan tri', 'phe duyet', 'xet duyet', 'tu choi', 'dang ky', 'dang nhap', 'mat khau', 'danh gia', 'review',
    'chuc nang', 'tinh nang', 'vai tro', 'customer', 'system_admin',
)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize('NFD', value.casefold())
    return ''.join(char for char in normalized if unicodedata.category(char) != 'Mn').replace('đ', 'd')


from .ai_sports_resolver import SportsContextResolver


@dataclass
class IntentEntities:
    sport_type: str | None = None
    court_type: str | None = None
    venue_name: str | None = None
    location: str | None = None
    date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    preferred_time: str | None = None
    max_price: float | None = None
    number_of_players: int | None = None
    booking_code: str | None = None
    sports_entity: str | None = None
    active_entity: str | None = None
    entity_type: str | None = None
    competition: str | None = None
    year: str | None = None
    recent_entities: list[str] = field(default_factory=list)
    current_topic: str | None = None
    target_trophy: str | None = None
    rewritten_query: str | None = None
    sports_entities: list[str] = field(default_factory=list)
    venue_names: list[str] = field(default_factory=list)
    sport_types: list[str] = field(default_factory=list)
    athlete: str | None = None
    team: str | None = None
    is_return_to_business: bool = False
    is_conditional: bool = False
    conditional_note: str | None = None
    is_meme_or_joke: bool = False
    explicit_entity_mention: bool = False

    @property
    def price_max(self) -> float | None:
        """Backward-compatible alias; new clients should use max_price."""
        return self.max_price


@dataclass
class IntentRoute:
    intent: AssistantIntent
    confidence: float
    entities: IntentEntities = field(default_factory=IntentEntities)
    needs_clarification: bool = False
    is_follow_up: bool = False
    context_reset: bool = False
    is_combined_out_of_scope: bool = False

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result['intent'] = self.intent.value
        result['entities']['price_max'] = result['entities']['max_price']
        return result


class IntentRouter:
    """Pure routing layer: it never reads SportHub repositories or mutates data."""
    @staticmethod
    def is_system_domain_followup(query: str, context: dict[str, Any] | None = None) -> bool:
        """Return whether a short query continues a System Domain conversation."""
        context = context or {}
        domain_kind = context.get('domain_context_type')
        if domain_kind not in {'sport_products', 'sport_amenities', 'venue_products', 'venue_amenities'}:
            return False

        normalized = normalize_text(query).strip().rstrip('?!.,;:')
        if not normalized:
            return False

        explicit_business_terms = (
            'tim san', 'tim co so', 'kiem san', 'muon tim san', 'toi muon tim',
            'dat san', 'thue san', 'booking', 'lich trong', 'khung gio',
            'con trong', 'con san nao', 'san nao', 'san bong', 'san cau long',
            'san tennis', 'san pickleball', 'san bong ro', 'san bong chuyen',
            'toi nay', 'toi mai', 'ngay mai', 'ngay kia', 'gio ', ' h',
        )
        if any(term in normalized for term in explicit_business_terms):
            return False

        continuation_terms = (
            'con ', 'the ', 'vay ', 'thi sao', 'mon nay', 'mon do',
            'mon the thao nay', 'mon the thao do', 'san nay', 'san do',
            'co so nay', 'co so do', 'noi do',
        )
        return any(term in normalized for term in continuation_terms)

    def route(self, message: str, context: dict[str, Any] | None = None, *, today: date | None = None) -> IntentRoute:
        query = normalize_text(' '.join(message.strip().split()))
        context = context or {}
        current_date = today or date.today()
        fresh_entities = self._entities(query, {}, current_date)
        has_context = any(context.get(key) is not None for key in (
            'sport_type', 'location', 'booking_date', 'date', 'field_id', 'result_field_ids', 'booking_code',
            'partner_application_status', 'partner_application_id', 'last_intent',
            'domain_context_type',
        ))
        system_domain_followup = self.is_system_domain_followup(query, context)
        unresolved_explicit_entity = (
            fresh_entities.explicit_entity_mention
            and not fresh_entities.active_entity
            and not fresh_entities.sports_entities
        )
        context_reset = has_context and not system_domain_followup and (
            self._starts_new_request(query, fresh_entities, context)
            or unresolved_explicit_entity
        )
        if context.get("sports_entities") and any(term in query for term in ("ho dang", "hai nguoi", "hai cau thu", "ca hai", "thi dau o dau", "dang thi dau")):
            context_reset = False
        effective_context = {} if context_reset else context
        entities = self._entities(query, effective_context, current_date)
        follow_up = has_context and (
            self._is_follow_up(query) or self._has_continuation_detail(query)
            or fresh_entities.sport_type is not None or fresh_entities.court_type is not None
        )

        # 1. Safety / Abusive detection
        if self._is_abusive(query):
            return IntentRoute(AssistantIntent.ABUSIVE, 0.99, fresh_entities, context_reset=True)

        # 2. Nonsense / Spam / Keyboard mash detection
        if self._is_nonsense(query):
            return IntentRoute(AssistantIntent.NONSENSE, 0.99, fresh_entities, context_reset=True)

        has_unsupported_sport = any(bool(re.search(r'\b' + re.escape(term) + r'\b', query)) for term in UNSUPPORTED_SPORTS_TERMS)
        if has_unsupported_sport and not fresh_entities.sports_entities:
            return IntentRoute(AssistantIntent.OUT_OF_SCOPE, 0.99, fresh_entities, context_reset=True)

        has_out_of_scope = any(bool(re.search(r'\b' + re.escape(term) + r'\b', query)) for term in OUT_OF_SCOPE_TERMS)
        has_domain_term = any(bool(re.search(r'\b' + re.escape(term) + r'\b', query)) for term in (
            'cho san', 'dat san', 'tim san', 'xem san', 'thue san', 'san con trong',
            'lich trong', 'booking', 'sporthub', 'chu san', 'san nao', 'co san',
            'san the thao', 'san bong', 'san cau long', 'san tennis', 'san pickleball',
            'khung gio', 'slot', 'doi lich', 'doi gio', 'huy san', 'huy booking', 'huy don',
        )) or bool(re.search(r'\bsan\b', query)) or fresh_entities.sport_type is not None or fresh_entities.venue_name is not None

        if has_out_of_scope:
            if has_domain_term:
                domain_intent, domain_conf = self._match_intent(query, follow_up, effective_context, fresh_entities)
                if domain_intent is not None and domain_conf >= 0.55:
                    needs_clarification = self._needs_clarification(domain_intent, entities, has_context)
                    return IntentRoute(domain_intent, domain_conf, entities, needs_clarification, follow_up, context_reset, is_combined_out_of_scope=True)
                return IntentRoute(AssistantIntent.OUT_OF_SCOPE, 0.95, fresh_entities, context_reset=False, is_combined_out_of_scope=True)
            return IntentRoute(AssistantIntent.OUT_OF_SCOPE, 0.99, fresh_entities, context_reset=True)

        # 3. Natural Conversation / Social greetings & chit-chat (when no specific search / booking request)
        if self._is_greeting(query):
            return IntentRoute(AssistantIntent.GREETING, 0.99, entities)
        if self._is_ai_identity(query, fresh_entities):
            return IntentRoute(AssistantIntent.AI_IDENTITY, 0.99, entities)
        if self._is_ai_capability(query, fresh_entities):
            return IntentRoute(AssistantIntent.AI_CAPABILITY, 0.98, entities)
        if self._is_thanks(query):
            return IntentRoute(AssistantIntent.THANKS, 0.98, entities)
        if self._is_goodbye(query):
            return IntentRoute(AssistantIntent.GOODBYE, 0.98, entities)
        if self._is_casual(query):
            return IntentRoute(AssistantIntent.CASUAL, 0.95, entities)

        # Keep the semantic System Domain operation for short entity switches.
        # The assistant may answer before business handlers, but its route
        # must also remain GET_PRODUCTS/GET_VENUE_DETAIL for downstream policy
        # and metadata consumers.
        if system_domain_followup:
            semantic_intent = (
                AssistantIntent.GET_PRODUCTS if context.get('domain_context_type', '').endswith('_products')
                else AssistantIntent.GET_VENUE_DETAIL
            )
            return IntentRoute(semantic_intent, 0.97, entities, False, follow_up, False)

        intent, confidence = self._match_intent(query, follow_up, effective_context, fresh_entities, entities)
        if intent is None:
            if follow_up:
                intent, confidence = AssistantIntent.FOLLOW_UP, 0.82
            elif self._looks_ambiguous(query):
                intent, confidence = AssistantIntent.UNCLEAR, 0.35
            elif not any(term in query for term in DOMAIN_TERMS) and not entities.sport_type and not entities.sports_entity and not entities.sports_entities:
                intent, confidence = AssistantIntent.OUT_OF_SCOPE, 0.86
            else:
                intent, confidence = AssistantIntent.UNCLEAR, 0.4

        if confidence < 0.55:
            intent = AssistantIntent.UNCLEAR
        if intent == AssistantIntent.PARTNER_APPLICATION_SUPPORT and context.get('last_intent') != intent.value:
            context_reset = context_reset or bool(context)
        needs_clarification = self._needs_clarification(intent, entities, has_context)
        return IntentRoute(intent, confidence, entities, needs_clarification, follow_up, context_reset)

    @staticmethod
    def _match_intent(
        query: str,
        follow_up: bool,
        context: dict[str, Any],
        fresh_entities: IntentEntities,
        entities: IntentEntities | None = None,
    ) -> tuple[AssistantIntent | None, float]:
        effective_sports_ent = fresh_entities.sports_entity or (entities.sports_entity if entities else None)
        partner_context = context.get('last_intent') == AssistantIntent.PARTNER_APPLICATION_SUPPORT.value
        if any(term in query for term in (
            'tro thanh chu san', 'dang ky lam doi tac', 'dang ky doi tac', 'dang ky owner',
            'ho so doi tac', 'ho so chu san', 'ho so owner', 'gui lai ho so', 'lam chu san', 'lam doi tac',
            'quy trinh dang ky', 'quy trinh tro thanh',
            'ho so cua toi dang o trang thai nao', 'ho so cua toi den dau',
            'tai sao ho so bi tu choi', 'cap nhat va gui lai ho so',
            'can chuan bi thong tin gi', 'can chuan bi giay to gi', 'duyet ho so cua toi',
        )) or (partner_context and any(term in query for term in (
            'ho so cua toi', 'trang thai nao', 'den dau roi', 'tai sao bi tu choi',
            'gui lai', 'can chuan bi', 'buoc tiep theo',
        ))):
            return AssistantIntent.PARTNER_APPLICATION_SUPPORT, 0.98
        if any(term in query for term in (
            'thoi tim san', 'quay lai tim san', 'quay lai dat san', 'tim san luc nay', 'san luc nay',
            'dat san luc nay', 'thoi xem san', 'quay lai xem san', 'thoi kiem san', 'tim san bong luc nay',
        )):
            return AssistantIntent.SEARCH_VENUE, 0.95
        if any(term in query for term in (
            'cong suat', 'thap diem', 'cao diem', 'it khach', 'gio vang',
            'chay uu dai', 'khuyen mai luc nao', 'san nao vang', 'lap day', 'ty le lap day',
        )):
            return AssistantIntent.OCCUPANCY_INSIGHT, 0.97
        if any(term in query for term in (
            'san pham', 'dich vu them', 'dich vu nao', 'cho thue gi',
            'con hang', 'so luong con', 'ton kho', 'thue vot', 'vot cho thue', 'mua nuoc',
            'ban nuoc', 'nuoc uong', 'phu kien', 'thue bong', 'ao pitch',
        )):
            return AssistantIntent.GET_PRODUCTS, 0.97
        if any(term in query for term in ('hoan tien', 'thanh toan', 'dat coc', 'tien coc', 'hoa don', 'bien lai', 'giao dich', 'hoan coc', 'doanh thu')) and not any(term in query for term in ('chinh sach huy', 'huy booking', 'huy dat')):
            return AssistantIntent.PAYMENT_SUPPORT, 0.96
        has_booking_context = bool(
            fresh_entities.booking_code or context.get('booking_code')
            or context.get('last_intent') in {'GET_BOOKING', 'CANCEL_BOOKING', 'RESCHEDULE_BOOKING'}
            or any(term in query for term in ('booking', 'lich dat', 'ma dat', 'dat san'))
        )
        is_search_follow_up = bool(
            context.get('last_intent') in {'SEARCH_VENUE', 'RECOMMEND_VENUE', 'CHECK_AVAILABILITY', 'RECOMMEND_SLOT'}
            or (context.get('sport_type') and not has_booking_context)
        )
        reschedule_terms = ('doi lich', 'doi gio', 'doi ngay', 'doi san', 'dời lịch', 'doi ca', 'reschedule')
        if any(term in query for term in reschedule_terms) and (not is_search_follow_up or has_booking_context):
            return AssistantIntent.RESCHEDULE_BOOKING, 0.97
        if re.search(r'\b(huy|huỷ)\b', query) and any(term in query for term in ('san', 'booking', 'lich dat', 'ma dat', 'chinh sach', 'don', 'don dat')):
            return AssistantIntent.CANCEL_BOOKING, 0.96
        if any(term in query for term in (
            'trang thai booking', 'booking cua toi', 'lich su dat', 'lich dat cua toi', 'xem booking',
            'ma dat', 'bao nhieu booking', 'booking hom nay', 'kiem tra don dat', 'kiem tra don', 'don dat san', 'don dat'
        )) or (
            'booking' in query and ('the nao' in query or 'trang thai' in query)
        ):
            return AssistantIntent.GET_BOOKING, 0.95
        if any(term in query for term in ('tai khoan', 'ho so', 'thong tin cua toi', 'doi mat khau', 'dang nhap', 'dang ky tai khoan', 'dang ky sporthub', 'sua thong tin ca nhan', 'chinh sua ho so', 'bao nhieu owner', 'bao nhieu customer', 'owner dang hoat dong')):
            return AssistantIntent.ACCOUNT_SUPPORT, 0.94
        if any(term in query for term in (
            'huong dan dat san', 'huong dan tim san', 'huong dan su dung', 'huong dan sporthub', 'huong dan dang ky',
            'huong dan chu san', 'huong dan thanh toan', 'huong dan danh gia', 'huong dan tao san',
            'cach su dung', 'cach dat san', 'lam the nao de dat san', 'lam sao de dat san',
            'sporthub lam duoc gi', 'tro ly nay lam duoc gi', 'lam duoc gi', 'chuc nang', 'tro ly lam gi',
            'giup toi nhung gi', 'giup duoc gi', 'sporthub la gi',
            'sporthub hoat dong nhu the nao', 'he thong hoat dong nhu the nao', 'tro ly hoat dong nhu the nao', 'app hoat dong nhu the nao',
            'vai tro', 'phan quyen', 'cac buoc dat san', 'danh gia san', 'lam the nao de danh gia',
            'lam the nao de tim san', 'cach tim san', 'lam sao de tim san',
            'dieu kien dang ky chu san', 'yeu cau dang ky owner', 'can gi de dang ky lam chu san',
            'chu san duoc quan ly', 'owner quan ly', 'chu san them san', 'tao san moi', 'them san moi',
            'chu san quan ly khung gio', 'cai dat khung gio', 'tao slot', 'bang gia gio vang', 'cai dat bang gia',
            'chu san quan ly san pham', 'thue vot bong', 'san pham phu tro', 'xem doanh thu chu san',
            'admin quan ly', 'duyet ho so chu san', 'duyet co so', 'phe duyet co so',
            'bao lau thi duyet', 'thoi gian duyet', 'phi dang ky chu san', 'phi duy tri',
        )) or (('huong dan' in query or 'hoat dong nhu the nao' in query) and any(term in query for term in ('sporthub', 'he thong', 'tro ly', 'app', 'ung dung', 'san', 'chu san', 'owner', 'booking', 'dat coc', 'tai khoan'))):
            return AssistantIntent.SYSTEM_GUIDE, 0.95
        if any(term in query for term in ('bao nhieu co so', 'co bao nhieu co so', 'so luong co so')):
            return AssistantIntent.SEARCH_VENUE, 0.96

        if follow_up and not any(term in query for term in ('gia bao nhieu', 'dia chi', 'tien ich', 'chi tiet')) and (
            re.search(r'\b(san|lua chon|ket qua)\s*(?:thu\s*|so\s*)?(\d+|mot|hai|ba|tu|nam|dau|dau tien|cuoi|cuoi cung)\b', query)
            or any(term in query for term in ('san khac', 'ngay khac', 'gio khac', 'khung khac'))
        ):
            return AssistantIntent.FOLLOW_UP, 0.9

        if any(term in query for term in ('muon dat san', 'dat giup', 'dat san nay', 'xac nhan dat', 'tao booking')):
            return AssistantIntent.CREATE_BOOKING, 0.95

        # Explicit search venue verbs prioritize SEARCH_VENUE
        if any(term in query for term in ('tim san', 'tim co so', 'kiem san', 'cho toi san', 'muon tim san', 'danh sach san')) or (query.startswith('tim ') and not any(term in query for term in ('khung gio', 'gio'))):
            if any(term in query for term in ('con trong', 'lich trong', 'con san', 'con gio', 'co trong khong')):
                return AssistantIntent.CHECK_AVAILABILITY, 0.95
            return AssistantIntent.SEARCH_VENUE, 0.94

        if 're hon' not in query and (any(term in query for term in ('con trong', 'lich trong', 'con san', 'con gio', 'khung gio nao', 'con 19h', 'co trong khong', 'ngay nao trong', 'ngay trong', 'con khung gio', 'con slot')) or (
            follow_up and re.search(r'\bcon\s+\d{1,2}(?::\d{2})?\s*(?:h|gio)?\b', query)
        )):
            return AssistantIntent.CHECK_AVAILABILITY, 0.95

        if any(term in query for term in ('goi y khung gio', 'goi y gio', 'gio phu hop', 'gio nao phu hop', 'gio gan do', 're hon', 'tim khung gio', 'khung gio')) or (
            follow_up and (fresh_entities.start_time is not None or fresh_entities.preferred_time is not None)
        ):
            return AssistantIntent.RECOMMEND_SLOT, 0.94
        if any(term in query for term in ('goi y', 'de xuat', 'phu hop', 'nen chon', 'tot nhat', 'san ngon', 'vai san ngon')) and not any(term in query for term in ('gio', 'khung gio', 'slot')):
            return AssistantIntent.RECOMMEND_VENUE, 0.93
        if any(term in query for term in (
            'dia chi', 'tien ich', 'thong tin san', 'chi tiet san', 'gia bao nhieu', 'gia san', 'bang gia',
            'bao tri', 'dong cua', 'gio mo cua', 'mo cua luc nao', 'bai do xe', 'dieu hoa',
        )):
            return AssistantIntent.GET_VENUE_DETAIL, 0.92

        domain_terms = (
            'san', 'co so', 'choi', 'dat', 'tim', 'kiem', 'dia diem', 'co', 'o dau', 'khu vuc'
        )

        is_sports_spec_or_rule = any(term in query for term in (
            'kich thuoc san', 'chieu cao luoi', 'kich thuoc luoi', 'luat choi', 'luat thi dau', 'luat',
            'tieu chuan', 'quy dinh', 'quy tac', 'viet vi', 'tie-break', '3 diem', 'cach tinh diem',
            'thoi gian thi dau', 'ky thuat', 'chien thuat', 'doi hinh', 'tieu su', 'la ai', 'ai la',
            'thanh tich', 'lich su', 'nguon goc', 'phong trao', 'huan luyen vien', 'hlv',
            'ictu co san', 'truong ictu', 'truong dai hoc', 'san van dong', 'svd', 'suc chua', 'quy mo'
        ))

        # Check SPORTS_KNOWLEDGE
        is_venue_operation = not is_sports_spec_or_rule and (any(term in query for term in (
            'dat san', 'thue san', 'tim san', 'con trong', 'lich trong', 'khung gio',
            'cho toi san', 'muon dat', 'tao booking', 'xem san',
            'gia san', 'co so nao', 'co bao nhieu co so', 'kiem san', 'gia bao nhieu',
            'dat lich', 'huy san', 'doi lich', 'san con trong', 'slot', 'co slot', 'gia ca',
            'con gio', 'con san', 'tim co so', 'san nao con', 'san nao trong', 'co san',
            'co san nao', 'co san khong', 'san o'
        )) or bool(re.search(r'\b(san|co so|thue san|dat san)\b', query)))
        if not is_venue_operation:
            # If sports entity is a geographic location (province/city) or school/university, require sports knowledge context/keywords
            geo_locations = {'ha noi', 'thai nguyen', 'tp hcm', 'tp.hcm', 'ho chi minh', 'hcm', 'da nang', 'hai phong', 'can tho'}
            academic_terms = ('tuyen sinh', 'hoc phi', 'diem chuan', 'nganh hoc', 'dao tao', 'khoa hoc', 'nhap hoc', 'xet tuyen', 'chuong trinh hoc')
            has_academic = any(term in query for term in academic_terms)
            is_geo_or_school = effective_sports_ent and (
                normalize_text(effective_sports_ent) in geo_locations
                or any(k in normalize_text(effective_sports_ent) for k in ('ictu', 'truong', 'dai hoc', 'fit', 'fet'))
            )
            has_sports_inquiry = any(term in query for term in (
                'the thao', 'clb', 'cau lac bo', 'doi bong', 'doi tuyen', 'mon the thao', 'mon gi', 'mon nao',
                'giai', 'phong trao', 'manh ve', 'co nhung doi', 'co doi', 'vdv', 'van dong vien',
                'bong da', 'da bong', 'choi bong', 'thi dau', 'giai dau', 'co doi khong',
                'cau long', 'pickleball', 'tennis', 'bong ro', 'bong chuyen', 'bong ban', 'e-sports', 'san'
            ))

            if fresh_entities.is_meme_or_joke:
                return AssistantIntent.SPORTS_KNOWLEDGE, 0.95

            if fresh_entities.is_conditional and fresh_entities.sports_entities:
                return AssistantIntent.SPORTS_KNOWLEDGE, 0.95

            if fresh_entities.explicit_entity_mention and any(term in query for term in (
                'la ai', 'ai la', 'gioi thieu', 'tieu su', 'dang choi',
                'thi dau', 'choi mon', 'choi bo mon',
            )):
                return AssistantIntent.SPORTS_KNOWLEDGE, 0.75

            if effective_sports_ent is not None and not has_academic and (not is_geo_or_school or has_sports_inquiry):
                return AssistantIntent.SPORTS_KNOWLEDGE, 0.96

            is_athlete_inquiry = any(p in query for p in (
                'anh ay sinh', 'ong ay sinh', 'co ay sinh', 'cau thu nay sinh', 'vdv nay sinh', 'tay vot nay sinh',
                'anh ay bao nhieu tuoi', 'anh ay da cho', 'anh ay choi cho', 'ong ay da cho', 'ong ay choi cho',
                'anh ay thi dau', 'ong ay thi dau', 'anh ay sinh nam', 'ong ay sinh nam', 'sinh nam bao nhieu',
                'anh ay da o vi tri', 'anh ay choi o vi tri', 'da o vi tri nao', 'choi o vi tri nao'
            ))
            if is_athlete_inquiry:
                return AssistantIntent.SPORTS_KNOWLEDGE, 0.95

            is_sports_context = context.get('last_intent') == AssistantIntent.SPORTS_KNOWLEDGE.value
            if is_sports_context:
                if any(term in query for term in (
                    'anh ay', 'cau thu nay', 'cau thu do', 'ong ay', 'co ay', 'chi ay',
                    'tay vot nay', 'tay vot do', 'vdv nay', 'vdv do', 'van dong vien nay', 'van dong vien do',
                    'nguoi nay', 'nguoi do', 'doi nay', 'doi do', 'clb nay', 'clb do',
                    'cau lac bo nay', 'cau lac bo do', 'svd nay', 'svd do', 'san nay', 'san do',
                    'doi nao', 'clb nao', 'cau lac bo nao', 'giai nao', 'choi cho', 'da cho', 'thi dau cho',
                    'dang thi dau', 'dang choi', 'o dau', 'con ', 'the con ', 'thi sao', 'thanh tich', 'sinh nam',
                    'bao nhieu tuoi', 'que o dau', 'huan luyen vien', 'hlv', 'con o', 'the con o',
                    'cau lac bo', 'clb', 'doi tuyen', 'doi bong', 'co bao nhieu ban thang', 'danh hieu', 'vo dich',
                    'tinh nay', 'thanh pho nay', 'tp nay', 'dia phuong nay', 'con mon khac', 'mon khac', 'co doi'
                )):
                    return AssistantIntent.SPORTS_KNOWLEDGE, 0.95
            effective_sport_type = fresh_entities.sport_type or (entities.sport_type if entities else None) or context.get('sport_type')
            has_supported_sport = (
                effective_sport_type in SUPPORTED_SPORTS
                or any(k in query for k in SPORT_ALIASES)
                or any(k in query for k in ('vff', 'fifa', 'v-league', 'vba', 'ictu cup', 'cau thu', 'tay vot', 'van dong vien', 'vdv'))
                or (any(k in query for k in ('clb', 'cau lac bo', 'doi bong', 'doi tuyen')) and any(k in query for k in ('la ai', 'ai la', 'tieu su', 'thanh tich', 'vo dich', 'o dau', 'thanh lap')))
            )
            if has_supported_sport:
                if any(term in query for term in (
                    'la ai', 'ai la', 'tieu su', 'bao nhieu tuoi', 'sinh nam', 'que o dau',
                    'o dau co nhung gi', 'co nhung gi', 'co gi noi bat', 'co nhung ai', 'nhung ai', 'noi tieng',
                    'ai gioi', 'gioi', 'noi bat', 'tieu bieu', 'xuat sac', 'hang dau', 'co ai',
                    'choi cho doi nao', 'da cho doi nao', 'clb nao', 'doi bong nao', 'doi nao', 'nhung doi nao',
                    'co nhung doi nao', 'co doi nao', 'cac doi nao', 'nhung clb nao', 'co nhung clb nao', 'co clb nao',
                    'doi tuyen', 'tuyen quoc gia', 'tuyen nu', 'tuyen nam',
                    'thanh tich', 'giai dau', 'giai vo dich', 'vo dich', 'quan quan', 'a quan',
                    'huy chuong', 'cup', 'danh hieu', 'ky luc', 'ban thang',
                    'ket qua tran', 'ket qua thi dau', 'ket qua moi nhat', 'ket qua', 'ti so',
                    'lich thi dau', 'lich dau', 'bang xep hang', 'xep hang', 'tran dau', 'chuyen nhuong',
                    'tin chuyen nhuong', 'hop dong', 'gia nhap', 'roi clb',
                    'lich su', 'nguon goc', 'ra doi', 'quy mo', 'phat trien', 'phong trao', 'thuc trang',
                    'luat choi', 'luat thi dau', 'luat', 'quy dinh', 'quy tac', 'viet vi', 'tie-break', '3 diem',
                    'cach tinh diem', 'tinh diem', 'kich thuoc san', 'kich thuoc', 'tieu chuan',
                    'kich thuoc luoi', 'chieu cao luoi', 'thoi gian thi dau', 'bao nhieu nguoi', 'may nguoi',
                    'ky thuat', 'cach giao bong', 'cach dap bong', 'cach bat bong', 'cach nem bong',
                    'chien thuat', 'doi hinh', 'vi tri',
                    'huan luyen vien', 'hlv', 'cau thu', 'van dong vien', 'vdv', 'tay vot', 'trong tai',
                    'san van dong', 'svd', 'khu lien hop', 'cau lac bo', 'clb', 'hoc vien',
                    'o thai nguyen', 'o viet nam', 'the gioi', 'quoc te', 'nhu the nao', 'the nao',
                    'co gi', 'la gi', 'y nghia'
                )) or fresh_entities.current_topic in ('athletes', 'identity', 'achievements'):
                    return AssistantIntent.SPORTS_KNOWLEDGE, 0.94

        # General Search / Availability matching
        has_search_entities = bool(fresh_entities.sport_type or fresh_entities.court_type) or (
            bool(fresh_entities.location) and (
                any(term in query for term in domain_terms) or bool(re.search(r'\b(san|co so|choi|dat|tim|kiem|dia diem|co)\b', query))
            )
        )
        has_date_or_time = bool(fresh_entities.date or fresh_entities.start_time or fresh_entities.preferred_time)
        has_search_terms = any(term in query for term in (
            'co san', 'san nao', 'tim san', 'tim co so', 'kiem san', 'cho toi san',
            'toi muon san', 'muon san', 'muon tim', 'giup toi tim', 'co tim san', 'tim giup', 'giup tim',
            'thue san', 'muon thue', 'can thue', 'cho thue san',
        )) or query.startswith('co san') or query.startswith('tim ') or query.startswith('san ') or query.startswith('thue ')

        if has_search_entities or has_search_terms:
            if has_date_or_time or any(term in query for term in ('hom nay', 'ngay mai', 'toi nay', 'toi mai', 'ngay kia')):
                return AssistantIntent.CHECK_AVAILABILITY, 0.93
            return AssistantIntent.SEARCH_VENUE, 0.92

        return None, 0.0

    @staticmethod
    def _is_abusive(query: str) -> bool:
        abusive_patterns = (
            r'\b(?:dcm|clgt|dm|vcl|vl|vcc|dkm|đkm|đcm|đụ|địt)\b',
            r'\b(?:dit\s*me|du\s*me|dit\s*con\s*me|du\s*con\s*me|dmm|dcmm|clmm)\b',
            r'\b(?:cai\s*buoi|dau\s*buoi|cai\s*lon|con\s*lon|lon\s*me|cai\s*cac|con\s*cac|an\s*cac)\b',
            r'\b(?:do\s*ngu|ngu\s*vcl|ngu\s*vl|ngu\s*ngoc|ngu\s*qua|do\s*cho|con\s*cho|thang\s*cho|mat\s*day|chet\s*di|cut\s*di|bien\s*di|chet\s*me)\b',
            r'\b(?:fuck|bitch|asshole|bullshit)\b',
        )
        return any(bool(re.search(pat, query, re.IGNORECASE)) for pat in abusive_patterns)

    @staticmethod
    def _is_nonsense(query: str) -> bool:
        cleaned = re.sub(r'[^a-z0-9 ]', '', query).strip()
        if not cleaned:
            return True
        # Repeated single character >= 5 times (e.g. aaaaa, zzzzzz, 11111)
        if re.search(r'(.)\1{4,}', cleaned):
            return True
        # Repeated words >= 3 times (e.g. test test test)
        if re.search(r'\b([a-z0-9]+)(?:\s+\1){2,}\b', cleaned):
            return True
        # Keyboard mash / random tokens
        mash_tokens = {'asdf', 'asdfg', 'asdfgh', 'asdfghjkl', 'qwerty', 'qwertyuiop', 'zxcv', 'zxcvbn', 'zxcvbnm', 'lkjhg', 'poiuy', '123456', '12345678'}
        words = cleaned.split()
        if len(words) == 1 and (words[0] in mash_tokens or (len(words[0]) >= 7 and not any(v in words[0] for v in 'aeiouy'))):
            return True
        # 6 or more consecutive consonants without any vowels (a, e, i, o, u, y), excluding known acronyms
        consonant_match = re.search(r'[bcdfghjklmnpqrstvwxz]{6,}', cleaned)
        if consonant_match:
            matched_str = consonant_match.group(0)
            if matched_str not in {'sporthub', 'tphcm'}:
                return True
        return False

    @staticmethod
    def _is_greeting(query: str) -> bool:
        cleaned = re.sub(r'[^a-z0-9 ]', '', query).strip()
        if not cleaned:
            return False
        tokens = cleaned.split()
        if len(tokens) > 6:
            return False
        greeting_starts = (
            'xin chao', 'chao buoi sang', 'chao buoi chieu', 'chao buoi toi',
            'good morning', 'good afternoon', 'good evening',
            'chao ban nhe', 'chao ban nha', 'chao ban', 'chao tro ly', 'chao sporthub', 'chao ad', 'chao shop',
            'chao anh', 'chao em', 'chao chi', 'chao nhe', 'chao nha', 'chao',
            'hello sporthub', 'hi sporthub', 'hello ban', 'hi ban', 'hey ban', 'hello ad', 'hi ad',
            'hello', 'hi', 'hey', 'alo sporthub', 'alo ban', 'alo', 'helo',
        )
        remaining = cleaned
        for g in sorted(greeting_starts, key=len, reverse=True):
            remaining = re.sub(r'\b' + re.escape(g) + r'\b', '', remaining).strip()
        particles = {'nha', 'nhe', 'a', 'ha', 'oi', 'sporthub', 'ai', 'ad', 'shop', 'tro ly', 'ban', 'em', 'anh', 'chi', 'bot', 'minh'}
        rem_tokens = [t for t in remaining.split() if t not in particles]
        return len(rem_tokens) == 0

    @staticmethod
    def _is_ai_identity(query: str, fresh_entities: IntentEntities) -> bool:
        if fresh_entities.sports_entities or fresh_entities.sport_type or fresh_entities.venue_name:
            return False
        if any(k in query for k in ('chuc nang', 'tinh nang', 'lam duoc', 'giup duoc', 'ho tro')):
            return False
        identity_patterns = (
            r'\b(?:ban|tro ly|bot)\s+(?:la\s+ai|ten\s+gi|ten\s+la\s+gi|la\s+gi|la\s+ai\s+the|la\s+ai\s+vay|la\s+ai\s+gi|la\s+con\s+gi|la\s+bot\s+gi|la\s+ai\s+day)\b',
            r'\b(?:ten\s+cua\s+ban|ten\s+ban\s+la\s+gi|ten\s+ban\s+la\s+chi)\b',
            r'\b(?:ai\s+tao\s+ra\s+ban|ai\s+sinh\s+ra\s+ban|ai\s+lam\s+ra\s+ban|ai\s+phat\s+trien\s+ban|ban\s+do\s+ai\s+tao|ban\s+tu\s+dau\s+den)\b',
            r'\b(?:tro\s+ly\s+nay\s+la\s+ai|tro\s+ly\s+sporthub\s+la\s+ai|bot\s+nay\s+la\s+ai)\b',
        )
        return any(bool(re.search(pat, query, re.IGNORECASE)) for pat in identity_patterns)

    @staticmethod
    def _is_ai_capability(query: str, fresh_entities: IntentEntities) -> bool:
        if fresh_entities.venue_name or fresh_entities.booking_code:
            return False
        if fresh_entities.sport_type and any(term in query for term in ('tim', 'san', 'dat', 'gia', 'con trong')):
            return False
        capability_patterns = (
            'ban co the lam gi', 'ban lam duoc gi', 'ban giup duoc gi', 'ban giup toi duoc gi',
            'ban giup duoc gi cho toi', 'tro ly nay dung de lam gi', 'tro ly nay lam duoc gi', 'tro ly nay lam gi',
            'chuc nang cua ban', 'tinh nang cua ban', 'ban co chuc nang gi', 'ban co tinh nang gi',
            'ban biet lam gi', 'ban ho tro duoc gi', 'ban ho tro nhung gi', 'sporthub lam duoc gi',
            'sporthub ai lam duoc gi', 'bot lam duoc gi', 'ai nay lam duoc gi', 'ban lam gi duoc',
            'ban giup gi', 'giup duoc gi', 'lam duoc gi', 'ban lam duoc nhung viec gi', 'ban lam duoc nhung gi',
            'ban lam duoc viec gi', 'tro ly nay lam gi', 'tro ly sporthub lam duoc gi',
        )
        return any(p in query for p in capability_patterns)

    @staticmethod
    def _is_thanks(query: str) -> bool:
        cleaned = re.sub(r'[^a-z0-9 ]', '', query).strip()
        if not cleaned:
            return False
        has_domain = any(term in cleaned for term in ('tim', 'san', 'dat', 'gia', 'huy', 'doi', 'xem', 'lich', 'kiem'))
        if has_domain:
            return False
        thanks_phrases = (
            'cam on ban nhe', 'cam on ban nha', 'cam on ban', 'cam on nha', 'cam on nhe',
            'cam on nhieu', 'cam on tro ly', 'cam on sporthub', 'cam on',
            'thank you so much', 'thank you', 'thanks a lot', 'thanks ban', 'thanks nha', 'thanks nhe', 'thanks', 'thank ban', 'thank',
            'ok ban nhe', 'ok ban nha', 'ok ban', 'ok nha', 'ok nhe', 'ok roi', 'ok nhe ban', 'okie', 'oki', 'ok',
            'duoc roi ban', 'duoc roi nha', 'duoc roi nhe', 'duoc roi', 'da hieu roi', 'da hieu', 'ro roi ban', 'ro roi',
            'da vang', 'vang a', 'vang', 'da cam on',
        )
        tokens = cleaned.split()
        if len(tokens) > 6:
            return False
        return any(cleaned == p or cleaned.startswith(p + ' ') or cleaned.endswith(' ' + p) for p in thanks_phrases)

    @staticmethod
    def _is_goodbye(query: str) -> bool:
        cleaned = re.sub(r'[^a-z0-9 ]', '', query).strip()
        if not cleaned:
            return False
        goodbye_phrases = (
            'tam biet ban nhe', 'tam biet ban nha', 'tam biet ban', 'tam biet',
            'chao tam biet',
            'hen gap lai ban nhe', 'hen gap lai nhe', 'hen gap lai nha', 'hen gap lai',
            'bye bye ban', 'bye bye nha', 'bye bye nhe', 'bye bye', 'bye ban', 'bye nha', 'bye nhe', 'bye',
            'goodbye ban', 'goodbye', 'bai bai',
            'chuc ngu ngon', 'good night', 'g9',
            'chuc mot ngay tot lanh', 'chuc ngay tot lanh', 'ngay moi tot lanh', 'chuc buoi toi vui ve',
        )
        tokens = cleaned.split()
        if len(tokens) > 6:
            return False
        return any(cleaned == p or cleaned.startswith(p + ' ') or cleaned.endswith(' ' + p) for p in goodbye_phrases)

    @staticmethod
    def _is_casual(query: str) -> bool:
        cleaned = re.sub(r'[^a-z0-9 ]', '', query).strip()
        if not cleaned:
            return False
        if any(term in cleaned for term in ('tim san', 'dat san', 'thue san', 'gia san', 'huy san', 'doi lich', 'con trong', 'con slot', 'san bong', 'san cau long', 'san tennis')):
            return False
        casual_phrases = (
            'hom nay ban the nao', 'hom nay the nao roi', 'hom nay the nao', 'ban the nao roi', 'ban the nao',
            'ban khoe khong', 'ban co khoe khong', 'khoe khong ban', 'khoe khong',
            'dao nay the nao', 'ban on khong', 'the nao roi ban', 'the nao roi',
            'hay qua ban', 'hay qua nha', 'hay qua nhe', 'hay qua', 'hay the',
            'tuyet voi qua', 'tuyet voi lam', 'tuyet voi', 'tuyet qua',
            'duoc do ban', 'duoc do nha', 'duoc do nhe', 'duoc do', 'duoc day',
            'tot lam ban', 'tot lam nha', 'tot lam',
            'dinh qua ban', 'dinh qua', 'dinh the',
            'gioi qua ban', 'gioi qua', 'gioi the',
            'xin qua ban', 'xin qua', 'xin the',
            'chuan luon ban', 'chuan luon', 'chuan qua',
            'thong minh qua ban', 'thong minh qua', 'thong minh the',
        )
        tokens = cleaned.split()
        if len(tokens) > 6:
            return False
        return any(cleaned == p or cleaned.startswith(p + ' ') or cleaned.endswith(' ' + p) for p in casual_phrases)

    @staticmethod
    def _has_continuation_detail(query: str) -> bool:
        return bool(
            re.search(r'\b(?:hom nay|ngay mai|toi mai|mai|ngay kia|ngay mot|cuoi tuan|thu hai|thu ba|thu tu|thu nam|thu sau|thu bay|chu nhat)\b', query)
            or re.search(r'\b(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*(?:h|gio)\b', query)
            or re.search(r'\b(?:duoi|toi da|khong qua)\s*[\d.,]+', query)
            or re.search(r'\b(?:buoi sang|buoi chieu|buoi toi|sang som|gio toi)\b', query)
        )

    @staticmethod
    def _is_follow_up(query: str) -> bool:
        return bool(re.search(r'\b(san|lua chon|ket qua)\s*(?:thu\s*|so\s*)?(\d+|mot|hai|ba|tu|nam|dau|dau tien|cuoi|cuoi cung)\b', query)) or any(
            term in query for term in (
                'san nay', 'cai nay', 'phuong an nay', 'san do', 'gia bao nhieu', 'bao nhieu co so',
                'con gio nao', 'con 19h', 'the con', 're hon', 'doi sang',
                'thi sao', 'vay con', 'con khong', 'san khac', 'ngay khac', 'gio khac', 'khung khac', 'khac',
                'anh ay', 'cau thu nay', 'ong ay', 'doi nay', 'clb nay', 'thi dau', 'choi cho', 'da cho',
            )
        )

    @staticmethod
    def _looks_ambiguous(query: str) -> bool:
        return len(query.split()) <= 4 and any(term in query for term in (
            'bao nhieu', 'the nao', 'con khong', 'cai nao', 'gi vay', 'dat', 'muon dat', 'gia the nao', 'co duoc khong'
        ))

    @staticmethod
    def _needs_clarification(intent: AssistantIntent, entities: IntentEntities, has_context: bool) -> bool:
        if intent == AssistantIntent.UNCLEAR:
            return True
        if intent in (AssistantIntent.SEARCH_VENUE, AssistantIntent.RECOMMEND_VENUE):
            return entities.sport_type is None and entities.location is None
        if intent == AssistantIntent.RECOMMEND_SLOT:
            return entities.sport_type is None or entities.date is None
        if intent == AssistantIntent.CHECK_AVAILABILITY:
            return (entities.venue_name is None and not has_context and entities.sport_type is None) or entities.date is None
        if intent == AssistantIntent.GET_VENUE_DETAIL:
            return entities.venue_name is None and not has_context
        if intent in (AssistantIntent.CANCEL_BOOKING, AssistantIntent.RESCHEDULE_BOOKING):
            return entities.booking_code is None
        return False

    def _entities(self, query: str, context: dict[str, Any], today: date) -> IntentEntities:
        start_time, end_time = self._times(query)

        # Multi-sport type extraction
        sport_matches: list[tuple[int, int, str]] = []
        for key in sorted(SPORT_ALIASES.keys(), key=len, reverse=True):
            pattern = r'(?<![a-z0-9])' + re.escape(key) + r'(?![a-z0-9])'
            for m in re.finditer(pattern, query):
                s, e = m.start(), m.end()
                if not any(max(s, ex_s) < min(e, ex_e) for ex_s, ex_e, _ in sport_matches):
                    sport_matches.append((s, e, SPORT_ALIASES[key]))
        sport_matches.sort(key=lambda x: x[0])
        sport_types: list[str] = []
        seen_sports = set()
        for _, _, sp in sport_matches:
            if sp not in seen_sports:
                seen_sports.add(sp)
                sport_types.append(sp)

        extracted_sport = sport_types[0] if sport_types else None

        # Multi-entity sports extraction
        sports_matches: list[tuple[int, int, str, str]] = []  # (start, end, sport, canonical_name)
        for key in sorted(KNOWN_SPORTS_ENTITIES.keys(), key=len, reverse=True):
            pattern = r'(?<![a-z0-9])' + re.escape(key) + r'(?![a-z0-9])'
            for m in re.finditer(pattern, query):
                s, e = m.start(), m.end()
                if not any(max(s, ex_s) < min(e, ex_e) for ex_s, ex_e, _, _ in sports_matches):
                    sport, name = KNOWN_SPORTS_ENTITIES[key]
                    sports_matches.append((s, e, sport, name))

        sports_matches.sort(key=lambda x: x[0])
        sports_entities: list[str] = []
        seen_entities = set()
        for _, _, sport, name in sports_matches:
            if extracted_sport and sport and sport != extracted_sport:
                continue
            if name not in seen_entities:
                seen_entities.add(name)
                sports_entities.append(name)

        # Natural & Context-aware sports resolution (nicknames, numbers in words/digits, slangs, follow-ups)
        sports_res = SportsContextResolver.resolve(query, context)
        if sports_res.sport and extracted_sport is None:
            extracted_sport = sports_res.sport
        if sports_res.active_entity and sports_res.active_entity not in sports_entities:
            sports_entities.insert(0, sports_res.active_entity)
            seen_entities.add(sports_res.active_entity)
        for ent in sports_res.entities:
            if ent not in sports_entities:
                sports_entities.append(ent)
                seen_entities.add(ent)

        # Resolve 'ICTU' entity to 'Bóng đá ICTU' if context/query is about football / teams
        if 'ICTU' in sports_entities and (
            extracted_sport == 'bóng đá'
            or any(k in query for k in ('doi bong', 'bong da', 'da bong', 'cung mot doi', 'thai nguyen t&t', 'doi nam', 'doi nu', 'giai', 'thi dau'))
        ):
            idx = sports_entities.index('ICTU')
            sports_entities[idx] = 'Bóng đá ICTU'
            if extracted_sport is None:
                extracted_sport = 'bóng đá'

        # Check flexible Thai Nguyen patterns if not directly matched
        if not sports_entities and 'thai nguyen' in query:
            tn_entity = None
            tn_sport = None
            if any(k in query for k in ('san van dong', 'svd')):
                tn_entity = 'Sân vận động Thái Nguyên'
                tn_sport = 'bóng đá'
            elif any(k in query for k in ('ngoai bong da', 'nhung mon the thao', 'cac mon the thao', 'the thao gi', 'nhung doi the thao', 'cac doi the thao', 'the thao thai nguyen')):
                tn_entity = 'Thể thao Thái Nguyên'
            elif 'cau long' in query:
                tn_entity = 'Cầu lông Thái Nguyên'
                tn_sport = 'cầu lông'
            elif 'pickleball' in query:
                tn_entity = 'Pickleball Thái Nguyên'
                tn_sport = 'pickleball'
            elif 'tennis' in query or 'quan vot' in query:
                tn_entity = 'Tennis Thái Nguyên'
                tn_sport = 'tennis'
            elif 'bong ro' in query:
                tn_entity = 'Bóng rổ Thái Nguyên'
                tn_sport = 'bóng rổ'
            elif 'bong chuyen' in query:
                tn_entity = 'Bóng chuyền Thái Nguyên'
                tn_sport = 'bóng chuyền'
            elif 'bong da' in query or 'doi bong' in query:
                if any(k in query for k in ('sinh vien', 'hoc duong', 'ictu', 'truong dai hoc', 'dh cntt')):
                    tn_entity = 'Bóng đá ICTU'
                elif any(k in query for k in ('t&t', 'tt', 'clb nu', 'doi nu', 'bong da nu', 'nu')):
                    tn_entity = 'Thái Nguyên T&T'
                elif any(k in query for k in ('nam', 'fc thai nguyen', 'bong da nam')):
                    tn_entity = 'Bóng đá nam Thái Nguyên'
                else:
                    tn_entity = 'Bóng đá Thái Nguyên'
                tn_sport = 'bóng đá'
            if tn_entity and tn_entity not in sports_entities:
                sports_entities.append(tn_entity)
                if extracted_sport is None:
                    extracted_sport = tn_sport

        # Check flexible Hanoi patterns
        if any(k in query for k in ('ha noi', 'hanoi', 'thu do')):
            hn_ent = None
            hn_sp = None
            if any(k in query for k in ('bong ro', 'basketball')):
                hn_ent = 'Bóng rổ Hà Nội'
                hn_sp = 'bóng rổ'
            elif any(k in query for k in ('bong chuyen', 'volleyball')):
                hn_ent = 'Bóng chuyền Hà Nội'
                hn_sp = 'bóng chuyền'
            elif any(k in query for k in ('cau long', 'badminton')):
                hn_ent = 'Cầu lông Hà Nội'
                hn_sp = 'cầu lông'
            elif any(k in query for k in ('dai hoc', 'sinh vien', 'truong dai hoc')):
                hn_ent = 'Thể thao Đại học Hà Nội'
            elif any(k in query for k in ('ngoai bong da', 'manh ve mon gi', 'the thao gi', 'nhung mon the thao', 'cac mon the thao', 'the thao ha noi', 'the thao')):
                hn_ent = 'Thể thao Hà Nội'
            elif any(k in query for k in ('bong da', 'doi bong', 'clb bong da', 'clb nao', 'doi nao')):
                hn_ent = 'Bóng đá Hà Nội'
                hn_sp = 'bóng đá'
            if hn_ent and hn_ent not in sports_entities:
                sports_entities.append(hn_ent)
                if extracted_sport is None and hn_sp is not None:
                    extracted_sport = hn_sp

        # Check flexible TP.HCM patterns
        if any(k in query for k in ('tp.hcm', 'tphcm', 'ho chi minh', 'sai gon')):
            hcm_ent = None
            hcm_sp = None
            if any(k in query for k in ('bong ro', 'basketball')):
                hcm_ent = 'Bóng rổ TP.HCM'
                hcm_sp = 'bóng rổ'
            elif any(k in query for k in ('bong chuyen', 'volleyball')):
                hcm_ent = 'Bóng chuyền TP.HCM'
                hcm_sp = 'bóng chuyền'
            elif any(k in query for k in ('cau long', 'badminton')):
                hcm_ent = 'Cầu lông TP.HCM'
                hcm_sp = 'cầu lông'
            elif any(k in query for k in ('bong ban', 'table tennis')):
                hcm_ent = 'Bóng bàn TP.HCM'
                hcm_sp = 'bóng bàn'
            elif any(k in query for k in ('ngoai bong da', 'the thao gi', 'nhung mon the thao', 'cac mon the thao', 'the thao tp.hcm', 'the thao tphcm', 'the thao')):
                hcm_ent = 'Thể thao TP.HCM'
            elif any(k in query for k in ('bong da', 'doi bong', 'clb bong da', 'clb nao', 'doi nao')):
                hcm_ent = 'Bóng đá TP.HCM'
                hcm_sp = 'bóng đá'
            if hcm_ent and hcm_ent not in sports_entities:
                sports_entities.append(hcm_ent)
                if extracted_sport is None and hcm_sp is not None:
                    extracted_sport = hcm_sp

        # Check flexible ICTU patterns if query contains ICTU context
        is_ictu_query = any(k in query for k in ('ictu', 'truong cntt', 'dh cntt', 'dai hoc cong nghe thong tin va truyen thong', 'cong nghe thong tin va truyen thong'))
        if is_ictu_query:
            ictu_ent = None
            ictu_sp = None
            if any(k in query for k in ('cau long', 'badminton')):
                ictu_ent = 'Cầu lông ICTU'
                ictu_sp = 'cầu lông'
            elif any(k in query for k in ('bong chuyen', 'volleyball')):
                ictu_ent = 'Bóng chuyền ICTU'
                ictu_sp = 'bóng chuyền'
            elif any(k in query for k in ('bong ban', 'table tennis')):
                ictu_ent = 'Bóng bàn ICTU'
                ictu_sp = 'bóng bàn'
            elif any(k in query for k in ('pickleball', 'pickle ball')):
                ictu_ent = 'Pickleball ICTU'
                ictu_sp = 'pickleball'
            elif any(k in query for k in ('mon the thao', 'nhung mon', 'con choi mon', 'cac mon', 'clb the thao', 'clb nao', 'ngoai bong da', 'the thao gi', 'nhung clb')):
                ictu_ent = 'Thể thao ICTU'
            elif any(k in query for k in ('bong da', 'doi bong', 'san bong', 'ictu cup', 'cup')):
                ictu_ent = 'Bóng đá ICTU'
                ictu_sp = 'bóng đá'
            if ictu_ent and ictu_ent not in sports_entities:
                sports_entities.append(ictu_ent)
                if extracted_sport is None and ictu_sp is not None:
                    extracted_sport = ictu_sp

        # Inherit previous sports entity ONLY if this query is a genuine pronoun/follow-up reference
        if not sports_entities and context.get('last_intent') == AssistantIntent.SPORTS_KNOWLEDGE.value:
            is_loc_followup = any(term in query for term in ('tinh nay', 'thanh pho nay', 'o day', 'dia phuong nay', 'con mon khac', 'mon khac thi sao', 'con mon nao', 'cac mon khac', 'con mon gi'))
            is_followup = is_loc_followup or any(term in query for term in (
                'anh ay', 'cau thu nay', 'cau thu do', 'ong ay', 'co ay', 'chi ay',
                'tay vot nay', 'tay vot do', 'vdv nay', 'vdv do', 'van dong vien nay', 'van dong vien do',
                'nguoi nay', 'nguoi do', 'doi nay', 'doi do', 'clb nay', 'clb do',
                'cau lac bo nay', 'cau lac bo do', 'svd nay', 'svd do', 'san nay', 'san do',
                'ho', 'ca hai', 'hai nguoi nay', 'cac cau thu nay', 'cac vdv nay', 'hai cau thu nay',
                'dang thi dau cho', 'dang thi dau o', 'dang choi cho', 'choi cho doi nao', 'da cho doi nao',
                'thi dau cho clb nao', 'thi dau cho doi nao', 'dang da cho', 'dang thi dau', 'dang choi',
                'sinh nam bao nhieu', 'sinh ngay nao', 'sinh o dau', 'que o dau', 'bao nhieu tuoi', 'co bao nhieu ban thang',
                'danh hieu', 'vo dich nam nao', 'thanh tich gi', 'da giai nghe chua', 'giai nghe chua',
                'quoc tich gi', 'trang thai thi dau', 'qua trinh thi dau',
                'thang ai', 'danh bai ai', 'ha ai', 'thang doi nao', 'danh bai doi nao', 'ha doi nao',
                'to chuc o dau', 'dien ra o dau', 'dang cai o dau', 'vua pha luoi', 'ai ghi ban'
            ))
            if is_loc_followup:
                prev_str = " ".join(context.get('sports_entities', [])) + " " + str(context.get('sports_entity', '')) + " " + str(context.get('location', ''))
                norm_prev = normalize_text(prev_str)
                loc_target = None
                if any(k in norm_prev for k in ('thai nguyen', 'ictu')):
                    loc_target = 'Thái Nguyên'
                elif any(k in norm_prev for k in ('ha noi', 'hanoi', 'thu do')):
                    loc_target = 'Hà Nội'
                elif any(k in norm_prev for k in ('tp.hcm', 'tphcm', 'ho chi minh', 'sai gon')):
                    loc_target = 'TP.HCM'

                if loc_target:
                    if any(k in query for k in ('bong chuyen', 'volleyball')):
                        sports_entities.append(f"Bóng chuyền {loc_target}")
                        extracted_sport = 'bóng chuyền'
                    elif any(k in query for k in ('bong ro', 'basketball')):
                        sports_entities.append(f"Bóng rổ {loc_target}")
                        extracted_sport = 'bóng rổ'
                    elif any(k in query for k in ('cau long', 'badminton')):
                        sports_entities.append(f"Cầu lông {loc_target}")
                        extracted_sport = 'cầu lông'
                    elif any(k in query for k in ('bong ban', 'table tennis')):
                        sports_entities.append(f"Bóng bàn {loc_target}")
                        extracted_sport = 'bóng bàn'
                    elif any(k in query for k in ('mon khac', 'con mon nao', 'con mon gi', 'the thao')):
                        sports_entities.append(f"Thể thao {loc_target}")
                    elif any(k in query for k in ('clb', 'doi bong', 'doi nao')):
                        sports_entities.append(f"Bóng đá {loc_target}")
                        extracted_sport = 'bóng đá'

            # Do not inherit previous athlete/team if sport has explicitly changed
            if is_followup and not sports_entities:
                prev_sport_type = context.get('sport_type')
                if not extracted_sport or not prev_sport_type or extracted_sport == prev_sport_type:
                    prev_entities = context.get('sports_entities')
                    if prev_entities and isinstance(prev_entities, list):
                        for pe in prev_entities:
                            if pe not in sports_entities:
                                sports_entities.append(pe)
                    elif context.get('sports_entity'):
                        sports_entities.append(context.get('sports_entity'))
                    if extracted_sport is None:
                        extracted_sport = prev_sport_type

        # Preserve multiple previously resolved entities for plural/pronominal follow-ups.
        if context.get("sports_entities") and any(term in query for term in ("ho dang", "hai nguoi", "hai cau thu", "ca hai", "so sanh", "thi dau o dau", "dang thi dau")):
            sports_entities = list(context["sports_entities"])
        # Resume venue search using the previous search sport when the user refers back to it.
        if extracted_sport is None and context.get("last_search") and any(term in query for term in ("tim san bong luc nay", "san bong luc nay", "mon do", "loai san do")):
            extracted_sport = context["last_search"].get("sport_type") or context.get("sport_type")

        sports_entity = sports_entities[0] if sports_entities else None
        active_entity = sports_res.active_entity if sports_res.active_entity is not None else sports_entity
        recent_entities = sports_res.recent_entities
        if sports_res.is_return_to_business:
                extracted_sport = None
                if context.get('last_search'):
                    extracted_sport = context['last_search'].get('sport_type') or context.get('sport_type')
        elif sports_res.sport:
            extracted_sport = sports_res.sport
        elif extracted_sport is None and sports_matches:
            extracted_sport = sports_matches[0][2]

        venue_names = self._venue_names(query)
        venue_name = venue_names[0] if venue_names else None

        result = IntentEntities(
            sport_type=extracted_sport,
            court_type=self._court_type(query),
            venue_name=venue_name,
            location=extract_location(query) or sports_res.location,
            date=self._date(query, today),
            start_time=start_time,
            end_time=end_time,
            preferred_time=self._preferred_time(query),
            max_price=self._price(query),
            number_of_players=self._players(query),
            booking_code=self._booking_code(query),
            sports_entity=sports_entity,
            active_entity=active_entity,
            entity_type=sports_res.entity_type,
            competition=sports_res.competition,
            year=sports_res.year,
            recent_entities=recent_entities,
            current_topic=sports_res.topic,
            target_trophy=sports_res.target_trophy,
            rewritten_query=sports_res.rewritten_query,
            sports_entities=sports_entities,
            venue_names=venue_names,
            sport_types=sport_types,
            athlete=sports_res.athlete,
            team=sports_res.team,
            is_return_to_business=sports_res.is_return_to_business,
            is_conditional=sports_res.is_conditional,
            conditional_note=sports_res.conditional_note,
            is_meme_or_joke=sports_res.is_meme_or_joke,
            explicit_entity_mention=sports_res.explicit_entity_mention,
        )
        aliases = {
            'sport_type': ('sport_type',), 'court_type': ('court_type',), 'venue_name': ('venue_name', 'field_name'),
            'location': ('location',), 'date': ('date', 'booking_date'),
            'start_time': ('start_time',), 'end_time': ('end_time',),
            'preferred_time': ('preferred_time',), 'max_price': ('max_price', 'price_max'),
            'number_of_players': ('number_of_players', 'people'),
            'booking_code': ('booking_code',),
            'active_entity': ('active_entity', 'sports_entity'),
        }
        for target, keys in aliases.items():
            if getattr(result, target) is None:
                if target == 'active_entity' and result.explicit_entity_mention:
                    continue
                if target == 'active_entity' and result.sport_type and context.get('sport_type') and result.sport_type != context.get('sport_type'):
                    continue
                if sports_res.is_return_to_business and context.get('business_context'):
                    value = next((context['business_context'].get(key) for key in keys if context['business_context'].get(key) is not None), None)
                    if value is None:
                        value = next((context.get(key) for key in keys if context.get(key) is not None), None)
                else:
                    value = next((context.get(key) for key in keys if context.get(key) is not None), None)
                if value is not None:
                    setattr(result, target, value)
        return result

    @staticmethod
    def _starts_new_request(query: str, entities: IntentEntities, context: dict[str, Any]) -> bool:
        if any(term in query for term in (
            'thoi tim san', 'quay lai tim san', 'quay lai dat san', 'tim san luc nay', 'san luc nay',
            'dat san luc nay', 'thoi xem san', 'quay lai xem san', 'thoi kiem san', 'tim san bong luc nay',
            'tiep tuc tim san', 'quay lai san', 'quay lai luc nay', 'quay lai'
        )):
            return False
        explicitly_searching = any(term in query for term in (
            'tim san', 'tim co so', 'kiem san', 'goi y san', 'toi muon san', 'muon tim san', 'dat san',
        ))
        from_sports_to_search = (context.get('last_intent') == AssistantIntent.SPORTS_KNOWLEDGE.value and explicitly_searching)
        from_search_to_sports = (context.get('last_intent') != AssistantIntent.SPORTS_KNOWLEDGE.value and entities.sports_entity is not None)
        previous_sport = context.get('sport_type')
        is_sports_context = context.get('last_intent') == AssistantIntent.SPORTS_KNOWLEDGE.value
        is_sports_followup = is_sports_context and any(term in query for term in (
            'tinh nay', 'thanh pho nay', 'tp nay', 'dia phuong nay', 'o day', 'con mon', 'mon khac', 'cac mon', 'co doi',
            'con ', 'the con', 'vay con', 'anh ay', 'ong ay', 'ong nay', 'cau thu nay', 'cau thu do'
        ))
        changed_sport = bool(entities.sport_type and previous_sport and entities.sport_type != previous_sport)
        if is_sports_followup or (is_sports_context and not explicitly_searching):
            changed_sport = False
        previous_location = context.get('location')
        changed_location = bool(entities.location and previous_location and entities.location != previous_location)
        if is_sports_context and not explicitly_searching:
            changed_location = False
        previous_entity = context.get('active_entity') or context.get('sports_entity')
        changed_entity = bool(entities.sports_entity and previous_entity and entities.sports_entity != previous_entity)
        if is_sports_context and not explicitly_searching:
            changed_entity = False
        return explicitly_searching or changed_sport or changed_location or changed_entity or from_sports_to_search or from_search_to_sports

    @staticmethod
    def _court_type(query: str) -> str | None:
        people = re.search(r'\b(?:san\s+)?(?:bong\s+)?(\d{1,2})\s*nguoi\b', query)
        if people:
            return f'{int(people[1])} người'
        if 'san don' in query:
            return 'sân đơn'
        if 'san doi' in query:
            return 'sân đôi'
        if 'trong nha' in query:
            return 'trong nhà'
        if 'ngoai troi' in query:
            return 'ngoài trời'
        return None

    @staticmethod
    def _preferred_time(query: str) -> str | None:
        if any(term in query for term in ('buoi sang', 'sang som')):
            return 'morning'
        if 'buoi chieu' in query:
            return 'afternoon'
        if any(term in query for term in ('buoi toi', 'gio toi', 'toi nay', 'toi mai')) or re.search(r'\b(?:toi\s+(?:thu|ngay|\d|luc|khoang)|\d{1,2}(?::\d{2})?\s*(?:h|gio)?\s*toi)\b', query):
            return 'evening'
        return None

    @staticmethod
    def _booking_code(query: str) -> str | None:
        match = re.search(r'\bSH[- ]?[A-Z0-9-]{3,}\b', query.upper())
        return match[0].replace(' ', '-') if match else None

    @staticmethod
    def _venue_names(query: str) -> list[str]:
        quoted = re.findall(r'["“]([^"”]{2,80})["”]', query)
        if quoted:
            return [q.strip() for q in quoted if q.strip()]
        unquoted = re.findall(r'\bsan\s+([a-zA-Z0-9\s_-]{1,30}?)(?=\s+(?:va|va\s+san|gia|,|\.|\?|$))', query, flags=re.IGNORECASE)
        reserved_words = {'bong', 'cau long', 'pickleball', 'tennis', 'bong ro', 'bong chuyen', 'don', 'doi', 'trong nha', 'ngoai troi', 'con trong', 're', 'dep', 'tot', 'nao', 'nay', 'do'}
        filtered = []
        for m in unquoted:
            cand = m.strip()
            if cand and cand not in reserved_words and len(cand) >= 1:
                filtered.append(f"sân {cand}")
        if len(filtered) >= 2:
            return filtered
        return []

    @staticmethod
    def _venue_name(query: str) -> str | None:
        names = IntentRouter._venue_names(query)
        if names:
            return names[0]
        quoted = re.search(r'["“]([^"”]{2,80})["”]', query)
        return quoted[1].strip() if quoted else None

    @staticmethod
    def _players(query: str) -> int | None:
        match = re.search(r'\b(\d{1,3})\s*(?:nguoi|thanh vien)\b', query)
        return int(match[1]) if match else None

    @staticmethod
    def _price(query: str) -> float | None:
        match = re.search(r'(?:duoi|toi da|khong qua|<=?)\s*([\d.,]+)\s*(trieu|k|nghin|d|dong)?', query)
        if not match:
            return None
        raw, unit = match[1], match[2]
        value = float(raw.replace('.', '').replace(',', '.'))
        return value * (1_000_000 if unit == 'trieu' else 1_000 if unit in ('k', 'nghin') else 1)

    @staticmethod
    def _times(query: str) -> tuple[str | None, str | None]:
        is_evening = any(term in query for term in ('toi nay', 'toi mai', 'buoi toi', 'gio toi')) or bool(re.search(r'\b(?:toi\s+(?:thu|ngay|\d|luc|khoang)|\d{1,2}(?::\d{2})?\s*(?:h|gio)?\s*toi)\b', query))
        range_match = re.search(r'\b([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:-|–|den|toi)\s*([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:h|gio)?\b', query)
        if range_match:
            h1, m1 = int(range_match[1]), int(range_match[2] or 0)
            h2, m2 = int(range_match[3]), int(range_match[4] or 0)
            if is_evening and h1 < 12 and h2 <= 12:
                h1 += 12
                h2 += 12
            return f'{h1:02d}:{m1:02d}', f'{h2:02d}:{m2:02d}'
        match = re.search(r'\b([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:h|gio)\b', query)
        if not match:
            return None, None
        hour = int(match[1])
        if is_evening and hour < 12:
            hour += 12
        return f'{hour:02d}:{int(match[2] or 0):02d}', None

    @staticmethod
    def _date(query: str, today: date) -> str | None:
        if 'hom nay' in query or 'toi nay' in query:
            return today.isoformat()
        if 'ngay mai' in query or 'toi mai' in query or re.search(r'\bmai\b', query):
            return (today + timedelta(days=1)).isoformat()
        if 'ngay kia' in query or 'ngay mot' in query:
            return (today + timedelta(days=2)).isoformat()
        if 'cuoi tuan nay' in query or 'cuoi tuan' in query:
            days = (5 - today.weekday()) % 7
            return (today + timedelta(days=days)).isoformat()
        iso = re.search(r'\b(20\d{2})-(\d{1,2})-(\d{1,2})\b', query)
        short = re.search(r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](20\d{2}))?\b(?!\s*(?:h|gio|pm|am))\b', query)
        try:
            if iso:
                return date(int(iso[1]), int(iso[2]), int(iso[3])).isoformat()
            if short:
                # If separator is '-' and there is no year and no explicit 'ngay/thang' keyword,
                # check if this is likely a time range (e.g., 8-9) or preceded by time markers
                sep = query[short.start(0):short.end(0)]
                is_hyphen_range = '-' in sep and not short.group(3)
                has_date_context = bool(re.search(r'\b(?:ngay|thang|date)\s*' + re.escape(sep), query))
                is_time_marked = bool(re.search(r'\b(?:tu|luc|khoang|tam|tu\s+khoang)\s*' + re.escape(sep), query))
                if is_hyphen_range and (is_time_marked or not has_date_context and not ('/' in sep)):
                    pass
                else:
                    return date(int(short[3] or today.year), int(short[2]), int(short[1])).isoformat()
        except ValueError:
            return None
        for label, weekday in WEEKDAYS.items():
            if label in query:
                return (today + timedelta(days=(weekday - today.weekday()) % 7)).isoformat()
        return None
