from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.datasets.loader import FEATURE_COLUMNS, load_demand_dataset
from app.ai.evaluation.evaluate_model import evaluate_saved_model
from app.ai.inference.model_loader import (
    ModelNotReadyError, load_metrics, load_model_artifact, load_model_metadata,
)
from app.ai.inference.prediction_service import DemandPredictionService
from app.ai.preprocessing.feature_engineering import build_feature_record
from app.ai.training.train_model import candidate_models
from app.database.base import Base
from app.models.facility import Facility
from app.models.field import Field
from app.models.time_slot import TimeSlot
from app.models.user import User
from app.repositories.ai_repository import AIRepository
from app.schemas.ai import DemandPredictionRequest


@pytest.fixture
def ml_phase4_db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    owner = User(
        id=1, email='owner_ml@sporthub.vn',
        role='OWNER', full_name='ML Owner Phase 4',
        hashed_password='hashed_pw', is_active=True,
    )
    customer = User(
        id=2, email='customer_ml@sporthub.vn',
        role='CUSTOMER', full_name='ML Customer Phase 4',
        hashed_password='hashed_pw', is_active=True,
    )
    facility = Facility(
        id=1, owner_id=1, name='Facility ML Phase 4',
        is_active=True, status='APPROVED', location='123 ML St'
    )
    field = Field(
        id=1, facility_id=1, owner_id=1, name='San ML 1',
        sport_type='bóng đá', status='available', location='123 ML St', capacity=14, base_price=Decimal('650000')
    )
    session.add_all([owner, customer, facility, field])
    session.commit()

    yield session
    session.close()


def test_ml_dataset_and_feature_engineering():
    dataset = load_demand_dataset()
    assert len(dataset) >= 100
    for col in FEATURE_COLUMNS:
        assert col in dataset.columns
    assert 'demand_level' in dataset.columns

    record = build_feature_record(
        sport_type='Bóng Đá',
        booking_date=date(2026, 8, 28),
        start_hour=18,
        price=650000.0,
        previous_booking_count=10,
        field_capacity=14,
    )
    assert record['sport_type'] == 'bóng đá'
    assert record['day_of_week'] == 4 # Friday
    assert record['month'] == 8
    assert record['is_weekend'] == 0
    assert record['start_hour'] == 18
    assert record['previous_booking_count'] == 10
    assert record['field_capacity'] == 14


def test_ml_candidate_models():
    models = candidate_models()
    assert 'Random Forest' in models
    assert 'Logistic Regression' in models
    assert 'Decision Tree' in models


def test_ml_inference_service(ml_phase4_db):
    service = DemandPredictionService(AIRepository(ml_phase4_db))
    user = ml_phase4_db.query(User).filter_by(id=1).first()
    service.for_user(user)

    payload = DemandPredictionRequest(
        sport_type='bóng đá',
        booking_date=date.today() + timedelta(days=1),
        start_hour=19,
        price=650000,
        field_capacity=14,
        previous_booking_count=10,
    )

    res = service.predict(payload)
    assert res.demand_level.value in ('LOW', 'MEDIUM', 'HIGH')
    assert 0.0 <= res.confidence <= 1.0
    assert res.model_name == 'Random Forest'
    assert 'bóng đá' in res.features['sport_type']


def test_ml_model_missing_error():
    load_model_artifact.cache_clear()
    fake_path = Path('/non/existent/demand_pipeline.joblib')
    with patch('app.ai.inference.model_loader.MODEL_PATH', fake_path):
        with pytest.raises(ModelNotReadyError, match='Chưa có model AI'):
            load_model_artifact()


def test_ml_version_mismatch_error():
    load_model_artifact.cache_clear()
    with patch('app.ai.inference.model_loader.sklearn.__version__', '99.0.0'):
        with pytest.raises(ModelNotReadyError, match='đồng bộ dependency'):
            load_model_artifact()
