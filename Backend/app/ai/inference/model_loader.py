import json
import logging
from functools import lru_cache
from pathlib import Path

import joblib
import sklearn

from ..datasets.loader import FEATURE_COLUMNS

SAVED_MODELS_DIR = Path(__file__).resolve().parents[1] / 'saved_models'
MODEL_PATH = SAVED_MODELS_DIR / 'demand_pipeline.joblib'
METRICS_PATH = SAVED_MODELS_DIR / 'metrics.json'
METADATA_PATH = SAVED_MODELS_DIR / 'model_metadata.json'
logger = logging.getLogger(__name__)


class ModelNotReadyError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load_model_artifact() -> dict:
    if not MODEL_PATH.exists():
        raise ModelNotReadyError('Chưa có model AI. Hãy chạy: python -m app.ai.training.train_model')
    metadata = load_model_metadata()
    saved_version = metadata['sklearn_version']
    if saved_version != sklearn.__version__:
        logger.warning(
            'ML model/runtime version mismatch model=%s runtime=%s',
            saved_version, sklearn.__version__,
        )
        raise ModelNotReadyError(
            f'Model AI được tạo bằng scikit-learn {saved_version} nhưng runtime đang dùng '
            f'{sklearn.__version__}. Hãy đồng bộ dependency trước khi inference.'
        )
    try:
        artifact = joblib.load(MODEL_PATH)
    except Exception as exc:
        raise ModelNotReadyError(f'Không thể nạp model AI: {exc}') from exc
    if not isinstance(artifact, dict) or 'pipeline' not in artifact:
        raise ModelNotReadyError('File model AI không đúng định dạng')
    pipeline = artifact['pipeline']
    actual_features = list(getattr(pipeline, 'feature_names_in_', []))
    if actual_features != metadata['feature_names']:
        raise ModelNotReadyError(
            f'Feature contract của model không khớp metadata: {actual_features}'
        )
    artifact_metadata = dict(artifact.get('metadata') or {})
    artifact_metadata.update(metadata)
    artifact['metadata'] = artifact_metadata
    return artifact


@lru_cache(maxsize=1)
def load_model_metadata() -> dict:
    if not METADATA_PATH.exists():
        raise ModelNotReadyError('Model AI thiếu file model_metadata.json')
    try:
        metadata = json.loads(METADATA_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelNotReadyError(f'Không thể đọc metadata model AI: {exc}') from exc
    required = {
        'sklearn_version', 'trained_at', 'feature_names', 'model_type', 'model_version',
    }
    missing = required - set(metadata) if isinstance(metadata, dict) else required
    if missing:
        raise ModelNotReadyError(f'Metadata model AI thiếu trường: {sorted(missing)}')
    if metadata['feature_names'] != FEATURE_COLUMNS:
        raise ModelNotReadyError('Feature names trong metadata không khớp code inference')
    return metadata


@lru_cache(maxsize=1)
def load_metrics() -> dict:
    if not METRICS_PATH.exists():
        raise ModelNotReadyError('Chưa có kết quả đánh giá model. Hãy huấn luyện model trước')
    try:
        return json.loads(METRICS_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelNotReadyError(f'Không thể đọc metrics AI: {exc}') from exc
