import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.ai_intent_router import AssistantIntent, IntentRouter


def load_dataset():
    dataset_path = Path(__file__).resolve().parents[1] / 'datasets' / 'nlu_eval_dataset.json'
    with open(dataset_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def evaluate_intent_router():
    data = load_dataset()
    router = IntentRouter()
    
    y_true = []
    y_pred = []
    details = []
    
    for item in data:
        text = item['text']
        expected_intent = item['intent']
        
        # Determine context simulation for follow-up questions
        context = {}
        if expected_intent == 'FOLLOW_UP':
            context = {
                'sport_type': 'bóng đá',
                'location': 'Hà Nội',
                'result_field_ids': [1, 2, 3],
                'result_prices': [200000, 250000, 300000],
                'reference_price': 250000,
                'last_intent': 'SEARCH_VENUE'
            }
        
        route = router.route(text, context=context)
        pred_intent = route.intent.value
        
        y_true.append(expected_intent)
        y_pred.append(pred_intent)
        
        details.append({
            'text': text,
            'expected': expected_intent,
            'predicted': pred_intent,
            'confidence': route.confidence,
            'is_correct': expected_intent == pred_intent
        })
    
    labels = sorted(list(set(y_true) | set(y_pred)))
    
    accuracy = accuracy_score(y_true, y_pred)
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    
    return {
        'total_samples': len(data),
        'accuracy': accuracy,
        'labels': labels,
        'report': report,
        'confusion_matrix': cm.tolist(),
        'details': details
    }


def print_evaluation_report(results):
    print("=" * 80)
    print("BÁO CÁO ĐÁNH GIÁ THỰC NGHIỆM INTENT ROUTER - SPORTHUB AI")
    print("=" * 80)
    print(f"Tổng số mẫu kiểm thử: {results['total_samples']}")
    print(f"Accuracy toàn cục   : {results['accuracy'] * 100:.2f}%\n")
    
    print(f"{'Intent':<30}{'Precision':>12}{'Recall':>12}{'F1-Score':>12}{'Support':>10}")
    print("-" * 76)
    
    report = results['report']
    for label in results['labels']:
        if label in report:
            metrics = report[label]
            print(f"{label:<30}{metrics['precision']:>12.4f}{metrics['recall']:>12.4f}{metrics['f1-score']:>12.4f}{int(metrics['support']):>10}")
    
    print("-" * 76)
    macro = report.get('macro avg', {})
    weighted = report.get('weighted avg', {})
    print(f"{'Macro Avg':<30}{macro.get('precision', 0):>12.4f}{macro.get('recall', 0):>12.4f}{macro.get('f1-score', 0):>12.4f}{int(macro.get('support', 0)):>10}")
    print(f"{'Weighted Avg':<30}{weighted.get('precision', 0):>12.4f}{weighted.get('recall', 0):>12.4f}{weighted.get('f1-score', 0):>12.4f}{int(weighted.get('support', 0)):>10}")
    print("=" * 80)
    
    incorrect = [item for item in results['details'] if not item['is_correct']]
    if incorrect:
        print(f"\nDanh sách {len(incorrect)} trường hợp phân loại sai:")
        for item in incorrect:
            print(f"- Câu hỏi : \"{item['text']}\"")
            print(f"  Kỳ vọng : {item['expected']} | Dự đoán: {item['predicted']} (Confidence: {item['confidence']:.2f})")
    else:
        print("\nTuyệt đối chính xác: Không có mẫu kiểm thử nào bị phân loại sai!")


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    res = evaluate_intent_router()
    print_evaluation_report(res)
