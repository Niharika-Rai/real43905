"""
Full underwriting add-on for the Metro Breakdown tab: lender debt sizing and
a levered IRR, laid on top of the existing Feasibility Score screening
metric -- the "turn the Feasibility screen into a complete pro forma"
roadmap item.

Illustrative screening math, not a lender's term sheet or a substitute for
a full multi-year operating budget: it assumes flat-in-real-terms
stabilized operations growing at one constant rate and a single exit sale,
which is the standard simplifying assumption for a screening tool, not a
real lease-up or renovation schedule. A real deal still needs an actual
lender quote and a licensed appraisal.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from finance import monthly_payment


def remaining_balance(
    principal: float, annual_rate_pct: float, term_years: int, years_elapsed: float
) -> float:
    """Outstanding principal on a standard amortizing loan after `years_elapsed` years."""
    r = (annual_rate_pct / 100.0) / 12
    n = term_years * 12
    k = years_elapsed * 12
    if principal <= 0:
        return 0.0
    if r == 0:
        return max(principal * (1 - k / n), 0.0)
    return principal * ((1 + r) ** n - (1 + r) ** k) / ((1 + r) ** n - 1)


@dataclass
class DebtSizingResult:
    noi_usd: float
    dscr_target: float
    max_ltv_pct: float
    loan_rate_pct: float
    loan_term_years: int
    loan_dscr_constrained_usd: float
    loan_ltv_constrained_usd: float
    loan_amount_usd: float
    binding_constraint: str  # "DSCR" or "LTV"
    annual_debt_service_usd: float
    equity_required_usd: float


def size_debt(
    noi_usd: float,
    development_cost_usd: float,
    dscr_target: float = 1.25,
    max_ltv_pct: float = 70.0,
    loan_rate_pct: float = 6.5,
    loan_term_years: int = 30,
) -> DebtSizingResult:
    """Max supportable loan under a DSCR constraint and an LTV-of-cost cap.

    Whichever constraint produces the smaller loan amount binds -- standard
    lender practice is to size to the tighter of the two.
    """
    annual_constant_per_dollar = monthly_payment(1.0, loan_rate_pct, loan_term_years) * 12
    loan_dscr = max(noi_usd, 0.0) / (dscr_target * annual_constant_per_dollar)
    loan_ltv = (max_ltv_pct / 100.0) * development_cost_usd
    loan_amount = min(loan_dscr, loan_ltv)
    binding = "DSCR" if loan_dscr <= loan_ltv else "LTV"
    annual_debt_service = loan_amount * annual_constant_per_dollar
    equity_required = development_cost_usd - loan_amount

    return DebtSizingResult(
        noi_usd=noi_usd,
        dscr_target=dscr_target,
        max_ltv_pct=max_ltv_pct,
        loan_rate_pct=loan_rate_pct,
        loan_term_years=loan_term_years,
        loan_dscr_constrained_usd=loan_dscr,
        loan_ltv_constrained_usd=loan_ltv,
        loan_amount_usd=loan_amount,
        binding_constraint=binding,
        annual_debt_service_usd=annual_debt_service,
        equity_required_usd=equity_required,
    )


@dataclass
class ScheduleYearCF:
    year: int
    noi_usd: float
    debt_service_usd: float
    levered_cf_usd: float
    is_exit_year: bool
    exit_value_usd: float = 0.0
    loan_payoff_usd: float = 0.0
    net_sale_proceeds_usd: float = 0.0


@dataclass
class UnderwritingResult:
    debt: DebtSizingResult
    hold_years: int
    noi_growth_pct: float
    exit_cap_rate_pct: float
    selling_cost_pct: float
    schedule: list[ScheduleYearCF] = field(default_factory=list)
    equity_cash_flows: list[float] = field(default_factory=list)  # [0]=-equity, [1..N]=year CFs
    irr_pct: float | None = None
    equity_multiple: float | None = None


def irr(cash_flows: list[float], low: float = -0.99, high: float = 10.0, tol: float = 1e-7, max_iter: int = 200) -> float | None:
    """Internal rate of return via bisection on the NPV function.

    `cash_flows[0]` is the initial (typically negative) outlay, one entry
    per subsequent period. Bisection (rather than Newton's method) is used
    because it needs no derivative and is robust for the single-sign-change
    cash flow pattern this module always produces (one outflow, then
    positive flows) -- returns None if no root exists in [low, high] (e.g.
    cash flows that never turn positive).
    """
    def npv(rate: float) -> float:
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))

    f_low, f_high = npv(low), npv(high)
    if f_low == 0:
        return low
    if f_high == 0:
        return high
    if f_low * f_high > 0:
        return None
    for _ in range(max_iter):
        mid = (low + high) / 2
        f_mid = npv(mid)
        if abs(f_mid) < tol:
            return mid
        if f_low * f_mid < 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2


def run_underwriting(
    noi_usd: float,
    development_cost_usd: float,
    cap_rate_pct: float,
    hold_years: int = 5,
    noi_growth_pct: float = 2.0,
    exit_cap_rate_pct: float | None = None,
    selling_cost_pct: float = 3.0,
    dscr_target: float = 1.25,
    max_ltv_pct: float = 70.0,
    loan_rate_pct: float = 6.5,
    loan_term_years: int = 30,
) -> UnderwritingResult:
    """Size the debt, project a levered cash-flow schedule, and solve for IRR.

    Exit value is forward-NOI / exit cap rate (the NOI one year past the
    sale date, the standard convention for how year-N's buyer prices the
    asset), net of selling costs and the remaining loan balance at exit.
    """
    exit_cap_rate_pct = cap_rate_pct if exit_cap_rate_pct is None else exit_cap_rate_pct
    debt = size_debt(noi_usd, development_cost_usd, dscr_target, max_ltv_pct, loan_rate_pct, loan_term_years)

    schedule: list[ScheduleYearCF] = []
    cash_flows: list[float] = [-debt.equity_required_usd]
    noi_t = noi_usd
    for year in range(1, hold_years + 1):
        is_exit = year == hold_years
        levered_cf = noi_t - debt.annual_debt_service_usd
        exit_value = payoff = proceeds = 0.0
        total_cf = levered_cf
        if is_exit:
            forward_noi = noi_t * (1 + noi_growth_pct / 100.0)
            exit_value = forward_noi / (exit_cap_rate_pct / 100.0)
            payoff = remaining_balance(debt.loan_amount_usd, loan_rate_pct, loan_term_years, hold_years)
            proceeds = exit_value * (1 - selling_cost_pct / 100.0) - payoff
            total_cf = levered_cf + proceeds
        schedule.append(ScheduleYearCF(year, noi_t, debt.annual_debt_service_usd, levered_cf, is_exit, exit_value, payoff, proceeds))
        cash_flows.append(total_cf)
        noi_t *= 1 + noi_growth_pct / 100.0

    irr_rate = irr(cash_flows)
    irr_pct = irr_rate * 100 if irr_rate is not None else None
    total_distributions = sum(cash_flows[1:])
    equity_multiple = (total_distributions / debt.equity_required_usd) if debt.equity_required_usd > 0 else None

    return UnderwritingResult(
        debt=debt,
        hold_years=hold_years,
        noi_growth_pct=noi_growth_pct,
        exit_cap_rate_pct=exit_cap_rate_pct,
        selling_cost_pct=selling_cost_pct,
        schedule=schedule,
        equity_cash_flows=cash_flows,
        irr_pct=irr_pct,
        equity_multiple=equity_multiple,
    )
