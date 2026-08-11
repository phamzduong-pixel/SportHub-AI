from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import HTTPException

from ...core.config import settings
from ...core.ownership import management_owner_id
from ...repositories.ai_repository import AIRepository
from ...schemas.ai import (
    DemandOverviewResponse, DemandPredictionResponse, ModelMetricsResponse,
    RecommendationResponse,
)
from ..datasets.loader import FEATURE_COLUMNS
from ..preprocessing.feature_engineering import build_feature_record
from .model_loader import ModelNotReadyError, load_metrics, load_model_artifact


class DemandPredictionService:
    def __init__(self, repository: AIRepository):
        self.repository = repository
        self.timezone = ZoneInfo(settings.TIMEZONE)

    def for_user(self, user):
        owner_id = management_owner_id(user, self.repository.db)
        if owner_id is None:
            raise HTTPException(status_code=403, detail='Tài khoản quản lý chưa được gán cho OWNER')
        self.repository.scope_to_owner(owner_id)
        return self

    def predict(self, payload) -> DemandPredictionResponse:
        sport_type, capacity = payload.sport_type, payload.field_capacity
        if payload.field_id:
            field = self.repository.field_context(payload.field_id)
            if field is None:
                raise HTTPException(status_code=404, detail='Không tìm thấy sân dùng cho dự đoán')
            if field.sport_type.strip().lower() != sport_type:
                raise HTTPException(status_code=422, detail='sport_type không khớp với sân đã chọn')
            capacity = capacity or field.capacity
        capacity = capacity or self.repository.average_capacity(sport_type)
        previous = payload.previous_booking_count
        if previous is None:
            previous = self.repository.previous_booking_count(
                sport_type=sport_type, before_date=payload.booking_date,
                start_hour=payload.start_hour, field_id=payload.field_id,
            )
        features = build_feature_record(
            sport_type=sport_type, booking_date=payload.booking_date,
            start_hour=payload.start_hour, price=payload.price,
            previous_booking_count=previous, field_capacity=capacity,
        )
        return self._predict_features(features)

    def model_metrics(self):
        try:
            return ModelMetricsResponse.model_validate(load_metrics())
        except ModelNotReadyError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

    def overview(self, *, days: int, sport_type: str | None):
        inventory = self.repository.inventory(sport_type)
        now = datetime.now(self.timezone); today = now.date(); items = []; distribution = {'LOW': 0, 'MEDIUM': 0, 'HIGH': 0}
        for offset in range(days):
            target_date = today + timedelta(days=offset)
            counts = {'LOW': 0, 'MEDIUM': 0, 'HIGH': 0}
            for field, slot in inventory:
                previous = self.repository.previous_booking_count(
                    sport_type=field.sport_type, before_date=target_date,
                    start_hour=slot.start_time.hour, field_id=field.id,
                )
                prediction = self._predict_features(build_feature_record(
                    sport_type=field.sport_type, booking_date=target_date,
                    start_hour=slot.start_time.hour, price=float(slot.price),
                    previous_booking_count=previous, field_capacity=field.capacity,
                ))
                counts[prediction.demand_level.value] += 1
                distribution[prediction.demand_level.value] += 1
            items.append({'date': target_date, 'low': counts['LOW'], 'medium': counts['MEDIUM'], 'high': counts['HIGH'], 'total': sum(counts.values())})
        return DemandOverviewResponse(sport_type=sport_type, days=days, items=items, distribution=distribution)

    def recommendations(self, *, sport_type: str, booking_date: date, max_price: float | None, limit: int):
        now = datetime.now(self.timezone)
        if booking_date < now.date():
            raise HTTPException(status_code=422, detail='Không thể đề xuất khung giờ trong quá khứ')
        candidates = self.repository.available_candidates(sport_type, booking_date, max_price)
        if booking_date == now.date():
            candidates = [(field, slot) for field, slot in candidates if slot.start_time > now.time().replace(tzinfo=None)]
        if not candidates:
            return RecommendationResponse(
                booking_date=booking_date, sport_type=sport_type,
                strategy=self._strategy(), items=[],
            )
        highest_price = max(float(slot.price) for _, slot in candidates) or 1
        items = []
        demand_bonus = {'LOW': 25, 'MEDIUM': 19, 'HIGH': 10}
        for field, slot in candidates:
            previous = self.repository.previous_booking_count(
                sport_type=field.sport_type, before_date=booking_date,
                start_hour=slot.start_time.hour, field_id=field.id,
            )
            prediction = self._predict_features(build_feature_record(
                sport_type=field.sport_type, booking_date=booking_date,
                start_hour=slot.start_time.hour, price=float(slot.price),
                previous_booking_count=previous, field_capacity=field.capacity,
            ))
            level = prediction.demand_level.value
            price_score = (1 - float(slot.price) / highest_price) * 45
            score = round(30 + price_score + demand_bonus[level], 2)
            reasons = ['Sân và khung giờ đang còn trống', 'Phù hợp môn thể thao đã chọn']
            reasons.append('Mức giá cạnh tranh trong các lựa chọn còn trống' if price_score >= 20 else 'Mức giá nằm trong giới hạn đã chọn')
            reasons.append({'LOW': 'Nhu cầu dự đoán thấp, thường dễ đặt hơn', 'MEDIUM': 'Nhu cầu dự đoán cân bằng', 'HIGH': 'Khung giờ phổ biến, nên đặt sớm'}[level])
            items.append({
                'field_id': field.id, 'field_name': field.name, 'sport_type': field.sport_type,
                'location': field.location, 'time_slot_id': slot.id, 'time_slot_name': slot.name,
                'start_time': slot.start_time.strftime('%H:%M'), 'end_time': slot.end_time.strftime('%H:%M'),
                'price': float(slot.price), 'demand_level': level, 'demand_confidence': prediction.confidence,
                'recommendation_score': score, 'reasons': reasons,
            })
        items.sort(key=lambda item: (-item['recommendation_score'], item['price'], item['start_time']))
        return RecommendationResponse(booking_date=booking_date, sport_type=sport_type, strategy=self._strategy(), items=items[:limit])

    def _predict_features(self, features: dict):
        try:
            artifact = load_model_artifact()
            pipeline = artifact['pipeline']
            frame = pd.DataFrame([features], columns=FEATURE_COLUMNS)
            demand_level = str(pipeline.predict(frame)[0])
            probabilities = {}
            if hasattr(pipeline, 'predict_proba'):
                values = pipeline.predict_proba(frame)[0]
                probabilities = {str(label): round(float(value), 4) for label, value in zip(pipeline.classes_, values)}
            confidence = probabilities.get(demand_level, 1.0)
            return DemandPredictionResponse(
                demand_level=demand_level, confidence=round(confidence, 4), probabilities=probabilities,
                explanation=self._explanation(demand_level, features), features=features,
                model_name=artifact.get('model_name', 'Unknown'),
            )
        except ModelNotReadyError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

    @staticmethod
    def _explanation(level: str, features: dict):
        signals = []
        if features['is_weekend']:
            signals.append('ngày cuối tuần')
        if 17 <= features['start_hour'] <= 21:
            signals.append('khung giờ cao điểm 17–21h')
        if features['previous_booking_count'] >= 15:
            signals.append('nhiều lượt đặt trong lịch sử gần đây')
        elif features['previous_booking_count'] <= 5:
            signals.append('ít lượt đặt trong lịch sử gần đây')
        context = ', '.join(signals) if signals else 'các đặc trưng lịch, giá và môn thể thao'
        labels = {'LOW': 'thấp', 'MEDIUM': 'trung bình', 'HIGH': 'cao'}
        return f'Mô hình dự đoán nhu cầu {labels[level]} dựa trên {context}. Đây là dự báo xác suất, không phải cam kết số lượt đặt thực tế.'

    @staticmethod
    def _strategy():
        return 'Chỉ lấy sân/khung giờ còn trống đúng môn; xếp hạng rule-based theo giá (45 điểm), tính phù hợp và mức nhu cầu do model dự đoán. LOW/MEDIUM được ưu tiên cho khả năng đặt và giá trị; HIGH được cảnh báo nên đặt sớm.'
