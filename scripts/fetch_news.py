#!/usr/bin/env python3
"""
Fetches chiropractic / spine-health headlines from the GNews API and writes
them to news.json in the exact shape faq.html's news column expects:

    [
      {"title": "...", "source": "...", "date": "YYYY-MM-DD",
       "summary": "...", "url": "https://..."},
      ...
    ]

Run on a schedule by .github/workflows/fetch-news.yml (see that file for the
cron schedule). Requires the GNEWS_API_KEY environment variable — never hard
-code the key in this file or in git history; set it as a GitHub Actions
repository secret (Settings > Secrets and variables > Actions).

Local test:
    export GNEWS_API_KEY=your_key_here
    python3 scripts/fetch_news.py
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

# ---- Config -----------------------------------------------------------
QUERY = 'chiropractic OR "spinal health" OR "back pain" OR "spine health"'
LANG = "en"
MAX_ARTICLES = 6          # keep in sync with faq.html's news-card-grid (slice(0,6))
SUMMARY_MAX_LEN = 180      # keeps card text a consistent length
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "news.json")
API_URL = "https://gnews.io/api/v4/search"
# -------------------------------------------------------------------------


def fetch_articles(api_key: str) -> list[dict]:
    params = {
        "q": QUERY,
        "lang": LANG,
        "max": MAX_ARTICLES,
        "sortby": "publishedAt",
        "apikey": api_key,
    }
    resp = requests.get(API_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data.get("articles", [])


def to_news_json(articles: list[dict]) -> list[dict]:
    items = []
    for a in articles[:MAX_ARTICLES]:
        title = (a.get("title") or "").strip()
        url = (a.get("url") or "").strip()
        if not title or not url:
            continue  # skip malformed entries rather than publish a broken card

        source = ((a.get("source") or {}).get("name") or "").strip() or "Unknown source"

        published_at = a.get("publishedAt") or ""
        try:
            date = datetime.fromisoformat(published_at.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except ValueError:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        summary = (a.get("description") or a.get("content") or "").strip()
        if len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN].rsplit(" ", 1)[0] + "..."

        items.append({
            "title": title,
            "source": source,
            "date": date,
            "summary": summary,
            "url": url,
        })
    return items


def main() -> int:
    api_key = os.environ.get("GNEWS_API_KEY")
    if not api_key:
        print("ERROR: GNEWS_API_KEY environment variable is not set.", file=sys.stderr)
        return 1

    try:
        articles = fetch_articles(api_key)
    except requests.RequestException as exc:
        print(f"ERROR: GNews request failed: {exc}", file=sys.stderr)
        return 1

    items = to_news_json(articles)

    if not items:
        # Don't overwrite a good news.json with an empty one just because
        # this run found nothing (e.g. a transient API hiccup or an empty
        # result set) — leave the existing file in place.
        print("WARNING: no usable articles returned; leaving news.json unchanged.", file=sys.stderr)
        return 0

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(items)} articles to {os.path.abspath(OUTPUT_PATH)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
