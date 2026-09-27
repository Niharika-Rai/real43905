"""
Affordable Housing Opportunity Explorer

Ranks the top U.S. metro areas by an Opportunity Score derived from a
Shortage Score (need signal) and a Feasibility Score (can-it-be-built
without subsidy signal), per the REAL 43905 project charter.
"""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from metros import metros_frame
from pipeline.synthetic import DENSITY_TIERS, AMI_TIERS_PCT, DEFAULT_AMI_TIER_PCT
from pipeline.subareas import generate_subarea_dataset
from scoring import (
    score_metros,
    DEFAULT_SHORTAGE_WEIGHTS,
    DEFAULT_FEASIBILITY_WEIGHTS,
    DEFAULT_UNIT_SIZE_SF,
    DEFAULT_SOFT_COST_PCT,
)
from finance import two_one_buydown

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "metro_dataset.csv")

st.set_page_config(
    page_title="Affordable Housing Opportunity Explorer",
    page_icon="\U0001F3D8️",
    layout="wide",
)


@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    ref = metros_frame()[["cbsa", "lat", "lon", "state", "population"]]
    df["cbsa"] = df["cbsa"].astype(str).str.zfill(5)
    ref["cbsa"] = ref["cbsa"].astype(str).str.zfill(5)
    return df.merge(ref, on="cbsa", how="left")


def normalized_weights(raw: dict[str, float]) -> dict[str, float]:
    total = sum(raw.values())
    if total <= 0:
        n = len(raw)
        return {k: 1.0 / n for k in raw}
    return {k: v / total for k, v in raw.items()}


# ---------------------------------------------------------------- sidebar --
st.sidebar.title("Model Controls")

n_metros = st.sidebar.radio(
    "Metro universe", options=[20, 50], index=1, horizontal=True,
    help="MVP scope is the top 20 metros; the full product covers the top 50.",
)

st.sidebar.markdown("### Opportunity Score weighting")
alpha = st.sidebar.slider(
    "α (Shortage weight)  —  β = 1-α is Feasibility weight",
    min_value=0.0, max_value=1.0, value=0.5, step=0.05,
)
st.sidebar.caption(f"Opportunity = {alpha:.2f} × Shortage + {1 - alpha:.2f} × Feasibility")

with st.sidebar.expander("Shortage component weights", expanded=False):
    w_permit_gap = st.slider("Permit Gap", 0.0, 1.0, DEFAULT_SHORTAGE_WEIGHTS["permit_gap"])
    w_vacancy = st.slider("Vacancy Tightness", 0.0, 1.0, DEFAULT_SHORTAGE_WEIGHTS["vacancy_tightness"])
    w_price_income = st.slider("Price-to-Income Ratio", 0.0, 1.0, DEFAULT_SHORTAGE_WEIGHTS["price_to_income"])
    w_rent_income = st.slider("Rent-Income Divergence", 0.0, 1.0, DEFAULT_SHORTAGE_WEIGHTS["rent_income_divergence"])
    shortage_weights = normalized_weights(
        {
            "permit_gap": w_permit_gap,
            "vacancy_tightness": w_vacancy,
            "price_to_income": w_price_income,
            "rent_income_divergence": w_rent_income,
        }
    )

with st.sidebar.expander("Feasibility component weights", expanded=False):
    v1 = st.slider("Feasibility Gap (v1)", 0.0, 1.0, DEFAULT_FEASIBILITY_WEIGHTS["feasibility_gap"])
    v2 = st.slider("Permit Velocity penalty (v2)", 0.0, 1.0, DEFAULT_FEASIBILITY_WEIGHTS["permit_velocity"])
    feasibility_weights = normalized_weights({"feasibility_gap": v1, "permit_velocity": v2})

st.sidebar.markdown("### Feasibility assumptions")
ami_tier_pct = st.sidebar.select_slider(
    "AMI tier (affordability target)", options=AMI_TIERS_PCT, value=DEFAULT_AMI_TIER_PCT,
    format_func=lambda p: f"{p}% AMI",
)
density_tier = st.sidebar.selectbox("Zoning / density tier", options=list(DENSITY_TIERS.keys()), index=1)
unit_size_sf = st.sidebar.slider(
    "Unit size (SF)", min_value=500, max_value=1400,
    value=int(DENSITY_TIERS[density_tier]["default_unit_sf"]), step=25,
)
soft_cost_pct = st.sidebar.slider("Soft costs (% of land + hard cost)", 0.0, 40.0, DEFAULT_SOFT_COST_PCT, step=1.0)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Scheduled batch refresh: run `python -m pipeline.build_dataset` "
    "(with `ENABLE_LIVE_FETCH=1`) on a schedule -- e.g. a weekly Render Cron "
    "Job -- to regenerate `data/metro_dataset.csv` from live sources. "
    "See README for details."
)

