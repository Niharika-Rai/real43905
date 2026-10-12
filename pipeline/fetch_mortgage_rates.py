"""
Live pull of today's benchmark mortgage rates from Mortgage News Daily's
public rates page, for the Buy-Down Calculator's rate-preset dropdown.

No auth required -- mortgagenewsdaily.com publishes a plain rates page.
MND doesn't offer a documented JSON API for this, so the page is scraped:
HTML tags are stripped to plain text, then each loan type's rate is
located by searching near its label text for a percentage figure. This is
necessarily a best-effort text match (brittle to page redesigns) rather
than a stable CSS/JSON contract, so a clean result requires finding ALL
six rates with plausible values -- a partial/ambiguous parse returns None
rather than risk returning a mismatched rate for the wrong loan type.

This app's dev sandbox has restricted outbound network access and cannot
reach mortgagenewsdaily.com (confirmed directly -- same as Census, Zillow,
FHFA, and FRED; see README). fetch_live_rates() will return None in that
environment every time, which is the expected and handled failure path:
callers fall back to FALLBACK_RATES. The live path is real code, not a
stub, and will start working the moment this runs somewhere with normal
internet access (e.g. a deployed Render service).
"""

from __future__ import annotations

import re

import requests

TIMEOUT = 10

MND_URL = "https://www.mortgagenewsdaily.com/mortgage-rates"

_HEADERS = {
    # A plain `requests` default User-Agent is blocked by some sites' bot
    # filters; a normal browser-looking UA avoids that false negative.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Our preset label -> text aliases to search for on the page (MND's own
# label wording may differ slightly or change over time, so each loan type
# lists a few plausible phrasings to try, in order).
_RATE_LABEL_ALIASES: dict[str, list[str]] = {
    "30-Year Fixed": ["30 Yr. Fixed", "30 Year Fixed", "30yr Fixed", "30-Year Fixed"],
    "15-Year Fixed": ["15 Yr. Fixed", "15 Year Fixed", "15yr Fixed", "15-Year Fixed"],
    "FHA 30-Year Fixed": ["30 Yr. FHA", "FHA 30 Year", "FHA 30yr", "30-Year FHA"],
    "VA 30-Year Fixed": ["30 Yr. VA", "VA 30 Year", "VA 30yr", "30-Year VA"],
    "Jumbo 30-Year Fixed": ["30 Yr. Jumbo", "Jumbo 30 Year", "Jumbo 30yr", "30-Year Jumbo"],
    "5/1 ARM (initial rate)": ["5/1 ARM", "5-1 ARM", "5 Yr. ARM"],
}

# Illustrative fallback -- used whenever the live fetch fails, is
# incomplete, or returns an implausible value. Kept here (not just in
# app.py) so the fallback and the live-fetch label set are defined once,
# in the same place, and can't drift apart.
FALLBACK_RATES: dict[str, float] = {
    "30-Year Fixed": 6.50,
    "15-Year Fixed": 5.75,
    "FHA 30-Year Fixed": 6.25,
    "VA 30-Year Fixed": 6.10,
    "Jumbo 30-Year Fixed": 6.65,
    "5/1 ARM (initial rate)": 5.90,
}

_RATE_PATTERN = re.compile(r"(\d{1,2}\.\d{1,3})\s*%")
_SEARCH_WINDOW = 200  # chars to look ahead of a label for its rate figure
_MIN_PLAUSIBLE_PCT = 0.5
_MAX_PLAUSIBLE_PCT = 20.0


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text


def _find_rate_near_label(text: str, aliases: list[str]) -> float | None:
    for alias in aliases:
        idx = text.lower().find(alias.lower())
        if idx == -1:
            continue
        window = text[idx : idx + _SEARCH_WINDOW]
        match = _RATE_PATTERN.search(window)
        if match:
            value = float(match.group(1))
            if _MIN_PLAUSIBLE_PCT <= value <= _MAX_PLAUSIBLE_PCT:
                return value
    return None


def fetch_live_rates(timeout: int = TIMEOUT) -> dict[str, float] | None:
    """Best-effort live scrape of today's benchmark rates by loan type.

    Returns a dict with exactly the same keys as FALLBACK_RATES on a clean
    full parse, or None if the page is unreachable, the request fails, or
    any single rate can't be confidently located -- callers should treat
    None as "use the fallback," not retry in a loop.
    """
    try:
        resp = requests.get(MND_URL, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    text = _strip_html(resp.text)
    rates: dict[str, float] = {}
    for label, aliases in _RATE_LABEL_ALIASES.items():
        value = _find_rate_near_label(text, aliases)
        if value is None:
            return None  # incomplete parse -- don't return a partial/mismatched set
        rates[label] = value
    return rates
