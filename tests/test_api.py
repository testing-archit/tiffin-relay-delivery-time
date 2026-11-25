import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
GOOD = {"distance_km": 12.0, "tiffins": 30, "handovers": 3, "wait_at_station_min": 10.0,
        "rider_age": 35, "temp_c": 28.0, "transport": "scooter", "route_zone": "Old City"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_predict_ok():
    r = client.post("/predict", json=GOOD)
    assert r.status_code == 200
    assert 0 < r.json()["delivery_min"] < 300


@pytest.mark.parametrize("field,value", [("distance_km", 35.1), ("temp_c", 4.9),
                                         ("transport", "rocket"), ("route_zone", "Mars")])
def test_rules_give_422(field, value):
    assert client.post("/predict", json={**GOOD, field: value}).status_code == 422


def test_boundaries_allowed():
    assert client.post("/predict", json={**GOOD, "distance_km": 35, "temp_c": 5}).status_code == 200


def test_missing_field_422():
    body = dict(GOOD); body.pop("rider_age")
    assert client.post("/predict", json=body).status_code == 422


def test_explain_parts_add_up():
    r = client.post("/explain", json=GOOD).json()
    assert {p["feature"] for p in r["parts"]} == set(GOOD)
    total = r["typical_min"] + sum(p["minutes"] for p in r["parts"])
    assert abs(total - r["delivery_min"]) < 0.5
