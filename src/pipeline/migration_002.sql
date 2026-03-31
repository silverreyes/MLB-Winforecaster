-- Phase 16 Migration: game_logs table for historical game cache
-- Idempotent: safe to re-run on every container startup

CREATE TABLE IF NOT EXISTS game_logs (
    game_id         VARCHAR PRIMARY KEY,
    game_date       DATE NOT NULL,
    home_team       VARCHAR NOT NULL,
    away_team       VARCHAR NOT NULL,
    home_score      INTEGER NOT NULL,
    away_score      INTEGER NOT NULL,
    winning_team    VARCHAR NOT NULL,
    losing_team     VARCHAR NOT NULL,
    home_probable_pitcher VARCHAR,
    away_probable_pitcher VARCHAR,
    season          INTEGER NOT NULL
);

-- Performance indexes for FeatureBuilder queries
CREATE INDEX IF NOT EXISTS idx_game_logs_date ON game_logs (game_date);
CREATE INDEX IF NOT EXISTS idx_game_logs_season ON game_logs (season);
CREATE INDEX IF NOT EXISTS idx_game_logs_home_team ON game_logs (home_team, season);
CREATE INDEX IF NOT EXISTS idx_game_logs_away_team ON game_logs (away_team, season);
