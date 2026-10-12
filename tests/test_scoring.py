import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pytest

from scoring import score_metros, zscore, normalize_0_100
from finance import (
    monthly_payment,
    two_one_buydown,
    temporary_buydown,
    permanent_buydown,
    TEMPORARY_BUYDOWN_STRUCTURES,
)
from pipeline.subareas import generate_subarea_dataset, SUBAREA_TIERS, ring_bounds_miles
from pipeline.geo_shapes import counties_by_ring, state_rings
from metros import ALL_METROS
from pipeline.anchors import ANCHORS


@pytest.fixture
def dataset():
    return pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "metro_dataset.csv"))


def test_zscore_mean_zero():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    z = zscore(s)
    assert abs(z.mean()) < 1e-9
    assert abs(z.std(ddof=0) - 1.0) < 1e-9


def test_normalize_bounds():
    s = pd.Series([10.0, 20.0, 30.0])
    n = normalize_0_100(s)
    assert n.min() == 0.0
    assert n.max() == 100.0


def test_score_metros_shape_and_ranges(dataset):
    scored = score_metros(dataset)
    assert len(scored) == len(dataset)
    for col in ("shortage_score", "feasibility_score", "opportunity_score"):
        assert scored[col].between(-1, 101).all(), col
    assert scored["rank"].tolist() == list(range(1, len(scored) + 1))
    # highest opportunity score should be rank 1
    assert scored.iloc[0]["opportunity_score"] == scored["opportunity_score"].max()


def test_alpha_beta_extremes_match_component_scores(dataset):
    shortage_only = score_metros(dataset, alpha=1.0)
    feasibility_only = score_metros(dataset, alpha=0.0)
    assert (shortage_only["opportunity_score"] - shortage_only["shortage_score"]).abs().max() < 1e-9
    assert (feasibility_only["opportunity_score"] - feasibility_only["feasibility_score"]).abs().max() < 1e-9


def test_density_tier_changes_feasibility(dataset):
    garden = score_metros(dataset, density_tier="Garden / Townhome (8-14 u/acre)")
    highrise = score_metros(dataset, density_tier="High-Rise (60-120+ u/acre)")
    assert not garden["feasibility_score"].equals(highrise["feasibility_score"])


def test_monthly_payment_basic():
    # $300k, 6% APR, 30yr -> approx $1798.65
    m = monthly_payment(300_000, 6.0, 30)
    assert 1790 < m < 1810


def test_two_one_buydown_savings_positive():
    result = two_one_buydown(300_000, 6.5, 30)
    assert result.year1_monthly_savings > 0
    assert result.year2_monthly_savings > 0
    assert result.year1_monthly_savings > result.year2_monthly_savings
    assert result.total_buydown_subsidy > 0


def test_two_one_buydown_short_term_does_not_crash():
    result = two_one_buydown(300_000, 6.5, 1)
    assert result.year1_payment > 0


def test_generate_subarea_dataset_shape(dataset):
    row = dataset.iloc[0]
    sub = generate_subarea_dataset(row)
    assert len(sub) == len(SUBAREA_TIERS)
    assert set(sub["subarea"]) == set(SUBAREA_TIERS)
    assert sub["ami_usd"].nunique() == 1
    assert sub.loc[sub["subarea"] == "Urban Core", "land_cost_per_acre_usd"].iloc[0] > \
        sub.loc[sub["subarea"] == "Exurban / Micropolitan Fringe", "land_cost_per_acre_usd"].iloc[0]


def test_subarea_scores_within_metro(dataset):
    row = dataset.iloc[0]
    sub = generate_subarea_dataset(row)
    scored_sub = score_metros(sub)
    assert len(scored_sub) == len(SUBAREA_TIERS)
    for col in ("shortage_score", "feasibility_score", "opportunity_score"):
        assert scored_sub[col].between(-1, 101).all(), col


# ------------------------------------------------------------ metro universe --
def test_all_metros_have_anchors():
    metro_cbsas = {m.cbsa for m in ALL_METROS}
    assert metro_cbsas == set(ANCHORS.keys())
    assert len(ALL_METROS) == 150


# -------------------------------------------------------- temporary buydown --
@pytest.mark.parametrize("name", list(TEMPORARY_BUYDOWN_STRUCTURES.keys()))
def test_temporary_buydown_structures_step_down_correctly(name):
    steps = TEMPORARY_BUYDOWN_STRUCTURES[name]
    result = temporary_buydown(300_000, 6.5, 30, steps)
    assert len(result.schedule) == len(steps)
    for year, reduction in zip(result.schedule, steps):
        assert abs(year.rate_pct - (6.5 - reduction)) < 1e-9
        assert year.monthly_savings_vs_note > 0
    assert result.total_subsidy > 0
    # every later-numbered year's payment should be >= an earlier year's
    # (rate step-down or flat, never stepping back down after an increase)
    payments = [y.payment for y in result.schedule]
    assert payments == sorted(payments)


def test_temporary_buydown_rate_floors_at_zero():
    result = temporary_buydown(300_000, 1.0, 30, [3.0, 2.0, 1.0])
    assert all(y.rate_pct >= 0.0 for y in result.schedule)


def test_temporary_buydown_truncates_to_short_term():
    # a 3-2-1 structure sliced to a 2-year term should only have 2 scheduled years
    result = temporary_buydown(300_000, 6.5, 2, TEMPORARY_BUYDOWN_STRUCTURES["3-2-1 Buydown"][:2])
    assert len(result.schedule) == 2


# -------------------------------------------------------- permanent buydown --
def test_permanent_buydown_lowers_rate_and_payment():
    result = permanent_buydown(300_000, 6.5, 30, points=2.0)
    assert result.effective_rate_pct == pytest.approx(6.0)
    assert result.effective_payment < result.note_payment
    assert result.monthly_savings > 0
    assert result.points_cost == pytest.approx(6_000.0)  # 2 pts * 1% * 300k
    assert result.breakeven_months is not None
    assert result.breakeven_months == pytest.approx(result.points_cost / result.monthly_savings)


def test_permanent_buydown_zero_points_no_savings():
    result = permanent_buydown(300_000, 6.5, 30, points=0.0)
    assert result.monthly_savings == pytest.approx(0.0, abs=0.01)
    assert result.points_cost == 0.0


# --------------------------------------------------------- county ring data --
def test_ring_bounds_are_contiguous_and_increasing():
    bounds = ring_bounds_miles()
    assert len(bounds) == len(SUBAREA_TIERS)
    prev_hi = 0.0
    for tier in SUBAREA_TIERS:
        lo, hi = bounds[tier]
        assert lo == prev_hi
        assert hi > lo
        prev_hi = hi


def test_counties_by_ring_returns_real_sorted_names():
    bounds = ring_bounds_miles()
    # San Jose, CA
    result = counties_by_ring(37.3382, -121.8863, bounds)
    assert set(result.keys()) == set(SUBAREA_TIERS)
    all_counties = [c for tier_list in result.values() for c in tier_list]
    assert "Santa Clara, CA" in all_counties
    for tier_list in result.values():
        assert tier_list == sorted(tier_list)


def test_state_rings_returns_points_for_known_state():
    rings = state_rings("CA")
    assert len(rings) > 0
    assert all(len(r) >= 3 for r in rings)  # a polygon ring needs at least 3 points
