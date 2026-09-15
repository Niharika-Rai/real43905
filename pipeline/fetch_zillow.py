"""
Live pull from Zillow Research's public bulk CSV exports: ZHVI (Zillow
Home Value Index) and ZORI (Zillow Observed Rent Index), metro-level.

No auth required. Zillow's metro files key on "RegionName" formatted as
"City, ST" (e.g. "New York, NY") rather than CBSA code, so results are
joined back to our metro table by name -- see NAME_TO_CBSA in
pipeline/build_dataset.py.
"""

from __future__ import annotations

import pandas as pd
import requests

TIMEOUT = 30

ZORI_URL = (
    "https://files.zillowstatic.com/research/public_csv/zori/"
    "Metro_zori_uc_sfrcondomfr_sm_month.csv"
)
ZHVI_URL = (
    "https://files.zillowstatic.com/research/public_csv/zhvi/"
    "Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)


def _load_wide_csv(url: str) -> pd.DataFrame:
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    from io import StringIO

    return pd.read_csv(StringIO(resp.text))


def _latest_and_n_years_ago_growth(df: pd.DataFrame, years_back: int = 3) -> pd.DataFrame:
    date_cols = [c for c in df.columns if c[:4].isdigit() and "-" in c]
    date_cols = sorted(date_cols)
    latest_col = date_cols[-1]
    # find a column ~years_back years before the latest month
    target_idx = max(0, len(date_cols) - 1 - years_back * 12)
    past_col = date_cols[target_idx]

    out = df[["RegionName", latest_col, past_col]].copy()
    out = out.rename(columns={"RegionName": "region_name", latest_col: "value_latest", past_col: "value_past"})
    out["growth_pct"] = (out["value_latest"] / out["value_past"] - 1) * 100
    return out


def rent_growth_3yr() -> pd.DataFrame:
    """3-year cumulative growth in Zillow Observed Rent Index, by metro name."""
    df = _load_wide_csv(ZORI_URL)
    out = _latest_and_n_years_ago_growth(df, years_back=3)
    return out.rename(columns={"growth_pct": "rent_growth_3yr_pct"})[["region_name", "rent_growth_3yr_pct"]]


def home_value_growth_3yr() -> pd.DataFrame:
    """3-year cumulative growth in Zillow Home Value Index, by metro name."""
    df = _load_wide_csv(ZHVI_URL)
    out = _latest_and_n_years_ago_growth(df, years_back=3)
    return out.rename(columns={"growth_pct": "zhvi_growth_3yr_pct"})[["region_name", "zhvi_growth_3yr_pct"]]
