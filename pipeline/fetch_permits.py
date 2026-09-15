"""
Live pull from the Census Bureau's Building Permits Survey (BPS),
metro-area annual new privately-owned housing units authorized.

BPS publishes fixed-format text files per year, e.g.:
https://www2.census.gov/econ/bps/Metro/ma{YY}a.txt

This parses the "Total" units-authorized column keyed by CBSA code. The
file format has been stable for years but is whitespace/CSV-hybrid, so this
parser is defensive: any row it can't cleanly parse is skipped rather than
raising, since a handful of dropped rows just means those metros fall back
to synthetic permit data.
"""

from __future__ import annotations

import io

import pandas as pd
import requests

TIMEOUT = 20


def annual_permits_by_metro(year: int) -> pd.DataFrame:
    """Total housing units authorized by building permits, by CBSA, for one year.

    `year` is the 4-digit survey year (e.g. 2023). Returns columns:
    cbsa, permits_total_units.
    """
    yy = f"{year % 100:02d}"
    url = f"https://www2.census.gov/econ/bps/Metro/ma{yy}a.txt"
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()

    df = pd.read_csv(io.StringIO(resp.text), skiprows=2, header=None, on_bad_lines="skip")
    # Column layout (BPS "a" = annual, metro file): CBSA code is typically
    # the first column, total units in the "Bldgs/Units" total block.
    # Keep this narrow and defensive -- if the layout doesn't match what we
    # expect, raise so the caller falls back to synthetic data rather than
    # silently returning garbage.
    df = df.rename(columns={0: "cbsa"})
    df["cbsa"] = df["cbsa"].astype(str).str.extract(r"(\d{5})")[0]
    df = df.dropna(subset=["cbsa"])

    # Total units authorized is typically the last numeric "Total" column
    # in the annual metro file; select the last column as a best-effort.
    numeric_cols = [c for c in df.columns if c != "cbsa" and pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        raise ValueError("Could not locate a numeric permits column in BPS file")
    df["permits_total_units"] = pd.to_numeric(df[numeric_cols[-1]], errors="coerce")

    return df[["cbsa", "permits_total_units"]].dropna()


def permits_per_1000_units_cagr(
    cbsas: list[str],
    total_housing_units: pd.DataFrame,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """CAGR of (trailing permits authorized / existing housing-unit stock * 1000).

    `total_housing_units` must have columns cbsa, total_housing_units
    (e.g. from fetch_census.total_housing_units).
    """
    start = annual_permits_by_metro(start_year).rename(columns={"permits_total_units": "permits_start"})
    end = annual_permits_by_metro(end_year).rename(columns={"permits_total_units": "permits_end"})

    merged = total_housing_units.merge(start, on="cbsa", how="inner").merge(end, on="cbsa", how="inner")
    merged = merged[merged["cbsa"].isin(cbsas)]

    merged["ratio_start"] = merged["permits_start"] / merged["total_housing_units"] * 1000
    merged["ratio_end"] = merged["permits_end"] / merged["total_housing_units"] * 1000

    n_years = end_year - start_year
    with pd.option_context("mode.use_inf_as_na", True):
        merged["permits_per_1000_cagr_pct"] = (
            (merged["ratio_end"] / merged["ratio_start"]).clip(lower=1e-6) ** (1 / n_years) - 1
        ) * 100

    return merged[["cbsa", "permits_per_1000_cagr_pct"]].dropna()
