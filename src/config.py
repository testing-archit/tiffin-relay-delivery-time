"Load config.yaml once and expose project paths."
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path | str = ROOT / "config.yaml") -> dict:
    with open(path) as fh:
        cfg = yaml.safe_load(fh)
    cfg["paths"] = {k: ROOT / v for k, v in cfg["paths"].items()}
    return cfg


def features(cfg: dict) -> list[str]:
    return cfg["numeric_features"] + cfg["categorical_features"]
