import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from ..models.knowledge_entry import KnowledgeEntry
from .ai_intent_router import AssistantIntent, is_supported_sport, normalize_text


DEFAULT_SPORTS_SOURCE_WHITELIST: Dict[str, str] = {
    # 1. Official sports federations & organizers
    "vff.org.vn": "Liên đoàn Bóng đá Việt Nam (VFF)",
    "vpf.vn": "Công ty Cổ phần Bóng đá Chuyên nghiệp Việt Nam (VPF)",
    "vba.vn": "Giải Bóng rổ Chuyên nghiệp Việt Nam (VBA)",
    "fifa.com": "FIFA",
    "bwfbadminton.com": "BWF Badminton",
    "fiba.basketball": "FIBA Basketball",
    "itftennis.com": "ITF Tennis",
    "fivb.com": "FIVB Volleyball",

    # 2. Official government & local sports portals
    "svhttdl.thainguyen.gov.vn": "Sở VHTTDL Thái Nguyên",
    "thainguyen.gov.vn": "Cổng TTĐT Tỉnh Thái Nguyên",
    "sovanhoathethao.hanoi.gov.vn": "Sở Văn hóa & Thể thao Hà Nội",
    "hanoi.gov.vn": "Cổng TTĐT Thành phố Hà Nội",
    "svhtt.hochiminhcity.gov.vn": "Sở Văn hóa & Thể thao TP.HCM",
    "hochiminhcity.gov.vn": "Cổng TTĐT TP. Hồ Chí Minh",
    "tdtt.gov.vn": "Cục Thể dục Thể thao",
    "cucduc.gov.vn": "Cục TDTT Việt Nam",
    "bvhttdl.gov.vn": "Bộ Văn hóa, Thể thao và Du lịch",

    # 3. Official clubs, teams, universities & schools
    "ictu.edu.vn": "Trường ĐH Công nghệ Thông tin & Truyền thông Thái Nguyên",
    "fit.ictu.edu.vn": "Khoa CNTT - ICTU",
    "fet.ictu.edu.vn": "Khoa Kỹ thuật và Công nghệ - ICTU",
    "hanoifc.com.vn": "CLB Bóng đá Hà Nội",
    "saigonheat.com": "Saigon Heat",

    # 4. Reputable sports & news media
    "baothainguyen.vn": "Báo Thái Nguyên",
    "thanhnien.vn": "Báo Thanh Niên",
    "tuoitre.vn": "Báo Tuổi Trẻ",
    "vnexpress.net": "VnExpress Thể Thao",
    "thethao247.vn": "Thể Thao 247",
    "bongdaplus.vn": "Bóng Đá Plus",
    "webthethao.vn": "Webthethao",
    "baoxaydung.com.vn": "Báo Xây Dựng",
}

# High-volatility keywords / topics
HIGH_VOLATILITY_PATTERNS = (
    "dang thi dau cho",
    "dang thi dau o dau",
    "dang thi dau",
    "clb hien tai",
    "doi bong hien tai",
    "doi hien tai",
    "khoac ao",
    "dang khoac ao",
    "choi cho",
    "dang choi cho",
    "dang choi",
    "dang da cho",
    "dang da",
    "thi dau cho doi bong nao",
    "thi dau cho clb nao",
    "da cho doi bong nao",
    "da cho clb nao",
    "choi cho doi bong nao",
    "choi cho clb nao",
    "khoac ao clb nao",
    "thi dau o dau",
    "chuyen nhuong",
    "tin chuyen nhuong",
    "gia nhap",
    "roi clb",
    "hop dong",
    "ky hop dong",
    "roi khoi",
    "hlv hien tai",
    "huan luyen vien hien tai",
    "ai dang lam hlv",
    "ai dan dat",
    "ket qua tran",
    "ket qua thi dau",
    "ti so",
    "vua thang",
    "vua thua",
    "tran gan nhat",
    "bang xep hang",
    "xep hang hien tai",
    "top may",
    "dung thu may",
    "lich thi dau",
    "lich dau",
    "chan thuong",
    "treo gio",
    "co thi dau khong",
    "phong do hien tai",
    "tinh hinh thi dau",
    "ket qua moi nhat",
    "ket qua hom nay",
    "ti so moi nhat",
    "bang xep hang moi nhat",
    "vong bang",
    "tu ket",
    "ban ket",
    "chung ket",
    "mua giai 2024",
    "mua giai 2025",
    "mua giai 2026",
    "v-league 2024",
    "v-league 2025",
    "v-league 2026",
    "vba 2024",
    "vba 2025",
    "vba 2026",
)

