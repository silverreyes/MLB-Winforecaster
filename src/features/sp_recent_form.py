"""SP recent form loader using the MLB Stats API.

Replaces pybaseball.pitching_stats_range(), which scraped Baseball Reference.
BRef (and FanGraphs' equivalent endpoint) are now behind Cloudflare JS-challenge
and return HTTP 403 for all programmatic requests.

Strategy:
  1. Build a name→playerID map for the season via sports_players (1 API call).
  2. For each SP who appears as a probable starter, fetch their full-season
     per-game pitching log via the person/hydrate endpoint (1 call per pitcher,
     cached per pitcher-season).
  3. For each game_date, slice each pitcher's log to the 30-day window
     [date-31, date-1] and compute ERA = (ER * 9) / IP.

Output matches the interface expected by FeatureBuilder._add_advanced_features:
    fetch_sp_recent_form_bulk(game_dates, season, sp_names) ->
        dict[date_str, DataFrame(Name, ERA)]

MLB Stats API innings-pitched strings use "X.Y" where Y is outs (0/1/2),
so "5.2" = 5 + 2/3 innings = 5.667. _parse_ip() converts this correctly.
"""

import time
import logging
import pandas as pd
import statsapi
from datetime import datetime, timedelta
from src.data.cache import is_cached, save_to_cache, read_cached

logger = logging.getLogger(__name__)

RATE_LIMIT_DELAY = 0.3  # seconds between MLB Stats API requests

# ---------------------------------------------------------------------------
# v2 extended game log constants
# ---------------------------------------------------------------------------

V2_GAME_LOG_COLS = [
    "date", "innings_pitched", "earned_runs",
    "strikeouts", "base_on_balls", "home_runs",
    "number_of_pitches", "games_started",
]

LEAGUE_AVG_PITCH_COUNT = 93  # League average pitches per start (imputation)
MAX_DAYS_REST = 7            # Cap days rest at 7 (anything longer is treated as 7)


# ---------------------------------------------------------------------------
# Innings-pitched string parser
# ---------------------------------------------------------------------------

def _parse_ip(ip_str) -> float:
    """Convert MLB API innings-pitched string to fractional innings.

    "5.2" → 5 + 2/3 = 5.667  (Y is outs, not tenths)
    "5.0" → 5.0
    "0.1" → 0.333
    """
    try:
        ip = float(ip_str)
        whole = int(ip)
        outs = round((ip - whole) * 10)  # 0, 1, or 2
        return whole + outs / 3.0
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Step 1 — pitcher name → MLB player ID map (one call per season)
# ---------------------------------------------------------------------------

def _get_pitcher_id_map(season: int) -> dict[str, int]:
    """Return {fullName: playerId} for all pitchers active in a season.

    Cached as pitcher_id_map_{season} (Parquet with columns name, player_id).
    One API call per season.
    """
    key = f"pitcher_id_map_{season}"
    parquet_path = f"mlb_api/pitcher_id_map_{season}.parquet"

    if is_cached(key):
        df = read_cached(key)
        return dict(zip(df["name"], df["player_id"]))

    result = statsapi.get("sports_players", {"season": season, "sportId": 1})
    players = result.get("people", [])

    rows = [
        {"name": p["fullName"], "player_id": p["id"]}
        for p in players
        if p.get("primaryPosition", {}).get("type") == "Pitcher"
    ]
    df = pd.DataFrame(rows)
    save_to_cache(df, key, parquet_path, season)
    logger.info("Built pitcher ID map for %d: %d pitchers", season, len(df))
    return dict(zip(df["name"], df["player_id"]))


# ---------------------------------------------------------------------------
# Step 2 — per-pitcher season game log (one call per pitcher-season)
# ---------------------------------------------------------------------------