# ------------------------------------------------------------------ data --
raw = load_data()
raw = raw.sort_values("population", ascending=False).head(n_metros).reset_index(drop=True)

scored = score_metros(
    raw,
    shortage_weights=shortage_weights,
    feasibility_weights=feasibility_weights,
    ami_tier_pct=ami_tier_pct,
    density_tier=density_tier,
    unit_size_sf=unit_size_sf,
    soft_cost_pct=soft_cost_pct,
    alpha=alpha,
)

data_vintage = raw["data_vintage"].iloc[0] if "data_vintage" in raw.columns else "unknown"

# ------------------------------------------------------------------ header --
st.title("\U0001F3D8️ Affordable Housing Opportunity Explorer")
st.markdown(
    "Ranks U.S. metro areas by an **Opportunity Score** that combines a "
    "**Shortage Score** (how undersupplied a metro is) and a **Feasibility "
    "Score** (whether affordable development pencils out without subsidy) "
    "-- so developers, CDFIs, and housing authorities can screen sites "
    "before commissioning a full pro forma."
)
st.caption(f"Data vintage: `{data_vintage}` · Metro universe: top {n_metros} U.S. metros by population")

if "synthetic" in str(data_vintage):
    st.info(
        "This deployment is running on the bundled **synthetic snapshot** dataset "
        "(no live network pull has been run yet). Shortage-side fields "
        "(population growth, vacancy, home prices, income, rents) are wired "
        "to pull live from Census/ACS/Zillow/FHFA -- see the **Data Sources** "
        "tab and README for how to trigger a live refresh. Feasibility-side "
        "fields (land cost, construction $/SF, cap rate, opex, vacancy/"
        "collection loss, permit velocity) are **always synthetic estimates**, "
        "per the project charter, since no free public source covers them "
        "at metro granularity.",
        icon="ℹ️",
    )

tab_rank, tab_map, tab_breakdown, tab_buydown, tab_sources = st.tabs(
    ["\U0001F4CA Ranked Table", "\U0001F5FA️ Map", "\U0001F50D Metro Breakdown", "\U0001F3E1 Buy-Down Calculator", "\U0001F4C1 Data Sources"]
)

# ------------------------------------------------------------- ranked table --
with tab_rank:
    st.subheader("Ranked by Opportunity Score")
    display_cols = {
        "rank": "Rank",
        "metro": "Metro",
        "state": "State",
        "opportunity_score": "Opportunity",
        "shortage_score": "Shortage",
        "feasibility_score": "Feasibility",
        "price_to_income": "Price/Income",
        "feasibility_gap_usd": "Feasibility Gap ($/unit)",
    }
    table = scored[list(display_cols.keys())].rename(columns=display_cols)
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=560,
        column_config={
            "Opportunity": st.column_config.ProgressColumn(
                "Opportunity", min_value=0, max_value=100, format="%.1f"
            ),
            "Shortage": st.column_config.NumberColumn("Shortage", format="%.1f"),
            "Feasibility": st.column_config.NumberColumn("Feasibility", format="%.1f"),
            "Price/Income": st.column_config.NumberColumn("Price/Income", format="%.2f×"),
            "Feasibility Gap ($/unit)": st.column_config.NumberColumn(
                "Feasibility Gap ($/unit)", format="$%,.0f"
            ),
        },
    )
    st.download_button(
        "Download ranked table (CSV)",
        data=scored.to_csv(index=False).encode(),
        file_name="opportunity_ranked_metros.csv",
        mime="text/csv",
    )

