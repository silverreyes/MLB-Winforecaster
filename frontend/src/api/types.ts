export interface PredictionResponse {
  game_date: string;
  home_team: string;
  away_team: string;
  prediction_version: 'pre_lineup' | 'post_lineup' | 'confirmation';
  prediction_status: 'confirmed' | 'pending_sp' | 'tbd';
  lr_prob: number | null;
  rf_prob: number | null;
  xgb_prob: number | null;
  ensemble_prob: number | null;
  feature_set: string;
  home_sp: string | null;
  away_sp: string | null;
  sp_uncertainty: boolean;
  sp_may_have_changed: boolean;
  kalshi_yes_price: number | null;
  edge_signal: 'BUY_YES' | 'BUY_NO' | 'NO_EDGE' | null;
  edge_magnitude: number | null;
  created_at: string;
  game_time: string | null;
}

export interface TodayResponse {
  predictions: PredictionResponse[];
  latest_prediction_at: string | null;
  generated_at: string;
}

export interface LatestTimestampResponse {
  timestamp: string | null;
}

/** Grouped game: combines pre_lineup and post_lineup for same matchup */
export interface GameGroup {
  home_team: string;
  away_team: string;
  game_date: string;
  game_time: string | null;
  pre_lineup: PredictionResponse | null;
  post_lineup: PredictionResponse | null;
}

// Phase 13: /games/{date} response types

export type GameStatus = 'PRE_GAME' | 'LIVE' | 'FINAL' | 'POSTPONED';

export interface PredictionGroup {
  pre_lineup: PredictionResponse | null;
  post_lineup: PredictionResponse | null;
}

export interface GameResponse {
  game_id: number;
  home_team: string;
  away_team: string;
  game_time: string | null;
  game_status: GameStatus;
  prediction: PredictionGroup | null;
}

export interface GamesDateResponse {
  games: GameResponse[];
  generated_at: string;
}
