from types import SimpleNamespace
from datetime import date, timedelta

import pytest

from app.schemas.ai import AssistantMode
from app.services import ai_assistant_service
from app.services.ai_assistant_service import AIAssistantService
from app.services.ai_intent_router import AssistantIntent, IntentRouter


class _VenueRepository:
    def __init__(self):
        self.search_args = None
        self.db = object()

    def scope_for_user(self, user):
        return None

    def search_venues(self, **kwargs):
        self.search_args = kwargs
        return [SimpleNamespace(
            id=7,
            facility_id=3,
            facility=SimpleNamespace(name='Sân SportHub', location='Quận 1, TP.HCM'),
            name='Sân bóng số 1',
            sport_type='bóng đá',
            capacity=7,
            location='Quận 1, TP.HCM',
            base_price=500000,
            rating=4.8,
            image_url=None,
        )]

    def inventory(self):
        return []


class _NoopGuardrail:
    pass


@pytest.mark.parametrize('mode', [AssistantMode.NATURAL, AssistantMode.PROFESSIONAL])
def test_budgeted_sports_venue_query_searches_catalog_in_both_modes(mode):
    repository = _VenueRepository()
    service = AIAssistantService(repository, guardrail=_NoopGuardrail())

    response = service.ask('Tìm sân bóng dưới 700.000đ', assistant_mode=mode)

    assert response['classification'] == 'IN_SCOPE'
    assert response['venue_results'][0]['base_price'] == 500000
    assert repository.search_args['sport_type'] == 'bóng đá'
    assert repository.search_args['max_price'] == 700000
    assert repository.search_args['location'] is None


@pytest.mark.parametrize('mode', [AssistantMode.NATURAL, AssistantMode.PROFESSIONAL])
def test_bare_san_bong_query_asks_for_search_details(mode):
    repository = _VenueRepository()
    service = AIAssistantService(repository, guardrail=_NoopGuardrail())

    response = service.ask('Sân bóng', assistant_mode=mode)

    assert response['status'] == 'NEED_MORE_DATA'
    assert response['needs_clarification'] is True
    assert response['missing_fields'] == ['sport_type', 'location', 'date']
    assert repository.search_args is None


def test_budgeted_venue_query_is_not_classified_as_nonsense_or_out_of_scope():
    route = IntentRouter().route('Tìm sân bóng dưới 700.000đ', {})

    assert route.intent == AssistantIntent.SEARCH_VENUE
    assert route.entities.sport_type == 'bóng đá'
    assert route.entities.max_price == 700000


def test_price_without_explicit_sport_uses_catalog_and_asks_for_details():
    repository = _VenueRepository()
    service = AIAssistantService(repository, guardrail=_NoopGuardrail())

    response = service.ask('Tìm sân dưới 700.000đ', assistant_mode=AssistantMode.PROFESSIONAL)

    assert response['status'] == 'NEED_MORE_DATA'
    assert response['venue_results'][0]['base_price'] == 500000
    assert response['missing_fields'] == ['sport_type', 'location', 'date']
    assert repository.search_args['sport_type'] is None
    assert repository.search_args['max_price'] == 700000


@pytest.mark.parametrize('mode', [AssistantMode.NATURAL, AssistantMode.PROFESSIONAL])
@pytest.mark.parametrize('followup', ['vậy còn ngày nào', 'còn ngày nào còn trống'])
def test_alternative_date_followup_searches_after_context_date(monkeypatch, followup, mode):
    tomorrow = date.today() + timedelta(days=1)
    next_available = tomorrow + timedelta(days=1)
    repository = _VenueRepository()

    class _UnavailableFeatureService:
        def __init__(self, db):
            pass

        def recommend_slots(self, payload):
            return {'status': 'NO_AVAILABLE_SLOT', 'message': 'Không có khung giờ thực sự còn trống phù hợp với nhu cầu đã chọn.'}

    monkeypatch.setattr(ai_assistant_service, 'AIFeatureService', _UnavailableFeatureService)
    service = AIAssistantService(repository, guardrail=_NoopGuardrail())
    alternative_requests = []

    def search_alternatives(payload, days=7):
        alternative_requests.append((payload, days))
        return [{
            'booking_date': next_available,
            'start_time': '18:00',
            'end_time': '19:00',
            'court_id': 7,
            'field_id': 7,
            'slot_id': 12,
            'time_slot_id': 12,
            'slot_name': '18:00–19:00',
            'facility_id': 3,
            'facility_name': 'Cụm sân Cầu Vồng',
            'court_name': 'Sân cầu lông 1',
            'sport_type': 'cầu lông',
            'location': 'Cầu Giấy, Hà Nội',
            'price': 120000,
            'duration_minutes': 60,
            'rating': 4.7,
            'reason': 'Còn lịch',
        }]

    monkeypatch.setattr(service, '_search_alternative_dates', search_alternatives)
    context = {
        'sport_type': 'cầu lông',
        'location': 'Hà Nội',
        'max_price': 700000,
        'booking_date': tomorrow.isoformat(),
        'last_intent': 'CHECK_AVAILABILITY',
        'business_context': {
            'sport_type': 'cầu lông',
            'location': 'Hà Nội',
            'max_price': 700000,
            'booking_date': tomorrow.isoformat(),
        },
    }

    response = service.ask(followup, context=context, assistant_mode=mode)

    assert response['status'] == 'OK'
    assert 'Gần nhất tôi tìm thấy' in response['reply']
    assert response['venue_results'] == []
    assert len(alternative_requests) == 1
    assert alternative_requests[0][0].booking_date == tomorrow
    assert alternative_requests[0][0].sport_type == 'cầu lông'
    assert alternative_requests[0][0].location == 'Hà Nội'
    assert alternative_requests[0][0].max_price == 700000
    assert alternative_requests[0][1] == 14
    assert response['suggestions'][0]['booking_date'] == next_available


