"""
Persistence layer for scraped ad data.

Writes into the existing `advertisers` and `ads` tables. Each site gets one
`advertisers` row (keyed by the Facebook page id pulled from its ads-library
URL), and each ad is upserted by its Library ID (`ads.ad_archive_id`), so
re-running the same scrape refreshes existing rows instead of duplicating
them.

get_db_connection() (db_connection.py) handles connecting via the
DATABASE_* environment variables.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from app.database.db_connection import get_db_connection

UPSERT_ADVERTISER_SQL = """
INSERT INTO advertisers (page_id, page_name, page_url)
VALUES (%s, %s, %s)
ON CONFLICT (page_id) DO UPDATE SET
    page_name = EXCLUDED.page_name,
    page_url = COALESCE(EXCLUDED.page_url, advertisers.page_url),
    last_seen = now()
RETURNING id;
"""

UPSERT_AD_SQL = """
INSERT INTO ads (
    ad_archive_id, advertiser_id, page_id, page_name, ad_snapshot_url,
    is_active, delivery_start_time, publisher_platforms,
    poster_name, poster_url, posted_with, body_text, media_url,
    shop_now_url, headline, multiple_versions, raw
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (ad_archive_id) DO UPDATE SET
    advertiser_id = EXCLUDED.advertiser_id,
    page_id = EXCLUDED.page_id,
    page_name = EXCLUDED.page_name,
    ad_snapshot_url = EXCLUDED.ad_snapshot_url,
    is_active = EXCLUDED.is_active,
    delivery_start_time = EXCLUDED.delivery_start_time,
    publisher_platforms = EXCLUDED.publisher_platforms,
    poster_name = EXCLUDED.poster_name,
    poster_url = EXCLUDED.poster_url,
    posted_with = EXCLUDED.posted_with,
    body_text = EXCLUDED.body_text,
    media_url = EXCLUDED.media_url,
    shop_now_url = EXCLUDED.shop_now_url,
    headline = EXCLUDED.headline,
    multiple_versions = EXCLUDED.multiple_versions,
    raw = EXCLUDED.raw,
    last_scraped_at = now();
"""


def _extract_page_id(url: str, site_name: str) -> str:
    """Pull the Facebook page id out of an ads-library URL's
    `view_all_page_id` param, falling back to the site name for ad-hoc
    URLs that don't carry one."""
    page_ids = parse_qs(urlparse(url).query).get("view_all_page_id")
    return page_ids[0] if page_ids else site_name


def _most_common_page_url(ads: list[dict], default: str) -> str:
    """Pick the poster_url that shows up most often among the scraped ads.

    Keyword-search sources (no view_all_page_id) can surface ads from
    several different advertiser pages that merely mention the keyword, so
    the most frequent poster_url is a better stand-in for "the" advertiser
    than whichever ad happened to load first."""
    poster_urls = [ad["poster_url"] for ad in ads if ad.get("poster_url")]
    if not poster_urls:
        return default
    return Counter(poster_urls).most_common(1)[0][0]


def _parse_started_running(value: str | None) -> datetime | None:
    """Parse the scraper's "Mar 23, 2026" style date text."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%b %d, %Y")
    except ValueError:
        return None


def _is_active(status: str | None) -> bool | None:
    if status is None:
        return None
    return status == "Active"


def save_ads(site_name: str, source_url: str, ads: list[dict]) -> int:
    """
    Upsert scraped ad dicts (as produced by scrape_ads_library) into the
    `advertisers` and `ads` tables. Returns the number of ads saved. Ads
    without a library_id are skipped since ad_archive_id is required.
    """
    if not ads:
        return 0

    page_id = _extract_page_id(source_url, site_name)
    page_url = _most_common_page_url(ads, default=source_url)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(UPSERT_ADVERTISER_SQL, (page_id, site_name, page_url))
            advertiser_id = cur.fetchone()[0]

            saved = 0
            for ad in ads:
                library_id = ad.get("library_id")
                if not library_id:
                    print(f"  skipping ad with no library_id: {ad.get('headline')!r}")
                    continue

                cur.execute(UPSERT_AD_SQL, (
                    library_id,
                    advertiser_id,
                    page_id,
                    site_name,
                    f"https://www.facebook.com/ads/library/?id={library_id}",
                    _is_active(ad.get("status")),
                    _parse_started_running(ad.get("started_running")),
                    ad.get("platforms") or [],
                    ad.get("poster_name"),
                    ad.get("poster_url"),
                    ad.get("posted_with"),
                    ad.get("body_text"),
                    ad.get("media_url"),
                    ad.get("shop_now_url"),
                    ad.get("headline"),
                    ad.get("multiple_versions"),
                    json.dumps(ad),
                ))
                saved += 1

        conn.commit()
        return saved
    finally:
        conn.close()
