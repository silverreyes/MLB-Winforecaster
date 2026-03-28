"""Tests for Kalshi market data loader (DATA-06).

Covers: _parse_ticker(), _parse_market_result(), _is_mlb_game_winner(),
        fetch_kalshi_markets() dedup/schema/caching, and _to_game_row().

Key invariant: fetch_kalshi_markets() returns ONE row per game, using the
HOME TEAM's YES market as the canonical probability signal.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

kalshi = pytest.importorskip("src.data.kalshi")

# ---------------------------------------------------------------------------
# Sample market data — NYY @ BOS, Apr 15 2025, 19:05 EDT, BOS won
# Ticker format: KXMLBGAME-{YY}{MON}{DD}{HHMM}{AWAY}{HOME}-{YESTEAM}
# ---------------------------------------------------------------------------
SAMPLE_HOME_MARKET = {
    # Home team (BOS) YES market — this is the one we KEEP
    "ticker": "KXMLBGAME-25APR151905NYYBOS-BOS",
    "title": "New York Y vs Boston Winner?",
    "subtitle": "",
    "status": "settled",
    "close_time": "2025-04-15T23:05:00Z",
    "settlement_value_dollars": "1.0000",   # BOS won → YES
    "last_price_dollars": "0.5500",
    "result": "yes",
}

SAMPLE_AWAY_MARKET = {
    # Away team (NYY) YES market — DROPPED by dedup (not home YES)
    "ticker": "KXMLBGAME-25APR151905NYYBOS-NYY",
    "title": "New York Y vs Boston Winner?",
    "subtitle": "",
    "status": "settled",
    "close_time": "2025-04-15T23:05:00Z",
    "settlement_value_dollars": "0.0000",   # NYY lost → NO
    "last_price_dollars": "0.4500",
    "result": "no",
}

# Voided game — used only for _parse_market_result() unit test
SAMPLE_MARKET_VOIDED = {
    "ticker": "KXMLBGAME-25APR291830LADSFG-SFG",
    "title": "Los Angeles D vs San Francisco Winner?",
    "subtitle": "",
    "status": "settled",
    "close_time": "2025-04-29T22:30:00Z",
    "settlement_value_dollars": "",   # postponed/voided
    "last_price_dollars": "0.5500",
    "result": "",
}

SAMPLE_API_RESPONSE = {
    "markets": [SAMPLE_HOME_MARKET, SAMPLE_AWAY_MARKET],
    "cursor": None,
}


def _make_mock_response(json_data):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.raise_for_status = MagicMock()
    return mock


def _setup_mock(mock_get):
    """Single live-endpoint call returning home + away market for one game."""
    mock_get.side_effect = [_make_mock_response(SAMPLE_API_RESPONSE)]


# ===========================================================================
# _parse_ticker — unit tests
# ===========================================================================

def test_parse_ticker_home_is_yes():
    """Home-team-YES ticker: away=NYY, home=BOS, date parsed correctly."""
    r = kalshi._parse_ticker("KXMLBGAME-25APR151905NYYBOS-BOS")
    assert r["date"] == "2025-04-15"
    assert r["away_code"] == "NYY"
    assert r["home_code"] == "BOS"
    assert r["yes_team"] == "BOS"
    assert r["game_id"] == "25APR151905NYYBOS"


def test_parse_ticker_away_is_yes():
    """Away-team-YES ticker: same away/home split, yes_team is away."""
    r = kalshi._parse_ticker("KXMLBGAME-25APR151905NYYBOS-NYY")
    assert r["date"] == "2025-04-15"
    assert r["away_code"] == "NYY"
    assert r["home_code"] == "BOS"
    assert r["yes_team"] == "NYY"


def test_parse_ticker_short_home_code():
    """Two-character home code (SD) splits correctly."""
    r = kalshi._parse_ticker("KXMLBGAME-25APR161830CHCSD-SD")
    assert r["away_code"] == "CHC"
    assert r["home_code"] == "SD"
    assert r["yes_team"] == "SD"


def test_parse_ticker_short_away_code():
    """Two-character away code (TB) splits correctly."""
    r = kalshi._parse_ticker("KXMLBGAME-25APR161415TBSTL-STL")
    assert r["away_code"] == "TB"
    assert r["home_code"] == "STL"
    assert r["yes_team"] == "STL"


def test_parse_ticker_invalid_prefix_returns_empty():
    """Non-KXMLBGAME tickers return empty dict."""
    assert kalshi._parse_ticker("KXMLB-25-NYY") == {}
    assert kalshi._parse_ticker("NOTGAME-25APR15NYYBOS-BOS") == {}
    assert kalshi._parse_ticker("") == {}


def test_parse_ticker_wrong_part_count_returns_empty():
    """Ticker with wrong number of dash-separated parts returns empty dict."""
    assert kalshi._parse_ticker("KXMLBGAME-25APR151905NYYBOS") == {}


# ===========================================================================
# _parse_market_result — unit tests
# ===========================================================================

def test_parse_market_result_yes():
    """Settlement value 1.0000 maps to 'YES'."""
    assert kalshi._parse_market_result({"settlement_value_dollars": "1.0000"}) == "YES"


def test_parse_market_result_no():
    """Settlement value 0.0000 maps to 'NO'."""
    assert kalshi._parse_market_result({"settlement_value_dollars": "0.0000"}) == "NO"


def test_kalshi_voided_market_result_is_none():
    """Empty settlement_value_dollars → None (not 'NO').

    Voided/cancelled markets must not be silently coded as NO outcomes —
    that would corrupt win labels in the training set.
    """
    result = kalshi._parse_market_result(SAMPLE_MARKET_VOIDED)
    assert result is None, (
        f"Voided market should return None, got {result!r}"
    )


# ===========================================================================
# _is_mlb_game_winner — unit tests
# ===========================================================================

def test_is_mlb_game_winner_kxmlbgame_ticker():
    """KXMLBGAME prefix is the primary positive indicator."""
    market = {"ticker": "KXMLBGAME-25APR151905NYYBOS-BOS", "title": "", "subtitle": ""}
    assert kalshi._is_mlb_game_winner(market) is True


def test_is_mlb_game_winner_rejects_non_mlb():
    """Non-MLB markets (e.g., political) are rejected."""
    market = {"ticker": "KXPRES-2025", "title": "Will candidate X win?", "subtitle": ""}
    assert kalshi._is_mlb_game_winner(market) is False


def test_is_mlb_game_winner_fallback_title():
    """Fallback title matching catches markets without KXMLBGAME prefix."""
    market = {
        "ticker": "UNKNOWN-123",
        "title": "Will the Yankees beat the Red Sox?",
        "subtitle": "MLB game",
    }
    assert kalshi._is_mlb_game_winner(market) is True


# ===========================================================================
# fetch_kalshi_markets — integration-style tests (mocked HTTP)
# ===========================================================================

@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_fetch_returns_one_row_per_game(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """Two markets for the same game (home + away) deduplicate to exactly 1 row."""
    _setup_mock(mock_get)
    result = kalshi.fetch_kalshi_markets()
    assert len(result) == 1, f"Expected 1 row after dedup, got {len(result)}"


@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_fetch_keeps_home_yes_market(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """The kept row uses the HOME team's market price and result."""
    _setup_mock(mock_get)
    result = kalshi.fetch_kalshi_markets()
    row = result.iloc[0]
    # BOS is home; home market had last_price=0.55 and settlement=YES
    assert row["kalshi_yes_price"] == pytest.approx(0.55)
    assert row["result"] == "YES"
    assert row["market_ticker"] == "KXMLBGAME-25APR151905NYYBOS-BOS"


