import unittest
import warnings
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import sklearn
from sklearn.exceptions import InconsistentVersionWarning

from app.ai.datasets.loader import FEATURE_COLUMNS
from app.ai.inference.model_loader import (
    ModelNotReadyError, load_model_artifact, load_model_metadata,
)
from app.ai.preprocessing.feature_engineering import build_feature_record


class MLModelCompatibilityTests(unittest.TestCase):
    def tearDown(self):
        load_model_artifact.cache_clear()
        load_model_metadata.cache_clear()

    def test_saved_model_loads(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            artifact = load_model_artifact()
        self.assertFalse(any(isinstance(item.message, InconsistentVersionWarning) for item in caught))
        self.assertIn('pipeline', artifact)
        self.assertEqual(artifact['model_name'], 'Random Forest')
        self.assertEqual(artifact['metadata']['sklearn_version'], sklearn.__version__)

    def test_model_feature_shape(self):
        artifact = load_model_artifact()
        pipeline = artifact['pipeline']
        self.assertEqual(list(pipeline.feature_names_in_), FEATURE_COLUMNS)
        self.assertEqual(pipeline.n_features_in_, len(FEATURE_COLUMNS))
        self.assertEqual(artifact['metadata']['feature_names'], FEATURE_COLUMNS)

    def test_model_inference(self):
        features = build_feature_record(
            sport_type='bóng đá', booking_date=date(2026, 8, 14),
            start_hour=19, price=650000,
            previous_booking_count=12, field_capacity=14,
        )
        frame = pd.DataFrame([features], columns=FEATURE_COLUMNS)
        pipeline = load_model_artifact()['pipeline']
        prediction = str(pipeline.predict(frame)[0])
        probabilities = pipeline.predict_proba(frame)[0]
        self.assertIn(prediction, {'LOW', 'MEDIUM', 'HIGH'})
        self.assertEqual(len(probabilities), len(pipeline.classes_))
        self.assertAlmostEqual(float(sum(probabilities)), 1.0, places=6)

    def test_model_metadata_version(self):
        metadata = load_model_metadata()
        requirement = next(
            line for line in Path('requirements.txt').read_text(encoding='utf-8').splitlines()
            if line.startswith('scikit-learn==')
        )
        self.assertEqual(metadata['sklearn_version'], requirement.split('==', 1)[1])
        self.assertEqual(metadata['sklearn_version'], sklearn.__version__)
        self.assertTrue(metadata['trained_at'])
        self.assertTrue(metadata['model_type'])
        self.assertTrue(metadata['model_version'])

    def test_version_mismatch_fails_before_unpickling(self):
        load_model_artifact.cache_clear()
        with patch('app.ai.inference.model_loader.sklearn.__version__', '0.0.0'), \
             patch('app.ai.inference.model_loader.joblib.load') as joblib_load:
            with self.assertRaisesRegex(ModelNotReadyError, 'đồng bộ dependency'):
                load_model_artifact()
            joblib_load.assert_not_called()


if __name__ == '__main__':
    unittest.main()
