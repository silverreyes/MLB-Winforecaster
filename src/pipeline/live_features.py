"""Live feature construction for today's games.

Adapts the existing FeatureBuilder infrastructure for live (single-day) use.
Key constraint: MUST NOT duplicate feature logic from FeatureBuilder.
Uses FeatureBuilder internally by constructing it for the current season
with as_of_date set to today, then extracting features for today's games.

Design rationale: Rather than rewriting feature computation, we instantiate
FeatureBuilder for the current season (with as_of_date=today to exclude
today's games from rolling stats), build the feature matrix, and then match
today's games against it. For games not yet in the matrix (because they
haven't been played), we construct feature rows by reusing the FeatureBuilder's
lookup infrastructure.
"""
import logging
import math
from datetime import date, timedelta

import pandas as pd

from src.data.mlb_schedule import fetch_today_schedule
from src.data.team_mappings import normalize_team
from src.features.feature_builder import FeatureBuilder
from src.models.feature_sets import TEAM_ONLY_FEATURE_COLS, SP_ENHANCED_PRUNED_COLS

logger = logging.getLogger(__name__)


class LiveFeatureBuilder:
    """Construct features for today's MLB games using existing FeatureBuilder.

    Strategy:
    1. Instantiate FeatureBuilder for current season with as_of_date=today
    2. Call build() to get full feature matrix for the season up to yesterday
    3. For today's games, construct feature rows using the lookup dicts
       that FeatureBuilder populated internally

    This ensures feature values are computed identically to backtest.
    """

    def __init__(self):
        today = date.today()
        self.today_str = today.strftime("%Y-%m-%d")
        self.season = today.year
        # FeatureBuilder processes all games BEFORE today (temporal safety)
        # Include prior season so rolling stats are non-NaN at the start of a new season.
        # Without this, Opening Day predictions fail because the current-season feature
        # matrix has zero completed games and all rolling averages are NaN.
        self._builder = FeatureBuilder(
            seasons=[self.season - 1, self.season],
            as_of_date=self.today_str,
        )
        self._feature_matrix = None
        self._initialized = False

    def initialize(self):
        """Build the season-to-date feature matrix. Call once at pipeline start."""
        if self._initialized:
            return
        logger.info(f"Building season-to-date features for {self.season}...")
        self._feature_matrix = self._builder.build()
        self._initialized = True
        logger.info(f"Feature matrix built: {len(self._feature_matrix)} rows")

    def get_today_games(self) -> list[dict]:
        """Fetch today's games with normalized team names and probable pitchers.

        Returns:
            List of game dicts with keys: game_id, game_date, home_team,
            away_team, home_probable_pitcher, away_probable_pitcher, status.
        """
        raw_games = fetch_today_schedule()
        games = []
        for g in raw_games:
            games.append({
                "game_id": g.get("game_id"),
                "game_date": self.today_str,
                "home_team": normalize_team(g.get("home_name", "")),
                "away_team": normalize_team(g.get("away_name", "")),
                "home_probable_pitcher": g.get("home_probable_pitcher") or None,
                "away_probable_pitcher": g.get("away_probable_pitcher") or None,
                "status": g.get("status", ""),
            })
        return games

    def build_features_for_game(
        self,
        game: dict,
        feature_set: str = "team_only",
    ) -> dict | None:
        """Build a feature dict for a single today's game.

        Args:
            game: Game dict from get_today_games().
            feature_set: "team_only" or "sp_enhanced".

        Returns:
            Dict of feature_name -> value, or None if features cannot be built.
        """
        if not self._initialized:
            self.initialize()

        if feature_set == "team_only":
            target_cols = TEAM_ONLY_FEATURE_COLS
        else:
            target_cols = SP_ENHANCED_PRUNED_COLS

        # Strategy: Build a minimal 1-row DataFrame mimicking FeatureBuilder's
        # pipeline, then extract the feature dict.
        # We construct a row by running the game through the same pipeline
        # stages that FeatureBuilder.build() uses.

        game_row = pd.DataFrame([{
            "game_date": pd.Timestamp(game["game_date"]),
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "home_probable_pitcher": game.get("home_probable_pitcher"),
            "away_probable_pitcher": game.get("away_probable_pitcher"),
            "season": self.season,
            "game_id": game.get("game_id"),
            # Placeholder fields that FeatureBuilder expects
            "home_score": 0,
            "away_score": 0,
            "winning_team": "",
            "losing_team": "",
            "status": game.get("status", "Scheduled"),
        }])

        try:
            # KNOWN COUPLING RISK: calls private methods on FeatureBuilder.
            # Any refactor to FeatureBuilder internals (rename, signature change)
            # will break live_features.py silently at runtime, not at import time.
            # Acceptable for v1 pipeline; tracked in STATE.md as tech debt.
            # Run through FeatureBuilder's pipeline stages
            # Each stage adds its columns to the DataFrame
            if feature_set == "sp_enhanced":
                # Need both SP and team features
                if not game.get("home_probable_pitcher") or not game.get("away_probable_pitcher"):
                    logger.warning(
                        f"SP not confirmed for {game['home_team']} vs "
                        f"{game['away_team']}, cannot build sp_enhanced"
                    )
                    return None
                game_row = self._builder._add_sp_features(game_row)
            game_row = self._builder._add_offense_features(game_row)
            game_row = self._builder._add_rolling_features(game_row)
            game_row = self._builder._add_bullpen_features(game_row)
            game_row = self._builder._add_park_features(game_row)
            game_row = self._builder._add_advanced_features(game_row)

            # Extract only the feature columns we need
            available_cols = [c for c in target_cols if c in game_row.columns]
            if len(available_cols) < len(target_cols):
                missing = set(target_cols) - set(available_cols)
                logger.warning(
                    f"Missing features for {game['home_team']} vs "
                    f"{game['away_team']}: {missing}"
                )

            features = game_row[available_cols].iloc[0].to_dict()

            # Impute NaN differential features with 0.0 (neutral: no known advantage).
            # On Opening Day and early in the season, current-year Statcast and
            # pitcher game-log data don't exist yet, causing xwoba_diff,
            # sp_recent_era_diff, sp_recent_fip_diff (and others) to be NaN.
            # Imputing to 0.0 (no differential) is the safest neutral assumption
            # and keeps predict_game from skipping all models due to NaN features.
            for col, val in list(features.items()):
                if (val is None or (isinstance(val, float) and math.isnan(val))) and col.endswith("_diff"):
                    logger.debug("Imputing NaN feature %s=0.0 for %s vs %s", col, game["home_team"], game["away_team"])
                    features[col] = 0.0

            return features

        except Exception as e:
            logger.error(
                f"Feature build failed for {game['home_team']} vs "
                f"{game['away_team']}: {e}"
            )
            return None

    def sp_confirmed(self, game: dict) -> bool:
        """Check if both starting pitchers are confirmed (not None/TBD)."""
        home_sp = game.get("home_probable_pitcher")
        away_sp = game.get("away_probable_pitcher")
        return bool(home_sp) and bool(away_sp)
