"""
Anchor values for median home price and median household income by metro.

These anchor the synthetic dataset to plausible, internally-consistent
mid-2020s market levels so that derived ratios (price-to-income, etc.) look
like a real cross-section of U.S. metros even before live data is wired in.
They are ILLUSTRATIVE, not sourced from a specific live pull -- see
pipeline/fetch_census.py for the real ACS B25077 / B19013 pulls that should
replace these values when the app runs with network access (e.g. on Render).

Values are in whole dollars.
"""

from __future__ import annotations

# cbsa -> (median_home_price_usd, median_household_income_usd)
ANCHORS: dict[str, tuple[int, int]] = {
    "35620": (650_000, 92_000),   # New York
    "31080": (880_000, 86_000),   # Los Angeles
    "16980": (310_000, 78_000),   # Chicago
    "19100": (370_000, 80_000),   # Dallas-Fort Worth
    "26420": (310_000, 74_000),   # Houston
    "47900": (570_000, 115_000),  # Washington, DC
    "33100": (480_000, 68_000),   # Miami
    "12060": (370_000, 78_000),   # Atlanta
    "37980": (320_000, 82_000),   # Philadelphia
    "38060": (430_000, 74_000),   # Phoenix
    "14460": (650_000, 105_000),  # Boston
    "40140": (520_000, 78_000),   # Riverside
    "41860": (1_100_000, 130_000),  # San Francisco
    "19820": (230_000, 65_000),   # Detroit
    "42660": (650_000, 105_000),  # Seattle
    "33460": (350_000, 90_000),   # Minneapolis
    "45300": (370_000, 66_000),   # Tampa
    "41740": (850_000, 92_000),   # San Diego
    "19740": (550_000, 92_000),   # Denver
    "12580": (330_000, 90_000),   # Baltimore
    "41180": (230_000, 70_000),   # St. Louis
    "36740": (380_000, 68_000),   # Orlando
    "16740": (380_000, 76_000),   # Charlotte
    "41700": (290_000, 66_000),   # San Antonio
    "38900": (530_000, 84_000),   # Portland
    "40900": (530_000, 84_000),   # Sacramento
    "38300": (220_000, 68_000),   # Pittsburgh
    "12420": (450_000, 88_000),   # Austin
    "29820": (410_000, 68_000),   # Las Vegas
    "17140": (250_000, 70_000),   # Cincinnati
    "28140": (280_000, 72_000),   # Kansas City
    "18140": (290_000, 72_000),   # Columbus
    "26900": (240_000, 68_000),   # Indianapolis
    "17460": (210_000, 62_000),   # Cleveland
    "41940": (1_400_000, 155_000),  # San Jose
    "34980": (430_000, 76_000),   # Nashville
    "47260": (300_000, 72_000),   # Virginia Beach
    "39300": (420_000, 82_000),   # Providence
    "33340": (280_000, 68_000),   # Milwaukee
    "27260": (330_000, 68_000),   # Jacksonville
    "36420": (230_000, 62_000),   # Oklahoma City
    "39580": (410_000, 82_000),   # Raleigh
    "32820": (220_000, 58_000),   # Memphis
    "40060": (330_000, 78_000),   # Richmond
    "31140": (240_000, 64_000),   # Louisville
    "35380": (250_000, 55_000),   # New Orleans
    "41620": (530_000, 86_000),   # Salt Lake City
    "25540": (280_000, 82_000),   # Hartford
    "15380": (220_000, 62_000),   # Buffalo
    "13820": (210_000, 58_000),   # Birmingham
}
