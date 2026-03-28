"""Kalshi API diagnostic — sports filters + event structure explorer.

Calls:
  1. GET /search/filters_by_sport  — what sports/series tickers exist
  2. GET /events?status=settled&limit=5  — raw event structure sample

No cache, no project imports. Raw output only.
"""
import json
import os
import requests

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


def headers():
    h = {"Accept": "application/json"}
    key = os.environ.get("KALSHI_API_KEY")
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def get(path, params=None):
    url = f"{BASE_URL}/{path}"
    resp = requests.get(url, params=params or {}, headers=headers(), timeout=15)
    print(f"  {resp.request.method} {resp.url}")
    print(f"  HTTP {resp.status_code}")
    return resp


def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    auth = "authenticated" if os.environ.get("KALSHI_API_KEY") else "unauthenticated"
    print(f"Auth: {auth}")

    # ------------------------------------------------------------------ #
    # 1. GET /search/filters_by_sport
    # ------------------------------------------------------------------ #
    section("1. GET /search/filters_by_sport")
    try:
        resp = get("search/filters_by_sport")
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2))
        else:
            print(f"  Error body: {resp.text[:500]}")
    except Exception as e:
        print(f"  Exception: {e}")

    # ------------------------------------------------------------------ #
    # 2. GET /events?status=settled&limit=5  (raw event structure)
    # ------------------------------------------------------------------ #
    section("2. GET /events?status=settled&limit=5")
    try:
        resp = get("events", {"status": "settled", "limit": 5})
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2))
        else:
            print(f"  Error body: {resp.text[:500]}")
    except Exception as e:
        print(f"  Exception: {e}")

    # ------------------------------------------------------------------ #
    # 3. Bonus: GET /events?status=settled&limit=5 with series_ticker guess
    # ------------------------------------------------------------------ #
    section("3. GET /events?status=settled&series_ticker=KXMLB&limit=5  (guess)")
    try:
        resp = get("events", {"status": "settled", "series_ticker": "KXMLB", "limit": 5})
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2))
        else:
            print(f"  Error body: {resp.text[:500]}")
    except Exception as e:
        print(f"  Exception: {e}")

    # ------------------------------------------------------------------ #
    # 4. GET /markets with min/max_settled_ts (date-range filter test)
    # ------------------------------------------------------------------ #
    section("4. GET /markets?min_settled_ts=&max_settled_ts= (Opening Day 2025 window)")
    import time, datetime
    # 2025-03-27 00:00:00 UTC  →  2025-03-28 23:59:59 UTC
    ts_min = int(datetime.datetime(2025, 3, 27, 0, 0, 0).timestamp())
    ts_max = int(datetime.datetime(2025, 3, 28, 23, 59, 59).timestamp())
    print(f"  Window: {datetime.datetime.utcfromtimestamp(ts_min)} UTC  ->  {datetime.datetime.utcfromtimestamp(ts_max)} UTC")
    try:
        resp = get("markets", {
            "status": "settled",
            "min_settled_ts": ts_min,
            "max_settled_ts": ts_max,
            "limit": 10,
        })
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2))
        else:
            print(f"  Error body: {resp.text[:500]}")
    except Exception as e:
        print(f"  Exception: {e}")


if __name__ == "__main__":
    main()
