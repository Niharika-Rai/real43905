"""
Live pull from FRED (Federal Reserve Economic Data).

Uses the public fredgraph.csv export endpoint, which does not require an
API key for a single series download. If FRED_API_KEY is set, the JSON API
is used instead (slightly more robust / higher rate limits).
"""

from __future__ import annotations

import io
import os

import pandas as pd
import requests

TIMEOUT = 20
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")


def series_csv(series_id: str) -> pd.DataFrame:
    """Fetch a FRED series as a DataFrame with columns date, value (no key needed)."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna()


def latest_10yr_treasury_pct() -> float:
    """FRED DGS10 -- 10-Year Treasury Constant Maturity Rate, most recent value.

    Used as a macro input for a cap-rate floor/benchmark (cap rates broadly
    track the risk-free rate plus a spread).
    """
    df = series_csv("DGS10")
    return float(df.sort_values("date").iloc[-1]["value"])
