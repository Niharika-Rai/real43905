import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from finance import monthly_payment
from underwriting import irr, remaining_balance, run_underwriting, size_debt


def test_remaining_balance_at_start_equals_principal():
    assert remaining_balance(300_000, 6.5, 30, 0) == pytest.approx(300_000)


def test_remaining_balance_at_full_term_is_zero():
    assert remaining_balance(300_000, 6.5, 30, 30) == pytest.approx(0.0, abs=0.01)


def test_remaining_balance_decreases_over_time():
    bal_5 = remaining_balance(300_000, 6.5, 30, 5)
    bal_15 = remaining_balance(300_000, 6.5, 30, 15)
    assert 0 < bal_15 < bal_5 < 300_000


def test_remaining_balance_past_term_is_zero_not_negative():
    # hold period and amortization term are independent sliders -- a loan
    # that fully amortizes well before a long hold period ends should just
    # be retired (0 owed), not run the formula past its own term and come
    # out negative.
    assert remaining_balance(300_000, 6.5, 1, 20) == pytest.approx(0.0, abs=0.01)
    assert remaining_balance(300_000, 6.5, 5, 20) == pytest.approx(0.0, abs=0.01)
    assert remaining_balance(300_000, 0.0, 1, 20) == pytest.approx(0.0, abs=0.01)


def test_size_debt_picks_the_tighter_constraint():
    # a small NOI relative to a large development cost should be DSCR-bound
    debt = size_debt(noi_usd=5_000, development_cost_usd=300_000, dscr_target=1.25, max_ltv_pct=70.0)
    assert debt.binding_constraint == "DSCR"
    assert debt.loan_amount_usd == pytest.approx(debt.loan_dscr_constrained_usd)
    assert debt.loan_amount_usd < debt.loan_ltv_constrained_usd

    # a large NOI relative to a modest development cost should be LTV-bound
    debt2 = size_debt(noi_usd=50_000, development_cost_usd=300_000, dscr_target=1.25, max_ltv_pct=70.0)
    assert debt2.binding_constraint == "LTV"
    assert debt2.loan_amount_usd == pytest.approx(300_000 * 0.70)


def test_size_debt_equity_required_is_cost_minus_loan():
    debt = size_debt(noi_usd=20_000, development_cost_usd=300_000)
    assert debt.equity_required_usd == pytest.approx(300_000 - debt.loan_amount_usd)


def test_size_debt_handles_negative_noi():
    debt = size_debt(noi_usd=-5_000, development_cost_usd=300_000)
    assert debt.loan_dscr_constrained_usd == 0.0
    assert debt.loan_amount_usd == 0.0
    assert debt.equity_required_usd == pytest.approx(300_000)


def test_irr_matches_a_simple_known_case():
    # -100 today, +110 in one year -> exactly 10% IRR
    result = irr([-100, 110])
    assert result == pytest.approx(0.10, abs=1e-5)


def test_irr_returns_none_when_cash_flows_never_turn_positive():
    assert irr([-100, -10, -10]) is None


def test_run_underwriting_produces_a_full_schedule_and_plausible_irr():
    uw = run_underwriting(
        noi_usd=20_000, development_cost_usd=300_000, cap_rate_pct=5.5,
        hold_years=5, noi_growth_pct=2.0,
    )
    assert len(uw.schedule) == 5
    assert uw.schedule[-1].is_exit_year
    assert not any(y.is_exit_year for y in uw.schedule[:-1])
    assert len(uw.equity_cash_flows) == 6
    assert uw.equity_cash_flows[0] == pytest.approx(-uw.debt.equity_required_usd)
    assert uw.irr_pct is not None
    assert -50 < uw.irr_pct < 100  # sane bound for a screening tool, not a hard business rule
    assert uw.equity_multiple > 1  # a profitable illustrative deal should return more than it put in


def test_run_underwriting_exit_value_uses_forward_noi_and_payoff():
    uw = run_underwriting(
        noi_usd=20_000, development_cost_usd=300_000, cap_rate_pct=5.5,
        hold_years=3, noi_growth_pct=3.0, exit_cap_rate_pct=6.0,
    )
    exit_year = uw.schedule[-1]
    forward_noi = exit_year.noi_usd * 1.03
    assert exit_year.exit_value_usd == pytest.approx(forward_noi / 0.06)
    assert exit_year.loan_payoff_usd == pytest.approx(
        remaining_balance(uw.debt.loan_amount_usd, uw.debt.loan_rate_pct, uw.debt.loan_term_years, 3)
    )


def test_debt_constant_matches_standard_amortization():
    # sanity cross-check against finance.monthly_payment directly
    debt = size_debt(noi_usd=1_000_000, development_cost_usd=1, loan_rate_pct=6.5, loan_term_years=30)
    # with an enormous NOI the LTV constraint binds at development_cost=1, so
    # check the DSCR-implied constant instead via a controlled case:
    annual_constant = monthly_payment(1.0, 6.5, 30) * 12
    debt2 = size_debt(noi_usd=annual_constant * 1.25, development_cost_usd=10**9, dscr_target=1.25, max_ltv_pct=99.0)
    assert debt2.loan_dscr_constrained_usd == pytest.approx(1.0, rel=1e-6)
