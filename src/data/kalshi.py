"""Kalshi settled MLB per-game winner market loader.

Fetches individual game-winner markets from the KXMLBGAME series and
deduplicates to one row per game, keeping the HOME TEAM's YES market as the
canonical probability signal. This aligns kalshi_yes_price with the model's
home/away treatment: kalshi_yes_price = P(home wins) per Kalshi market.

Series: KXMLBGAME (per-game)  vs  KXMLB (season-long championship futures — wrong series)
Endpoint: GET /markets?status=settled&series_ticker=KXMLBGAME
Coverage: Apr 2025-present (~2,236 games, two raw markets each)
"""
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

# Month abbreviation → zero-padded number (Kalshi ticker month format)
_MONTH_MAP = {
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
    "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
    "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
}

# Parses the game-id portion of a KXMLBGAME ticker.
# Format: {YY}{MON}{DD}[{HHMM}]{AWAYCODE}{HOMECODE}[G{N}]
# HHMM is present for most regular-season games but absent for many
# playoff and some regular-season games — made optional with (?:\d{4})?.
# G{N} is a doubleheader suffix (G2 = second game) stripped before team split.
# Examples:
#   25APR161905NYYBOS  →  date=2025-04-16, time=19:05, teams=NYYBOS
#   25OCT31LADTOR      →  date=2025-10-31, no time,    teams=LADTOR
#   25SEP16ATLWSHG2    →  date=2025-09-16, no time,    teams=ATLWSH (G2 stripped)
_GAME_ID_RE = re.compile(
    r"^(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2})(?:\d{4})?(.+)$"
)


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


def _parse_ticker(ticker: str) -> dict:
    """Parse a KXMLBGAME ticker into game components.

    Ticker format: KXMLBGAME-{YY}{MON}{DD}{HHMM}{AWAYCODE}{HOMECODE}-{YESTEAM}
    Examples:
        KXMLBGAME-26MAR281420WSHCHC-CHC  →  WSH @ CHC, YES = CHC (home)
        KXMLBGAME-25APR151905NYYBOS-NYY  →  NYY @ BOS, YES = NYY (away)

    The YES team (ticker suffix) anchors the team-code split within the
    concatenated {AWAY}{HOME} string:
      - If teams_combined starts with yes_team → yes_team is away, remainder is home
      - If teams_combined ends with yes_team   → yes_team is home, remainder is away

    Returns dict with: date, game_id, away_code, home_code, yes_team
    Returns empty dict on parse failure (logged as warning).
    """
    # Split: ['KXMLBGAME', '{game_id}', '{yes_team}']
    parts = ticker.split("-", 2)
    if len(parts) != 3 or parts[0].upper() != "KXMLBGAME":
        return {}

    game_id = parts[1]   # e.g. '26MAR281420WSHCHC'
    yes_team = parts[2].upper()  # e.g. 'CHC'

    m = _GAME_ID_RE.match(game_id)
    if not m:
        logger.warning("Could not parse game_id from ticker %r", ticker)
        return {}

    year_2d, mon, day, teams_combined = m.groups()
    date_str = f"20{year_2d}-{_MONTH_MAP[mon]}-{day}"

    # Strip doubleheader/game-number suffix before splitting team codes.
    # Kalshi uses two formats: "ATLWSHG2" (explicit G prefix) and "MINATL2"
    # (bare digit). Pattern G?\d+ covers both without affecting alphabetic codes.
    t = re.sub(r"G?\d+$", "", teams_combined.upper())

    # Anchor split on yes_team
    if t.startswith(yes_team):
        away_code = yes_team
        home_code = t[len(yes_team):]
    elif t.endswith(yes_team):
        home_code = yes_team
        away_code = t[: len(t) - len(yes_team)]
    else:
        logger.warning(
            "Cannot split teams from ticker %r (teams=%r, yes_team=%r)",
            ticker, t, yes_team,
        )
        return {}

    if not away_code or not home_code:
        logger.warning("Empty team code in ticker %r (away=%r, home=%r)", ticker, away_code, home_code)
        return {}

    return {
        "date": date_str,
        "game_id": game_id,
        "away_code": away_code,
        "home_code": home_code,
        "yes_team": yes_team,
    }


