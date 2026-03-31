"""Tests for live score data parsing and API response enrichment.

Covers: LIVE-01 (score on card), LIVE-04 (runners), LIVE-05 (count),
LIVE-06 (batter stats), LIVE-07 (on-deck batter).
"""
import pytest
from unittest.mock import MagicMock, patch

from src.data.mlb_schedule import parse_linescore, get_linescore_cached


@pytest.fixture(autouse=True)
def clear_linescore_cache():
    """Reset module-level linescore cache between tests."""
    from src.data import mlb_schedule
    if hasattr(mlb_schedule, '_linescore_cache'):
        mlb_schedule._linescore_cache.clear()
    yield
    if hasattr(mlb_schedule, '_linescore_cache'):
        mlb_schedule._linescore_cache.clear()


# Sample raw MLB API response (verified against statsapi.mlb.com game 747009)
SAMPLE_LIVE_RESPONSE = {
    'liveData': {
        'linescore': {
            'currentInning': 7,
            'inningHalf': 'Top',
            'outs': 2,
            'balls': 1,
            'strikes': 2,
            'teams': {
                'home': {'runs': 1},
                'away': {'runs': 3},
            },
            'offense': {
                'batter': {'fullName': 'Justin Turner', 'id': 457759},
                'onDeck': {'fullName': 'Rafael Devers', 'id': 646240},
                'first': {'fullName': 'Runner One'},
                'third': {'fullName': 'Runner Three'},
            },
        },
        'boxscore': {
            'teams': {
                'away': {
                    'players': {
                        'ID457759': {
                            'person': {'fullName': 'Justin Turner'},
                            'seasonStats': {
                                'batting': {'avg': '.287', 'ops': '.821'}
                            }
                        }
                    }
                },
                'home': {'players': {}}
            }
        },
    }
}

SAMPLE_PREGAME_RESPONSE = {
    'liveData': {
        'linescore': {
            'teams': {
                'home': {},
                'away': {},
            },
        },
    }
}

SAMPLE_BETWEEN_INNINGS = {
    'liveData': {
        'linescore': {
            'currentInning': 5,
            'inningHalf': 'Middle',
            'outs': 0,
            'balls': 0,
            'strikes': 0,
            'teams': {
                'home': {'runs': 2},
                'away': {'runs': 2},
            },
            'offense': {},
        },
        'boxscore': {'teams': {'home': {'players': {}}, 'away': {'players': {}}}},
    }
}


class TestParseLinescore:
    """LIVE-01, LIVE-04, LIVE-05, LIVE-06, LIVE-07: Parse raw MLB API response."""

    def test_live_game_has_score(self):
        """LIVE-01: Extracts home_score and away_score from live game."""
        result = parse_linescore(SAMPLE_LIVE_RESPONSE)
        assert result is not None
        assert result['home_score'] == 1
        assert result['away_score'] == 3

    def test_non_live_game_null_score(self):
        """LIVE-01: Returns None when runs are missing (pre-game)."""
        result = parse_linescore(SAMPLE_PREGAME_RESPONSE)
        assert result is None

    def test_runners_parsed(self):
        """LIVE-04: Parses runner positions from offense dict."""
        result = parse_linescore(SAMPLE_LIVE_RESPONSE)
        assert result is not None
        assert result['runner_on_1b'] is True
        assert result['runner_on_2b'] is False
        assert result['runner_on_3b'] is True

    def test_count_parsed(self):
        """LIVE-05: Parses balls, strikes, outs."""
        result = parse_linescore(SAMPLE_LIVE_RESPONSE)
        assert result is not None
        assert result['balls'] == 1
        assert result['strikes'] == 2
        assert result['outs'] == 2

    def test_batter_stats(self):
        """LIVE-06: Parses batter name, AVG, OPS from boxscore."""
        result = parse_linescore(SAMPLE_LIVE_RESPONSE)
        assert result is not None
        assert result['current_batter'] == 'Justin Turner'
        assert result['batter_avg'] == '.287'
        assert result['batter_ops'] == '.821'

    def test_on_deck_parsed(self):
        """LIVE-07: Parses on-deck batter name."""
        result = parse_linescore(SAMPLE_LIVE_RESPONSE)
        assert result is not None
        assert result['on_deck_batter'] == 'Rafael Devers'

    def test_inning_parsing(self):
        """LIVE-01: Parses inning number and half."""
        result = parse_linescore(SAMPLE_LIVE_RESPONSE)
        assert result is not None
        assert result['inning'] == 7
        assert result['inning_half'] == 'top'

    def test_between_innings_null_batter(self):
        """LIVE-06: Null batter during between-innings (Middle state)."""
        result = parse_linescore(SAMPLE_BETWEEN_INNINGS)
        assert result is not None
        assert result['current_batter'] is None
        assert result['batter_avg'] is None
        assert result['on_deck_batter'] is None

    def test_inning_half_middle_maps_to_top(self):
        """Pitfall 4: 'Middle' inningHalf maps to 'top'."""
        result = parse_linescore(SAMPLE_BETWEEN_INNINGS)
        assert result is not None
        assert result['inning_half'] == 'top'

    def test_no_runners_all_false(self):
        """LIVE-04: Empty offense means bases empty."""
        result = parse_linescore(SAMPLE_BETWEEN_INNINGS)
        assert result is not None
        assert result['runner_on_1b'] is False
        assert result['runner_on_2b'] is False
        assert result['runner_on_3b'] is False


class TestGetLinescoreCached:
    """Cache behavior for linescore data."""

    @patch('src.data.mlb_schedule.statsapi')
    def test_cache_hit_within_ttl(self, mock_statsapi):
        """Returns cached data without API call within 90s TTL."""
        mock_statsapi.get.return_value = SAMPLE_LIVE_RESPONSE
        # First call: fetches
        result1 = get_linescore_cached(747009)
        assert mock_statsapi.get.call_count == 1
        # Second call: cached
        result2 = get_linescore_cached(747009)
        assert mock_statsapi.get.call_count == 1
        assert result1 == result2

    @patch('src.data.mlb_schedule.statsapi')
    def test_api_error_returns_none(self, mock_statsapi):
        """Returns None on MLB API error (silent skip)."""
        mock_statsapi.get.side_effect = Exception("503 Service Unavailable")
        result = get_linescore_cached(999999)
        assert result is None
