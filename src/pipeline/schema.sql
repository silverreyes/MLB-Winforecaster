-- Phase 7: Live Pipeline Database Schema
-- Run via: apply_schema() in db.py

-- Custom ENUM types
CREATE TYPE prediction_version AS ENUM ('pre_lineup', 'post_lineup', 'confirmation');
CREATE TYPE prediction_status AS ENUM ('confirmed', 'pending_sp', 'tbd');

-- Games table: one row per MLB game
CREATE TABLE IF NOT EXISTS games (
    id             SERIAL PRIMARY KEY,
    game_date      DATE NOT NULL,
    home_team      VARCHAR(3) NOT NULL,
    away_team      VARCHAR(3) NOT NULL,
    game_id        INTEGER,
    home_score     INTEGER,
    away_score     INTEGER,
    home_win       BOOLEAN,
    status         VARCHAR(20),
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (game_date, home_team, away_team)
);

-- Predictions table: one row per game per prediction version
CREATE TABLE IF NOT EXISTS predictions (
    id                    SERIAL PRIMARY KEY,
    game_date             DATE NOT NULL,
    home_team             VARCHAR(3) NOT NULL,
    away_team             VARCHAR(3) NOT NULL,
    prediction_version    prediction_version NOT NULL,
    prediction_status     prediction_status NOT NULL DEFAULT 'tbd',

    -- Model probabilities (calibrated P(home_win))
    lr_prob               REAL,
    rf_prob               REAL,
    xgb_prob              REAL,

    -- Feature set used
    feature_set           VARCHAR(20) NOT NULL,

    -- SP metadata
    home_sp               VARCHAR(100),
    away_sp               VARCHAR(100),
    sp_uncertainty         BOOLEAN DEFAULT FALSE,
    sp_may_have_changed    BOOLEAN DEFAULT FALSE,

    -- Kalshi data
    kalshi_yes_price       REAL,
    edge_signal            VARCHAR(10),

    -- Lifecycle
    is_latest              BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMPTZ DEFAULT NOW(),

    -- DB-level invariant: post_lineup requires confirmed starters (PIPE-07)
    CONSTRAINT chk_post_lineup_confirmed CHECK (
        prediction_version != 'post_lineup'
        OR prediction_status = 'confirmed'
    ),
    -- Prevent exact duplicates on re-run (PIPE-07 uniqueness)
    CONSTRAINT uq_prediction UNIQUE (game_date, home_team, away_team, prediction_version, is_latest)
);

-- Pipeline runs audit table
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                SERIAL PRIMARY KEY,
    prediction_version prediction_version NOT NULL,
    run_date          DATE NOT NULL,
    run_started_at    TIMESTAMPTZ NOT NULL,
    run_finished_at   TIMESTAMPTZ,
    status            VARCHAR(20) NOT NULL DEFAULT 'running',
    games_processed   INTEGER DEFAULT 0,
    error_message     TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions (game_date);
CREATE INDEX IF NOT EXISTS idx_predictions_latest ON predictions (game_date, is_latest) WHERE is_latest = TRUE;
CREATE INDEX IF NOT EXISTS idx_predictions_version ON predictions (game_date, prediction_version);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_date ON pipeline_runs (run_date, prediction_version);