# ---------------------------------------------------------------------- map --
with tab_map:
    st.subheader("Opportunity Score by Metro")
    st.caption(
        "Bubble size = population, color = Opportunity Score. Hover a metro "
        "for its score breakdown."
    )
    fig = px.scatter_geo(
        scored,
        lat="lat",
        lon="lon",
        color="opportunity_score",
        size="population",
        hover_name="metro",
        hover_data={
            "opportunity_score": ":.1f",
            "shortage_score": ":.1f",
            "feasibility_score": ":.1f",
            "lat": False,
            "lon": False,
            "population": ":,",
        },
        color_continuous_scale="RdYlGn",
        scope="usa",
        size_max=32,
    )
    fig.update_traces(marker=dict(line=dict(width=0.5, color="rgba(40,40,40,0.4)")))
    fig.update_geos(
        showland=True, landcolor="rgb(235, 238, 231)",
        showlakes=True, lakecolor="rgb(255, 255, 255)",
        showsubunits=True, subunitcolor="rgb(190, 190, 190)", subunitwidth=1,
        showcountries=True, countrycolor="rgb(150, 150, 150)",
        showcoastlines=True, coastlinecolor="rgb(150, 150, 150)",
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(
        height=640, margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(bgcolor="rgba(255,255,255,0.8)"),
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------- metro breakdown --
with tab_breakdown:
    st.subheader("Per-Metro Score Breakdown")
    metro_choice = st.selectbox("Choose a metro", options=scored["metro"].tolist())
    row = scored[scored["metro"] == metro_choice].iloc[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Opportunity Score", f"{row['opportunity_score']:.1f}", f"Rank #{int(row['rank'])}")
    c2.metric("Shortage Score", f"{row['shortage_score']:.1f}")
    c3.metric("Feasibility Score", f"{row['feasibility_score']:.1f}")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Shortage components (z-scores)**")
        shortage_components = pd.DataFrame(
            {
                "component": ["Permit Gap", "Vacancy Tightness", "Price-to-Income", "Rent-Income Divergence"],
                "z_score": [
                    row["z_permit_gap"], row["z_vacancy_tightness"],
                    row["z_price_to_income"], row["z_rent_income_divergence"],
                ],
            }
        )
        fig_s = go.Figure(go.Bar(x=shortage_components["z_score"], y=shortage_components["component"], orientation="h"))
        fig_s.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="z-score")
        st.plotly_chart(fig_s, use_container_width=True)

    with col_b:
        st.markdown("**Feasibility waterfall ($/unit)**")
        fig_f = go.Figure(
            go.Waterfall(
                orientation="v",
                measure=["relative", "relative", "relative", "total", "relative", "total"],
                x=["Land Cost", "Hard Cost", "Soft Cost", "Dev Cost", "Supportable Value", "Feasibility Gap"],
                y=[
                    row["land_cost_per_unit_usd"],
                    row["hard_cost_per_unit_usd"],
                    row["soft_costs_usd"],
                    0,
                    row["supportable_value_usd"] - row["development_cost_per_unit_usd"],
                    0,
                ],
            )
        )
        fig_f.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="$/unit")
        st.plotly_chart(fig_f, use_container_width=True)

    st.markdown("**Underlying values**")
    detail_cols = [
        "median_home_price_usd", "median_household_income_usd", "ami_usd",
        "rental_vacancy_pct", "homeowner_vacancy_pct", "pop_cagr_pct", "permits_per_1000_cagr_pct",
        "rent_growth_3yr_pct", "income_growth_3yr_pct",
        "achievable_rent_monthly_usd", "development_cost_per_unit_usd",
        "supportable_value_usd", "feasibility_gap_usd", "cap_rate_pct", "permit_velocity_index",
    ]
    detail = row[detail_cols].to_frame(name="value")
    st.dataframe(detail, use_container_width=True)

    st.divider()
    st.subheader(f"Zoom In: Sub-Metro Rings within {metro_choice}")
    st.caption(
        "The metro-wide score above is a useful first screen, but affordable "
        "developers site at the sub-metro level. Every metro is broken into "
        "four illustrative submarket rings -- Urban Core, Inner Suburbs, "
        "Outer Suburbs, and Exurban / Micropolitan Fringe -- using "
        "real-estate-standard core-vs-periphery adjustments (land cost, "
        "construction cost, vacancy, and permitting friction all vary "
        "predictably from downtown outward). These are **illustrative "
        "estimates for comparing rings within this one metro**, not "
        "specific real places and not comparable across metros -- there is "
        "no free, sub-metro-level public dataset for the feasibility "
        "inputs, same as at the metro level. See the Data Sources tab."
    )

    subarea_raw = generate_subarea_dataset(row)
    subarea_scored = score_metros(
        subarea_raw,
        shortage_weights=shortage_weights,
        feasibility_weights=feasibility_weights,
        ami_tier_pct=ami_tier_pct,
        density_tier=density_tier,
        unit_size_sf=unit_size_sf,
        soft_cost_pct=soft_cost_pct,
        alpha=alpha,
    ).sort_values("opportunity_score", ascending=False)

    ring_col, chart_col = st.columns([3, 2])
    with ring_col:
        ring_display_cols = {
            "subarea": "Sub-Metro Ring",
            "opportunity_score": "Opportunity (local)",
            "shortage_score": "Shortage (local)",
            "feasibility_score": "Feasibility (local)",
            "price_to_income": "Price/Income",
            "land_cost_per_unit_usd": "Land Cost/Unit",
            "permit_velocity_index": "Permit Friction",
        }
        ring_table = subarea_scored[list(ring_display_cols.keys())].rename(columns=ring_display_cols)
        st.dataframe(
            ring_table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Opportunity (local)": st.column_config.ProgressColumn(
                    "Opportunity (local)", min_value=0, max_value=100, format="%.0f"
                ),
                "Shortage (local)": st.column_config.NumberColumn(format="%.0f"),
                "Feasibility (local)": st.column_config.NumberColumn(format="%.0f"),
                "Price/Income": st.column_config.NumberColumn(format="%.2f×"),
                "Land Cost/Unit": st.column_config.NumberColumn(format="$%,.0f"),
                "Permit Friction": st.column_config.NumberColumn(format="%.0f"),
            },
        )
        st.caption(
            "\"Local\" scores are z-scored across just these 4 rings, so they "
            "show which ring is relatively best *within this metro* -- they "
            "are not on the same 0-100 scale as the national metro rankings."
        )

    with chart_col:
        fig_ring = go.Figure(
            go.Bar(
                x=subarea_scored["opportunity_score"],
                y=subarea_scored["subarea"],
                orientation="h",
                marker=dict(
                    color=subarea_scored["opportunity_score"],
                    colorscale="RdYlGn", cmin=0, cmax=100,
                ),
            )
        )
        fig_ring.update_layout(
            height=280, margin=dict(l=0, r=0, t=30, b=0),
            xaxis_title="Local Opportunity Score", yaxis=dict(autorange="reversed"),
            title="Best ring to site within this metro",
        )
        st.plotly_chart(fig_ring, use_container_width=True)

