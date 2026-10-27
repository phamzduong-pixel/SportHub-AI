"""Synthetic, explicitly authorized sports records for retrieval integration tests."""

from app.models.knowledge_entry import KnowledgeEntry
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_service import KnowledgeService


TEST_USES = (
    "retrieve_internal",
    "prompt_llm_external",
    "display_answer",
    "display_citation",
)
_SYNTHETIC_AUTHORIZED_IDS: set[str] = set()


def authorized_sports_knowledge_service() -> KnowledgeService:
    """Build synthetic in-memory entries; values here are not production approvals."""
    repository = object.__new__(KnowledgeRepository)
    repository.knowledge_root = "<in-memory sports test fixture>"
    repository._entries = []
    service = KnowledgeService(repository=repository)

    rows = [
        ("TEST-MESSI-IDENTITY", "bóng đá", "Lionel Messi", "identity", "Messi là ai?",
         "Bản ghi hồ sơ giả lập: Lionel Messi là cầu thủ bóng đá người Argentina, có 8 Quả bóng vàng, thi đấu cho Inter Miami tại MLS và cùng Argentina vô địch World Cup 2022.", "FIFA (test fixture)", "https://example.test/fifa/messi", "2026-03-01"),
        ("TEST-MESSI-CLUB", "bóng đá", "Lionel Messi", "current_club", "Messi đang chơi cho đội nào? Anh ấy đang chơi cho đội nào?",
         "Trong bộ dữ liệu giả lập kiểm thử, Lionel Messi thi đấu cho Inter Miami tại MLS.", "MLS (test fixture)", "https://example.test/mls/messi", "2026-03-01"),
        ("TEST-MESSI-BIRTH", "bóng đá", "Lionel Messi", "birth_date", "Lionel Messi sinh ngày tháng năm nào?",
         "Trong bộ dữ liệu giả lập kiểm thử, Messi sinh ngày 24 tháng 6 năm 1987.", "FIFA (test fixture)", "https://example.test/fifa/messi-bio", "2026-03-01"),
        ("TEST-MESSI-TROPHIES", "bóng đá", "Lionel Messi", "achievements", "Messi có bao nhiêu Quả bóng vàng?",
         "Bản ghi kiểm thử nêu Messi có 8 Quả bóng vàng.", "FIFA (test fixture)", "https://example.test/fifa/messi-awards", "2026-03-01"),
        ("TEST-THUY-IDENTITY", "cầu lông", "Nguyễn Thùy Linh", "identity", "Nguyễn Thùy Linh là ai?",
         "Bản ghi kiểm thử mô tả Nguyễn Thùy Linh là tay vợt nữ số 1 Việt Nam.", "BWF (test fixture)", "https://example.test/bwf/thuy-linh", "2026-03-01"),
        ("TEST-THUY-BIRTH", "cầu lông", "Nguyễn Thùy Linh", "birth_date", "Nguyễn Thùy Linh sinh ngày tháng năm nào?",
         "Trong bộ dữ liệu giả lập kiểm thử, Nguyễn Thùy Linh sinh năm 1997.", "BWF (test fixture)", "https://example.test/bwf/thuy-linh-bio", "2026-03-01"),
        ("TEST-VN-BADMINTON", "cầu lông", "Cầu lông Việt Nam", "athletes", "Cầu lông Việt Nam có tay vợt nào tiêu biểu?",
         "Bản ghi kiểm thử liệt kê Nguyễn Thùy Linh và Nguyễn Tiến Minh.", "Test fixture", "https://example.test/badminton/vietnam", "2026-03-01"),
        ("TEST-QUANG-HAI", "bóng đá", "Quang Hải", "identity", "Quang Hải là ai?",
         "Bản ghi kiểm thử nhắc đến Quang Hải trong bóng đá Việt Nam.", "Test fixture", "https://example.test/football/quang-hai", "2026-03-01"),
        ("TEST-THAI-TT", "bóng đá", "Thái Nguyên T&T", "team_identity", "Thái Nguyên T&T là đội bóng nào?",
         "Thái Nguyên T&T là câu lạc bộ bóng đá trong bộ dữ liệu giả lập kiểm thử.", "Báo Thái Nguyên (test fixture)", "https://baothainguyen.vn/test-fixture/team", "2026-03-01"),
        ("TEST-THAI-LIST", "bóng đá", "Bóng đá Thái Nguyên", "clubs", "Ở Thái Nguyên có những CLB bóng đá nào?",
         "Danh sách giả lập kiểm thử gồm FC Thái Nguyên và Thái Nguyên T&T.", "Test fixture", "https://example.test/thai-nguyen/clubs", "2026-03-01"),
        ("TEST-THAI-FC", "bóng đá", "FC Thai Nguyen", "team_identity", "Đội Thái Nguyên thì sao? FC Thai Nguyen là đội nào?",
         "FC Thai Nguyen là đội bóng được dùng làm thực thể giả lập trong kiểm thử.", "Test fixture", "https://example.test/thai-nguyen/fc", "2026-03-01"),
        ("TEST-RONALDO-CLUB", "bóng đá", "Cristiano Ronaldo", "current_club", "Ronaldo hiện đang thi đấu cho câu lạc bộ nào?",
         "Trong bộ dữ liệu giả lập kiểm thử, Cristiano Ronaldo thi đấu cho Al-Nassr.", "Test fixture", "https://example.test/football/ronaldo", "2026-03-01"),
    ]
    for entry_id, sport, entity, topic, question, answer, source_name, source_url, collected_at in rows:
        entry = KnowledgeEntry(
            id=entry_id,
            topic=topic,
            role="CUSTOMER,OWNER,SYSTEM_ADMIN",
            intent="SPORTS_KNOWLEDGE",
            sport=sport,
            entity=entity,
            question=question,
            answer=answer,
            source=f"{source_name} ({source_url})",
            classification="static",
            source_name=source_name,
            source_url=source_url,
            collected_at=collected_at,
            priority=1,
            rights_status="approved",
            approved_uses=TEST_USES,
            record_status="active",
        )
        service.index_entry(entry)
    return service


def authorize_test_entry(entry, service: KnowledgeService) -> None:
    """Set synthetic metadata for a test only; does not create a review decision."""
    entry.rights_status = "approved"
    entry.approved_uses = TEST_USES
    entry.record_status = "active"
    _SYNTHETIC_AUTHORIZED_IDS.add(entry.id)
    service.update_entry(entry)


class SyntheticReviewAuthorizer:
    """Test double for an authenticated review gate; it writes no ledger decision."""

    status = "valid"

    @staticmethod
    def authorizes(entry, purpose):
        entry_id = getattr(entry, "id", "")
        return (
            isinstance(entry_id, str)
            and (entry_id.startswith("TEST-") or entry_id in _SYNTHETIC_AUTHORIZED_IDS)
            and purpose in TEST_USES
        )