def test_alternative_date_phrase_routes_as_availability_followup():
    context = {
        'sport_type': 'cầu lông',
        'last_intent': 'CHECK_AVAILABILITY',
        'business_context': {'sport_type': 'cầu lông'},
    }

    route = IntentRouter().route('Vậy còn ngày nào?', context)

    assert route.intent == AssistantIntent.CHECK_AVAILABILITY
    assert route.context_reset is False


def test_no_alternative_dates_gives_contextual_next_fourteen_days_response(monkeypatch):
    tomorrow = date.today() + timedelta(days=1)

    class _UnavailableFeatureService:
        def __init__(self, db):
            pass

        def recommend_slots(self, payload):
            return {'status': 'NO_AVAILABLE_SLOT', 'message': 'Không có khung giờ phù hợp.'}

    monkeypatch.setattr(ai_assistant_service, 'AIFeatureService', _UnavailableFeatureService)
    service = AIAssistantService(_VenueRepository(), guardrail=_NoopGuardrail())
    monkeypatch.setattr(service, '_search_alternative_dates', lambda payload, days=7: [])

    response = service.ask(
        'Vậy còn ngày nào?',
        context={
            'sport_type': 'cầu lông',
            'location': 'Hà Nội',
            'booking_date': tomorrow.isoformat(),
            'last_intent': 'CHECK_AVAILABILITY',
        },
        assistant_mode=AssistantMode.NATURAL,
    )

    assert response['status'] == 'NO_AVAILABLE_SLOT'
    assert response['needs_clarification'] is True
    assert 'trong 14 ngày tiếp theo' in response['reply']
    assert response['missing_fields'] == ['date_or_filters']


@pytest.mark.parametrize('mode', [AssistantMode.NATURAL, AssistantMode.PROFESSIONAL])
def test_multi_turn_budget_sport_switch_and_alternative_date_search(monkeypatch, mode):
    tomorrow = date.today() + timedelta(days=1)
    available_date = tomorrow + timedelta(days=1)

    class _UnavailableFeatureService:
        def __init__(self, db):
            pass

        def recommend_slots(self, payload):
            return {'status': 'NO_AVAILABLE_SLOT', 'message': 'Không có khung giờ phù hợp.'}

    monkeypatch.setattr(ai_assistant_service, 'AIFeatureService', _UnavailableFeatureService)
    repository = _VenueRepository()
    service = AIAssistantService(repository, guardrail=_NoopGuardrail())
    alt_calls = []

    def alternatives(payload, days=7):
        alt_calls.append((payload, days))
        if len(alt_calls) == 1:
            return []
        return [{
            'booking_date': available_date,
            'start_time': '18:00',
            'end_time': '19:00',
            'field_id': 7,
            'time_slot_id': 12,
            'facility_id': 3,
            'facility_name': 'Cụm sân Cầu Vồng',
            'court_name': 'Sân cầu lông 1',
            'sport_type': 'cầu lông',
            'location': 'Cầu Giấy, Hà Nội',
            'price': 120000,
            'rating': 4.7,
        }]

    monkeypatch.setattr(service, '_search_alternative_dates', alternatives)

    first = service.ask('Tìm sân bóng dưới 700.000đ ở Hà Nội', assistant_mode=mode)
    switched_sport = service.ask('còn sân cầu lông', context=first['understood'], assistant_mode=mode)
    assert switched_sport['missing_fields'] == ['date']
    assert repository.search_args['sport_type'] == 'cầu lông'
    assert repository.search_args['location'] == 'Hà Nội'
    assert repository.search_args['max_price'] == 700000

    no_slots = service.ask('ngày mai', context=switched_sport['understood'], assistant_mode=mode)
    assert no_slots['status'] == 'NO_AVAILABLE_SLOT'
    alternative = service.ask('vậy còn ngày nào', context=no_slots['understood'], assistant_mode=mode)

    assert alternative['status'] == 'OK'
    assert alternative['suggestions'][0]['booking_date'] == available_date
    assert alt_calls[-1][0].booking_date == tomorrow
    assert alt_calls[-1][0].sport_type == 'cầu lông'
    assert alt_calls[-1][0].location == 'Hà Nội'
    assert alt_calls[-1][0].max_price == 700000
    assert alt_calls[0][1] == 7
    assert alt_calls[-1][1] == 14