# ------------------------------------------------------------- buy-down calc --
with tab_buydown:
    st.subheader("2-1 Temporary Buy-Down Calculator")
    st.caption("Illustrative only -- not a loan offer or financial advice.")

    buydown_metro = st.selectbox(
        "Example scenario for a site in", options=scored["metro"].tolist(), key="buydown_metro",
    )
    metro_ctx = scored[scored["metro"] == buydown_metro].iloc[0]

    input_col, summary_col = st.columns(2)

    with input_col:
        with st.container(border=True):
            st.markdown("**LOAN INPUTS**")
            home_price = st.number_input(
                "Home price ($)", min_value=50_000, max_value=3_000_000,
                value=int(round(metro_ctx["median_home_price_usd"], -3)), step=5_000,
                key=f"home_price_{buydown_metro}",
                help="Defaults to this metro's median home price -- edit for a specific property.",
            )
            down_pct = st.slider("Down payment (%)", 0, 50, 10)
            down_usd = home_price * down_pct / 100
            st.caption(f"{down_pct}% · \\${down_usd:,.0f}")
            term_years = st.slider("Loan term (years)", min_value=1, max_value=30, value=30, step=1)
            note_rate = st.number_input("Note rate (%)", min_value=0.0, max_value=15.0, value=6.5, step=0.125)
            financing_type = st.radio(
                "Financing type", ["Standard Fixed", "2-1 Buydown"], index=1, horizontal=True,
            )

    principal = home_price - down_usd
    result = two_one_buydown(principal, note_rate, term_years)
    standard_payment = result.note_payment

    with summary_col:
        with st.container(border=True):
            st.markdown("**PAYMENT SUMMARY**")
            periods = [("Year 1", result.year1_rate_pct, result.year1_payment)]
            if term_years >= 2:
                periods.append(("Year 2", result.year2_rate_pct, result.year2_payment))
            if term_years >= 3:
                label = "Year 3" if term_years == 3 else f"Year 3-{term_years}"
                periods.append((label, result.note_rate_pct, result.note_payment))

            if financing_type == "2-1 Buydown":
                summary_table = pd.DataFrame(
                    [{"Year": p, "Rate": f"{r:.2f}%", "Monthly Payment": f"${m:,.0f}"} for p, r, m in periods]
                )
                st.table(summary_table)

                savings_parts = [f"about \\${result.year1_monthly_savings:,.0f}/mo in Year 1"]
                total_savings = result.year1_monthly_savings * 12
                if term_years >= 2:
                    savings_parts.append(f"\\${result.year2_monthly_savings:,.0f}/mo in Year 2")
                    total_savings += result.year2_monthly_savings * 12
                savings_sentence = "Buyer saves " + " and ".join(savings_parts)
                if term_years >= 3:
                    savings_sentence += f" -- roughly \\${total_savings:,.0f} total before the rate resets."
                else:
                    savings_sentence += f" -- roughly \\${total_savings:,.0f} total over the life of this {term_years}-year loan."
                st.success(savings_sentence, icon="✅")
            else:
                st.table(pd.DataFrame([{"Year": f"1-{term_years}", "Rate": f"{note_rate:.2f}%", "Monthly Payment": f"${standard_payment:,.0f}"}]))
                st.info(
                    f"Standard fixed loan -- \\${standard_payment:,.0f}/mo for all {term_years} years, "
                    "no temporary rate reduction. Switch to \"2-1 Buydown\" above to see payment relief.",
                    icon="ℹ️",
                )
            st.caption(f"Financed amount: \\${principal:,.0f} ({100 - down_pct}% of \\${home_price:,.0f})")

    with st.container(border=True):
        st.markdown("**MONTHLY PAYMENT OVER TIME**")
        chart_years = min(5, term_years)
        st.caption(f"{term_years}-year fixed loan · {down_pct}% down · \\${principal:,.0f} principal")

        x_years = list(range(1, chart_years + 1))
        y_buydown = [
            result.year1_payment if y == 1 else result.year2_payment if y == 2 else result.note_payment
            for y in x_years
        ]
        y_standard = [standard_payment] * len(x_years)

        fig_pay = go.Figure()
        fig_pay.add_trace(go.Scatter(
            x=x_years, y=y_buydown, name="2-1 Buydown", mode="lines+markers",
            line=dict(color="#c1873b", width=3), marker=dict(size=8),
        ))
        fig_pay.add_trace(go.Scatter(
            x=x_years, y=y_standard, name="Standard Fixed", mode="lines",
            line=dict(color="#555555", width=2, dash="dash"),
        ))
        if term_years >= 3:
            fig_pay.add_vline(x=2.5, line_width=1, line_dash="dot", line_color="gray")
            fig_pay.add_annotation(x=2.5, y=max(y_buydown + y_standard), text="Rate resets", showarrow=False, yshift=12, font=dict(size=10, color="gray"))
        fig_pay.update_layout(
            height=340, margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(title="Year", tickmode="array", tickvals=x_years),
            yaxis_title="Monthly payment ($)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        )
        st.plotly_chart(fig_pay, use_container_width=True)
        if term_years >= 3:
            st.caption("Rate and payment return to the note rate in Year 3 and hold there for the rest of the loan.")

    stat1, stat2, stat3 = st.columns(3)
    stat1.metric("Median Home Price", f"${metro_ctx['median_home_price_usd']:,.0f}")
    stat2.metric("Price-to-Income Ratio", f"{metro_ctx['price_to_income']:.1f}×")
    stat3.metric(f"Opportunity Score -- {buydown_metro}", f"{metro_ctx['opportunity_score']:.0f} / 100")

# ------------------------------------------------------------------ sources --
with tab_sources:
    st.subheader("Data Sources & Provenance")
    st.markdown(
        """
Per the project charter, most inputs come from **public APIs and bulk data
files**: Census / ACS, Census Building Permits Survey, FRED, FHFA HPI, and
Zillow Research (ZHVI/ZORI). CoStar/RCA are explicitly **not** used. Any
cost, land, or cap-rate data not available from public sources is flagged
as a **synthetic estimate**.
"""
    )
    source_cols = [c for c in scored.columns if c.endswith("__source")]
    if source_cols:
        prov = pd.DataFrame(
            {
                "field": [c.replace("__source", "") for c in source_cols],
                "provenance": [scored[c].iloc[0] for c in source_cols],
            }
        ).sort_values(["provenance", "field"])
        st.dataframe(prov, use_container_width=True, hide_index=True, height=420)

    st.markdown(
        """
**Always-synthetic fields** (no free, metro-level public source exists):
land cost/acre, construction $/SF, cap rate, operating expenses/unit,
vacancy/collection loss %, units/acre (zoning policy input), and permit
velocity / regulatory-friction index.

**Live-eligible fields** (pulled from Census/ACS/Zillow when the pipeline
runs with network access; synthetic fallback otherwise): population growth,
permits per 1,000 units, rental & homeowner vacancy, median home price,
median household income, 3-year rent growth, 3-year income growth.
"""
    )
