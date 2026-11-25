"MP098 prediction service: tiffin relay delivery time in minutes."
import os
from enum import StrEnum
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app import ai
from app.explain import contributions
from app.observability import ai_timer, event, instrument, record_prediction

MODEL_PATH = Path(os.getenv("MODEL_PATH", Path(__file__).resolve().parent.parent / "models" / "model.joblib"))
bundle = joblib.load(MODEL_PATH)
model, FEATURES = bundle["model"], bundle["features"]

app = FastAPI(title="MP098 Tiffin Relay Delivery Time",
              description="Predicts minutes from pick-up to the office desk for the Bhopal Dabba Relay Union.",
              version="1.0.0")


instrument(app, bundle["version"])
event("model_loaded", version=bundle["version"], path=str(MODEL_PATH), ai_enabled=ai.enabled())


class Transport(StrEnum):
    bicycle = "bicycle"
    local_train = "local_train"
    scooter = "scooter"


class RouteZone(StrEnum):
    central = "Central"
    suburb = "Suburb"
    old_city = "Old City"


class Batch(BaseModel):
    "One tiffin batch at pick-up time."
    model_config = ConfigDict(extra="forbid")

    distance_km: float = Field(..., gt=0, le=35, examples=[10.5],
                               description="Route length; above 35 km is impossible.")
    tiffins: int = Field(..., ge=1, examples=[35])
    handovers: int = Field(..., ge=0, examples=[3])
    wait_at_station_min: float = Field(..., ge=0, examples=[13.0])
    rider_age: int = Field(..., ge=14, le=90, examples=[40])
    temp_c: float = Field(..., ge=5, le=55, examples=[28.0],
                          description="Noon temperature; below 5 is a typing mistake.")
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
    return {"status": "ok", "model_version": bundle["version"], "ai_enabled": ai.enabled(),
            "build": os.getenv("GIT_SHA", "dev")}


@app.post("/predict", response_model=Prediction)
def predict(batch: Batch):
    return Prediction(delivery_min=round(_predict_row(batch), 1), model_version=bundle["version"])


def _row(batch: Batch) -> pd.DataFrame:
    return pd.DataFrame([batch.model_dump(mode="json")])[FEATURES]


def _predict_row(batch: Batch) -> float:
    minutes = float(model.predict(_row(batch))[0])
    record_prediction(batch.model_dump(mode="json"), minutes)
    return minutes


@app.post("/explain", response_model=Explanation)
def explain(batch: Batch):
    "The estimate plus how many minutes each input adds or saves versus a typical batch."
    minutes = _predict_row(batch)
    parts = contributions(model, _row(batch)) or []
    return Explanation(delivery_min=round(minutes, 1), model_version=bundle["version"],
                       typical_min=round(minutes - sum(p["minutes"] for p in parts), 1), parts=parts)


# --- Gemini features --------------------------------------------------------

class ParseRequest(BaseModel):
    text: str = Field(..., min_length=2, max_length=2000)


class AIExplainRequest(BaseModel):
    batch: Batch
    language: str = Field("English", max_length=40)


class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|model)$")
    text: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatTurn] = Field(..., min_length=1, max_length=40)
    form: dict | None = None


def _ai_call(fn, *args):
    if not ai.enabled():
        raise HTTPException(503, "AI is off: set GEMINI_API_KEY to turn it on.")
    try:
        with ai_timer(fn.__name__):
            return fn(*args)
    except HTTPException:
        raise
    except Exception as exc:  # network, quota or model errors
        raise HTTPException(502, f"Gemini did not answer: {type(exc).__name__}") from exc


def _tool_predict(fields: dict) -> dict:
    "Used by the chatbot: same rules as POST /predict."
    try:
        batch = Batch(**fields)
    except ValidationError as exc:
        return {"error": "; ".join(f"{e['loc'][0]}: {e['msg']}" for e in exc.errors())}
    return {"delivery_min": round(_predict_row(batch), 1)}


@app.post("/ai/parse")
def ai_parse(req: ParseRequest):
    "Turn a note in English, Hindi or Hinglish into form fields."
    return {"fields": _ai_call(ai.parse_batch, req.text)}


@app.post("/ai/explain")
def ai_explain(req: AIExplainRequest):
    "A short explanation of one estimate in the chosen language."
    e = explain(req.batch)
    text = _ai_call(ai.explain, req.batch.model_dump(mode="json"), e.delivery_min,
                    [p.model_dump() for p in e.parts], req.language)
    return {"text": text, "delivery_min": e.delivery_min}


@app.post("/ai/chat")
def ai_chat(req: ChatRequest):
    "Chat with the dispatch assistant; it calls the delivery model for estimates."
    return _ai_call(ai.chat, [m.model_dump() for m in req.messages], _tool_predict, req.form)
