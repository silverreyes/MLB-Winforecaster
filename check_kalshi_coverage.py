"""Standalone Kalshi coverage checker.

Hits GET /markets?status=settled&series_ticker=KXMLB directly — no cache,
no fetch_kalshi_markets(). Prints every market returned so you can inspect
raw ticker, title, and close_time.
"""
import os
import time
import requests

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


def get_headers():
    headers = {"Accept": "application/json"}
    api_key = os.environ.get("KALSHI_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def fetch_all_pages():
    markets = []
    cursor = None
    page = 1
    headers = get_headers()

    while True:
        params = {"status": "settled", "series_ticker": "KXMLBGAME", "limit": 1000}
        if cursor:
            params["cursor"] = cursor

        print(f"  [page {page}] fetching...", flush=True)
        resp = requests.get(f"{BASE_URL}/markets", params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        page_markets = data.get("markets", [])
        markets.extend(page_markets)
        print(f"  [page {page}] got {len(page_markets)} markets (running total: {len(markets)})")

        cursor = data.get("cursor")
        if not cursor or not page_markets:
            break

        page += 1
        time.sleep(0.1)

    return markets


def main():
    print("=" * 70)
    print("Kalshi live endpoint: GET /markets?status=settled&series_ticker=KXMLBGAME")
    print("=" * 70)

    auth_status = "authenticated (KALSHI_API_KEY set)" if os.environ.get("KALSHI_API_KEY") else "unauthenticated (no KALSHI_API_KEY)"
    print(f"Auth: {auth_status}\n")

    markets = fetch_all_pages()

    print(f"\nTotal markets returned: {len(markets)}")
    print("-" * 70)

    if not markets:
        print("No markets returned.")
        return

    # Sort by close_time for readability
    markets_sorted = sorted(markets, key=lambda m: m.get("close_time") or "")

    print(f"{'#':<4}  {'TICKER':<30}  {'CLOSE_TIME':<22}  TITLE")
    print("-" * 70)
    for i, m in enumerate(markets_sorted, 1):
        ticker    = m.get("ticker", "")[:30]
        close     = (m.get("close_time") or "")[:19].replace("T", " ")
        title     = m.get("title", "")
        print(f"{i:<4}  {ticker:<30}  {close:<22}  {title}")

    # Coverage summary
    dates = sorted(
        m.get("close_time", "")[:10]
        for m in markets
        if m.get("close_time")
    )
    if dates:
        print("-" * 70)
        print(f"Date range : {dates[0]}  ->  {dates[-1]}")
        print(f"Unique dates: {len(set(dates))}")

    # Settlement breakdown
    settled_yes = sum(1 for m in markets if m.get("settlement_value_dollars") == "1")
    settled_no  = sum(1 for m in markets if m.get("settlement_value_dollars") == "0")
    voided      = sum(1 for m in markets if not (m.get("settlement_value_dollars") or "").strip())
    print(f"Results    : YES={settled_yes}  NO={settled_no}  voided/empty={voided}")
    print("=" * 70)


if __name__ == "__main__":
    main()
