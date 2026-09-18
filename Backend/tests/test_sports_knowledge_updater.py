import unittest
from unittest.mock import MagicMock

from app.models.knowledge_entry import KnowledgeEntry
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.sports_knowledge_updater import (
    ExtractedSportsFact,
    FactValidationStatus,
    KnowledgeUpdateAction,
    SportsKnowledgeUpdater,
)
from app.services.sports_web_retriever import SportsWebEvidence, SportsWebRetriever


class SportsKnowledgeUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.mock_repo = MagicMock(spec=KnowledgeRepository)
        self.mock_repo.knowledge_root = "test_knowledge"
        self.sample_entries = [
            KnowledgeEntry(
                id="PLY-FB-MESSI-003",
                topic="current_club",
                role="CUSTOMER,OWNER,SYSTEM_ADMIN",
                intent="SPORTS_KNOWLEDGE",
                sport="bóng đá",
                entity="Lionel Messi",
                question="Messi hiện thi đấu cho CLB nào?",
                answer="Lionel Messi hiện đang thi đấu cho câu lạc bộ Inter Miami CF.",
                source_name="MLS Soccer",
                source_url="https://www.mlssoccer.com/players/lionel-messi/",
                collected_at="2026-01-01",
                priority=1,
                classification="static",
                source="MLS Soccer (https://www.mlssoccer.com/players/lionel-messi/)",
            )
        ]
        self.mock_repo._entries = list(self.sample_entries)
        self.mock_repo.list_entries.side_effect = lambda: self.mock_repo._entries
        self.updater = SportsKnowledgeUpdater(repository=self.mock_repo, retriever=SportsWebRetriever())

    # 1. Insert new knowledge
    def test_insert_new_knowledge_entry(self):
        fact = ExtractedSportsFact(
            sport="cầu lông",
            entity="Nguyễn Thùy Linh",
            topic="current_ranking",
            question="Nguyễn Thùy Linh hiện xếp thứ mấy thế giới?",
            answer="Nguyễn Thùy Linh hiện đang xếp hạng 22 thế giới theo bảng xếp hạng mới nhất của BWF.",
            source_name="BWF Badminton",
            source_url="https://bwfbadminton.com/rankings/thuy-linh",
            collected_at="2026-09-15",
            priority=1,
            is_confirmed=True,
            reliability_score=0.95,
        )

        result = self.updater.apply_fact_update(fact, persist_markdown=False)
        self.assertEqual(result.action, KnowledgeUpdateAction.INSERTED)
        self.assertIsNotNone(result.entry_id)
        self.assertTrue(result.entry_id.startswith("AUTO-BDM-"))
        self.assertIn("Inserted new knowledge", result.message)
        # Entry added to repository list
        self.assertEqual(len(self.mock_repo._entries), 2)
        self.assertEqual(self.mock_repo._entries[-1].entity, "Nguyễn Thùy Linh")

    # 2. Update existing knowledge
    def test_update_existing_knowledge_entry(self):
        # Update Messi's current club with newer verified statement
        fact = ExtractedSportsFact(
            sport="bóng đá",
            entity="Lionel Messi",
            topic="current_club",
            question="Messi hiện thi đấu cho CLB nào?",
            answer="Lionel Messi gia hạn và tiếp tục thi đấu cho CLB Inter Miami CF với tư cách đội trưởng.",
            source_name="FIFA",
            source_url="https://fifa.com/news/messi-inter-miami-2026",
            collected_at="2026-09-10",
            priority=1,
            is_confirmed=True,
            reliability_score=0.98,
        )

        result = self.updater.apply_fact_update(fact, persist_markdown=False)
        self.assertEqual(result.action, KnowledgeUpdateAction.UPDATED)
        self.assertEqual(result.entry_id, "PLY-FB-MESSI-003")
        self.assertIn("Updated existing knowledge", result.message)
        # Content in repository was updated
        updated_entry = self.mock_repo._entries[0]
        self.assertEqual(updated_entry.answer, fact.answer)
        self.assertEqual(updated_entry.collected_at, "2026-09-10")
        self.assertEqual(updated_entry.source_name, "FIFA")

    # 3. Duplicate detection
    def test_duplicate_fact_is_skipped(self):
        # Exact same answer
        fact = ExtractedSportsFact(
            sport="bóng đá",
            entity="Lionel Messi",
            topic="current_club",
            question="Messi hiện thi đấu cho CLB nào?",
            answer="Lionel Messi hiện đang thi đấu cho câu lạc bộ Inter Miami CF.",
            source_name="MLS Soccer",
            source_url="https://www.fifa.com/players/messi",
            collected_at="2026-09-12",
            priority=1,
            is_confirmed=True,
            reliability_score=0.95,
        )

        result = self.updater.apply_fact_update(fact, persist_markdown=False)
        self.assertEqual(result.action, KnowledgeUpdateAction.DUPLICATE_SKIPPED)
        self.assertEqual(result.entry_id, "PLY-FB-MESSI-003")
        self.assertIn("Duplicate skipped", result.message)
        # Entry count remains 1
        self.assertEqual(len(self.mock_repo._entries), 1)
        # Timestamp refreshed
        self.assertEqual(self.mock_repo._entries[0].collected_at, "2026-09-12")

    # 4. Invalid / out-of-scope fact rejection
    def test_rejected_out_of_scope_sport(self):
        # Sport 'bơi lội' is outside the 6 supported sports
        fact = ExtractedSportsFact(
            sport="bơi lội",
            entity="Ánh Viên",
            topic="achievements",
            question="Thành tích của Ánh Viên?",
            answer="Nguyễn Thị Ánh Viên đã giành được 25 huy chương vàng SEA Games.",
            source_name="Báo Tuổi Trẻ",
            source_url="https://tuoitre.vn/the-thao/anh-vien",
            collected_at="2026-09-10",
        )
        val = self.updater.validate_fact(fact)
        self.assertFalse(val.is_valid)
        self.assertEqual(val.status, FactValidationStatus.REJECTED_OUT_OF_SCOPE_SPORT)

        res = self.updater.apply_fact_update(fact)
        self.assertEqual(res.action, KnowledgeUpdateAction.REJECTED)

    def test_rejected_unapproved_source(self):
        # Random blog / unapproved domain
        fact = ExtractedSportsFact(
            sport="bóng đá",
            entity="Quang Hải",
            topic="current_club",
            question="Quang Hải đá cho đội nào?",
            answer="Quang Hải đang thi đấu tại V-League.",
            source_name="Blog Bóng Đá",
            source_url="https://random-football-blog.xyz/quang-hai",
            collected_at="2026-09-10",
        )
        val = self.updater.validate_fact(fact)
        self.assertFalse(val.is_valid)
        self.assertEqual(val.status, FactValidationStatus.REJECTED_UNAPPROVED_SOURCE)

    def test_rejected_rumor_and_speculation(self):
        # Rumor pattern in answer
        fact = ExtractedSportsFact(
            sport="bóng đá",
            entity="Quang Hải",
            topic="transfer",
            question="Quang Hải chuyển nhượng đi đâu?",
            answer="Theo tin đồn nội bộ rộ tin Quang Hải có thể sẽ sang thi đấu ở Nhật Bản.",
            source_name="Báo Thanh Niên",
            source_url="https://thanhnien.vn/the-thao/quang-hai-tin-don",
            collected_at="2026-09-10",
            is_confirmed=False,
        )
        val = self.updater.validate_fact(fact)
        self.assertFalse(val.is_valid)
        self.assertEqual(val.status, FactValidationStatus.REJECTED_RUMOR)

    # 5. Provenance validation
    def test_provenance_fields_preserved(self):
        fact = ExtractedSportsFact(
            sport="pickleball",
            entity="Giải Pickleball Quốc gia 2026",
            topic="schedule",
            question="Lịch thi đấu giải Pickleball Quốc gia 2026?",
            answer="Giải Pickleball Vô địch Quốc gia 2026 diễn ra từ ngày 15 đến 20 tháng 10 tại Hà Nội.",
            source_name="Cục Thể dục Thể thao",
            source_url="https://tdtt.gov.vn/giai-pickleball-2026",
            collected_at="2026-09-14",
            priority=1,
            is_confirmed=True,
            reliability_score=0.96,
        )
        result = self.updater.apply_fact_update(fact, persist_markdown=False)
        self.assertEqual(result.action, KnowledgeUpdateAction.INSERTED)
        entry = result.entry
        self.assertIsNotNone(entry)
        self.assertEqual(entry.source_url, "https://tdtt.gov.vn/giai-pickleball-2026")
        self.assertEqual(entry.source_name, "Cục Thể dục Thể thao")
        self.assertEqual(entry.entity, "Giải Pickleball Quốc gia 2026")
        self.assertEqual(entry.sport, "pickleball")
        self.assertEqual(entry.collected_at, "2026-09-14")

    # 6. Conflict handling
    def test_conflict_rejected_when_incoming_date_is_older(self):
        # Existing entry date is 2026-01-01. Incoming conflicting fact has older date 2025-05-01.
        fact = ExtractedSportsFact(
            sport="bóng đá",
            entity="Lionel Messi",
            topic="current_club",
            question="Messi hiện thi đấu cho CLB nào?",
            answer="Lionel Messi đã chuyển sang thi đấu cho CLB Barcelona ở La Liga.",
            source_name="FIFA",
            source_url="https://fifa.com/messi-old",
            collected_at="2025-05-01",
            priority=1,
            is_confirmed=True,
            reliability_score=0.95,
        )
        result = self.updater.apply_fact_update(fact, persist_markdown=False)
        self.assertEqual(result.action, KnowledgeUpdateAction.CONFLICT_REJECTED)
        self.assertIn("older than existing entry", result.message)
        # Existing entry was NOT modified
        self.assertEqual(self.mock_repo._entries[0].answer, "Lionel Messi hiện đang thi đấu cho câu lạc bộ Inter Miami CF.")

    # 7. End-to-end batch processing pipeline
    def test_process_pipeline_batch(self):
        batch = [
            {
                "url": "https://vff.org.vn/u23-viet-nam-2026",
                "title": "U23 Việt Nam",
                "content": "Đội tuyển U23 Việt Nam đã hoàn tất danh sách tập trung chuẩn bị vòng chung kết châu Á.",
                "sport": "bóng đá",
                "entity": "U23 Việt Nam",
                "topic": "squad",
                "published_date": "2026-09-16",
            },
            {
                "url": "https://invalid-untrusted-news.com/messi",
                "title": "Messi",
                "content": "Messi ghi bàn trong trận đấu mới.",
                "sport": "bóng đá",
                "entity": "Lionel Messi",
                "topic": "goal",
            },
        ]
        results = self.updater.process_pipeline(batch, persist_markdown=False)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].action, KnowledgeUpdateAction.INSERTED)
        self.assertEqual(results[1].action, KnowledgeUpdateAction.REJECTED)

    # 8. CP-06B Incremental Indexing & Retrieval Tests
    def test_incremental_index_new_knowledge_and_retrieve_in_rag(self):
        from app.services.knowledge_retriever import KnowledgeRetriever
        from app.services.knowledge_service import KnowledgeService

        repo = KnowledgeRepository(knowledge_root="nonexistent_dir")
        repo._entries = [
            KnowledgeEntry(
                id="PLY-FB-MESSI-001",
                topic="identity",
                role="CUSTOMER,OWNER,SYSTEM_ADMIN",
                intent="SPORTS_KNOWLEDGE",
                sport="bóng đá",
                entity="Lionel Messi",
                question="Lionel Messi là ai?",
                answer="Lionel Messi là cầu thủ bóng đá chuyên nghiệp người Argentina.",
                source="FIFA",
                classification="static",
                priority=1,
            )
        ]
        retriever = KnowledgeRetriever(repository=repo, use_semantic=False)
        knowledge_service = KnowledgeService(repository=repo, retriever=retriever)
        updater = SportsKnowledgeUpdater(repository=repo, knowledge_retriever=retriever)

        # Fact for new entity (Nguyễn Thùy Linh)
        fact = ExtractedSportsFact(
            sport="cầu lông",
            entity="Nguyễn Thùy Linh",
            topic="achievements",
            question="Thành tích của Nguyễn Thùy Linh là gì?",
            answer="Nguyễn Thùy Linh là tay vợt cầu lông số 1 Việt Nam, từng vô địch Vietnam Open và tham dự Olympic.",
            source_name="BWF Badminton",
            source_url="https://bwfbadminton.com/news/thuy-linh",
            collected_at="2026-09-15",
            priority=1,
            is_confirmed=True,
            reliability_score=0.95,
        )

        update_res = updater.apply_fact_update(fact, persist_markdown=False)
        self.assertEqual(update_res.action, KnowledgeUpdateAction.INSERTED)
        self.assertTrue(update_res.is_indexed)

        # Verify KnowledgeRetriever can immediately retrieve the new fact without full rebuild
        retrieved = knowledge_service.retrieve(
            query="Thành tích của Nguyễn Thùy Linh",
            sport="cầu lông",
            entity="Nguyễn Thùy Linh",
        )
        self.assertTrue(len(retrieved) > 0)
        top_entry, score = retrieved[0]
        self.assertEqual(top_entry.entity, "Nguyễn Thùy Linh")
        self.assertIn("tay vợt cầu lông số 1 Việt Nam", top_entry.answer)
        self.assertGreaterEqual(score, 0.60)

    def test_incremental_reindex_updated_knowledge_and_retrieve_in_rag(self):
        from app.services.knowledge_retriever import KnowledgeRetriever
        from app.services.knowledge_service import KnowledgeService

        repo = KnowledgeRepository(knowledge_root="nonexistent_dir")
        repo._entries = [
            KnowledgeEntry(
                id="PLY-FB-MESSI-003",
                topic="current_club",
                role="CUSTOMER,OWNER,SYSTEM_ADMIN",
                intent="SPORTS_KNOWLEDGE",
                sport="bóng đá",
                entity="Lionel Messi",
                question="Messi hiện thi đấu cho CLB nào?",
                answer="Lionel Messi hiện đang thi đấu cho PSG.",
                source="PSG Official",
                collected_at="2022-01-01",
                classification="static",
                priority=2,
            )
        ]
        retriever = KnowledgeRetriever(repository=repo, use_semantic=False)
        knowledge_service = KnowledgeService(repository=repo, retriever=retriever)
        updater = SportsKnowledgeUpdater(repository=repo, knowledge_retriever=retriever)

        # Update Messi's club to Inter Miami
        fact = ExtractedSportsFact(
            sport="bóng đá",
            entity="Lionel Messi",
            topic="current_club",
            question="Messi hiện thi đấu cho CLB nào?",
            answer="Lionel Messi hiện đang thi đấu cho câu lạc bộ Inter Miami CF tại MLS.",
            source_name="FIFA",
            source_url="https://fifa.com/players/lionel-messi",
            collected_at="2026-09-16",
            priority=1,
            is_confirmed=True,
            reliability_score=0.98,
        )

        update_res = updater.apply_fact_update(fact, persist_markdown=False)
        self.assertEqual(update_res.action, KnowledgeUpdateAction.UPDATED)
        self.assertTrue(update_res.is_indexed)

        # Retrieve through RAG
        retrieved = knowledge_service.retrieve(
            query="Messi hiện đang đá cho clb nào?",
            sport="bóng đá",
            entity="Lionel Messi",
        )
        self.assertTrue(len(retrieved) > 0)
        top_entry, score = retrieved[0]
        self.assertEqual(top_entry.id, "PLY-FB-MESSI-003")
        self.assertIn("Inter Miami CF", top_entry.answer)
        self.assertNotIn("PSG", top_entry.answer)

    def test_unchanged_knowledge_skips_reindexing(self):
        from app.services.knowledge_retriever import KnowledgeRetriever

        repo = KnowledgeRepository(knowledge_root="nonexistent_dir")
        existing_entry = KnowledgeEntry(
            id="PLY-FB-MESSI-003",
            topic="current_club",
            role="CUSTOMER,OWNER,SYSTEM_ADMIN",
            intent="SPORTS_KNOWLEDGE",
            sport="bóng đá",
            entity="Lionel Messi",
            question="Messi hiện thi đấu cho CLB nào?",
            answer="Lionel Messi hiện đang thi đấu cho Inter Miami.",
            source="FIFA",
            collected_at="2026-01-01",
            classification="static",
            priority=1,
        )
        repo._entries = [existing_entry]
        retriever = KnowledgeRetriever(repository=repo, use_semantic=False)
        updater = SportsKnowledgeUpdater(repository=repo, knowledge_retriever=retriever)

        # Incoming fact with identical content
        fact = ExtractedSportsFact(
            sport="bóng đá",
            entity="Lionel Messi",
            topic="current_club",
            question="Messi hiện thi đấu cho CLB nào?",
            answer="Lionel Messi hiện đang thi đấu cho Inter Miami.",
            source_name="FIFA",
            source_url="https://fifa.com/players/lionel-messi",
            collected_at="2026-09-17",
            priority=1,
            is_confirmed=True,
            reliability_score=0.95,
        )

        update_res = updater.apply_fact_update(fact, persist_markdown=False)
        self.assertEqual(update_res.action, KnowledgeUpdateAction.DUPLICATE_SKIPPED)
        self.assertFalse(update_res.is_indexed)
        # Entry count remains unchanged
        self.assertEqual(len(retriever._static_entries), 1)

    def test_rejected_fact_not_indexed_and_not_retrievable(self):
        from app.services.knowledge_retriever import KnowledgeRetriever
        from app.services.knowledge_service import KnowledgeService

        repo = KnowledgeRepository(knowledge_root="nonexistent_dir")
        repo._entries = []
        retriever = KnowledgeRetriever(repository=repo, use_semantic=False)
        knowledge_service = KnowledgeService(repository=repo, retriever=retriever)
        updater = SportsKnowledgeUpdater(repository=repo, knowledge_retriever=retriever)

        # Rumor fact
        fact = ExtractedSportsFact(
            sport="bóng đá",
            entity="Quang Hải",
            topic="transfer",
            question="Quang Hải đi đâu?",
            answer="Rộ tin đồn Quang Hải có thể chuyển sang giải đấu khác.",
            source_name="VFF",
            source_url="https://vff.org.vn/news",
            collected_at="2026-09-15",
            is_confirmed=False,
        )

        update_res = updater.apply_fact_update(fact, persist_markdown=False)
        self.assertEqual(update_res.action, KnowledgeUpdateAction.REJECTED)
        self.assertFalse(update_res.is_indexed)
        self.assertEqual(len(retriever._static_entries), 0)

        # Verify not retrievable
        results = knowledge_service.retrieve(query="Quang Hải đi đâu?")
        self.assertEqual(len(results), 0)

    def test_incremental_vector_embedding_reindex(self):
        import numpy as np
        from unittest.mock import MagicMock
        from app.services.knowledge_retriever import KnowledgeRetriever

        repo = KnowledgeRepository(knowledge_root="nonexistent_dir")
        entry_a = KnowledgeEntry(
            id="ENTRY-1",
            topic="identity",
            role="CUSTOMER",
            intent="SPORTS_KNOWLEDGE",
            sport="bóng đá",
            entity="Messi",
            question="Messi là ai?",
            answer="Cầu thủ xuất sắc.",
            source="FIFA",
            classification="static",
        )
        repo._entries = [entry_a]

        retriever = KnowledgeRetriever(repository=repo, use_semantic=False)
        retriever.use_semantic = True
        mock_model = MagicMock()
        mock_model.encode.side_effect = lambda texts, **kwargs: np.ones((len(texts), 4)) * 0.5
        retriever._model = mock_model
        retriever._embeddings = np.array([[0.1, 0.2, 0.3, 0.4]])

        # 1. Index new entry
        entry_b = KnowledgeEntry(
            id="ENTRY-2",
            topic="identity",
            role="CUSTOMER",
            intent="SPORTS_KNOWLEDGE",
            sport="cầu lông",
            entity="Thùy Linh",
            question="Thùy Linh là ai?",
            answer="Vận động viên cầu lông.",
            source="BWF Badminton",
            classification="static",
        )
        res_idx = retriever.index_entry(entry_b)
        self.assertTrue(res_idx)
        self.assertEqual(len(retriever._static_entries), 2)
        self.assertEqual(len(retriever._embeddings), 2)

        # 2. Update existing entry
        entry_b_updated = KnowledgeEntry(
            id="ENTRY-2",
            topic="identity",
            role="CUSTOMER",
            intent="SPORTS_KNOWLEDGE",
            sport="cầu lông",
            entity="Thùy Linh",
            question="Nguyễn Thùy Linh là ai?",
            answer="Vận động viên cầu lông số 1 Việt Nam.",
            source="BWF Badminton",
            classification="static",
        )
        res_upd = retriever.update_entry(entry_b_updated)
        self.assertTrue(res_upd)
        self.assertEqual(len(retriever._static_entries), 2)
        self.assertEqual(retriever._static_entries[1].answer, "Vận động viên cầu lông số 1 Việt Nam.")

        # 3. Unchanged update returns False
        res_unchanged = retriever.update_entry(entry_b_updated)
        self.assertFalse(res_unchanged)


if __name__ == "__main__":
    unittest.main()
