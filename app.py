"""
Affordable Housing Opportunity Explorer

Ranks the top U.S. metro areas by an Opportunity Score derived from a
Shortage Score (need signal) and a Feasibility Score (can-it-be-built
without subsidy signal), per the REAL 43905 project charter.
"""

from __future__ import annotations

import math
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from metros import metros_frame
from pipeline.synthetic import DENSITY_TIERS, AMI_TIERS_PCT, DEFAULT_AMI_TIER_PCT
from scoring import (
    score_metros,
    DEFAULT_SHORTAGE_WEIGHTS,
    DEFAULT_FEASIBILITY_WEIGHTS,
    DEFAULT_UNIT_SIZE_SF,
    DEFAULT_SOFT_COST_PCT,
)
from finance import monthly_payment, two_one_buydown

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
        "Plotted by longitude/latitude with a geographic aspect correction "
        "(not a tile/basemap map) so it renders with no external map-tile "
        "dependency -- reliable in locked-down networks and offline demos."
    )
    fig = px.scatter(
        scored,
        x="lon",
        y="lat",
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
        size_max=32,
        text="state",
    )
    fig.update_traces(textposition="top center", textfont_size=9)
    mean_lat = scored["lat"].mean()
    fig.update_yaxes(
        scaleanchor="x",
        scaleratio=1 / max(0.2, math.cos(math.radians(mean_lat))),
        showgrid=False, zeroline=False, visible=False,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, visible=False)
    fig.update_layout(
        height=620, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="rgba(240,246,255,0.6)",
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

# ------------------------------------------------------------- buy-down calc --
with tab_buydown:
    st.subheader("Homebuyer Buy-Down Calculator (illustrative only)")
    st.caption("Not a loan product or financial advice -- for illustration of payment relief from a 2-1 temporary rate buy-down.")

    bc1, bc2, bc3 = st.columns(3)
    home_price = bc1.number_input("Home price ($)", min_value=50_000, max_value=3_000_000, value=350_000, step=5_000)
    down_pct = bc2.slider("Down payment (%)", 0, 50, 10)
    note_rate = bc3.number_input("Note rate (%)", min_value=0.0, max_value=15.0, value=6.5, step=0.125)
    term_years = st.select_slider("Loan term (years)", options=[15, 20, 30], value=30)

    principal = home_price * (1 - down_pct / 100)
    result = two_one_buydown(principal, note_rate, term_years)

    st.markdown(f"Financed amount: **${principal:,.0f}**")

    payment_table = pd.DataFrame(
        {
            "Period": ["Year 1 (buy-down)", "Year 2 (buy-down)", "Year 3+ (note rate)"],
            "Rate": [f"{result.year1_rate_pct:.2f}%", f"{result.year2_rate_pct:.2f}%", f"{result.note_rate_pct:.2f}%"],
            "Monthly payment": [
                f"${result.year1_payment:,.0f}", f"${result.year2_payment:,.0f}", f"${result.note_payment:,.0f}",
            ],
            "Monthly savings vs. note rate": [
                f"${result.year1_monthly_savings:,.0f}", f"${result.year2_monthly_savings:,.0f}", "$0",
            ],
        }
    )
    st.table(payment_table)
    st.metric("Total buy-down subsidy needed (Years 1-2)", f"${result.total_buydown_subsidy:,.0f}")

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
