"Model pipeline factory shared by training, retraining and tests."
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

CANDIDATES = {
    "linear_regression": lambda seed: LinearRegression(),
    "ridge": lambda seed: Ridge(alpha=1.0),
    "random_forest": lambda seed: RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=seed, n_jobs=-1),
    "gradient_boosting": lambda seed: GradientBoostingRegressor(n_estimators=300, learning_rate=0.05, max_depth=3, random_state=seed),
}


def build_pipeline(name: str, cfg: dict) -> Pipeline:
    pre = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")),
                          ("scale", StandardScaler())]), cfg["numeric_features"]),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cfg["categorical_features"]),
    ])
    return Pipeline([("pre", pre), ("model", CANDIDATES[name](cfg["seed"]))])
