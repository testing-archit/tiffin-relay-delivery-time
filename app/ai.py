"""Gemini features for the dispatcher UI.

- parse_batch: free text (English / Hindi / Hinglish) -> form fields
- explain:     a short explanation of one estimate, grounded in model numbers
- chat:        a chatbot that calls our delivery model as a tool

The key is read from GEMINI_API_KEY (a .env file locally, a Kubernetes Secret
in the cluster). Without it every AI endpoint answers 503 and the rest of the
service keeps working.
"""
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # the container gets the key from the environment
    pass

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")  # ~3x faster than 3.5-flash, same answers here

LANGUAGE_RULE = (
    "Reply in the language and script the user writes or speaks in: Hindi in Devanagari, "
    "Hinglish (Hindi in Roman letters mixed with English), or English. If the user asks for "
    "a language, use that one. Keep numbers as digits."
)

DOMAIN = (
    "You help dispatchers of the Bhopal Dabba Relay Union, who carry home-cooked tiffins from "
    "homes to offices by relay. A batch is described by: distance_km (route length, at most 35), "
    "tiffins (count), handovers (times the batch changes hands), wait_at_station_min, rider_age, "
    "temp_c (noon temperature, at least 5), transport (bicycle, local_train or scooter) and "
    "route_zone (Central, Suburb or Old City)."
)

_client = None


def enabled() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


class ParsedBatch(BaseModel):
    distance_km: float | None = None
    tiffins: int | None = None
    handovers: int | None = None
    wait_at_station_min: float | None = None
    rider_age: int | None = None
    temp_c: float | None = None
    transport: Literal["bicycle", "local_train", "scooter"] | None = None
    route_zone: Literal["Central", "Suburb", "Old City"] | None = None


def parse_batch(text: str) -> dict:
    from google.genai import types
    prompt = (
        f"{DOMAIN}\nExtract the batch fields from the dispatcher's note below. The note may be "
        "in English, Hindi or Hinglish. Words like dabba/tiffin mean tiffins; train/local means "
        "local_train; cycle means bicycle; scooty/bike means scooter; purana shehar means Old City. "
        "Convert seconds or hours of waiting to minutes. Leave out anything the note does not say.\n\n"
        f"Note: {text}"
    )
    r = client().models.generate_content(
        model=MODEL, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json",
                                           response_schema=ParsedBatch),
    )
    parsed = r.parsed or ParsedBatch()
    return {k: v for k, v in parsed.model_dump().items() if v is not None}


def explain(batch: dict, minutes: float, contributions: list[dict], language: str) -> str:
    prompt = (
        f"{DOMAIN}\nOur model estimates this batch takes {minutes:.0f} minutes. Batch: "
        f"{json.dumps(batch)}.\nMinutes each input adds (+) or saves (-) compared with a typical "
        f"batch: {json.dumps(contributions)}.\n"
        "In at most 3 short sentences for a dispatcher: say what drives this time most, and give "
        "one practical suggestion (for example fewer handovers or another transport) only if the "
        "numbers support it. Do not invent numbers. Plain text, no markdown.\n"
        f"Write it in {language}."
    )
    return client().models.generate_content(model=MODEL, contents=prompt).text.strip()


def chat(history: list[dict], predict: Callable[[dict], dict], form: dict | None) -> dict:
    """history: [{"role": "user"|"model", "text": str}, ...]. Returns reply + any estimate made."""
    from google.genai import types
    estimates: list[dict] = []

    def predict_delivery(distance_km: float, tiffins: int, handovers: int,
                         wait_at_station_min: float, rider_age: int, temp_c: float,
                         transport: str, route_zone: str) -> dict:
        """Estimate minutes from pick-up to the office desk for one tiffin batch.

        Args:
            distance_km: route length in km (more than 0, at most 35)
            tiffins: number of tiffins in the batch
            handovers: times the batch changes hands
            wait_at_station_min: minutes spent waiting at the station
            rider_age: age of the main runner in years
            temp_c: noon temperature in deg C (at least 5)
            transport: one of bicycle, local_train, scooter
            route_zone: one of Central, Suburb, Old City
        """
        batch = dict(distance_km=distance_km, tiffins=tiffins, handovers=handovers,
                     wait_at_station_min=wait_at_station_min, rider_age=rider_age,
                     temp_c=temp_c, transport=transport, route_zone=route_zone)
        result = predict(batch)
        if "delivery_min" in result:
            estimates.append({"batch": batch, **result})
        return result

    system = (
        f"{DOMAIN}\nYou are the union's dispatch assistant. {LANGUAGE_RULE}\n"
        "Whenever the user wants a delivery time, call predict_delivery; never guess a time "
        "yourself. If a field is missing, use the value from the current form below, and say "
        "which values you assumed. If the tool returns an error, explain the rule that was broken. "
        "Answers are read aloud too, so keep them short and conversational, without markdown "
        "or bullet lists.\n"
        f"Current form: {json.dumps(form) if form else 'empty'}"
    )
    turns = [m for m in history if m.get("text")]
    past = [types.Content(role=m["role"], parts=[types.Part(text=m["text"])]) for m in turns[:-1]]
    session = client().chats.create(
        model=MODEL, history=past,
        config=types.GenerateContentConfig(system_instruction=system, tools=[predict_delivery]),
    )
    r = session.send_message(turns[-1]["text"])
    return {"reply": (r.text or "").strip(), "estimate": estimates[-1] if estimates else None}
