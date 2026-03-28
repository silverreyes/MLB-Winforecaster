"""Tests for Kalshi market data loader (DATA-06).

Tests the Kalshi dual-endpoint loader: fetch_kalshi_markets(),
_is_mlb_game_winner(), _parse_market_result(), deduplication, and caching.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Skip entire module if loader not yet implemented
kalshi = pytest.importorskip("src.data.kalshi")


# Sample market data mimicking Kalshi API response
SAMPLE_MARKET_SETTLED = {
    "ticker": "KXMLB-25MAR28-NYYBOS",
    "title": "Will the Yankees beat the Red Sox?",
    "subtitle": "MLB Regular Season",
    "status": "settled",
    "close_time": "2025-03-28T23:00:00Z",
    "settlement_value_dollars": "1.00",
    "last_price_dollars": "0.65",
    "yes_bid_dollars": "0.64",
    "no_bid_dollars": "0.36",
    "result": "yes",
}

SAMPLE_MARKET_VOIDED = {
    "ticker": "KXMLB-25MAR29-LADSFG",
    "title": "Will the Dodgers beat the Giants?",
    "subtitle": "MLB Regular Season",
    "status": "settled",
    "close_time": "2025-03-29T23:00:00Z",
    "settlement_value_dollars": "",
    "last_price_dollars": "0.55",
    "yes_bid_dollars": "0.54",
    "no_bid_dollars": "0.46",
    "result": "",
}

# Sample API response wrapping markets
SAMPLE_API_RESPONSE = {
    "markets": [SAMPLE_MARKET_SETTLED, SAMPLE_MARKET_VOIDED],
    "cursor": None,
}

# Cutoff response
SAMPLE_CUTOFF_RESPONSE = {
    "market_settled_ts": "2025-06-01T00:00:00Z",
}

# Empty response (for historical endpoint returning no markets)
EMPTY_API_RESPONSE = {
    "markets": [],
    "cursor": None,
}


def _make_mock_response(json_data):
    """Create a mock requests.Response with the given JSON payload."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _setup_dual_endpoint_mock(mock_get):
    """Set up mock to handle the 3-call sequence: cutoff, live markets, historical markets.

    The implementation calls:
    1. GET /historical/cutoff -> cutoff timestamp
    2. GET /markets (live, with series_ticker) -> settled markets
    3. GET /historical/markets (no series_ticker filter) -> empty (filtered client-side)
    """
    mock_get.side_effect = [
        _make_mock_response(SAMPLE_CUTOFF_RESPONSE),   # cutoff
        _make_mock_response(SAMPLE_API_RESPONSE),       # live endpoint
        _make_mock_response(EMPTY_API_RESPONSE),        # historical endpoint
    ]


@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_fetch_kalshi_markets_returns_dataframe(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """fetch_kalshi_markets() returns a pandas DataFrame."""
    _setup_dual_endpoint_mock(mock_get)
    result = kalshi.fetch_kalshi_markets()
    assert isinstance(result, pd.DataFrame)


@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_kalshi_has_required_columns(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """Result has required columns: date, home_team, away_team, kalshi_yes_price,
    kalshi_no_price, result, market_ticker."""
    _setup_dual_endpoint_mock(mock_get)
    result = kalshi.fetch_kalshi_markets()
    required = [
        "date", "home_team", "away_team",
        "kalshi_yes_price", "kalshi_no_price",
        "result", "market_ticker",
    ]
    for col in required:
        assert col in result.columns, f"Missing column: {col}"


@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_kalshi_prices_are_floats(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """Price columns (kalshi_yes_price, kalshi_no_price) are numeric floats."""
    _setup_dual_endpoint_mock(mock_get)
    result = kalshi.fetch_kalshi_markets()
    assert pd.api.types.is_float_dtype(result["kalshi_yes_price"]), \
        "kalshi_yes_price should be float"
    assert pd.api.types.is_float_dtype(result["kalshi_no_price"]), \
        "kalshi_no_price should be float"


@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_kalshi_teams_are_normalized(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """Team values are canonical 3-letter codes from team_mappings."""
    from src.data.team_mappings import TEAM_MAP

    _setup_dual_endpoint_mock(mock_get)
    result = kalshi.fetch_kalshi_markets()
    canonical_codes = set(TEAM_MAP.values())
    for _, row in result.iterrows():
        if pd.notna(row["home_team"]):
            assert row["home_team"] in canonical_codes, \
                f"home_team '{row['home_team']}' not a canonical code"
        if pd.notna(row["away_team"]):
            assert row["away_team"] in canonical_codes, \
                f"away_team '{row['away_team']}' not a canonical code"


@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_kalshi_caches_to_parquet(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """After fetch, cached Kalshi data exists."""
    from src.data.cache import is_cached

    _setup_dual_endpoint_mock(mock_get)
    kalshi.fetch_kalshi_markets()
    assert is_cached("kalshi_game_winners")


def test_kalshi_voided_market_result_is_none():
    """A market with empty settlement_value_dollars has result=None, NOT 'NO'.

    Voided/cancelled markets should not be silently coded as NO outcomes.
    """
    parsed = kalshi._parse_market_result(SAMPLE_MARKET_VOIDED)
    assert parsed is None, (
        f"Voided market (empty settlement_value_dollars) should have "
        f"result=None, got {parsed!r}"
    )


def test_is_mlb_game_winner_kxmlb_ticker():
    """KXMLB prefix is the primary positive indicator for MLB game-winner markets."""
    market = {
        "ticker": "KXMLB-25-NYYBOS",
        "title": "",
        "subtitle": "",
    }
    assert kalshi._is_mlb_game_winner(market) is True


def test_is_mlb_game_winner_rejects_non_mlb():
    """Non-MLB markets (e.g., political) are rejected."""
    market = {
        "ticker": "KXPRES-2025",
        "title": "Will candidate X win?",
        "subtitle": "",
    }
    assert kalshi._is_mlb_game_winner(market) is False


def test_is_mlb_game_winner_fallback_title():
    """Fallback title matching works when ticker doesn't have KXMLB prefix."""
    market = {
        "ticker": "UNKNOWN-123",
        "title": "Will the Yankees beat the Red Sox?",
        "subtitle": "MLB game",
    }
    assert kalshi._is_mlb_game_winner(market) is True


@patch("src.data.kalshi.CACHE_DIR")
@patch("src.data.kalshi.requests.get")
def test_kalshi_deduplication_by_ticker(mock_get, mock_kalshi_cache_dir, mock_cache_dir):
    """Markets appearing in both live and historical endpoints are deduplicated by ticker."""
    # Both endpoints return the same market -- should only appear once
    mock_get.side_effect = [
        _make_mock_response(SAMPLE_CUTOFF_RESPONSE),
        _make_mock_response({
            "markets": [SAMPLE_MARKET_SETTLED],
            "cursor": None,
        }),
        _make_mock_response({
            "markets": [SAMPLE_MARKET_SETTLED],  # duplicate
            "cursor": None,
        }),
    ]
    result = kalshi.fetch_kalshi_markets()
    assert len(result) == 1, f"Expected 1 row after dedup, got {len(result)}"


def test_parse_market_result_yes():
    """Settlement value 1.00 maps to 'YES'."""
    market = {"settlement_value_dollars": "1.00"}
    assert kalshi._parse_market_result(market) == "YES"


def test_parse_market_result_no():
    """Settlement value 0.00 maps to 'NO'."""
    market = {"settlement_value_dollars": "0.00"}
    assert kalshi._parse_market_result(market) == "NO"
