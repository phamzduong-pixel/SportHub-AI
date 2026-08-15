import re
import unicodedata


LOCATION_ALIASES = {
    'ha noi': 'Hà Nội', 'hanoi': 'Hà Nội',
    'thai nguyen': 'Thái Nguyên',
    'tp hcm': 'TP.HCM', 'tphcm': 'TP.HCM', 'ho chi minh': 'TP.HCM',
    'sai gon': 'TP.HCM',
    'da nang': 'Đà Nẵng',
    'cau giay': 'Cầu Giấy', 'tay ho': 'Tây Hồ',
    'binh thanh': 'Bình Thạnh', 'go vap': 'Gò Vấp',
    'tan binh': 'Tân Bình', 'thu duc': 'Thủ Đức',
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
    patterns = (
        r'\b(?:o|tai|quanh|gan)\s+(.+?)(?=\s+(?:co|tim|con|ngay|luc|gia|duoi|khong)\b|$)',
        r'^(.+?)\s+co\s+(?:san|co so)\b',
        r'^co\s+(.+?)\s+khong$',
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            candidate = re.sub(r'\b(?:san|co so|nao)$', '', match[1]).strip()
            if candidate and candidate not in {'day', 'toi', 'san nao'}:
                return canonical_location(candidate)
    return None


def location_matches(requested: str, *values: str | None) -> bool:
    needle = normalize_location_text(requested)
    return any(needle in normalize_location_text(value or '') for value in values)
