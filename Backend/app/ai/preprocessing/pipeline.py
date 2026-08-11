from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

CATEGORICAL_FEATURES = ['sport_type']
NUMERIC_FEATURES = [
    'day_of_week', 'start_hour', 'price', 'month', 'is_weekend',
    'previous_booking_count', 'field_capacity',
]


def build_preprocessor() -> ColumnTransformer:
    categorical = Pipeline([
        ('imputer', SimpleImputer(strategy='most_frequent')),
        ('encoder', OneHotEncoder(handle_unknown='ignore')),
    ])
    numeric = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler()),
    ])
    return ColumnTransformer([
        ('categorical', categorical, CATEGORICAL_FEATURES),
        ('numeric', numeric, NUMERIC_FEATURES),
    ])


def build_pipeline(estimator) -> Pipeline:
    return Pipeline([('preprocessor', build_preprocessor()), ('classifier', estimator)])
