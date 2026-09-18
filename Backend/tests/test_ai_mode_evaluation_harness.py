import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.ai.evaluation.evaluate_mode_scenarios import (
    load_mode_dataset,
    evaluate_mode_scenario,
    run_mode_scenario_evaluation,
    AssistantScenarioMockProvider,
)


class AIModeEvaluationHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=AssistantScenarioMockProvider())
        cls.provider_patch.start()
        cls.client = TestClient(app)
        cls.context = cls.client.__enter__()
        cls.dataset = load_mode_dataset()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.__exit__(None, None, None)
        finally:
            cls.client.close()
            cls.provider_patch.stop()

    def test_full_evaluation_harness_pass_rate_100_percent(self):
        """Execute full evaluation dataset and assert 100% pass rate across all scenarios."""
        summary = run_mode_scenario_evaluation()
        failed_cases = [r for r in summary['results'] if not r['passed']]
        error_msg = "\n".join([f"[{f['id']}] {f['failures']}" for f in failed_cases])
        self.assertEqual(summary['failed'], 0, f"Expected 0 failed scenarios, but got {summary['failed']}:\n{error_msg}")
        self.assertEqual(summary['pass_rate'], 100.0)

    def test_group_1_natural_mode_scenarios(self):
        """Group 1: NATURAL Mode scenarios (Sports knowledge, SportHub business, follow-up, evidence, fallback, out-of-scope)."""
        natural_cases = [item for item in self.dataset if item.get('category') == 'NATURAL']
        self.assertGreaterEqual(len(natural_cases), 5)
        for item in natural_cases:
            with self.subTest(scenario_id=item['id'], input_text=item['input']):
                result = evaluate_mode_scenario(item, self.client)
                self.assertTrue(result['passed'], f"Scenario {item['id']} failed: {result.get('failures')}")

    def test_group_2_professional_mode_scenarios(self):
        """Group 2: PROFESSIONAL Mode scenarios (Search venue, availability, booking/account, business terms, sports knowledge blocked)."""
        pro_cases = [item for item in self.dataset if item.get('category') == 'PROFESSIONAL']
        self.assertGreaterEqual(len(pro_cases), 5)
        for item in pro_cases:
            with self.subTest(scenario_id=item['id'], input_text=item['input']):
                result = evaluate_mode_scenario(item, self.client)
                self.assertTrue(result['passed'], f"Scenario {item['id']} failed: {result.get('failures')}")

    def test_group_3_mode_switching_scenarios(self):
        """Group 3: MODE SWITCHING scenarios (NATURAL -> PROFESSIONAL, PROFESSIONAL -> NATURAL, context isolation)."""
        switch_cases = [item for item in self.dataset if item.get('category') == 'MODE_SWITCHING']
        self.assertGreaterEqual(len(switch_cases), 3)
        for item in switch_cases:
            with self.subTest(scenario_id=item['id'], input_text=item['input']):
                result = evaluate_mode_scenario(item, self.client)
                self.assertTrue(result['passed'], f"Scenario {item['id']} failed: {result.get('failures')}")

    def test_group_4_grounding_and_safety_scenarios(self):
        """Group 4: GROUNDING / SAFETY scenarios (Grounding with evidence, controlled fallback, no hallucination, DB only in professional, policy adherence)."""
        safety_cases = [item for item in self.dataset if item.get('category') == 'GROUNDING_SAFETY']
        self.assertGreaterEqual(len(safety_cases), 3)
        for item in safety_cases:
            with self.subTest(scenario_id=item['id'], input_text=item['input']):
                result = evaluate_mode_scenario(item, self.client)
                self.assertTrue(result['passed'], f"Scenario {item['id']} failed: {result.get('failures')}")


if __name__ == '__main__':
    unittest.main()
