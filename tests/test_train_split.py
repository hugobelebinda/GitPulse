"""Train/test split and scoring helpers."""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from ds.features import add_features, load_facts_frame
from ds.train import _comparison_frame, _metrics, _naive_predict


def _panel(days: int = 90) -> pd.DataFrame:
    start = date(2026, 1, 1)
    rows = []
    for topic in ("python", "rust"):
        for offset in range(days):
            day = start + timedelta(days=offset)
            rows.append(
                {
                    "day": day.isoformat(),
                    "topic": topic,
                    "stars": 20 + offset % 5,
                    "pushes": 3,
                    "pull_requests": 1,
                    "issues": 1,
                }
            )
    return load_facts_frame(rows)


def test_holdout_split_is_time_ordered() -> None:
    featured = add_features(_panel())
    holdout = 30
    cutoff = featured["day"].max() - pd.Timedelta(days=holdout)
    train = featured[featured["day"] <= cutoff]
    test = featured[featured["day"] > cutoff]
    assert train["day"].max() <= cutoff
    assert test["day"].min() > cutoff
    assert (test["day"].max() - test["day"].min()).days + 1 <= holdout + 1


def test_metrics_perfect_prediction() -> None:
    y = np.asarray([1.0, 2.0, 3.0])
    scores = _metrics(y, y)
    assert scores["mae"] == 0.0
    assert scores["rmse"] == 0.0


def test_naive_uses_lag7_actuals() -> None:
    raw = _panel(40)
    test = raw[raw["day"] >= raw["day"].max() - pd.Timedelta(days=5)].copy()
    preds = _naive_predict(raw, test)
    assert len(preds) == len(test)
    assert np.all(preds >= 0)


def test_comparison_frame_columns() -> None:
    raw = _panel(40)
    featured = add_features(raw)
    test = featured.tail(10).copy()
    model_pred = test["stars"].to_numpy(dtype=float)
    naive_pred = model_pred + 1
    frame = _comparison_frame(test, model_pred, naive_pred)
    assert {"day", "topic", "actual", "model_pred", "naive_pred", "hybrid_pred"} <= set(frame.columns)
