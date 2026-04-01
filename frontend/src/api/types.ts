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
  actual_winner: string | null;
  prediction_correct: boolean | null;
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

// Phase 14: view mode for date navigation
export type ViewMode = 'live' | 'historical' | 'tomorrow' | 'future';

export interface PredictionGroup {
  pre_lineup: PredictionResponse | null;
  post_lineup: PredictionResponse | null;
}

export interface LiveScoreData {
  away_score: number;
  home_score: number;
  inning: number;
  inning_half: 'top' | 'bottom';
  outs: number;
  balls: number;
  strikes: number;
  runner_on_1b: boolean;
  runner_on_2b: boolean;
  runner_on_3b: boolean;
  current_batter: string | null;
  batter_avg: string | null;
  batter_ops: string | null;
  on_deck_batter: string | null;
}

export interface GameResponse {
  game_id: number;
  home_team: string;
  away_team: string;
  game_time: string | null;
  game_status: GameStatus;
  prediction: PredictionGroup | null;
  prediction_label: 'PRELIMINARY' | null;
  home_probable_pitcher: string | null;
  away_probable_pitcher: string | null;
  live_score: LiveScoreData | null;
  home_final_score: number | null;
  away_final_score: number | null;
  actual_winner: string | null;
  prediction_correct: boolean | null;
}

export interface GamesDateResponse {
  games: GameResponse[];
  generated_at: string;
  view_mode: ViewMode;
}

// Phase 18: /history response types

export interface HistoryRow {
  game_date: string;
  home_team: string;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  lr_prob: number | null;
  rf_prob: number | null;
  xgb_prob: number | null;
  ensemble_prob: number | null;
  prediction_correct: boolean;
}

export interface ModelAccuracy {
  correct: number;
  total: number;
  pct: number;
}

export interface PnLSummary {
  total: number;
  wins: number;
  losses: number;
}

export interface HistoryResponse {
  games: HistoryRow[];
  accuracy: Record<string, ModelAccuracy>;
  pnl: PnLSummary;
  start_date: string;
  end_date: string;
}
