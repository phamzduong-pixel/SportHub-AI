import json
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

_module_path = Path(__file__).resolve().parents[1] / "app" / "services" / "world_cup_lookup.py"
_spec = importlib.util.spec_from_file_location("sporthub_world_cup_lookup", _module_path)
_lookup_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _lookup_module
_spec.loader.exec_module(_lookup_module)
DATA_DIR = _lookup_module.DATA_DIR
SOURCE_COMMIT = _lookup_module.SOURCE_COMMIT
SUPPORTED_YEARS = _lookup_module.SUPPORTED_YEARS
WorldCupDatasetError = _lookup_module.WorldCupDatasetError
canonicalize_team = _lookup_module.canonicalize_team
format_world_cup_answer = _lookup_module.format_world_cup_answer
load_world_cup_finals = _lookup_module.load_world_cup_finals
lookup_world_cup_query = _lookup_module.lookup_world_cup_query
validate_records = _lookup_module.validate_records

HAS_APP_DEPENDENCIES = all(importlib.util.find_spec(name) is not None for name in ("pydantic", "fastapi"))


EXPECTED = {
    1998: ("France", "Brazil", [0, 3], None),
    2002: ("Brazil", "Germany", [0, 2], None),
    2006: ("Italy", "France", [1, 1], [5, 3]),
    2010: ("Spain", "Netherlands", [0, 1], None),
    2014: ("Germany", "Argentina", [1, 0], None),
    2018: ("France", "Croatia", [4, 2], None),
    2022: ("Argentina", "France", [3, 3], [4, 2]),
}


class WorldCupDatasetTests(unittest.TestCase):
    def test_all_pilot_editions_match_verified_champions_and_final_scores(self):
        records = load_world_cup_finals()
        self.assertEqual(tuple(sorted(records)), SUPPORTED_YEARS)
        for year, (champion, runner_up, final_score, penalty_score) in EXPECTED.items():
            with self.subTest(year=year):
                record = records[year]
                self.assertEqual(record["champion"], champion)
                self.assertEqual(record["runner_up"], runner_up)
                self.assertEqual(record["score_after_extra_time"], final_score)
                self.assertEqual(record["penalty_score"], penalty_score)
                self.assertEqual(record["provenance"]["revision"], SOURCE_COMMIT)

    def test_extra_time_and_shootout_scores_are_not_conflated(self):
        records = load_world_cup_finals()
        self.assertEqual(records[2010]["score_90"], [0, 0])
        self.assertEqual(records[2010]["score_after_extra_time"], [0, 1])
        self.assertEqual(records[2006]["score_after_extra_time"], [1, 1])
        self.assertEqual(records[2006]["penalty_score"], [5, 3])
        self.assertEqual(records[2022]["score_90"], [2, 2])
        self.assertEqual(records[2022]["score_after_extra_time"], [3, 3])
        self.assertEqual(records[2022]["penalty_score"], [4, 2])

    def test_source_files_are_scoped_to_seven_years_with_one_final_each(self):
        source_root = DATA_DIR / "source"
        self.assertEqual(tuple(sorted(int(path.name) for path in source_root.iterdir())), SUPPORTED_YEARS)
        for year in SUPPORTED_YEARS:
            with self.subTest(year=year):
                source = json.loads((source_root / str(year) / "worldcup.json").read_text(encoding="utf-8"))
                finals = [match for match in source["matches"] if match.get("round", "").casefold() == "final"]
                self.assertEqual(len(finals), 1)

    def test_duplicate_and_conflicting_records_are_rejected(self):
        record = {
            "year": 1998, "team1": "Brazil", "team2": "France", "score_90": [0, 3],
            "score_after_extra_time": [0, 3], "penalty_score": None,
            "champion": "France", "runner_up": "Brazil",
        }
        with self.assertRaisesRegex(WorldCupDatasetError, "Duplicate"):
            validate_records([record, dict(record)], expected_years=(1998,))
        conflicting = dict(record, champion="Brazil", runner_up="France")
        with self.assertRaisesRegex(WorldCupDatasetError, "Conflicting"):
            validate_records([record, conflicting], expected_years=(1998,))

    def test_team_aliases_are_normalized(self):
        self.assertEqual(canonicalize_team("Pháp"), "France")
        self.assertEqual(canonicalize_team("Đức"), "Germany")
        self.assertEqual(canonicalize_team("Tây Ban Nha"), "Spain")


