"""Feature engineering tests."""

from datetime import date, timedelta

import pandas as pd

from ds.features import FEATURE_COLUMNS, add_features, load_facts_frame, rising_table


def _synthetic(days: int = 60, topic: str = "python") -> pd.DataFrame:
    start = date(2026, 1, 1)
    rows = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        rows.append(
            {
                "day": day.isoformat(),
                "topic": topic,
                "stars": 10 + (offset % 7),
                "pushes": 5,
                "pull_requests": 2,
                "issues": 1,
            }
        )
    return load_facts_frame(rows)


def test_add_features_has_required_columns() -> None:
    featured = add_features(_synthetic())
    assert not featured.empty
    for col in FEATURE_COLUMNS:
        assert col in featured.columns
    assert featured["stars_lag_1"].notna().all()


def test_rising_table_ranks() -> None:
    frame = pd.concat(
        [
            _synthetic(60, "python"),
            _synthetic(60, "rust").assign(stars=lambda df: df["stars"] * 2),
        ],
        ignore_index=True,
    )
    rising = rising_table(frame)
    assert list(rising["rank"]) == list(range(1, len(rising) + 1))
    assert rising.iloc[0]["wow_growth"] >= rising.iloc[-1]["wow_growth"]
