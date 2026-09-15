"""
Homebuyer add-on: standard mortgage amortization and a 2-1 temporary
buy-down comparison, per the project charter. Illustrative only -- not a
loan product or financial advice.
"""

from __future__ import annotations

from dataclasses import dataclass


def monthly_payment(principal: float, annual_rate_pct: float, term_years: int = 30) -> float:
    """Standard fixed-rate amortization: M = P[r(1+r)^n] / [(1+r)^n - 1]."""
    r = (annual_rate_pct / 100.0) / 12
    n = term_years * 12
    if r == 0:
        return principal / n
    return principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


@dataclass
class BuydownResult:
    note_rate_pct: float
    note_payment: float
    year1_rate_pct: float
    year1_payment: float
    year2_rate_pct: float
    year2_payment: float
    year1_monthly_savings: float
    year2_monthly_savings: float
    total_buydown_subsidy: float


def two_one_buydown(principal: float, note_rate_pct: float, term_years: int = 30) -> BuydownResult:
    """2-1 temporary buy-down: year 1 at note - 2pts, year 2 at note - 1pt, year 3+ at note rate."""
    note_payment = monthly_payment(principal, note_rate_pct, term_years)
    year1_rate = max(note_rate_pct - 2.0, 0.0)
    year2_rate = max(note_rate_pct - 1.0, 0.0)
    year1_payment = monthly_payment(principal, year1_rate, term_years)
    year2_payment = monthly_payment(principal, year2_rate, term_years)

    y1_savings = note_payment - year1_payment
    y2_savings = note_payment - year2_payment
    total_subsidy = y1_savings * 12 + y2_savings * 12

    return BuydownResult(
        note_rate_pct=note_rate_pct,
        note_payment=note_payment,
        year1_rate_pct=year1_rate,
        year1_payment=year1_payment,
        year2_rate_pct=year2_rate,
        year2_payment=year2_payment,
        year1_monthly_savings=y1_savings,
        year2_monthly_savings=y2_savings,
        total_buydown_subsidy=total_subsidy,
    )
