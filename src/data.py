"""Clean train.csv / later.csv using what src.issues found.

Run:  python -m src.data
"""
import numpy as np
import pandas as pd

from src.config import load_config
from src.issues import detect_all, normalise_label, target_typo_mask


def clean(df: pd.DataFrame, issues: dict, cfg: dict, fix_target_typos: bool = True) -> pd.DataFrame:
    df = df.copy()
    target = cfg["target"]

    # duplicate rows: keep the first copy
    df = df.drop_duplicates(keep="first")

    # sentinel value -> missing (imputed inside the model pipeline)
    s = issues["sentinel_value"]
    if s["present"]:
        df.loc[df[s["column"]] == s["value"], s["column"]] = np.nan

    # unit mix-up: divide the affected group back into the right unit
    u = issues["unit_mixup"]
    if u["present"]:
        rows = df[cfg["group_column"]] == u["group_value"]
        df.loc[rows, u["column"]] = df.loc[rows, u["column"]] / u["factor"]

    # spelling variants: one spelling per category
    if issues["spelling_variants"]["present"]:
        for col in cfg["categorical_features"]:
            canon = df[col].map(normalise_label)
            first = df.groupby(canon)[col].agg(lambda s: s.mode().iat[0])
            df[col] = canon.map(first)

    # stuck sensor: the repeated readings are not real, treat as missing
    st = issues["stuck_sensor"]
    if st["present"]:
        d = df[cfg["date_column"]]
        rows = d.between(st["start_date"], st["end_date"]) & (df[st["column"]] == st["value"])
        df.loc[rows, st["column"]] = np.nan

    # target typed 10x too big
    if fix_target_typos and target in df and issues["target_typos"]["present"]:
        rows = target_typo_mask(df, cfg)
        df.loc[rows, target] = df.loc[rows, target] / 10

    # leaking column: never a feature
    if issues["leaking_column"]["present"]:
        df = df.drop(columns=[issues["leaking_column"]["column"]])

    return df.sort_values([cfg["date_column"], cfg["id_column"]]).reset_index(drop=True)


def main() -> None:
    cfg = load_config()
    issues = detect_all(cfg)
    p = cfg["paths"]
    p["clean_train"].parent.mkdir(parents=True, exist_ok=True)
    train = clean(pd.read_csv(p["train"]), issues, cfg)
    # later.csv is described as clean; we still drop duplicates/sort but do not
    # apply train-specific fixes (unit/target) unless the same problem shows up.
    later = pd.read_csv(p["later"]).drop_duplicates()
    later = later.sort_values([cfg["date_column"], cfg["id_column"]]).reset_index(drop=True)
    train.to_csv(p["clean_train"], index=False)
    later.to_csv(p["clean_later"], index=False)
    print(f"train: {len(train)} rows clean | later: {len(later)} rows")
    print(train.describe().T[["min", "50%", "max"]])


if __name__ == "__main__":
    main()
