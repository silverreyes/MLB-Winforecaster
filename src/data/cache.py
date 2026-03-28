"""Shared cache infrastructure for data loaders.

Provides cache-check-then-fetch pattern with JSON manifest tracking.
Full implementation in Task 2.
"""

import json
import os
from pathlib import Path
from datetime import datetime
import pandas as pd

# Cache root -- relative to repo root
CACHE_DIR = Path("data/raw")
MANIFEST_PATH = CACHE_DIR / "cache_manifest.json"


def load_manifest() -> dict:
    """Load the cache manifest JSON. Returns empty dict if not found."""
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return {}


def save_manifest(manifest: dict):
    """Write the cache manifest JSON. Creates parent dirs if needed."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)


def is_cached(key: str) -> bool:
    """Check if a cache key exists in manifest AND the file exists on disk."""
    manifest = load_manifest()
    if key not in manifest:
        return False
    filepath = CACHE_DIR / manifest[key]["path"]
    return filepath.exists()


def get_cache_path(relative_path: str) -> Path:
    """Return absolute path for a cache-relative path. Creates parent dirs."""
    full = CACHE_DIR / relative_path
    full.parent.mkdir(parents=True, exist_ok=True)
    return full


def update_manifest(key: str, path: str, season: int, row_count: int):
    """Add or update a cache manifest entry with fetch metadata."""
    manifest = load_manifest()
    manifest[key] = {
        "path": path,
        "season": season,
        "fetch_date": datetime.now().isoformat(),
        "row_count": row_count,
    }
    save_manifest(manifest)


def read_cached(key: str) -> pd.DataFrame:
    """Read a cached Parquet file by manifest key. Raises KeyError if not cached."""
    manifest = load_manifest()
    if key not in manifest:
        raise KeyError(f"Cache key '{key}' not found in manifest")
    filepath = CACHE_DIR / manifest[key]["path"]
    return pd.read_parquet(filepath, engine="pyarrow")


def save_to_cache(df: pd.DataFrame, key: str, relative_path: str, season: int):
    """Save DataFrame as Parquet with snappy compression and update manifest."""
    filepath = get_cache_path(relative_path)
    df.to_parquet(filepath, engine="pyarrow", compression="snappy", index=False)
    update_manifest(key, relative_path, season, len(df))
