from pathlib import Path
import sys

import numpy as np
import pandas as pd

from ..datasets.loader import DEFAULT_DATASET_PATH

SPORTS = {
    'bóng đá': {'price': 650_000, 'capacity': 14, 'popularity': 1.2},
    'cầu lông': {'price': 180_000, 'capacity': 4, 'popularity': .7},
    'bóng rổ': {'price': 420_000, 'capacity': 12, 'popularity': .55},
    'tennis': {'price': 360_000, 'capacity': 4, 'popularity': .25},
    'pickleball': {'price': 240_000, 'capacity': 4, 'popularity': .8},
}


def generate_dataset(path: str | Path = DEFAULT_DATASET_PATH, rows: int = 2400, seed: int = 42) -> Path:
    """Create deterministic synthetic demand data for educational use only."""
    rng = np.random.default_rng(seed)
    records = []
    sport_names = list(SPORTS)
    sport_weights = np.array([.30, .25, .14, .12, .19])
    hours = np.array([6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21])
    hour_weights = np.array([.03, .04, .06, .06, .05, .04, .04, .05, .06, .07, .10, .12, .12, .09, .07])
    for _ in range(rows):
        sport = rng.choice(sport_names, p=sport_weights)
        profile = SPORTS[sport]
        day = int(rng.integers(0, 7)); month = int(rng.integers(1, 13)); start_hour = int(rng.choice(hours, p=hour_weights))
        weekend = int(day >= 5); evening = int(17 <= start_hour <= 21)
        seasonal = .55 if month in (5, 6, 7, 8) else (.25 if month in (11, 12, 1) else 0)
        expected_previous = 5.0 + profile['popularity'] * 5 + weekend * 3.2 + evening * 4.2 + seasonal * 2
        previous_count = int(np.clip(rng.poisson(expected_previous), 0, 35))
        price_factor = rng.uniform(.78, 1.28) + evening * .08 + weekend * .05
        price = int(round(profile['price'] * price_factor / 10_000) * 10_000)
        capacity = int(max(2, profile['capacity'] + rng.choice([-2, 0, 0, 0, 2, 4])))
        relative_price = price / profile['price']
        score = (
            previous_count * .32 + weekend * 1.05 + evening * 1.35 + profile['popularity']
            + seasonal - max(relative_price - 1, 0) * 2.1 + rng.normal(0, .65)
        )
        demand = 'LOW' if score < 4.6 else ('MEDIUM' if score < 7.2 else 'HIGH')
        records.append({
            'sport_type': sport, 'day_of_week': day, 'start_hour': start_hour,
            'price': price, 'month': month, 'is_weekend': weekend,
            'previous_booking_count': previous_count, 'field_capacity': capacity,
            'demand_level': demand,
        })
    output = Path(path); output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(output, index=False, encoding='utf-8')
    return output


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    generated = generate_dataset()
    print(f'Đã tạo dataset mô phỏng tại {generated}')