# Stable keywords / topics
STABLE_PATTERNS = (
    "sinh nam",
    "ngay sinh",
    "que quan",
    "noi sinh",
    "la ai",
    "tieu su",
    "thanh tich",
    "danh hieu",
    "vo dich nam nao",
    "qua bong vang",
    "lich su",
    "ngay thanh lap",
    "nam thanh lap",
    "quy tac",
    "luat choi",
    "kich thuoc san",
    "quy mo",
)

# Rumor / speculation patterns
RUMOR_PATTERNS = (
    "tin don",
    "rumor",
    "nghi van",
    "co the gia nhap",
    "dang dam phan",
    "chua xac nhan",
    "du doan",
    "nguon tin noi bo",
    "chua chinh thuc",
    "theo loi don",
    "co the se",
    "ro tin",
)


OFFICIAL_SOURCE_DOMAINS = {
    "vff.org.vn", "vpf.vn", "vba.vn", "fifa.com", "bwfbadminton.com", "fiba.basketball",
    "itftennis.com", "fivb.com", "svhttdl.thainguyen.gov.vn", "thainguyen.gov.vn",
    "sovanhoathethao.hanoi.gov.vn", "hanoi.gov.vn", "svhtt.hochiminhcity.gov.vn",
    "hochiminhcity.gov.vn", "tdtt.gov.vn", "cucduc.gov.vn", "bvhttdl.gov.vn",
    "ictu.edu.vn", "fit.ictu.edu.vn", "fet.ictu.edu.vn", "hanoifc.com.vn", "saigonheat.com",
}

SPORT_SPECIFIC_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "football": ("bong da", "football", "soccer", "v-league", "vff", "fifa", "cau thu", "tien dao", "thu mon", "clb bong da", "giai bong da"),
    "badminton": ("cau long", "badminton", "tay vot", "bwf", "vot cau long", "nguyen thuy linh", "tien minh", "cau vot", "danh don", "danh doi"),
    "pickleball": ("pickleball", "pickle", "vot pickleball", "dink", "san pickleball"),
    "tennis": ("tennis", "quan vot", "tay vot tennis", "itf", "atp", "wta", "grand slam", "tie-break"),
    "basketball": ("bong ro", "basketball", "vba", "nba", "fiba", "saigon heat", "hanoi buffaloes", "nem bong"),
    "volleyball": ("bong chuyen", "volleyball", "fivb", "bong chuyen hoi", "dap bong"),
}


@dataclass
class SportsWebEvidence:
    url: str
    title: str
    source_name: str
    domain: str
    snippet: str
    sport: str | None = None
    published_date: str | None = None
    relevance_score: float = 0.0
    is_rumor: bool = False
    is_confirmed: bool = True


@dataclass
class FreshnessEvaluationResult:
    is_high_volatility: bool
    needs_fresh_web: bool
    reason: str
    internal_is_sufficient: bool


