# fb-scraper

Facebook Ad Library Scraper — pulls active ads for a list of brands and saves them to a database (and/or a JSON/CSV file).

## How it works (the flow)

```
1. You run a command (locally or via GitHub Actions)
        |
        v
2. app/runner.py         → parses the target + options (--limit, --headless, etc.)
        |
        v
3. app/scraper/websites.py → looks up the Facebook Ads Library URL(s) for that target
        |
        v
4. app/scraper/scraper.py  → opens Chrome (Selenium), loads the page, scrolls to
                              load more ads, opens each ad's "details" panel, and
                              pulls out the fields (poster, headline, body text,
                              media, status, library ID, platforms, etc.)
        |
        v
5. app/database/repository.py → saves each ad into Postgres (advertisers + ads
                                  tables), OR
   app/runner.py            → writes everything to a JSON/CSV file
```

In short: **pick a brand → find its ad library URL → scrape the page with a real browser → store the results.**

## Project layout

| File | Role |
|---|---|
| [app/runner.py](app/runner.py) | CLI entry point — `python -m app.runner <target>` |
| [app/scraper/runner.py](app/scraper/runner.py) | Parses args, resolves the target, runs the scrape, writes output/DB |
| [app/scraper/websites.py](app/scraper/websites.py) | The list of tracked brands and their Ads Library URLs |
| [app/scraper/scraper.py](app/scraper/scraper.py) | The actual Selenium scraping logic |
| [app/database/db_connection.py](app/database/db_connection.py) | Opens a Postgres connection from env vars |
| [app/database/repository.py](app/database/repository.py) | Upserts scraped ads into the database |
| [.github/workflows/](.github/workflows/) | Scheduled/automated scrapes (see below) |

## Running it yourself

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Set up your `.env`** (only needed if saving to the database):
```
DATABASE_HOSTNAME=...
DATABASE_PORT=...
DATABASE_NAME=...
DATABASE_USERNAME=...
DATABASE_PASSWORD=...
```

**3. Run a scrape**
```bash
# Scrape one tracked brand (see app/scraper/websites.py for the full list)
python -m app.runner carpe

# Scrape every tracked brand
python -m app.runner all

# Limit how many ads to grab
python -m app.runner carpe --limit 20

# No limit — grab everything the page reports
python -m app.runner carpe --limit none

# Scrape any Ads Library URL directly, not just tracked brands
python -m app.runner "https://www.facebook.com/ads/library/?...=123" --limit 20

# Skip the database and just write a file
python -m app.runner carpe --no-save-db --output app/test/scraped_data.json

# Run Chrome headless (no visible browser window — required in CI)
python -m app.runner carpe --headless
```

Every scrape also writes its results to `app/test/scraped_data.json` by default (change with `--output`), in addition to the database (unless `--no-save-db` is set).

## Adding a new brand to track

Open [app/scraper/websites.py](app/scraper/websites.py) and add a new entry:

```python
WEBSITES = {
    "your-brand": [
        "https://www.facebook.com/ads/library/?...&view_all_page_id=XXXXXXXXX",
    ],
}
```

Then it's scrapeable via `python -m app.runner your-brand`.

## Automated scrapes (GitHub Actions)

Each tracked brand has its own scheduled workflow in [.github/workflows/](.github/workflows/) that runs automatically and saves straight to the database:

- **`scrape-<brand>.yml`** — runs daily on GitHub's hosted runner (headless Chrome).
- **`vm_scrape-<brand>.yml`** — same idea, but runs on a self-hosted VM runner (needed for brands that hit bot detection on GitHub's shared runners), using a virtual display (`xvfb`) instead of headless mode.
- **`general-scraper.yml`** — manually triggered; scrape *any* Ads Library URL on demand.
- **`test-scraper.yml`** — manually triggered; scrapes without touching the database, useful for testing changes to the scraper.

All of these can also be triggered manually from the GitHub Actions tab ("Run workflow").

## Notes

- The scraper drives a real Chrome browser (via Selenium), so Facebook's page layout changing can break the CSS/XPath selectors in [scraper.py](app/scraper/scraper.py) — that's the most common thing to fix if scrapes start returning empty results.
- Ads without a `library_id` are skipped when saving to the database (it's the unique key used to avoid duplicates).
- Re-running a scrape is safe — ads are upserted by `library_id`, so existing rows get refreshed instead of duplicated.
