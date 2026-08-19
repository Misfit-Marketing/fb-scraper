# fb-scraper

A Python + Selenium scraper that pulls active ads from the Facebook Ad Library for a list of brands.

## How it works (the flow)

```
1. You run a command
        |
        v
2. app/runner.py            → parses the target + options (--limit, --headless, etc.)
        |
        v
3. app/scraper/websites.py  → looks up the Facebook Ads Library URL(s) for that target
        |
        v
4. app/scraper/scraper.py   → opens Chrome with Selenium and does the actual scraping:
                                 a. loads the ads-library page
                                 b. scrolls down repeatedly to load more ads
                                 c. for each ad, clicks "See ad details" to expand it
                                 d. reads the fields out of the page (poster, headline,
                                    body text, media, status, library ID, platforms...)
                                 e. closes the details panel and moves to the next ad
        |
        v
5. app/scraper/runner.py    → writes all the collected ads to a JSON/CSV file
```

In short: **pick a brand → find its ad library URL → drive a real Chrome browser to load and read every ad → write the results to a file.**

## Why Selenium?

The Ad Library is a JavaScript-heavy page — ads load in as you scroll, and each ad's full details (status, library ID, platforms) only appear after clicking to expand it. That's not something a simple HTTP request can do, so the scraper uses [Selenium](https://www.selenium.dev/) to control a real Chrome browser: it navigates, scrolls, clicks, waits for content to appear, and then reads the text/attributes straight out of the rendered page (via XPath selectors).

## Project layout

| File | Role |
|---|---|
| [app/runner.py](app/runner.py) | CLI entry point — `python -m app.runner <target>` |
| [app/scraper/runner.py](app/scraper/runner.py) | Parses args, resolves the target, runs the scrape, writes the output file |
| [app/scraper/websites.py](app/scraper/websites.py) | The list of tracked brands and their Ads Library URLs |
| [app/scraper/scraper.py](app/scraper/scraper.py) | The Selenium scraping logic — this is where the actual work happens |
| [.github/workflows/](.github/workflows/) | Scheduled/automated scrapes (see below) |

## Running it yourself

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Run a scrape**
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

# Choose where the output file goes
python -m app.runner carpe --output app/test/scraped_data.json

# Run Chrome headless (no visible browser window — required in CI)
python -m app.runner carpe --headless
```

Every scrape writes its results to `app/test/scraped_data.json` by default (change with `--output`; use a `.csv` path to get CSV instead of JSON).

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

Each tracked brand has its own scheduled workflow in [.github/workflows/](.github/workflows/) that runs the scraper automatically:

- **`scrape-<brand>.yml`** — runs daily on GitHub's hosted runner (headless Chrome).
- **`vm_scrape-<brand>.yml`** — same idea, but runs on a self-hosted VM runner (needed for brands that hit bot detection on GitHub's shared runners), using a virtual display (`xvfb`) instead of headless mode.
- **`general-scraper.yml`** — manually triggered; scrape *any* Ads Library URL on demand.
- **`test-scraper.yml`** — manually triggered; scrapes without saving to a database, useful for testing changes to the scraper.

All of these can also be triggered manually from the GitHub Actions tab ("Run workflow").

## Notes

- The scraper drives a real Chrome browser, so Facebook's page layout changing can break the XPath selectors in [scraper.py](app/scraper/scraper.py) — that's the most common thing to fix if scrapes start returning empty results.
- `--limit` controls how many ads are collected; `--headless` controls whether Chrome shows a window while it works.