def _fetch_pitcher_game_log(player_id: int, season: int) -> pd.DataFrame:
    """Return per-game pitching stats for one pitcher in one season.

    Cached as pitcher_game_log_{season}_{player_id}.
    Columns: date (datetime), innings_pitched (float), earned_runs (int).
    """
    key = f"pitcher_game_log_{season}_{player_id}"
    parquet_path = f"mlb_api/pitcher_game_log_{season}_{player_id}.parquet"

    if is_cached(key):
        df = read_cached(key)
        df["date"] = pd.to_datetime(df["date"])
        return df

    try:
        result = statsapi.get(
            "person",
            {
                "personId": player_id,
                "hydrate": f"stats(type=gameLog,group=pitching,season={season})",
            },
        )
        people = result.get("people", [])
        if not people:
            return pd.DataFrame(columns=["date", "innings_pitched", "earned_runs"])

        stats_list = people[0].get("stats", [])
        if not stats_list:
            return pd.DataFrame(columns=["date", "innings_pitched", "earned_runs"])

        splits = stats_list[0].get("splits", [])
        rows = []
        for s in splits:
            stat = s.get("stat", {})
            rows.append({
                "date": pd.to_datetime(s.get("date")),
                "innings_pitched": _parse_ip(stat.get("inningsPitched", "0.0")),
                "earned_runs": int(stat.get("earnedRuns", 0)),
            })
        df = pd.DataFrame(rows) if rows else pd.DataFrame(
            columns=["date", "innings_pitched", "earned_runs"]
        )
        save_to_cache(df, key, parquet_path, season)
        return df

    except Exception as e:
        logger.debug("No game log for player %d season %d: %s", player_id, season, e)
        return pd.DataFrame(columns=["date", "innings_pitched", "earned_runs"])


# ---------------------------------------------------------------------------
# Step 2b — per-pitcher season game log v2 (extended fields for SP features)
# ---------------------------------------------------------------------------

def _fetch_pitcher_game_log_v2(player_id: int, season: int) -> pd.DataFrame:
    """Return per-game pitching stats with extended fields for one pitcher in one season.

    Cached as pitcher_game_log_v2_{season}_{player_id} (distinct from v1 cache).
    Columns: date, innings_pitched, earned_runs, strikeouts, base_on_balls,
             home_runs, number_of_pitches, games_started.
    """
    key = f"pitcher_game_log_v2_{season}_{player_id}"
    parquet_path = f"mlb_api/pitcher_game_log_v2_{season}_{player_id}.parquet"

    if is_cached(key):
        df = read_cached(key)
        df["date"] = pd.to_datetime(df["date"])
        return df

    try:
        result = statsapi.get(
            "person",
            {
                "personId": player_id,
                "hydrate": f"stats(type=gameLog,group=pitching,season={season})",
            },
        )
        people = result.get("people", [])
        if not people:
            return pd.DataFrame(columns=V2_GAME_LOG_COLS)

        stats_list = people[0].get("stats", [])
        if not stats_list:
            return pd.DataFrame(columns=V2_GAME_LOG_COLS)

        splits = stats_list[0].get("splits", [])
        rows = []
        for s in splits:
            stat = s.get("stat", {})
            rows.append({
                "date": pd.to_datetime(s.get("date")),
                "innings_pitched": _parse_ip(stat.get("inningsPitched", "0.0")),
                "earned_runs": int(stat.get("earnedRuns", 0)),
                "strikeouts": int(stat.get("strikeOuts", 0)),
                "base_on_balls": int(stat.get("baseOnBalls", 0)),
                "home_runs": int(stat.get("homeRuns", 0)),
                "number_of_pitches": int(stat.get("numberOfPitches", 0)),
                "games_started": int(stat.get("gamesStarted", 0)),
            })
        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=V2_GAME_LOG_COLS)
        save_to_cache(df, key, parquet_path, season)
        return df

    except Exception as e:
        logger.debug("No v2 game log for player %d season %d: %s", player_id, season, e)
        return pd.DataFrame(columns=V2_GAME_LOG_COLS)


# ---------------------------------------------------------------------------
# Step 3 — compute rolling ERA for a set of dates (public interface)
# ---------------------------------------------------------------------------

