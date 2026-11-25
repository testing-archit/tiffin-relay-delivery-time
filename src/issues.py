"""Detect the seven kinds of data problem in train.csv.

Every number written to findings.yaml under `data_issues` comes from here.
Run:  python -m src.issues
"""
import json
import re

import numpy as np
import pandas as pd

from src.config import load_config

SENTINEL_CANDIDATES = [-9999, -999, -99, -1, 999, 9999, 99999]
UNIT_FACTORS = [10, 12, 24, 60, 100, 1000, 1.609, 3.6]


# 1. Leaking column -----------------------------------------------------------
def find_leaking_column(train: pd.DataFrame, holdout: pd.DataFrame, cfg: dict) -> dict:
    """A column is leaking if it is not known at prediction time.

    Test 1: it is in train but missing from the holdout features (filled in
    after the event). Test 2: it is so close to the target (|r| > 0.97) that
    it must be computed from it.
    """
    target, skip = cfg["target"], {cfg["id_column"], cfg["date_column"]}
    missing = [c for c in train.columns if c not in holdout.columns and c != target]
    if missing:
        return {"present": True, "column": missing[0], "evidence": "not in holdout"}
    clean = train[train[target] < train[target].quantile(0.95)]
    for col in train.select_dtypes("number").columns:
        if col in skip or col == target:
            continue
        r = clean[col].corr(clean[target])
        if abs(r) > 0.97:
            return {"present": True, "column": col, "evidence": f"corr={r:.3f}"}
    return {"present": False, "column": None}


# 2. Unit mix-up --------------------------------------------------------------
def find_unit_mixup(train: pd.DataFrame, cfg: dict) -> dict:
    """One group's values of one column are a constant factor away from the rest."""
    group = cfg["group_column"]
    best = None
    for col in cfg["numeric_features"]:
        values = train[col].where(~train[col].isin(SENTINEL_CANDIDATES))
        for g in train[group].unique():
            inside = values[train[group] == g].median()
            outside = values[train[group] != g].median()
            if not outside or np.isnan(inside) or outside <= 0:
                continue
            ratio = inside / outside
            if ratio < 3:  # only a big jump counts
                continue
            factor = min(UNIT_FACTORS, key=lambda f: abs(np.log(ratio / f)))
            if abs(np.log(ratio / factor)) < 0.25 and (best is None or ratio > best["ratio"]):
                best = {"present": True, "column": col, "group_value": g,
                        "factor": factor, "ratio": round(float(ratio), 2)}
    return best or {"present": False, "column": None, "group_value": None, "factor": None}


# 3. Sentinel value -----------------------------------------------------------
def find_sentinel(train: pd.DataFrame, cfg: dict) -> dict:
    """A special number typed instead of a blank (e.g. -999)."""
    best = None
    for col in cfg["numeric_features"] + [cfg["target"]]:
        for value in SENTINEL_CANDIDATES:
            count = int((train[col] == value).sum())
            rest = train.loc[train[col] != value, col]
            # it must repeat and sit far outside the normal range of the column
            outside = value < rest.min() - 3 * rest.std() or value > rest.max() + 3 * rest.std()
            if count >= 3 and outside and (best is None or count > best["count"]):
                best = {"present": True, "column": col, "value": value, "count": count}
    return best or {"present": False, "column": None, "value": None, "count": None}


# 4. Duplicate rows -----------------------------------------------------------
def find_duplicates(train: pd.DataFrame) -> dict:
    extra = int(train.duplicated(keep="first").sum())
    return {"present": extra > 0, "count": extra if extra else None}


# 5. Stuck sensor -------------------------------------------------------------
def find_stuck_sensor(train: pd.DataFrame, cfg: dict, min_run: int = 5) -> dict:
    """The same reading repeated over consecutive records on several days.

    Only continuous measurements can be stuck sensors, so small counts like
    `handovers` (5 possible values) are skipped: a run there is normal.
    Sentinel values are not readings, so they are ignored too.
    """
    data = train.drop_duplicates().sort_values([cfg["date_column"], cfg["id_column"]])
    best = None
    for col in cfg["numeric_features"]:
        if data[col].nunique() < 50:
            continue
        values = data[col].to_numpy()
        dates = data[cfg["date_column"]].to_numpy()
        start = 0
        for i in range(1, len(values) + 1):
            if i == len(values) or values[i] != values[start]:
                run = i - start
                if (run >= min_run and values[start] not in SENTINEL_CANDIDATES
                        and dates[start] != dates[i - 1]
                        and (best is None or run > best["run_length"])):
                    best = {"present": True, "column": col,
                            "start_date": str(dates[start]), "end_date": str(dates[i - 1]),
                            "value": float(values[start]), "run_length": run}
                start = i
    return best or {"present": False, "column": None, "start_date": None, "end_date": None}


# 6. Target typos (10x too big) -----------------------------------------------
def target_typo_mask(train: pd.DataFrame, cfg: dict) -> pd.Series:
    """Targets that are far above the normal range but normal once divided by 10."""
    y = train[cfg["target"]]
    q1, q3 = y.quantile([0.25, 0.75])
    upper = q3 + 5 * (q3 - q1)
    normal = y[y <= upper]
    return (y > upper) & ((y / 10).between(normal.min(), normal.max()))


def find_target_typos(train: pd.DataFrame, cfg: dict) -> dict:
    count = int(target_typo_mask(train, cfg).sum())
    return {"present": count > 0, "count": count if count else None}


# 7. Spelling variants --------------------------------------------------------
def normalise_label(value: str) -> str:
    return re.sub(r"[\s_\-]+", "_", str(value).strip().lower())


def find_spelling_variants(train: pd.DataFrame, cfg: dict) -> dict:
    for col in cfg["categorical_features"]:
        raw = train[col].dropna().nunique()
        true = train[col].dropna().map(normalise_label).nunique()
        if true < raw:
            return {"present": True, "column": col, "true_levels": int(true), "raw_levels": int(raw)}
    return {"present": False, "column": None, "true_levels": None}


def detect_all(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    train = pd.read_csv(cfg["paths"]["train"])
    holdout = pd.read_csv(cfg["paths"]["holdout"])
    return {
        "leaking_column": find_leaking_column(train, holdout, cfg),
        "unit_mixup": find_unit_mixup(train, cfg),
        "sentinel_value": find_sentinel(train, cfg),
        "duplicate_rows": find_duplicates(train),
        "stuck_sensor": find_stuck_sensor(train, cfg),
        "target_typos": find_target_typos(train, cfg),
        "spelling_variants": find_spelling_variants(train, cfg),
    }


def main() -> None:
    cfg = load_config()
    report = detect_all(cfg)
    out = cfg["paths"]["issues_report"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
