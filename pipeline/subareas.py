"""
Sub-metro "zoom in" tiers: an illustrative ring typology (Urban Core, Inner
Suburbs, Outer Suburbs, Exurban / Micropolitan Fringe) applied within a
single metro, so a developer can compare where inside a metro the numbers
work best -- not just which metro, nationally, ranks highest.

This is a deliberate design choice, not a shortcut: the project charter
explicitly defers "sub-metro/parcel-level siting" for the MVP because there
is no free, sub-metro-level public dataset for the feasibility-side inputs
(land cost, construction cost, cap rate, etc.) -- the same reason those
fields are synthetic at the metro level. Rather than fabricate specific
place/county names we can't verify for all 50 metros, every metro is broken
into the same four generic, real-estate-standard submarket rings, with
adjustment factors that encode well-established core-vs-periphery patterns
(land is far more expensive and permitting far more restrictive in an urban
core; land is cheap and permitting light in the exurban fringe; suburbs sit
in between). These are ILLUSTRATIVE estimates for relative comparison
within one metro, not observed sub-metro data -- labeled as such everywhere
they appear in the app.

HUD Area Median Income (AMI) is deliberately held constant across a metro's
rings: HUD publishes one income-limit schedule per metro (with rare
county-level exceptions), so the achievable-rent side of the feasibility
math doesn't change by ring -- only the cost side does, which is itself a
realistic and useful insight (the same affordable rent target is harder to
hit downtown, purely because land and construction cost more there).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SUBAREA_TIERS = [
    "Urban Core",
    "Inner Suburbs",
    "Outer Suburbs",
    "Exurban / Micropolitan Fringe",
]

# Multiplicative factors apply as value *= factor; additive factors apply as
# value += factor (used for things already expressed as a rate/index, where
# a multiplier would behave oddly near zero).
_TIER_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "Urban Core": dict(
        land_cost_mult=2.20, construction_cost_mult=1.12,
        rental_vacancy_mult=0.75, homeowner_vacancy_mult=0.75,
        permit_velocity_add=18.0, cap_rate_add=-0.6,
        home_price_mult=1.30, household_income_mult=1.05,
        pop_cagr_add=-0.3, rent_growth_add=1.0, income_growth_add=0.0,
        vacancy_collection_loss_add=-0.5, opex_mult=1.10,
    ),
    "Inner Suburbs": dict(
        land_cost_mult=1.00, construction_cost_mult=1.00,
        rental_vacancy_mult=1.00, homeowner_vacancy_mult=1.00,
        permit_velocity_add=5.0, cap_rate_add=-0.1,
        home_price_mult=1.05, household_income_mult=1.02,
        pop_cagr_add=0.0, rent_growth_add=0.0, income_growth_add=0.0,
        vacancy_collection_loss_add=0.0, opex_mult=1.02,
    ),
    "Outer Suburbs": dict(
        land_cost_mult=0.55, construction_cost_mult=0.95,
        rental_vacancy_mult=1.10, homeowner_vacancy_mult=1.10,
        permit_velocity_add=-12.0, cap_rate_add=0.5,
        home_price_mult=0.85, household_income_mult=0.98,
        pop_cagr_add=0.6, rent_growth_add=-0.5, income_growth_add=0.0,
        vacancy_collection_loss_add=0.5, opex_mult=0.95,
    ),
    "Exurban / Micropolitan Fringe": dict(
        land_cost_mult=0.28, construction_cost_mult=0.90,
        rental_vacancy_mult=1.30, homeowner_vacancy_mult=1.25,
        permit_velocity_add=-22.0, cap_rate_add=1.1,
        home_price_mult=0.65, household_income_mult=0.90,
        pop_cagr_add=0.3, rent_growth_add=-1.5, income_growth_add=-0.5,
        vacancy_collection_loss_add=1.5, opex_mult=0.90,
    ),
}

# small per-metro/tier noise so rings don't look mechanically identical
# across metros, layered on top of the tier adjustment above
_NOISE_STD = dict(
    land_cost_mult=0.06, construction_cost_mult=0.03,
    rental_vacancy_mult=0.05, homeowner_vacancy_mult=0.05,
    permit_velocity_add=4.0, cap_rate_add=0.15,
    home_price_mult=0.03, household_income_mult=0.02,
    pop_cagr_add=0.15, rent_growth_add=0.4, income_growth_add=0.3,
    vacancy_collection_loss_add=0.4, opex_mult=0.03,
)


def _rng_for(cbsa: str, tier_index: int) -> np.random.Generator:
    return np.random.default_rng(seed=int(cbsa) * 10 + tier_index)


def generate_subarea_dataset(metro_row: pd.Series) -> pd.DataFrame:
    """Build the 4 illustrative sub-area rows for one metro.

    `metro_row` must carry the same raw fields as the main metro dataset
    (see pipeline/synthetic.py) -- pass a row from the already-scored or
    pre-scored metro dataframe.
    """
    rows = []
    for i, tier in enumerate(SUBAREA_TIERS):
        rng = _rng_for(str(metro_row["cbsa"]), i)
        adj = {
            k: v + rng.normal(0, _NOISE_STD[k]) for k, v in _TIER_ADJUSTMENTS[tier].items()
        }

        row = {
            "cbsa": f"{metro_row['cbsa']}-{i}",
            "metro": metro_row["metro"],
            "subarea": tier,
            "tier": metro_row.get("tier", ""),
            "lat": metro_row.get("lat"),
            "lon": metro_row.get("lon"),
        }

        row["land_cost_per_acre_usd"] = max(20_000.0, metro_row["land_cost_per_acre_usd"] * adj["land_cost_mult"])
        row["construction_cost_per_sf_usd"] = max(60.0, metro_row["construction_cost_per_sf_usd"] * adj["construction_cost_mult"])
        row["rental_vacancy_pct"] = max(0.3, metro_row["rental_vacancy_pct"] * adj["rental_vacancy_mult"])
        row["homeowner_vacancy_pct"] = max(0.1, metro_row["homeowner_vacancy_pct"] * adj["homeowner_vacancy_mult"])
        row["permit_velocity_index"] = min(max(metro_row["permit_velocity_index"] + adj["permit_velocity_add"], 0.0), 100.0)
        row["cap_rate_pct"] = min(max(metro_row["cap_rate_pct"] + adj["cap_rate_add"], 3.0), 9.5)
        row["median_home_price_usd"] = metro_row["median_home_price_usd"] * adj["home_price_mult"]
        row["median_household_income_usd"] = metro_row["median_household_income_usd"] * adj["household_income_mult"]
        row["pop_cagr_pct"] = metro_row["pop_cagr_pct"] + adj["pop_cagr_add"]
        row["rent_growth_3yr_pct"] = metro_row["rent_growth_3yr_pct"] + adj["rent_growth_add"]
        row["income_growth_3yr_pct"] = metro_row["income_growth_3yr_pct"] + adj["income_growth_add"]
        row["vacancy_collection_loss_pct"] = min(max(metro_row["vacancy_collection_loss_pct"] + adj["vacancy_collection_loss_add"], 2.0), 18.0)
        row["operating_expense_per_unit_usd"] = metro_row["operating_expense_per_unit_usd"] * adj["opex_mult"]

        # unchanged across rings: permits/1000 CAGR (metro-wide BPS series
        # isn't sub-divided) and AMI (HUD publishes one figure per metro)
        row["permits_per_1000_cagr_pct"] = metro_row["permits_per_1000_cagr_pct"]
        row["ami_usd"] = metro_row["ami_usd"]

        rows.append(row)

    return pd.DataFrame(rows)
