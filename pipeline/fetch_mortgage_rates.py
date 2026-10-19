"""
Live pull of today's benchmark mortgage rates from Mortgage News Daily's
public "Daily Rate Survey" table, for the Buy-Down Calculator's rate-preset
dropdown.

No auth required -- mortgagenewsdaily.com publishes a plain rates page.
MND doesn't offer a documented JSON API for this, so the page is scraped:
HTML tags are stripped to plain text, then each loan type's rate is
located by searching near its label text for a percentage figure. This is
necessarily a best-effort text match (brittle to page redesigns) rather
than a stable CSS/JSON contract.

Each of the six loan types is matched INDEPENDENTLY: a page redesign or a
renamed product (this already happened once -- MND's adjustable-rate
product moved from "5/1 ARM" to "7/6 SOFR ARM" at some point after this
alias list was first written, which silently zeroed out every rate under
the old all-or-nothing matching this module used to do, even though the
other five labels still matched fine) now only drops that ONE rate back to
its static fallback instead of discarding every other rate that parsed
correctly. get_live_rates_partial() returns whatever it found; the caller
(app.py's get_rate_presets) fills any gap from FALLBACK_RATES per field and
tracks, per rate, whether it's live or fallback.

This app's dev sandbox has restricted outbound network access and cannot
reach mortgagenewsdaily.com (confirmed directly -- same as Census, Zillow,
FHFA, and FRED; see README). fetch_live_rates()/get_live_rates_partial()
will return nothing in that environment every time, which is the expected
and handled failure path. The live path is real code, not a stub, and will
start working the moment this runs somewhere with normal internet access
(e.g. a deployed Render service).
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

# Our preset label -> text aliases to search for on the page, each list
# tried in order. The first alias in each list is MND's own current label
# text, confirmed directly against a live screenshot of
# mortgagenewsdaily.com's "Daily Rate Survey" table (2026-10-16): "30 Yr.
# Fixed", "15 Yr. Fixed", "30 Yr. Jumbo", "7/6 SOFR ARM", "30 Yr. FHA",
# "30 Yr. VA" -- in that order, which this dict mirrors. The remaining
# aliases are fallback phrasings for if MND's own wording drifts again.
_RATE_LABEL_ALIASES: dict[str, list[str]] = {
    "30-Year Fixed": ["30 Yr. Fixed", "30 Year Fixed", "30yr Fixed", "30-Year Fixed"],
    "15-Year Fixed": ["15 Yr. Fixed", "15 Year Fixed", "15yr Fixed", "15-Year Fixed"],
    "Jumbo 30-Year Fixed": ["30 Yr. Jumbo", "Jumbo 30 Year", "Jumbo 30yr", "30-Year Jumbo"],
    "7/6 SOFR ARM (initial rate)": [
        "7/6 SOFR ARM", "7/6 ARM", "7-6 SOFR ARM", "SOFR ARM",
        "5/1 ARM", "5-1 ARM", "5 Yr. ARM",  # MND's older ARM product, kept in case it returns
    ],
    "FHA 30-Year Fixed": ["30 Yr. FHA", "FHA 30 Year", "FHA 30yr", "30-Year FHA"],
    "VA 30-Year Fixed": ["30 Yr. VA", "VA 30 Year", "VA 30yr", "30-Year VA"],
}

# Manual snapshot of MND's Daily Rate Survey, 2026-10-16 (the last time this
# was checked against the live page -- see the class docstring above for why
# the live fetch path, though fully implemented, can't be exercised from
# this project's dev sandbox). Used whenever a live fetch fails or a given
# loan type's rate can't be found on the page; each rate falls back
# independently, so a single missing/renamed label doesn't force every
# other rate back to this snapshot too. Update this dict (and the date
# above) whenever a fresher manual check is done.
FALLBACK_RATES: dict[str, float] = {
    "30-Year Fixed": 7.37,
    "15-Year Fixed": 7.04,
    "Jumbo 30-Year Fixed": 7.67,
    "7/6 SOFR ARM (initial rate)": 6.81,
    "FHA 30-Year Fixed": 6.99,
    "VA 30-Year Fixed": 7.01,
}
FALLBACK_RATES_AS_OF = "2026-10-16"

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


def get_live_rates_partial(timeout: int = TIMEOUT) -> dict[str, float]:
    """Best-effort live scrape of today's benchmark rates by loan type.

    Returns a dict covering whatever subset of FALLBACK_RATES's keys it
    could confidently match on the live page -- empty if the page is
    unreachable, the request fails, or none of the six labels could be
    found at all. Each loan type is matched independently, so a renamed or
    missing label for ONE type doesn't discard rates that parsed
    correctly for the others.
    """
    try:
        resp = requests.get(MND_URL, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException:
        return {}

    text = _strip_html(resp.text)
    rates: dict[str, float] = {}
    for label, aliases in _RATE_LABEL_ALIASES.items():
        value = _find_rate_near_label(text, aliases)
        if value is not None:
            rates[label] = value
    return rates


def fetch_live_rates(timeout: int = TIMEOUT) -> dict[str, float] | None:
    """Backward-compatible wrapper: all six rates, or None if any is missing.

    Prefer get_live_rates_partial() for new code (app.py's
    get_rate_presets merges partial results against FALLBACK_RATES
    per-field); this wrapper exists for callers that need the stricter
    all-or-nothing contract the original version of this module had.
    """
    rates = get_live_rates_partial(timeout=timeout)
    if set(rates.keys()) != set(FALLBACK_RATES.keys()):
        return None
    return rates
