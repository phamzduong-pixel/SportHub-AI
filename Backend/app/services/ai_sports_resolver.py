import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


def normalize_text(value: str) -> str:
    """Normalize Vietnamese text to lowercase ASCII without diacritics."""
    if not value:
        return ""
    normalized = unicodedata.normalize('NFD', value.casefold())
    return ''.join(char for char in normalized if unicodedata.category(char) != 'Mn').replace('đ', 'd')


NUMBER_WORDS_MAP = {
    'khong': '0',
    'mot': '1',
    'hai': '2',
    'ba': '3',
    'bon': '4',
    'tu': '4',
    'nam': '5',
    'sau': '6',
    'bay': '7',
    'tam': '8',
    'chin': '9',
    'muoi': '10',
    'muoi mot': '11',
    'muoi hai': '12',
    'muoi ba': '13',
    'muoi bon': '14',
    'muoi lam': '15',
    'muoi sau': '16',
    'muoi bay': '17',
    'muoi tam': '18',
    'muoi chin': '19',
    'hai muoi': '20',
}


def normalize_sports_numbers(text: str) -> str:
    """Normalize numbers written as words to digits when associated with common sports honorifics/prefixes.
    
    Examples:
    - 'anh bay' -> 'anh 7'
    - 'anh muoi' -> 'anh 10'
    - 'anh chin' -> 'anh 9'
    - 'so bay' -> 'so 7'
    - 'ao so muoi' -> 'ao so 10'
    """
    norm = normalize_text(text)
    prefixes = ['anh', 'chi', 'chu', 'cau thu', 'tay vot', 'vdv', 'so', 'ao so', 'ao']
    for prefix in prefixes:
        for word, digit in sorted(NUMBER_WORDS_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            pattern = r'\b' + re.escape(prefix) + r'\s+' + re.escape(word) + r'\b'
            norm = re.sub(pattern, f"{prefix} {digit}", norm)
    return norm


@dataclass
class EntityDescriptor:
    canonical_name: str
    entity_type: str  # 'athlete', 'team', 'sport', 'competition', 'location', 'venue'
    sport: str | None = None
    location: str | None = None
    aliases: tuple[str, ...] = ()
    notes: str | None = None


# Generic Multi-Sport, Multi-Entity Registry
GLOBAL_ENTITY_CATALOG: list[EntityDescriptor] = [
    # ── ATHLETES: Football ──────────────────────────────────────────────
    EntityDescriptor(
        canonical_name='Lionel Messi',
        entity_type='athlete',
        sport='bóng đá',
        location='Argentina',
        aliases=('messi', 'lionel messi', 'leo messi', 'leo', 'm10', 'anh 10', 'anh muoi', 'la pulga', 'el pulga', 'so 10', 'ao so 10'),
        notes='Lionel Messi - Siêu sao bóng đá Argentina (M10)',
    ),
    EntityDescriptor(
        canonical_name='Cristiano Ronaldo',
        entity_type='athlete',
        sport='bóng đá',
        location='Bồ Đào Nha',
        aliases=('ronaldo', 'cristiano ronaldo', 'cristiano', 'cr7', 'c ronaldo', 'c.ronaldo', 'anh 7', 'chi 7', 'anh bay', 'chi bay', 'so 7', 'ao so 7'),
        notes='Cristiano Ronaldo - Siêu sao bóng đá Bồ Đào Nha (CR7)',
    ),
    EntityDescriptor(
        canonical_name='Kylian Mbappé',
        entity_type='athlete',
        sport='bóng đá',
        location='Pháp',
        aliases=('mbappe', 'kylian mbappe', 'm3p', 'ninja rua'),
        notes='Kylian Mbappé (M3P / Ninja rùa)',
    ),
    EntityDescriptor(
        canonical_name='Erling Haaland',
        entity_type='athlete',
        sport='bóng đá',
        location='Na Uy',
        aliases=('haaland', 'erling haaland'),
        notes='Erling Haaland',
    ),
    EntityDescriptor(
        canonical_name='Neymar',
        entity_type='athlete',
        sport='bóng đá',
        location='Brazil',
        aliases=('neymar', 'neymar jr', 'ney'),
        notes='Neymar Jr',
    ),
    EntityDescriptor(
        canonical_name='Ronaldo de Lima',
        entity_type='athlete',
        sport='bóng đá',
        location='Brazil',
        aliases=('r9', 'ro beo', 'nguoi ngoai hanh tinh', 'ronaldo de lima', 'ronaldo beo'),
        notes='Ronaldo de Lima (R9 / Rô béo)',
    ),
    EntityDescriptor(
        canonical_name='Harry Maguire',
        entity_type='athlete',
        sport='bóng đá',
        location='Anh',
        aliases=('harry maguire', 'maguire', 'dang maguire', 'chua te maguire', 'mac hai'),
        notes='Harry Maguire',
    ),
    EntityDescriptor(
        canonical_name='Romelu Lukaku',
        entity_type='athlete',
        sport='bóng đá',
        location='Bỉ',
        aliases=('romelu lukaku', 'lukaku', 'lakaka'),
        notes='Romelu Lukaku',
    ),
    EntityDescriptor(
        canonical_name='Nguyễn Quang Hải',
        entity_type='athlete',
        sport='bóng đá',
        location='Hà Nội',
        aliases=('quang hai', 'nguyen quang hai', 'hai con'),
        notes='Nguyễn Quang Hải',
    ),
    EntityDescriptor(
        canonical_name='Nguyễn Hoàng Đức',
        entity_type='athlete',
        sport='bóng đá',
        location='Hải Dương',
        aliases=('hoang duc', 'nguyen hoang duc'),
        notes='Nguyễn Hoàng Đức',
    ),
    EntityDescriptor(
        canonical_name='Nguyễn Tiến Linh',
        entity_type='athlete',
        sport='bóng đá',
        location='Hải Dương',
        aliases=('tien linh', 'nguyen tien linh'),
        notes='Nguyễn Tiến Linh',
    ),
    EntityDescriptor(
        canonical_name='Đặng Văn Lâm',
        entity_type='athlete',
        sport='bóng đá',
        location='Việt Nam',
        aliases=('van lam', 'dang van lam', 'lam tay dai'),
        notes='Đặng Văn Lâm (Lâm Tây)',
    ),
    EntityDescriptor(
        canonical_name='Trần Thị Kim Thanh',
        entity_type='athlete',
        sport='bóng đá',
        location='Thái Nguyên',
        aliases=('kim thanh', 'tran thi kim thanh'),
        notes='Trần Thị Kim Thanh (Thủ môn Thái Nguyên T&T)',
    ),
    EntityDescriptor(
        canonical_name='Nguyễn Thị Bích Thùy',
        entity_type='athlete',
        sport='bóng đá',
        location='Thái Nguyên',
        aliases=('bich thuy', 'nguyen thi bich thuy'),
        notes='Nguyễn Thị Bích Thùy (Thái Nguyên T&T)',
    ),

    # ── ATHLETES: Badminton ────────────────────────────────────────────
    EntityDescriptor(
        canonical_name='Nguyễn Thùy Linh',
        entity_type='athlete',
        sport='cầu lông',
        location='Phú Thọ',
        aliases=('thuy linh', 'nguyen thuy linh', 'hoa khoi cau long'),
        notes='Nguyễn Thùy Linh (Hoa khôi cầu lông)',
    ),
    EntityDescriptor(
        canonical_name='Nguyễn Tiến Minh',
        entity_type='athlete',
        sport='cầu lông',
        location='TP.HCM',
        aliases=('tien minh', 'nguyen tien minh', 'tuong dai cau long'),
        notes='Nguyễn Tiến Minh (Tượng đài cầu lông Việt Nam)',
    ),
    EntityDescriptor(
        canonical_name='Viktor Axelsen',
        entity_type='athlete',
        sport='cầu lông',
        location='Đan Mạch',
        aliases=('axelsen', 'viktor axelsen'),
        notes='Viktor Axelsen',
    ),
    EntityDescriptor(
        canonical_name='Lin Dan',
        entity_type='athlete',
        sport='cầu lông',
        location='Trung Quốc',
        aliases=('lin dan', 'super dan'),
        notes='Lin Dan (Super Dan)',
    ),
    EntityDescriptor(
        canonical_name='Lee Chong Wei',
        entity_type='athlete',
        sport='cầu lông',
        location='Malaysia',
        aliases=('lee chong wei', 'chong wei'),
        notes='Lee Chong Wei',
    ),
    EntityDescriptor(
        canonical_name='Kento Momota',
        entity_type='athlete',
        sport='cầu lông',
        location='Nhật Bản',
        aliases=('kento momota', 'momota'),
        notes='Kento Momota',
    ),
    EntityDescriptor(
        canonical_name='An Se Young',
        entity_type='athlete',
        sport='cầu lông',
        location='Hàn Quốc',
        aliases=('an se young', 'se young'),
        notes='An Se Young',
    ),

    # ── ATHLETES: Tennis ──────────────────────────────────────────────
    EntityDescriptor(
        canonical_name='Roger Federer',
        entity_type='athlete',
        sport='tennis',
        location='Thụy Sĩ',
        aliases=('roger federer', 'federer', 'tau toc hanh', 'fedex', 'swiss maestro'),
        notes='Roger Federer (Tàu tốc hành / FedEx)',
    ),
    EntityDescriptor(
        canonical_name='Rafael Nadal',
        entity_type='athlete',
        sport='tennis',
        location='Tây Ban Nha',
        aliases=('rafael nadal', 'nadal', 'vua dat nen', 'vua san dat nen', 'king of clay'),
        notes='Rafael Nadal (Vua đất nện)',
    ),
    EntityDescriptor(
        canonical_name='Novak Djokovic',
        entity_type='athlete',
        sport='tennis',
        location='Serbia',
        aliases=('novak djokovic', 'djokovic', 'nole', 'the djoker'),
        notes='Novak Djokovic (Nole)',
    ),
    EntityDescriptor(
        canonical_name='Carlos Alcaraz',
        entity_type='athlete',
        sport='tennis',
        location='Tây Ban Nha',
        aliases=('carlos alcaraz', 'alcaraz', 'tieu federer'),
        notes='Carlos Alcaraz',
    ),
    EntityDescriptor(
        canonical_name='Jannik Sinner',
        entity_type='athlete',
        sport='tennis',
        location='Ý',
        aliases=('jannik sinner', 'sinner'),
        notes='Jannik Sinner',
    ),
    EntityDescriptor(
        canonical_name='Lý Hoàng Nam',
        entity_type='athlete',
        sport='tennis',
        location='Việt Nam',
        aliases=('ly hoang nam', 'hoang nam'),
        notes='Lý Hoàng Nam',
    ),

    # ── ATHLETES: Basketball ──────────────────────────────────────────
    EntityDescriptor(
        canonical_name='LeBron James',
        entity_type='athlete',
        sport='bóng rổ',
        location='Mỹ',
        aliases=('lebron james', 'lebron', 'king james', 'the king', 'nha vua'),
        notes='LeBron James (King James)',
    ),
    EntityDescriptor(
        canonical_name='Stephen Curry',
        entity_type='athlete',
        sport='bóng rổ',
        location='Mỹ',
        aliases=('stephen curry', 'curry', 'bep truong', 'bep truong curry', 'chef curry'),
        notes='Stephen Curry (Chef Curry)',
    ),
    EntityDescriptor(
        canonical_name='Kobe Bryant',
        entity_type='athlete',
        sport='bóng rổ',
        location='Mỹ',
        aliases=('kobe bryant', 'kobe', 'black mamba', 'mamba'),
        notes='Kobe Bryant (Black Mamba)',
    ),
    EntityDescriptor(
        canonical_name='Michael Jordan',
        entity_type='athlete',
        sport='bóng rổ',
        location='Mỹ',
        aliases=('michael jordan', 'jordan', 'ngai jordan', 'vua bong ro'),
        notes='Michael Jordan (Ngài Jordan)',
    ),

    # ── ATHLETES: Volleyball ──────────────────────────────────────────
    EntityDescriptor(
        canonical_name='Nguyễn Thị Bích Tuyền',
        entity_type='athlete',
        sport='bóng chuyền',
        location='Việt Nam',
        aliases=('nguyen thi bich tuyen', 'bich tuyen', 'khung long bong chuyen', 'khung long 420'),
        notes='Nguyễn Thị Bích Tuyền (Khủng long bóng chuyền)',
    ),
    EntityDescriptor(
        canonical_name='Trần Thị Thanh Thúy',
        entity_type='athlete',
        sport='bóng chuyền',
        location='Việt Nam',
        aliases=('tran thi thanh thuy', 'thanh thuy', '4t', 'chu cong 4t'),
        notes='Trần Thị Thanh Thúy (4T)',
    ),
    EntityDescriptor(
        canonical_name='Hoàng Thị Kiều Trinh',
        entity_type='athlete',
        sport='bóng chuyền',
        location='Việt Nam',
        aliases=('hoang thi kieu trinh', 'kieu trinh', 'hoa khoi bong chuyen'),
        notes='Hoàng Thị Kiều Trinh',
    ),

    # ── ATHLETES: Pickleball ──────────────────────────────────────────
    EntityDescriptor(
        canonical_name='Ben Johns',
        entity_type='athlete',
        sport='pickleball',
        location='Mỹ',
        aliases=('ben johns', 'vua pickleball'),
        notes='Ben Johns (Vua pickleball)',
    ),
    EntityDescriptor(
        canonical_name='Anna Leigh Waters',
        entity_type='athlete',
        sport='pickleball',
        location='Mỹ',
        aliases=('anna leigh waters', 'nu hoang pickleball'),
        notes='Anna Leigh Waters (Nữ hoàng pickleball)',
    ),
    EntityDescriptor(
        canonical_name='Quang Dương',
        entity_type='athlete',
        sport='pickleball',
        location='Mỹ',
        aliases=('quang duong', 'duong quang', 'than dong pickleball'),
        notes='Quang Dương (Thần đồng pickleball gốc Việt)',
    ),

    # ── TEAMS / CLUBS ─────────────────────────────────────────────────
    EntityDescriptor(
        canonical_name='Thái Nguyên T&T',
        entity_type='team',
        sport='bóng đá',
        location='Thái Nguyên',
        aliases=('thai nguyen t&t', 'thai nguyen tt', 'clb nu thai nguyen', 'doi nu thai nguyen', 'bong da nu thai nguyen', 'doi bong nu thai nguyen', 'clb bong da nu thai nguyen'),
        notes='CLB Bóng đá Nữ Thái Nguyên T&T',
    ),
    EntityDescriptor(
        canonical_name='Bóng đá nam Thái Nguyên',
        entity_type='team',
        sport='bóng đá',
        location='Thái Nguyên',
        aliases=('fc thai nguyen', 'bong da nam thai nguyen', 'doi bong nam thai nguyen', 'clb bong da nam thai nguyen', 'doi nam thai nguyen', 'cau lac bo bong da nam thai nguyen'),
        notes='CLB Bóng đá nam Thái Nguyên (FC Thái Nguyên)',
    ),
    EntityDescriptor(
        canonical_name='Bóng đá ICTU',
        entity_type='team',
        sport='bóng đá',
        location='Thái Nguyên',
        aliases=('bong da ictu', 'doi bong ictu', 'bong da sinh vien ictu', 'truong dai hoc cong nghe thong tin va truyen thong', 'cntt va truyen thong thai nguyen', 'truong cntt va truyen thong thai nguyen', 'truong dh cntt&tt', 'truong dh cntt va tt', 'dai hoc cong nghe thong tin va truyen thong'),
        notes='Đội tuyển bóng đá sinh viên ICTU',
    ),
    EntityDescriptor(
        canonical_name='Đội tuyển Việt Nam',
        entity_type='team',
        sport='bóng đá',
        location='Việt Nam',
        aliases=('doi tuyen viet nam', 'tuyen viet nam', 'doi tuyen quoc gia', 'doi tuyen bong da nam', 'doi tuyen bong da nu', 'tuyen quoc gia'),
        notes='Đội tuyển Quốc gia Việt Nam',
    ),
    EntityDescriptor(
        canonical_name='Inter Miami CF',
        entity_type='team',
        sport='bóng đá',
        location='Mỹ',
        aliases=('inter miami', 'inter miami cf', 'clb inter miami'),
        notes='Inter Miami CF',
    ),
    EntityDescriptor(
        canonical_name='Al-Nassr FC',
        entity_type='team',
        sport='bóng đá',
        location='Ả Rập Xê Út',
        aliases=('al-nassr', 'al nassr', 'al nassr fc', 'clb al-nassr'),
        notes='Al-Nassr FC',
    ),
    EntityDescriptor(
        canonical_name='Đội tuyển Argentina',
        entity_type='team',
        sport='bóng đá',
        location='Argentina',
        aliases=('argentina', 'doi tuyen argentina', 'tuyen argentina', 'doi bong argentina', 'la albiceleste', 'albiceleste'),
        notes='Đội tuyển Quốc gia Argentina (La Albiceleste)',
    ),
    EntityDescriptor(
        canonical_name='Đội tuyển Pháp',
        entity_type='team',
        sport='bóng đá',
        location='Pháp',
        aliases=('phap', 'doi tuyen phap', 'tuyen phap', 'doi bong phap', 'les bleus'),
        notes='Đội tuyển Quốc gia Pháp (Les Bleus)',
    ),
    EntityDescriptor(
        canonical_name='Đội tuyển Brazil',
        entity_type='team',
        sport='bóng đá',
        location='Brazil',
        aliases=('brazil', 'doi tuyen brazil', 'tuyen brazil', 'doi bong brazil', 'selecao'),
        notes='Đội tuyển Quốc gia Brazil (Seleção)',
    ),
    EntityDescriptor(
        canonical_name='Đội tuyển Bồ Đào Nha',
        entity_type='team',
        sport='bóng đá',
        location='Bồ Đào Nha',
        aliases=('bo dao nha', 'doi tuyen bo dao nha', 'tuyen bo dao nha', 'doi bong bo dao nha', 'selecao das quinas'),
        notes='Đội tuyển Quốc gia Bồ Đào Nha',
    ),
    EntityDescriptor(
        canonical_name='Công An Hà Nội',
        entity_type='team',
        sport='bóng đá',
        location='Hà Nội',
        aliases=('cong an ha noi', 'cahn', 'clb cahn', 'clb cong an ha noi'),
        notes='CLB Công An Hà Nội',
    ),
    EntityDescriptor(
        canonical_name='Becamex Bình Dương',
        entity_type='team',
        sport='bóng đá',
        location='Bình Dương',
        aliases=('becamex binh duong', 'binh duong fc', 'clb becamex binh duong', 'clb binh duong'),
        notes='CLB Becamex Bình Dương',
    ),
    EntityDescriptor(
        canonical_name='Phù Đổng Ninh Bình',
        entity_type='team',
        sport='bóng đá',
        location='Ninh Bình',
        aliases=('phu dong ninh binh', 'clb phu dong ninh binh', 'phu dong'),
        notes='CLB Phù Đổng Ninh Bình',
    ),
    EntityDescriptor(
        canonical_name='Saigon Heat',
        entity_type='team',
        sport='bóng rổ',
        location='TP.HCM',
        aliases=('saigon heat', 'clb saigon heat'),
        notes='Saigon Heat',
    ),

    # ── COMPETITIONS / TOURNAMENTS ─────────────────────────────────────
    EntityDescriptor(
        canonical_name='FIFA World Cup',
        entity_type='competition',
        sport='bóng đá',
        aliases=('world cup', 'fifa world cup', 'wc', 'cup world cup', 'cup the gioi', 'giai vo dich the gioi'),
        notes='FIFA World Cup',
    ),
    EntityDescriptor(
        canonical_name='UEFA Champions League',
        entity_type='competition',
        sport='bóng đá',
        aliases=('uefa champions league', 'champions league', 'c1', 'cup c1', 'cup chau au'),
        notes='UEFA Champions League (Cúp C1)',
    ),
    EntityDescriptor(
        canonical_name='Ballon d\'Or',
        entity_type='competition',
        sport='bóng đá',
        aliases=('ballon d\'or', 'ballon dor', 'qua bong vang', 'qua bong vang the gioi'),
        notes='Quả bóng vàng (Ballon d\'Or)',
    ),
    EntityDescriptor(
        canonical_name='V.League 1',
        entity_type='competition',
        sport='bóng đá',
        location='Việt Nam',
        aliases=('v-league', 'vleague', 'v.league', 'v league', 'vleague 1'),
        notes='Giải Vô địch Quốc gia V.League 1',
    ),
    EntityDescriptor(
        canonical_name='ICTU CUP',
        entity_type='competition',
        sport='bóng đá',
        location='Thái Nguyên',
        aliases=('ictu cup', 'giai ictu cup', 'bong da ictu cup'),
        notes='Giải bóng đá sinh viên ICTU CUP',
    ),
    EntityDescriptor(
        canonical_name='BWF World Tour',
        entity_type='competition',
        sport='cầu lông',
        aliases=('bwf', 'bwf world tour', 'giai cau long the gioi'),
        notes='BWF World Tour',
    ),
    EntityDescriptor(
        canonical_name='Grand Slam',
        entity_type='competition',
        sport='tennis',
        aliases=('grand slam', 'wimbledon', 'us open', 'australian open', 'roland garros'),
        notes='Grand Slam Tennis',
    ),
    EntityDescriptor(
        canonical_name='NBA',
        entity_type='competition',
        sport='bóng rổ',
        aliases=('nba', 'giai bong ro nha nghe my'),
        notes='NBA',
    ),
    EntityDescriptor(
        canonical_name='VTV Cup',
        entity_type='competition',
        sport='bóng chuyền',
        location='Việt Nam',
        aliases=('vtv cup', 'giai bong chuyen vtv cup'),
        notes='VTV Cup',
    ),
    EntityDescriptor(
        canonical_name='PPA Tour',
        entity_type='competition',
        sport='pickleball',
        aliases=('ppa tour', 'ppa'),
        notes='PPA Tour',
    ),

    # ── LOCATIONS ─────────────────────────────────────────────────────
    EntityDescriptor(
        canonical_name='Việt Nam',
        entity_type='location',
        aliases=('viet nam', 'vietnam', 'vn', 'toan quoc', 'trong nuoc'),
        notes='Việt Nam',
    ),
    EntityDescriptor(
        canonical_name='Thái Nguyên',
        entity_type='location',
        aliases=('thai nguyen', 'tinh thai nguyen', 'tp thai nguyen', 'thanh pho thai nguyen'),
        notes='Thái Nguyên',
    ),
    EntityDescriptor(
        canonical_name='Hà Nội',
        entity_type='location',
        aliases=('ha noi', 'hanoi', 'thu do ha noi', 'thu do'),
        notes='Hà Nội',
    ),
    EntityDescriptor(
        canonical_name='TP.HCM',
        entity_type='location',
        aliases=('tp hcm', 'tphcm', 'tp ho chi minh', 'thanh pho ho chi minh', 'sai gon', 'tp.hcm'),
        notes='TP. Hồ Chí Minh',
    ),
    EntityDescriptor(
        canonical_name='Đà Nẵng',
        entity_type='location',
        aliases=('da nang', 'tp da nang'),
        notes='Đà Nẵng',
    ),
    EntityDescriptor(
        canonical_name='Phú Thọ',
        entity_type='location',
        aliases=('phu tho', 'tinh phu tho'),
        notes='Phú Thọ',
    ),
    EntityDescriptor(
        canonical_name='Hải Dương',
        entity_type='location',
        aliases=('hai duong', 'tinh hai duong'),
        notes='Hải Dương',
    ),
    EntityDescriptor(
        canonical_name='Đồng Nai',
        entity_type='location',
        aliases=('dong nai', 'tinh dong nai'),
        notes='Đồng Nai',
    ),
    EntityDescriptor(
        canonical_name='Bình Dương',
        entity_type='location',
        aliases=('binh duong', 'tinh binh duong'),
        notes='Bình Dương',
    ),
    EntityDescriptor(
        canonical_name='Ninh Bình',
        entity_type='location',
        aliases=('ninh binh', 'tinh ninh binh'),
        notes='Ninh Bình',
    ),

    # ── SPORTS ────────────────────────────────────────────────────────
    EntityDescriptor(
        canonical_name='bóng đá',
        entity_type='sport',
        aliases=('bong da', 'da bong', 'football', 'soccer', 'mon da bong', 'mon bong da', 'san co'),
        notes='Môn bóng đá',
    ),
    EntityDescriptor(
        canonical_name='cầu lông',
        entity_type='sport',
        aliases=('cau long', 'danh cau long', 'badminton', 'mon cau long', 'choi cau long'),
        notes='Môn cầu lông',
    ),
    EntityDescriptor(
        canonical_name='tennis',
        entity_type='sport',
        aliases=('tennis', 'quan vot', 'danh tennis', 'choi tennis', 'mon tennis', 'mon quan vot'),
        notes='Môn tennis',
    ),
    EntityDescriptor(
        canonical_name='pickleball',
        entity_type='sport',
        aliases=('pickleball', 'pickle ball', 'danh pickleball', 'choi pickleball', 'mon pickleball'),
        notes='Môn pickleball',
    ),
    EntityDescriptor(
        canonical_name='bóng rổ',
        entity_type='sport',
        aliases=('bong ro', 'basketball', 'choi bong ro', 'mon bong ro'),
        notes='Môn bóng rổ',
    ),
    EntityDescriptor(
        canonical_name='bóng chuyền',
        entity_type='sport',
        aliases=('bong chuyen', 'volleyball', 'choi bong chuyen', 'mon bong chuyen'),
        notes='Môn bóng chuyền',
    ),
]


SPORT_KEYWORDS_MAP = {
    'bong da': 'bóng đá',
    'da bong': 'bóng đá',
    'football': 'bóng đá',
    'soccer': 'bóng đá',
    'cau long': 'cầu lông',
    'badminton': 'cầu lông',
    'pickleball': 'pickleball',
    'pickle ball': 'pickleball',
    'tennis': 'tennis',
    'quan vot': 'tennis',
    'bong ro': 'bóng rổ',
    'basketball': 'bóng rổ',
    'bong chuyen': 'bóng chuyền',
    'volleyball': 'bóng chuyền',
}


@dataclass
class SportsResolutionResult:
    entities: list[str] = field(default_factory=list)
    active_entity: str | None = None
    entity_type: str | None = None
    recent_entities: list[str] = field(default_factory=list)
    sport: str | None = None
    location: str | None = None
    competition: str | None = None
    year: str | None = None
    team: str | None = None
    athlete: str | None = None
    topic: str | None = None
    target_trophy: str | None = None
    previous_intent: str | None = None
    is_follow_up: bool = False
    is_return_to_business: bool = False
    is_conditional: bool = False
    conditional_note: str | None = None
    is_meme_or_joke: bool = False
    rewritten_query: str | None = None
    notes: list[str] = field(default_factory=list)


class SportsContextResolver:
    """Generic Context-Aware Resolver for Sports, Entities, Pronouns, Sports Shifts and Location Context."""

    PERSON_PRONOUNS = (
        'anh ay', 'ong ay', 'ong nay', 'anh nay', 'cau thu nay', 'cau thu do',
        'tay vot nay', 'tay vot do', 'vdv nay', 'vdv do', 'van dong vien nay',
        'van dong vien do', 'nguoi nay', 'nguoi do', 'han', 'chu ay', 'co ay', 'chi ay',
        'bac nay', 'sieu sao nay', 'tien dao nay', 'tien ve nay',
        'ho', 'doi nay', 'doi do', 'clb nay', 'clb do', 'doi thang', 'doi vo dich', 'quan quan', 'nha vo dich',
    )
    SPORT_DEICTICS = (
        'mon nay', 'bo mon nay', 'mon the thao nay', 'mon do', 'bo mon do',
    )
    LOCATION_DEICTICS = (
        'noi nay', 'o day', 'dia phuong nay', 'tinh nay', 'thanh pho nay', 'khu vuc nay', 'o do', 'cho nay',
    )
    TEAM_DEICTICS = (
        'doi nay', 'clb nay', 'cau lac bo nay', 'doi bong nay', 'doi do', 'clb do', 'ho',
    )

    AMBIGUOUS_NICKNAMES = {
        'anh 7', 'anh bay', 'anh 10', 'anh muoi', 'tau toc hanh', 'vua dat nen', 'vua san dat nen', 'ninja rua',
    }

    @classmethod
    def resolve(cls, query: str, context: dict[str, Any] | None = None) -> SportsResolutionResult:
        context = context or {}
        norm_raw = normalize_text(query)
        norm_query = normalize_sports_numbers(query)

        # ── 1. Context Extraction from Previous Turns ─────────────────────
        prev_intent = context.get('last_intent')
        prev_sport = context.get('sport_type') or context.get('sport')
        prev_location = context.get('location')
        prev_active_entity = context.get('active_entity') or context.get('sports_entity')
        prev_entity_type = context.get('entity_type')
        if not prev_entity_type and prev_active_entity:
            for desc in GLOBAL_ENTITY_CATALOG:
                if desc.canonical_name == prev_active_entity or normalize_text(desc.canonical_name) == normalize_text(prev_active_entity):
                    prev_entity_type = desc.entity_type
                    break
        prev_competition = context.get('competition')
        prev_year = context.get('year') or context.get('competition_year')
        prev_recent_entities = list(context.get('recent_entities') or [])
        if prev_active_entity and prev_active_entity not in prev_recent_entities:
            prev_recent_entities.insert(0, prev_active_entity)

        # Year detection in current query
        year_match = re.search(r'\b(20\d{2}|19\d{2})\b', query)
        effective_year = year_match.group(1) if year_match else prev_year

        # ── 2. Detect Follow-up Indicator & Pronouns ───────────────────────
        is_follow_up_phrase = any(re.search(r'\b' + re.escape(p) + r'\b', norm_query) for p in (
            'con ', 'the con', 'vay con', 'con thi sao', 'thi sao', 'the nao', 'nhu the nao', 'the con ai', 'con ong nao', 'con cau thu nao',
            'con nguoi nay', 'con ai khac', 'the ai', 'con o dau', 'con clb nao', 'vay ', 'the thi',
            'con c1', 'con wc', 'con world cup', 'con qua bong vang', 'con may qua', 'o day thi sao', 'o do thi sao',
        )) or norm_query.startswith('con ') or norm_query.startswith('the con ') or norm_query.startswith('vay con ') or norm_query.startswith('vay ')

        has_person_pronoun = any(re.search(r'\b' + re.escape(p) + r'\b', norm_query) for p in cls.PERSON_PRONOUNS)
        has_sport_deictic = any(re.search(r'\b' + re.escape(p) + r'\b', norm_query) for p in cls.SPORT_DEICTICS)
        has_location_deictic = any(re.search(r'\b' + re.escape(p) + r'\b', norm_query) for p in cls.LOCATION_DEICTICS)
        has_team_deictic = any(re.search(r'\b' + re.escape(p) + r'\b', norm_query) for p in cls.TEAM_DEICTICS)

        # ── 3. Detect Sports Memes / Humor ─────────────────────────────────
        is_meme = any(p in norm_query for p in (
            'di bo vuot toc', 'vuot toc', 'ganh team', 'tau hai', 'hai huoc', 'siuuu', 'siu',
            'co biet da bong khong', 'biet da bong khong', 'ai la goat', 'goat cua bong da',
            'dang maguire', 'chua te maguire', 'lakaka'
        ))

        # ── 4. Detect Explicit Sport Context from Query ───────────────────
        detected_sport = None
        for kw, sp in sorted(SPORT_KEYWORDS_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if re.search(r'\b' + re.escape(kw) + r'\b', norm_query) or re.search(r'\b' + re.escape(kw) + r'\b', norm_raw):
                detected_sport = sp
                break

        # If sport changed explicitly (e.g. "còn cầu lông?"), update effective sport
        if detected_sport:
            effective_sport = detected_sport
        elif has_sport_deictic or is_follow_up_phrase or has_person_pronoun or prev_intent == 'SPORTS_KNOWLEDGE':
            effective_sport = prev_sport
        else:
            effective_sport = None

        # ── 5. Detect Explicit Location Context from Query ────────────────
        from .location_utils import extract_location
        detected_location = extract_location(query)

        if detected_location:
            effective_location = detected_location
        elif has_location_deictic or is_follow_up_phrase or has_sport_deictic:
            effective_location = prev_location
        else:
            effective_location = None

        # ── 6. Generic Entity Resolution against Catalog ──────────────────
        matched_descriptors: list[EntityDescriptor] = []
        matched_notes: list[str] = []

        # Sort descriptors so longer aliases are checked first
        for desc in GLOBAL_ENTITY_CATALOG:
            # Check if any alias matches the query
            alias_matched = False
            for alias in desc.aliases:
                norm_alias = normalize_text(alias)
                pattern = r'(?<![a-z0-9])' + re.escape(norm_alias) + r'(?![a-z0-9])'
                if re.search(pattern, norm_query) or re.search(pattern, norm_raw):
                    alias_matched = True
                    break

            if alias_matched:
                matched_descriptors.append(desc)
                if desc.notes and desc.notes not in matched_notes:
                    matched_notes.append(desc.notes)

        # Context-based filtering / disambiguation
        # If multiple athletes match, prioritize one matching effective_sport / effective_location
        resolved_entities: list[str] = []
        resolved_entity_types: list[str] = []
        effective_competition = prev_competition

        # Separate non-sport/non-location entities (athletes, teams, competitions)
        athlete_team_comp = [d for d in matched_descriptors if d.entity_type in ('athlete', 'team', 'competition')]
        if detected_sport:
            athlete_team_comp = [d for d in athlete_team_comp if not d.sport or d.sport == detected_sport]
        
        # Sort by relevance: matching effective_sport gets priority
        if athlete_team_comp:
            def sort_key(d: EntityDescriptor):
                score = 0
                if effective_sport and d.sport == effective_sport:
                    score += 10
                if effective_location and d.location == effective_location:
                    score += 5
                return score
            athlete_team_comp.sort(key=sort_key, reverse=True)

            for d in athlete_team_comp:
                if d.canonical_name not in resolved_entities:
                    resolved_entities.append(d.canonical_name)
                    resolved_entity_types.append(d.entity_type)
                    if d.entity_type == 'competition':
                        effective_competition = d.canonical_name
                    if d.sport and not detected_sport and not effective_sport:
                        effective_sport = d.sport

        # Separate entities: athlete/team vs competition
        athlete_team_entities = [d.canonical_name for d in athlete_team_comp if d.entity_type in ('athlete', 'team')]
        competition_entities = [d.canonical_name for d in athlete_team_comp if d.entity_type == 'competition']

        # ── 7. Entity Switching vs Pronoun Resolution ─────────────────────
        active_entity = None
        active_entity_type = None
        recent_entities = list(prev_recent_entities)

        if athlete_team_entities:
            # Query explicitly mentions one or more athletes/teams
            active_entity = athlete_team_entities[0]
            matched_desc = next((d for d in athlete_team_comp if d.canonical_name == active_entity), None)
            active_entity_type = matched_desc.entity_type if matched_desc else 'athlete'
            if matched_desc and matched_desc.sport:
                effective_sport = matched_desc.sport
            if prev_active_entity and prev_active_entity != active_entity:
                # User switched entity (e.g. CR7 -> Messi -> Mbappé)
                if prev_active_entity not in recent_entities:
                    recent_entities.insert(0, prev_active_entity)
            if active_entity in recent_entities:
                recent_entities.remove(active_entity)
            recent_entities.insert(0, active_entity)
        elif competition_entities and not has_person_pronoun and not (is_follow_up_phrase and prev_entity_type == 'athlete' and not any(p in norm_query for p in ('doi nao', 'ai vo dich', 'vua pha luoi', 'to chuc', 'dien ra', 'o dau'))):
            # Query explicitly mentions a competition
            active_entity = competition_entities[0]
            active_entity_type = 'competition'
            resolved_entities = competition_entities
        elif detected_sport and not athlete_team_entities:
            # User switched sport (or asked general sport question) -> active athlete from old sport is unset
            active_entity = None
            active_entity_type = 'sport'
        elif (has_person_pronoun or (is_follow_up_phrase and not detected_sport and not detected_location and not any(p in norm_query for p in ('con mon khac', 'mon khac thi sao', 'con mon nao', 'cac mon khac', 'con mon gi', 'tinh nay', 'thanh pho nay', 'o day')))) and prev_active_entity:
            # Pronoun or follow-up referring to previous active entity
            active_entity = prev_active_entity
            active_entity_type = prev_entity_type or 'athlete'
            resolved_entities = [active_entity] + competition_entities
            is_follow_up_phrase = True
        elif competition_entities:
            active_entity = competition_entities[0]
            active_entity_type = 'competition'
            resolved_entities = competition_entities

        # ── 8. Ambiguous Bare Nickname Conditional Handling ───────────────
        is_conditional = False
        conditional_note = None

        used_bare_nickname = any(re.search(r'\b' + re.escape(s) + r'\b', norm_query) for s in cls.AMBIGUOUS_NICKNAMES)
        if resolved_entities and not detected_sport and not prev_sport and used_bare_nickname:
            is_conditional = True
            first_ent = resolved_entities[0]
            if first_ent == 'Cristiano Ronaldo':
                conditional_note = (
                    "Trong văn hóa thể thao và cộng đồng mạng bóng đá, 'anh 7' (hoặc 'anh Bảy') thường được dùng để chỉ "
                    "siêu sao Cristiano Ronaldo (CR7) gắn liền với chiếc áo số 7 huyền thoại."
                )
            elif first_ent == 'Lionel Messi':
                conditional_note = (
                    "Trong bóng đá và cộng đồng người hâm mộ, 'anh 10' (hoặc 'anh Mười') thường là cách gọi quen thuộc "
                    "dành cho siêu sao Lionel Messi (M10) với chiếc áo số 10 trứ danh."
                )
            elif first_ent == 'Roger Federer':
                conditional_note = (
                    "Trong môn quần vợt (Tennis), 'Tàu tốc hành' (FedEx) là biệt danh nổi tiếng của huyền thoại Roger Federer."
                )
            elif first_ent == 'Rafael Nadal':
                conditional_note = (
                    "Trong quần vợt, 'Vua đất nện' (King of Clay) là danh xưng vĩ đại dành cho Rafael Nadal."
                )

        # ── 9. Topic and Specific Target Resolution ───────────────────────
        topic = None
        target_trophy = None

        is_return_to_business = any(term in norm_query for term in (
            'thoi tim san', 'quay lai tim san', 'quay lai dat san', 'tim san luc nay', 'san luc nay',
            'dat san luc nay', 'thoi xem san', 'quay lai xem san', 'thoi kiem san', 'tim san bong luc nay',
        ))

        if any(p in norm_query for p in ('to chuc o dau', 'dien ra o dau', 'dang cai o dau', 'dia diem to chuc', 'dia diem')):
            topic = 'host_location'
        elif any(p in norm_query for p in ('ghi ban', 'ai ghi ban', 'cau thu nao ghi ban', 'vua pha luoi', 'ghi nhieu ban nhat', 'top ghi ban', 'top scorer')):
            topic = 'top_scorer'
        elif any(p in norm_query for p in (
            'thang ai', 'danh bai ai', 'ha ai', 'thang doi nao', 'danh bai doi nao', 'ha doi nao',
            'vuot qua ai', 'vuot qua doi nao', 'ket qua tran chung ket', 'chung ket thang ai',
        )):
            topic = 'match_result'
        elif any(p in norm_query for p in ('cup wc', 'wc', 'world cup', 'cup the gioi', 'vo dich the gioi')):
            topic = 'achievements'
            target_trophy = 'FIFA World Cup'
            effective_competition = 'FIFA World Cup'
        elif any(p in norm_query for p in ('c1', 'cup c1', 'champions league', 'uefa champions league', 'cup chau au')):
            topic = 'achievements'
            target_trophy = 'UEFA Champions League'
            effective_competition = 'UEFA Champions League'
        elif any(p in norm_query for p in ('grand slam', 'wimbledon', 'us open', 'australian open', 'roland garros')):
            topic = 'achievements'
            target_trophy = 'Grand Slam'
            effective_competition = 'Grand Slam'
        elif any(p in norm_query for p in ('qua bong vang', 'may qua', 'may qua bong vang', 'ballon d\'or', 'ballon dor', 'qua bong')):
            topic = 'achievements'
            target_trophy = 'Ballon d\'Or'
        elif any(p in norm_query for p in ('thanh tich', 'danh hieu', 'giai thuong', 'huy chuong', 'cup', 'vo dich', 'quan quan')):
            topic = 'achievements'
        elif any(p in norm_query for p in ('la ai', 'gioi thieu', 'tieu su', 'profil', 'la doi nao', 'la doi bong nao', 'la clb nao', 'la doi', 'la clb', 'co nhung doi nao', 'co nhung doi', 'co nhung clb', 'co nhung clb nao', 'co nhung doi bong', 'co nhung mon nao', 'co nhung mon')):
            topic = 'identity'
        elif any(p in norm_query for p in (
            'clb hien tai', 'doi hien tai', 'dang choi cho', 'dang thi dau cho', 'khoac ao',
            'dang da cho', 'clb nao', 'doi nao', 'dang da', 'thi dau o dau', 'choi o dau',
            'da o dau', 'o doi nao', 'clb gi', 'doi bong nao'
        )):
            topic = 'current_club'
        elif any(p in norm_query for p in ('thuoc quoc gia nao', 'o nuoc nao', 'thuoc nuoc nao', 'quoc gia nao', 'dat nuoc nao')):
            topic = 'country'
        elif any(p in norm_query for p in ('sinh ngay', 'ngay sinh', 'sinh nam', 'sinh vao ngay', 'sinh ngay bao nhieu', 'sinh ngay nao', 'bao nhieu tuoi')):
            topic = 'birth_date'
        elif any(p in norm_query for p in ('sinh o dau', 'noi sinh', 'que o dau', 'que quan', 'sinh tai', 'que o')):
            topic = 'birth_place'
        elif any(p in norm_query for p in ('trang thai', 'giai nghe', 'con thi dau', 'da gia tu', 'giai nghe chua', 'da giai nghe')):
            topic = 'status'
        elif any(p in norm_query for p in ('qua trinh thi dau', 'su nghiep', 'tung thi dau', 'cac clb')):
            topic = 'career'
        elif any(p in norm_query for p in ('co ai', 'nhung ai', 'ai gioi', 'ai noi bat', 'ai tieu bieu', 'van dong vien nao', 'cau thu nao', 'tay vot nao', 'ai xuat sac')):
            topic = 'athletes'

        # ── 10. Generic Query Rewriting Engine for RAG ────────────────────
        rewritten_query = query
        ent_name = active_entity or (resolved_entities[0] if resolved_entities else None)

        matched_topics_count = sum([
            bool((target_trophy and ent_name != target_trophy and topic != 'achievements') or (any(p in norm_query for p in ('c1', 'cup c1', 'champions league', 'qua bong vang', 'ballon d\'or')) and topic != 'achievements')),
            bool(any(p in norm_query for p in ('clb hien tai', 'doi hien tai', 'dang choi cho', 'dang thi dau cho', 'khoac ao', 'dang da cho', 'clb nao', 'doi nao', 'dang da', 'thi dau o dau', 'choi o dau', 'da o dau', 'o doi nao', 'thi dau cho clb', 'clb bong chuyen nao'))),
            bool(any(p in norm_query for p in ('sinh ngay', 'ngay sinh', 'sinh nam', 'sinh vao ngay', 'sinh ngay bao nhieu', 'sinh ngay nao', 'bao nhieu tuoi'))),
            bool(any(p in norm_query for p in ('sinh o dau', 'noi sinh', 'que o dau', 'que quan', 'sinh tai', 'que o'))),
            bool(any(p in norm_query for p in ('quoc gia nao', 'den tu dau', 'o nuoc nao', 'thuoc nuoc nao'))),
            bool(any(p in norm_query for p in ('la ai', 'gioi thieu', 'tieu su', 'profil', 'la doi nao', 'la doi bong nao', 'la clb nao', 'la doi', 'la clb'))),
            bool(any(p in norm_query for p in ('trang thai', 'giai nghe', 'con thi dau', 'da gia tu'))),
            bool(any(p in norm_query for p in ('qua trinh thi dau', 'su nghiep', 'tung thi dau'))),
            bool(topic in ('top_scorer', 'country', 'host_location', 'match_result')),
        ])

        if topic == 'match_result':
            subject_team = ent_name or prev_active_entity or 'Đội vô địch'
            comp_name = effective_competition or 'FIFA World Cup'
            year_str = f" {effective_year}" if effective_year else ""
            rewritten_query = f"{subject_team} đã thắng ai / đánh bại đội nào ở trận chung kết {comp_name}{year_str}?"
        elif topic == 'host_location' and effective_competition:
            year_str = f" {effective_year}" if effective_year else ""
            rewritten_query = f"Giải đấu {effective_competition}{year_str} được tổ chức ở đâu?"
        elif topic == 'top_scorer' and effective_competition:
            year_str = f" {effective_year}" if effective_year else ""
            rewritten_query = f"Vua phá lưới / cầu thủ ghi nhiều bàn nhất tại giải {effective_competition}{year_str} là ai?"
        elif has_sport_deictic or (effective_sport and any(p in norm_query for p in ('mon nay', 'mon do', 'bo mon nay', 'bo mon do'))):
            # Sport deictic resolution e.g. "Việt Nam có ai nổi bật ở môn này?"
            rq = query
            sp_name = effective_sport or 'thể thao'
            # Check and replace both accented and non-accented variations
            deictic_patterns = [
                r'\b(?:môn|mon)\s+(?:này|nay|đó|do)\b',
                r'\b(?:bộ\s+môn|bo\s+mon)\s+(?:này|nay|đó|do)\b',
                r'\b(?:môn\s+thể\s+thao|mon\s+the\s+thao)\s+(?:này|nay|đó|do)\b',
            ]
            for pat in deictic_patterns:
                rq = re.sub(pat, f"môn {sp_name}", rq, flags=re.IGNORECASE)
            rewritten_query = rq
        elif is_follow_up_phrase and not ent_name and effective_sport and effective_location and len(norm_query.split()) <= 6:
            # E.g. "còn cầu lông?" in Thái Nguyên context, or "ở Việt Nam thì sao?" in Tennis context
            rewritten_query = f"Phong trào và thông tin thể thao {effective_sport} tại {effective_location} như thế nào?"
        elif is_follow_up_phrase and not ent_name and effective_location and len(norm_query.split()) <= 6:
            # E.g. "Thái Nguyên thì sao?", "ở Hà Nội thì sao?"
            sp_part = f"môn {effective_sport}" if effective_sport else "thể thao"
            rewritten_query = f"Phong trào và thông tin {sp_part} tại {effective_location} như thế nào?"
        elif ent_name:
            if matched_topics_count > 1:
                # Compound query: replace person pronouns with entity name preserving all clauses
                rq = query
                for pron in cls.PERSON_PRONOUNS:
                    rq = re.sub(rf'\b{re.escape(pron)}\b', ent_name, rq, flags=re.IGNORECASE)
                if ent_name.lower() not in normalize_text(rq):
                    rq = f"{ent_name}: {rq}"
                rewritten_query = rq
            elif target_trophy == 'FIFA World Cup':
                year = f" {effective_year}" if effective_year else ""
                if any(p in norm_query for p in ('co', 'chua', 'may', 'bao nhieu', 'gianh')) and ent_name != 'FIFA World Cup':
                    rewritten_query = f"{ent_name} đã từng vô địch FIFA World Cup chưa và có thành tích gì tại World Cup?"
                elif any(p in norm_query for p in ('doi nao', 'ai vo dich', 'quan quan', 'vo dich')):
                    rewritten_query = f"Đội tuyển nào vô địch FIFA World Cup{year}?".strip()
                elif ent_name == 'FIFA World Cup':
                    rewritten_query = f"Giải đấu FIFA World Cup{year} có những thông tin và thành tích nổi bật nào?"
                else:
                    rewritten_query = f"Thành tích FIFA World Cup của {ent_name} là gì?"
            elif target_trophy == 'UEFA Champions League':
                rewritten_query = f"{ent_name} đã giành bao nhiêu chức vô địch UEFA Champions League (Cúp C1)?"
            elif target_trophy == 'Ballon d\'Or':
                rewritten_query = f"{ent_name} đã giành được bao nhiêu Quả bóng vàng (Ballon d'Or)?"
            elif target_trophy == 'Grand Slam':
                rewritten_query = f"{ent_name} đã giành được bao nhiêu danh hiệu Grand Slam?"
            elif topic == 'current_club':
                rewritten_query = f"{ent_name} hiện đang thi đấu cho câu lạc bộ nào?"
            elif topic == 'country':
                rewritten_query = f"{ent_name} thuộc quốc gia nào?"
            elif topic == 'birth_date':
                rewritten_query = f"{ent_name} sinh ngày tháng năm nào?"
            elif topic == 'birth_place':
                rewritten_query = f"{ent_name} sinh ra ở đâu, quê quán ở đâu?"
            elif topic == 'status':
                rewritten_query = f"{ent_name} hiện còn thi đấu chuyên nghiệp hay đã giải nghệ?"
            elif topic == 'achievements':
                rewritten_query = f"Những thành tích và danh hiệu nổi bật nhất của {ent_name} là gì?"
            elif is_follow_up_phrase and len(norm_query.split()) <= 4:
                # E.g. "còn Messi?", "còn CR7?", "còn Mbappé?"
                rewritten_query = f"{ent_name} là ai và có thông tin thành tích nổi bật nào?"
            else:
                # Replace person pronouns
                rq = query
                for pron in cls.PERSON_PRONOUNS:
                    rq = re.sub(rf'\b{re.escape(pron)}\b', ent_name, rq, flags=re.IGNORECASE)
                rewritten_query = rq

        if active_entity_type == 'athlete':
            resolved_athlete = active_entity
        elif not detected_sport and prev_entity_type == 'athlete':
            resolved_athlete = prev_active_entity
        else:
            resolved_athlete = None
        resolved_team = active_entity if active_entity_type == 'team' else next((d.canonical_name for d in matched_descriptors if d.entity_type == 'team'), None)

        return SportsResolutionResult(
            entities=resolved_entities,
            active_entity=active_entity,
            entity_type=active_entity_type,
            recent_entities=recent_entities,
            sport=effective_sport,
            location=effective_location,
            competition=effective_competition,
            year=effective_year,
            team=resolved_team,
            athlete=resolved_athlete,
            topic=topic,
            target_trophy=target_trophy,
            previous_intent=prev_intent,
            is_follow_up=is_follow_up_phrase or has_person_pronoun or has_sport_deictic or has_location_deictic,
            is_return_to_business=is_return_to_business,
            is_conditional=is_conditional,
            conditional_note=conditional_note,
            is_meme_or_joke=is_meme,
            rewritten_query=rewritten_query,
            notes=matched_notes,
        )
