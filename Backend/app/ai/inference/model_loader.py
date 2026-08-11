import json
from functools import lru_cache
from pathlib import Path

import joblib

SAVED_MODELS_DIR = Path(__file__).resolve().parents[1] / 'saved_models'
MODEL_PATH = SAVED_MODELS_DIR / 'demand_pipeline.joblib'
METRICS_PATH = SAVED_MODELS_DIR / 'metrics.json'


class ModelNotReadyError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load_model_artifact() -> dict:
    if not MODEL_PATH.exists():
        raise ModelNotReadyError('Chưa có model AI. Hãy chạy: python -m app.ai.training.train_model')
    try:
        artifact = joblib.load(MODEL_PATH)
    except Exception as exc:
        raise ModelNotReadyError(f'Không thể nạp model AI: {exc}') from exc
    if not isinstance(artifact, dict) or 'pipeline' not in artifact:
        raise ModelNotReadyError('File model AI không đúng định dạng')
    return artifact


@lru_cache(maxsize=1)
def load_metrics() -> dict:
    if not METRICS_PATH.exists():
        raise ModelNotReadyError('Chưa có kết quả đánh giá model. Hãy huấn luyện model trước')
    try:
        return json.loads(METRICS_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelNotReadyError(f'Không thể đọc metrics AI: {exc}') from exc
