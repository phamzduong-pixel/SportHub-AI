from datetime import date


def build_feature_record(
    *, sport_type: str, booking_date: date, start_hour: int, price: float,
    previous_booking_count: int, field_capacity: int,
) -> dict:
    return {
        'sport_type': sport_type.strip().lower(),
        'day_of_week': booking_date.weekday(),
        'start_hour': start_hour,
        'price': price,
        'month': booking_date.month,
        'is_weekend': int(booking_date.weekday() >= 5),
        'previous_booking_count': previous_booking_count,
        'field_capacity': field_capacity,
    }
