"""Train v1 on cleaned train.csv, track every candidate in MLflow,
register the best one and make it @champion.

Run:  python -m src.train
"""
import json

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow import MlflowClient
from mlflow.models import infer_signature
from sklearn.model_selection import KFold, cross_val_score

from src.config import features, load_config
from src.model import CANDIDATES, build_pipeline

# Types inside our pipelines that skops must be told are safe to load.
SKOPS_TRUSTED = ["numpy.dtype", "sklearn.tree._tree.Tree"]


def setup_mlflow(cfg: dict) -> MlflowClient:
    mlflow.set_tracking_uri(cfg["mlflow"]["tracking_uri"])
    mlflow.set_experiment(cfg["mlflow"]["experiment_name"])
    return MlflowClient()


def log_and_register(pipe, X, run_name_tag: str, cfg: dict, client: MlflowClient) -> str:
    "Log the fitted pipeline in the active run and register it; return the version."
    info = mlflow.sklearn.log_model(
        pipe, name="model", signature=infer_signature(X, pipe.predict(X)),
        input_example=X.head(3), registered_model_name=cfg["mlflow"]["registered_model_name"],
        skops_trusted_types=SKOPS_TRUSTED,
    )
    version = str(info.registered_model_version)
    client.set_model_version_tag(cfg["mlflow"]["registered_model_name"], version, "role", run_name_tag)
    return version


def main() -> None:
    cfg = load_config()
    client = setup_mlflow(cfg)
    train = pd.read_csv(cfg["paths"]["clean_train"])
    X, y = train[features(cfg)], train[cfg["target"]]
    cv = KFold(n_splits=5, shuffle=True, random_state=cfg["seed"])

    results = {}
    for name in CANDIDATES:
        with mlflow.start_run(run_name=f"candidate-{name}"):
            pipe = build_pipeline(name, cfg)
            mae = -cross_val_score(pipe, X, y, cv=cv, scoring="neg_mean_absolute_error").mean()
            mlflow.log_params({"model": name, "cv_folds": 5, "train_rows": len(X)})
            mlflow.log_metric("cv_mae", mae)
            results[name] = mae
            print(f"{name:20s} CV MAE = {mae:.3f}")

    best = min(results, key=results.get)
    with mlflow.start_run(run_name="v1") as run:
        pipe = build_pipeline(best, cfg).fit(X, y)
        mlflow.log_params({"model": best, "train_rows": len(X), "data": "cleaned train.csv"})
        mlflow.log_metric("cv_mae", results[best])
        mlflow.set_tag("model_stage", "v1")
        version = log_and_register(pipe, X, "v1", cfg, client)
        run_id = run.info.run_id

    name = cfg["mlflow"]["registered_model_name"]
    client.set_registered_model_alias(name, cfg["mlflow"]["champion_alias"], version)
    print(f"best={best} run_id={run_id} registered {name} v{version} as @champion")

    out = cfg["paths"]["metrics_report"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"cv_mae": results, "best_model": best, "v1_run_id": run_id,
                               "v1_version": version}, indent=2))


if __name__ == "__main__":
    main()
