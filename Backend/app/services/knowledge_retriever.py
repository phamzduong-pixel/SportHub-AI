import os
import re
import difflib
import unicodedata
from typing import List, Tuple, Optional

from ..models.knowledge_entry import KnowledgeEntry
from ..repositories.knowledge_repository import KnowledgeRepository


class KnowledgeRetriever:
    """Retrieve static knowledge entries based on a user query.

    The retriever supports:
    - keyword fuzzy matching (difflib.SequenceMatcher)
    - optional semantic similarity using a lightweight sentence‑transformer
    - role and intent filtering
    - top‑k selection and relevance gating
    """

    RELEVANCE_THRESHOLD = 0.60  # can be overridden by caller
    DEFAULT_TOP_K = 5
    # Use a small model that works on Windows without heavy GPU requirements
    EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, repository: KnowledgeRepository = None, use_semantic: bool = False):
        self.repo = repository or KnowledgeRepository()
        self.use_semantic = use_semantic
        self._static_entries: List[KnowledgeEntry] = self.repo.get_static_entries()
        if self.use_semantic:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.EMBEDDING_MODEL_NAME)
                # Pre‑compute embeddings for all static questions
                questions = [e.question for e in self._static_entries]
                self._embeddings = self._model.encode(questions, batch_size=32, show_progress_bar=False)
            except Exception:
                self.use_semantic = False
                self._model = None
                self._embeddings = None
        else:
            self.use_semantic = False
            self._model = None
            self._embeddings = None

    def index_entry(self, entry: KnowledgeEntry) -> bool:
        """Incrementally index a new knowledge entry without rebuilding entire index.

        Returns:
            bool: True if entry was newly indexed, False if skipped or delegated to update.
        """
        for idx, existing in enumerate(self._static_entries):
            if existing.id == entry.id:
                return self.update_entry(entry)

        # Append new entry
        self._static_entries.append(entry)

        # Incrementally encode vector embedding for the new chunk if semantic is active
        if self.use_semantic and self._model is not None:
            try:
                import numpy as np
                new_emb = self._model.encode([entry.question], show_progress_bar=False)
                if self._embeddings is not None and len(self._embeddings) > 0:
                    self._embeddings = np.vstack([self._embeddings, new_emb])
                else:
                    self._embeddings = np.array(new_emb)
            except Exception:
                pass

        return True

    def update_entry(self, entry: KnowledgeEntry, force: bool = False) -> bool:
        """Incrementally update an existing indexed entry's affected chunk/record.

        Returns:
            bool: True if record was updated and re-indexed, False if unchanged/skipped.
        """
        target_idx = None
        for idx, existing in enumerate(self._static_entries):
            if existing.id == entry.id:
                target_idx = idx
                break

        if target_idx is None:
            return self.index_entry(entry)

        existing = self._static_entries[target_idx]
        is_changed = (
            existing.answer != entry.answer
            or existing.question != entry.question
            or existing.topic != entry.topic
            or existing.entity != entry.entity
            or existing.sport != entry.sport
        )

        if not is_changed and not force:
            # Update metadata in place without re-indexing
            if entry.collected_at:
                existing.collected_at = entry.collected_at
            if entry.source_url:
                existing.source_url = entry.source_url
            if entry.source_name:
                existing.source_name = entry.source_name
            return False

        # Update affected entry in-place
        self._static_entries[target_idx] = entry

        # Re-compute vector embedding ONLY for the affected record
        if self.use_semantic and self._model is not None and self._embeddings is not None:
            try:
                if target_idx < len(self._embeddings):
                    new_emb = self._model.encode([entry.question], show_progress_bar=False)[0]
                    self._embeddings[target_idx] = new_emb
            except Exception:
                pass

        return True

    def remove_entry(self, entry_id: str) -> bool:
        """Remove an entry from the index by ID.

        Returns:
            bool: True if removed, False if not found.
        """
        target_idx = None
        for idx, existing in enumerate(self._static_entries):
            if existing.id == entry_id:
                target_idx = idx
                break

        if target_idx is None:
            return False

        self._static_entries.pop(target_idx)
        if self.use_semantic and self._embeddings is not None:
            try:
                import numpy as np
                if target_idx < len(self._embeddings):
                    self._embeddings = np.delete(self._embeddings, target_idx, axis=0)
            except Exception:
                pass

        return True

    @staticmethod
    def _normalize(text: str) -> str:
        if not text:
            return ""
        normalized = unicodedata.normalize('NFD', text.casefold())
        unaccented = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn').replace('đ', 'd')
        cleaned = re.sub(r'[?!.,;:"\'()\[\]{}]', ' ', unaccented)
        return " ".join(cleaned.split())

    # Maps normalized alias → canonical entity name (as stored in KnowledgeEntry.entity).
    # Aliases are checked when the query text does not directly contain the entry entity.
    ENTITY_ALIASES: dict[str, str] = {
        # Football — international
        'messi': 'Lionel Messi',
        'leo messi': 'Lionel Messi',
        'leo': 'Lionel Messi',
        'la pulga': 'Lionel Messi',
        'el pulga': 'Lionel Messi',
        'anh 10': 'Lionel Messi',
        'anh muoi': 'Lionel Messi',
        'm10': 'Lionel Messi',
        'ronaldo': 'Cristiano Ronaldo',
        'cr7': 'Cristiano Ronaldo',
        'cristiano': 'Cristiano Ronaldo',
        'anh 7': 'Cristiano Ronaldo',
        'anh bay': 'Cristiano Ronaldo',
        'chi 7': 'Cristiano Ronaldo',
        'chi bay': 'Cristiano Ronaldo',
        'dang maguire': 'Harry Maguire',
        'chua te maguire': 'Harry Maguire',
        'harry maguire': 'Harry Maguire',
        'lakaka': 'Romelu Lukaku',
        'lukaku': 'Romelu Lukaku',
        'haaland': 'Erling Haaland',
        'erling haaland': 'Erling Haaland',
        'mbappe': 'Kylian Mbappé',
        'kylian mbappe': 'Kylian Mbappé',
        # Football — Vietnam
        'quang hai': 'Nguyễn Quang Hải',
        'nguyen quang hai': 'Nguyễn Quang Hải',
        'hai con': 'Nguyễn Quang Hải',
        'thanh truot co': 'Nguyễn Quang Hải',
        'tien linh': 'Nguyễn Tiến Linh',
        'nguyen tien linh': 'Nguyễn Tiến Linh',
        'linh ka': 'Nguyễn Tiến Linh',
        'hoang duc': 'Nguyễn Hoàng Đức',
        'nguyen hoang duc': 'Nguyễn Hoàng Đức',
        'thay park': 'Park Hang-seo',
        'park hang-seo': 'Park Hang-seo',
        # Tennis
        'tau toc hanh': 'Roger Federer',
        'federer': 'Roger Federer',
        'roger federer': 'Roger Federer',
        'vua dat nen': 'Rafael Nadal',
        'nadal': 'Rafael Nadal',
        'rafael nadal': 'Rafael Nadal',
        'nole': 'Novak Djokovic',
        'djokovic': 'Novak Djokovic',
        'novak djokovic': 'Novak Djokovic',
        'alcaraz': 'Carlos Alcaraz',
        # Basketball
        'nha vua': 'LeBron James',
        'king james': 'LeBron James',
        'lebron': 'LeBron James',
        'bep truong': 'Stephen Curry',
        'chef curry': 'Stephen Curry',
        'curry': 'Stephen Curry',
        'black mamba': 'Kobe Bryant',
        'kobe': 'Kobe Bryant',
        # Badminton
        'super dan': 'Lin Dan',
        'lin dan': 'Lin Dan',
        'thuy linh': 'Nguyễn Thùy Linh',
        'nguyen thuy linh': 'Nguyễn Thùy Linh',
        'hoa khoi cau long': 'Nguyễn Thùy Linh',
        'tien minh': 'Nguyễn Tiến Minh',
        'nguyen tien minh': 'Nguyễn Tiến Minh',
        'tuong dai cau long': 'Nguyễn Tiến Minh',
        'axelsen': 'Viktor Axelsen',
        'viktor axelsen': 'Viktor Axelsen',
        # Volleyball
        'khung long bong chuyen': 'Nguyễn Thị Bích Tuyền',
        'bich tuyen': 'Nguyễn Thị Bích Tuyền',
        '4t': 'Trần Thị Thanh Thúy',
        'thanh thuy': 'Trần Thị Thanh Thúy',
        'kieu trinh': 'Hoàng Thị Kiều Trinh',
        # Pickleball
        'vua pickleball': 'Ben Johns',
        'ben johns': 'Ben Johns',
        'nu hoang pickleball': 'Anna Leigh Waters',
        'anna leigh waters': 'Anna Leigh Waters',
        'quang duong': 'Quang Dương',
        # Football — Thai Nguyen
        'thai nguyen t&t': 'Thái Nguyên T&T',
        'thai nguyen tt': 'Thái Nguyên T&T',
        'clb nu thai nguyen': 'Thái Nguyên T&T',
        'bong da nu thai nguyen': 'Thái Nguyên T&T',
        'doi bong nu thai nguyen': 'Thái Nguyên T&T',
        'fc thai nguyen': 'Bóng đá nam Thái Nguyên',
        'clb bong da nam thai nguyen': 'Bóng đá nam Thái Nguyên',
        'cau lac bo bong da nam thai nguyen': 'Bóng đá nam Thái Nguyên',
        'bong da nam thai nguyen': 'Bóng đá nam Thái Nguyên',
        'clb bong da thai nguyen': 'Bóng đá Thái Nguyên',
        'cau lac bo bong da thai nguyen': 'Bóng đá Thái Nguyên',
        # Tournaments
        'world cup': 'FIFA World Cup',
        'fifa world cup': 'FIFA World Cup',
        'champions league': 'UEFA Champions League',
        'uefa champions league': 'UEFA Champions League',
        'c1': 'UEFA Champions League',
        'cup c1': 'UEFA Champions League',
        'v-league': 'V-League',
        'vleague': 'V-League',
        'clb thai nguyen': 'Bóng đá Thái Nguyên',
        'cau lac bo thai nguyen': 'Bóng đá Thái Nguyên',
        'bong da thai nguyen': 'Bóng đá Thái Nguyên',
        'bong da o thai nguyen': 'Bóng đá Thái Nguyên',
        'bong da tai thai nguyen': 'Bóng đá Thái Nguyên',
        'bong da tinh thai nguyen': 'Bóng đá Thái Nguyên',
        'van dong vien thai nguyen': 'Bóng đá Thái Nguyên',
        'van dong vien o thai nguyen': 'Bóng đá Thái Nguyên',
        'van dong vien bong da thai nguyen': 'Bóng đá Thái Nguyên',
        'cau thu thai nguyen': 'Bóng đá Thái Nguyên',
        'cau thu o thai nguyen': 'Bóng đá Thái Nguyên',
        'cau thu bong da thai nguyen': 'Bóng đá Thái Nguyên',
        'cau thu nu thai nguyen': 'Thái Nguyên T&T',
        'vdv thai nguyen': 'Bóng đá Thái Nguyên',
        # Football — ICTU (Trường Đại học CNTT & TT Thái Nguyên)
        'truong dai hoc cong nghe thong tin va truyen thong': 'Bóng đá ICTU',
        'dai hoc cong nghe thong tin va truyen thong': 'Bóng đá ICTU',
        'truong cntt va truyen thong thai nguyen': 'Bóng đá ICTU',
        'cntt va truyen thong thai nguyen': 'Bóng đá ICTU',
        'truong dh cntt&tt': 'Bóng đá ICTU',
        'truong dh cntt va tt': 'Bóng đá ICTU',
        'dh cntt&tt thai nguyen': 'Bóng đá ICTU',
        'dh cntt va tt thai nguyen': 'Bóng đá ICTU',
        'dh cntt&tt': 'Bóng đá ICTU',
        'dh cntt va tt': 'Bóng đá ICTU',
        'doi tuyen bong da nam sinh vien ictu': 'Bóng đá ICTU',
        'doi bong sinh vien ictu': 'Bóng đá ICTU',
        'bong da sinh vien ictu': 'Bóng đá ICTU',
        'doi bong ictu': 'Bóng đá ICTU',
        'bong da ictu': 'Bóng đá ICTU',
        'ictu': 'Bóng đá ICTU',
        'giai bong da sinh vien ictu cup': 'ICTU CUP',
        'ictu cup': 'ICTU CUP',
        'doi bong khoa cntt ictu': 'Khoa CNTT ICTU',
        'bong da khoa cntt ictu': 'Khoa CNTT ICTU',
        'khoa cntt ictu': 'Khoa CNTT ICTU',
        'fit ictu': 'Khoa CNTT ICTU',
        'khoa ky thuat va cong nghe ictu': 'Khoa Kỹ thuật và Công nghệ ICTU',
        'fet ictu': 'Khoa Kỹ thuật và Công nghệ ICTU',
        # ICTU Multi-sports
        'cau long ictu': 'Cầu lông ICTU',
        'clb cau long ictu': 'Cầu lông ICTU',
        'phong trao cau long ictu': 'Cầu lông ICTU',
        'bong chuyen ictu': 'Bóng chuyền ICTU',
        'bong chuyen hoi ictu': 'Bóng chuyền ICTU',
        'doi bong chuyen ictu': 'Bóng chuyền ICTU',
        'clb bong chuyen ictu': 'Bóng chuyền ICTU',
        'phong trao bong chuyen ictu': 'Bóng chuyền ICTU',
        'bong ban ictu': 'Bóng bàn ICTU',
        'clb bong ban ictu': 'Bóng bàn ICTU',
        'phong trao bong ban ictu': 'Bóng bàn ICTU',
        'pickleball ictu': 'Pickleball ICTU',
        'pickle ball ictu': 'Pickleball ICTU',
        'san pickleball ictu': 'Pickleball ICTU',
        'the thao ictu': 'Thể thao ICTU',
        'phong trao the thao ictu': 'Thể thao ICTU',
        'clb the thao ictu': 'Thể thao ICTU',
        'the thao o ictu': 'Thể thao ICTU',
        'clb the thao o ictu': 'Thể thao ICTU',
        'cac mon the thao ictu': 'Thể thao ICTU',
        'mon the thao ictu': 'Thể thao ICTU',
        # Thai Nguyen General
        'the thao thai nguyen': 'Thể thao Thái Nguyên',
        'phong trao the thao thai nguyen': 'Thể thao Thái Nguyên',
        'cac mon the thao thai nguyen': 'Thể thao Thái Nguyên',
        'cac doi the thao thai nguyen': 'Thể thao Thái Nguyên',
        'cau long thai nguyen': 'Cầu lông Thái Nguyên',
        'clb cau long thai nguyen': 'Cầu lông Thái Nguyên',
        'phong trao cau long thai nguyen': 'Cầu lông Thái Nguyên',
        'bong chuyen thai nguyen': 'Bóng chuyền Thái Nguyên',
        'clb bong chuyen thai nguyen': 'Bóng chuyền Thái Nguyên',
        'pickleball thai nguyen': 'Pickleball Thái Nguyên',
        'clb pickleball thai nguyen': 'Pickleball Thái Nguyên',
        'tennis thai nguyen': 'Tennis Thái Nguyên',
        'clb tennis thai nguyen': 'Tennis Thái Nguyên',
        'bong ro thai nguyen': 'Bóng rổ Thái Nguyên',
        'clb bong ro thai nguyen': 'Bóng rổ Thái Nguyên',
        # Hanoi
        'ha noi fc': 'Hà Nội FC',
        'clb ha noi': 'Hà Nội FC',
        'the cong viettel': 'Thể Công Viettel',
        'viettel fc': 'Thể Công Viettel',
        'clb the cong': 'Thể Công Viettel',
        'cong an ha noi': 'Công an Hà Nội',
        'clb cong an ha noi': 'Công an Hà Nội',
        'cahn': 'Công an Hà Nội',
        'hanoi buffaloes': 'Hanoi Buffaloes',
        'thang long warriors': 'Thang Long Warriors',
        'bong da ha noi': 'Bóng đá Hà Nội',
        'clb bong da ha noi': 'Bóng đá Hà Nội',
        'doi bong ha noi': 'Bóng đá Hà Nội',
        'bong ro ha noi': 'Bóng rổ Hà Nội',
        'clb bong ro ha noi': 'Bóng rổ Hà Nội',
        'bong chuyen ha noi': 'Bóng chuyền Hà Nội',
        'doi bong chuyen ha noi': 'Bóng chuyền Hà Nội',
        'cau long ha noi': 'Cầu lông Hà Nội',
        'clb cau long ha noi': 'Cầu lông Hà Nội',
        'the thao ha noi': 'Thể thao Hà Nội',
        'phong trao the thao ha noi': 'Thể thao Hà Nội',
        'the thao thu do': 'Thể thao Hà Nội',
        'the thao dai hoc ha noi': 'Thể thao Đại học Hà Nội',
        'the thao sinh vien ha noi': 'Thể thao Đại học Hà Nội',
        'cac truong dai hoc ha noi': 'Thể thao Đại học Hà Nội',
        # TP.HCM
        'clb tp.hcm': 'Bóng đá TP.HCM',
        'clb tphcm': 'Bóng đá TP.HCM',
        'clb bong da tp.hcm': 'Bóng đá TP.HCM',
        'clb bong da tphcm': 'Bóng đá TP.HCM',
        'bong da tp.hcm': 'Bóng đá TP.HCM',
        'bong da tphcm': 'Bóng đá TP.HCM',
        'bong da sai gon': 'Bóng đá TP.HCM',
        'saigon heat': 'Saigon Heat',
        'ho chi minh city wings': 'Ho Chi Minh City Wings',
        'hcmc wings': 'Ho Chi Minh City Wings',
        'city wings': 'Ho Chi Minh City Wings',
        'bong ro tp.hcm': 'Bóng rổ TP.HCM',
        'bong ro tphcm': 'Bóng rổ TP.HCM',
        'bong ro sai gon': 'Bóng rổ TP.HCM',
        'clb bong ro tp.hcm': 'Bóng rổ TP.HCM',
        'clb bong ro tphcm': 'Bóng rổ TP.HCM',
        'cau long tp.hcm': 'Cầu lông TP.HCM',
        'cau long tphcm': 'Cầu lông TP.HCM',
        'clb cau long tp.hcm': 'Cầu lông TP.HCM',
        'clb cau long tphcm': 'Cầu lông TP.HCM',
        'bong ban tp.hcm': 'Bóng bàn TP.HCM',
        'bong ban tphcm': 'Bóng bàn TP.HCM',
        'bong chuyen tp.hcm': 'Bóng chuyền TP.HCM',
        'bong chuyen tphcm': 'Bóng chuyền TP.HCM',
        'maseco tp.hcm': 'Bóng chuyền TP.HCM',
        'the thao tp.hcm': 'Thể thao TP.HCM',
        'the thao tphcm': 'Thể thao TP.HCM',
        'the thao sai gon': 'Thể thao TP.HCM',
        'the thao thanh pho ho chi minh': 'Thể thao TP.HCM',
    }

    # Pre-compute normalized alias keys (sorted longest-first for greedy matching)
    _ALIAS_KEYS_SORTED: list[str] = sorted(ENTITY_ALIASES.keys(), key=len, reverse=True)

    TOPIC_ALIASES = {
        'cầu thủ': 'identity',
        'vận động viên': 'identity',
        'profile': 'identity',
        'tiểu sử': 'identity',
        'clb bóng đá': ('identity', 'achievements'),
        'clb bóng đá nữ': ('identity', 'achievements'),
        'clb bóng đá nam': ('identity', 'achievements'),
        'đội bóng thái nguyên': ('identity', 'achievements'),
        'clb bóng đá thái nguyên': ('identity', 'achievements'),
        'bóng đá nữ thái nguyên': ('identity', 'achievements'),
        'số lượng clb bóng đá': 'identity',
        'clb chuyên nghiệp thái nguyên': 'identity',
        'bóng đá sinh viên ictu': 'identity',
        'thành tích bóng đá ictu': ('achievements', 'career'),
        'giải bóng đá ictu cup': 'identity',
        'bóng đá nữ ictu': 'identity',
        'bóng đá khoa cntt ictu': 'identity',
        'bóng đá khoa kỹ thuật công nghệ ictu': 'identity',
        'phân biệt ictu và thái nguyên t&t': 'identity',
        'phân biệt ictu và fc thái nguyên': 'identity',
        'đội bóng sinh viên thái nguyên': 'identity',
        'phong trào thể thao ictu': 'identity',
        'cầu lông ictu': 'identity',
        'bóng chuyền ictu': 'identity',
        'bóng bàn ictu': 'identity',
        'pickleball ictu': 'identity',
        'clb thể thao ictu': 'identity',
        'tổng quan thể thao thái nguyên': 'identity',
        'tổng quan thể thao hà nội': 'identity',
        'clb bóng đá hà nội': 'identity',
        'clb bóng rổ hà nội': 'identity',
        'bóng chuyền hà nội': 'identity',
        'cầu lông hà nội': 'identity',
        'điền kinh & võ thuật hà nội': 'identity',
        'thể thao đại học hà nội': 'identity',
        'tổng quan thể thao tp.hcm': 'identity',
        'clb bóng đá tp.hcm': 'identity',
        'clb bóng rổ tp.hcm': 'identity',
        'cầu lông tp.hcm': 'identity',
        'bóng bàn tp.hcm': 'identity',
        'bóng chuyền tp.hcm': 'identity',
        'giải đấu': 'identity',
    }

    TOPIC_PATTERNS = {
        'identity': ('la ai', 'gioi thieu', 'tieu su', 'profil', 'ai la', 'la doi nao', 'la doi bong nao', 'la clb nao', 'la doi', 'la clb', 'co nhung doi nao', 'co nhung doi', 'co nhung clb nao', 'co nhung doi bong nao', 'co nhung clb', 'co nhung clb bong ro', 'co nhung mon nao', 'co nhung mon the thao nao', 'ngoai bong da con co mon gi', 'con co mon gi'),
        'birth_date': ('sinh ngay', 'ngay sinh', 'sinh nam', 'sinh ngay bao nhieu', 'sinh ngay nao', 'sinh vao ngay', 'sinh vao ngay nao', 'bao nhieu tuoi'),
        'birth_place': ('sinh o dau', 'noi sinh', 'que o dau', 'que quan', 'sinh tai', 'que o', 'quoc gia nao', 'den tu dau', 'den tu quoc gia', 'o nuoc nao', 'thuoc nuoc nao'),
        'current_club': ('clb hien tai', 'doi hien tai', 'dang choi cho', 'dang thi dau cho', 'khoac ao', 'dang da cho', 'thi dau cho clb nao', 'thi dau cho clb', 'thi dau cho doi nao', 'thi dau cho', 'choi cho doi nao', 'da cho clb nao', 'thi dau o dau', 'choi o dau', 'da o dau', 'dang da', 'dang choi', 'khoac ao doi nao', 'o doi nao', 'clb nao', 'doi nao', 'doi bong nao', 'clb bong chuyen nao', 'clb bong ro nao', 'clb bong da nao'),
        'career': ('qua trinh thi dau', 'su nghiep', 'tung thi dau', 'cac clb', 'qua trinh', 'thi dau o dau', 'thi dau tai dau'),
        'status': ('trang thai', 'giai nghe', 'con thi dau', 'da gia tu', 'giai nghe chua', 'da giai nghe'),
        'achievements': (
            'thanh tich', 'danh hieu', 'giai thuong', 'qua bong vang', 'huy chuong', 'cup vo dich',
            'chuc vo dich', 'vo dich', 'gianh cup', 'cup', 'wc', 'world cup', 'cup wc', 'c1', 'cup c1',
            'champions league', 'may qua', 'bao nhieu qua', 'bao nhieu cup', 'may cup', 'vo dich chua',
            'co cup chua', 'da co cup', 'co wc', 'co world cup', 'co c1', 'co qua bong vang', 'ballon d\'or', 'ballon dor'
        ),
        'host_location': ('to chuc o dau', 'dien ra o dau', 'dang cai o dau', 'dia diem to chuc', 'dia diem', 'to chuc tai dau', 'dien ra tai dau'),
        'top_scorer': ('vua pha luoi', 'ghi ban', 'ai ghi ban', 'ghi nhieu ban nhat', 'top scorer', 'cau thu ghi ban', 'chiec giay vang'),
        'match_result': ('thang ai', 'danh bai ai', 'ha ai', 'thang doi nao', 'danh bai doi nao', 'ha doi nao', 'chung ket', 'tran chung ket', 'vuot qua ai', 'vuot qua doi nao'),
        'founded': ('thanh lap', 'ngay thanh lap', 'nam thanh lap', 'thanh lap nam nao', 'thanh lap khi nao', 'ra mat khi nao', 'thanh lap vao nam'),
        'community': ('phong trao', 'phat trien phong trao', 'phat trien the nao', 'hoat dong sinh vien', 'tap luyen'),
    }

    def _resolve_all_entity_aliases(self, norm_query: str) -> list[str]:
        """Return all matching canonical entity names in the query."""
        results = []
        for alias_key in self._ALIAS_KEYS_SORTED:
            if alias_key in norm_query:
                canon = self.ENTITY_ALIASES[alias_key]
                if canon not in results:
                    results.append(canon)
        return results

    def _resolve_entity_alias(self, norm_query: str) -> Optional[str]:
        """Return the canonical entity name if the query contains a known alias, else None."""
        for alias_key in self._ALIAS_KEYS_SORTED:
            if alias_key in norm_query:
                return self.ENTITY_ALIASES[alias_key]
        return None

    def _keyword_score(self, query: str, question: str) -> float:
        # Simple fuzzy ratio in range [0, 1]
        return difflib.SequenceMatcher(None, self._normalize(query), self._normalize(question)).ratio()

    def _compute_kw_score(self, query: str, entry: KnowledgeEntry, target_entity: Optional[str] = None) -> float:
        norm_query = self._normalize(query)
        norm_question = self._normalize(entry.question)
        norm_ent = self._normalize(entry.entity) if entry.entity else ""
        target_norm = self._normalize(target_entity) if target_entity else ""

        q_tokens = [t for t in norm_query.split() if t]
        doc_q_tokens = set(norm_question.split())
        ent_tokens = set(norm_ent.split())

        matches_entity = bool(
            (norm_ent and norm_ent in norm_query)
            or (target_norm and (target_norm == norm_ent or target_norm in norm_ent or norm_ent in target_norm))
        )

        # Alias resolution: if direct match failed, check if any alias in the query
        # resolves to the same canonical entity as this entry.
        if not matches_entity and norm_ent:
            resolved_all = self._resolve_all_entity_aliases(norm_query)
            for resolved in resolved_all:
                if self._normalize(resolved) == norm_ent:
                    matches_entity = True
                    ent_tokens = set(self._normalize(resolved).split())
                    break

        # Strip entity phrases from query when checking topic patterns to prevent false topic matches
        query_for_topic = norm_query
        if norm_ent and norm_ent in query_for_topic:
            query_for_topic = query_for_topic.replace(norm_ent, ' ')
        if target_norm and target_norm in query_for_topic:
            query_for_topic = query_for_topic.replace(target_norm, ' ')
        # Also strip words like 'clb', 'doi bong', 'thanh pho' from topic check
        for token_strip in ('clb', 'doi bong', 'thanh pho', 'tinh'):
            query_for_topic = query_for_topic.replace(token_strip, ' ')

        # Identify all topics requested in the query
        query_matched_topics = set()
        for t_key, t_patterns in self.TOPIC_PATTERNS.items():
            if any(p in query_for_topic for p in t_patterns):
                query_matched_topics.add(t_key)

        topic_match = False
        topic_mismatch = False
        entry_topic_key = entry.topic.lower() if entry.topic else ""
        entry_topic_val = self.TOPIC_ALIASES.get(entry_topic_key, entry_topic_key)
        entry_topic_keys = {entry_topic_val} if isinstance(entry_topic_val, str) else set(entry_topic_val)

        valid_topic_keys = entry_topic_keys & set(self.TOPIC_PATTERNS.keys())
        if valid_topic_keys:
            if valid_topic_keys & query_matched_topics:
                topic_match = True
            elif query_matched_topics:
                topic_mismatch = True
        elif query_matched_topics and not ('identity' in query_matched_topics and len(query_matched_topics) == 1):
            topic_mismatch = True

        # If query is an individual/athlete/person question, prevent matching generic sport rules
        is_person_inquiry = any(p in norm_query for p in (
            'la ai', 'ai la', 'tieu su', 'profil', 'sinh nam', 'sinh ngay', 'que o', 'que quan', 'khoac ao',
            'van dong vien', 'vdv', 'cau thu', 'tay vot', 'co ai', 'nhung ai', 'ai gioi', 'ai dang la', 'nguoi choi',
        )) and not any(p in norm_query for p in ('kich thuoc', 'chieu cao luoi', 'chieu cao vanh', 'luat', 'san'))
        entry_id_norm = (getattr(entry, 'id', '') or '').lower()
        entry_top_norm = (entry.topic or '').lower()
        is_rule_entry = 'rule' in entry_id_norm or entry_top_norm in ('rules', 'luật', 'luật thi đấu', 'luật bóng đá', 'luật cầu lông')
        is_general_sport_rule = is_rule_entry or (entry.entity and self._normalize(entry.entity) in ('bong da', 'cau long', 'bong ro', 'bong chuyen', 'bong ban', 'tennis', 'pickleball', 'the thao'))
        if is_person_inquiry and is_general_sport_rule:
            return 0.10

        has_specific_trophy_in_q = any(k in norm_query for k in ('wc', 'world cup', 'c1', 'champions league', 'qua bong vang', 'ballon d\'or', 'ballon dor', 'qua bong'))

        if matches_entity:
            if topic_match:
                if has_specific_trophy_in_q:
                    doc_combined = (norm_question + " " + self._normalize(entry.answer))
                    for k in ('world cup', 'wc', 'champions league', 'c1', 'qua bong vang', 'ballon d\'or', 'ballon dor'):
                        if k in norm_query and (
                            k in doc_combined
                            or ('c1' in norm_query and 'champions league' in doc_combined)
                            or ('wc' in norm_query and 'world cup' in doc_combined)
                            or ('qua bong vang' in norm_query and 'ballon d\'or' in doc_combined)
                        ):
                            return 0.98
                return 0.95
            if topic_mismatch or (has_specific_trophy_in_q and entry_top_norm in ('identity', 'profile', 'cầu thủ', 'vận động viên')):
                return 0.20
            non_ent_q_tokens = [t for t in q_tokens if t not in ent_tokens]
            if not non_ent_q_tokens:
                # Pure entity lookup e.g. "Messi", "Đội tuyển Việt Nam"
                return 0.90
            # Common inquiry / question particles in Vietnamese
            inquiry_tokens = {'co', 'khong', 'la', 'gi', 'the', 'nao', 'o', 'dau', 'cho', 'hoi', 've', 'ra', 'sao', 'nhu', 'nhung', 'ai', 'con', 'sinh', 'va', 'cac'}
            content_non_ent = [t for t in non_ent_q_tokens if t not in inquiry_tokens]
            if not content_non_ent:
                # Pure entity inquiry e.g. "Thái Nguyên có cầu lông không?", "Giải bóng đá Nữ Quốc gia là gì?", "Còn Thùy Linh sinh ở đâu?"
                return 0.90
            # Follow-up phrases e.g. "con ... thi sao", "anh ay the nao"
            is_followup = any(t in non_ent_q_tokens for t in ('con', 'the', 'sao', 'thi', 'anh', 'ay', 'ong', 'co', 'chi'))
            doc_combined_tokens = set(self._normalize(f"{entry.question or ''} {entry.answer or ''} {entry.entity or ''}").split())
            matching_non_ent = [t for t in content_non_ent if t in doc_combined_tokens]
            non_ent_recall = len(matching_non_ent) / len(content_non_ent) if content_non_ent else 0.0
            if is_followup and len(non_ent_q_tokens) <= 4:
                return 0.85
            if non_ent_recall == 0.0 and len(content_non_ent) >= 2:
                return 0.20
            return 0.70 + 0.25 * non_ent_recall

        # If the query asks about a specific person/entity ("... là ai?", "... sinh năm nào?", "đang thi đấu cho CLB nào?", etc.) but no entity matched,
        # do not match random general rules or other players.
        is_entity_inquiry = any(p in norm_query for p in (
            'la ai', 'ai la', 'sinh nam', 'sinh ngay', 'que o', 'que quan', 'noi sinh',
            'dang choi cho', 'dang thi dau cho', 'thi dau cho', 'choi cho', 'dang da cho', 'da cho',
            'khoac ao', 'chuyen nhuong', 'gia nhap', 'roi clb', 'bao nhieu tuoi', 'con thi dau', 'da giai nghe'
        ))
        if is_entity_inquiry:
            return 0.10

        # Fallback if no entity match: check if query is asking for general athletes / players / stars in a sport, or sport + location overview
        is_sport_athletes_inquiry = any(p in norm_query for p in (
            'van dong vien', 'vdv', 'tay vot', 'cau thu', 'nguoi choi', 'co ai', 'nhung ai',
            'ai dang la', 'ai la van dong vien', 'ai la cau thu', 'ai la tay vot', 'ai gioi',
            'noi bat', 'noi tieng', 'gioi', 'hang dau', 'xuat sac', 'tieu bieu', 'ngoi sao',
            'cac van dong vien', 'nhung van dong vien', 'cac cau thu', 'nhung cau thu', 'cac tay vot',
            'danh sach van dong vien', 'danh sach cau thu', 'danh sach tay vot'
        ))
        is_sport_location_inquiry = any(p in norm_query for p in ('phong trao', 'thong tin', 'nhu the nao', 'the nao', 'phat trien', 'co gi', 'co nhung'))
        
        if is_sport_athletes_inquiry or is_sport_location_inquiry:
            entry_id = getattr(entry, 'id', '') or ''
            entry_top = (entry.topic or '').lower()
            if 'rule' in entry_id.lower() or entry_top in ('rules', 'luật'):
                return 0.10
            if entry.sport:
                entry_sport_norm = self._normalize(entry.sport)
                query_sport_matches = entry_sport_norm in norm_query
                if query_sport_matches:
                    doc_combined = self._normalize(f"{entry.entity or ''} {entry.question or ''} {entry.answer or ''}")
                    query_loc_matches = any(
                        loc in norm_query and loc in doc_combined
                        for loc in ('thai nguyen', 'ha noi', 'tphcm', 'tp hcm', 'da nang', 'viet nam', 'phu tho', 'hai duong', 'dong nai', 'binh duong', 'ninh binh')
                    )
                    if query_loc_matches:
                        return 0.90
                    is_person_profile = entry_top in ('identity', 'profile', 'cầu thủ', 'vận động viên', 'tieu su', 'clb bóng đá')
                    if is_person_profile and entry.entity and self._normalize(entry.entity) not in ('bong da', 'cau long', 'bong ro', 'bong chuyen', 'bong ban', 'tennis', 'pickleball', 'the thao'):
                        return 0.88

        seq_ratio = difflib.SequenceMatcher(None, norm_query, norm_question).ratio()
        matching_q_tokens = [t for t in q_tokens if t in doc_q_tokens]
        token_recall = len(matching_q_tokens) / len(q_tokens) if q_tokens else 0.0
        doc_combined = self._normalize(f"{entry.entity or ''} {entry.question or ''} {entry.answer or ''}")
        # If query has high token overlap with document title + answer
        combined_tokens = set(doc_combined.split())
        combined_overlap = len([t for t in q_tokens if t in combined_tokens]) / len(q_tokens) if q_tokens else 0.0
        if combined_overlap >= 0.50:
            return max(0.85, 0.50 * seq_ratio + 0.50 * combined_overlap)
        if len(matching_q_tokens) < 2 and seq_ratio < 0.80:
            return 0.20
        return 0.50 * seq_ratio + 0.50 * token_recall

    def _semantic_score(self, query: str, question_idx: int) -> float:
        if not self.use_semantic:
            return 0.0
        from sklearn.metrics.pairwise import cosine_similarity
        query_emb = self._model.encode([query], show_progress_bar=False)[0]
        return float(cosine_similarity([query_emb], [self._embeddings[question_idx]])[0, 0])

    def retrieve(
        self,
        query: str,
        role: Optional[str] = None,
        intent: Optional[str] = None,
        sport: Optional[str] = None,
        entity: Optional[str] = None,
        top_k: int = DEFAULT_TOP_K,
        relevance_threshold: float = RELEVANCE_THRESHOLD,
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """Return a list of (entry, score) sorted by descending relevance.

        If no entry reaches ``relevance_threshold`` an empty list is returned.
        Supports role, intent, sport, and entity filtering as well as priority weighting.
        """
        if not query:
            return []
        # Resolve entity alias so that callers can pass short names / nicknames
        if entity:
            resolved = self._resolve_entity_alias(self._normalize(entity))
            if resolved:
                entity = resolved
        norm_query = self._normalize(query)
        candidates = []
        for idx, entry in enumerate(self._static_entries):
            # Role filtering – entry.role may contain multiple roles separated by commas
            entry_roles = [r.strip().lower() for r in entry.role.split(',')]
            if role and role.lower() not in entry_roles:
                continue
            if intent and intent.upper() != entry.intent.upper():
                continue
            if sport and entry.sport and sport.lower() != entry.sport.lower():
                continue

            # Compute keyword similarity against question & entity
            kw_score = self._compute_kw_score(query, entry, target_entity=entity)

            # Compute semantic similarity if enabled
            sem_score = self._semantic_score(query, idx) if self.use_semantic else 0.0
            # Combine – simple average when both are available, otherwise use whichever exists
            if self.use_semantic:
                combined = (kw_score + sem_score) / 2.0
            else:
                combined = kw_score

            # Entity focus weighting for follow-up and entity disambiguation
            if entity and entry.entity:
                norm_target_ent = self._normalize(entity)
                resolved_target = self._resolve_entity_alias(norm_target_ent)
                if resolved_target:
                    norm_target_ent = self._normalize(resolved_target)
                norm_entry_ent = self._normalize(entry.entity)
                is_exact_ent = (norm_target_ent == norm_entry_ent)
                is_partial_ent = (norm_target_ent in norm_entry_ent or norm_entry_ent in norm_target_ent)
                if is_exact_ent:
                    if combined >= 0.58:
                        combined *= 1.3
                elif is_partial_ent:
                    if combined >= 0.58:
                        combined *= 1.15
                else:
                    # Conflicting named entity -> heavily penalize to prevent entity contamination
                    combined *= 0.15
            # Apply geographical priority weight: priority 3 (Thái Nguyên) -> +15%, priority 2 (VN) -> +8%
            if getattr(entry, 'priority', 0) and combined >= 0.58:
                combined = combined * (1.0 + 0.05 * entry.priority)

            candidates.append((entry, combined))

        # Sort by combined score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        # Apply relevance gate
        top_candidates = [c for c in candidates if c[1] >= relevance_threshold][:top_k]
        return top_candidates