def fetch_sp_recent_form_bulk(
    game_dates: list[str],
    season: int,
    sp_names: set[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Compute 30-day rolling ERA for each pitcher on each game date.

    Args:
        game_dates: List of game dates (YYYY-MM-DD). Deduplicated internally.
        season: MLB season year.
        sp_names: Optional set of pitcher full names to look up. If None,
            all pitchers in the season are used (expensive — pass sp_names).

    Returns:
        dict mapping date_str -> DataFrame with columns [Name, ERA].
        ERA is NaN-free; pitchers with zero IP in the window are excluded.
    """
    unique_dates = sorted(set(game_dates))

    # --- 1. Name → ID map ---
    id_map = _get_pitcher_id_map(season)

    # --- 2. Filter to only the SPs we need ---
    if sp_names:
        relevant = {name: id_map[name] for name in sp_names if name in id_map}
        missing = sp_names - set(id_map.keys())
        if missing:
            logger.debug(
                "%d SP names not found in %d ID map: %s",
                len(missing), season, sorted(missing)[:5]
            )
    else:
        relevant = id_map

    # --- 3. Fetch / load pitcher game logs ---
    fetched = 0
    game_logs: dict[str, pd.DataFrame] = {}
    for name, pid in relevant.items():
        log_key = f"pitcher_game_log_{season}_{pid}"
        if not is_cached(log_key):
            time.sleep(RATE_LIMIT_DELAY)
            fetched += 1
        log = _fetch_pitcher_game_log(pid, season)
        if not log.empty:
            game_logs[name] = log

    if fetched:
        logger.info(
            "Fetched %d pitcher game logs for season %d (%d total SPs)",
            fetched, season, len(relevant)
        )

    # --- 4. Compute rolling ERA per date ---
    results: dict[str, pd.DataFrame] = {}
    for date_str in unique_dates:
        date_dt = pd.to_datetime(date_str)
        window_start = date_dt - timedelta(days=31)
        rows = []
        for name, log in game_logs.items():
            if log.empty:
                continue
            window = log[
                (log["date"] >= window_start) & (log["date"] < date_dt)
            ]
            if window.empty:
                continue
            total_ip = window["innings_pitched"].sum()
            total_er = window["earned_runs"].sum()
            if total_ip > 0:
                era = (total_er * 9.0) / total_ip
                rows.append({"Name": name, "ERA": era})
        results[date_str] = pd.DataFrame(rows, columns=["Name", "ERA"])

    return results


# ---------------------------------------------------------------------------
# Step 4 — compute rolling FIP for a set of dates (SP-07)
# ---------------------------------------------------------------------------

def compute_rolling_fip_bulk(
    game_dates: list[str],
    season: int,
    sp_names: set[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Compute 30-day rolling raw FIP for each pitcher on each game date.

    Raw FIP = ((13*HR) + (3*BB) - (2*K)) / IP
    No cFIP constant needed -- cancels in home-away differentials.

    Args:
        game_dates: List of game dates (YYYY-MM-DD). Deduplicated internally.
        season: MLB season year.
        sp_names: Optional set of pitcher full names to look up.

    Returns:
        dict mapping date_str -> DataFrame with columns [Name, FIP].
        FIP is NaN-free; pitchers with zero IP in the window are excluded.
    """
    unique_dates = sorted(set(game_dates))

    # --- 1. Name -> ID map ---
    id_map = _get_pitcher_id_map(season)

    # --- 2. Filter to only the SPs we need ---
    if sp_names:
        relevant = {name: id_map[name] for name in sp_names if name in id_map}
    else:
        relevant = id_map

    # --- 3. Fetch / load v2 pitcher game logs ---
    fetched = 0
    game_logs: dict[str, pd.DataFrame] = {}
    for name, pid in relevant.items():
        v2_key = f"pitcher_game_log_v2_{season}_{pid}"
        if not is_cached(v2_key):
            time.sleep(RATE_LIMIT_DELAY)
            fetched += 1
        log = _fetch_pitcher_game_log_v2(pid, season)
        if not log.empty:
            game_logs[name] = log

    if fetched:
        logger.info(
            "Fetched %d v2 pitcher game logs for FIP (season %d, %d total SPs)",
            fetched, season, len(relevant),
        )

    # --- 4. Compute rolling FIP per date ---
    results: dict[str, pd.DataFrame] = {}
    for date_str in unique_dates:
        date_dt = pd.to_datetime(date_str)
        window_start = date_dt - timedelta(days=31)
        rows = []
        for name, log in game_logs.items():
            if log.empty:
                continue
            window = log[
                (log["date"] >= window_start) & (log["date"] < date_dt)
            ]
            if window.empty:
                continue
            sum_ip = window["innings_pitched"].sum()
            if sum_ip > 0:
                sum_hr = window["home_runs"].sum()
                sum_bb = window["base_on_balls"].sum()
                sum_k = window["strikeouts"].sum()
                raw_fip = ((13 * sum_hr) + (3 * sum_bb) - (2 * sum_k)) / sum_ip
                rows.append({"Name": name, "FIP": raw_fip})
        results[date_str] = pd.DataFrame(rows, columns=["Name", "FIP"])

    return results


# ---------------------------------------------------------------------------
# Step 5 — compute pitch count and days rest for a set of dates (SP-08)
# ---------------------------------------------------------------------------

def compute_pitch_count_and_rest_bulk(
    game_dates: list[str],
    season: int,
    sp_names: set[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Compute pitch count from last start and days rest for each pitcher.

    Args:
        game_dates: List of game dates (YYYY-MM-DD). Deduplicated internally.
        season: MLB season year.
        sp_names: Optional set of pitcher full names to look up.

    Returns:
        dict mapping date_str -> DataFrame with columns
                 [Name, pitch_count_last, days_rest].
        pitch_count_last: numberOfPitches from most recent start before this date.
            Imputed to LEAGUE_AVG_PITCH_COUNT (93) if no prior start.
        days_rest: integer days since last start, capped at MAX_DAYS_REST (7).
            Set to MAX_DAYS_REST if no prior start found.
    """
    unique_dates = sorted(set(game_dates))

    # --- 1. Name -> ID map ---
    id_map = _get_pitcher_id_map(season)

    # --- 2. Filter to only the SPs we need ---
    if sp_names:
        relevant = {name: id_map[name] for name in sp_names if name in id_map}
    else:
        relevant = id_map

    # --- 3. Fetch / load v2 pitcher game logs ---
    fetched = 0
    game_logs: dict[str, pd.DataFrame] = {}
    for name, pid in relevant.items():
        v2_key = f"pitcher_game_log_v2_{season}_{pid}"
        if not is_cached(v2_key):
            time.sleep(RATE_LIMIT_DELAY)
            fetched += 1
        log = _fetch_pitcher_game_log_v2(pid, season)
        if not log.empty:
            game_logs[name] = log

    if fetched:
        logger.info(
            "Fetched %d v2 pitcher game logs for pitch count/rest (season %d, %d total SPs)",
            fetched, season, len(relevant),
        )

    # --- 4. Compute pitch count and days rest per date ---
    results: dict[str, pd.DataFrame] = {}
    for date_str in unique_dates:
        date_dt = pd.to_datetime(date_str)
        rows = []
        for name, log in game_logs.items():
            if log.empty:
                continue
            # Find starts (games_started >= 1) BEFORE this date
            starts = log[(log["date"] < date_dt) & (log["games_started"] >= 1)]
            if not starts.empty:
                last_start = starts.iloc[-1]  # log is sorted by date
                pitch_count_last = int(last_start["number_of_pitches"])
                days_gap = (date_dt - last_start["date"]).days
                days_rest = min(days_gap, MAX_DAYS_REST)
            else:
                # Cold start: no prior start found
                pitch_count_last = LEAGUE_AVG_PITCH_COUNT
                days_rest = MAX_DAYS_REST
            rows.append({
                "Name": name,
                "pitch_count_last": pitch_count_last,
                "days_rest": days_rest,
            })
        results[date_str] = pd.DataFrame(
            rows, columns=["Name", "pitch_count_last", "days_rest"]
        )

    return results
