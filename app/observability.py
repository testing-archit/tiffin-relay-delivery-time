"""Logging and Prometheus metrics for the prediction service.

Logs: one JSON object per line on stdout (Docker / Kubernetes collect stdout).
Every request gets an id (X-Request-ID, echoed back) that is on all its log lines.

Metrics (scraped from GET /metrics):
- http_requests_total, http_request_duration_seconds: traffic, errors, latency
- predictions_total{route_zone,transport}, predicted_minutes: what the model says
- prediction_input{feature}: live input distributions, for drift checks vs training
- validation_errors_total{field}: requests the client rules rejected (422)
- ai_requests_total{kind,outcome}, ai_request_duration_seconds: Gemini calls
- model_info{version}: which model version is serving
"""
import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

request_id: ContextVar[str] = ContextVar("request_id", default="-")

HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
HTTP_LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["path"],
                         buckets=(.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10, 30))
PREDICTIONS = Counter("predictions_total", "Predictions served", ["route_zone", "transport"])
PREDICTED_MIN = Histogram("predicted_minutes", "Predicted delivery minutes",
                          buckets=(20, 30, 40, 50, 60, 70, 80, 90, 100, 120, 150))
INPUTS = Histogram("prediction_input", "Input values seen in production", ["feature"],
                   buckets=(0, 1, 2, 3, 5, 8, 10, 12, 15, 20, 25, 30, 35, 40, 50, 60))
VALIDATION_ERRORS = Counter("validation_errors_total", "Fields rejected by the request schema", ["field"])
AI_REQUESTS = Counter("ai_requests_total", "Gemini calls", ["kind", "outcome"])
AI_LATENCY = Histogram("ai_request_duration_seconds", "Gemini call latency", ["kind"],
                       buckets=(.5, 1, 2, 3, 5, 8, 13, 20, 30))
MODEL_INFO = Gauge("model_info", "Model being served", ["version"])


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
               "level": record.levelname, "logger": record.name, "msg": record.getMessage(),
               "request_id": request_id.get()}
        out.update(getattr(record, "fields", {}))
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


def setup_logging(level: str = "INFO") -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("uvicorn.access", "httpx", "httpx2", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return logging.getLogger("mp098")


log = setup_logging()


def event(msg: str, **fields) -> None:
    log.info(msg, extra={"fields": fields})


def record_prediction(batch: dict, minutes: float) -> None:
    PREDICTIONS.labels(batch["route_zone"], batch["transport"]).inc()
    PREDICTED_MIN.observe(minutes)
    for k in ("distance_km", "tiffins", "handovers", "wait_at_station_min", "rider_age", "temp_c"):
        INPUTS.labels(k).observe(batch[k])
    event("prediction", inputs=batch, delivery_min=round(minutes, 2))


class ai_timer:
    "with ai_timer('chat'): ... counts and times one Gemini call."
    def __init__(self, kind: str):
        self.kind = kind

    def __enter__(self):
        self.t = time.perf_counter()

    def __exit__(self, exc_type, exc, tb):
        took = time.perf_counter() - self.t
        outcome = "error" if exc_type else "ok"
        AI_REQUESTS.labels(self.kind, outcome).inc()
        AI_LATENCY.labels(self.kind).observe(took)
        event("ai_call", kind=self.kind, outcome=outcome, seconds=round(took, 2),
              error=type(exc).__name__ if exc else None)
        return False


def instrument(app: FastAPI, model_version: str) -> None:
    MODEL_INFO.labels(model_version).set(1)

    @app.middleware("http")
    async def observe(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = request_id.set(rid)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["x-request-id"] = rid
            return response
        finally:
            took = time.perf_counter() - start
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")
            if path != "/metrics":
                HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
                HTTP_LATENCY.labels(path).observe(took)
                event("request", method=request.method, path=path, status=status, ms=round(took * 1000, 1))
            request_id.reset(token)

    @app.exception_handler(RequestValidationError)
    async def count_rejections(request: Request, exc: RequestValidationError):
        fields = sorted({str(e["loc"][-1]) for e in exc.errors()})
        for f in fields:
            VALIDATION_ERRORS.labels(f).inc()
        event("rejected", fields=fields)
        return await request_validation_exception_handler(request, exc)

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
