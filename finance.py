"""
Homebuyer add-on: standard mortgage amortization, several temporary
buy-down structures, and a permanent discount-points buy-down, per the
project charter's buy-down calculator. Illustrative only -- not a loan
product, rate quote, or financial advice.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def monthly_payment(principal: float, annual_rate_pct: float, term_years: int = 30) -> float:
    """Standard fixed-rate amortization: M = P[r(1+r)^n] / [(1+r)^n - 1]."""
    r = (annual_rate_pct / 100.0) / 12
    n = term_years * 12
    if r == 0:
        return principal / n
    return principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


# ---------------------------------------------------------------- temporary --
@dataclass
class ScheduleYear:
    label: str
    rate_pct: float
    payment: float
    monthly_savings_vs_note: float


@dataclass
class TemporaryBuydownResult:
    note_rate_pct: float
    note_payment: float
    schedule: list[ScheduleYear] = field(default_factory=list)
    total_subsidy: float = 0.0  # sum of 12 * monthly savings across all discounted years


# Standard temporary buy-down structures, named by their rate reduction in
# each successive year (e.g. "3-2-1" = 3 points off in year 1, 2 off in
# year 2, 1 off in year 3, note rate from year 4 on). "1-0" is a one-year
# buydown (no second discounted year); "1-1" holds a flat 1-point discount
# for two years instead of stepping down.
TEMPORARY_BUYDOWN_STRUCTURES: dict[str, list[float]] = {
    "3-2-1 Buydown": [3.0, 2.0, 1.0],
    "2-1 Buydown": [2.0, 1.0],
    "1-1 Buydown": [1.0, 1.0],
    "1-0 Buydown": [1.0],
}


def temporary_buydown(
    principal: float, note_rate_pct: float, term_years: int, step_downs: list[float]
) -> TemporaryBuydownResult:
    """A temporary buy-down defined by a list of rate reductions, one per discounted year.

    `step_downs=[3, 2, 1]` is a 3-2-1 buydown: year 1 at note-3pts, year 2
    at note-2pts, year 3 at note-1pt, note rate from year 4 on (or from
    year `len(step_downs)+1` in general). Rates floor at 0%.
    """
    note_payment = monthly_payment(principal, note_rate_pct, term_years)
    schedule: list[ScheduleYear] = []
    total_subsidy = 0.0
    for i, reduction in enumerate(step_downs, start=1):
        rate = max(note_rate_pct - reduction, 0.0)
        payment = monthly_payment(principal, rate, term_years)
        savings = note_payment - payment
        schedule.append(ScheduleYear(f"Year {i}", rate, payment, savings))
        total_subsidy += savings * 12
    return TemporaryBuydownResult(note_rate_pct, note_payment, schedule, total_subsidy)


@dataclass
class BuydownResult:
    """Kept for backward compatibility with the original 2-1-only API."""

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
    r = temporary_buydown(principal, note_rate_pct, term_years, TEMPORARY_BUYDOWN_STRUCTURES["2-1 Buydown"])
    y1, y2 = r.schedule[0], r.schedule[1]
    return BuydownResult(
        note_rate_pct=r.note_rate_pct,
        note_payment=r.note_payment,
        year1_rate_pct=y1.rate_pct,
        year1_payment=y1.payment,
        year2_rate_pct=y2.rate_pct,
        year2_payment=y2.payment,
        year1_monthly_savings=y1.monthly_savings_vs_note,
        year2_monthly_savings=y2.monthly_savings_vs_note,
        total_buydown_subsidy=r.total_subsidy,
    )


# ---------------------------------------------------------------- permanent --
@dataclass
class PermanentBuydownResult:
    note_rate_pct: float
    note_payment: float
    points: float
    rate_reduction_per_point_pct: float
    effective_rate_pct: float
    effective_payment: float
    points_cost: float
    monthly_savings: float
    breakeven_months: float | None  # None when there's no monthly savings to break even on


def permanent_buydown(
    principal: float,
    note_rate_pct: float,
    term_years: int,
    points: float,
    rate_reduction_per_point_pct: float = 0.25,
) -> PermanentBuydownResult:
    """Permanent rate buy-down: pay discount points upfront to permanently lower the rate.

    Standard rule of thumb (and this function's default): 1 point costs 1%
    of the loan amount and buys roughly a 0.25-point rate reduction for the
    full loan term -- actual pricing varies by lender and market
    conditions, so this is illustrative, not a quote.
    """
    note_payment = monthly_payment(principal, note_rate_pct, term_years)
    effective_rate = max(note_rate_pct - points * rate_reduction_per_point_pct, 0.0)
    effective_payment = monthly_payment(principal, effective_rate, term_years)
    points_cost = (points / 100.0) * principal
    monthly_savings = note_payment - effective_payment
    breakeven_months = (points_cost / monthly_savings) if monthly_savings > 0 else None

    return PermanentBuydownResult(
        note_rate_pct=note_rate_pct,
        note_payment=note_payment,
        points=points,
        rate_reduction_per_point_pct=rate_reduction_per_point_pct,
        effective_rate_pct=effective_rate,
        effective_payment=effective_payment,
        points_cost=points_cost,
        monthly_savings=monthly_savings,
        breakeven_months=breakeven_months,
    )
