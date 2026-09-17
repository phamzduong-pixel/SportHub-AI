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
        'ronaldo': 'Cristiano Ronaldo',
        'cr7': 'Cristiano Ronaldo',
        'cristiano': 'Cristiano Ronaldo',
        # Football — Vietnam
        'quang hai': 'Nguyễn Quang Hải',
        'nguyen quang hai': 'Nguyễn Quang Hải',
        'tien linh': 'Nguyễn Tiến Linh',
        'nguyen tien linh': 'Nguyễn Tiến Linh',
        'hoang duc': 'Nguyễn Hoàng Đức',
        'nguyen hoang duc': 'Nguyễn Hoàng Đức',
        # Badminton
        'thuy linh': 'Nguyễn Thùy Linh',
        'nguyen thuy linh': 'Nguyễn Thùy Linh',
        'tien minh': 'Nguyễn Tiến Minh',
        'nguyen tien minh': 'Nguyễn Tiến Minh',
        'axelsen': 'Viktor Axelsen',
        'viktor axelsen': 'Viktor Axelsen',
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
        'clb thai nguyen': 'Bóng đá Thái Nguyên',
        'cau lac bo thai nguyen': 'Bóng đá Thái Nguyên',
        'bong da thai nguyen': 'Bóng đá Thái Nguyên',
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
    }

    TOPIC_PATTERNS = {
        'identity': ('la ai', 'gioi thieu', 'tieu su', 'profil', 'ai la', 'la doi nao', 'la doi bong nao', 'la clb nao', 'la doi', 'la clb', 'co nhung doi nao', 'co nhung clb nao'),
        'birth_date': ('sinh ngay', 'ngay sinh', 'sinh nam', 'sinh ngay bao nhieu', 'sinh ngay nao', 'sinh vao ngay', 'sinh vao ngay nao'),
        'birth_place': ('sinh o dau', 'noi sinh', 'que o dau', 'que quan', 'sinh tai', 'que o'),
        'current_club': ('clb hien tai', 'doi hien tai', 'dang choi cho', 'dang thi dau cho', 'khoac ao', 'dang da cho', 'thi dau cho clb nao', 'thi dau cho doi nao', 'choi cho doi nao', 'da cho clb nao', 'thi dau o dau', 'choi o dau'),
        'career': ('qua trinh thi dau', 'su nghiep', 'tung thi dau', 'cac clb', 'qua trinh', 'thi dau o dau', 'thi dau tai dau'),
        'status': ('trang thai', 'giai nghe', 'con thi dau', 'da gia tu', 'giai nghe chua', 'da giai nghe'),
        'achievements': ('thanh tich', 'danh hieu', 'giai thuong', 'qua bong vang', 'huy chuong', 'cup vo dich', 'chuc vo dich', 'vo dich', 'gianh cup'),
        'founded': ('thanh lap', 'ngay thanh lap', 'nam thanh lap', 'thanh lap nam nao', 'thanh lap khi nao', 'ra mat khi nao', 'thanh lap vao nam'),
    }

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

        # Alias resolution: if direct match failed, check if the query contains a known alias
        # that resolves to the same canonical entity as this entry.
        if not matches_entity and norm_ent:
            resolved = self._resolve_entity_alias(norm_query)
            if resolved and self._normalize(resolved) == norm_ent:
                matches_entity = True
                # Merge resolved canonical entity tokens so non-entity token filtering works correctly
                ent_tokens = set(self._normalize(resolved).split())

        # Strip entity phrases from query when checking topic patterns to prevent false topic matches
        query_for_topic = norm_query
        if norm_ent and norm_ent in query_for_topic:
            query_for_topic = query_for_topic.replace(norm_ent, ' ')
        if target_norm and target_norm in query_for_topic:
            query_for_topic = query_for_topic.replace(target_norm, ' ')

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

        if matches_entity:
            if topic_match:
                return 0.95
            non_ent_q_tokens = [t for t in q_tokens if t not in ent_tokens]
            if not non_ent_q_tokens:
                # Pure entity lookup e.g. "Messi", "Đội tuyển Việt Nam"
                return 0.90
            if topic_mismatch:
                return 0.20
            # Follow-up phrases e.g. "con ... thi sao", "anh ay the nao"
            is_followup = any(t in non_ent_q_tokens for t in ('con', 'the', 'sao', 'thi', 'anh', 'ay', 'ong', 'co', 'chi'))
            matching_non_ent = [t for t in non_ent_q_tokens if t in doc_q_tokens]
            non_ent_recall = len(matching_non_ent) / len(non_ent_q_tokens)
            if is_followup and len(non_ent_q_tokens) <= 4:
                return 0.85
            return 0.35 * 1.0 + 0.65 * non_ent_recall

        # Fallback if no entity match: combine sequence ratio and token recall
        seq_ratio = difflib.SequenceMatcher(None, norm_query, norm_question).ratio()
        matching_q_tokens = [t for t in q_tokens if t in doc_q_tokens]
        token_recall = len(matching_q_tokens) / len(q_tokens)
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
                    combined *= 0.5
            # Apply geographical priority weight: priority 3 (Thái Nguyên) -> +15%, priority 2 (VN) -> +8%
            if getattr(entry, 'priority', 0) and combined >= 0.58:
                combined = combined * (1.0 + 0.05 * entry.priority)

            candidates.append((entry, combined))

        # Sort by combined score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        # Apply relevance gate
        top_candidates = [c for c in candidates if c[1] >= relevance_threshold][:top_k]
        return top_candidates
