"""
Orchestrates the full metro dataset build: try live public-data sources for
every field that can, in principle, come from one; fall back to the
tier-calibrated synthetic generator (pipeline/synthetic.py) for anything
that fails, is unavailable, or -- per the project charter -- has no free
public source at all (land cost, construction $/SF, cap rate, opex,
vacancy/collection loss, units/acre, permit velocity).

Usage:
    python -m pipeline.build_dataset                 # synthetic-only (safe default)
    ENABLE_LIVE_FETCH=1 python -m pipeline.build_dataset   # attempt live pulls first

Output: data/metro_dataset.csv, plus a `<field>__source` column for every
live-eligible field recording "live" or "synthetic".

In this development sandbox, outbound network access to Census/Zillow/FHFA/
FRED is blocked by the environment's egress policy, so ENABLE_LIVE_FETCH
runs will simply fail over to synthetic for every field -- the exact same
fallback path that fires in production if a source is temporarily down.
Live fetching is fully wired for deployment environments (e.g. Render) that
have normal outbound network access.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metros import TOP_50_METROS  # noqa: E402
from pipeline.synthetic import generate_synthetic_dataset, LIVE_ELIGIBLE_FIELDS  # noqa: E402

# Zillow's metro files key on "City, ST" region names -- map those onto our
# CBSA codes. Kept close to metros.short_name but Zillow's naming can
# diverge slightly (e.g. it drops the second city in "Dallas-Fort Worth").
NAME_TO_CBSA = {m.short_name: m.cbsa for m in TOP_50_METROS}
ZILLOW_NAME_OVERRIDES = {
    "Dallas-Fort Worth, TX": "Dallas, TX",
    "Washington, DC": "Washington, DC",
    "Miami, FL": "Miami, FL",
}


def _try_live_shortage_fields(cbsas: list[str]) -> pd.DataFrame:
    """Attempt every live shortage-side pull; return whatever succeeds.

    Each sub-fetch is isolated in its own try/except so a single failing
    source (e.g. BPS file layout drift) doesn't block the others.
    """
    frames = []

    try:
        from pipeline import fetch_census

        income = fetch_census.median_household_income()
        income = income[income["cbsa"].isin(cbsas)][["cbsa", "median_household_income_usd"]]
        frames.append(income)
    except Exception as exc:  # noqa: BLE001
        print(f"[build_dataset] live median_household_income failed: {exc}")

    try:
        from pipeline import fetch_census

        home_value = fetch_census.median_home_value()
        home_value = home_value[home_value["cbsa"].isin(cbsas)][["cbsa", "median_home_price_usd"]]
        frames.append(home_value)
    except Exception as exc:  # noqa: BLE001
        print(f"[build_dataset] live median_home_value failed: {exc}")

    try:
        from pipeline import fetch_census

        vac = fetch_census.vacancy_rates()
        vac = vac[vac["cbsa"].isin(cbsas)][["cbsa", "homeowner_vacancy_pct", "rental_vacancy_pct"]]
        frames.append(vac)
    except Exception as exc:  # noqa: BLE001
        print(f"[build_dataset] live vacancy_rates failed: {exc}")

    try:
        from pipeline import fetch_zillow

        rent_growth = fetch_zillow.rent_growth_3yr()
        rent_growth["cbsa"] = rent_growth["region_name"].map(
            {**{v: NAME_TO_CBSA[k] for k, v in ZILLOW_NAME_OVERRIDES.items()}, **NAME_TO_CBSA}
        )
        rent_growth = rent_growth.dropna(subset=["cbsa"])[["cbsa", "rent_growth_3yr_pct"]]
        frames.append(rent_growth)
    except Exception as exc:  # noqa: BLE001
        print(f"[build_dataset] live rent_growth_3yr failed: {exc}")

    if not frames:
        return pd.DataFrame(columns=["cbsa"])

    merged = frames[0]
    for f in frames[1:]:
        merged = merged.merge(f, on="cbsa", how="outer")
    return merged


def build(enable_live: bool | None = None) -> pd.DataFrame:
    enable_live = ENABLE_LIVE_FETCH if enable_live is None else enable_live

    synthetic = generate_synthetic_dataset()
    cbsas = synthetic["cbsa"].tolist()

    # every live-eligible field starts flagged synthetic; live pulls (if any
    # succeed) overwrite both the value and the flag below
    for field in LIVE_ELIGIBLE_FIELDS:
        synthetic[f"{field}__source"] = "synthetic"
    for field in synthetic.columns:
        if field.endswith("__source"):
            continue
        if field not in LIVE_ELIGIBLE_FIELDS and field not in ("cbsa", "metro", "tier", "data_vintage"):
            synthetic[f"{field}__source"] = "synthetic"

    if enable_live:
        live = _try_live_shortage_fields(cbsas)
        if not live.empty:
            live = live.set_index("cbsa")
            for field in live.columns:
                if field not in synthetic.columns:
                    continue
                have_value = live[field].notna()
                idx = synthetic["cbsa"].map(live[field]).notna()
                synthetic.loc[idx, field] = synthetic["cbsa"].map(live[field])[idx]
                synthetic.loc[idx, f"{field}__source"] = "live"

    synthetic["data_vintage"] = (
        "live-refresh-" + datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if enable_live
        else "synthetic-2024-estimate"
    )
    return synthetic


ENABLE_LIVE_FETCH = os.environ.get("ENABLE_LIVE_FETCH", "0") == "1"


def main() -> None:
    df = build()
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "metro_dataset.csv")
    df.to_csv(out_path, index=False)

    n_live = sum(
        (df[c] == "live").sum() for c in df.columns if c.endswith("__source")
    )
    n_total = sum(
        len(df) for c in df.columns if c.endswith("__source")
    )
    print(f"[build_dataset] wrote {len(df)} metros to {out_path}")
    print(f"[build_dataset] live-sourced values: {n_live}/{n_total} field-metro cells")


if __name__ == "__main__":
    main()
