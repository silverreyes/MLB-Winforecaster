-- Phase 13 Migration: game_id + reconciliation columns
-- Idempotent: safe to re-run on every container startup

-- SCHM-01: Add game_id column to predictions
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS game_id INTEGER;

-- SCHM-01: Rebuild unique constraint to include game_id
-- (prevents doubleheader row collisions for new inserts)
ALTER TABLE predictions DROP CONSTRAINT IF EXISTS uq_prediction;
ALTER TABLE predictions ADD CONSTRAINT uq_prediction
    UNIQUE (game_date, home_team, away_team, prediction_version, is_latest, game_id);

-- SCHM-02: Add reconciliation columns (nullable, no default)
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS actual_winner TEXT;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS prediction_correct BOOLEAN;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS reconciled_at TIMESTAMPTZ;

-- Performance index for game_id lookups (Phase 15/16)
CREATE INDEX IF NOT EXISTS idx_predictions_game_id ON predictions (game_id)
    WHERE game_id IS NOT NULL;