class WorldCupQueryTests(unittest.TestCase):
    def test_competition_alias_and_follow_up_year(self):
        first = lookup_world_cup_query("Ai vô địch Cúp thế giới năm 1998?")
        self.assertEqual(first.status, "found")
        follow_up = lookup_world_cup_query(
            "Còn năm 2002 thì sao?",
            competition="FIFA World Cup",
            context={"competition": "FIFA World Cup", "year": 1998},
        )
        self.assertEqual(follow_up.records[0]["champion"], "Brazil")

    def test_year_range_returns_only_available_editions_and_citations(self):
        result = lookup_world_cup_query("Kết quả chung kết World Cup từ 1998 đến 2022")
        self.assertEqual(result.years, SUPPORTED_YEARS)
        answer = format_world_cup_answer(result)
        self.assertIn("1998", answer)
        self.assertIn("2022", answer)
        self.assertIn(SOURCE_COMMIT, answer)
        self.assertIn("luân lưu 4–2", answer)

    def test_missing_year_and_missing_dataset_year_fail_closed_without_network(self):
        no_year = lookup_world_cup_query("Ai vô địch World Cup?")
        self.assertEqual(no_year.status, "needs_year")
        outside_scope = lookup_world_cup_query("Ai vô địch World Cup năm 1994?")
        self.assertEqual(outside_scope.status, "missing_data")
        self.assertEqual(outside_scope.missing_years, (1994,))
        self.assertIn("không thể kết luận", format_world_cup_answer(outside_scope))

    def test_non_result_world_cup_question_remains_for_existing_rag(self):
        self.assertIsNone(lookup_world_cup_query("World Cup 2022 được tổ chức ở đâu?"))

    @unittest.skipUnless(HAS_APP_DEPENDENCIES, "Backend application dependencies are not installed")
    def test_professional_guard_precedes_new_lookup(self):
        from app.schemas.ai import AssistantMode
        from app.services.ai_assistant_service import AIAssistantService
        from app.services.ai_intent_router import AssistantIntent, IntentEntities, IntentRoute

        service = AIAssistantService.__new__(AIAssistantService)
        service._assistant_mode = AssistantMode.PROFESSIONAL
        service._active_route = IntentRoute(
            intent=AssistantIntent.SPORTS_KNOWLEDGE,
            confidence=1.0,
            entities=IntentEntities(competition="FIFA World Cup", year="2022"),
        )
        service._conversation_context = {}
        service._mode_evaluation = None
        service.current_user = None
        service.guardrail = SimpleNamespace(retrieve_context=Mock(), retrieve_web_context=Mock())
        with patch("app.services.ai_assistant_service.lookup_world_cup_query") as lookup:
            response = service._answer_sports_knowledge("Ai vô địch World Cup 2022?", service._active_route)
        lookup.assert_not_called()
        service.guardrail.retrieve_context.assert_not_called()
        service.guardrail.retrieve_web_context.assert_not_called()
        self.assertEqual(response["classification"], "OUT_OF_SCOPE")

    @unittest.skipUnless(HAS_APP_DEPENDENCIES, "Backend application dependencies are not installed")
    def test_natural_world_cup_lookup_returns_before_rag(self):
        from app.schemas.ai import AssistantMode
        from app.services.ai_assistant_service import AIAssistantService
        from app.services.ai_intent_router import AssistantIntent, IntentEntities, IntentRoute

        service = AIAssistantService.__new__(AIAssistantService)
        service._assistant_mode = AssistantMode.NATURAL
        service._active_route = IntentRoute(
            intent=AssistantIntent.SPORTS_KNOWLEDGE,
            confidence=1.0,
            entities=IntentEntities(competition="FIFA World Cup", year="2022"),
        )
        service._conversation_context = {}
        service._mode_evaluation = None
        service.current_user = None
        service.guardrail = SimpleNamespace(retrieve_context=Mock(), retrieve_web_context=Mock())
        response = service._answer_sports_knowledge("Ai vô địch World Cup 2022?", service._active_route)
        service.guardrail.retrieve_context.assert_not_called()
        service.guardrail.retrieve_web_context.assert_not_called()
        self.assertIn("Argentina vô địch", response["reply"])
        self.assertIn("luân lưu 4–2", response["reply"])
        self.assertIn(SOURCE_COMMIT, response["reply"])


if __name__ == "__main__":
    unittest.main()
