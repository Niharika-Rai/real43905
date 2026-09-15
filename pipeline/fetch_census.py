"""
Live pulls from the Census Bureau: ACS 5-Year Estimates and Population
Estimates Program (PEP), at the CBSA (metro) level.

These call api.census.gov directly. A CENSUS_API_KEY environment variable
is recommended (free, instant signup at https://api.census.gov/data/key_signup.html)
to avoid rate limiting, but small pulls like this generally work without one.

Every function returns a pandas DataFrame indexed by "cbsa", or raises on
failure -- callers (build_dataset.py) are expected to catch exceptions and
fall back to synthetic data per metro/field.
"""

from __future__ import annotations

import os

import pandas as pd
import requests

CENSUS_API_KEY = os.environ.get("CENSUS_API_KEY", "")
BASE = "https://api.census.gov/data"
TIMEOUT = 20


def _get(url: str, params: dict) -> list:
    if CENSUS_API_KEY:
        params = {**params, "key": CENSUS_API_KEY}
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def acs5_metro_variable(year: int, variable: str) -> pd.DataFrame:
    """Pull one ACS 5-Year variable for every Metropolitan Statistical Area.

    e.g. acs5_metro_variable(2022, "B19013_001E") -> median household income
    """
    url = f"{BASE}/{year}/acs/acs5"
    data = _get(
        url,
        {
            "get": f"NAME,{variable}",
            "for": "metropolitan statistical area/micropolitan statistical area:*",
        },
    )
    header, *rows = data
    df = pd.DataFrame(rows, columns=header)
    df = df.rename(
        columns={
            variable: variable,
            "metropolitan statistical area/micropolitan statistical area": "cbsa",
        }
    )
    df[variable] = pd.to_numeric(df[variable], errors="coerce")
    return df[["cbsa", "NAME", variable]]


def median_household_income(year: int = 2022) -> pd.DataFrame:
    """ACS 5-Year, Table B19013 -- median household income."""
    df = acs5_metro_variable(year, "B19013_001E")
    return df.rename(columns={"B19013_001E": "median_household_income_usd"})


def median_home_value(year: int = 2022) -> pd.DataFrame:
    """ACS 5-Year, Table B25077 -- median value, owner-occupied units."""
    df = acs5_metro_variable(year, "B25077_001E")
    return df.rename(columns={"B25077_001E": "median_home_price_usd"})


def median_gross_rent(year: int = 2022) -> pd.DataFrame:
    """ACS 5-Year, Table B25064 -- median gross rent."""
    df = acs5_metro_variable(year, "B25064_001E")
    return df.rename(columns={"B25064_001E": "median_gross_rent_usd"})


def total_housing_units(year: int = 2022) -> pd.DataFrame:
    """ACS 5-Year, Table B25001 -- total housing units (permits-ratio denominator)."""
    df = acs5_metro_variable(year, "B25001_001E")
    return df.rename(columns={"B25001_001E": "total_housing_units"})


def vacancy_rates(year: int = 2022) -> pd.DataFrame:
    """ACS 1-Year, Table DP04 -- rental & homeowner vacancy rate.

    DP04_0005PE = rental vacancy rate, DP04_0003PE = homeowner vacancy rate
    (profile-table variable IDs; verify against the current ACS data
    dictionary for the target year before relying on this in production).
    """
    url = f"{BASE}/{year}/acs/acs1/profile"
    data = _get(
        url,
        {
            "get": "NAME,DP04_0003PE,DP04_0005PE",
            "for": "metropolitan statistical area/micropolitan statistical area:*",
        },
    )
    header, *rows = data
    df = pd.DataFrame(rows, columns=header)
    df = df.rename(
        columns={
            "metropolitan statistical area/micropolitan statistical area": "cbsa",
            "DP04_0003PE": "homeowner_vacancy_pct",
            "DP04_0005PE": "rental_vacancy_pct",
        }
    )
    for c in ("homeowner_vacancy_pct", "rental_vacancy_pct"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[["cbsa", "NAME", "homeowner_vacancy_pct", "rental_vacancy_pct"]]


def population_estimate(year: int = 2023) -> pd.DataFrame:
    """Census Population Estimates Program (PEP), metro-area population."""
    url = f"{BASE}/{year}/pep/population"
    data = _get(
        url,
        {
            "get": "NAME,POP_2023,POP_2022",
            "for": "metropolitan statistical area/micropolitan statistical area:*",
        },
    )
    header, *rows = data
    df = pd.DataFrame(rows, columns=header)
    df = df.rename(
        columns={"metropolitan statistical area/micropolitan statistical area": "cbsa"}
    )
    for c in df.columns:
        if c.startswith("POP_"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
