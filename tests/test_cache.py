"""Unit tests for src.data.cache module.

All tests use tmp_path fixture with monkeypatched CACHE_DIR and MANIFEST_PATH
to ensure test isolation -- no real data/ directory is touched.
"""

import json
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch

from src.data import cache


@pytest.fixture
def isolated_cache(tmp_path):
    """Redirect cache operations to tmp_path for test isolation."""
    cache_dir = tmp_path / "data" / "raw"
    cache_dir.mkdir(parents=True)
    manifest_path = cache_dir / "cache_manifest.json"
    with patch.object(cache, "CACHE_DIR", cache_dir), \
         patch.object(cache, "MANIFEST_PATH", manifest_path):
        yield cache_dir, manifest_path


class TestLoadManifest:
    def test_returns_empty_dict_when_no_manifest(self, isolated_cache):
        """load_manifest() returns {} when manifest file does not exist."""
        result = cache.load_manifest()
        assert result == {}

    def test_returns_manifest_content_when_exists(self, isolated_cache):
        """load_manifest() reads existing manifest JSON correctly."""
        _, manifest_path = isolated_cache
        expected = {"key1": {"path": "test.parquet", "season": 2023}}
        manifest_path.write_text(json.dumps(expected))
        result = cache.load_manifest()
        assert result == expected


class TestSaveManifest:
    def test_creates_manifest_file(self, isolated_cache):
        """save_manifest() creates the manifest file."""
        _, manifest_path = isolated_cache
        cache.save_manifest({"test": "data"})
        assert manifest_path.exists()

    def test_creates_parent_dirs(self, tmp_path):
        """save_manifest() creates parent directories if needed."""
        deep_dir = tmp_path / "deep" / "nested" / "dir"
        manifest_path = deep_dir / "cache_manifest.json"
        with patch.object(cache, "CACHE_DIR", deep_dir), \
             patch.object(cache, "MANIFEST_PATH", manifest_path):
            cache.save_manifest({"test": "data"})
            assert manifest_path.exists()

    def test_roundtrip_with_load(self, isolated_cache):
        """save_manifest() then load_manifest() round-trips correctly."""
        data = {
            "team_batting_2023": {
                "path": "pybaseball/team_batting_2023.parquet",
                "season": 2023,
                "fetch_date": "2024-01-01T00:00:00",
                "row_count": 30,
            }
        }
        cache.save_manifest(data)
        result = cache.load_manifest()
        assert result == data


class TestIsCached:
    def test_returns_false_for_unknown_key(self, isolated_cache):
        """is_cached() returns False when key is not in manifest."""
        assert cache.is_cached("nonexistent_key") is False

    def test_returns_false_when_file_missing(self, isolated_cache):
        """is_cached() returns False when manifest entry exists but file does not."""
        _, manifest_path = isolated_cache
        manifest = {"key1": {"path": "missing_file.parquet"}}
        manifest_path.write_text(json.dumps(manifest))
        assert cache.is_cached("key1") is False

    def test_returns_true_after_save_to_cache(self, isolated_cache):
        """is_cached() returns True after save_to_cache() writes data."""
        cache_dir, _ = isolated_cache
        df = pd.DataFrame({"a": [1, 2, 3]})
        cache.save_to_cache(df, "test_key", "test/data.parquet", 2023)
        assert cache.is_cached("test_key") is True


class TestSaveToCache:
    def test_writes_parquet_file(self, isolated_cache):
        """save_to_cache() writes a Parquet file at the specified path."""
        cache_dir, _ = isolated_cache
        df = pd.DataFrame({"x": [10, 20], "y": ["a", "b"]})
        cache.save_to_cache(df, "my_key", "subdir/test.parquet", 2023)
        expected_file = cache_dir / "subdir" / "test.parquet"
        assert expected_file.exists()

    def test_updates_manifest(self, isolated_cache):
        """save_to_cache() records entry in manifest."""
        df = pd.DataFrame({"col": [1]})
        cache.save_to_cache(df, "cache_key", "path/file.parquet", 2022)
        manifest = cache.load_manifest()
        assert "cache_key" in manifest
        assert manifest["cache_key"]["path"] == "path/file.parquet"
        assert manifest["cache_key"]["season"] == 2022
        assert manifest["cache_key"]["row_count"] == 1


class TestReadCached:
    def test_returns_identical_dataframe(self, isolated_cache):
        """read_cached() returns DataFrame identical to what was saved."""
        df_original = pd.DataFrame({
            "team": ["NYY", "BOS", "LAD"],
            "wins": [99, 87, 106],
            "wOBA": [0.340, 0.310, 0.350],
        })
        cache.save_to_cache(df_original, "round_trip", "rt/test.parquet", 2023)
        df_loaded = cache.read_cached("round_trip")
        pd.testing.assert_frame_equal(df_original, df_loaded)

    def test_raises_keyerror_for_unknown_key(self, isolated_cache):
        """read_cached() raises KeyError for keys not in manifest."""
        with pytest.raises(KeyError, match="not found"):
            cache.read_cached("unknown_key")


class TestUpdateManifest:
    def test_records_all_metadata(self, isolated_cache):
        """update_manifest() records season, row_count, fetch_date, path."""
        cache.update_manifest("sp_stats_2023", "pitching/sp_2023.parquet", 2023, 150)
        manifest = cache.load_manifest()
        entry = manifest["sp_stats_2023"]
        assert entry["path"] == "pitching/sp_2023.parquet"
        assert entry["season"] == 2023
        assert entry["row_count"] == 150
        assert "fetch_date" in entry  # ISO timestamp string


class TestGetCachePath:
    def test_returns_path_under_cache_dir(self, isolated_cache):
        """get_cache_path() returns path rooted at CACHE_DIR."""
        cache_dir, _ = isolated_cache
        result = cache.get_cache_path("sub/file.parquet")
        assert str(result).startswith(str(cache_dir))
        assert result.name == "file.parquet"

    def test_creates_parent_dirs(self, isolated_cache):
        """get_cache_path() creates parent directories."""
        cache_dir, _ = isolated_cache
        result = cache.get_cache_path("deep/nested/file.parquet")
        assert result.parent.exists()
