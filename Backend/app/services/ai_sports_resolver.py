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
    
    # Sort number words by length descending so multi-word numbers match first
    prefixes = ['anh', 'chi', 'chu', 'cau thu', 'tay vot', 'vdv', 'so', 'ao so', 'ao']
    for prefix in prefixes:
        for word, digit in sorted(NUMBER_WORDS_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            pattern = r'\b' + re.escape(prefix) + r'\s+' + re.escape(word) + r'\b'
            norm = re.sub(pattern, f"{prefix} {digit}", norm)
    return norm


# Multi-sport Nickname, Slang & Alias dictionary
# Key: sport -> { alias_phrase: (canonical_entity, notes) }
SPORT_SLANG_REGISTRY: dict[str, dict[str, tuple[str, str]]] = {
    'bóng đá': {
        'anh 7': ('Cristiano Ronaldo', 'Biệt danh gắn liền với số áo 7 huyền thoại của Cristiano Ronaldo (CR7)'),
        'cr7': ('Cristiano Ronaldo', 'CR7 - Siêu sao Cristiano Ronaldo'),
        'c ronaldo': ('Cristiano Ronaldo', 'Cristiano Ronaldo'),
        'c.ronaldo': ('Cristiano Ronaldo', 'Cristiano Ronaldo'),
        'chi 7': ('Cristiano Ronaldo', 'Cách gọi vui trên mạng xã hội dành cho Cristiano Ronaldo'),
        'anh bay': ('Cristiano Ronaldo', 'Cristiano Ronaldo'),
        'chi bay': ('Cristiano Ronaldo', 'Cristiano Ronaldo'),
        'so 7': ('Cristiano Ronaldo', 'Cristiano Ronaldo'),
        'ao so 7': ('Cristiano Ronaldo', 'Cristiano Ronaldo'),
        
        'anh 10': ('Lionel Messi', 'Biệt danh gắn liền với số áo 10 huyền thoại của Lionel Messi (M10)'),
        'm10': ('Lionel Messi', 'M10 - Siêu sao Lionel Messi'),
        'anh muoi': ('Lionel Messi', 'Lionel Messi'),
        'el pulga': ('Lionel Messi', 'La Pulga (Bọ chét nguyên tử) - Biệt danh của Lionel Messi'),
        'la pulga': ('Lionel Messi', 'La Pulga - Biệt danh của Lionel Messi'),
        'so 10': ('Lionel Messi', 'Lionel Messi'),
        'ao so 10': ('Lionel Messi', 'Lionel Messi'),
        
        'anh 9': ('Ronaldo de Lima', 'Ronaldo de Lima (Rô béo) / Tiền đạo số 9'),
        'r9': ('Ronaldo de Lima', 'Ronaldo de Lima (Rô béo) - Huyền thoại bóng đá Brazil'),
        'ro beo': ('Ronaldo de Lima', 'Ronaldo de Lima (Người ngoài hành tinh)'),
        'nguoi ngoai hanh tinh': ('Ronaldo de Lima', 'Biệt danh của huyền thoại Ronaldo de Lima'),
        
        'dang maguire': ('Harry Maguire', 'Meme vui trong cộng đồng bóng đá dành cho trung vệ Harry Maguire'),
        'chua te maguire': ('Harry Maguire', 'Meme vui dành cho Harry Maguire'),
        'mac hai': ('Harry Maguire', 'Cách gọi vui tiếng Việt của Harry Maguire'),
        'harry maguire': ('Harry Maguire', 'Trung vệ Harry Maguire'),
        'maguire': ('Harry Maguire', 'Harry Maguire'),
        
        'lakaka': ('Romelu Lukaku', 'Meme hài hước của người hâm mộ bóng đá dành cho tiền đạo Romelu Lukaku'),
        'lukaku': ('Romelu Lukaku', 'Tiền đạo Romelu Lukaku'),
        'romelu lukaku': ('Romelu Lukaku', 'Tiền đạo Romelu Lukaku'),
        
        'hai con': ('Nguyễn Quang Hải', 'Biệt danh thân mật của tiền vệ Nguyễn Quang Hải'),
        'thanh truot co': ('Nguyễn Quang Hải', 'Meme vui gắn với màn ăn mừng tại VCK U23 Châu Á của Quang Hải'),
        'quang hai': ('Nguyễn Quang Hải', 'Nguyễn Quang Hải'),
        
        'linh ka': ('Nguyễn Tiến Linh', 'Biệt danh vui của tiền đạo Nguyễn Tiến Linh'),
        'tien linh': ('Nguyễn Tiến Linh', 'Nguyễn Tiến Linh'),
        
        'hoang duc': ('Nguyễn Hoàng Đức', 'Nguyễn Hoàng Đức'),
        'thay park': ('Park Hang-seo', 'HLV Park Hang-seo'),
        'park hang-seo': ('Park Hang-seo', 'Park Hang-seo'),
        'park hang seo': ('Park Hang-seo', 'Park Hang-seo'),
        
        'quai vat ghi ban': ('Erling Haaland', 'Biệt danh về hiệu suất ghi bàn của Erling Haaland'),
        'haaland': ('Erling Haaland', 'Erling Haaland'),
        'erling haaland': ('Erling Haaland', 'Erling Haaland'),
        
        'ninja rua': ('Kylian Mbappé', 'Biệt danh vui do đồng đội và người hâm mộ đặt cho Kylian Mbappé'),
        'mbappe': ('Kylian Mbappé', 'Kylian Mbappé'),
        'kylian mbappe': ('Kylian Mbappé', 'Kylian Mbappé'),
        
        'lam tay dai': ('Đặng Văn Lâm', 'Biệt danh vui của thủ môn Đặng Văn Lâm'),
        'van lam': ('Đặng Văn Lâm', 'Đặng Văn Lâm'),
        'dang van lam': ('Đặng Văn Lâm', 'Đặng Văn Lâm'),
        'kim thanh': ('Trần Thị Kim Thanh', 'Trần Thị Kim Thanh'),
        'bich thuy': ('Nguyễn Thị Bích Thùy', 'Nguyễn Thị Bích Thùy'),
    },
    'tennis': {
        'tau toc hanh': ('Roger Federer', 'Biệt danh Tàu tốc hành (FedEx / The Swiss Maestro) của Roger Federer'),
        'fedex': ('Roger Federer', 'Roger Federer'),
        'swiss maestro': ('Roger Federer', 'Roger Federer'),
        'federer': ('Roger Federer', 'Roger Federer'),
        'roger federer': ('Roger Federer', 'Roger Federer'),
        
        'vua dat nen': ('Rafael Nadal', 'Biệt danh Vua sân đất nện (King of Clay) của Rafael Nadal'),
        'vua san dat nen': ('Rafael Nadal', 'Rafael Nadal'),
        'king of clay': ('Rafael Nadal', 'Rafael Nadal'),
        'nadal': ('Rafael Nadal', 'Rafael Nadal'),
        'rafael nadal': ('Rafael Nadal', 'Rafael Nadal'),
        
        'nole': ('Novak Djokovic', 'Biệt danh Nole / The Djoker của Novak Djokovic'),
        'the djoker': ('Novak Djokovic', 'Novak Djokovic'),
        'djokovic': ('Novak Djokovic', 'Novak Djokovic'),
        'novak djokovic': ('Novak Djokovic', 'Novak Djokovic'),
        
        'tieu federer': ('Carlos Alcaraz', 'Cách gọi dành cho tài năng trẻ Carlos Alcaraz hoặc Grigor Dimitrov'),
        'alcaraz': ('Carlos Alcaraz', 'Carlos Alcaraz'),
        'carlos alcaraz': ('Carlos Alcaraz', 'Carlos Alcaraz'),
        'sinner': ('Jannik Sinner', 'Jannik Sinner'),
        'jannik sinner': ('Jannik Sinner', 'Jannik Sinner'),
        'ly hoang nam': ('Lý Hoàng Nam', 'Lý Hoàng Nam'),
    },
    'bóng rổ': {
        'nha vua': ('LeBron James', 'Biệt danh King James (Nhà vua) của LeBron James'),
        'king james': ('LeBron James', 'LeBron James'),
        'the king': ('LeBron James', 'LeBron James'),
        'lebron': ('LeBron James', 'LeBron James'),
        'lebron james': ('LeBron James', 'LeBron James'),
        
        'bep truong': ('Stephen Curry', 'Biệt danh Chef Curry (Bếp trưởng) của Stephen Curry'),
        'bep truong curry': ('Stephen Curry', 'Stephen Curry'),
        'chef curry': ('Stephen Curry', 'Stephen Curry'),
        'curry': ('Stephen Curry', 'Stephen Curry'),
        'stephen curry': ('Stephen Curry', 'Stephen Curry'),
        
        'black mamba': ('Kobe Bryant', 'Biệt danh Black Mamba (Tinh thần Mamba) của Kobe Bryant'),
        'mamba': ('Kobe Bryant', 'Kobe Bryant'),
        'kobe': ('Kobe Bryant', 'Kobe Bryant'),
        'kobe bryant': ('Kobe Bryant', 'Kobe Bryant'),
        
        'vua bong ro': ('Michael Jordan', 'Biệt danh của huyền thoại Michael Jordan'),
        'ngai jordan': ('Michael Jordan', 'Michael Jordan'),
        'jordan': ('Michael Jordan', 'Michael Jordan'),
        'michael jordan': ('Michael Jordan', 'Michael Jordan'),
        'saigon heat': ('Saigon Heat', 'Saigon Heat'),
        'hanoi buffaloes': ('Hanoi Buffaloes', 'Hanoi Buffaloes'),
        'thang long warriors': ('Thang Long Warriors', 'Thang Long Warriors'),
    },
    'cầu lông': {
        'super dan': ('Lin Dan', 'Biệt danh Super Dan của huyền thoại Lin Dan'),
        'lin dan': ('Lin Dan', 'Lin Dan'),
        'lee chong wei': ('Lee Chong Wei', 'Lee Chong Wei'),
        'tuong dai cau long': ('Nguyễn Tiến Minh', 'Nguyễn Tiến Minh'),
        'tien minh': ('Nguyễn Tiến Minh', 'Nguyễn Tiến Minh'),
        'nguyen tien minh': ('Nguyễn Tiến Minh', 'Nguyễn Tiến Minh'),
        'hoa khoi cau long': ('Nguyễn Thùy Linh', 'Biệt danh của tay vợt nữ số 1 Việt Nam Nguyễn Thùy Linh'),
        'thuy linh': ('Nguyễn Thùy Linh', 'Nguyễn Thùy Linh'),
        'nguyen thuy linh': ('Nguyễn Thùy Linh', 'Nguyễn Thùy Linh'),
        'axelsen': ('Viktor Axelsen', 'Viktor Axelsen'),
        'viktor axelsen': ('Viktor Axelsen', 'Viktor Axelsen'),
        'kento momota': ('Kento Momota', 'Kento Momota'),
        'momota': ('Kento Momota', 'Kento Momota'),
        'an se young': ('An Se Young', 'An Se Young'),
        'le duc phat': ('Lê Đức Phát', 'Lê Đức Phát'),
    },
    'bóng chuyền': {
        'khung long bong chuyen': ('Nguyễn Thị Bích Tuyền', 'Biệt danh về sức mạnh và tầm bật nhảy của Nguyễn Thị Bích Tuyền'),
        'khung long 420': ('Nguyễn Thị Bích Tuyền', 'Nguyễn Thị Bích Tuyền'),
        'bich tuyen': ('Nguyễn Thị Bích Tuyền', 'Nguyễn Thị Bích Tuyền'),
        'nguyen thi bich tuyen': ('Nguyễn Thị Bích Tuyền', 'Nguyễn Thị Bích Tuyền'),
        
        '4t': ('Trần Thị Thanh Thúy', 'Biệt danh 4T (Trần Thị Thanh Thúy) - Đội trưởng tuyển bóng chuyền nữ Việt Nam'),
        'chu cong 4t': ('Trần Thị Thanh Thúy', 'Trần Thị Thanh Thúy'),
        'thanh thuy': ('Trần Thị Thanh Thúy', 'Trần Thị Thanh Thúy'),
        'tran thi thanh thuy': ('Trần Thị Thanh Thúy', 'Trần Thị Thanh Thúy'),
        
        'hoa khoi bong chuyen': ('Hoàng Thị Kiều Trinh', 'Hoàng Thị Kiều Trinh'),
        'kieu trinh': ('Hoàng Thị Kiều Trinh', 'Hoàng Thị Kiều Trinh'),
        'hoang thi kieu trinh': ('Hoàng Thị Kiều Trinh', 'Hoàng Thị Kiều Trinh'),
        'vtv cup': ('VTV Cup', 'VTV Cup'),
    },
    'pickleball': {
        'vua pickleball': ('Ben Johns', 'Biệt danh của tay vợt số 1 thế giới Ben Johns'),
        'ben johns': ('Ben Johns', 'Ben Johns'),
        'nu hoang pickleball': ('Anna Leigh Waters', 'Biệt danh của nữ tay vợt số 1 thế giới Anna Leigh Waters'),
        'anna leigh waters': ('Anna Leigh Waters', 'Anna Leigh Waters'),
        'than dong pickleball': ('Quang Dương', 'Tay vợt gốc Việt tài năng Quang Dương'),
        'quang duong': ('Quang Dương', 'Quang Dương'),
        'duong quang': ('Quang Dương', 'Quang Dương'),
        'trinh linh giang': ('Trịnh Linh Giang', 'Trịnh Linh Giang'),
    },
}

# Supported sport keywords in normalized text
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
    sport: str | None = None
    is_follow_up: bool = False
    is_conditional: bool = False
    conditional_note: str | None = None
    is_meme_or_joke: bool = False
    notes: list[str] = field(default_factory=list)


class SportsContextResolver:
    """Context-aware resolver for natural sports queries, nicknames, slang and memes."""

    @classmethod
    def resolve(cls, query: str, context: dict[str, Any] | None = None) -> SportsResolutionResult:
        context = context or {}
        norm_raw = normalize_text(query)
        norm_query = normalize_sports_numbers(query)
        
        # 1. Detect explicit sport in query
        detected_sport = None
        for kw, sp in sorted(SPORT_KEYWORDS_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if re.search(r'\b' + re.escape(kw) + r'\b', norm_query) or re.search(r'\b' + re.escape(kw) + r'\b', norm_raw):
                detected_sport = sp
                break

        # 2. Context sport & entity inheritance
        prev_intent = context.get('last_intent')
        prev_sport = context.get('sport_type')
        prev_entities = context.get('sports_entities') or ([context.get('sports_entity')] if context.get('sports_entity') else [])

        is_follow_up_phrase = any(re.search(r'\b' + re.escape(p) + r'\b', norm_query) for p in (
            'con ', 'the con', 'vay con', 'con thi sao', 'the con ai', 'con ong nao', 'con cau thu nao',
            'con nguoi nay', 'con ai khac', 'the ai', 'con o dau', 'con clb nao'
        )) or norm_query.startswith('con ') or norm_query.startswith('the con ') or norm_query.startswith('vay con ')

        # Effective sport considering context
        effective_sport = detected_sport or (prev_sport if (is_follow_up_phrase or prev_intent == 'SPORTS_KNOWLEDGE') else None)

        # 3. Detect Sports Memes / Humor / Teasing
        is_meme = any(p in norm_query for p in (
            'di bo vuot toc', 'vuot toc', 'ganh team', 'tau hai', 'hai huoc', 'siuuu', 'siu',
            'co biet da bong khong', 'biet da bong khong', 'ai la goat', 'goat cua bong da', 'dang maguire', 'chua te maguire', 'lakaka'
        ))

        # 4. Resolve Aliases with/without sport context
        resolved_entities: list[str] = []
        matched_notes: list[str] = []
        is_conditional = False
        conditional_note = None

        # Try searching in effective sport first if known
        sports_to_search = [effective_sport] if effective_sport else list(SPORT_SLANG_REGISTRY.keys())

        for sp in sports_to_search:
            if not sp or sp not in SPORT_SLANG_REGISTRY:
                continue
            registry = SPORT_SLANG_REGISTRY[sp]
            for alias_key in sorted(registry.keys(), key=len, reverse=True):
                pattern = r'(?<![a-z0-9])' + re.escape(alias_key) + r'(?![a-z0-9])'
                if re.search(pattern, norm_query) or re.search(pattern, norm_raw):
                    canonical_name, note = registry[alias_key]
                    if canonical_name not in resolved_entities:
                        resolved_entities.append(canonical_name)
                        matched_notes.append(note)
                        if not detected_sport and not effective_sport:
                            effective_sport = sp

        # Check if query had no sport context and was a bare nickname (e.g. "anh 7 là ai?", "anh 10 là ai?")
        if resolved_entities and not detected_sport and not prev_sport:
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

        # If follow-up has no new entities but refers to previous turn
        if not resolved_entities and is_follow_up_phrase and prev_entities:
            resolved_entities = list(prev_entities)

        return SportsResolutionResult(
            entities=resolved_entities,
            sport=effective_sport,
            is_follow_up=is_follow_up_phrase,
            is_conditional=is_conditional,
            conditional_note=conditional_note,
            is_meme_or_joke=is_meme,
            notes=matched_notes,
        )
