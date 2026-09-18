import unittest
from unittest.mock import MagicMock, patch

from app.models.knowledge_entry import KnowledgeEntry
from app.services.knowledge_update_service import (
    KnowledgeUpdateService,
    KnowledgeUpdateSummary,
)
from app.services.sports_knowledge_updater import (
    FactValidationStatus,
    KnowledgeUpdateAction,
    SportsKnowledgeUpdater,
)
from app.services.sports_web_retriever import SportsWebEvidence, SportsWebRetriever


class MockRepository:
    def __init__(self, initial_entries=None):
        self._entries = list(initial_entries or [])
        self.knowledge_root = "test_knowledge"

    def list_entries(self):
        return list(self._entries)

    def get_static_entries(self):
        return list(self._entries)

    def upsert_entry(self, entry):
        for idx, e in enumerate(self._entries):
            if e.id == entry.id:
                self._entries[idx] = entry
                return
        self._entries.append(entry)


class MockRetriever:
    def __init__(self):
        self.indexed_entries = []
        self.updated_entries = []

    def index_entry(self, entry):
        self.indexed_entries.append(entry)
        return True

    def update_entry(self, entry, force=True):
        self.updated_entries.append(entry)
        return True


class KnowledgeUpdateServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo = MockRepository()
        self.retriever = MockRetriever()
        self.web_retriever = SportsWebRetriever()
        self.service = KnowledgeUpdateService(
            repository=self.repo,
            retriever=self.retriever,
            web_retriever=self.web_retriever,
        )

    # 1. Approved Web Sources Only
    def test_approved_web_source_only(self):
        items = [
            {
                "url": "https://vff.org.vn/doi-tuyen-viet-nam-2026",
                "title": "Đội tuyển Việt Nam - Thông tin",
                "snippet": "Đội tuyển bóng đá nam quốc gia Việt Nam triệu tập danh sách mới chuẩn bị thi đấu.",
                "sport": "bóng đá",
                "entity": "Đội tuyển Việt Nam",
                "topic": "squad",
                "published_date": "2026-09-01",
            },
            {
                "url": "https://unapproved-random-blog.xyz/rumors",
                "title": "Tin đồn chuyển nhượng",
                "snippet": "Cầu thủ này sắp ký hợp đồng khủng.",
                "sport": "bóng đá",
                "entity": "Quang Hải",
                "topic": "transfer",
                "published_date": "2026-09-01",
            },
        ]

        summary = self.service.update_knowledge_pipeline(items)
        self.assertEqual(summary.total_sources_scanned, 2)
        self.assertEqual(summary.accepted, 1)
        self.assertEqual(summary.rejected, 1)
        self.assertEqual(summary.inserted, 1)
        # Check details
        self.assertEqual(summary.details[1]["action"], "REJECTED")
        self.assertEqual(summary.details[1]["status"], FactValidationStatus.REJECTED_UNAPPROVED_SOURCE.value)

    # 2. Supported 6 Sports Only
    def test_supported_6_sports_only(self):
        items = [
            {
                "url": "https://baothainguyen.vn/the-thao-badminton",
                "title": "CLB Cầu lông Thái Nguyên",
                "snippet": "CLB Cầu lông Thái Nguyên đạt giải nhất toàn đoàn tại giải đấu thanh thiếu niên.",
                "sport": "cầu lông",
                "entity": "Cầu lông Thái Nguyên",
                "topic": "achievement",
                "published_date": "2026-09-01",
            },
            {
                "url": "https://baothainguyen.vn/the-thao-golf",
                "title": "Giải Golf Thái Nguyên",
                "snippet": "Giải golf phong trào mở rộng tổ chức cuối tuần qua.",
                "sport": "golf",
                "entity": "Golf Thái Nguyên",
                "topic": "tournament",
                "published_date": "2026-09-01",
            },
        ]

        summary = self.service.update_knowledge_pipeline(items)
        self.assertEqual(summary.accepted, 1)
        self.assertEqual(summary.rejected, 1)
        self.assertEqual(summary.inserted, 1)
        self.assertEqual(summary.details[1]["status"], FactValidationStatus.REJECTED_OUT_OF_SCOPE_SPORT.value)

    # 3. Insert New Knowledge
    def test_insert_new_knowledge(self):
        items = [
            {
                "url": "https://baothainguyen.vn/pickleball-thai-nguyen-2026",
                "title": "CLB Pickleball Thái Nguyên",
                "snippet": "Phong trào Pickleball Thái Nguyên phát triển mạnh mẽ với hơn 500 thành viên sinh hoạt thường xuyên.",
                "sport": "pickleball",
                "entity": "Pickleball Thái Nguyên",
                "topic": "community",
                "published_date": "2026-09-05",
            }
        ]

        summary = self.service.update_knowledge_pipeline(items)
        self.assertEqual(summary.inserted, 1)
        self.assertEqual(summary.accepted, 1)
        self.assertEqual(summary.rejected, 0)
        self.assertEqual(len(self.repo.list_entries()), 1)
        self.assertEqual(self.repo.list_entries()[0].sport, "pickleball")
        self.assertEqual(len(self.retriever.indexed_entries), 1)

    # 4. Update Existing Knowledge
    def test_update_existing_knowledge(self):
        existing_entry = KnowledgeEntry(
            id="AUTO-FB-LIONELME-GEN",
            topic="current_club",
            role="CUSTOMER,OWNER,SYSTEM_ADMIN",
            intent="SPORTS_KNOWLEDGE",
            sport="bóng đá",
            entity="Lionel Messi",
            question="Lionel Messi đang thi đấu cho đội nào?",
            answer="Lionel Messi hiện đang thi đấu cho PSG.",
            source="VnExpress Thể Thao (https://vnexpress.net/the-thao/messi-psg)",
            source_name="VnExpress Thể Thao",
            source_url="https://vnexpress.net/the-thao/messi-psg",
            collected_at="2023-01-01",
            priority=2,
            classification="static",
        )
        self.repo._entries = [existing_entry]

        items = [
            {
                "url": "https://baothainguyen.vn/the-thao/messi-inter-miami",
                "title": "Lionel Messi - Inter Miami",
                "snippet": "Lionel Messi hiện đang thi đấu cho câu lạc bộ Inter Miami CF tại giải MLS Hoa Kỳ.",
                "sport": "bóng đá",
                "entity": "Lionel Messi",
                "topic": "current_club",
                "published_date": "2026-08-01",
            }
        ]

        summary = self.service.update_knowledge_pipeline(items)
        self.assertEqual(summary.updated, 1)
        self.assertEqual(summary.inserted, 0)
        self.assertEqual(summary.skipped, 0)
        # Entry answer updated
        self.assertIn("Inter Miami", self.repo.list_entries()[0].answer)
        self.assertEqual(len(self.retriever.updated_entries), 1)

    # 5. Duplicate Skipped
    def test_duplicate_skipped(self):
        existing_entry = KnowledgeEntry(
            id="AUTO-FB-LIONELME-GEN",
            topic="current_club",
            role="CUSTOMER,OWNER,SYSTEM_ADMIN",
            intent="SPORTS_KNOWLEDGE",
            sport="bóng đá",
            entity="Lionel Messi",
            question="Lionel Messi đang thi đấu cho đội nào?",
            answer="Lionel Messi hiện đang thi đấu cho câu lạc bộ Inter Miami CF tại giải MLS Hoa Kỳ.",
            source="Báo Thái Nguyên (https://baothainguyen.vn/the-thao/messi-inter-miami)",
            source_name="Báo Thái Nguyên",
            source_url="https://baothainguyen.vn/the-thao/messi-inter-miami",
            collected_at="2026-08-01",
            priority=2,
            classification="static",
        )
        self.repo._entries = [existing_entry]

        # Incoming fact with identical content
        items = [
            {
                "url": "https://baothainguyen.vn/the-thao/messi-inter-miami",
                "title": "Lionel Messi - Inter Miami",
                "snippet": "Lionel Messi hiện đang thi đấu cho câu lạc bộ Inter Miami CF tại giải MLS Hoa Kỳ.",
                "sport": "bóng đá",
                "entity": "Lionel Messi",
                "topic": "current_club",
                "published_date": "2026-08-15",
            }
        ]

        summary = self.service.update_knowledge_pipeline(items)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(summary.inserted, 0)
        self.assertEqual(summary.updated, 0)
        self.assertEqual(len(self.retriever.updated_entries), 0)

    # 6. Unverified Conflict Rejected (No Overwrite)
    def test_conflict_rejected_no_overwrite(self):
        official_entry = KnowledgeEntry(
            id="AUTO-FB-LIONELME-GEN",
            topic="current_club",
            role="CUSTOMER,OWNER,SYSTEM_ADMIN",
            intent="SPORTS_KNOWLEDGE",
            sport="bóng đá",
            entity="Lionel Messi",
            question="Lionel Messi đang thi đấu cho đội nào?",
            answer="Lionel Messi hiện đang thi đấu cho Inter Miami theo xác nhận chính thức từ FIFA.",
            source="FIFA (https://fifa.com/news/messi)",
            source_name="FIFA",
            source_url="https://fifa.com/news/messi",
            collected_at="2026-08-01",
            priority=1,  # Official priority
            classification="static",
        )
        self.repo._entries = [official_entry]

        # Incoming stale/older fact from secondary source
        stale_item = [
            {
                "url": "https://baothainguyen.vn/the-thao/messi-old",
                "title": "Lionel Messi",
                "snippet": "Lionel Messi đã ký hợp đồng chuyển sang thi đấu cho CLB Al-Hilal tại Ả Rập Xê Út.",
                "sport": "bóng đá",
                "entity": "Lionel Messi",
                "topic": "current_club",
                "published_date": "2024-01-01",  # Older date
            }
        ]

        summary = self.service.update_knowledge_pipeline(stale_item)
        self.assertEqual(summary.rejected, 1)
        self.assertEqual(summary.updated, 0)
        self.assertEqual(summary.inserted, 0)
        # Entry answer remains unchanged
        self.assertIn("Inter Miami", self.repo.list_entries()[0].answer)

    # 7. Provenance Preservation
    def test_provenance_preservation(self):
        items = [
            {
                "url": "https://baothainguyen.vn/the-thao/ictu-cup-2026",
                "title": "Giải bóng đá ICTU Cup",
                "snippet": "Giải bóng đá ICTU Cup 2026 quy tụ 16 đội tuyển sinh viên các khoa tham gia tranh tài sôi nổi.",
                "sport": "bóng đá",
                "entity": "Bóng đá ICTU",
                "topic": "tournament",
                "published_date": "2026-05-20",
            }
        ]

        summary = self.service.update_knowledge_pipeline(items)
        self.assertEqual(summary.inserted, 1)
        entry = self.repo.list_entries()[0]
        self.assertEqual(entry.source_name, "Báo Thái Nguyên")
        self.assertEqual(entry.source_url, "https://baothainguyen.vn/the-thao/ictu-cup-2026")
        self.assertEqual(entry.collected_at, "2026-05-20")
        self.assertEqual(entry.sport, "bóng đá")
        self.assertEqual(entry.entity, "Bóng đá ICTU")

    # 8. Error Resilience (One failed item does not break the job)
    def test_error_resilience_one_failed_source_does_not_break_job(self):
        items = [
            {
                "url": "https://vff.org.vn/valid-1",
                "title": "Đội tuyển Việt Nam",
                "snippet": "Đội tuyển bóng đá nam quốc gia Việt Nam chuẩn bị giải đấu mới.",
                "sport": "bóng đá",
                "entity": "Đội tuyển Việt Nam",
                "topic": "squad",
                "published_date": "2026-09-01",
            },
            # Malformed item that causes updater exception when forced
            None,
            {
                "url": "https://baothainguyen.vn/valid-2",
                "title": "Pickleball Thái Nguyên",
                "snippet": "Pickleball Thái Nguyên thu hút đông đảo người chơi thể thao phong trào.",
                "sport": "pickleball",
                "entity": "Pickleball Thái Nguyên",
                "topic": "community",
                "published_date": "2026-09-02",
            },
        ]

        # Patch extract_facts_from_raw_web_item to raise when item is None
        summary = self.service.update_knowledge_pipeline(items)
        self.assertEqual(summary.total_sources_scanned, 3)
        self.assertEqual(summary.inserted, 2)
        self.assertEqual(len(summary.errors), 1)
        self.assertEqual(summary.status, "PARTIAL_SUCCESS")

    # 9. Update from SportsWebEvidence
    def test_update_from_sports_web_evidence(self):
        evidences = [
            SportsWebEvidence(
                url="https://vff.org.vn/nu-viet-nam-2026",
                title="Đội tuyển nữ Việt Nam",
                source_name="Liên đoàn Bóng đá Việt Nam (VFF)",
                domain="vff.org.vn",
                snippet="Đội tuyển bóng đá nữ quốc gia Việt Nam bắt đầu đợt tập huấn mới tại Trung tâm Đào tạo bóng đá trẻ.",
                sport="bóng đá",
                published_date="2026-09-01",
                relevance_score=0.95,
                is_confirmed=True,
            )
        ]

        summary = self.service.update_from_web_evidence(evidences)
        self.assertEqual(summary.inserted, 1)
        self.assertEqual(summary.accepted, 1)
        self.assertEqual(summary.status, "COMPLETED")
        self.assertGreaterEqual(summary.duration_seconds, 0.0)

    # 10. Retrieval Integration Verification
    def test_retrieval_integration_after_update(self):
        from app.services.knowledge_service import KnowledgeService

        items = [
            {
                "url": "https://baothainguyen.vn/the-thao/clb-bong-ro-thai-nguyen",
                "title": "CLB Bóng rổ Thái Nguyên",
                "question": "Thông tin về CLB Bóng rổ Thái Nguyên?",
                "snippet": "CLB Bóng rổ Thái Nguyên thành lập năm 2022 và thường xuyên tổ chức giải đấu trẻ.",
                "sport": "bóng rổ",
                "entity": "Bóng rổ Thái Nguyên",
                "topic": "general",
                "published_date": "2026-09-01",
            }
        ]

        summary = self.service.update_knowledge_pipeline(items)
        self.assertEqual(summary.inserted, 1)

        # Real retriever can find the inserted entry
        real_repo = MockRepository(initial_entries=self.repo.list_entries())
        knowledge_service = KnowledgeService(repository=real_repo)
        results = knowledge_service.retrieve(
            query="Thông tin về CLB Bóng rổ Thái Nguyên",
            sport="bóng rổ",
            entity="Bóng rổ Thái Nguyên",
        )
        self.assertTrue(len(results) > 0)
        self.assertIn("2022", results[0][0].answer)


if __name__ == "__main__":
    unittest.main()
