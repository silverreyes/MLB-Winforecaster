"""FeatureBuilder: core computation engine for game-level differential features.

Transforms raw Phase 1 cached data into a game-level feature matrix. Shared
between the backtest pipeline (Phase 3) and any future live prediction pipeline.

Every rolling feature enforces temporal safety via shift(1) with season boundary
reset. The class produces a DataFrame (not yet the final Parquet file -- Plan 03).

Output columns include:
    - SP differentials: sp_fip_diff, sp_xfip_diff, sp_k_bb_pct_diff,
      sp_siera_diff, sp_whip_diff, sp_era_diff
    - Offense differentials: team_woba_diff, team_ops_diff, pyth_win_pct_diff
    - Rolling: rolling_ops_diff (10-game window with shift(1))
    - Bullpen: bullpen_era_diff, bullpen_fip_diff
    - Park: is_home, park_factor
    - Advanced: xwoba_diff, sp_recent_era_diff, log5_home_wp
    - Kalshi: kalshi_yes_price
    - Labels: home_win
"""

import logging
import numpy as np
import pandas as pd

from src.data.mlb_schedule import fetch_schedule
from src.data.sp_stats import fetch_sp_stats
from src.data.team_batting import fetch_team_batting
from src.data.statcast import fetch_statcast_pitcher
from src.data.kalshi import fetch_kalshi_markets
from src.features.formulas import (
    log5_probability,
    pythagorean_win_pct,
    get_park_factor,
)
from src.data.sp_id_bridge import build_mlb_to_fg_bridge, strip_accents, MANUAL_OVERRIDES
from src.features.game_logs import fetch_team_game_log
from src.features.sp_recent_form import (
    fetch_sp_recent_form_bulk,
    _fetch_pitcher_game_log_v2,
    _get_pitcher_id_map,
    compute_rolling_fip_bulk,
    compute_pitch_count_and_rest_bulk,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# League-average constants for cold-start imputation (SP-10)
# ---------------------------------------------------------------------------
LEAGUE_AVG_ERA = 4.25
LEAGUE_AVG_K_BB_PCT = 0.10   # 10% K-BB differential
LEAGUE_AVG_WHIP = 1.30
LEAGUE_AVG_SIERA = 4.15
LEAGUE_AVG_FIP = 4.15
LEAGUE_AVG_XFIP = 4.10


class FeatureBuilder:
    """Build game-level differential features from raw cached data.

    Args:
        seasons: List of MLB season years to include (e.g., [2015, ..., 2024]).
        as_of_date: Optional YYYY-MM-DD cutoff for walk-forward safety.
            If set, only games before this date are included.
    """

    def __init__(self, seasons: list[int], as_of_date: str | None = None):
        self.seasons = seasons
        self.as_of_date = as_of_date  # YYYY-MM-DD cutoff for walk-forward

    def build(self) -> pd.DataFrame:
        """Build complete feature matrix. Returns one row per game.

        Pipeline:
            1. Load schedule backbone
            2. Filter TBD starters
            3. Add outcome label
            4. Add SP features (FIP, xFIP, K%, SIERA)
            5. Add offense features (wOBA, OPS, Pythagorean win%)
            6. Add rolling features (10-game OPS)
            7. Add bullpen features (ERA, FIP)
            8. Add park features (is_home, park_factor)
            9. Add advanced features (xwOBA, SP recent ERA, Log5)
            10. Add Kalshi features (market implied probability)

        Returns:
            DataFrame with one row per game, all differential features,
            and the home_win outcome label.
        """
        df = self._load_schedule()
        df = self._filter_tbd_starters(df)
        df = self._add_outcome_label(df)
        df = self._add_sp_features(df)
        df = self._add_offense_features(df)
        df = self._add_rolling_features(df)
        df = self._add_bullpen_features(df)
        df = self._add_park_features(df)
        df = self._add_advanced_features(df)
        df = self._add_kalshi_features(df)
        return df

    def _load_schedule(self) -> pd.DataFrame:
        """Load and concatenate schedule data for all requested seasons.

        Applies as_of_date filter if set (walk-forward safety).
        """
        logger.info("Loading schedule data...")
        frames = []
        for season in self.seasons:
            sched = fetch_schedule(season)
            frames.append(sched)
        df = pd.concat(frames, ignore_index=True)

        # Ensure game_date is datetime
        df["game_date"] = pd.to_datetime(df["game_date"])

        if self.as_of_date is not None:
            cutoff = pd.to_datetime(self.as_of_date)
            df = df[df["game_date"] < cutoff].copy()

        logger.info(f"Schedule loaded: {len(df)} games across {len(self.seasons)} seasons")
        return df

    def _filter_tbd_starters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Drop games where either starter is TBD/None/NaN."""
        logger.info("Filtering TBD starters...")
        mask = df["home_probable_pitcher"].notna() & df["away_probable_pitcher"].notna()
        excluded = (~mask).sum()
        logger.info(f"Excluded {excluded} games with TBD starters")
        return df[mask].copy()

    def _add_outcome_label(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add home_win column: 1 if home team won, else 0."""
        logger.info("Adding outcome label...")
        df["home_win"] = (df["winning_team"] == df["home_team"]).astype(int)
        return df

    def _resolve_sp_stats(
        self,
        season: int,
        pitcher_name: str,
        sp_lookup: dict[tuple[int, str], dict],
        fg_id_to_stats: dict[int, dict],
        bridge: dict[int, int],
        pitcher_id_map: dict[str, int],
        fg_name_lookup: dict[str, dict],
    ) -> dict:
        """Resolve SP stats via multi-tier lookup chain.

        1. Exact name match in sp_lookup
        2. Manual override name, then retry sp_lookup
        3. Accent-stripped name match in sp_lookup
        4. ID bridge: pitcher_name -> MLB ID -> FG ID -> fg_id_to_stats
        5. Accent-stripped name in fg_name_lookup

        Returns stats dict or empty dict.
        """
        # Tier 1: exact name match
        stats = sp_lookup.get((season, pitcher_name))
        if stats:
            return stats

        # Tier 2: manual override
        override_name = MANUAL_OVERRIDES.get(pitcher_name)
        if override_name:
            stats = sp_lookup.get((season, override_name))
            if stats:
                return stats

        # Tier 3: accent-stripped name match
        stripped = strip_accents(pitcher_name)
        if stripped != pitcher_name:
            stats = sp_lookup.get((season, stripped))
            if stats:
                return stats

        # Tier 4: ID bridge (name -> MLB ID -> FG ID -> stats)
        mlb_id = pitcher_id_map.get(pitcher_name)
        if mlb_id is not None:
            fg_id = bridge.get(mlb_id)
            if fg_id is not None:
                stats = fg_id_to_stats.get(fg_id)
                if stats:
                    return stats

        # Tier 5: accent-stripped name in fg_name_lookup
        fg_stats = fg_name_lookup.get(strip_accents(pitcher_name).lower())
        if fg_stats:
            return fg_stats

        return {}

    def _add_sp_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add starting pitcher differential features (SP-03, SP-04, SP-05, SP-06, SP-10).

        Temporally-safe features (season-to-date rolling via cumsum + shift(1)):
            sp_era_diff, sp_k_bb_pct_diff

        FanGraphs season-level features (not computable from game logs):
            sp_fip_diff, sp_xfip_diff, sp_whip_diff, sp_siera_diff

        Cold-start handling: first start of season falls back to previous-season
        FanGraphs stats, then to league-average constants.

        Uses multi-tier name resolution:
        1. Exact FanGraphs name match
        2. Manual override (MANUAL_OVERRIDES dict)
        3. Accent-stripped name match
        4. ID bridge (Chadwick register + MLB Stats API -> FG ID -> stats)
        5. Accent-stripped name in fg_name_lookup
        """
        logger.info("Adding SP features...")

        # Collect all probable starter names across all games
        all_sp_names: set[str] = set()
        all_sp_names.update(df["home_probable_pitcher"].dropna().unique())
        all_sp_names.update(df["away_probable_pitcher"].dropna().unique())

        # ------------------------------------------------------------------
        # 1. Build per-season FanGraphs lookup and ID bridge infrastructure
        # ------------------------------------------------------------------
        # FanGraphs season-level lookup: {(season, pitcher_name): {stat: value}}
        fg_season_lookup: dict[tuple[int, str], dict] = {}
        # Also build per-season auxiliary lookups for ID bridge
        season_fg_id_to_stats: dict[int, dict[int, dict]] = {}
        season_bridge: dict[int, dict[int, int]] = {}
        season_pitcher_id_map: dict[int, dict[str, int]] = {}
        season_fg_name_lookup: dict[int, dict[str, dict]] = {}

        for season in self.seasons:
            sp_df = fetch_sp_stats(season, min_gs=1)

            # Primary lookup by exact name (includes WHIP, SIERA, FIP, xFIP)
            for _, row in sp_df.iterrows():
                name = row["Name"]
                stats = {
                    "FIP": row.get("FIP"),
                    "xFIP": row.get("xFIP"),
                    "SIERA": row.get("SIERA"),
                    "WHIP": row.get("WHIP"),
                    "ERA": row.get("ERA"),
                    "K-BB%": row.get("K-BB%"),
                }
                fg_season_lookup[(season, name)] = stats

            # Build FG ID -> stats lookup
            fg_id_to_stats: dict[int, dict] = {}
            fg_name_lookup: dict[str, dict] = {}
            for _, row in sp_df.iterrows():
                idfg = row.get("IDfg")
                stats = {
                    "FIP": row.get("FIP"),
                    "xFIP": row.get("xFIP"),
                    "SIERA": row.get("SIERA"),
                    "WHIP": row.get("WHIP"),
                    "ERA": row.get("ERA"),
                    "K-BB%": row.get("K-BB%"),
                }
                if idfg is not None and pd.notna(idfg):
                    fg_id_to_stats[int(idfg)] = stats
                name = row.get("Name", "")
                if name:
                    fg_name_lookup[strip_accents(str(name)).lower()] = stats

            season_fg_id_to_stats[season] = fg_id_to_stats
            season_fg_name_lookup[season] = fg_name_lookup

            # Build ID bridge and pitcher_id_map for this season
            try:
                pitcher_id_map = _get_pitcher_id_map(season)
            except Exception as e:
                logger.debug("Could not load pitcher_id_map for %d: %s", season, e)
                pitcher_id_map = {}

            try:
                bridge = build_mlb_to_fg_bridge(season, sp_df, pitcher_id_map=pitcher_id_map)
            except Exception as e:
                logger.debug("Could not build ID bridge for %d: %s", season, e)
                bridge = {}

            season_bridge[season] = bridge
            season_pitcher_id_map[season] = pitcher_id_map

        # ------------------------------------------------------------------
        # 2. Build per-game pitcher log and compute season-to-date rolling
        # ------------------------------------------------------------------
        all_logs = []
        for season in self.seasons:
            pid_map = season_pitcher_id_map.get(season, {})
            for sp_name in all_sp_names:
                mlb_id = pid_map.get(sp_name)
                if mlb_id is None:
                    continue
                log = _fetch_pitcher_game_log_v2(mlb_id, season)
                if log is not None and not log.empty:
                    log = log.copy()
                    log["pitcher_name"] = sp_name
                    log["pitcher_id"] = mlb_id
                    log["season"] = season
                    all_logs.append(log)

        # Season-to-date lookup: {(season, pitcher_name, date_str): {std_era, std_k_bb_rate}}
        std_lookup: dict[tuple[int, str, str], dict] = {}

        if all_logs:
            logs = pd.concat(all_logs, ignore_index=True)
            logs["date"] = pd.to_datetime(logs["date"])
            logs = logs.sort_values(["pitcher_id", "season", "date"])

            # Compute cumulative stats per pitcher per season
            grp = logs.groupby(["pitcher_id", "season"])
            logs["cum_er"] = grp["earned_runs"].cumsum()
            logs["cum_ip"] = grp["innings_pitched"].cumsum()
            logs["cum_k"] = grp["strikeouts"].cumsum()
            logs["cum_bb"] = grp["base_on_balls"].cumsum()

            # shift(1): game N sees only stats through game N-1
            logs["prev_cum_er"] = grp["cum_er"].shift(1)
            logs["prev_cum_ip"] = grp["cum_ip"].shift(1)
            logs["prev_cum_k"] = grp["cum_k"].shift(1)
            logs["prev_cum_bb"] = grp["cum_bb"].shift(1)

            # Season-to-date ERA
            logs["std_era"] = np.where(
                logs["prev_cum_ip"] > 0,
                (logs["prev_cum_er"] * 9) / logs["prev_cum_ip"],
                np.nan,
            )

            # Season-to-date K-BB rate (per 9 IP for scale)
            logs["std_k_bb_rate"] = np.where(
                logs["prev_cum_ip"] > 0,
                ((logs["prev_cum_k"] - logs["prev_cum_bb"]) * 9) / logs["prev_cum_ip"],
                np.nan,
            )

            # Build lookup from logs DataFrame
            for _, row in logs.iterrows():
                date_str = row["date"].strftime("%Y-%m-%d")
                std_lookup[(row["season"], row["pitcher_name"], date_str)] = {
                    "std_era": row["std_era"],
                    "std_k_bb_rate": row["std_k_bb_rate"],
                }

        # ------------------------------------------------------------------
        # 3. Build cold-start fallback from previous season FanGraphs stats
        # ------------------------------------------------------------------
        prev_season_stats: dict[tuple[int, str], dict] = {}
        for season in self.seasons:
            prev = season - 1
            try:
                prev_fg = fetch_sp_stats(prev, min_gs=1)
                for _, row in prev_fg.iterrows():
                    prev_season_stats[(season, row["Name"])] = {
                        "ERA": row.get("ERA", LEAGUE_AVG_ERA),
                        "K-BB%": row.get("K-BB%", LEAGUE_AVG_K_BB_PCT),
                        "WHIP": row.get("WHIP", LEAGUE_AVG_WHIP),
                        "SIERA": row.get("SIERA", LEAGUE_AVG_SIERA),
                        "FIP": row.get("FIP", LEAGUE_AVG_FIP),
                        "xFIP": row.get("xFIP", LEAGUE_AVG_XFIP),
                    }
            except Exception:
                pass

        # ------------------------------------------------------------------
        # 4. Map features to the game DataFrame
        # ------------------------------------------------------------------
        for prefix, pitcher_col in [("home_sp", "home_probable_pitcher"),
                                     ("away_sp", "away_probable_pitcher")]:
            # Season-to-date rolling: ERA, K-BB rate
            era_vals = []
            k_bb_vals = []
            # FanGraphs season-level: FIP, xFIP, WHIP, SIERA
            fip_vals = []
            xfip_vals = []
            whip_vals = []
            siera_vals = []

            for _, row in df.iterrows():
                season = row["season"]
                pitcher_name = row[pitcher_col]
                game_date_str = row["game_date"].strftime("%Y-%m-%d") if hasattr(row["game_date"], "strftime") else str(row["game_date"])[:10]

                # --- std_era: rolling -> prev_season -> league_avg ---
                std_stats = std_lookup.get((season, pitcher_name, game_date_str), {})
                era_val = std_stats.get("std_era")
                if era_val is None or (isinstance(era_val, float) and np.isnan(era_val)):
                    # Cold-start: try previous season
                    prev_stats = prev_season_stats.get((season, pitcher_name), {})
                    era_val = prev_stats.get("ERA")
                    if era_val is None or (isinstance(era_val, float) and np.isnan(era_val)):
                        era_val = LEAGUE_AVG_ERA
                era_vals.append(era_val)

                # --- std_k_bb_rate: rolling -> prev_season K-BB% -> league_avg ---
                k_bb_val = std_stats.get("std_k_bb_rate")
                if k_bb_val is None or (isinstance(k_bb_val, float) and np.isnan(k_bb_val)):
                    prev_stats = prev_season_stats.get((season, pitcher_name), {})
                    k_bb_val = prev_stats.get("K-BB%")
                    if k_bb_val is None or (isinstance(k_bb_val, float) and np.isnan(k_bb_val)):
                        k_bb_val = LEAGUE_AVG_K_BB_PCT
                k_bb_vals.append(k_bb_val)

                # --- FanGraphs season-level: FIP, xFIP, WHIP, SIERA ---
                fg_stats = self._resolve_sp_stats(
                    season,
                    pitcher_name,
                    fg_season_lookup,
                    season_fg_id_to_stats.get(season, {}),
                    season_bridge.get(season, {}),
                    season_pitcher_id_map.get(season, {}),
                    season_fg_name_lookup.get(season, {}),
                )

                # FIP: FG season -> prev_season -> league_avg
                fip_v = fg_stats.get("FIP")
                if fip_v is None or (isinstance(fip_v, float) and np.isnan(fip_v)):
                    prev_stats = prev_season_stats.get((season, pitcher_name), {})
                    fip_v = prev_stats.get("FIP", LEAGUE_AVG_FIP)
                fip_vals.append(fip_v)

                # xFIP
                xfip_v = fg_stats.get("xFIP")
                if xfip_v is None or (isinstance(xfip_v, float) and np.isnan(xfip_v)):
                    prev_stats = prev_season_stats.get((season, pitcher_name), {})
                    xfip_v = prev_stats.get("xFIP", LEAGUE_AVG_XFIP)
                xfip_vals.append(xfip_v)

                # WHIP (FG season-level -- not computable from game logs)
                whip_v = fg_stats.get("WHIP")
                if whip_v is None or (isinstance(whip_v, float) and np.isnan(whip_v)):
                    prev_stats = prev_season_stats.get((season, pitcher_name), {})
                    whip_v = prev_stats.get("WHIP", LEAGUE_AVG_WHIP)
                whip_vals.append(whip_v)

                # SIERA
                siera_v = fg_stats.get("SIERA")
                if siera_v is None or (isinstance(siera_v, float) and np.isnan(siera_v)):
                    prev_stats = prev_season_stats.get((season, pitcher_name), {})
                    siera_v = prev_stats.get("SIERA", LEAGUE_AVG_SIERA)
                siera_vals.append(siera_v)

            df[f"{prefix}_std_era"] = era_vals
            df[f"{prefix}_std_k_bb_rate"] = k_bb_vals
            df[f"{prefix}_fip"] = fip_vals
            df[f"{prefix}_xfip"] = xfip_vals
            df[f"{prefix}_whip"] = whip_vals
            df[f"{prefix}_siera"] = siera_vals

            # Log unmatched pitchers at DEBUG level
            unmatched = df[df[f"{prefix}_fip"].isna()][pitcher_col].unique()
            for name in unmatched:
                season_vals = df[df[pitcher_col] == name]["season"].unique()
                for s in season_vals:
                    logger.debug(
                        f"SP name unmatched: '{name}' not found in sp_stats (season={s})"
                    )

        # ------------------------------------------------------------------
        # 5. Compute differentials
        # ------------------------------------------------------------------
        df["sp_era_diff"] = df["home_sp_std_era"] - df["away_sp_std_era"]
        df["sp_k_bb_pct_diff"] = df["home_sp_std_k_bb_rate"] - df["away_sp_std_k_bb_rate"]
        df["sp_whip_diff"] = df["home_sp_whip"] - df["away_sp_whip"]
        df["sp_siera_diff"] = df["home_sp_siera"] - df["away_sp_siera"]
        df["sp_fip_diff"] = df["home_sp_fip"] - df["away_sp_fip"]
        df["sp_xfip_diff"] = df["home_sp_xfip"] - df["away_sp_xfip"]

        # ------------------------------------------------------------------
        # 6. Drop intermediate columns
        # ------------------------------------------------------------------
        for prefix in ["home_sp", "away_sp"]:
            df = df.drop(
                columns=[
                    f"{prefix}_std_era", f"{prefix}_std_k_bb_rate",
                    f"{prefix}_fip", f"{prefix}_xfip",
                    f"{prefix}_whip", f"{prefix}_siera",
                ],
                errors="ignore",
            )

        return df

    def _add_offense_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add team offensive differential features (FEAT-02).

        Features: team_woba_diff, team_ops_diff, pyth_win_pct_diff
        """
        logger.info("Adding offense features...")

        # Build per-season team lookup
        team_lookup: dict[tuple[int, str], dict] = {}
        for season in self.seasons:
            bat_df = fetch_team_batting(season)
            for _, row in bat_df.iterrows():
                team = row["Team"]
                # OPS = OBP + SLG if not directly available
                ops = row.get("OPS")
                if ops is None or pd.isna(ops):
                    obp = row.get("OBP", 0)
                    slg = row.get("SLG", 0)
                    ops = obp + slg if (obp and slg) else None
                team_lookup[(season, team)] = {
                    "wOBA": row.get("wOBA"),
                    "OPS": ops,
                    "R": row.get("R"),
                }

        # Map team stats for home and away
        for prefix, team_col in [("home", "home_team"), ("away", "away_team")]:
            for stat, col_name in [("wOBA", f"{prefix}_woba"),
                                    ("OPS", f"{prefix}_ops"),
                                    ("R", f"{prefix}_r")]:
                df[col_name] = df.apply(
                    lambda r, s=stat, tc=team_col: team_lookup.get(
                        (r["season"], r[tc]), {}
                    ).get(s),
                    axis=1,
                )

        # Compute Pythagorean win% using schedule-derived runs
        # Aggregate runs scored and allowed per team per season from schedule
        pyth_lookup: dict[tuple[int, str], float] = {}
        for season in self.seasons:
            season_df = df[df["season"] == season]
            teams = set(season_df["home_team"].unique()) | set(
                season_df["away_team"].unique()
            )
            for team in teams:
                # Runs scored: home_score when home, away_score when away
                home_rs = season_df.loc[
                    season_df["home_team"] == team, "home_score"
                ]
                away_rs = season_df.loc[
                    season_df["away_team"] == team, "away_score"
                ]
                rs = pd.concat([home_rs, away_rs]).sum()

                # Runs allowed: away_score when home, home_score when away
                home_ra = season_df.loc[
                    season_df["home_team"] == team, "away_score"
                ]
                away_ra = season_df.loc[
                    season_df["away_team"] == team, "home_score"
                ]
                ra = pd.concat([home_ra, away_ra]).sum()

                pyth_lookup[(season, team)] = pythagorean_win_pct(rs, ra)

        for prefix, team_col in [("home", "home_team"), ("away", "away_team")]:
            df[f"{prefix}_pyth"] = df.apply(
                lambda r, tc=team_col: pyth_lookup.get(
                    (r["season"], r[tc]), 0.5
                ),
                axis=1,
            )

        # Compute differentials
        df["team_woba_diff"] = df["home_woba"] - df["away_woba"]
        df["team_ops_diff"] = df["home_ops"] - df["away_ops"]
        df["pyth_win_pct_diff"] = df["home_pyth"] - df["away_pyth"]

        # Drop intermediate columns
        for prefix in ["home", "away"]:
            df = df.drop(
                columns=[f"{prefix}_woba", f"{prefix}_ops", f"{prefix}_r",
                         f"{prefix}_pyth"],
                errors="ignore",
            )

        return df

    def _add_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add rolling 10-game OPS differential (FEAT-03).

        Uses shift(1) within season-grouped data for temporal safety.
        min_periods=10 ensures games 1-9 are NaN (no partial windows).
        Season boundary reset via groupby.
        """
        logger.info("Adding rolling features...")

        # Collect all game logs
        all_logs = []
        teams = set(df["home_team"].unique()) | set(df["away_team"].unique())
        for season in self.seasons:
            for team in teams:
                try:
                    log = fetch_team_game_log(season, team)
                    if log is not None and not log.empty:
                        log = log.copy()
                        # Ensure team and season columns
                        if "team" not in log.columns:
                            log["team"] = team
                        if "season" not in log.columns:
                            log["season"] = season
                        all_logs.append(log)
                except Exception as e:
                    logger.debug(f"No game log for {team} {season}: {e}")

        if not all_logs:
            df["rolling_ops_diff"] = np.nan
            return df

        logs_df = pd.concat(all_logs, ignore_index=True)

        # Ensure game_date column is datetime for sorting.
        # MLB Stats API schema uses "game_date" (lowercase, already datetime).
        # Legacy BRef schema used "Date" — handle both for compatibility.
        if "game_date" not in logs_df.columns:
            if "Date" in logs_df.columns:
                logs_df["game_date"] = pd.to_datetime(logs_df["Date"])
            else:
                df["rolling_ops_diff"] = np.nan
                return df
        else:
            logs_df["game_date"] = pd.to_datetime(logs_df["game_date"])

        # Resolve OPS column — MLB Stats API uses lowercase "ops";
        # legacy BRef schema used uppercase "OPS".  Compute from components
        # if neither is present.
        if "ops" in logs_df.columns:
            logs_df["OPS"] = pd.to_numeric(logs_df["ops"], errors="coerce")
        elif "OPS" in logs_df.columns:
            logs_df["OPS"] = pd.to_numeric(logs_df["OPS"], errors="coerce")
        else:
            obp_col = "obp" if "obp" in logs_df.columns else "OBP"
            slg_col = "slg" if "slg" in logs_df.columns else "SLG"
            obp = pd.to_numeric(logs_df.get(obp_col, pd.Series(0, index=logs_df.index)), errors="coerce")
            slg = pd.to_numeric(logs_df.get(slg_col, pd.Series(0, index=logs_df.index)), errors="coerce")
            logs_df["OPS"] = obp + slg

        # Sort and compute rolling OPS with shift(1) within season groups
        logs_df = logs_df.sort_values(["team", "season", "game_date"])
        logs_df["rolling_ops_10"] = (
            logs_df.groupby(["team", "season"])["OPS"]
            .transform(lambda x: x.shift(1).rolling(10, min_periods=10).mean())
        )

        # Create lookup for joining: (team, game_date) -> rolling_ops_10
        # Take the first value per (team, game_date) to handle duplicates
        rolling_lookup = (
            logs_df.groupby(["team", "game_date"])["rolling_ops_10"]
            .first()
            .to_dict()
        )

        # Fallback: team -> most recent non-NaN rolling_ops_10.
        # Used for live games on dates with no completed log entries
        # (e.g., Opening Day when no 2026 games are Final yet).
        latest_rolling = (
            logs_df.dropna(subset=["rolling_ops_10"])
            .sort_values("game_date")
            .groupby("team")["rolling_ops_10"]
            .last()
            .to_dict()
        )

        def _lookup_rolling(team, game_date):
            val = rolling_lookup.get((team, game_date))
            if val is None or pd.isna(val):
                val = latest_rolling.get(team)
            return val

        # Join for home and away teams
        df["home_rolling_ops_10"] = df.apply(
            lambda r: _lookup_rolling(r["home_team"], r["game_date"]),
            axis=1,
        )
        df["away_rolling_ops_10"] = df.apply(
            lambda r: _lookup_rolling(r["away_team"], r["game_date"]),
            axis=1,
        )

        df["rolling_ops_diff"] = df["home_rolling_ops_10"] - df["away_rolling_ops_10"]

        # Drop intermediate columns
        df = df.drop(columns=["home_rolling_ops_10", "away_rolling_ops_10"],
                      errors="ignore")

        return df

    def _add_bullpen_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add bullpen ERA and FIP differentials (FEAT-04, FEAT-06 partial).

        Features: bullpen_era_diff, bullpen_fip_diff
        Uses GS < 3 and IP >= 5 to identify relievers.
        """
        logger.info("Adding bullpen features...")

        # Build per-season team bullpen lookup
        bullpen_lookup: dict[tuple[int, str], dict] = {}
        for season in self.seasons:
            # min_gs=0 fetches ALL pitchers (not just starters)
            all_pitchers = fetch_sp_stats(season, min_gs=0)

            # Filter to relievers: GS < 3 (catches openers) AND IP >= 5
            # (excludes position players who pitched in blowouts)
            relievers = all_pitchers[
                (all_pitchers["GS"] < 3) & (all_pitchers["IP"] >= 5)
            ].copy()

            # Aggregate by team: mean ERA and FIP
            if not relievers.empty:
                team_bullpen = relievers.groupby("Team").agg(
                    bullpen_era=("ERA", "mean"),
                    bullpen_fip=("FIP", "mean"),
                ).to_dict("index")

                for team, stats in team_bullpen.items():
                    bullpen_lookup[(season, team)] = stats

        # Map bullpen stats
        for prefix, team_col in [("home", "home_team"), ("away", "away_team")]:
            for stat, col_name in [("bullpen_era", f"{prefix}_bullpen_era"),
                                    ("bullpen_fip", f"{prefix}_bullpen_fip")]:
                df[col_name] = df.apply(
                    lambda r, s=stat, tc=team_col: bullpen_lookup.get(
                        (r["season"], r[tc]), {}
                    ).get(s),
                    axis=1,
                )

        # Compute differentials
        df["bullpen_era_diff"] = df["home_bullpen_era"] - df["away_bullpen_era"]
        df["bullpen_fip_diff"] = df["home_bullpen_fip"] - df["away_bullpen_fip"]

        # Drop intermediate columns
        for prefix in ["home", "away"]:
            df = df.drop(
                columns=[f"{prefix}_bullpen_era", f"{prefix}_bullpen_fip"],
                errors="ignore",
            )

        return df

    def _add_park_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add home/away indicator and park run factor (FEAT-05).

        Features: is_home (always 1, matrix is from home perspective),
                  park_factor (from PARK_FACTORS dict)
        """
        logger.info("Adding park features...")
        df["is_home"] = 1
        df["park_factor"] = df["home_team"].map(get_park_factor)
        return df

    def _add_advanced_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add advanced differential features (FEAT-06).

        Features: xwoba_diff, sp_recent_era_diff, log5_home_wp
        """
        logger.info("Adding advanced features...")

        # --- xwOBA differential from Statcast ---
        xwoba_lookup: dict[tuple[int, str], float] = {}
        for season in self.seasons:
            try:
                sc_df = fetch_statcast_pitcher(season)
                # Baseball Savant returns a single merged column 'last_name, first_name'
                # xwOBA column is 'est_woba' (not 'xwoba')
                name_col = "last_name, first_name"
                xwoba_col = "est_woba"
                if name_col in sc_df.columns and xwoba_col in sc_df.columns:
                    for _, row in sc_df.iterrows():
                        raw_name = str(row[name_col]).strip()
                        # Format: "Webb, Logan" -> "Logan Webb"
                        if ", " in raw_name:
                            parts = raw_name.split(", ", 1)
                            name = f"{parts[1]} {parts[0]}"
                        else:
                            name = raw_name
                        xwoba_val = row[xwoba_col]
                        if pd.notna(xwoba_val):
                            xwoba_lookup[(season, name)] = float(xwoba_val)
            except Exception as e:
                logger.debug(f"No Statcast data for season {season}: {e}")

        df["home_sp_xwoba"] = df.apply(
            lambda r: xwoba_lookup.get((r["season"], r["home_probable_pitcher"])),
            axis=1,
        )
        df["away_sp_xwoba"] = df.apply(
            lambda r: xwoba_lookup.get((r["season"], r["away_probable_pitcher"])),
            axis=1,
        )
        df["xwoba_diff"] = df["home_sp_xwoba"] - df["away_sp_xwoba"]
        df = df.drop(columns=["home_sp_xwoba", "away_sp_xwoba"], errors="ignore")

        # --- SP recent form (30-day rolling ERA via pitching_stats_range) ---
        # Per CONTEXT.md locked decision: uses pitching_stats_range, not season ERA
        sp_recent_lookup: dict[tuple[str, str], float] = {}
        for season in self.seasons:
            season_games = df[df["season"] == season]
            game_dates = season_games["game_date"].dt.strftime("%Y-%m-%d").unique().tolist()
            # Pass probable-starter names so the loader only fetches game logs
            # for pitchers who actually start games (not all ~300 roster pitchers).
            season_sps = (
                set(season_games["home_probable_pitcher"].dropna())
                | set(season_games["away_probable_pitcher"].dropna())
            )
            if game_dates:
                bulk_results = fetch_sp_recent_form_bulk(game_dates, season, sp_names=season_sps)
                for date_str, form_df in bulk_results.items():
                    if form_df is not None and not form_df.empty and "Name" in form_df.columns:
                        for _, row in form_df.iterrows():
                            era = row.get("ERA")
                            if era is not None and not pd.isna(era):
                                sp_recent_lookup[(date_str, row["Name"])] = era

        df["home_sp_recent_era"] = df.apply(
            lambda r: sp_recent_lookup.get(
                (r["game_date"].strftime("%Y-%m-%d"), r["home_probable_pitcher"])
            ),
            axis=1,
        )
        df["away_sp_recent_era"] = df.apply(
            lambda r: sp_recent_lookup.get(
                (r["game_date"].strftime("%Y-%m-%d"), r["away_probable_pitcher"])
            ),
            axis=1,
        )
        df["sp_recent_era_diff"] = df["home_sp_recent_era"] - df["away_sp_recent_era"]
        df = df.drop(
            columns=["home_sp_recent_era", "away_sp_recent_era"], errors="ignore"
        )

        # --- SP recent FIP (30-day rolling from game logs) ---
        sp_fip_recent_lookup: dict[tuple[str, str], float] = {}
        for season in self.seasons:
            season_games = df[df["season"] == season]
            game_dates = season_games["game_date"].dt.strftime("%Y-%m-%d").unique().tolist()
            season_sps = (
                set(season_games["home_probable_pitcher"].dropna())
                | set(season_games["away_probable_pitcher"].dropna())
            )
            if game_dates:
                fip_results = compute_rolling_fip_bulk(game_dates, season, sp_names=season_sps)
                for date_str, fip_df in fip_results.items():
                    if fip_df is not None and not fip_df.empty:
                        for _, row in fip_df.iterrows():
                            fip_val = row.get("FIP")
                            if fip_val is not None and not pd.isna(fip_val):
                                sp_fip_recent_lookup[(date_str, row["Name"])] = fip_val

        df["home_sp_recent_fip"] = df.apply(
            lambda r: sp_fip_recent_lookup.get(
                (r["game_date"].strftime("%Y-%m-%d"), r["home_probable_pitcher"])
            ),
            axis=1,
        )
        df["away_sp_recent_fip"] = df.apply(
            lambda r: sp_fip_recent_lookup.get(
                (r["game_date"].strftime("%Y-%m-%d"), r["away_probable_pitcher"])
            ),
            axis=1,
        )
        df["sp_recent_fip_diff"] = df["home_sp_recent_fip"] - df["away_sp_recent_fip"]
        df = df.drop(columns=["home_sp_recent_fip", "away_sp_recent_fip"], errors="ignore")

        # --- SP pitch count and days rest ---
        sp_pcount_rest_lookup: dict[tuple[str, str], dict] = {}
        for season in self.seasons:
            season_games = df[df["season"] == season]
            game_dates = season_games["game_date"].dt.strftime("%Y-%m-%d").unique().tolist()
            season_sps = (
                set(season_games["home_probable_pitcher"].dropna())
                | set(season_games["away_probable_pitcher"].dropna())
            )
            if game_dates:
                pc_results = compute_pitch_count_and_rest_bulk(game_dates, season, sp_names=season_sps)
                for date_str, pc_df in pc_results.items():
                    if pc_df is not None and not pc_df.empty:
                        for _, row in pc_df.iterrows():
                            sp_pcount_rest_lookup[(date_str, row["Name"])] = {
                                "pitch_count_last": row.get("pitch_count_last"),
                                "days_rest": row.get("days_rest"),
                            }

        for prefix, pitcher_col in [("home_sp", "home_probable_pitcher"),
                                     ("away_sp", "away_probable_pitcher")]:
            df[f"{prefix}_pitch_count_last"] = df.apply(
                lambda r, pc=pitcher_col: sp_pcount_rest_lookup.get(
                    (r["game_date"].strftime("%Y-%m-%d"), r[pc]), {}
                ).get("pitch_count_last"),
                axis=1,
            )
            df[f"{prefix}_days_rest"] = df.apply(
                lambda r, pc=pitcher_col: sp_pcount_rest_lookup.get(
                    (r["game_date"].strftime("%Y-%m-%d"), r[pc]), {}
                ).get("days_rest"),
                axis=1,
            )

        df["sp_pitch_count_last_diff"] = df["home_sp_pitch_count_last"] - df["away_sp_pitch_count_last"]
        df["sp_days_rest_diff"] = df["home_sp_days_rest"] - df["away_sp_days_rest"]
        df = df.drop(
            columns=["home_sp_pitch_count_last", "away_sp_pitch_count_last",
                     "home_sp_days_rest", "away_sp_days_rest"],
            errors="ignore",
        )

        # --- Log5 win probability ---
        # Derived from game-by-game results with shift(1), NOT from season-level data
        # Build per-team cumulative win% from schedule results
        cumulative_wp = self._compute_cumulative_win_pct(df)

        df["home_cum_wp"] = df.apply(
            lambda r: cumulative_wp.get(
                (r["season"], r["home_team"], r["game_date"]), 0.5
            ),
            axis=1,
        )
        df["away_cum_wp"] = df.apply(
            lambda r: cumulative_wp.get(
                (r["season"], r["away_team"], r["game_date"]), 0.5
            ),
            axis=1,
        )
        df["log5_home_wp"] = df.apply(
            lambda r: log5_probability(r["home_cum_wp"], r["away_cum_wp"]),
            axis=1,
        )
        df = df.drop(columns=["home_cum_wp", "away_cum_wp"], errors="ignore")

        return df

    def _compute_cumulative_win_pct(
        self, df: pd.DataFrame
    ) -> dict[tuple[int, str, pd.Timestamp], float]:
        """Compute per-team per-game cumulative win percentage with shift(1).

        For each game, a team's win% is computed from all PRIOR games in that
        season only. Default before any games: 0.5 (neutral prior).

        Returns:
            Dict mapping (season, team, game_date) -> cumulative win% as of
            that game (excluding that game's result).
        """
        # Build long-form per-team game record
        records = []
        for _, row in df.iterrows():
            game_date = row["game_date"]
            season = row["season"]
            home = row["home_team"]
            away = row["away_team"]
            winner = row["winning_team"]

            records.append({
                "team": home,
                "season": season,
                "game_date": game_date,
                "won": 1 if winner == home else 0,
            })
            records.append({
                "team": away,
                "season": season,
                "game_date": game_date,
                "won": 1 if winner == away else 0,
            })

        if not records:
            return {}

        long_df = pd.DataFrame(records)
        long_df = long_df.sort_values(["team", "season", "game_date"])

        # Compute shifted cumulative win% per (team, season)
        long_df["cum_wins"] = long_df.groupby(["team", "season"])["won"].cumsum()
        long_df["games_played"] = long_df.groupby(["team", "season"]).cumcount() + 1

        # shift(1) so each game's win% uses only prior games
        long_df["prev_wins"] = long_df.groupby(["team", "season"])["cum_wins"].shift(1)
        long_df["prev_games"] = long_df.groupby(["team", "season"])["games_played"].shift(1)

        # Default: 0.5 before any games played
        long_df["cum_wp"] = long_df.apply(
            lambda r: r["prev_wins"] / r["prev_games"]
            if pd.notna(r["prev_games"]) and r["prev_games"] > 0
            else 0.5,
            axis=1,
        )

        # Build lookup dict
        result = {}
        for _, row in long_df.iterrows():
            result[(row["season"], row["team"], row["game_date"])] = row["cum_wp"]

        return result

    def _add_kalshi_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Kalshi market implied probability (FEAT-08 partial).

        Left-joins on (game_date, home_team, away_team). NaN for pre-2025 games.
        """
        logger.info("Adding Kalshi features...")

        try:
            kalshi_df = fetch_kalshi_markets()
        except Exception as e:
            logger.warning(f"Could not fetch Kalshi markets: {e}")
            df["kalshi_yes_price"] = np.nan
            return df

        if kalshi_df.empty:
            df["kalshi_yes_price"] = np.nan
            return df

        # Type coercion must be explicit
        kalshi_df["date"] = pd.to_datetime(kalshi_df["date"])
        df["game_date"] = pd.to_datetime(df["game_date"])
        kalshi_df = kalshi_df.rename(columns={"date": "game_date"})

        # Left-join on (game_date, home_team, away_team)
        kalshi_subset = kalshi_df[
            ["game_date", "home_team", "away_team", "kalshi_yes_price"]
        ].copy()

        df = df.merge(
            kalshi_subset,
            on=["game_date", "home_team", "away_team"],
            how="left",
        )

        return df

    def build_and_save_v2(
        self, output_path: str = "data/features/feature_store_v2.parquet"
    ) -> pd.DataFrame:
        """Build features and save as v2 feature store.

        Preserves v1 feature store unchanged. Saves v2 as a new file.
        """
        df = self.build()
        df.to_parquet(output_path, index=False)
        logger.info(
            "Saved feature_store_v2.parquet: %d games, %d columns",
            df.shape[0], df.shape[1],
        )
        return df
