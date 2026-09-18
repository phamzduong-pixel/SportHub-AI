import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.services.ai_domain_policy import AssistantMode, ScopeClassification, ScopeDecision, AllowedSource, evaluate_mode_scope


def load_mode_dataset() -> List[Dict[str, Any]]:
    dataset_path = Path(__file__).resolve().parents[1] / 'datasets' / 'mode_evaluation_dataset.json'
    with open(dataset_path, 'r', encoding='utf-8') as f:
        return json.load(f)


class AssistantScenarioMockProvider:
    def generate_json(self, **kwargs):
        available = kwargs.get('system_data', {}).get('available_slots', [])
        return {
            'status': 'OK',
            'recommendations': [
                {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Phù hợp nhu cầu.'}
                for item in available[:3]
            ],
        }


def evaluate_mode_scenario(scenario: Dict[str, Any], client: TestClient) -> Dict[str, Any]:
    scenario_id = scenario['id']
    mode_str = scenario.get('mode', 'NATURAL')
    input_text = scenario['input']
    expected_scope = scenario.get('expected_scope')
    expected_behavior = scenario.get('expected_behavior')
    allowed_sources = scenario.get('allowed_sources', [])
    forbidden_sources = scenario.get('forbidden_sources', [])
    context = scenario.get('context')
    assert_contains = scenario.get('assert_contains', [])
    assert_not_contains = scenario.get('assert_not_contains', [])
    expected_status = scenario.get('expected_status')

    payload: Dict[str, Any] = {
        'message': input_text,
        'assistant_mode': mode_str,
    }
    if context:
        payload['context'] = context

    # Test via API
    response = client.post('/ai/assistant', json=payload)
    status_code = response.status_code
    if status_code != 200:
        return {
            'id': scenario_id,
            'category': scenario.get('category'),
            'passed': False,
            'status_code': status_code,
            'error': f"HTTP status {status_code}: {response.text}",
        }

    data = response.json()
    reply = data.get('reply', '')
    res_status = data.get('status')
    understood = data.get('understood', {})
    actual_scope = understood.get('scope_decision')
    actual_mode = data.get('assistant_mode', mode_str)

    failures = []

    # 1. Mode check
    if actual_mode != mode_str:
        failures.append(f"Mode mismatch: expected {mode_str}, got {actual_mode}")

    # 2. Scope decision check
    if expected_scope and actual_scope != expected_scope:
        failures.append(f"Scope decision mismatch: expected {expected_scope}, got {actual_scope}")

    # 3. Status check
    if expected_status and res_status != expected_status:
        failures.append(f"Status mismatch: expected {expected_status}, got {res_status}")

    # 4. Expected behavior check
    if expected_behavior == 'ANSWER_GROUNDED':
        if 'chưa có thông tin kiểm chứng' in reply:
            failures.append("Expected ANSWER_GROUNDED but got safe fallback notice.")
        if res_status == 'OUT_OF_SCOPE':
            failures.append("Expected ANSWER_GROUNDED but got OUT_OF_SCOPE status.")
    elif expected_behavior == 'SAFE_FALLBACK':
        if 'chưa có thông tin kiểm chứng' not in reply:
            failures.append("Expected SAFE_FALLBACK but missing fallback notice in reply.")
    elif expected_behavior == 'CONTROLLED_REFUSAL':
        if 'Chuyên nghiệp (Professional)' not in reply and 'Tự nhiên (Natural)' not in reply:
            failures.append("Expected CONTROLLED_REFUSAL with mode notice, but missing in reply.")
        if res_status != 'OUT_OF_SCOPE':
            failures.append(f"Expected status OUT_OF_SCOPE for controlled refusal, got {res_status}.")
    elif expected_behavior == 'BUSINESS_FLOW':
        if res_status == 'OUT_OF_SCOPE':
            failures.append("Expected BUSINESS_FLOW but got OUT_OF_SCOPE status.")
        if 'Chuyên nghiệp (Professional)' in reply and 'hỗ trợ các nghiệp vụ trực tiếp' in reply:
            failures.append("Expected BUSINESS_FLOW but got mode refusal notice in reply.")
    elif expected_behavior == 'OUT_OF_SCOPE_REFUSAL':
        if res_status != 'OUT_OF_SCOPE':
            failures.append(f"Expected status OUT_OF_SCOPE for general refusal, got {res_status}.")

    # 5. Assert contains
    for term in assert_contains:
        if term.lower() not in reply.lower():
            failures.append(f"Missing expected keyword '{term}' in reply.")

    # 6. Assert not contains
    for term in assert_not_contains:
        if term.lower() in reply.lower():
            failures.append(f"Forbidden keyword '{term}' found in reply.")

    # 7. Source routing policy check
    if forbidden_sources:
        # Verify that forbidden sources are not present in allowed sources according to domain policy
        last_intent = understood.get('last_intent') or 'SEARCH_VENUE'
        policy = evaluate_mode_scope(mode=AssistantMode(mode_str), intent=last_intent)
        allowed_source_names = [s.value for s in policy.allowed_sources]
        for forbidden in forbidden_sources:
            if forbidden in allowed_source_names:
                failures.append(f"Source policy error: {forbidden} was found in allowed sources.")

    passed = len(failures) == 0

    return {
        'id': scenario_id,
        'category': scenario.get('category'),
        'input': input_text,
        'mode': mode_str,
        'actual_scope': actual_scope,
        'expected_scope': expected_scope,
        'actual_status': res_status,
        'expected_status': expected_status,
        'passed': passed,
        'failures': failures,
        'reply': reply,
    }


def run_mode_scenario_evaluation() -> Dict[str, Any]:
    dataset = load_mode_dataset()
    results = []
    
    with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=AssistantScenarioMockProvider()):
        with TestClient(app) as client:
            for item in dataset:
                res = evaluate_mode_scenario(item, client)
                results.append(res)

    total = len(results)
    passed_count = sum(1 for r in results if r['passed'])
    failed_count = total - passed_count
    
    by_category: Dict[str, Dict[str, int]] = {}
    for r in results:
        cat = r.get('category', 'OTHER')
        if cat not in by_category:
            by_category[cat] = {'total': 0, 'passed': 0, 'failed': 0}
        by_category[cat]['total'] += 1
        if r['passed']:
            by_category[cat]['passed'] += 1
        else:
            by_category[cat]['failed'] += 1

    return {
        'total_scenarios': total,
        'passed': passed_count,
        'failed': failed_count,
        'pass_rate': (passed_count / total * 100) if total > 0 else 0.0,
        'by_category': by_category,
        'results': results,
    }


