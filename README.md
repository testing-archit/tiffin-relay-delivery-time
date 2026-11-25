# Tiffin Relay Delivery Time (Bhopal)

SCSE3040 MLOps mini project — predicting `delivery_min` (regression, MAE) for the Bhopal Dabba Relay Union.

- **Group:** G220
- **Problem:** MP098
- **Faculty:** Upasna Joshi — Batch 12

## Members

| Enrolment no. | Name |
|---|---|
| S24CSEU1089 | Anany Sharma |
| S24CSEU1049 | Archit Gupta |
| S24CSEU1229 | Akshat Rastogi |
| S24CSEU1057 | Doni Sehrawat |

**Live:** <https://tiffin.architgupta.tech> (app) and <https://grafana.tiffin.architgupta.tech> (dashboards)

## Architecture

```
            browser ──HTTPS──> Caddy ─┬─> web (Next.js UI) ──/api/*──> api (FastAPI + model) ──> Gemini
                                     └─> Grafana <── Prometheus <──scrape /metrics── api
GitHub push ─> CI (lint, tests, builds) ─> CD (images to GHCR) ─> Watchtower on the VM pulls & restarts
DVC pipeline: issues → clean → train (MLflow) → monitor (PSI, v2, promotion) → predict → findings
```

## Layout

| Path | What it is |
|---|---|
| `config.yaml` | every path, column list, MLflow name and monitoring setting |
| `src/issues.py` | detects the 7 data problems in `train.csv` → `reports/data_issues.json` |
| `src/data.py` | cleans train/later → `data/processed/` |
| `src/model.py`, `src/train.py` | candidate models, 5-fold CV, v1 logged + registered in MLflow as `@champion` |
| `src/monitor.py` | PSI drift, v1 MAE per `route_zone`, v2 retrain, 15% promotion rule |
| `src/predict.py` | `@champion` → `predictions/holdout_predictions.csv` + `models/model.joblib` for the API |
| `src/findings.py` | writes `findings.yaml` from the reports |
| `app/main.py` | FastAPI service (`/health`, `/predict`, rules enforced with pydantic `Field`) |
| `Dockerfile`, `k8s/` | image `mp098-api:1.0`; Deployment `mp098-api` (3 replicas), Service `mp098-svc` 80→8000 |
| `app/explain.py` | splits a prediction into minutes added/saved per input (`POST /explain`) |
| `app/ai.py` | Gemini: note → form fields, plain-language explanations, chatbot that calls the model as a tool |
| `app/observability.py` | JSON logs with request ids, Prometheus `/metrics` |
| `web/` | Next.js 16 UI: live estimates, relay route, breakdown, Gemini assistant with Hindi/Hinglish/English voice |
| `tests/` | API, rules, metrics, cleaning and PSI tests (`pytest -q`) |
| `dvc.yaml` | the whole pipeline; raw CSVs are DVC-tracked |
| `deploy/` | Docker Compose stack: Caddy (HTTPS), API, web, Prometheus + alerts, Grafana dashboard, MLflow, Watchtower |
| `.github/workflows/` | `ci.yml` lint/test/build everything; `cd.yml` publish images to GHCR and verify the live rollout |

## Run it

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
dvc repro                       # issues → clean → train → monitor → predict → findings
pytest -q
mlflow ui --backend-store-uri sqlite:///mlflow.db   # browse runs / registry

docker build -t mp098-api:1.0 .
kubectl apply -f k8s/
kubectl port-forward svc/mp098-svc 8080:80
curl localhost:8080/health
```

Web UI against a local API:

```bash
uvicorn app.main:app --port 8000          # needs GEMINI_API_KEY in .env for the AI features
cd web && npm install && npm run dev      # http://localhost:3000
```

Whole stack (what runs on the server):

```bash
cp deploy/.env.example deploy/.env        # fill in GEMINI_API_KEY and GRAFANA_PASSWORD
docker compose -f deploy/docker-compose.yml --profile tracking --profile cd up -d
```

Re-running the `train`/`monitor` stages on an existing `mlflow.db` adds new
registry versions; delete `mlflow.db` and `mlruns/` first for a clean v1/v2 run.

## Results

**Data issues in `train.csv`**: 35 duplicate rows; `temp_c = -999` sentinel in
48 rows; `wait_at_station_min` for `Suburb` recorded in seconds (×60); 11 targets
typed 10× too big. No leaking column (every column is in the holdout file and
the request schema), no stuck sensor (the only long run is `handovers = 5`, a
5-level count, and model residuals show those values are real), no spelling variants.

**v1**: Ridge regression, CV MAE ≈ 2.2 min (beat linear, random forest, gradient boosting).

**Monitoring**: `distance_km` drifted hugely (PSI 3.65; later routes are ~2× longer).
v1 serves `Central` worst (MAE 25.3 vs 3–4 elsewhere). v2 (train + first 70% of
later) cut check-set MAE from 7.61 to 5.34 (−30%) → **promoted**, champion = v2.

## AI features (Gemini)

- **Describe the batch** in English, हिन्दी or Hinglish, typed or spoken. Gemini fills the form (`POST /ai/parse`).
- **Explain in plain words**: Gemini explains the estimate from the model's own per-input minutes, so it can't invent numbers (`POST /ai/explain`).
- **Dispatch assistant**: a chatbot that calls the delivery model as a tool and replies in the user's language. Its voice mode listens, speaks the reply and listens again (browser speech engines; `POST /ai/chat`).
- The key lives only in `.env` / `deploy/.env` / a Kubernetes Secret. Without it the AI endpoints return 503 and everything else keeps working.

## Observability

- **Logging:** one JSON line per event on stdout: every request (path, status, ms), every prediction (inputs + output), every Gemini call, every rejected request. All lines of one request share a `request_id` (sent back as `X-Request-ID`).
- **Prometheus** scrapes `/metrics`: traffic, latency, 5xx rate, predictions per zone/transport, predicted minutes, live input distributions, 422s per field, Gemini calls and latency.
- **Alerts** (`deploy/prometheus/alerts.yml`): API down, 5xx > 5 %, p95 latency > 500 ms, distance drift (live median > 15 km vs 10.5 km in training), Gemini failing.
- **Grafana** dashboard *MP098 Tiffin relay* is provisioned from `deploy/grafana/dashboards/mp098.json` (regenerate with `python deploy/grafana/build_dashboard.py`).
- **MLflow** holds the experiment (`mp098-tiffin-delivery`), the candidate runs, v1/v2 and the `@champion` alias. On the server it runs on 127.0.0.1:5000; open it with `ssh -p 2200 -L 5000:localhost:5000 <vm>`.

## CI/CD

| Workflow | When | What |
|---|---|---|
| `CI` | every push to `main`/`dev`, every PR | ruff + pytest; web lint, typecheck and build; compose, Prometheus (promtool) and Kubernetes (kubeconform) validation; both Docker images build |
| `CD` | after `CI` passes on `main` | builds `mp098-api` and `mp098-web` for linux/amd64, pushes `latest`, the commit sha (and `1.0` for the API) to GHCR; waits until the live `/api/health` reports the new commit, then smoke-tests `/predict` and the 35 km rule |

Deployment is pull-based: Watchtower on the VM checks GHCR every minute and restarts a service when its image changes, so GitHub holds no server credentials. Set the repository variable `DEPLOY_URL` to turn on the live verification.
