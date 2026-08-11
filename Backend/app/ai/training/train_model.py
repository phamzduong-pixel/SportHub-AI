import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

from ..datasets.loader import DEFAULT_DATASET_PATH, FEATURE_COLUMNS, TARGET_COLUMN, load_demand_dataset
from ..evaluation.metrics import calculate_metrics
from ..preprocessing.pipeline import build_pipeline
from .generate_dataset import generate_dataset

SAVED_MODELS_DIR = Path(__file__).resolve().parents[1] / 'saved_models'
MODEL_PATH = SAVED_MODELS_DIR / 'demand_pipeline.joblib'
METRICS_PATH = SAVED_MODELS_DIR / 'metrics.json'
COMPARISON_PATH = SAVED_MODELS_DIR / 'model_comparison.csv'


def candidate_models():
    return {
        'Decision Tree': DecisionTreeClassifier(max_depth=7, min_samples_leaf=4, class_weight='balanced', random_state=42),
        'Random Forest': RandomForestClassifier(n_estimators=220, max_depth=12, min_samples_leaf=2, class_weight='balanced', random_state=42, n_jobs=-1),
        'Logistic Regression': LogisticRegression(max_iter=2000, class_weight='balanced', random_state=42),
    }


def train_and_save() -> dict:
    if not DEFAULT_DATASET_PATH.exists():
        generate_dataset()
    frame = load_demand_dataset()
    x_train, x_test, y_train, y_test = train_test_split(
        frame[FEATURE_COLUMNS], frame[TARGET_COLUMN], test_size=.2,
        random_state=42, stratify=frame[TARGET_COLUMN],
    )
    trained = {}; comparison = []
    for name, estimator in candidate_models().items():
        pipeline = build_pipeline(estimator)
        pipeline.fit(x_train, y_train)
        metrics = calculate_metrics(y_test, pipeline.predict(x_test))
        trained[name] = pipeline
        comparison.append({'model_name': name, **{key: metrics[key] for key in ('accuracy', 'precision', 'recall', 'f1_score')}, 'confusion_matrix': metrics['confusion_matrix']})
    comparison.sort(key=lambda item: (item['f1_score'], item['accuracy']), reverse=True)
    best = comparison[0]; trained_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        'model_name': best['model_name'], 'trained_at': trained_at,
        'dataset_path': str(DEFAULT_DATASET_PATH), 'dataset_type': 'synthetic',
        'dataset_note': 'Dữ liệu mô phỏng có seed cố định cho mục đích học tập, không phải dữ liệu thị trường thực tế.',
        'dataset_rows': len(frame), 'train_size': len(x_train), 'test_size': len(x_test),
        'features': FEATURE_COLUMNS, 'classes': ['LOW', 'MEDIUM', 'HIGH'],
        'target_distribution': {str(key): int(value) for key, value in frame[TARGET_COLUMN].value_counts().sort_index().items()},
    }
    artifact = {'pipeline': trained[best['model_name']], 'model_name': best['model_name'], 'metadata': metadata}
    report = {'selected_model': best['model_name'], 'selected_metrics': {**best, 'labels': ['LOW', 'MEDIUM', 'HIGH']}, 'models': comparison, 'metadata': metadata}
    SAVED_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    pd.DataFrame([{key: value for key, value in item.items() if key != 'confusion_matrix'} for item in comparison]).to_csv(COMPARISON_PATH, index=False)
    return report


def print_comparison(report: dict):
    print('\nSO SÁNH MÔ HÌNH')
    print('-' * 78)
    print(f"{'Mô hình':<24}{'Accuracy':>12}{'Precision':>12}{'Recall':>12}{'F1':>12}")
    for item in report['models']:
        print(f"{item['model_name']:<24}{item['accuracy']:>12.4f}{item['precision']:>12.4f}{item['recall']:>12.4f}{item['f1_score']:>12.4f}")
    print('-' * 78)
    print(f"Mô hình được chọn: {report['selected_model']}")
    print('Confusion matrix [LOW, MEDIUM, HIGH]:')
    for row in report['selected_metrics']['confusion_matrix']:
        print(row)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    result = train_and_save()
    print_comparison(result)
    print(f'\nĐã lưu pipeline: {MODEL_PATH}')
    print(f'Đã lưu metrics: {METRICS_PATH}')
