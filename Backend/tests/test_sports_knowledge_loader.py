import os
import unittest

from app.models.knowledge_entry import KnowledgeEntry
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_retriever import KnowledgeRetriever
from app.services.knowledge_service import KnowledgeService


class SportsKnowledgeLoaderTests(unittest.TestCase):
    def setUp(self):
        self.repo = KnowledgeRepository()
        self.retriever = KnowledgeRetriever(self.repo)
        self.service = KnowledgeService(self.repo, self.retriever)

    # ----------------------------------------------------
    # 1. LOADER READS ROOT & SUBFOLDERS
    # ----------------------------------------------------
    def test_loader_reads_general_and_customer_knowledge(self):
        entries = self.repo.list_entries()
        self.assertGreater(len(entries), 0)

        # Verify customer entries exist
        customer_entry = next((e for e in entries if e.id == 'CUST-001'), None)
        self.assertIsNotNone(customer_entry)
        self.assertEqual(customer_entry.topic, 'SportHub Overview')
        self.assertEqual(customer_entry.intent, 'SYSTEM_GUIDE')
        self.assertEqual(customer_entry.classification, 'static')
        self.assertTrue(customer_entry.content)

    def test_loader_reads_sports_root_and_subfolders(self):
        entries = self.repo.list_entries()

        # Thai Nguyen subfolder entry
        tn_entry = next((e for e in entries if e.id == 'TN-SPT-001'), None)
        self.assertIsNotNone(tn_entry, 'Should load entries from sports/thai_nguyen/ subfolder')
        self.assertEqual(tn_entry.sport, 'bóng đá')
        self.assertEqual(tn_entry.entity, 'Thái Nguyên T&T')
        self.assertEqual(tn_entry.priority, 1)

        # National teams subfolder entry
        team_entry = next((e for e in entries if e.id == 'VN-TEAM-003'), None)
        self.assertIsNotNone(team_entry, 'Should load entries from sports/national_teams/ subfolder')
        self.assertEqual(team_entry.sport, 'bóng chuyền')
        self.assertEqual(team_entry.entity, 'Đội tuyển bóng chuyền nữ Việt Nam')
        self.assertEqual(team_entry.priority, 2)

        # Players subfolder entry
        player_entry = next((e for e in entries if e.id == 'PLY-FB-001'), None)
        self.assertIsNotNone(player_entry, 'Should load entries from sports/players/ subfolder')
        self.assertEqual(player_entry.sport, 'bóng đá')
        self.assertEqual(player_entry.entity, 'Lionel Messi')
        self.assertEqual(player_entry.priority, 1)

    # ----------------------------------------------------
    # 2. METADATA PRESERVATION
    # ----------------------------------------------------
    def test_knowledge_entry_metadata_integrity(self):
        entries = self.repo.list_entries()
        messi_entry = next((e for e in entries if e.id == 'PLY-FB-001'), None)
        self.assertIsNotNone(messi_entry)

        self.assertEqual(messi_entry.topic, 'Cầu thủ')
        self.assertEqual(messi_entry.sport, 'bóng đá')
        self.assertEqual(messi_entry.entity, 'Lionel Messi')
        self.assertEqual(messi_entry.source_name, 'FIFA')
        self.assertIn('fifa.com', messi_entry.source_url)
        self.assertTrue(messi_entry.collected_at)
        self.assertIn('Lionel Messi', messi_entry.content)
        self.assertEqual(messi_entry.classification, 'static')

    # ----------------------------------------------------
    # 3. DEDUPLICATION INTEGRITY
    # ----------------------------------------------------
    def test_no_duplicate_entry_ids(self):
        entries = self.repo.list_entries()
        entry_ids = [e.id for e in entries]
        unique_ids = set(entry_ids)
        self.assertEqual(len(entry_ids), len(unique_ids), 'Knowledge entries must have unique IDs with no duplication')

    # ----------------------------------------------------
    # 4. SHARED RETRIEVAL PIPELINE USAGE
    # ----------------------------------------------------
    def test_sports_retrieval_via_shared_pipeline(self):
        # Query for Thai Nguyen sports
        results = self.service.retrieve('Thái Nguyên T&T', intent='SPORTS_KNOWLEDGE')
        self.assertGreater(len(results), 0)
        top_entry, score = results[0]
        self.assertEqual(top_entry.entity, 'Thái Nguyên T&T')
        self.assertIn('Báo Thái Nguyên', top_entry.source_name)

        # Query for Vietnam volleyball team
        vb_results = self.service.retrieve('Đội tuyển bóng chuyền nữ Việt Nam', intent='SPORTS_KNOWLEDGE', sport='bóng chuyền')
        self.assertGreater(len(vb_results), 0)
        self.assertEqual(vb_results[0][0].sport, 'bóng chuyền')

        # Query for general customer knowledge
        cust_results = self.service.retrieve('SportHub là gì?', intent='SYSTEM_GUIDE')
        self.assertGreater(len(cust_results), 0)
        self.assertEqual(cust_results[0][0].id, 'CUST-001')


if __name__ == '__main__':
    unittest.main()
