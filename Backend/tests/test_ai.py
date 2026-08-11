import unittest
from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.inference.model_loader import load_metrics, load_model_artifact
from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.field import Booking, Field
from app.models.time_slot import TimeSlot
from app.models.user import User, UserRole


class AIDemandTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            owner = User(full_name='Owner', email='aiowner@test.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value)
            analyst = User(full_name='AI Operator', email='aianalyst@test.local', hashed_password=get_password_hash('Operator@123'), role=UserRole.CUSTOMER.value)
            operator = User(full_name='No AI', email='ainone@test.local', hashed_password=get_password_hash('Operator@123'), role=UserRole.CUSTOMER.value)
            customer = User(full_name='Customer', email='aicustomer@test.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value)
            db.add_all([owner, analyst, operator, customer]); db.flush()
            field = Field(name='Sân AI', sport_type='bóng đá', location='Quận 1', capacity=14, base_price=600000, status='available', amenities=[])
            db.add(field); db.flush()
            slot = TimeSlot(field_id=field.id, name='Ca tối', start_time=time(18), end_time=time(20), price=Decimal('650000'), is_active=True)
            db.add(slot); db.flush()
            historical = Booking(
                booking_code='AI-HISTORY', customer_id=customer.id, field_id=field.id, time_slot_id=slot.id,
                booking_date=date.today() - timedelta(days=10), start_time_snapshot=time(18), end_time_snapshot=time(20),
                price_snapshot=650000, total_amount=650000, status='completed',
            )
            db.add(historical); db.commit()
            self.field_id, self.slot_id = field.id, slot.id

        def override_db():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.owner = self.login('aiowner@test.local', 'Owner@123456')
        self.analyst = self.owner
        self.no_ai = self.login('ainone@test.local', 'Operator@123')
        self.customer = self.login('aicustomer@test.local', 'Customer@123')
        self.future = date.today() + timedelta(days=7)

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(self.engine)

    def login(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def payload(self):
        return {
            'sport_type': 'Bóng đá', 'booking_date': self.future.isoformat(),
            'start_hour': 18, 'price': 650000, 'field_id': self.field_id,
        }

    def test_real_prediction_metrics_and_determinism(self):
        first = self.client.post('/ai/predict-demand', headers=self.analyst, json=self.payload())
        second = self.client.post('/ai/predict-demand', headers=self.analyst, json=self.payload())
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json(), second.json())
        self.assertIn(first.json()['demand_level'], ('LOW', 'MEDIUM', 'HIGH'))
        self.assertAlmostEqual(sum(first.json()['probabilities'].values()), 1, places=3)
        self.assertEqual(first.json()['model_name'], 'Random Forest')
        self.assertEqual(first.json()['features']['previous_booking_count'], 1)
        metrics = self.client.get('/ai/model-metrics', headers=self.owner)
        self.assertEqual(metrics.status_code, 200, metrics.text)
        self.assertEqual(metrics.json()['selected_model'], 'Random Forest')
        self.assertGreater(metrics.json()['selected_metrics']['f1_score'], .7)
        self.assertEqual(len(metrics.json()['models']), 3)

    def test_overview_recommendations_and_availability(self):
        overview = self.client.get('/ai/demand-overview?days=3&sport_type=bóng đá', headers=self.owner)
        self.assertEqual(overview.status_code, 200, overview.text)
        self.assertEqual(len(overview.json()['items']), 3)
        self.assertEqual(sum(overview.json()['distribution'].values()), 3)
        recommendations = self.client.get(
            f'/ai/recommendations?sport_type=bóng đá&booking_date={self.future}&max_price=700000', headers=self.owner,
        )
        self.assertEqual(recommendations.status_code, 200, recommendations.text)
        self.assertEqual(len(recommendations.json()['items']), 1)
        self.assertIn('rule-based', recommendations.json()['strategy'])
        with self.Session() as db:
            customer_id = db.scalar(select(User.id).where(User.role == 'CUSTOMER'))
            db.add(Booking(
                booking_code='AI-BLOCKED', customer_id=customer_id, field_id=self.field_id, time_slot_id=self.slot_id,
                booking_date=self.future, start_time_snapshot=time(18), end_time_snapshot=time(20),
                price_snapshot=650000, total_amount=650000, status='confirmed',
            )); db.commit()
        blocked = self.client.get(f'/ai/recommendations?sport_type=bóng đá&booking_date={self.future}', headers=self.owner)
        self.assertEqual(blocked.json()['items'], [])

    def test_permission_validation_and_missing_model_error(self):
        for headers in (self.no_ai, self.customer):
            self.assertEqual(self.client.post('/ai/predict-demand', headers=headers, json=self.payload()).status_code, 403)
            self.assertEqual(self.client.get('/ai/model-metrics', headers=headers).status_code, 403)
        mismatch = self.payload(); mismatch['sport_type'] = 'tennis'
        self.assertEqual(self.client.post('/ai/predict-demand', headers=self.owner, json=mismatch).status_code, 422)
        past = self.client.get(f'/ai/recommendations?sport_type=bóng đá&booking_date={date.today() - timedelta(days=1)}', headers=self.owner)
        self.assertEqual(past.status_code, 422)
        load_model_artifact.cache_clear(); load_metrics.cache_clear()
        with patch('app.ai.inference.model_loader.MODEL_PATH', Path('missing-model.joblib')):
            missing = self.client.post('/ai/predict-demand', headers=self.owner, json=self.payload())
            self.assertEqual(missing.status_code, 503)
            self.assertIn('Chưa có model', missing.json()['detail'])
        load_model_artifact.cache_clear(); load_metrics.cache_clear()


if __name__ == '__main__':
    unittest.main()
