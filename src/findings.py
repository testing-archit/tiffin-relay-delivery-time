"""Fill findings.yaml from the reports the pipeline wrote. Keeps every key.

Run:  python -m src.findings
"""
import json

import yaml

from src.config import load_config
from src.issues import detect_all

ISSUE_KEYS = {
    "leaking_column": ["column"],
    "unit_mixup": ["column", "group_value", "factor"],
    "sentinel_value": ["column", "value", "count"],
    "duplicate_rows": ["count"],
    "stuck_sensor": ["column", "start_date", "end_date"],
    "target_typos": ["count"],
    "spelling_variants": ["column", "true_levels"],
}


def main() -> None:
    cfg = load_config()
    path = cfg["paths"]["findings"]
    findings = yaml.safe_load(path.read_text())
    issues = detect_all(cfg)
    metrics = json.loads(cfg["paths"]["metrics_report"].read_text())
    mon = json.loads(cfg["paths"]["monitoring_report"].read_text())

    for kind, keys in ISSUE_KEYS.items():
        found = issues[kind]
        findings["data_issues"][kind] = {"present": bool(found["present"]),
                                         **{k: (found.get(k) if found["present"] else None) for k in keys}}

    findings["tracking"] = {
        "experiment_name": cfg["mlflow"]["experiment_name"],
        "best_run_id": metrics["v1_run_id"],
        "registered_model_name": cfg["mlflow"]["registered_model_name"],
        "champion_version": int(mon["champion_version"]),
    }
    findings["monitoring"] = {
        "psi": {c: mon["psi"][c] for c in cfg["numeric_features"]},
        "most_drifted_feature": mon["most_drifted_feature"],
        "mae_by_group": {g: mon["mae_by_group"][g] for g in ["Central", "Suburb", "Old City"]},
        "worst_served_group": mon["worst_served_group"],
        "mae_v1_on_check": mon["mae_v1_on_check"],
        "mae_v2_on_check": mon["mae_v2_on_check"],
        "decision": mon["decision"],
    }
    header = "\n".join(line for line in path.read_text().splitlines()[:3] if line.startswith("#"))
    path.write_text(header + "\n\n" + yaml.safe_dump(findings, sort_keys=False, allow_unicode=True))
    print(path.read_text())


if __name__ == "__main__":
    main()
