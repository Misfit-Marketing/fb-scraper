"""
CLI entry point for running the Facebook Ads Library scraper.

Usage:
    python -m app.runner carpe
    python -m app.runner all
    python -m app.runner carpe --limit 20
    python -m app.runner carpe --limit none   # scrape everything, no cap
    python -m app.runner "https://www.facebook.com/ads/library/?...=123" --limit 20
"""
from __future__ import annotations

import argparse
import csv
import json
import os

from dotenv import load_dotenv

from app.scraper.scraper import scrape_ads_library
from app.scraper.websites import WEBSITES


def _parse_limit(value: str) -> int | None:
    if value.strip().lower() in ("none", "null", ""):
        return None
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"--limit must be an integer or 'none', got {value!r}")


def _resolve_targets(target: str) -> dict[str, list[str]]:
    if target == "all":
        return WEBSITES
    if target in WEBSITES:
        return {target: WEBSITES[target]}
    if target.startswith("http://") or target.startswith("https://"):
        return {target: [target]}
    raise SystemExit(
        f"Unknown site '{target}'. Known sites: {', '.join(WEBSITES)}. "
        "You can also pass a full Facebook Ads Library URL."
    )


def _write_output(all_ads: list[dict], output: str) -> None:
    out_dir = os.path.dirname(output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if output.lower().endswith(".csv"):
        fieldnames = list(all_ads[0].keys()) if all_ads else []
        with open(output, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for ad in all_ads:
                row = dict(ad)
                if isinstance(row.get("platforms"), list):
                    row["platforms"] = ", ".join(row["platforms"])
                writer.writerow(row)
    else:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(all_ads, f, ensure_ascii=False, indent=4)


def run(
    target: str,
    limit: int | None,
    headless: bool,
    save_db: bool,
    output: str | None,
    upload_s3: bool = True,
) -> list[dict]:
    targets = _resolve_targets(target)
    all_ads: list[dict] = []

    for site_name, urls in targets.items():
        for url in urls:
            print(f"Scraping '{site_name}': {url}")
            ads = scrape_ads_library(url, data_limit=limit, headless=headless)
            print(f"  collected {len(ads)} ads")

            if upload_s3:
                from app.storage.s3_uploader import attach_s3_media_urls
                attach_s3_media_urls(ads)

            all_ads.extend(ads)

            if save_db:
                from app.database.repository import save_ads
                inserted = save_ads(site_name, url, ads)
                print(f"  saved {inserted} ads to database")

    if output:
        _write_output(all_ads, output)
        print(f"Wrote {len(all_ads)} ads to {output}")

    return all_ads


def main(argv=None) -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Run the Facebook Ads Library scraper.")
    parser.add_argument(
        "target",
        help=f"Site name to scrape ({', '.join(WEBSITES)}, or 'all'), or a full ads-library URL.",
    )
    parser.add_argument(
        "--limit",
        type=_parse_limit,
        default=10,
        help="Max ads to scrape per URL: an integer, or 'none' for no limit. Default 10.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help=(
            "Run Chrome headless. If omitted, Chrome runs headed, which needs a "
            "display (e.g. Xvfb) when there's no real monitor, such as in CI."
        ),
    )
    parser.add_argument("--no-save-db", action="store_true", help="Skip saving results to the database.")
    parser.add_argument(
        "--no-s3-upload",
        action="store_true",
        help="Skip uploading scraped media (image/video) to S3.",
    )
    parser.add_argument(
        "--output",
        default="app/test/scraped_data.json",
        help="Path to write the scraped JSON output.",
    )
    args = parser.parse_args(argv)

    run(
        target=args.target,
        limit=args.limit,
        headless=args.headless,
        save_db=not args.no_save_db,
        output=args.output,
        upload_s3=not args.no_s3_upload,
    )


if __name__ == "__main__":
    main()
