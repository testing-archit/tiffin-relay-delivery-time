"Builds deploy/grafana/dashboards/mp098.json. Run: python deploy/grafana/build_dashboard.py"
import json
from pathlib import Path

DS = {"type": "prometheus", "uid": "prometheus"}
panels, y = [], 0


def target(expr, legend=""):
    return {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": chr(65 + len(legend) % 26)}


def stat(title, expr, unit="short", x=0, w=4, thresholds=None, decimals=None):
    p = {"type": "stat", "title": title, "datasource": DS, "gridPos": {"x": x, "y": y, "w": w, "h": 4},
         "targets": [target(expr)],
         "fieldConfig": {"defaults": {"unit": unit, "decimals": decimals,
                                      "thresholds": {"mode": "absolute", "steps": thresholds or [{"color": "green", "value": None}]}},
                         "overrides": []},
         "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background", "graphMode": "area"}}
    panels.append(p)


def series(title, targets, unit="short", x=0, w=12, h=8, desc=""):
    panels.append({"type": "timeseries", "title": title, "description": desc, "datasource": DS,
                   "gridPos": {"x": x, "y": y, "w": w, "h": h},
                   "targets": [dict(target(e, legend), refId=chr(65 + i)) for i, (e, legend) in enumerate(targets)],
                   "fieldConfig": {"defaults": {"unit": unit, "custom": {"lineWidth": 2, "fillOpacity": 8}}, "overrides": []},
                   "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}})


def row(title):
    global y
    panels.append({"type": "row", "title": title, "collapsed": False, "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []})
    y += 1


row("Service health")
stat("API up", 'up{job="mp098-api"}', x=0, thresholds=[{"color": "red", "value": None}, {"color": "green", "value": 1}])
stat("Requests / s", "sum(rate(http_requests_total[5m]))", "reqps", x=4, decimals=2)
stat("5xx error rate", 'sum(rate(http_requests_total{status=~"5.."}[5m])) / clamp_min(sum(rate(http_requests_total[5m])), 1e-9)',
     "percentunit", x=8, thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 0.01}, {"color": "red", "value": 0.05}])
stat("p95 /predict latency", 'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{path=~"/predict|/explain"}[5m])))',
     "s", x=12, thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 0.25}, {"color": "red", "value": 0.5}])
stat("Predictions (24 h)", "sum(increase(predictions_total[24h]))", x=16, decimals=0)
stat("Model version", "max by (version) (model_info)", x=20)
panels[-1]["options"]["textMode"] = "name"
panels[-1]["targets"][0]["legendFormat"] = "v{{version}}"
y += 4
series("Requests by path and status", [('sum by (path, status) (rate(http_requests_total[5m]))', "{{path}} {{status}}")], "reqps", x=0)
series("Latency", [('histogram_quantile(0.5, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))', "p50"),
                   ('histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))', "p95"),
                   ('histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))', "p99")], "s", x=12)
y += 8

row("Model behaviour and drift")
series("Predictions by route zone", [("sum by (route_zone) (rate(predictions_total[5m]))", "{{route_zone}}")], "reqps", x=0, w=8)
series("Predicted delivery minutes", [("histogram_quantile(0.5, sum by (le) (rate(predicted_minutes_bucket[15m])))", "median"),
                                      ("histogram_quantile(0.9, sum by (le) (rate(predicted_minutes_bucket[15m])))", "p90")], "m", x=8, w=8)
series("Live median distance vs training", [
    ('histogram_quantile(0.5, sum by (le) (rate(prediction_input_bucket{feature="distance_km"}[30m])))', "live median km"),
    ("vector(10.5)", "training median km (Jan to Jun)")], "lengthkm", x=16, w=8,
    desc="later.csv drifted to about twice the training distance (PSI 3.6). A live median far above 10.5 km means it is time to retrain.")
y += 8
series("Live median of every input", [
    ('histogram_quantile(0.5, sum by (le, feature) (rate(prediction_input_bucket[30m])))', "{{feature}}")], x=0, w=12)
series("Requests rejected by the client rules (422)", [("sum by (field) (increase(validation_errors_total[15m]))", "{{field}}")], x=12, w=12,
       desc="distance_km > 35 and temp_c < 5 are rejected by the request schema.")
y += 8

row("Gemini assistant")
series("Gemini calls", [("sum by (kind, outcome) (rate(ai_requests_total[5m]))", "{{kind}} {{outcome}}")], "reqps", x=0)
series("Gemini latency p95", [("histogram_quantile(0.95, sum by (le, kind) (rate(ai_request_duration_seconds_bucket[5m])))", "{{kind}}")], "s", x=12)
y += 8

dashboard = {"uid": "mp098", "title": "MP098 Tiffin relay: service, model and AI", "tags": ["mp098", "mlops"],
             "timezone": "browser", "refresh": "30s", "time": {"from": "now-6h", "to": "now"},
             "schemaVersion": 41, "version": 1, "panels": panels}
out = Path(__file__).parent / "dashboards" / "mp098.json"
out.write_text(json.dumps(dashboard, indent=2))
print(f"wrote {out} with {len(panels)} panels")
