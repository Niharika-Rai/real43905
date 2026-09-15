"""
Shortage / Feasibility / Opportunity scoring engine, implementing the exact
formulas from the project charter's "Core Methodology" section.

All component inputs are standardized as z-scores across the current metro
set before being combined, per the charter. "normalize" in the charter's
`100 x normalize(...)` is implemented as min-max scaling of the weighted
z-score sum onto a 0-100 range, so scores are always comparable across the
metro set being ranked (e.g. top-20 vs. top-50 view).
"""

from __future__ import annotations

import pandas as pd

from pipeline.synthetic import DENSITY_TIERS

DEFAULT_SHORTAGE_WEIGHTS = {
    "permit_gap": 0.25,
    "vacancy_tightness": 0.25,
    "price_to_income": 0.25,
    "rent_income_divergence": 0.25,
}

DEFAULT_FEASIBILITY_WEIGHTS = {
    "feasibility_gap": 0.5,
    "permit_velocity": 0.5,
}

DEFAULT_UNIT_SIZE_SF = 900
DEFAULT_SOFT_COST_PCT = 20.0


def zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


def normalize_0_100(series: pd.Series) -> pd.Series:
    lo, hi = series.min(), series.max()
    if hi == lo or pd.isna(hi) or pd.isna(lo):
        return pd.Series(50.0, index=series.index)
    return (series - lo) / (hi - lo) * 100


def compute_shortage(df: pd.DataFrame, weights: dict | None = None) -> pd.DataFrame:
    """Shortage Score (need signal). Adds component + z-score + shortage_score columns."""
    weights = weights or DEFAULT_SHORTAGE_WEIGHTS
    out = df.copy()

    out["permit_gap"] = out["pop_cagr_pct"] - out["permits_per_1000_cagr_pct"]
    out["vacancy_tightness"] = -1.0 * (out["rental_vacancy_pct"] + out["homeowner_vacancy_pct"])
    out["price_to_income"] = out["median_home_price_usd"] / out["median_household_income_usd"]
    out["rent_income_divergence"] = out["rent_growth_3yr_pct"] - out["income_growth_3yr_pct"]

    for comp in DEFAULT_SHORTAGE_WEIGHTS:
        out[f"z_{comp}"] = zscore(out[comp])

    weighted_sum = sum(weights.get(c, 0.0) * out[f"z_{c}"] for c in DEFAULT_SHORTAGE_WEIGHTS)
    out["shortage_score"] = normalize_0_100(weighted_sum)
    return out


def compute_feasibility(
    df: pd.DataFrame,
    ami_tier_pct: float = 60.0,
    density_tier: str = "Podium / Wrap (25-45 u/acre)",
    unit_size_sf: float | None = None,
    soft_cost_pct: float = DEFAULT_SOFT_COST_PCT,
    weights: dict | None = None,
) -> pd.DataFrame:
    """Feasibility Score (can it be built without subsidy signal)."""
    weights = weights or DEFAULT_FEASIBILITY_WEIGHTS
    tier = DENSITY_TIERS[density_tier]
    unit_size_sf = unit_size_sf or tier["default_unit_sf"]

    out = df.copy()

    out["achievable_rent_monthly_usd"] = (0.30 * (ami_tier_pct / 100.0) * out["ami_usd"]) / 12
    out["land_cost_per_unit_usd"] = out["land_cost_per_acre_usd"] / tier["units_per_acre"]
    out["hard_cost_per_unit_usd"] = (
        out["construction_cost_per_sf_usd"] * tier["cost_multiplier"] * unit_size_sf
    )
    out["soft_costs_usd"] = (soft_cost_pct / 100.0) * (
        out["land_cost_per_unit_usd"] + out["hard_cost_per_unit_usd"]
    )
    out["development_cost_per_unit_usd"] = (
        out["land_cost_per_unit_usd"] + out["hard_cost_per_unit_usd"] + out["soft_costs_usd"]
    )

    out["effective_gross_income_usd"] = (
        out["achievable_rent_monthly_usd"] * 12 * (1 - out["vacancy_collection_loss_pct"] / 100.0)
    )
    out["noi_usd"] = out["effective_gross_income_usd"] - out["operating_expense_per_unit_usd"]
    out["supportable_value_usd"] = out["noi_usd"] / (out["cap_rate_pct"] / 100.0)
    out["feasibility_gap_usd"] = out["supportable_value_usd"] - out["development_cost_per_unit_usd"]

    out["z_feasibility_gap"] = zscore(out["feasibility_gap_usd"])
    out["z_permit_velocity"] = zscore(out["permit_velocity_index"])

    weighted = (
        weights.get("feasibility_gap", 0.5) * out["z_feasibility_gap"]
        - weights.get("permit_velocity", 0.5) * out["z_permit_velocity"]
    )
    out["feasibility_score"] = normalize_0_100(weighted)
    return out


def compute_opportunity(df: pd.DataFrame, alpha: float = 0.5, beta: float | None = None) -> pd.DataFrame:
    """Opportunity Score = alpha*Shortage + beta*Feasibility, alpha+beta=1."""
    beta = (1 - alpha) if beta is None else beta
    out = df.copy()
    out["opportunity_score"] = alpha * out["shortage_score"] + beta * out["feasibility_score"]
    return out


def score_metros(
    df: pd.DataFrame,
    shortage_weights: dict | None = None,
    feasibility_weights: dict | None = None,
    ami_tier_pct: float = 60.0,
    density_tier: str = "Podium / Wrap (25-45 u/acre)",
    unit_size_sf: float | None = None,
    soft_cost_pct: float = DEFAULT_SOFT_COST_PCT,
    alpha: float = 0.5,
) -> pd.DataFrame:
    """Run the full Shortage -> Feasibility -> Opportunity pipeline and rank."""
    out = compute_shortage(df, weights=shortage_weights)
    out = compute_feasibility(
        out,
        ami_tier_pct=ami_tier_pct,
        density_tier=density_tier,
        unit_size_sf=unit_size_sf,
        soft_cost_pct=soft_cost_pct,
        weights=feasibility_weights,
    )
    out = compute_opportunity(out, alpha=alpha)
    out = out.sort_values("opportunity_score", ascending=False).reset_index(drop=True)
    out["rank"] = out.index + 1
    return out
