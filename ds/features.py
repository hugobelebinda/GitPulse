"""Feature engineering for topic activity forecasts."""

from __future__ import annotations

import pandas as pd

FEATURE_COLUMNS = [
    "stars_lag_1",
    "stars_lag_7",
    "stars_roll7",
    "stars_roll28",
    "wow_growth",
    "pushes_lag_1",
    "pull_requests_lag_1",
    "issues_lag_1",
    "dow",
]


def load_facts_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["day"] = pd.to_datetime(frame["day"]).dt.normalize()
    return frame.sort_values(["topic", "day"]).reset_index(drop=True)


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    parts: list[pd.DataFrame] = []
    for topic, group in frame.groupby("topic", sort=False):
        item = group.copy()
        item["stars_lag_1"] = item["stars"].shift(1)
        item["stars_lag_7"] = item["stars"].shift(7)
        item["stars_roll7"] = item["stars"].shift(1).rolling(7, min_periods=3).mean()
        item["stars_roll28"] = item["stars"].shift(1).rolling(28, min_periods=7).mean()
        item["wow_growth"] = (item["stars_roll7"] / item["stars_roll7"].shift(7)) - 1.0
        item["pushes_lag_1"] = item["pushes"].shift(1)
        item["pull_requests_lag_1"] = item["pull_requests"].shift(1)
        item["issues_lag_1"] = item["issues"].shift(1)
        item["dow"] = item["day"].dt.dayofweek
        item["topic"] = topic
        parts.append(item)
    out = pd.concat(parts, ignore_index=True)
    return out.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)


def rising_table(frame: pd.DataFrame, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    featured = add_features(frame)
    if featured.empty:
        return featured
    if as_of is None:
        as_of = featured["day"].max()
    latest = featured[featured["day"] == as_of].copy()
    latest = latest.sort_values("wow_growth", ascending=False).reset_index(drop=True)
    latest["rank"] = latest.index + 1
    latest["momentum"] = latest["wow_growth"].fillna(0.0)
    return latest[["day", "topic", "wow_growth", "momentum", "rank", "stars_roll7"]]
