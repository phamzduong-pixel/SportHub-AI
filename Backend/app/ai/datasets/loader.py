from pathlib import Path

import pandas as pd

FEATURE_COLUMNS = [
    'sport_type', 'day_of_week', 'start_hour', 'price', 'month',
    'is_weekend', 'previous_booking_count', 'field_capacity',
]
TARGET_COLUMN = 'demand_level'
VALID_LABELS = {'LOW', 'MEDIUM', 'HIGH'}
DEFAULT_DATASET_PATH = Path(__file__).resolve().parents[3] / 'database' / 'datasets' / 'booking_demand.csv'


def load_demand_dataset(path: str | Path | None = None) -> pd.DataFrame:
    dataset_path = Path(path) if path else DEFAULT_DATASET_PATH
    if not dataset_path.exists():
        raise FileNotFoundError(f'Không tìm thấy dataset tại {dataset_path}')
    frame = pd.read_csv(dataset_path)
    missing = set(FEATURE_COLUMNS + [TARGET_COLUMN]) - set(frame.columns)
    if missing:
        raise ValueError(f'Dataset thiếu các cột: {sorted(missing)}')
    frame = frame[FEATURE_COLUMNS + [TARGET_COLUMN]].copy().dropna()
    frame['sport_type'] = frame['sport_type'].astype(str).str.strip().str.lower()
    for column in FEATURE_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    frame[TARGET_COLUMN] = frame[TARGET_COLUMN].astype(str).str.strip().str.upper()
    frame = frame.dropna().drop_duplicates()
    frame = frame[
        frame[TARGET_COLUMN].isin(VALID_LABELS)
        & frame['day_of_week'].between(0, 6)
        & frame['start_hour'].between(0, 23)
        & frame['month'].between(1, 12)
        & frame['price'].ge(0)
        & frame['previous_booking_count'].ge(0)
        & frame['field_capacity'].gt(0)
    ]
    if len(frame) < 100:
        raise ValueError('Dataset hợp lệ cần ít nhất 100 bản ghi')
    return frame.reset_index(drop=True)