def _is_mlb_game_winner(market: dict) -> bool:
    """Check if a market is a KXMLBGAME per-game MLB winner market.

    Primary check: KXMLBGAME series ticker prefix (server-side filtered in
    fetch_kalshi_markets, so this is a defensive guard only).
    Fallback: title-based detection for any markets not carrying the prefix.
    """
    ticker = (market.get("ticker") or "").upper()
    if "KXMLBGAME" in ticker:
        return True
    # Fallback: title-based detection
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
        "NO"  if the no-side won  (settlement < 0.5),
        None  if voided/postponed (empty settlement_value_dollars).

    NOTE: Do NOT silently code missing settlement as "NO" — voided/postponed
    games must be excluded from win-probability training, not mislabeled.
    """
    settlement_str = (market.get("settlement_value_dollars") or "").strip()
    if not settlement_str:
        return None   # Voided/postponed
    return "YES" if float(settlement_str) >= 0.5 else "NO"


def _parse_market(market: dict) -> dict | None:
    """Parse a raw KXMLBGAME market dict into an intermediate record.

    Returns a dict with:
        date, game_id, away_code, home_code, yes_team, is_home_yes,
        kalshi_yes_price, kalshi_no_price, result, market_ticker
    Returns None if the ticker cannot be parsed (logged as warning).
    """
    ticker = market.get("ticker", "")
    parsed = _parse_ticker(ticker)
    if not parsed:
        return None

    # PHASE 4 BLOCKER: last_price_dollars is the CLOSING price at market
    # settlement, NOT the pre-game opening price. Using it as a benchmark
    # introduces look-ahead bias — the price already reflects the outcome.
    # Resolve before Phase 4 evaluation: investigate candlestick/trade history
    # endpoint for pre-game price, or document the bias caveat explicitly.
    yes_price = float(market.get("last_price_dollars", "0") or "0")
    no_price = round(1.0 - yes_price, 4) if yes_price > 0 else 0.0

    return {
        "date": parsed["date"],
        "game_id": parsed["game_id"],
        "away_code": parsed["away_code"],
        "home_code": parsed["home_code"],
        "yes_team": parsed["yes_team"],
        "is_home_yes": parsed["yes_team"] == parsed["home_code"],
        "kalshi_yes_price": yes_price,
        "kalshi_no_price": no_price,
        "result": _parse_market_result(market),
        "market_ticker": ticker,
    }


def _safe_normalize(code: str) -> str:
    """Normalize a Kalshi team code, returning the raw code on failure.

    normalize_team() raises ValueError for unknown codes. This wrapper
    catches that so abstract playoff markers (NLHS, NLLS, ALHS, ALLS) and
    any future unknown Kalshi codes pass through as-is instead of crashing.
    Those rows will fail to join real game data in later phases, which is
    the correct silent-drop behaviour for abstract playoff series markers.
    """
    try:
        result = normalize_team(code)
        return result if result else code
    except ValueError:
        logger.debug("Unknown Kalshi team code %r — using raw code", code)
        return code


def _to_game_row(home_market: dict) -> dict:
    """Convert a home-team YES market record into the final output schema.

    Input is a record where is_home_yes=True, so:
        kalshi_yes_price = P(home team wins)
        result = "YES" if home team won, "NO" if away team won, None if voided

    Normalises raw Kalshi team codes to canonical 3-letter codes via team_mappings.
    Falls back to the raw code for unknown codes (e.g. abstract playoff markers).
    """
    home_team = _safe_normalize(home_market["home_code"])
    away_team = _safe_normalize(home_market["away_code"])
    return {
        "date": home_market["date"],
        "home_team": home_team,
        "away_team": away_team,
        "kalshi_yes_price": home_market["kalshi_yes_price"],
        "kalshi_no_price": home_market["kalshi_no_price"],
        "result": home_market["result"],
        "market_ticker": home_market["market_ticker"],
    }


def fetch_kalshi_markets(max_age_hours: float = 24) -> pd.DataFrame:
    """Fetch all settled Kalshi MLB per-game winner markets.

    Queries: GET /markets?status=settled&series_ticker=KXMLBGAME

    Each MLB game produces TWO Kalshi markets (one per team). This function
    deduplicates to ONE row per game by keeping the HOME TEAM's YES market as
    the canonical probability signal:
        kalshi_yes_price  = P(home wins)   per Kalshi closing price
        kalshi_no_price   = P(away wins)   = 1 - kalshi_yes_price
        result            = "YES" if home won, "NO" if away won, None if voided

    NOTE: Historical endpoint (/historical/markets) intentionally disabled.
    That endpoint has no server-side series_ticker filter and paginates ALL
    Kalshi markets across every category — unbounded (19+ minutes in testing).
    The live endpoint covers the full KXMLBGAME catalog (4,472 markets,
    Apr 2025–present). To re-enable: add a max_pages guard and a min_date
    filter anchored to the first KXMLBGAME market date.

    Args:
        max_age_hours: Re-fetch if cached file is older than this (default 24h).
                       Set 0 to force re-fetch; float('inf') to always use cache.

    Returns:
        DataFrame sorted by date with columns:
        date, home_team, away_team, kalshi_yes_price, kalshi_no_price,
        result, market_ticker
    """
    key = "kalshi_game_winners"
    parquet_path = "kalshi/kalshi_game_winners.parquet"

    # Staleness check — unlike pybaseball per-season files this cache grows
    # throughout the active season and must be periodically refreshed.
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

    # Step 1: Fetch all settled per-game markets (server-side filtered by series)
    raw = _paginate_endpoint("markets", {
        "status": "settled",
        "series_ticker": "KXMLBGAME",
    })
    print(f"KXMLBGAME: {len(raw)} raw markets fetched")

    # Step 2: Parse — drop markets with unparseable tickers
    parsed = []
    for m in raw:
        r = _parse_market(m)
        if r is not None:
            parsed.append(r)
    dropped = len(raw) - len(parsed)
    if dropped:
        logger.warning("%d markets dropped (unparseable tickers)", dropped)
    print(f"  {len(parsed)} parsed, {dropped} dropped")

    # Step 3: Keep only home-team YES markets (one per game).
    # Deduplicate by game_id to guard against pagination overlap (same market
    # on multiple pages) or any other source of duplicate raw markets.
    seen_game_ids: set = set()
    home_markets = []
    for p in parsed:
        if p["is_home_yes"] and p["game_id"] not in seen_game_ids:
            seen_game_ids.add(p["game_id"])
            home_markets.append(p)
    print(f"  {len(home_markets)} unique games (home-YES + game_id dedup)")

    # Step 4: Build output DataFrame
    rows = [_to_game_row(m) for m in home_markets]
    df = pd.DataFrame(rows)

    if df.empty:
        logger.warning("No KXMLBGAME markets found — returning empty DataFrame")
        return df

    df = df.sort_values("date").reset_index(drop=True)
    save_to_cache(df, key, parquet_path, season=2025)
    return df


def fetch_kalshi_open_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Fetch pre-game opening prices via Kalshi batch candlestick API.

    Groups markets by date and makes one batch GET /markets/candlesticks
    call per date (187 unique dates for 2025 season). Uses daily candles
    (period_interval=1440) and extracts price.open_dollars (first trade
    price of the day).

    Args:
        df: DataFrame from fetch_kalshi_markets() with 'market_ticker' and
            'date' columns.

    Returns:
        Same DataFrame with 'kalshi_open_price' column added.
        NaN where no candlestick data exists (no trades occurred).
    """
    from datetime import timedelta, timezone

    if df.empty or "market_ticker" not in df.columns:
        df["kalshi_open_price"] = pd.Series(dtype=float)
        return df

    headers = _get_headers()
    open_prices = {}  # ticker -> open_price_dollars

    # Group tickers by date for batch fetching
    grouped = df.groupby("date")["market_ticker"].apply(list).to_dict()
    total_dates = len(grouped)

    for i, (game_date, tickers) in enumerate(sorted(grouped.items()), 1):
        dt = datetime.strptime(game_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        start_ts = int(dt.timestamp())
        end_ts = int((dt + timedelta(hours=30)).timestamp())  # captures midnight-ET boundary

        try:
            resp = requests.get(
                f"{BASE_URL}/markets/candlesticks",
                params={
                    "market_tickers": ",".join(tickers),
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "period_interval": 1440,
                },
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            for m in data.get("markets", []):
                ticker = m["market_ticker"]
                candles = m.get("candlesticks", [])
                if candles and candles[0].get("price", {}).get("open_dollars") is not None:
                    open_prices[ticker] = float(candles[0]["price"]["open_dollars"])
                # else: no candle data, stays absent -> NaN

        except requests.RequestException as e:
            logger.warning("Candlestick fetch failed for date %s: %s", game_date, e)

        if i % 20 == 0 or i == total_dates:
            logger.info("Candlestick fetch progress: %d/%d dates", i, total_dates)

        time.sleep(RATE_LIMIT_DELAY)

    # Map ticker -> open price, NaN for missing
    df = df.copy()
    df["kalshi_open_price"] = df["market_ticker"].map(open_prices).astype(float)

    n_found = df["kalshi_open_price"].notna().sum()
    n_missing = df["kalshi_open_price"].isna().sum()
    logger.info(
        "Open prices: %d found, %d missing (%.1f%% coverage)",
        n_found, n_missing, 100 * n_found / len(df) if len(df) > 0 else 0,
    )

    return df
