"""Train scikit-learn forecasts and write rising ranks + results.json.

Default protocol: ~6 months of daily facts, time-ordered split into
first ~5 months (train) and last 30 days (test). Test predictions are
scored against the real held-out stars and compared to a seasonal-naive
baseline (same weekday last week).

Model quality upgrades:
- train on log1p(stars) to stabilize sparse topics
- fit a global model plus per-topic models when volume is high enough
- hybrid selector: per topic, keep whichever of {model, naive} wins on holdout MAE
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sqlalchemy import text

from ds.features import FEATURE_COLUMNS, add_features, load_facts_frame, rising_table
from gitpulse.config import get_settings
from gitpulse.db import connect, replace_forecasts, sync_topics
from gitpulse.topics import TOPIC_BY_SLUG

# Prefer a dedicated model when the topic has enough average daily stars.
PER_TOPIC_MIN_MEAN_STARS = 8.0
PER_TOPIC_MIN_TRAIN_ROWS = 60


def _read_facts() -> pd.DataFrame:
    with connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT day, topic, stars, pushes, pull_requests, issues
                FROM daily_facts
                ORDER BY topic, day
                """
            )
        ).mappings().all()
    return load_facts_frame([dict(row) for row in rows])


def _naive_predict(history: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """Seasonal naive: actual stars from the same weekday one week earlier."""
    preds = []
    for _, row in test.iterrows():
        hist = history[
            (history["topic"] == row["topic"])
            & (history["day"] == row["day"] - pd.Timedelta(days=7))
        ]
        if hist.empty:
            hist = history[
                (history["topic"] == row["topic"]) & (history["day"] < row["day"])
            ].tail(1)
        preds.append(float(hist["stars"].iloc[0]) if len(hist) else 0.0)
    return np.asarray(preds, dtype=float)


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    mae = float(np.mean(np.abs(y_true - y_pred)))
    denom = np.maximum(np.abs(y_true), 1.0)
    mape = float(np.mean(np.abs((y_true - y_pred) / denom)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    return {"mae": round(mae, 4), "mape": round(mape, 4), "rmse": round(rmse, 4)}


def _fit_gbr(frame: pd.DataFrame) -> GradientBoostingRegressor:
    model = GradientBoostingRegressor(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=3,
        subsample=0.9,
        random_state=42,
    )
    y = np.log1p(frame["stars"].to_numpy(dtype=float))
    model.fit(frame[FEATURE_COLUMNS], y)
    return model


def _predict_stars(model: GradientBoostingRegressor, frame: pd.DataFrame) -> np.ndarray:
    log_pred = model.predict(frame[FEATURE_COLUMNS])
    return np.maximum(np.expm1(log_pred), 0.0)


def _per_topic_bundle(
    train: pd.DataFrame,
    test: pd.DataFrame,
    global_model: GradientBoostingRegressor,
    naive_pred: np.ndarray,
) -> tuple[np.ndarray, dict[str, GradientBoostingRegressor], list[dict]]:
    """Score global + optional per-topic models; build hybrid predictions."""
    model_pred = np.zeros(len(test), dtype=float)
    topic_models: dict[str, GradientBoostingRegressor] = {}
    rows: list[dict] = []

    for topic, test_group in test.groupby("topic", sort=True):
        idx = test_group.index.to_numpy()
        train_group = train[train["topic"] == topic]
        use_local = (
            len(train_group) >= PER_TOPIC_MIN_TRAIN_ROWS
            and float(train_group["stars"].mean()) >= PER_TOPIC_MIN_MEAN_STARS
        )
        if use_local:
            local = _fit_gbr(train_group)
            topic_models[topic] = local
            pred = _predict_stars(local, test_group)
            model_kind = "per_topic"
        else:
            pred = _predict_stars(global_model, test_group)
            model_kind = "global"

        model_pred[idx] = pred
        y = test_group["stars"].to_numpy(dtype=float)
        naive = naive_pred[idx]
        model_scores = _metrics(y, pred)
        naive_scores = _metrics(y, naive)
        winner = "model" if model_scores["mae"] <= naive_scores["mae"] else "naive"
        rows.append(
            {
                "topic": topic,
                "label": TOPIC_BY_SLUG[topic].label if topic in TOPIC_BY_SLUG else topic,
                "rows": int(len(test_group)),
                "model_kind": model_kind,
                "model": model_scores,
                "baseline": naive_scores,
                "winner": winner,
            }
        )
    return model_pred, topic_models, rows


def _comparison_frame(
    test: pd.DataFrame,
    model_pred: np.ndarray,
    naive_pred: np.ndarray,
    hybrid_pred: np.ndarray | None = None,
) -> pd.DataFrame:
    frame = test[["day", "topic", "stars"]].copy()
    frame = frame.rename(columns={"stars": "actual"})
    frame["model_pred"] = model_pred
    frame["naive_pred"] = naive_pred
    if hybrid_pred is None:
        hybrid_pred = model_pred
    frame["hybrid_pred"] = hybrid_pred
    frame["model_error"] = frame["model_pred"] - frame["actual"]
    frame["naive_error"] = frame["naive_pred"] - frame["actual"]
    frame["hybrid_error"] = frame["hybrid_pred"] - frame["actual"]
    frame["day"] = frame["day"].dt.strftime("%Y-%m-%d")
    return frame.sort_values(["topic", "day"]).reset_index(drop=True)


def train_and_evaluate(holdout_days: int = 30) -> dict:
    """Fit on all history before the holdout window; score on the last month of real data."""
    sync_topics()
    raw = _read_facts()
    if raw.empty:
        raise SystemExit("daily_facts is empty; run ETL backfill first")

    data_start = raw["day"].min()
    data_end = raw["day"].max()
    span_days = int((data_end - data_start).days) + 1
    topic_counts = raw.groupby("topic")["day"].nunique()
    min_days = holdout_days + 28
    usable = topic_counts[topic_counts >= min_days].index.tolist()
    if not usable:
        raise SystemExit(
            f"need at least {min_days} days per topic; got max={int(topic_counts.max())}"
        )
    raw = raw[raw["topic"].isin(usable)].copy()
    featured = add_features(raw).reset_index(drop=True)

    cutoff = featured["day"].max() - pd.Timedelta(days=holdout_days)
    train = featured[featured["day"] <= cutoff].copy().reset_index(drop=True)
    test = featured[featured["day"] > cutoff].copy().reset_index(drop=True)
    if train.empty or test.empty:
        raise SystemExit("not enough history for the requested holdout window")

    print(
        f"split: train {train['day'].min().date()}→{train['day'].max().date()} "
        f"({len(train)} rows) | test {test['day'].min().date()}→{test['day'].max().date()} "
        f"({len(test)} rows, holdout={holdout_days}d)"
    )

    global_model = _fit_gbr(train)
    naive_pred = _naive_predict(raw, test[["day", "topic", "stars"]])
    model_pred, topic_models, per_topic = _per_topic_bundle(
        train, test, global_model, naive_pred
    )
    winners = {row["topic"]: row["winner"] for row in per_topic}
    hybrid_pred = np.asarray(
        [
            model_pred[i] if winners[topic] == "model" else naive_pred[i]
            for i, topic in enumerate(test["topic"].tolist())
        ],
        dtype=float,
    )

    y = test["stars"].to_numpy(dtype=float)
    model_scores = _metrics(y, model_pred)
    naive_scores = _metrics(y, naive_pred)
    hybrid_scores = _metrics(y, hybrid_pred)
    winner = min(
        ("model", model_scores["mae"]),
        ("naive", naive_scores["mae"]),
        ("hybrid", hybrid_scores["mae"]),
        key=lambda item: item[1],
    )[0]
    comparison = _comparison_frame(test, model_pred, naive_pred, hybrid_pred)
    importance = sorted(
        (
            {"feature": name, "importance": round(float(score), 6)}
            for name, score in zip(FEATURE_COLUMNS, global_model.feature_importances_, strict=True)
        ),
        key=lambda item: item["importance"],
        reverse=True,
    )

    settings = get_settings()
    model_dir = Path(settings.data_dir) / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "stars_gbr.joblib"
    comparison_path = Path(settings.data_dir) / "test_predictions.csv"
    comparison.to_csv(comparison_path, index=False)
    joblib.dump(
        {
            "global_model": global_model,
            "topic_models": topic_models,
            "features": FEATURE_COLUMNS,
            "target": "log1p_stars",
            "holdout_days": holdout_days,
            "topics": usable,
            "winners": winners,
            "train_end": cutoff.date().isoformat(),
            "test_start": test["day"].min().date().isoformat(),
            "test_end": test["day"].max().date().isoformat(),
        },
        model_path,
    )

    as_of = featured["day"].max()
    rising = rising_table(raw, as_of=as_of)
    with connect() as conn:
        conn.execute(text("DELETE FROM rising_scores"))
        if not rising.empty:
            conn.execute(
                text(
                    """
                    INSERT INTO rising_scores (as_of_day, topic, momentum, wow_growth, rank)
                    VALUES (:as_of_day, :topic, :momentum, :wow_growth, :rank)
                    """
                ),
                [
                    {
                        "as_of_day": row.day.date().isoformat(),
                        "topic": row.topic,
                        "momentum": float(row.momentum),
                        "wow_growth": float(row.wow_growth) if pd.notna(row.wow_growth) else 0.0,
                        "rank": int(row.rank),
                    }
                    for row in rising.itertuples()
                ],
            )

    forecast_rows: list[dict] = []
    latest = featured.sort_values("day").groupby("topic").tail(1)
    for row in latest.itertuples():
        x = pd.DataFrame([{col: getattr(row, col) for col in FEATURE_COLUMNS}])
        topic = row.topic
        if winners.get(topic) == "naive":
            hist = raw[(raw["topic"] == topic) & (raw["day"] == row.day - pd.Timedelta(days=7))]
            yhat = float(hist["stars"].iloc[0]) if len(hist) else float(row.stars)
            model_name = "seasonal_naive_lag7"
        else:
            model = topic_models.get(topic, global_model)
            yhat = float(_predict_stars(model, x)[0])
            model_name = "GradientBoostingRegressor_log1p"
        topic_row = next((item for item in per_topic if item["topic"] == topic), None)
        forecast_rows.append(
            {
                "topic": topic,
                "as_of_day": row.day.date().isoformat(),
                "horizon_days": 1,
                "yhat": yhat,
                "model_name": model_name,
                "mae": topic_row["model"]["mae"] if topic_row and winners.get(topic) == "model" else (
                    topic_row["baseline"]["mae"] if topic_row else hybrid_scores["mae"]
                ),
                "mape": topic_row["model"]["mape"] if topic_row and winners.get(topic) == "model" else (
                    topic_row["baseline"]["mape"] if topic_row else hybrid_scores["mape"]
                ),
            }
        )
    replace_forecasts(forecast_rows)

    model_wins = sum(1 for row in per_topic if row["winner"] == "model")
    results = {
        "as_of": as_of.date().isoformat(),
        "data_window": {
            "start": data_start.date().isoformat(),
            "end": data_end.date().isoformat(),
            "span_days": span_days,
        },
        "split": {
            "scheme": "time_ordered_5mo_train_1mo_test",
            "holdout_days": holdout_days,
            "train_start": train["day"].min().date().isoformat(),
            "train_end": train["day"].max().date().isoformat(),
            "test_start": test["day"].min().date().isoformat(),
            "test_end": test["day"].max().date().isoformat(),
            "note": "Model never sees test-month labels while fitting; scores compare predictions to real held-out stars.",
        },
        "topics_trained": usable,
        "topic_count": len(usable),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "baseline": {"name": "seasonal_naive_lag7", **naive_scores},
        "model": {
            "name": "GradientBoostingRegressor_log1p",
            "per_topic_models": sorted(topic_models),
            **model_scores,
        },
        "hybrid": {
            "name": "per_topic_best_of_model_or_naive",
            **hybrid_scores,
        },
        "winner": winner,
        "topics_model_wins": model_wins,
        "topics_naive_wins": len(per_topic) - model_wins,
        "feature_importance": importance,
        "per_topic": per_topic,
        "test_preview": comparison.head(20).to_dict(orient="records"),
        "test_predictions_path": str(comparison_path),
        "rising": [
            {
                "rank": int(row.rank),
                "topic": row.topic,
                "label": TOPIC_BY_SLUG[row.topic].label if row.topic in TOPIC_BY_SLUG else row.topic,
                "wow_growth": round(float(row.wow_growth), 4) if pd.notna(row.wow_growth) else None,
                "stars_roll7": round(float(row.stars_roll7), 2) if pd.notna(row.stars_roll7) else None,
            }
            for row in rising.itertuples()
        ],
        "model_path": str(model_path),
    }
    results_path = Path(settings.results_path)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Train GitPulse star forecasts")
    parser.add_argument(
        "--holdout-days",
        type=int,
        default=30,
        help="Last N days held out as the test month (default: 30 ≈ 1 month)",
    )
    args = parser.parse_args()
    train_and_evaluate(holdout_days=args.holdout_days)


if __name__ == "__main__":
    main()
