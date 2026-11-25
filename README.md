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
| `tests/` | API + cleaning tests (`pytest -q`) |
| `dvc.yaml` | the whole pipeline; raw CSVs are DVC-tracked |

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
