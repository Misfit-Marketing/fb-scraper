from __future__ import annotations

import json
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException


def _build_driver(headless: bool, profile_dir: str | None = None) -> webdriver.Chrome:
    chrome_options = Options()
    if headless:
        chrome_options.add_argument('--headless=new')
    else:
        chrome_options.add_argument('--start-maximized')

    # Reuse a dedicated Chrome profile so a Facebook login (needed for
    # age-gated ads) persists between runs.
    if profile_dir:
        chrome_options.add_argument(f'--user-data-dir={os.path.abspath(profile_dir)}')

    return webdriver.Chrome(options=chrome_options)


_SAME_SITE = {"lax": "Lax", "strict": "Strict", "no_restriction": "None", "none": "None"}


def _parse_fb_cookies(raw: str) -> list[dict]:
    """Accept either a Cookie-Editor JSON export (list of cookie objects) or a
    plain "name=value; name2=value2" header string."""
    raw = raw.strip().lstrip("\ufeff")
    # Tolerate a value copied straight from .env: FB_COOKIES='[...]'
    if raw.startswith("FB_COOKIES="):
        raw = raw[len("FB_COOKIES="):].strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        raw = raw[1:-1].strip()

    if raw.startswith("["):
        cookies = []
        for c in json.loads(raw):
            cookie = {
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", ".facebook.com"),
                "path": c.get("path", "/"),
                "secure": c.get("secure", True),
                "httpOnly": c.get("httpOnly", False),
            }
            same_site = _SAME_SITE.get(str(c.get("sameSite", "")).lower())
            if same_site:
                cookie["sameSite"] = same_site
            cookies.append(cookie)
        return cookies

    cookies = []
    for part in raw.split(";"):
        if "=" in part:
            name, value = part.strip().split("=", 1)
            cookies.append({"name": name, "value": value, "domain": ".facebook.com", "path": "/", "secure": True})
    return cookies


def _load_fb_cookies(driver: webdriver.Chrome, raw: str) -> None:
    """Log the browser into Facebook by injecting session cookies. Cookies can
    only be set for the domain currently loaded, so visit facebook.com first."""
    driver.get("https://www.facebook.com/")
    cookies = _parse_fb_cookies(raw)
    names = {c["name"] for c in cookies}
    if not {"c_user", "xs"} <= names:
        raise RuntimeError(
            f"FB_COOKIES is set but has no usable login (parsed {len(cookies)} cookies; "
            "need c_user and xs). Paste the Cookie-Editor JSON export as-is, starting "
            "with [ and ending with ] - no FB_COOKIES= and no surrounding quotes."
        )
    for cookie in cookies:
        driver.add_cookie(cookie)
    print(f"[debug] loaded {len(cookies)} Facebook cookies")


def login_to_facebook(profile_dir: str) -> None:
    """Open a visible Chrome on the given profile so the user can log into
    Facebook by hand; the session is saved in profile_dir for later runs."""
    driver = _build_driver(headless=False, profile_dir=profile_dir)
    try:
        driver.get("https://www.facebook.com/login")
        input("Log into Facebook in the opened Chrome window, then press Enter here to save and close...")
    finally:
        driver.quit()


