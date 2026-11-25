"How many minutes each input adds or saves compared with a typical batch."
import numpy as np
import pandas as pd

LABELS = {
    "distance_km": "Distance", "tiffins": "Tiffins", "handovers": "Handovers",
    "wait_at_station_min": "Station wait", "rider_age": "Rider age", "temp_c": "Temperature",
    "transport": "Transport", "route_zone": "Route zone",
}


def contributions(model, row: pd.DataFrame) -> list[dict] | None:
    """For a linear pipeline (pre -> linear model) split the prediction into parts.

    Numeric inputs are standardised, so coef * value is the change from an
    average batch. For a category the part is its coefficient minus the
    average coefficient of that column. Returns None for non-linear models.
    """
    pre, est = model.named_steps.get("pre"), model.named_steps.get("model")
    if pre is None or not hasattr(est, "coef_"):
        return None
    x = pre.transform(row)
    x = np.asarray(x.todense() if hasattr(x, "todense") else x)[0]
    names = pre.get_feature_names_out()
    coef = np.ravel(est.coef_)
    parts: dict[str, float] = {}
    for col in LABELS:
        idx = [i for i, n in enumerate(names) if n == f"num__{col}"]
        if idx:
            parts[col] = float(coef[idx[0]] * x[idx[0]])
            continue
        idx = [i for i, n in enumerate(names) if n.startswith(f"cat__{col}_")]
        if idx:
            active = [i for i in idx if x[i] == 1]
            parts[col] = float(coef[active[0]] - coef[idx].mean()) if active else 0.0
    return sorted(({"feature": k, "label": LABELS[k], "minutes": round(v, 1)} for k, v in parts.items()),
                  key=lambda p: -abs(p["minutes"]))
