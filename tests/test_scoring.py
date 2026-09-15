import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pytest

from scoring import score_metros, zscore, normalize_0_100
from finance import monthly_payment, two_one_buydown


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
