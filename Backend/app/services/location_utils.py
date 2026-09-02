import re
import unicodedata


LOCATION_ALIASES = {
    'ha noi': 'Hà Nội', 'hanoi': 'Hà Nội',
    'thai nguyen': 'Thái Nguyên',
    'tp hcm': 'TP.HCM', 'tphcm': 'TP.HCM', 'ho chi minh': 'TP.HCM',
    'sai gon': 'TP.HCM',
    'da nang': 'Đà Nẵng',
    'cau giay': 'Cầu Giấy', 'tay ho': 'Tây Hồ', 'hoan kiem': 'Hoàn Kiếm',
    'ba dinh': 'Ba Đình', 'dong da': 'Đống Đa', 'thanh xuan': 'Thanh Xuân',
    'nam tu liem': 'Nam Từ Liêm', 'bac tu liem': 'Bắc Từ Liêm',
    'long bien': 'Long Biên', 'ha dong': 'Hà Đông', 'hai ba trung': 'Hai Bà Trưng',
    'hoang mai': 'Hoàng Mai', 'thanh tri': 'Thanh Trì', 'gia lam': 'Gia Lâm',
    'binh thanh': 'Bình Thạnh', 'go vap': 'Gò Vấp',
    'tan binh': 'Tân Bình', 'tan phu': 'Tân Phú', 'phu nhuan': 'Phú Nhuận',
    'thu duc': 'Thủ Đức', 'binh tan': 'Bình Tân',
    'quan 1': 'Quận 1', 'quan 2': 'Quận 2', 'quan 3': 'Quận 3', 'quan 4': 'Quận 4',
    'quan 5': 'Quận 5', 'quan 6': 'Quận 6', 'quan 7': 'Quận 7', 'quan 8': 'Quận 8',
    'quan 9': 'Quận 9', 'quan 10': 'Quận 10', 'quan 11': 'Quận 11', 'quan 12': 'Quận 12',
}


def normalize_location_text(value: str) -> str:
    normalized = unicodedata.normalize('NFD', value.casefold())
    plain = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn').replace('đ', 'd')
    return re.sub(r'[^a-z0-9]+', ' ', plain).strip()


def canonical_location(value: str | None) -> str | None:
    if not value:
        return None
    normalized = normalize_location_text(value)
    if not normalized:
        return None
    if normalized in LOCATION_ALIASES:
        return LOCATION_ALIASES[normalized]
    district = re.fullmatch(r'quan\s+(\d+)', normalized)
    if district:
        return f'Quận {district[1]}'
    return ' '.join(part.capitalize() for part in normalized.split())


def extract_location(query: str) -> str | None:
    normalized = normalize_location_text(query)
    aliases = sorted(LOCATION_ALIASES, key=len, reverse=True)
    for alias in aliases:
        if re.search(rf'\b{re.escape(alias)}\b', normalized):
            return LOCATION_ALIASES[alias]
    district = re.search(r'\bquan\s+\d+\b', normalized)
    if district:
        return canonical_location(district[0])
    ignore_tokens = {
        'day', 'toi', 'san nao', 'san', 'co so', 're hon', 'trong', 'khung gio',
        'slot', 'bong da', 'cau long', 'pickleball', 'tennis', 'bong ro', 'bong chuyen',
        'gia re', 're nhat', 're', 'dat san', 'ngay mai', 'hom nay',
    }
    patterns = (
        r'\b(?:o|tai|quanh|gan)\s+(.+?)(?=\s+(?:co|tim|con|ngay|luc|gia|duoi|khong)\b|$)',
        r'^(.+?)\s+co\s+(?:san|co so)\b',
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            candidate = re.sub(r'\b(?:san|co so|nao)$', '', match[1]).strip()
            if candidate and candidate not in ignore_tokens and not any(tok in candidate for tok in ('re hon', 'con trong', 'bong da', 'cau long', 'pickleball', 'tennis', 'san nao')):
                return canonical_location(candidate)
    return None


def location_matches(requested: str, *values: str | None) -> bool:
    needle = normalize_location_text(requested)
    return any(needle in normalize_location_text(value or '') for value in values)


def sport_matches(requested_sport: str | None, field_sport: str | None) -> bool:
    if not requested_sport or not field_sport:
        return False
    q_norm = normalize_location_text(requested_sport)
    f_norm = normalize_location_text(field_sport)
    if q_norm == f_norm:
        return True
    distinct_sports = ('bong da', 'bong ro', 'bong chuyen', 'cau long', 'tennis', 'pickleball')
    for sport in distinct_sports:
        if sport in q_norm and sport in f_norm:
            return True
        if (sport in q_norm) != (sport in f_norm):
            return False
    return q_norm in f_norm or f_norm in q_norm