def scrape_ads_library(
    url: str,
    data_limit: int | None = 10,
    headless: bool = False,
    profile_dir: str | None = None,
) -> list[dict]:
    """
    Scrape a Facebook Ads Library search results page.

    url: the ads-library URL to visit.
    data_limit: set to an integer to stop after that many ads, or None to
        scrape everything the page reports.
    headless: run Chrome headless (needed in CI where there is no display).
    profile_dir: optional Chrome profile folder holding a Facebook login
        (see login_to_facebook); needed to see age-restricted ads.

    If the FB_COOKIES environment variable is set, those Facebook session
    cookies are loaded first so age-restricted ads are visible.
    """

    fb_cookies = os.getenv("FB_COOKIES")

    results_locator = (
        "xpath",
        './/div[@class="x8t9es0 x1uxerd5 xrohxju x108nfp6 xq9mrsl x1h4wwuj x117nqv4 xeuugli"]'
    )

    def _age_gated(driver) -> bool:
        return any(
            el.is_displayed()
            for el in driver.find_elements("xpath", '//*[contains(text(),"confirm your age")]')
        )

    # Age-restricted advertisers (e.g. him) hide each ad's media behind a
    # "confirm your age by logging in" box unless the browser is logged in.
    # Even with valid cookies, Facebook randomly decides per browser session
    # whether to serve the gated version, and that choice sticks for the whole
    # session (reloading doesn't help). So when gated, start a fresh browser.
    max_attempts = 5 if fb_cookies else 1

    for attempt in range(1, max_attempts + 1):
        driver = _build_driver(headless, profile_dir)

        if fb_cookies:
            _load_fb_cookies(driver, fb_cookies)

        # Navigate to the website
        driver.get(url)

        try:
            results = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(results_locator)
            ).text
        except TimeoutException:
            title = driver.title
            driver.quit()
            raise RuntimeError(
                "Timed out waiting for the ads library results count to appear. "
                "Facebook may be showing a login/consent wall instead of the ads "
                f"library page (page title: {title!r})."
            )

        time.sleep(3)
        if not (fb_cookies and _age_gated(driver)):
            break

        driver.quit()
        if attempt == max_attempts:
            raise RuntimeError(
                f"Ads were still age-gated in {max_attempts} fresh browser sessions even "
                "though FB_COOKIES was set. The Facebook cookies have probably expired "
                "or been logged out: export fresh cookies and update FB_COOKIES."
            )
        print(f"[warn] ads are age-gated in this browser session (attempt {attempt}/{max_attempts}); starting a fresh one")
        time.sleep(5)

    try:
        total_results = int(
            results.replace('~', '')
                   .replace(',', '')
                   .replace(' results', '')
        )

        print(f"[debug] reported total_results: {total_results}")

        if _age_gated(driver):
            print("[warn] ads are age-gated; media/text will be empty. Set FB_COOKIES to log in.")

        # Scroll only when needed
        stall_count = 0
        max_stalls = 6  # consecutive no-growth scrolls tolerated before accepting we've hit bottom (limit=None only)
        scroll_attempt = 0

        while True:

            compare_result = driver.find_elements(
                "xpath",
                '(//div[@class="x1plvlek xryxfnj x1gzqxud x178xt8z x1lun4ml xso031l xpilrb4 xb9moi8 xe76qn7 x21b0me x142aazg x1i5p2am x1whfx0g xr2y4jy x1ihp6rs x1kmqopl x13fuv20 x18b5jzi x1q0q8m5 x1t7ytsu x9f619"]//div[@class="xh8yej3"])'
            )

            loaded_result = int(len(compare_result))

            print(f"[debug] scroll_attempt={scroll_attempt} loaded_result={loaded_result} total_results={total_results} stall_count={stall_count}")
            scroll_attempt += 1

            # If user only wants a limited amount
            if data_limit is not None:
                if loaded_result >= data_limit:
                    break

            # If user wants everything
            else:
                if loaded_result >= total_results:
                    break

            previous_loaded = loaded_result

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(6)

            compare_result = driver.find_elements(
                "xpath",
                '(//div[@class="x1plvlek xryxfnj x1gzqxud x178xt8z x1lun4ml xso031l xpilrb4 xb9moi8 xe76qn7 x21b0me x142aazg x1i5p2am x1whfx0g xr2y4jy x1ihp6rs x1kmqopl x13fuv20 x18b5jzi x1q0q8m5 x1t7ytsu x9f619"]//div[@class="xh8yej3"])'
            )

            loaded_result = int(len(compare_result))

            # No more ads are loading
            if loaded_result == previous_loaded:
                if data_limit is None:
                    stall_count += 1
                    if stall_count >= max_stalls:
                        break
                else:
                    break
            else:
                stall_count = 0

        compare_result = driver.find_elements(
            "xpath",
            '(//div[@class="x1plvlek xryxfnj x1gzqxud x178xt8z x1lun4ml xso031l xpilrb4 xb9moi8 xe76qn7 x21b0me x142aazg x1i5p2am x1whfx0g xr2y4jy x1ihp6rs x1kmqopl x13fuv20 x18b5jzi x1q0q8m5 x1t7ytsu x9f619"]//div[@class="xh8yej3"])'
        )

        loaded_result = int(len(compare_result))

        if data_limit is not None:
            compare_result = min(data_limit, loaded_result)
        else:
            compare_result = loaded_result

        collected_data = []

        for i in range(compare_result):      # <-- Number of ads to capture

            viewmores = driver.find_elements(
                "xpath",
                '//div[text()="See summary details" or text()="See ad details"]'
            )

            if i >= len(viewmores):
                break

            # Scope every field to the card that owns this ad's "See ad details"
            # button: the outermost ancestor that still contains only one such
            # button. That keeps media/headline/body tied to the same ad as the
            # details (library id, dates) instead of relying on two separate
            # positional indexes lining up.
            cards = viewmores[i].find_elements(
                "xpath",
                './ancestor::div[count(.//div[text()="See summary details" or text()="See ad details"])=1][last()]'
            )
            if cards:
                first_layer = cards[0]
            else:
                first_layer = driver.find_element("xpath", f'(//div[@class="xdj266r x11t971q xat24cr xvc5jky x1dr75xp xh8yej3 xkopdvs"]//div[@class="xh8yej3"])[{i+1}]')

            try:
                poster_name = first_layer.find_element("xpath", './/a[contains(@href,"facebook.com")]').text
            except NoSuchElementException:
                poster_name = None

            try:
                poster_url = first_layer.find_element("xpath", './/a[contains(@href,"facebook.com")]').get_attribute("href")
            except NoSuchElementException:
                poster_url = None

            posted_with = None
            posted_withs = first_layer.find_elements("xpath", './/*[contains(text(),"with")]')
            if posted_withs:
                posted_with = posted_withs[0].text

            try:
                body_text = first_layer.find_element("xpath", './/div[@style="white-space: pre-wrap;"]').get_attribute("innerText")
            except NoSuchElementException:
                body_text = None

            try:
                media_url = first_layer.find_element(
                    "xpath",
                    './/div[@class="x5yr21d x1uhb9sk xh8yej3"]//video | .//div[@class="x1ywc1zp x78zum5 xl56j7k x1e56ztr x1277o0a"]//img'
                ).get_attribute("src")
            except NoSuchElementException:
                media_url = None

            try:
                shop_now_url = first_layer.find_element("xpath", './/a[@class="x1hl2dhg x1lku1pv x8t9es0 x1fvot60 xxio538 xjnfcd9 xq9mrsl x1yc453h x1h4wwuj x1fcty0u x1lliihq"]').get_attribute("href")
            except NoSuchElementException:
                shop_now_url = None

            try:
                headline = first_layer.find_element("xpath", './/div[@class="x6ikm8r x10wlt62 xlyipyv x1mcwxda x190qgfh"]').text
            except NoSuchElementException:
                headline = None

            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", viewmores[i])
            driver.execute_script("arguments[0].click();", viewmores[i])

            time.sleep(1)

            data_to_gets = driver.find_elements(
                "xpath",
                '''
                //div[@class="xt9c220 x1sdr0u7 x1on1db2 xrvj5dj xmz0i5r"]
                  //div[@class="x1cy8zhl x78zum5 xyamay9 xv54qhq x18d9i69 xf7dkkf x1n2onr6"]
                  //div[@class="x78zum5 xdt5ytf x2lwn1j xeuugli"]
                |
                (//div[@class="xyamay9 xv54qhq x1l90r2v xf7dkkf x106t9lo xmd1z x1gzqxud x1i5p2am x1whfx0g xr2y4jy x1ihp6rs"]
                  //div[@class="x78zum5 xdt5ytf x2lwn1j xeuugli"])[1]
                '''
            )

            if not data_to_gets:
                ad_data = {
                    "poster_name": poster_name,
                    "poster_url": poster_url,
                    "posted_with": posted_with,
                    "body_text": body_text,
                    "media_url": media_url,
                    "shop_now_url": shop_now_url,
                    "headline": headline,
                    "status": None,
                    "library_id": None,
                    "started_running": None,
                    "platforms": [],
                    "multiple_versions": False,
                    "ad_snapshot_url": None
                }
                collected_data.append(ad_data)

            for data_to_get in data_to_gets:

                lines = data_to_get.text.split("\n")

                ad_data = {
                    "poster_name": poster_name,
                    "poster_url": poster_url,
                    "posted_with": posted_with,
                    "body_text": body_text,
                    "media_url": media_url,
                    "shop_now_url": shop_now_url,
                    "headline": headline,
                    "status": None,
                    "library_id": None,
                    "started_running": None,
                    "platforms": [],
                    "multiple_versions": False,
                    "ad_snapshot_url": None
                }

                for line in lines:

                    line = line.strip()

                    if line == "Active":
                        ad_data["status"] = line

                    elif line.startswith("Library ID:"):
                        ad_data["library_id"] = line.replace("Library ID:", "").strip()

                    elif line.startswith("Started running on"):
                        ad_data["started_running"] = line.replace("Started running on", "").strip()

                    elif line == "Platforms":
                        platform_map = {
                            "0px -955px": "Facebook",
                            "0px -1007px": "Instagram",
                            "-388px -732px": "Audience Network",
                            "-387px -753px": "Messenger",
                            "-387px -766px": "Threads"
                        }

                        ad_data["platforms"] = []

                        icons = data_to_get.find_elements(
                            "xpath",
                            './/div[contains(@style,"mask-position")]'
                        )

                        for icon in icons:

                            style = icon.get_attribute("style")

                            for position, platform in platform_map.items():
                                if f"mask-position: {position}" in style:
                                    ad_data["platforms"].append(platform)
                                    break

                    elif "multiple versions" in line.lower():
                        ad_data["multiple_versions"] = True

                if ad_data["library_id"]:
                    ad_data["ad_snapshot_url"] = f"https://www.facebook.com/ads/library/?id={ad_data['library_id']}"

                collected_data.append(ad_data)
                time.sleep(2)

            # Close the ad-details modal. Facebook's DOM shifts often, so match the
            # close button by its accessible label instead of an absolute path,
            # and fall back to pressing Escape if it can't be found.
            closes = driver.find_elements(
                "xpath",
                '//div[@role="dialog"]//div[@aria-label="Close" or @aria-label="close"]'
                ' | //div[@aria-label="Close" and @role="button"]'
            )
            if closes:
                driver.execute_script("arguments[0].click();", closes[-1])
            else:
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()

            time.sleep(1)
            if driver.find_elements("xpath", '//div[@role="dialog"]'):
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()

            print(f"Done scraping ad page {i+1}")
            time.sleep(2)

        return collected_data

    finally:
        driver.quit()
