"""Kalshi settled MLB game-winner market loader (live endpoint only)."""
import logging
import os
import re
import time

import pandas as pd
import requests
from datetime import datetime

from src.data.cache import is_cached, save_to_cache, read_cached, load_manifest, CACHE_DIR
from src.data.team_mappings import normalize_team

logger = logging.getLogger(__name__)

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
RATE_LIMIT_DELAY = 0.1  # 100ms between requests (stays under 20 req/sec Basic tier)


def _get_headers() -> dict:
    """Build request headers. Uses KALSHI_API_KEY if set, otherwise no auth."""
    headers = {"Accept": "application/json"}
    api_key = os.environ.get("KALSHI_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _paginate_endpoint(endpoint: str, params: dict) -> list:
    """Paginate through all results from a Kalshi API endpoint.
    Returns list of market dicts."""
    all_markets = []
    cursor = None
    headers = _get_headers()
    while True:
        req_params = {**params, "limit": 1000}
        if cursor:
            req_params["cursor"] = cursor
        resp = requests.get(
            f"{BASE_URL}/{endpoint}",
            params=req_params,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        markets = data.get("markets", [])
        if not markets:
            break
        all_markets.extend(markets)
        cursor = data.get("cursor")
        if not cursor:
            break
        time.sleep(RATE_LIMIT_DELAY)
    return all_markets


def _is_mlb_game_winner(market: dict) -> bool:
    """Check if a market is an MLB individual game-winner market based on ticker/title."""
    ticker = (market.get("ticker") or "").upper()
    # KXMLB is the confirmed MLB game-winner series ticker prefix -- primary indicator
    if "KXMLB" in ticker:
        return True
    # Fallback: title-based detection for markets not carrying KXMLB prefix
    # Check for MLB + game-action keywords; avoids inverted string logic
    title = (market.get("title") or "").upper()
    subtitle = (market.get("subtitle") or "").upper()
    combined = title + subtitle
    has_mlb = "MLB" in combined
    has_game_action = any(kw in combined for kw in ["WIN", "WINNER", "BEAT", "DEFEAT"])
    return has_mlb and has_game_action


def _parse_market_result(market: dict):
    """Parse market settlement outcome.

    Returns:
        "YES" if the yes-side won (settlement >= 0.5),
        "NO" if the no-side won (settlement < 0.5),
        None if voided/postponed (empty settlement_value_dollars).
    """
    # settlement_value_dollars: "1" = YES won, "0" = NO won, "" = voided/unresolved
    # Explicit None for unresolved markets (postponed games, voids) -- do NOT
    # silently code missing settlement as "NO" which would corrupt the win labels.
    settlement_str = (market.get("settlement_value_dollars") or "").strip()
    if not settlement_str:
        result = None  # Voided/postponed -- exclude from win-probability training
    elif float(settlement_str) >= 0.5:
        result = "YES"
    else:
        result = "NO"
    return result


def _parse_teams_from_title(title: str, subtitle: str) -> tuple:
    """Best-effort team extraction from Kalshi market title/subtitle.

    Common patterns:
    - "Will the Yankees beat the Red Sox?"
    - "Yankees vs Red Sox"

    Returns:
        (home_team, away_team) as raw strings (pre-normalization), or (None, None)
        if unparseable. Note: Kalshi titles typically frame the question as
        "Will {TeamA} beat {TeamB}?" where TeamA is often the favored or home team,
        but this is not guaranteed. We assign the first team as away and second as
        home following the "visitor @ home" convention, but this is best-effort.
    """
    # Pattern 1: "Will the {TeamA} beat the {TeamB}?"
    match = re.search(
        r"[Ww]ill\s+(?:the\s+)?(.+?)\s+(?:beat|defeat)\s+(?:the\s+)?(.+?)[\?\.]",
        title,
    )
    if match:
        team_a = match.group(1).strip()
        team_b = match.group(2).strip()
        # In "Will A beat B?" framing, A is typically away, B is home
        return team_b, team_a

    # Pattern 2: "{TeamA} vs {TeamB}" in title or subtitle
    combined = title + " " + subtitle
    match = re.search(
        r"(.+?)\s+(?:vs\.?|versus)\s+(.+?)(?:\s*[\?\.\-]|$)",
        combined,
        re.IGNORECASE,
    )
    if match:
        team_a = match.group(1).strip()
        team_b = match.group(2).strip()
        return team_b, team_a

    logger.warning("Could not parse teams from title: %r", title)
    return None, None


def _parse_market(market: dict) -> dict:
    """Parse a raw Kalshi market dict into our standard format.
    Returns dict with: date, home_team, away_team, kalshi_yes_price, kalshi_no_price,
                       result, market_ticker, title, subtitle"""
    # Parse date from close_time or expiration_time
    date_str = None
    for field in ["close_time", "expected_expiration_time", "expiration_time"]:
        val = market.get(field)
        if val:
            # ISO format: "2025-07-15T23:59:59Z"
            date_str = val[:10]  # Extract YYYY-MM-DD
            break

    # Parse prices -- dollar-denominated strings (Pitfall 8)
    # PHASE 4 BLOCKER: last_price_dollars is the CLOSING price (at market settlement),
    # NOT the pre-game opening price. Using it for benchmark comparison introduces
    # look-ahead bias -- the market already knows the outcome by settlement.
    # TODO: Investigate Kalshi API for pre-game price (e.g., candlestick/trade history
    # endpoint for the price at game start time). If unavailable via API, document
    # clearly and use the closing price with an explicit look-ahead bias caveat.
    # This must be resolved before Phase 4 benchmark evaluation is meaningful.
    yes_price = float(market.get("last_price_dollars", "0") or "0")
    no_price = 1.0 - yes_price if yes_price > 0 else 0.0

    # Parse settlement result
    result = _parse_market_result(market)

    # Parse teams from title
    title = market.get("title", "")
    subtitle = market.get("subtitle", "")
    home_team, away_team = _parse_teams_from_title(title, subtitle)

    return {
        "date": date_str,
        "home_team": home_team,
        "away_team": away_team,
        "kalshi_yes_price": yes_price,
        "kalshi_no_price": no_price,
        "result": result,
        "market_ticker": market.get("ticker", ""),
        "title": title,  # Keep for debugging/manual team resolution
        "subtitle": subtitle,
    }


def fetch_kalshi_markets(max_age_hours: float = 24) -> pd.DataFrame:
    """Fetch all settled Kalshi MLB game-winner markets from the live endpoint.

    Unlike per-season pybaseball files (immutable once a season ends), this file
    grows throughout the 2025 season and must be periodically refreshed.

    Args:
        max_age_hours: Re-fetch if cached file is older than this many hours.
                       Default 24h. Set to 0 to force re-fetch; float('inf') to
                       always use cache regardless of age.

    Queries ONLY the live endpoint:
    GET /markets?status=settled&series_ticker=KXMLB

    Returns DataFrame with columns:
    date, home_team, away_team, kalshi_yes_price, kalshi_no_price, result, market_ticker
    """
    key = "kalshi_game_winners"
    parquet_path = "kalshi/kalshi_game_winners.parquet"

    # Staleness check: Kalshi file grows as 2025 season progresses; re-fetch if stale.
    # Unlike pybaseball files, this is NOT a permanent cache -- it needs periodic refresh.
    if is_cached(key):
        manifest = load_manifest()
        fetch_date_str = manifest[key].get("fetch_date", "")
        if fetch_date_str:
            fetch_dt = datetime.fromisoformat(fetch_date_str)
            age_hours = (datetime.now() - fetch_dt).total_seconds() / 3600
            if age_hours < max_age_hours:
                return read_cached(key)
        else:
            return read_cached(key)

    # NOTE: Historical endpoint (/historical/markets) intentionally disabled.
    # The historical endpoint has no server-side series_ticker filter -- it paginates
    # ALL of Kalshi's archived markets across every category (politics, crypto, etc.),
    # making it unbounded and impractical (19+ minutes observed in testing).
    # The live endpoint is sufficient because the historical cutoff (2025-12-28) is
    # AFTER the 2025 MLB season ended -- all 2025 MLB settled markets are returned here.
    # To re-enable: add a max_pages guard (e.g., max_pages=5) and filter by
    # min_date >= first Kalshi MLB market date before calling historical endpoint.

    # Fetch settled MLB markets from live endpoint (supports series_ticker filter)
    recent = _paginate_endpoint("markets", {
        "status": "settled",
        "series_ticker": "KXMLB",
    })
    print(f"Live endpoint: {len(recent)} markets fetched")

    # Deduplicate by ticker (safety guard for future-proofing if endpoint
    # ever returns overlapping results across pages)
    seen_tickers = set()
    unique_markets = []
    for m in recent:
        ticker = m.get("ticker", "")
        if ticker and ticker not in seen_tickers:
            seen_tickers.add(ticker)
            unique_markets.append(m)

    # Parse into standard format
    parsed = [_parse_market(m) for m in unique_markets]
    df = pd.DataFrame(parsed)

    # Normalize team names where parseable
    if "home_team" in df.columns:
        df["home_team"] = df["home_team"].apply(
            lambda x: normalize_team(x) if pd.notna(x) and x else x
        )
    if "away_team" in df.columns:
        df["away_team"] = df["away_team"].apply(
            lambda x: normalize_team(x) if pd.notna(x) and x else x
        )

    # Cache as single file (not per-season -- Kalshi data is 2025 only)
    save_to_cache(df, key, parquet_path, season=2025)
    return df
