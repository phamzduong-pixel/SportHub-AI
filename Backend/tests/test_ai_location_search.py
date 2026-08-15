import unittest
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.facility import Facility
from app.models.field import Field
from app.models.user import User
from app.services.ai_intent_router import AssistantIntent, IntentRouter


class LocationIntentRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()

    def route(self, message, context=None):
        return self.router.route(message, context, today=date(2026, 8, 14))

    def test_search_venue_by_location(self):
        result = self.route('c\u00f3 s\u00e2n n\u00e0o \u1edf H\u00e0 N\u1ed9i kh\u00f4ng')
        self.assertEqual(result.intent, AssistantIntent.SEARCH_VENUE)
        self.assertEqual(result.entities.location, 'H\u00e0 N\u1ed9i')

    def test_search_venue_by_location_and_sport(self):
        result = self.route('\u1edf H\u00e0 N\u1ed9i c\u00f3 s\u00e2n b\u00f3ng kh\u00f4ng')
        self.assertEqual(result.intent, AssistantIntent.SEARCH_VENUE)
        self.assertEqual(result.entities.location, 'H\u00e0 N\u1ed9i')
        self.assertEqual(result.entities.sport_type, 'b\u00f3ng \u0111\u00e1')

    def test_location_entity_hanoi(self):
        self.assertEqual(self.route('c\u00f3 H\u00e0 N\u1ed9i kh\u00f4ng').entities.location, 'H\u00e0 N\u1ed9i')

    def test_location_without_diacritics(self):
        result = self.route('tim san cau long o Ha Noi')
        self.assertEqual(result.intent, AssistantIntent.SEARCH_VENUE)
        self.assertEqual(result.entities.location, 'H\u00e0 N\u1ed9i')

    def test_search_venue_does_not_require_date(self):
        result = self.route('t\u00ecm s\u00e2n c\u1ea7u l\u00f4ng \u1edf H\u00e0 N\u1ed9i')
        self.assertEqual(result.intent, AssistantIntent.SEARCH_VENUE)
        self.assertIsNone(result.entities.date)
        self.assertFalse(result.needs_clarification)

    def test_search_venue_does_not_require_time(self):
        result = self.route('t\u00f4i mu\u1ed1n s\u00e2n c\u1ea7u l\u00f4ng')
        self.assertEqual(result.intent, AssistantIntent.SEARCH_VENUE)
        self.assertIsNone(result.entities.start_time)

    def test_search_venue_and_check_availability_are_distinct(self):
        search = self.route('c\u00f3 s\u00e2n n\u00e0o \u1edf H\u00e0 N\u1ed9i kh\u00f4ng')
        availability = self.route('t\u1ed1i nay \u1edf H\u00e0 N\u1ed9i c\u00f2n s\u00e2n c\u1ea7u l\u00f4ng n\u00e0o')
        self.assertEqual(search.intent, AssistantIntent.SEARCH_VENUE)
        self.assertEqual(availability.intent, AssistantIntent.CHECK_AVAILABILITY)

    def test_venue_count_routes_to_search_instead_of_unclear(self):
        result = self.route('SportHub c\u00f3 bao nhi\u00eau c\u01a1 s\u1edf?')
        self.assertEqual(result.intent, AssistantIntent.SEARCH_VENUE)


class LocationVenueSearchApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            'sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool,
        )
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            owner = User(
                full_name='Location Owner', email='location-owner@test.local',
                hashed_password=get_password_hash('Owner@123456'), role='OWNER',
            )
            db.add(owner)
            db.flush()
            hanoi = Facility(
                owner_id=owner.id, name='Cau Giay Sports Center',
                location='C\u1ea7u Gi\u1ea5y, H\u00e0 N\u1ed9i', city='H\u00e0 N\u1ed9i', district='C\u1ea7u Gi\u1ea5y',
                sports=['b\u00f3ng \u0111\u00e1', 'c\u1ea7u l\u00f4ng'], status='APPROVED', is_active=True,
            )
            hcm = Facility(
                owner_id=owner.id, name='Saigon Sports Center',
                location='B\u00ecnh Th\u1ea1nh, TP.HCM', city='TP.HCM', district='B\u00ecnh Th\u1ea1nh',
                sports=['b\u00f3ng \u0111\u00e1'], status='APPROVED', is_active=True,
            )
            db.add_all([hanoi, hcm])
            db.flush()
            fields = [
                Field(owner_id=owner.id, facility_id=hanoi.id, name='S\u00e2n b\u00f3ng 7',
                      sport_type='b\u00f3ng \u0111\u00e1', location=hanoi.location, capacity=7,
                      base_price=350000, status='available', amenities=[]),
                Field(owner_id=owner.id, facility_id=hanoi.id, name='S\u00e2n c\u1ea7u l\u00f4ng A',
                      sport_type='c\u1ea7u l\u00f4ng', location=hanoi.location, capacity=4,
                      base_price=120000, status='available', amenities=[]),
                Field(owner_id=owner.id, facility_id=hcm.id, name='S\u00e2n b\u00f3ng HCM',
                      sport_type='b\u00f3ng \u0111\u00e1', location=hcm.location, capacity=7,
                      base_price=300000, status='available', amenities=[]),
            ]
            db.add_all(fields)
            db.commit()
            self.hanoi_field_ids = {fields[0].id, fields[1].id}
            self.known_field_ids = self.hanoi_field_ids | {fields[2].id}

        def override_db():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)

    def ask(self, message, context=None):
        body = {'message': message}
        if context is not None:
            body['context'] = context
        response = self.client.post('/ai/assistant', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_known_location_is_not_generic_fallback(self):
        payload = self.ask('c\u00f3 s\u00e2n n\u00e0o \u1edf H\u00e0 N\u1ed9i kh\u00f4ng')
        self.assertEqual(payload['intent'], 'SEARCH_VENUE')
        self.assertEqual(payload['status'], 'NEED_MORE_DATA')
        self.assertEqual(payload['missing_fields'], ['sport_type'])
        self.assertEqual({item['field_id'] for item in payload['venue_results']}, self.hanoi_field_ids)

    def test_clarification_asks_only_missing_entity(self):
        payload = self.ask('c\u00f3 H\u00e0 N\u1ed9i kh\u00f4ng')
        self.assertEqual(payload['missing_fields'], ['sport_type'])
        self.assertNotIn('location', payload['missing_fields'])

    def test_location_and_sport_query_real_database_before_date(self):
        payload = self.ask('t\u00ecm s\u00e2n c\u1ea7u l\u00f4ng \u1edf H\u00e0 N\u1ed9i')
        self.assertEqual(payload['status'], 'NEED_MORE_DATA')
        self.assertEqual(payload['missing_fields'], ['date'])
        self.assertEqual(len(payload['venue_results']), 1)
        self.assertEqual(payload['venue_results'][0]['court_name'], 'S\u00e2n c\u1ea7u l\u00f4ng A')

    def test_existing_location_not_asked_again(self):
        first = self.ask('c\u00f3 s\u00e2n n\u00e0o \u1edf H\u00e0 N\u1ed9i kh\u00f4ng')
        second = self.ask('B\u00f3ng \u0111\u00e1 7 ng\u01b0\u1eddi', first['understood'])
        self.assertEqual(second['entities']['location'], 'H\u00e0 N\u1ed9i')
        self.assertEqual(second['missing_fields'], ['date'])
        self.assertNotIn('location', second['missing_fields'])

    def test_clarification_does_not_repeat_known_location(self):
        payload = self.ask('t\u00ecm s\u00e2n b\u00f3ng \u1edf H\u00e0 N\u1ed9i')
        self.assertEqual(payload['missing_fields'], ['date'])
        self.assertNotIn('location', payload['missing_fields'])

    def test_follow_up_keeps_location(self):
        context = {'location': 'H\u00e0 N\u1ed9i', 'last_intent': 'SEARCH_VENUE'}
        payload = self.ask('c\u00f2n s\u00e2n c\u1ea7u l\u00f4ng th\u00ec sao', context)
        self.assertEqual(payload['understood']['location'], 'H\u00e0 N\u1ed9i')
        self.assertEqual(payload['venue_results'][0]['sport_type'], 'c\u1ea7u l\u00f4ng')

    def test_no_result_has_no_fake_cards(self):
        payload = self.ask('Th\u00e1i Nguy\u00ean c\u00f3 s\u00e2n c\u1ea7u l\u00f4ng kh\u00f4ng')
        self.assertEqual(payload['status'], 'NO_RESULT')
        self.assertEqual(payload['venue_results'], [])
        self.assertEqual(payload['suggestions'], [])

    def test_follow_up_count_uses_previous_context(self):
        first = self.ask('Th\u00e1i Nguy\u00ean c\u00f3 s\u00e2n c\u1ea7u l\u00f4ng kh\u00f4ng')
        second = self.ask('c\u00f3 bao nhi\u00eau c\u01a1 s\u1edf', first['understood'])
        self.assertEqual(second['intent'], 'SEARCH_VENUE')
        self.assertEqual(second['understood']['location'], 'Th\u00e1i Nguy\u00ean')
        self.assertEqual(second['understood']['sport_type'], 'c\u1ea7u l\u00f4ng')
        self.assertEqual(second['understood']['venue_count'], 0)

    def test_follow_up_does_not_return_generic_fallback(self):
        first = self.ask('Th\u00e1i Nguy\u00ean c\u00f3 s\u00e2n c\u1ea7u l\u00f4ng kh\u00f4ng')
        second = self.ask('c\u00f3 bao nhi\u00eau c\u01a1 s\u1edf', first['understood'])
        self.assertNotIn('booking hay thanh to\u00e1n', second['reply'])
        self.assertEqual(second['status'], 'NO_RESULT')

    def test_platform_venue_count_uses_real_database(self):
        payload = self.ask('SportHub c\u00f3 bao nhi\u00eau c\u01a1 s\u1edf?')
        self.assertEqual(payload['status'], 'OK')
        self.assertEqual(payload['understood']['venue_count'], 2)

    def test_ai_does_not_invent_venue_or_location(self):
        payload = self.ask('c\u00f3 s\u00e2n n\u00e0o \u1edf H\u00e0 N\u1ed9i kh\u00f4ng')
        self.assertTrue({item['field_id'] for item in payload['venue_results']} <= self.known_field_ids)
        self.assertTrue(all('H\u00e0 N\u1ed9i' in item['location'] for item in payload['venue_results']))

    def test_new_location_query_clears_stale_results(self):
        first = self.ask('c\u00f3 s\u00e2n n\u00e0o \u1edf H\u00e0 N\u1ed9i kh\u00f4ng')
        second = self.ask('Th\u00e1i Nguy\u00ean c\u00f3 s\u00e2n c\u1ea7u l\u00f4ng kh\u00f4ng', first['understood'])
        self.assertTrue(second['context_reset'])
        self.assertEqual(second['venue_results'], [])
        self.assertNotIn('result_field_ids', second['understood'])


if __name__ == '__main__':
    unittest.main()
