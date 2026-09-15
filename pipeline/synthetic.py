"""
Synthetic data generation for fields the project charter flags as
unavailable from free public sources (land cost/acre, construction $/SF by
metro, cap rate, operating expenses, vacancy/collection loss, units/acre,
permit velocity) plus a deterministic fallback for the shortage-side fields
when a live pull isn't available (e.g. no network, no API key, source
temporarily down).

Design: every metro is tagged with a regional "tier" (see metros.py) that
sets realistic mean/std parameters for each field. Values are then drawn
with a per-metro deterministic seed (derived from the CBSA code) so the
dataset is reproducible and every run of the pipeline yields the same
numbers until the anchors/params below are deliberately changed.

Nothing here should be mistaken for observed data -- the app always labels
these columns' provenance as "synthetic" in the UI (see app.py).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from metros import TOP_50_METROS, SUPERSTAR_COASTAL, SUNBELT_GROWTH, MIDWEST_LEGACY, MIXED_NORTHEAST
from pipeline.anchors import ANCHORS

# (mean, std) per tier for every generated field.
TIER_PARAMS: dict[str, dict[str, tuple[float, float]]] = {
    SUPERSTAR_COASTAL: dict(
        pop_cagr_pct=(0.4, 0.3),
        permits_per_1000_cagr_pct=(-1.0, 1.5),
        rental_vacancy_pct=(4.0, 0.8),
        homeowner_vacancy_pct=(0.8, 0.3),
        rent_growth_3yr_pct=(9.0, 2.0),
        income_growth_3yr_pct=(10.0, 2.0),
        land_cost_per_acre_usd=(2_200_000, 500_000),
        construction_cost_per_sf_usd=(285, 25),
        vacancy_collection_loss_pct=(5.0, 1.0),
        operating_expense_per_unit_usd=(9500, 1000),
        cap_rate_pct=(4.6, 0.4),
        permit_velocity_index=(78, 8),
    ),
    SUNBELT_GROWTH: dict(
        pop_cagr_pct=(2.1, 0.5),
        permits_per_1000_cagr_pct=(3.0, 2.0),
        rental_vacancy_pct=(7.8, 1.0),
        homeowner_vacancy_pct=(1.6, 0.4),
        rent_growth_3yr_pct=(13.0, 3.0),
        income_growth_3yr_pct=(12.0, 2.5),
        land_cost_per_acre_usd=(700_000, 250_000),
        construction_cost_per_sf_usd=(190, 20),
        vacancy_collection_loss_pct=(6.5, 1.0),
        operating_expense_per_unit_usd=(7200, 900),
        cap_rate_pct=(5.6, 0.4),
        permit_velocity_index=(42, 10),
    ),
    MIDWEST_LEGACY: dict(
        pop_cagr_pct=(0.2, 0.3),
        permits_per_1000_cagr_pct=(0.5, 1.5),
        rental_vacancy_pct=(7.2, 1.2),
        homeowner_vacancy_pct=(1.9, 0.4),
        rent_growth_3yr_pct=(7.5, 2.0),
        income_growth_3yr_pct=(8.5, 2.0),
        land_cost_per_acre_usd=(280_000, 120_000),
        construction_cost_per_sf_usd=(155, 15),
        vacancy_collection_loss_pct=(7.0, 1.2),
        operating_expense_per_unit_usd=(6200, 700),
        cap_rate_pct=(6.6, 0.5),
        permit_velocity_index=(35, 9),
    ),
    MIXED_NORTHEAST: dict(
        pop_cagr_pct=(0.6, 0.4),
        permits_per_1000_cagr_pct=(1.0, 1.5),
        rental_vacancy_pct=(5.8, 1.0),
        homeowner_vacancy_pct=(1.3, 0.35),
        rent_growth_3yr_pct=(9.5, 2.0),
        income_growth_3yr_pct=(9.5, 2.0),
        land_cost_per_acre_usd=(520_000, 180_000),
        construction_cost_per_sf_usd=(200, 20),
        vacancy_collection_loss_pct=(6.0, 1.0),
        operating_expense_per_unit_usd=(7500, 800),
        cap_rate_pct=(5.8, 0.4),
        permit_velocity_index=(58, 10),
    ),
}

# Zoning/density tiers used by the feasibility calculator's "units per acre"
# assumption -- these are policy inputs, not observed statistics, per the
# project ideas doc. Exposed as an editable slider in the app.
DENSITY_TIERS: dict[str, dict[str, float]] = {
    "Garden / Townhome (8-14 u/acre)": dict(units_per_acre=11, cost_multiplier=0.90, default_unit_sf=950),
    "Podium / Wrap (25-45 u/acre)": dict(units_per_acre=35, cost_multiplier=1.00, default_unit_sf=850),
    "High-Rise (60-120+ u/acre)": dict(units_per_acre=90, cost_multiplier=1.35, default_unit_sf=750),
}

# HUD-style AMI tiers -- the % is a modeling choice, not a separate data pull.
AMI_TIERS_PCT = [30, 50, 60, 80]
DEFAULT_AMI_TIER_PCT = 60


def _rng_for(cbsa: str) -> np.random.Generator:
    return np.random.default_rng(seed=int(cbsa))


def generate_synthetic_dataset() -> pd.DataFrame:
    """Build the full 50-metro synthetic fallback dataset.

    Every numeric column produced here is a deterministic, tier-calibrated
    draw -- not observed data. `build_dataset.py` overwrites any column it
    can obtain from a live source with real values and flips that column's
    entry in `_source_flags` from "synthetic" to "live".
    """
    rows = []
    for m in TOP_50_METROS:
        rng = _rng_for(m.cbsa)
        params = TIER_PARAMS[m.tier]
        home_price, household_income = ANCHORS[m.cbsa]

        row = {"cbsa": m.cbsa, "metro": m.short_name, "tier": m.tier}
        for field, (mean, std) in params.items():
            row[field] = float(rng.normal(mean, std))

        row["median_home_price_usd"] = float(home_price)
        row["median_household_income_usd"] = float(household_income)
        # HUD Area Median Income tracks close to, but not identical to, the
        # ACS median household income figure for the same metro.
        row["ami_usd"] = float(household_income * rng.uniform(0.97, 1.08))

        # clip a few fields to sane physical ranges after noise
        row["rental_vacancy_pct"] = max(0.5, row["rental_vacancy_pct"])
        row["homeowner_vacancy_pct"] = max(0.1, row["homeowner_vacancy_pct"])
        row["vacancy_collection_loss_pct"] = min(max(row["vacancy_collection_loss_pct"], 2.0), 15.0)
        row["cap_rate_pct"] = min(max(row["cap_rate_pct"], 3.0), 9.0)
        row["permit_velocity_index"] = min(max(row["permit_velocity_index"], 0.0), 100.0)
        row["construction_cost_per_sf_usd"] = max(80.0, row["construction_cost_per_sf_usd"])
        row["land_cost_per_acre_usd"] = max(50_000.0, row["land_cost_per_acre_usd"])

        rows.append(row)

    df = pd.DataFrame(rows)
    df["data_vintage"] = "synthetic-2024-estimate"
    return df


SYNTHETIC_ONLY_FIELDS = {
    # per the charter, these are flagged synthetic regardless of network
    # access because no free, metro-level public source exists for them
    "land_cost_per_acre_usd",
    "construction_cost_per_sf_usd",
    "vacancy_collection_loss_pct",
    "operating_expense_per_unit_usd",
    "cap_rate_pct",
    "permit_velocity_index",
}

LIVE_ELIGIBLE_FIELDS = {
    # these can in principle be pulled live from Census/ACS/FHFA/Zillow/FRED
    # (see pipeline/fetch_*.py); synthetic values here are only a fallback
    "pop_cagr_pct",
    "permits_per_1000_cagr_pct",
    "rental_vacancy_pct",
    "homeowner_vacancy_pct",
    "median_home_price_usd",
    "median_household_income_usd",
    "rent_growth_3yr_pct",
    "income_growth_3yr_pct",
    "ami_usd",
}
