"""
Live pull from FHFA's House Price Index (HPI), metro-area (MSA) series.

FHFA publishes a public bulk CSV, no auth required. This is used as a
cross-check / alternative source for home-price growth (the ACS B25077
median value is self-reported and lags; FHFA HPI is a repeat-sales index
and moves faster).
"""

from __future__ import annotations

import io

import pandas as pd
import requests

TIMEOUT = 30
HPI_MSA_URL = "https://www.fhfa.gov/hpi/download/annual/HPI_AT_metro.csv"


def hpi_by_metro() -> pd.DataFrame:
    """All-transactions annual HPI by metro area, long format.

    Returns columns: metro_name, cbsa, year, index_nsa, annual_change_pct.
    The published file has no header row; column order is
    (Metro Name, CBSA, Year, Index (NSA), Annual % change).
    """
    resp = requests.get(HPI_MSA_URL, timeout=TIMEOUT)
    resp.raise_for_status()
    df = pd.read_csv(
        io.StringIO(resp.text),
        header=None,
        names=["metro_name", "cbsa", "year", "index_nsa", "annual_change_pct"],
    )
    df["cbsa"] = df["cbsa"].astype(str).str.zfill(5)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["index_nsa"] = pd.to_numeric(df["index_nsa"], errors="coerce")
    df["annual_change_pct"] = pd.to_numeric(df["annual_change_pct"], errors="coerce")
    return df


def home_price_cagr(cbsas: list[str], start_year: int, end_year: int) -> pd.DataFrame:
    """CAGR of the FHFA HPI index between two years, by CBSA."""
    df = hpi_by_metro()
    df = df[df["cbsa"].isin(cbsas) & df["year"].isin([start_year, end_year])]
    pivot = df.pivot_table(index="cbsa", columns="year", values="index_nsa", aggfunc="last")
    n_years = end_year - start_year
    pivot["home_price_cagr_pct"] = ((pivot[end_year] / pivot[start_year]) ** (1 / n_years) - 1) * 100
    return pivot.reset_index()[["cbsa", "home_price_cagr_pct"]].dropna()
