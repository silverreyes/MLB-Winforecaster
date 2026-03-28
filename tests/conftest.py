"""Shared test fixtures for all data loader tests."""

import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def mock_cache_dir(tmp_path):
    """Redirect cache operations to tmp_path for test isolation.

    Patches src.data.cache.CACHE_DIR and src.data.cache.MANIFEST_PATH.
    This works because all functions in cache.py (is_cached, get_cache_path,
    save_to_cache, read_cached) reference CACHE_DIR as a module-level name,
    so they pick up the patched value at call time.

    NOTE: Any loader that does `from src.data.cache import CACHE_DIR` (creating
    a local binding) will NOT be affected by this patch. Loaders should access
    CACHE_DIR only through the cache API functions, not by importing the constant
    directly. kalshi.py currently imports CACHE_DIR directly -- its loader-level
    tests should additionally patch `src.data.kalshi.CACHE_DIR` if needed.
    """
    cache_dir = tmp_path / "data" / "raw"
    cache_dir.mkdir(parents=True)
    manifest_path = cache_dir / "cache_manifest.json"
    with patch("src.data.cache.CACHE_DIR", cache_dir), \
         patch("src.data.cache.MANIFEST_PATH", manifest_path):
        yield cache_dir
