import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.data import clean
from src.issues import detect_all
from src.monitor import psi

CFG = load_config()


def tiny():
    return pd.DataFrame({
        "record_id": ["a", "b", "b", "c", "d", "e"],
        "date": ["2026-01-01"] * 6,
        "distance_km": [5.0, 6.0, 6.0, 7.0, 8.0, 9.0],
        "tiffins": [10] * 6, "handovers": [2] * 6,
        "wait_at_station_min": [10.0, 600.0, 600.0, 12.0, 8.0, 9.0],
        "rider_age": [30] * 6, "temp_c": [25.0, -999.0, -999.0, 30.0, 20.0, 22.0],
        "transport": ["scooter"] * 6,
        "route_zone": ["Central", "Suburb", "Suburb", "Old City", "Central", "Old City"],
        "delivery_min": [40.0, 45.0, 45.0, 500.0, 50.0, 42.0],
    })


ISSUES = {
    "leaking_column": {"present": False}, "stuck_sensor": {"present": False},
    "spelling_variants": {"present": False},
    "unit_mixup": {"present": True, "column": "wait_at_station_min", "group_value": "Suburb", "factor": 60},
    "sentinel_value": {"present": True, "column": "temp_c", "value": -999, "count": 2},
    "target_typos": {"present": True, "count": 1}, "duplicate_rows": {"present": True, "count": 1},
}


def test_clean_fixes_everything():
    out = clean(tiny(), ISSUES, CFG)
    assert len(out) == 5
    assert out["temp_c"].isna().sum() == 1
    assert out.loc[out.route_zone == "Suburb", "wait_at_station_min"].iloc[0] == 10.0
    assert out["delivery_min"].max() == 50.0


@pytest.mark.skipif(not CFG["paths"]["train"].exists(), reason="train.csv is DVC-tracked")
def test_detect_on_real_train():
    issues = detect_all(CFG)
    assert issues["duplicate_rows"]["count"] == 35
    assert issues["unit_mixup"]["factor"] == 60


def test_psi_zero_for_same_data():
    s = pd.Series(np.random.default_rng(0).normal(size=500))
    assert psi(s, s) < 1e-9
    assert psi(s, s + 3) > 1
