"""Predict the holdout with the @champion model and export it for the API.

Run:  python -m src.predict
"""
import joblib
import mlflow
import pandas as pd
from mlflow import MlflowClient

from src.config import features, load_config


def main() -> None:
    cfg = load_config()
    mlflow.set_tracking_uri(cfg["mlflow"]["tracking_uri"])
    m = cfg["mlflow"]
    uri = f"models:/{m['registered_model_name']}@{m['champion_alias']}"
    model = mlflow.sklearn.load_model(uri)
    version = MlflowClient().get_model_version_by_alias(m["registered_model_name"], m["champion_alias"]).version

    holdout = pd.read_csv(cfg["paths"]["holdout"])
    out = pd.DataFrame({"record_id": holdout[cfg["id_column"]],
                        "prediction": model.predict(holdout[features(cfg)]).round(2)})
    cfg["paths"]["predictions"].parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(cfg["paths"]["predictions"], index=False)

    # plain joblib copy of the champion so the container needs no MLflow server
    cfg["paths"]["model_export"].parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "version": str(version), "features": features(cfg)},
                cfg["paths"]["model_export"])
    print(f"champion v{version}: wrote {len(out)} predictions and {cfg['paths']['model_export'].name}")


if __name__ == "__main__":
    main()
