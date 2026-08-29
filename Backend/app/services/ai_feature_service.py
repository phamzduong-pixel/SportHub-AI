import re
import itertools
from datetime import date, timedelta

from fastapi import HTTPException

from ..repositories.booking_repository import BookingRepository
from .ai_provider import AIProviderError, StructuredAIProvider
from .analytics_service import AnalyticsService
from .availability_service import AvailabilityService


class AIFeatureService:
    def __init__(self, db, provider=None):
        self.db = db
        self.provider = provider or StructuredAIProvider()
        self.availability = AvailabilityService(BookingRepository(db))

    def recommend_slots(self, payload):
        missing_fields = [name for name, value in (
            ('sport_type', payload.sport_type), ('date', payload.booking_date),
        ) if not value]
        if missing_fields:
            return {'status': 'NEED_MORE_DATA', 'message': 'Vui lòng cung cấp đúng thông tin còn thiếu.',
                    'missing_fields': missing_fields, 'recommendations': [], 'source': 'backend_validation'}
        if payload.start_time and payload.end_time and payload.end_time <= payload.start_time:
            return {'status': 'NEED_MORE_DATA', 'message': 'Giờ kết thúc phải sau giờ bắt đầu.',
                    'missing_fields': ['end_time'], 'recommendations': [], 'source': 'backend_validation'}
        candidates = self.availability.available_pairs(
            booking_date=payload.booking_date, sport_type=payload.sport_type,
            field_id=payload.court_id,
            location=payload.location,
            start_time=None if payload.time_ranges else payload.start_time,
            end_time=None if payload.time_ranges else payload.end_time,
            max_price=payload.max_price,
        )
        if payload.slot_id:
            candidates = [pair for pair in candidates if pair[1].id == payload.slot_id]
        candidates = [pair for pair in candidates if self._matches_court_type(pair[0], payload.court_type)]
        used_alternatives = False
        if not candidates and payload.allow_alternatives and (payload.start_time or payload.end_time):
            candidates = self.availability.available_pairs(
                booking_date=payload.booking_date, sport_type=payload.sport_type,
                field_id=payload.court_id, location=payload.location, max_price=payload.max_price,
            )
            candidates = [pair for pair in candidates if self._matches_court_type(pair[0], payload.court_type)]
            used_alternatives = bool(candidates)
        if not candidates:
            return {'status': 'NO_AVAILABLE_SLOT',
                    'message': 'Không có khung giờ thực sự còn trống phù hợp với nhu cầu đã chọn.',
                    'missing_fields': [], 'recommendations': [], 'source': 'live_backend'}
        available = self._slot_options(candidates, payload)
        if not available:
            return {'status': 'NO_AVAILABLE_SLOT',
                    'message': 'Không có chuỗi khung giờ liên tiếp còn trống phù hợp với thời lượng đã chọn.',
                    'missing_fields': [], 'recommendations': [], 'source': 'live_backend'}
        allowed = {(item['court_id'], item['slot_id']): item for item in available}
        schema = {
            'type': 'object', 'additionalProperties': False,
            'properties': {
                'status': {'type': 'string', 'enum': ['OK', 'NEED_MORE_DATA', 'NO_AVAILABLE_SLOT']},
                'recommendations': {'type': 'array', 'maxItems': 3, 'items': {
                    'type': 'object', 'additionalProperties': False,
                    'properties': {'court_id': {'type': 'integer'}, 'slot_id': {'type': 'integer'}, 'reason': {'type': 'string'}},
                    'required': ['court_id', 'slot_id', 'reason'],
                }},
            }, 'required': ['status', 'recommendations'],
        }
        try:
            ai_result = self.provider.generate_json(
                task='rank_available_slots',
                system_data={'customer_need': payload.model_dump(mode='json'), 'available_slots': available},
                schema=schema,
            )
            validated, seen = [], set()
            for choice in ai_result.get('recommendations', [])[:3]:
                key = (choice.get('court_id'), choice.get('slot_id'))
                if key not in allowed or key in seen:
                    continue
                seen.add(key)
                validated.append({**allowed[key], 'reason': str(choice.get('reason') or 'Phù hợp nhu cầu đã chọn.')[:240]})
            if validated:
                message = (
                    f'Không còn giờ khớp hoàn toàn; đã kiểm tra {len(validated)} lựa chọn gần nhất còn trống.'
                    if used_alternatives else f'Đã kiểm tra lại {len(validated)} gợi ý với lịch trống hiện tại.'
                )
                return {'status': 'OK', 'message': message,
                        'missing_fields': [], 'recommendations': validated, 'source': 'ai_validated'}
            return {'status': 'NO_AVAILABLE_SLOT',
                    'message': 'AI không trả về lựa chọn hợp lệ trong danh sách slot còn trống; backend đã loại toàn bộ kết quả không hợp lệ.',
                    'missing_fields': [], 'recommendations': [], 'source': 'ai_filtered'}
        except AIProviderError:
            ranked = sorted(available, key=lambda item: (
                abs(self._minutes(item['start_time']) - self._minutes(payload.start_time)) if payload.start_time else 0,
                item['price'], -item['rating'], item['court_id'], item['slot_id'],
            ))[:3]
            return {'status': 'OK', 'message': 'AI provider tạm thời không khả dụng; hệ thống dùng xếp hạng an toàn từ dữ liệu lịch trống.',
                    'recommendations': [{**item, 'reason': 'Lựa chọn còn trống phù hợp nhất theo giờ, giá và đánh giá.'} for item in ranked],
                    'missing_fields': [], 'source': 'fallback'}

    @staticmethod
    def _slot_data(field, slot, booking_date):
        return {
            'facility_id': field.facility_id,
            'court_id': field.id, 'slot_id': slot.id,
            'facility_name': field.facility.name if field.facility else field.name,
            'court_name': field.name, 'sport_type': field.sport_type,
            'court_type': AIFeatureService._court_type_label(field), 'location': field.location,
            'booking_date': booking_date, 'start_time': slot.start_time, 'end_time': slot.end_time,
            'slot_name': slot.name, 'image_url': field.image_url,
            'price': float(slot.price), 'rating': float(field.rating or 0),
            'distance_km': field.distance_km,
        }

    def _slot_options(self, candidates, payload):
        grouped = {}
        for field, slot in candidates:
            grouped.setdefault(field.id, {'field': field, 'slots': []})['slots'].append(slot)
        requested_duration = payload.duration_minutes
        if requested_duration is None and payload.start_time and payload.end_time:
            requested_duration = self._minutes(payload.end_time) - self._minutes(payload.start_time)
        options = []
        for group in grouped.values():
            field = group['field']
            slots = sorted(group['slots'], key=lambda item: item.start_time)
            if payload.time_ranges:
                sequence = []
                valid = True
                for requested_start, requested_end in payload.time_ranges:
                    range_slots = [
                        slot for slot in slots
                        if slot.start_time >= requested_start and slot.end_time <= requested_end
                    ]
                    range_slots.sort(key=lambda item: item.start_time)
                    if (not range_slots or range_slots[0].start_time != requested_start
                            or range_slots[-1].end_time != requested_end
                            or any(current.end_time != following.start_time for current, following in zip(range_slots, range_slots[1:]))):
                        valid = False
                        break
                    sequence.extend(range_slots)
                if not valid or len({slot.id for slot in sequence}) != len(sequence):
                    continue
                total_price = sum(float(slot.price) for slot in sequence)
                if payload.max_price is not None and total_price > payload.max_price:
                    continue
                first = sequence[0]
                data = self._slot_data(field, first, payload.booking_date)
                data.update({
                    'slot_ids': [slot.id for slot in sequence],
                    'slot_name': '; '.join(slot.name for slot in sequence),
                    'end_time': sequence[-1].end_time,
                    'price': total_price,
                    'duration_minutes': sum(self._minutes(slot.end_time) - self._minutes(slot.start_time) for slot in sequence),
                    'selected_slots': [
                        {'slot_id': slot.id, 'start_time': slot.start_time, 'end_time': slot.end_time, 'price': float(slot.price)}
                        for slot in sequence
                    ],
                })
                options.append(data)
                continue
            if not requested_duration:
                options.extend(self._slot_data(field, slot, payload.booking_date) | {
                    'slot_ids': [slot.id], 'duration_minutes': self._minutes(slot.end_time) - self._minutes(slot.start_time),
                    'selected_slots': [{'slot_id': slot.id, 'start_time': slot.start_time, 'end_time': slot.end_time, 'price': float(slot.price)}],
                } for slot in slots)
                continue
            for r in range(1, min(len(slots) + 1, 5)):
                for sequence_tuple in itertools.combinations(slots, r):
                    sequence = list(sequence_tuple)
                    duration = sum(self._minutes(slot.end_time) - self._minutes(slot.start_time) for slot in sequence)
                    if duration != requested_duration:
                        continue
                    if payload.start_time and sequence[0].start_time != payload.start_time:
                        continue
                    if payload.end_time and sequence[-1].end_time != payload.end_time:
                        continue
                    total_price = sum(float(slot.price) for slot in sequence)
                    if payload.max_price is not None and total_price > payload.max_price:
                        continue
                    data = self._slot_data(field, sequence[0], payload.booking_date)
                    data.update({
                        'slot_ids': [slot.id for slot in sequence],
                        'slot_name': '; '.join(slot.name for slot in sequence),
                        'end_time': sequence[-1].end_time,
                        'price': total_price,
                        'duration_minutes': duration,
                        'selected_slots': [
                            {'slot_id': slot.id, 'start_time': slot.start_time, 'end_time': slot.end_time, 'price': float(slot.price)}
                            for slot in sequence
                        ],
                    })
                    options.append(data)
        return options

    @staticmethod
    def _court_type_label(field):
        people = re.search(r'\b(\d{1,2})\s*(?:người|nguoi)\b', field.name, re.IGNORECASE)
        return f'{int(people[1])} người' if people else f'Sức chứa {field.capacity} người'

    @staticmethod
    def _matches_court_type(field, court_type):
        if not court_type:
            return True
        requested = re.search(r'\d{1,2}', court_type)
        if requested:
            return int(field.capacity or 0) >= int(requested[0])
        normalized = court_type.casefold()
        haystack = (field.name + ' ' + ' '.join(field.amenities or [])).casefold()
        return normalized.replace('sân ', '') in haystack or normalized in haystack

    @staticmethod
    def _minutes(value):
        return value.hour * 60 + value.minute

    def occupancy_summary(self, user, date_from: date | None, date_to: date | None, field_id: int | None):
        end = date_to or date.today()
        start = date_from or end - timedelta(days=29)
        if start > end or (end - start).days > 365:
            raise HTTPException(status_code=422, detail='Khoảng phân tích công suất không hợp lệ')
        analytics = AnalyticsService(self.db).occupancy(user, start, end, field_id)
        if analytics is None:
            raise HTTPException(status_code=403, detail='Tài khoản chưa được gán phạm vi OWNER')
        fallback_summary = (
            f'Công suất giai đoạn này là {analytics["occupancy_rate"]:.2f}% '
            f'({analytics["booked_hours"]:.2f}/{analytics["total_operating_hours"]:.2f} giờ khai thác).'
        )
        fallback_promotions = [
            f'{item["field_name"]} · {item["start_time"]}-{item["end_time"]}: '
            'cân nhắc ưu đãi giới hạn hoặc gói đặt theo nhóm cho giờ thấp điểm.'
            for item in analytics['low_demand_hours']
        ]
        base_response = {
            'analytics': analytics, 'label': 'Gợi ý AI',
            'peak_hours': analytics['peak_hours'],
            'low_demand_hours': analytics['low_demand_hours'],
        }
        if not analytics['low_demand_hours']:
            return {'summary': fallback_summary, 'promotion_suggestions': [],
                    'source': 'fallback', **base_response}
        schema = {
            'type': 'object', 'additionalProperties': False,
            'properties': {
                'summary': {'type': 'string'},
                'peak_slot_ids': {'type': 'array', 'maxItems': 3, 'items': {'type': 'integer'}},
                'low_demand_slot_ids': {'type': 'array', 'maxItems': 3, 'items': {'type': 'integer'}},
                'promotions': {'type': 'array', 'maxItems': 3, 'items': {
                    'type': 'object', 'additionalProperties': False,
                    'properties': {'slot_id': {'type': 'integer'}, 'suggestion': {'type': 'string'}},
                    'required': ['slot_id', 'suggestion'],
                }},
            }, 'required': ['summary', 'peak_slot_ids', 'low_demand_slot_ids', 'promotions'],
        }
        try:
            result = self.provider.generate_json(
                task='summarize_occupancy_and_suggest_promotions',
                system_data={
                    'analytics': analytics,
                    'instruction': 'Summary must be qualitative without numbers. Promotions may propose mechanics but must not claim a forecast or database change.',
                }, schema=schema,
            )
            summary = str(result.get('summary', '')).strip()
            if not summary or re.search(r'\d|[$€£₫]', summary):
                raise AIProviderError('AI summary changed numeric analytics')
            expected_peak = {item['slot_id'] for item in analytics['peak_hours']}
            expected_low = {item['slot_id'] for item in analytics['low_demand_hours']}
            if not set(result.get('peak_slot_ids', [])).issubset(expected_peak):
                raise AIProviderError('AI invented peak analytics')
            if not set(result.get('low_demand_slot_ids', [])).issubset(expected_low):
                raise AIProviderError('AI invented low-demand analytics')
            allowed = {item['slot_id']: item for item in analytics['low_demand_hours']}
            suggestions, seen = [], set()
            for item in result.get('promotions', [])[:3]:
                slot_id = item.get('slot_id')
                copy = str(item.get('suggestion', '')).strip()
                forbidden_action = any(term in copy.casefold() for term in ('đã tạo', 'đã áp dụng', 'đã cập nhật', 'tự động sửa'))
                if slot_id not in allowed or slot_id in seen or not copy or re.search(r'\d|[$€£₫]', copy) or forbidden_action:
                    continue
                seen.add(slot_id)
                slot = allowed[slot_id]
                suggestions.append(f'{slot["field_name"]} · {slot["start_time"]}-{slot["end_time"]}: {copy[:260]}')
            return {'summary': summary, 'promotion_suggestions': suggestions,
                    'source': 'ai_validated', **base_response}
        except AIProviderError:
            return {'summary': fallback_summary, 'promotion_suggestions': fallback_promotions,
                    'source': 'fallback', **base_response}
