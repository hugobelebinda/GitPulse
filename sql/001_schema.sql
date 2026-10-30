CREATE TABLE IF NOT EXISTS topics (
    slug TEXT PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_facts (
    day DATE NOT NULL,
    topic TEXT NOT NULL REFERENCES topics (slug),
    stars INTEGER NOT NULL DEFAULT 0,
    pushes INTEGER NOT NULL DEFAULT 0,
    pull_requests INTEGER NOT NULL DEFAULT 0,
    issues INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'unknown',
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (day, topic)
);

CREATE INDEX IF NOT EXISTS daily_facts_topic_day_idx ON daily_facts (topic, day);

CREATE TABLE IF NOT EXISTS forecasts (
    id BIGSERIAL PRIMARY KEY,
    topic TEXT NOT NULL REFERENCES topics (slug),
    as_of_day DATE NOT NULL,
    horizon_days INTEGER NOT NULL,
    yhat DOUBLE PRECISION NOT NULL,
    model_name TEXT NOT NULL,
    mae DOUBLE PRECISION,
    mape DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS etl_runs (
    id BIGSERIAL PRIMARY KEY,
    job TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    rows_written INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rising_scores (
    as_of_day DATE NOT NULL,
    topic TEXT NOT NULL REFERENCES topics (slug),
    momentum DOUBLE PRECISION NOT NULL,
    wow_growth DOUBLE PRECISION NOT NULL,
    rank INTEGER NOT NULL,
    PRIMARY KEY (as_of_day, topic)
);