class SportsWebRetriever:
    """
    Controlled Web Evidence Retriever for SPORTS_KNOWLEDGE only.
    Enforces deterministic source whitelisting, sport scope verification,
    freshness & volatility evaluation, rumor filtering, combined ranking,
    and conflict resolution.
    """

    def __init__(
        self,
        whitelist: Dict[str, str] | None = None,
        search_provider: Optional[Callable[[str], List[Dict[str, Any]]]] = None,
    ):
        self.whitelist = dict(whitelist or DEFAULT_SPORTS_SOURCE_WHITELIST)
        self.search_provider = search_provider

    def is_whitelisted(self, url: str) -> tuple[bool, str]:
        """Check if a URL belongs to a whitelisted domain."""
        if not url:
            return False, ""
        try:
            parsed = urlparse(url)
            netloc = (parsed.netloc or parsed.path).lower().split(':')[0]
        except Exception:
            return False, ""

        for domain, name in self.whitelist.items():
            if netloc == domain or netloc.endswith("." + domain):
                return True, name
        return False, ""

    def can_retrieve(self, intent: str | AssistantIntent, sport: str | None = None, query: str = "") -> bool:
        """
        Verify that ONLY SPORTS_KNOWLEDGE within supported sport scope can trigger web retrieval.
        Business intents and OUT_OF_SCOPE are strictly forbidden.
        """
        intent_val = intent.value if isinstance(intent, AssistantIntent) else str(intent)
        if intent_val != AssistantIntent.SPORTS_KNOWLEDGE.value:
            return False

        if sport and not is_supported_sport(sport):
            return False

        return True

    def is_sports_related_content(self, text: str, sport: str | None = None) -> bool:
        """Verify that content is specifically sports-related and within supported scope."""
        norm = normalize_text(text)
        sports_keywords = (
            'bong da', 'cau long', 'pickleball', 'tennis', 'quan vot', 'bong ro', 'bong chuyen',
            'clb', 'cau lac bo', 'doi bong', 'giai dau', 'vo dich', 'huy chuong', 'cup', 'tran dau',
            'cau thu', 'vdv', 'van dong vien', 'tay vot', 'huan luyen vien', 'hlv', 'san van dong',
            'ictu cup', 'saigon heat', 'v-league', 'vba', 'vff', 'fifa'
        )
        has_sports_term = any(k in norm for k in sports_keywords)
        if not has_sports_term:
            return False

        if sport:
            canonical_sport = normalize_text(sport)
            # Map canonical names
            if 'bong da' in canonical_sport or 'football' in canonical_sport:
                expected_key = 'football'
            elif 'cau long' in canonical_sport or 'badminton' in canonical_sport:
                expected_key = 'badminton'
            elif 'pickleball' in canonical_sport:
                expected_key = 'pickleball'
            elif 'tennis' in canonical_sport or 'quan vot' in canonical_sport:
                expected_key = 'tennis'
            elif 'bong ro' in canonical_sport or 'basketball' in canonical_sport:
                expected_key = 'basketball'
            elif 'bong chuyen' in canonical_sport or 'volleyball' in canonical_sport:
                expected_key = 'volleyball'
            else:
                expected_key = None

            if expected_key and expected_key in SPORT_SPECIFIC_KEYWORDS:
                keywords = SPORT_SPECIFIC_KEYWORDS[expected_key]
                has_target_sport = any(k in norm for k in keywords)
                if not has_target_sport:
                    # Check if it exclusively belongs to another sport
                    other_sports = [k for s, kw in SPORT_SPECIFIC_KEYWORDS.items() if s != expected_key for k in kw]
                    if any(k in norm for k in other_sports) and not any(k in norm for k in ('the thao', 'clb', 'giai dau', 'ictu')):
                        return False
                    return False

        return True

    def is_high_volatility_query(self, query: str) -> bool:
        """Deterministically check if a sports query touches high-volatility information."""
        norm = normalize_text(query)
        if any(p in norm for p in ("co nhung doi", "co nhung clb", "co bao nhieu clb", "cac doi the thao", "cac mon the thao", "tong quan")):
            return False
        return any(pattern in norm for pattern in HIGH_VOLATILITY_PATTERNS)

    def is_rumor_or_unconfirmed(self, text: str) -> bool:
        """Detect if content contains rumors, unconfirmed reports, or speculation."""
        norm = normalize_text(text)
        return any(pattern in norm for pattern in RUMOR_PATTERNS)

    def compute_source_reliability(self, source_name: str | None, source_url: str | None) -> float:
        """Compute reliability weight of a source."""
        if source_url:
            try:
                parsed = urlparse(source_url)
                netloc = (parsed.netloc or "").lower().split(':')[0]
                for domain in OFFICIAL_SOURCE_DOMAINS:
                    if netloc == domain or netloc.endswith("." + domain):
                        return 1.0
            except Exception:
                pass
        if source_name and any(k in normalize_name(source_name) for k in ('chinh thuc', 'official', 'vff', 'fifa', 'lien doan', 'ictu', 'so vhtt')):
            return 1.0
        return 0.85

    def compute_freshness_score(self, date_str: str | None, current_date_str: str = "2026-09-17") -> float:
        """Compute freshness score based on date difference."""
        if not date_str:
            return 0.5
        try:
            target_dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            curr_dt = datetime.strptime(current_date_str[:10], "%Y-%m-%d")
            delta_days = (curr_dt - target_dt).days
            if delta_days < 0:
                delta_days = 0
            if delta_days <= 30:
                return 1.0
            elif delta_days <= 90:
                return 0.9
            elif delta_days <= 180:
                return 0.8
            elif delta_days <= 365:
                return 0.6
            else:
                return 0.3
        except Exception:
            return 0.5

    def compute_composite_score(
        self,
        query: str,
        base_relevance: float,
        source_name: str | None,
        source_url: str | None,
        collected_at: str | None,
        current_date_str: str = "2026-09-17",
    ) -> float:
        """Compute final ranking score combining relevance, source reliability, and freshness."""
        rel_score = max(0.0, min(1.0, base_relevance))
        reliab_score = self.compute_source_reliability(source_name, source_url)
        fresh_score = self.compute_freshness_score(collected_at, current_date_str)

        is_vol = self.is_high_volatility_query(query)
        if is_vol:
            return 0.40 * rel_score + 0.30 * reliab_score + 0.30 * fresh_score
        else:
            return 0.50 * rel_score + 0.35 * reliab_score + 0.15 * fresh_score

    def evaluate_freshness_and_sufficiency(
        self,
        query: str,
        internal_entries: List[Tuple[KnowledgeEntry, float]],
        current_date_str: str = "2026-09-17",
    ) -> FreshnessEvaluationResult:
        """
        Deterministic evaluator for freshness and sufficiency.
        Evaluates query volatility, metadata update dates, relevance, and completeness.
        """
        is_vol = self.is_high_volatility_query(query)
        norm_q = normalize_text(query)

        # No internal entries found -> Internal is not sufficient, web needed
        if not internal_entries:
            return FreshnessEvaluationResult(
                is_high_volatility=is_vol,
                needs_fresh_web=True,
                reason="No internal knowledge entries found.",
                internal_is_sufficient=False,
            )

        best_score = max(score for _, score in internal_entries)
        if best_score < 0.6:
            return FreshnessEvaluationResult(
                is_high_volatility=is_vol,
                needs_fresh_web=True,
                reason=f"Internal knowledge relevance score ({best_score:.2f}) is below threshold.",
                internal_is_sufficient=False,
            )

        if is_vol:
            try:
                curr_date = datetime.strptime(current_date_str, "%Y-%m-%d")
            except Exception:
                curr_date = datetime.now()

            is_stale = False
            for entry, _ in internal_entries:
                if entry.collected_at:
                    try:
                        entry_date = datetime.strptime(entry.collected_at, "%Y-%m-%d")
                        delta_days = (curr_date - entry_date).days
                        if delta_days > 60:
                            is_stale = True
                            break
                    except Exception:
                        pass
                else:
                    is_stale = True

            if is_stale:
                return FreshnessEvaluationResult(
                    is_high_volatility=True,
                    needs_fresh_web=True,
                    reason="Query is high-volatility and internal knowledge is potentially stale.",
                    internal_is_sufficient=False,
                )

            has_dynamic_topic = any(
                any(k in normalize_text(entry.answer) for k in ("clb", "doi bong", "thi dau", "chuyen nhuong", "hlv"))
                for entry, _ in internal_entries
            )
            if not has_dynamic_topic:
                return FreshnessEvaluationResult(
                    is_high_volatility=True,
                    needs_fresh_web=True,
                    reason="Internal knowledge does not contain specific high-volatility details.",
                    internal_is_sufficient=False,
                )

            return FreshnessEvaluationResult(
                is_high_volatility=True,
                needs_fresh_web=False,
                reason="Internal knowledge is fresh and sufficient for high-volatility topic.",
                internal_is_sufficient=True,
            )

        return FreshnessEvaluationResult(
            is_high_volatility=False,
            needs_fresh_web=False,
            reason="Query is stable and internal knowledge is sufficient.",
            internal_is_sufficient=True,
        )

    def retrieve_evidence(
        self,
        query: str,
        intent: str | AssistantIntent = AssistantIntent.SPORTS_KNOWLEDGE,
        sport: str | None = None,
        entity: str | None = None,
    ) -> List[SportsWebEvidence]:
        """
        Retrieve and filter web evidence for sports knowledge queries.
        Filters out rumors, unrelated sports, and non-whitelisted sources.
        """
        if not self.can_retrieve(intent, sport=sport, query=query):
            return []

        if not self.search_provider:
            return []

        search_query = f"{entity} {query}" if entity and entity not in query else query
        try:
            raw_results = self.search_provider(search_query)
        except Exception:
            return []

        valid_evidence: List[SportsWebEvidence] = []
        for item in raw_results:
            url = item.get("url", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "") or item.get("content", "")
            pub_date = item.get("published_date") or item.get("date")

            whitelisted, source_name = self.is_whitelisted(url)
            if not whitelisted:
                continue

            combined_text = f"{title} {snippet}"
            if not self.is_sports_related_content(combined_text, sport=sport):
                continue

            is_rumor = self.is_rumor_or_unconfirmed(combined_text)

            parsed = urlparse(url)
            domain = (parsed.netloc or "").lower()

            evidence = SportsWebEvidence(
                url=url,
                title=title,
                source_name=source_name,
                domain=domain,
                snippet=snippet,
                sport=sport,
                published_date=pub_date,
                relevance_score=float(item.get("relevance_score", 0.9)),
                is_rumor=is_rumor,
                is_confirmed=not is_rumor,
            )
            valid_evidence.append(evidence)

        return valid_evidence

    def detect_conflicts_and_supersede(
        self,
        query: str,
        entries: List[Tuple[KnowledgeEntry, float]],
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """
        Analyze entries for:
        1. Stale internal facts that are directly superseded by newer verified web evidence.
        2. Unresolved conflicting reports between reliable sources from similar timeframe.
        """
        if len(entries) <= 1:
            return entries

        is_vol = self.is_high_volatility_query(query)
        norm_q = normalize_text(query)

        # Separate web and internal
        web_entries = [e for e, s in entries if e.source == "web" and getattr(e, 'is_confirmed', True)]
        internal_entries = [e for e, s in entries if e.source != "web"]

        # Check for superseding: If web entry is recent (2026) and internal is older (< 2025)
        # on current club / status, drop the stale internal club answer
        if is_vol and web_entries and internal_entries:
            stale_internal_indices = []
            for i, int_e in enumerate(internal_entries):
                int_date = getattr(int_e, 'collected_at', '') or ''
                if int_date and int_date < '2025-01-01':
                    stale_internal_indices.append(int_e.id)

            if stale_internal_indices:
                entries = [(e, s) for e, s in entries if e.id not in stale_internal_indices]

        # Check for unresolved conflict between top web sources
        if len(web_entries) >= 2:
            w1, w2 = web_entries[0], web_entries[1]
            t1, t2 = normalize_text(w1.answer), normalize_text(w2.answer)
            # Check if snippets claim conflicting destinations or explicit disputes
            has_explicit_conflict = any(k in t1 or k in t2 for k in ('trai chieu', 'khac biet', 'chua thong nhat', 'tranh cai', 'bat dong'))
            # If both mention different clubs for the same player transfer query
            if has_explicit_conflict or ('gia nhap' in t1 and 'gia nhap' in t2 and t1 != t2):
                conflict_note = (
                    f"Lưu ý: Hiện có sự khác biệt giữa các nguồn tin "
                    f"({w1.source_name} và {w2.source_name}). Cần chờ thông báo chính thức thống nhất."
                )
                conflict_entry = KnowledgeEntry(
                    id="CONFLICT-NOTE",
                    topic="Thể thao",
                    role="CUSTOMER",
                    intent="SPORTS_KNOWLEDGE",
                    question=query,
                    answer=conflict_note,
                    source="system",
                    classification="static",
                    priority=3,
                )
                return [(conflict_entry, 1.0)] + entries

        return entries

    def merge_and_prefer_evidence(
        self,
        query: str,
        internal_entries: List[Tuple[KnowledgeEntry, float]],
        web_evidences: List[SportsWebEvidence],
        current_date_str: str = "2026-09-17",
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """
        Combine Internal Knowledge RAG and validated Web Evidence:
        - Score and rank each candidate based on relevance, source reliability, and freshness.
        - Supersede stale internal facts when newer verified web evidence exists.
        - Retain stable internal facts (e.g. background/achievements) alongside fresh web evidence.
        - Flag unresolved conflicting reports when detected.
        """
        is_vol = self.is_high_volatility_query(query)
        confirmed_web = [ev for ev in web_evidences if ev.is_confirmed]

        # Process and score internal entries
        scored_entries: List[Tuple[KnowledgeEntry, float]] = []
        for entry, base_score in internal_entries:
            composite = self.compute_composite_score(
                query=query,
                base_relevance=base_score,
                source_name=getattr(entry, 'source_name', None) or entry.source,
                source_url=getattr(entry, 'source_url', None),
                collected_at=getattr(entry, 'collected_at', None),
                current_date_str=current_date_str,
            )
            scored_entries.append((entry, composite))

        # Process and score web entries
        for i, ev in enumerate(confirmed_web):
            entry = KnowledgeEntry(
                id=f"WEB-{i+1}",
                topic="Thể thao",
                role="CUSTOMER",
                intent="SPORTS_KNOWLEDGE",
                question=query,
                answer=ev.snippet,
                source="web",
                classification="static",
                sport=ev.sport,
                entity=None,
                source_name=ev.source_name,
                source_url=ev.url,
                collected_at=ev.published_date or current_date_str,
                priority=2 if is_vol else 1,
            )
            composite = self.compute_composite_score(
                query=query,
                base_relevance=ev.relevance_score,
                source_name=ev.source_name,
                source_url=ev.url,
                collected_at=ev.published_date or current_date_str,
                current_date_str=current_date_str,
            )
            scored_entries.append((entry, composite))

        # Sort combined evidence by composite score descending
        scored_entries.sort(key=lambda x: x[1], reverse=True)

        # Detect conflicts & supersede stale facts
        final_entries = self.detect_conflicts_and_supersede(query, scored_entries)
        return final_entries


def normalize_name(name: str) -> str:
    return normalize_text(name)

