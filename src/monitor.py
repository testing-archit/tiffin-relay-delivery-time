"""Two months later: drift (PSI), per-group MAE, retrain v2, promotion rule.

Run:  python -m src.monitor
"""
import json

import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

from src.config import features, load_config
from src.model import build_pipeline
from src.train import log_and_register, setup_mlflow


def psi(reference: pd.Series, current: pd.Series, bins: int = 10, eps: float = 1e-4) -> float:
    """Population Stability Index with `bins` quantile bins taken from the reference.

    The outer edges are opened to +/- infinity so new values outside the old
    range still land in the first/last bin. Missing values are ignored.
    """
    ref, cur = reference.dropna().to_numpy(), current.dropna().to_numpy()
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    ref_pct = np.histogram(ref, edges)[0] / len(ref)
    cur_pct = np.histogram(cur, edges)[0] / len(cur)
    ref_pct, cur_pct = np.clip(ref_pct, eps, None), np.clip(cur_pct, eps, None)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def main() -> None:
    cfg = load_config()
    client = setup_mlflow(cfg)
    mcfg, target, feats = cfg["monitoring"], cfg["target"], features(cfg)
    name = cfg["mlflow"]["registered_model_name"]

    train = pd.read_csv(cfg["paths"]["clean_train"])
    later = pd.read_csv(cfg["paths"]["clean_later"]).sort_values(
        [cfg["date_column"], cfg["id_column"]]).reset_index(drop=True)

    # 1. drift
    psi_values = {c: round(psi(train[c], later[c], mcfg["psi_bins"]), 4) for c in cfg["numeric_features"]}
    most_drifted = max(psi_values, key=psi_values.get)

    # 2. v1 per group on later.csv
    metrics = json.loads(cfg["paths"]["metrics_report"].read_text())
    v1_version = metrics["v1_version"]
    v1 = mlflow.sklearn.load_model(f"models:/{name}/{v1_version}")
    later_pred = v1.predict(later[feats])
    mae_by_group = {
        g: round(float(mean_absolute_error(later.loc[idx, target], later_pred[idx])), 4)
        for g, idx in later.groupby(cfg["group_column"]).groups.items()
    }
    worst_group = max(mae_by_group, key=mae_by_group.get)

    # 3. retrain v2 on train + first 70% of later, compare on last 30%
    cut = int(round(len(later) * (1 - mcfg["check_fraction"])))
    later_fit, check = later.iloc[:cut], later.iloc[cut:]
    v2_data = pd.concat([train, later_fit], ignore_index=True)
    model_name = metrics["best_model"]
    v2 = build_pipeline(model_name, cfg).fit(v2_data[feats], v2_data[target])

    mae_v1 = float(mean_absolute_error(check[target], v1.predict(check[feats])))
    mae_v2 = float(mean_absolute_error(check[target], v2.predict(check[feats])))
    improvement = (mae_v1 - mae_v2) / mae_v1
    decision = "promote" if improvement >= mcfg["promotion_improvement"] else "keep"

    with mlflow.start_run(run_name="v2") as run:
        mlflow.log_params({"model": model_name, "train_rows": len(v2_data),
                           "data": "cleaned train.csv + first 70% later.csv"})
        mlflow.log_metrics({"mae_v1_on_check": mae_v1, "mae_v2_on_check": mae_v2,
                            "improvement": improvement,
                            **{f"psi_{k}": v for k, v in psi_values.items()}})
        mlflow.set_tag("model_stage", "v2")
        mlflow.set_tag("decision", decision)
        v2_version = log_and_register(v2, v2_data[feats], "v2", cfg, client)
        v2_run_id = run.info.run_id

    # 4. promotion rule
    if decision == "promote":
        client.set_registered_model_alias(name, cfg["mlflow"]["champion_alias"], v2_version)
    champion = client.get_model_version_by_alias(name, cfg["mlflow"]["champion_alias"]).version

    report = {
        "psi": psi_values, "most_drifted_feature": most_drifted,
        "mae_by_group": mae_by_group, "worst_served_group": worst_group,
        "check_rows": len(check), "check_start_date": str(check[cfg["date_column"]].iloc[0]),
        "mae_v1_on_check": round(mae_v1, 4), "mae_v2_on_check": round(mae_v2, 4),
        "improvement": round(improvement, 4), "decision": decision,
        "v2_run_id": v2_run_id, "v2_version": v2_version, "champion_version": str(champion),
    }
    cfg["paths"]["monitoring_report"].write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
