import json
import sys
from pathlib import Path

from sklearn.model_selection import train_test_split

from ..datasets.loader import FEATURE_COLUMNS, TARGET_COLUMN, load_demand_dataset
from ..inference.model_loader import MODEL_PATH as DEFAULT_MODEL_PATH, load_model_artifact
from .metrics import calculate_metrics


def evaluate_saved_model(model_path: str | Path = DEFAULT_MODEL_PATH) -> dict:
    if Path(model_path).resolve() != DEFAULT_MODEL_PATH.resolve():
        raise ValueError('Evaluation chỉ chấp nhận artifact đã được model_loader kiểm tra')
    load_model_artifact.cache_clear()
    artifact = load_model_artifact()
    frame = load_demand_dataset()
    _, x_test, _, y_test = train_test_split(
        frame[FEATURE_COLUMNS], frame[TARGET_COLUMN], test_size=.2,
        random_state=42, stratify=frame[TARGET_COLUMN],
    )
    result = calculate_metrics(y_test, artifact['pipeline'].predict(x_test))
    result['model_name'] = artifact['model_name']
    result['test_size'] = len(x_test)
    return result


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(evaluate_saved_model(), ensure_ascii=False, indent=2))
