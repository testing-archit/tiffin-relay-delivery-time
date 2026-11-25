"MP098 prediction service: tiffin relay delivery time in minutes."
import os
from enum import Enum
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from app.explain import contributions

MODEL_PATH = Path(os.getenv("MODEL_PATH", Path(__file__).resolve().parent.parent / "models" / "model.joblib"))
bundle = joblib.load(MODEL_PATH)
model, FEATURES = bundle["model"], bundle["features"]

app = FastAPI(title="MP098 Tiffin Relay Delivery Time",
              description="Predicts minutes from pick-up to the office desk for the Bhopal Dabba Relay Union.",
              version="1.0.0")


class Transport(str, Enum):
    bicycle = "bicycle"
    local_train = "local_train"
    scooter = "scooter"


class RouteZone(str, Enum):
    central = "Central"
    suburb = "Suburb"
    old_city = "Old City"


class Batch(BaseModel):
    "One tiffin batch at pick-up time."
    model_config = ConfigDict(extra="forbid")

    distance_km: float = Field(..., gt=0, le=35, description="Route length; above 35 km is impossible.", examples=[10.5])
    tiffins: int = Field(..., ge=1, examples=[35])
    handovers: int = Field(..., ge=0, examples=[3])
    wait_at_station_min: float = Field(..., ge=0, examples=[13.0])
    rider_age: int = Field(..., ge=14, le=90, examples=[40])
    temp_c: float = Field(..., ge=5, le=55, description="Noon temperature; below 5 is a typing mistake.", examples=[28.0])
    transport: Transport
    route_zone: RouteZone


class Prediction(BaseModel):
    delivery_min: float
    model_version: str


class Part(BaseModel):
    feature: str
    label: str
    minutes: float


class Explanation(Prediction):
    typical_min: float
    parts: list[Part]


@app.get("/health")
def health():
    return {"status": "ok", "model_version": bundle["version"]}


@app.post("/predict", response_model=Prediction)
def predict(batch: Batch):
    return Prediction(delivery_min=round(_predict_row(batch), 1), model_version=bundle["version"])


def _row(batch: Batch) -> pd.DataFrame:
    return pd.DataFrame([batch.model_dump(mode="json")])[FEATURES]


def _predict_row(batch: Batch) -> float:
    return float(model.predict(_row(batch))[0])


@app.post("/explain", response_model=Explanation)
def explain(batch: Batch):
    "The estimate plus how many minutes each input adds or saves versus a typical batch."
    minutes = _predict_row(batch)
    parts = contributions(model, _row(batch)) or []
    return Explanation(delivery_min=round(minutes, 1), model_version=bundle["version"],
                       typical_min=round(minutes - sum(p["minutes"] for p in parts), 1), parts=parts)