def print_evaluation_summary(summary: Dict[str, Any]):
    print("=" * 80)
    print("BÁO CÁO ĐÁNH GIÁ SCENARIO HARNESS - SPORTHUB AI ASSISTANT MODES")
    print("=" * 80)
    print(f"Tổng số scenario: {summary['total_scenarios']}")
    print(f"Passed          : {summary['passed']}")
    print(f"Failed          : {summary['failed']}")
    print(f"Pass Rate       : {summary['pass_rate']:.2f}%\n")
    print(f"{'Category':<25}{'Total':>10}{'Passed':>10}{'Failed':>10}{'Pass Rate':>15}")
    print("-" * 70)
    for cat, stats in summary['by_category'].items():
        rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0.0
        print(f"{cat:<25}{stats['total']:>10}{stats['passed']:>10}{stats['failed']:>10}{rate:>14.1f}%")
    print("=" * 80)

    failed_items = [r for r in summary['results'] if not r['passed']]
    if failed_items:
        print("\nCHI TIẾT CÁC CASE FAILED:")
        for f in failed_items:
            print(f"- [{f['id']}] ({f['mode']}) Input: '{f['input']}'")
            for err in f['failures']:
                print(f"    * {err}")
    else:
        print("\nTất cả kịch bản (scenarios) đã PASS thành công 100%!")


if __name__ == '__main__':
    summary = run_mode_scenario_evaluation()
    print_evaluation_summary(summary)