@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_kalshi_has_required_columns(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """Output DataFrame has the Phase 4 required schema."""
    _setup_mock(mock_get)
    result = kalshi.fetch_kalshi_markets()
    required = ["date", "home_team", "away_team",
                "kalshi_yes_price", "kalshi_no_price", "result", "market_ticker"]
    for col in required:
        assert col in result.columns, f"Missing required column: {col}"


@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_kalshi_prices_are_floats(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """Price columns are numeric float dtype."""
    _setup_mock(mock_get)
    result = kalshi.fetch_kalshi_markets()
    assert pd.api.types.is_float_dtype(result["kalshi_yes_price"])
    assert pd.api.types.is_float_dtype(result["kalshi_no_price"])


@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_kalshi_yes_price_is_home_probability(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """kalshi_yes_price + kalshi_no_price sum to ~1.0 (home + away prob)."""
    _setup_mock(mock_get)
    result = kalshi.fetch_kalshi_markets()
    row = result.iloc[0]
    total = row["kalshi_yes_price"] + row["kalshi_no_price"]
    assert total == pytest.approx(1.0, abs=0.001)


@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_kalshi_teams_are_normalized(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """Team values are canonical codes from team_mappings (or raw fallback)."""
    from src.data.team_mappings import TEAM_MAP
    _setup_mock(mock_get)
    result = kalshi.fetch_kalshi_markets()
    canonical_codes = set(TEAM_MAP.values())
    for _, row in result.iterrows():
        if pd.notna(row["home_team"]) and row["home_team"]:
            assert row["home_team"] in canonical_codes, (
                f"home_team '{row['home_team']}' not a canonical code"
            )
        if pd.notna(row["away_team"]) and row["away_team"]:
            assert row["away_team"] in canonical_codes, (
                f"away_team '{row['away_team']}' not a canonical code"
            )


@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_kalshi_caches_to_parquet(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """After fetch, result is cached under 'kalshi_game_winners' key."""
    from src.data.cache import is_cached
    _setup_mock(mock_get)
    kalshi.fetch_kalshi_markets()
    assert is_cached("kalshi_game_winners")


@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_kalshi_returns_dataframe(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """fetch_kalshi_markets() returns a pandas DataFrame."""
    _setup_mock(mock_get)
    result = kalshi.fetch_kalshi_markets()
    assert isinstance(result, pd.DataFrame)


@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_kalshi_within_response_dedup(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """If the same home-YES market appears twice in the response, it's deduped to 1 row.

    This guards against pagination returning overlapping results.
    """
    mock_get.side_effect = [_make_mock_response({
        "markets": [SAMPLE_HOME_MARKET, SAMPLE_HOME_MARKET],  # duplicate home market
        "cursor": None,
    })]
    result = kalshi.fetch_kalshi_markets()
    # Two identical home markets → 1 game row (dedup by game_id in home_markets filter)
    # Note: game_id-level dedup relies on pandas drop_duplicates not being called —
    # the home_markets filter already reduces to 1 row per game since duplicate tickers
    # produce identical game_id. The test confirms no double-counting.
    assert len(result) == 1
