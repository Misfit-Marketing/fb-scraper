"""Registry of Facebook Ads Library URLs to scrape, grouped by site/client name.

Add a new client by adding a key with a list of one or more ads-library URLs.

Prefer page URLs (view_all_page_id=...). A keyword-search URL (q=...) also
returns other advertisers that merely mention the keyword, so give those a
POSTER_FILTERS entry to keep only the brand's own ads.
"""
from __future__ import annotations

WEBSITES: dict[str, list[str]] = {
    "carpe": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=315614678610514",
    ],
    "hexclad": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=306050696452078",
    ],
    "ridge wallet": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=176366735873065",
    ],
    "boka": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=1588086141435020",
    ],
    "simple modern": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=921864094549584",
    ],
    "gruns": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=107585658730958",
    ],
    "him": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=355136938262536",
    ],
    "shrubhub": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&q=ShrubHub&search_type=keyword_unordered&sort_data[direction]=desc&sort_data[mode]=total_impressions",
    ],
    "yardzen": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=194820137983518",
    ],
    "belgard": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=247619129935",
    ],
    "allied outdoor solutions": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=240154596024517",
    ],
    "pacific pavers": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&q=Pacific%20Pavers&search_type=keyword_unordered&sort_data[direction]=desc&sort_data[mode]=total_impressions",
    ],
    "bayside pavers": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=510293819176431",
    ],
    "nicosia backyard design": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=119774925030490",
    ],
    "mirador outdoor": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=197406813446746",
    ],
    "west shore home": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=218653264675416",
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=173483429401275",
    ],
    "leaf home": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=131079286762825",
    ],
    "archadeck": [
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=1590658784490429",
    ],
}

# For keyword-search entries: keep only ads whose poster_url contains this
# text (the brand's own Facebook page), dropping other advertisers.
POSTER_FILTERS: dict[str, str] = {
    "shrubhub": "facebook.com/shrubhubofficial",
    "pacific pavers": "facebook.com/100057424189202",
}
