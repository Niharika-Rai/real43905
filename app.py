"""
Affordable Housing Opportunity Explorer

Ranks the top U.S. metro areas by an Opportunity Score derived from a
Shortage Score (need signal) and a Feasibility Score (can-it-be-built
without subsidy signal), per the REAL 43905 project charter.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone

import pandas as pd
import plotly.colors as pcolors
import plotly.graph_objects as go
import streamlit as st

from metros import metros_frame
from pipeline.geo_shapes import state_rings, national_background_rings, counties_by_ring
from pipeline.synthetic import DENSITY_TIERS, AMI_TIERS_PCT, DEFAULT_AMI_TIER_PCT
from pipeline.subareas import (
    generate_subarea_dataset,
    SUBAREA_TIERS,
    RING_OUTER_RADIUS_MILES,
    ring_circle_points,
    ring_bounds_miles,
    MILES_PER_DEGREE_LAT,
)
from scoring import (
    score_metros,
    DEFAULT_SHORTAGE_WEIGHTS,
    DEFAULT_FEASIBILITY_WEIGHTS,
    DEFAULT_UNIT_SIZE_SF,
    DEFAULT_SOFT_COST_PCT,
)
from finance import (
    monthly_payment,
    temporary_buydown,
    permanent_buydown,
    TEMPORARY_BUYDOWN_STRUCTURES,
)
from pipeline.fetch_mortgage_rates import fetch_live_rates, FALLBACK_RATES
from report import build_pdf_report

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "metro_dataset.csv")

# shared geo styling (used by both the national map and the state-level
# sub-metro ring map): plain/transparent page background, land (states)
# tinted a very light blue instead of grey, state lines in a medium grey
# for contrast against the tint. Both maps draw their own state polygons
# from offline shapefile data (pipeline/geo_shapes.py) rather than using
# Plotly's built-in basemap layers, which require a CDN fetch at render
# time -- see the comment on fig_geo.update_geos below for why.
GEO_LAND_COLOR = "rgb(222, 235, 247)"
GEO_BG_COLOR = "rgba(0,0,0,0)"
GEO_SUBUNIT_COLOR = "rgb(140, 140, 140)"

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


@st.cache_data(ttl=86_400, show_spinner=False)
def get_rate_presets(_cache_date: str) -> tuple[dict[str, float], str, str | None]:
    """Today's benchmark note rates by loan type, refreshed once a day.

    Attempts a live pull from mortgagenewsdaily.com; `_cache_date` (today's
    date, passed by the caller) is unused in the body but makes it part of
    Streamlit's cache key, so this re-runs at most once per calendar day
    per the TTL rather than once per server process lifetime -- the "every
    day" refresh the rate presets are meant to have. Falls back to static
    illustrative benchmarks if the live pull fails (always true in this
    dev sandbox's restricted-egress environment; see pipeline/fetch_mortgage_rates.py).
    Returns (rates, "live" | "fallback", fetched_at_iso | None).
    """
    live = fetch_live_rates()
    if live is not None:
        return live, "live", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return FALLBACK_RATES, "fallback", None


def normalized_weights(raw: dict[str, float]) -> dict[str, float]:
    total = sum(raw.values())
    if total <= 0:
        n = len(raw)
        return {k: 1.0 / n for k in raw}
    return {k: v / total for k, v in raw.items()}


# ---------------------------------------------------------------- sidebar --
st.sidebar.title("Model Controls")

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
raw = raw.sort_values("population", ascending=False).reset_index(drop=True)
n_metros = len(raw)

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

if "live-refresh" not in str(data_vintage):
    st.info(
        "This deployment has not run a live network pull yet, so three "
        "levels of data provenance are in play -- see the **Data Sources** "
        "tab for the full field-by-field breakdown. **Published**: median "
        "home price and median household income are real figures grounded "
        "in Census ACS statistics (not modeled), just not fetched live this "
        "run -- the Price-to-Income Ratio is computed from these, so it's a "
        "real number. **Live-eligible**: population growth, permits, "
        "vacancy, and rent/income growth are wired to pull live from "
        "Census/ACS/Zillow/FHFA -- see the README for how to trigger a "
        "refresh -- and fall back to modeled estimates otherwise. "
        "**Always synthetic**: land cost, construction $/SF, cap rate, "
        "opex, vacancy/collection loss, and permit velocity are modeled "
        "estimates regardless of network access, per the project charter, "
        "since no free public source covers them at metro granularity.",
        icon="ℹ️",
    )

if "comparison_metros" not in st.session_state:
    st.session_state.comparison_metros = []

tab_rank, tab_map, tab_breakdown, tab_compare, tab_buydown, tab_sources = st.tabs(
    [
        "\U0001F4CA Ranked Table", "\U0001F5FA️ Map", "\U0001F50D Metro Breakdown",
        f"\U0001F4CB Metro Comparison ({len(st.session_state.comparison_metros)})",
        "\U0001F3E1 Buy-Down Calculator", "\U0001F4C1 Data Sources",
    ]
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
            "Rank": st.column_config.NumberColumn(
                "Rank", help="Position when sorted by Opportunity Score, highest first.",
            ),
            "Metro": st.column_config.TextColumn(
                "Metro", help="U.S. metro area (Core-Based Statistical Area), \"principal city, state\".",
            ),
            "State": st.column_config.TextColumn(
                "State", help="Principal state of the metro area.",
            ),
            "Opportunity": st.column_config.ProgressColumn(
                "Opportunity", min_value=0, max_value=100, format="%.1f",
                help=(
                    "Opportunity = α×Shortage + β×Feasibility (α/β set in the sidebar, "
                    "default 0.5/0.5). 0-100 scale, z-scored and normalized across the "
                    "current metro set -- higher means a more promising combination of "
                    "need and buildability."
                ),
            ),
            "Shortage": st.column_config.NumberColumn(
                "Shortage", format="%.1f",
                help=(
                    "How undersupplied this metro is. Combines Permit Gap, Vacancy "
                    "Tightness, Price-to-Income Ratio, and Rent-Income Divergence "
                    "(each z-scored across metros, weighted per the sidebar's "
                    "Shortage component weights, then normalized 0-100). Higher = "
                    "more acute shortage signal."
                ),
            ),
            "Feasibility": st.column_config.NumberColumn(
                "Feasibility", format="%.1f",
                help=(
                    "Whether affordable development pencils without subsidy. Combines "
                    "the Feasibility Gap (Supportable Value minus Development Cost) and "
                    "Permit Velocity, at the sidebar's AMI tier, density tier, and unit "
                    "size (z-scored, weighted, normalized 0-100). Higher = easier to "
                    "build without subsidy."
                ),
            ),
            "Price/Income": st.column_config.NumberColumn(
                "Price/Income", format="%.2f×",
                help=(
                    "Price-to-Income Ratio = median home price ÷ median household "
                    "income. One of the four Shortage Score components; higher means "
                    "less affordable relative to local income."
                ),
            ),
            "Feasibility Gap ($/unit)": st.column_config.NumberColumn(
                "Feasibility Gap ($/unit)", format="$%,.0f",
                help=(
                    "Supportable Value minus Development Cost, per unit, at the "
                    "sidebar's current AMI tier, density tier, and unit size. Positive "
                    "= buildable without subsidy at those assumptions; negative = would "
                    "need one. See the Metro Breakdown tab for the full cost waterfall."
                ),
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
    fig = go.Figure()
    for ring in national_background_rings():
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        fig.add_trace(go.Scattergeo(
            lon=lons, lat=lats, mode="lines", fill="toself",
            fillcolor=GEO_LAND_COLOR, line=dict(color=GEO_SUBUNIT_COLOR, width=1),
            showlegend=False, hoverinfo="skip",
        ))

    max_pop = scored["population"].max()
    fig.add_trace(go.Scattergeo(
        lat=scored["lat"], lon=scored["lon"], mode="markers",
        marker=dict(
            size=scored["population"], sizemode="area",
            sizeref=2.0 * max_pop / (42 ** 2), sizemin=4,
            color=scored["opportunity_score"], colorscale="RdYlGn", cmin=0, cmax=100,
            colorbar=dict(title="Opportunity<br>Score"),
            line=dict(width=0.5, color="rgba(40,40,40,0.5)"),
        ),
        text=scored["metro"],
        customdata=scored[["opportunity_score", "shortage_score", "feasibility_score", "population"]],
        hovertemplate=(
            "<b>%{text}</b><br>Opportunity: %{customdata[0]:.1f}<br>"
            "Shortage: %{customdata[1]:.1f} · Feasibility: %{customdata[2]:.1f}<br>"
            "Population: %{customdata[3]:,.0f}<extra></extra>"
        ),
        showlegend=False,
    ))

    fig.update_geos(
        projection_type="mercator",
        lataxis_range=[24, 50], lonaxis_range=[-125, -66],
        showland=False, showcountries=False, showcoastlines=False,
        showlakes=False, showsubunits=False, showocean=False, showframe=False,
        bgcolor=GEO_BG_COLOR,
    )
    fig.update_layout(height=640, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------- metro breakdown --
with tab_breakdown:
    st.subheader("Per-Metro Score Breakdown")
    metro_choice = st.selectbox("Choose a metro", options=scored["metro"].tolist())
    row = scored[scored["metro"] == metro_choice].iloc[0]

    with st.expander("✏️ Override land & hard costs for this metro", expanded=False):
        st.caption(
            "Land cost/acre and construction cost/SF are the two inputs the "
            "charter flags as having no free public source (see the Data "
            "Sources tab) -- the baseline below is a modeled estimate. Plug "
            "in your own market-sourced numbers to replace it for this "
            "metro; every score on this page (and the sub-metro rings "
            "further down) recomputes from your override, re-ranked "
            "against the other 149 metros' baseline estimates so "
            "comparisons stay apples-to-apples."
        )
        oc1, oc2 = st.columns(2)
        land_override = oc1.number_input(
            "Land cost per acre ($)", min_value=10_000, max_value=10_000_000,
            value=int(row["land_cost_per_acre_usd"]), step=10_000,
            key=f"land_override_{metro_choice}",
        )
        hard_override = oc2.number_input(
            "Construction cost per SF ($)", min_value=20, max_value=1_000,
            value=int(row["construction_cost_per_sf_usd"]), step=5,
            key=f"hard_override_{metro_choice}",
        )

    overridden = (
        land_override != int(row["land_cost_per_acre_usd"])
        or hard_override != int(row["construction_cost_per_sf_usd"])
    )
    if overridden:
        overridden_raw = raw.copy()
        mask = overridden_raw["metro"] == metro_choice
        overridden_raw.loc[mask, "land_cost_per_acre_usd"] = land_override
        overridden_raw.loc[mask, "construction_cost_per_sf_usd"] = hard_override
        scored_overridden = score_metros(
            overridden_raw,
            shortage_weights=shortage_weights,
            feasibility_weights=feasibility_weights,
            ami_tier_pct=ami_tier_pct,
            density_tier=density_tier,
            unit_size_sf=unit_size_sf,
            soft_cost_pct=soft_cost_pct,
            alpha=alpha,
        )
        row = scored_overridden[scored_overridden["metro"] == metro_choice].iloc[0]
        st.info(
            f"Showing scores recomputed with your overrides -- rank #{int(row['rank'])} "
            "here reflects a re-ranking against the other metros' baseline estimates, "
            "and may differ slightly from the Ranked Table tab (which always uses the "
            "baseline, not your override).",
            icon="✏️",
        )

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    c1.metric("Opportunity Score", f"{row['opportunity_score']:.1f}", f"Rank #{int(row['rank'])}")
    c2.metric("Shortage Score", f"{row['shortage_score']:.1f}")
    c3.metric("Feasibility Score", f"{row['feasibility_score']:.1f}")
    with c4:
        st.markdown("&nbsp;")  # vertical spacer to align the button with the metrics
        already_added = metro_choice in st.session_state.comparison_metros
        if st.button(
            "✅ Added" if already_added else "➕ Add to Comparison",
            disabled=already_added,
            key=f"add_compare_{metro_choice}",
            use_container_width=True,
        ):
            st.session_state.comparison_metros.append(metro_choice)
            st.rerun()

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
        gap = row["feasibility_gap_usd"]
        gap_color = "#2ca02c" if gap >= 0 else "#d62728"

        # Two traces sharing one categorical x-axis. The Waterfall handles
        # the running build-up (Land+Hard+Soft -> Dev Cost) and the bridge
        # to Supportable Value, positioned right after Dev Cost as its
        # cumulative total. Feasibility Gap can't be a third link in that
        # same chain without either double-counting the bridge amount or
        # losing its position next to Dev Cost (Plotly's "total" measure
        # only ever shows the cumulative sum of everything before it) --
        # so it's drawn as an independent bar, starting fresh from zero,
        # colored by whether the metro pencils without subsidy.
        fig_f = go.Figure()
        fig_f.add_trace(go.Waterfall(
            orientation="v",
            measure=["relative", "relative", "relative", "total", "relative"],
            x=["Land Cost", "Hard Cost", "Soft Cost", "Dev Cost", "Supportable Value"],
            y=[
                row["land_cost_per_unit_usd"],
                row["hard_cost_per_unit_usd"],
                row["soft_costs_usd"],
                0,
                gap,
            ],
            text=[
                f"${row['land_cost_per_unit_usd']:,.0f}",
                f"${row['hard_cost_per_unit_usd']:,.0f}",
                f"${row['soft_costs_usd']:,.0f}",
                f"${row['development_cost_per_unit_usd']:,.0f}",
                f"${row['supportable_value_usd']:,.0f}",
            ],
            textposition="outside",
            showlegend=False,
        ))
        fig_f.add_trace(go.Bar(
            x=["Feasibility Gap"], y=[gap],
            marker_color=gap_color,
            text=[f"${gap:,.0f}"], textposition="outside",
            name="Feasibility Gap", showlegend=False,
        ))
        fig_f.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="$/unit")
        st.plotly_chart(fig_f, use_container_width=True)
        st.caption(
            "Supportable Value floats from Dev Cost to show where it lands. "
            "Feasibility Gap is shown separately (green = buildable without "
            "subsidy, red = needs one) since it's the same amount as that "
            "bridge, not an additional cost or value."
        )

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

    with st.expander("How these ring radii were chosen", expanded=False):
        st.markdown(
            """
The four rings use **fixed radii -- 8 / 20 / 40 / 70 miles -- applied the
same way to every metro.** They are not measured per metro from commute
survey data, traffic patterns, or each metro's actual CBSA boundary; they're
a planning-literature-informed heuristic for a typical mid-to-large U.S.
metro, used as a consistent yardstick so every metro is comparable:

- **Urban Core (0-8 mi):** roughly the walkable/dense downtown and
  immediately adjacent neighborhoods of the principal city.
- **Inner Suburbs (8-20 mi):** roughly a 15-30 minute drive commute shed in
  most metros.
- **Outer Suburbs (20-40 mi):** extends to roughly the edge of a typical
  metro's continuously built-up suburban area.
- **Exurban / Micropolitan Fringe (40-70 mi):** commuter-shed overflow and
  satellite towns beyond that, out to where it stops being a plausible
  same-metro commute for most people.

These bands fit sprawling Sunbelt metros better than compact Northeast
metros hemmed in by geography or water -- that's an accepted tradeoff for
having one consistent, comparable measure across all 150 metros rather
than a custom-fit boundary for each one.
"""
        )

    st.markdown("**Counties within each ring**")
    county_bounds = ring_bounds_miles()
    county_lists = counties_by_ring(row["lat"], row["lon"], county_bounds)
    st.caption(
        "Real Census county names (not fabricated place names), bucketed by "
        "great-circle distance from this metro's center point to each "
        "county's nearest edge (its bounding box, not its precise shape). "
        "The metro's own \"home\" county -- the one its center point "
        "actually sits inside -- is always placed in Urban Core, exactly "
        "once, even for a large or irregularly-shaped county. A ring can "
        "still occasionally come up empty for a metro bordered by very "
        "large counties (common in parts of the rural West), where the "
        "next-nearest county's edge skips past that ring's distance band "
        "entirely."
    )
    cc1, cc2, cc3, cc4 = st.columns(4)
    for col, tier in zip((cc1, cc2, cc3, cc4), SUBAREA_TIERS):
        lo, hi = county_bounds[tier]
        counties = county_lists.get(tier, [])
        col.markdown(f"**{tier}**  \n*{lo:.0f}-{hi:.0f} mi*")
        if counties:
            col.markdown("\n".join(f"- {c}" for c in counties))
        else:
            col.caption("No county falls in this band for this metro.")

    st.markdown(f"**Where within {metro_choice}**")
    st.caption(
        "Schematic view only -- rings are stylized concentric bands around "
        "the metro's center point (fixed radii, the same for every metro), "
        "not surveyed neighborhood or county boundaries. Color = local "
        "Opportunity Score for that ring."
    )

    by_tier = subarea_scored.set_index("subarea")
    fig_geo = go.Figure()
    for ring in state_rings(row["state"]):
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        fig_geo.add_trace(go.Scattergeo(
            lon=lons, lat=lats, mode="lines", fill="toself",
            fillcolor=GEO_LAND_COLOR, line=dict(color=GEO_SUBUNIT_COLOR, width=1.5),
            showlegend=False, hoverinfo="skip",
        ))
    for tier in reversed(SUBAREA_TIERS):
        tier_row = by_tier.loc[tier]
        radius = RING_OUTER_RADIUS_MILES[tier]
        lats, lons = ring_circle_points(row["lat"], row["lon"], radius)
        color = pcolors.sample_colorscale("RdYlGn", [tier_row["opportunity_score"] / 100])[0]
        fig_geo.add_trace(go.Scattergeo(
            lat=lats, lon=lons, mode="lines", fill="toself",
            fillcolor=color, line=dict(color="rgba(80,80,80,0.5)", width=1),
            opacity=0.75, name=f"{tier} ({tier_row['opportunity_score']:.0f})",
            hoverinfo="text",
            text=(
                f"{tier}<br>Local Opportunity: {tier_row['opportunity_score']:.0f}<br>"
                f"Shortage: {tier_row['shortage_score']:.0f} · Feasibility: {tier_row['feasibility_score']:.0f}<br>"
                f"~{radius:.0f} mi radius (illustrative)"
            ),
        ))
    fig_geo.add_trace(go.Scattergeo(
        lat=[row["lat"]], lon=[row["lon"]], mode="markers+text",
        marker=dict(size=11, color="black", symbol="star"),
        text=[metro_choice], textposition="top center",
        name="Metro center", hoverinfo="text",
    ))

    lat_margin = 85 / MILES_PER_DEGREE_LAT
    lon_margin = 85 / (MILES_PER_DEGREE_LAT * max(0.15, math.cos(math.radians(row["lat"]))))
    fig_geo.update_geos(
        # NOTE: this deliberately avoids Plotly's built-in basemap layers
        # (showland/showcountries/showcoastlines/etc, and especially
        # scope="usa" or projection_type="albers usa") -- all of them
        # fetch topojson from cdn.plot.ly at render time, which is blocked
        # in restricted networks and rendered this map blank before. The
        # state outline and everything else visible here is drawn from our
        # own offline shapefile data (pipeline/geo_shapes.py) instead, so
        # this map needs no network access at all.
        projection_type="mercator",
        lataxis_range=[row["lat"] - lat_margin, row["lat"] + lat_margin],
        lonaxis_range=[row["lon"] - lon_margin, row["lon"] + lon_margin],
        showland=False, showcountries=False, showcoastlines=False,
        showlakes=False, showsubunits=False, showocean=False, showframe=False,
        bgcolor=GEO_BG_COLOR,
    )
    fig_geo.update_layout(
        height=560, margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(bgcolor="rgba(255,255,255,0.85)", orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig_geo, use_container_width=True)

# --------------------------------------------------------- metro comparison --
with tab_compare:
    st.subheader("Metro Comparison")
    st.caption(
        "Side-by-side comparison of metros added from the Metro Breakdown "
        "tab's \"➕ Add to Comparison\" button -- for weighing a shortlist "
        "of sites against each other directly, instead of flipping between "
        "single-metro breakdowns."
    )

    selected = st.session_state.comparison_metros
    if not selected:
        st.info(
            "No metros added yet. Go to the Metro Breakdown tab, pick a "
            "metro, and click \"➕ Add to Comparison\" to start building a "
            "shortlist.",
            icon="📋",
        )
    else:
        remove_cols = st.columns(len(selected) + 1)
        for i, m in enumerate(selected):
            if remove_cols[i].button(f"✕ {m}", key=f"remove_compare_{m}", help=f"Remove {m} from comparison"):
                st.session_state.comparison_metros = [x for x in selected if x != m]
                st.rerun()
        if remove_cols[-1].button("Clear all"):
            st.session_state.comparison_metros = []
            st.rerun()

        compare_df = scored[scored["metro"].isin(selected)].set_index("metro").loc[selected]

        fig_cmp = go.Figure()
        for score_col, label, color in [
            ("opportunity_score", "Opportunity", "#1f77b4"),
            ("shortage_score", "Shortage", "#d62728"),
            ("feasibility_score", "Feasibility", "#2ca02c"),
        ]:
            fig_cmp.add_trace(go.Bar(x=selected, y=compare_df[score_col], name=label, marker_color=color))
        fig_cmp.update_layout(
            barmode="group", height=360, yaxis_title="Score (0-100)",
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        )
        st.plotly_chart(fig_cmp, use_container_width=True)

        compare_metrics = {
            "rank": "National Rank",
            "opportunity_score": "Opportunity Score",
            "shortage_score": "Shortage Score",
            "feasibility_score": "Feasibility Score",
            "price_to_income": "Price-to-Income",
            "median_home_price_usd": "Median Home Price",
            "median_household_income_usd": "Median Household Income",
            "feasibility_gap_usd": "Feasibility Gap ($/unit)",
            "land_cost_per_unit_usd": "Land Cost/Unit",
            "development_cost_per_unit_usd": "Dev Cost/Unit",
            "permit_velocity_index": "Permit Friction Index",
            "cap_rate_pct": "Cap Rate (%)",
        }
        fmt_rows = {
            "National Rank": lambda v: f"#{int(v)}",
            "Opportunity Score": lambda v: f"{v:.1f}",
            "Shortage Score": lambda v: f"{v:.1f}",
            "Feasibility Score": lambda v: f"{v:.1f}",
            "Price-to-Income": lambda v: f"{v:.2f}×",
            "Median Home Price": lambda v: f"${v:,.0f}",
            "Median Household Income": lambda v: f"${v:,.0f}",
            "Feasibility Gap ($/unit)": lambda v: f"${v:,.0f}",
            "Land Cost/Unit": lambda v: f"${v:,.0f}",
            "Dev Cost/Unit": lambda v: f"${v:,.0f}",
            "Permit Friction Index": lambda v: f"{v:.0f}",
            "Cap Rate (%)": lambda v: f"{v:.2f}%",
        }
        display = compare_df[list(compare_metrics.keys())].rename(columns=compare_metrics).T
        display_fmt = display.apply(lambda r: r.map(fmt_rows[r.name]), axis=1)
        st.dataframe(display_fmt, use_container_width=True, height=36 * (len(display_fmt) + 1))

        st.markdown("---")
        st.markdown("**Save your findings**")
        st.caption(
            "Generates a formal PDF report covering every metro above -- scores, shortage "
            "components, feasibility cost breakdown, and key market data per metro -- plus "
            "the model settings and data provenance in effect right now, for sharing or "
            "attaching to an underwriting package."
        )
        pdf_bytes = build_pdf_report(
            compare_df=compare_df,
            selected=selected,
            model_controls={
                "alpha": alpha,
                "ami_tier_pct": ami_tier_pct,
                "density_tier": density_tier,
                "unit_size_sf": unit_size_sf,
                "soft_cost_pct": soft_cost_pct,
            },
            data_vintage=str(data_vintage),
        )
        st.download_button(
            "\U0001F4C4 Download PDF Report",
            data=pdf_bytes,
            file_name=f"opportunity-report-{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
        )

        st.download_button(
            "Download comparison (CSV)",
            data=compare_df.reset_index().to_csv(index=False).encode(),
            file_name="metro_comparison.csv",
            mime="text/csv",
        )

# ------------------------------------------------------------- buy-down calc --
with tab_buydown:
    st.subheader("Buy-Down Calculator")
    st.caption("Illustrative only -- not a loan offer, rate quote, or financial advice.")

    buydown_metro = st.selectbox(
        "Example scenario for a site in", options=scored["metro"].tolist(), key="buydown_metro",
    )
    metro_ctx = scored[scored["metro"] == buydown_metro].iloc[0]

    FINANCING_OPTIONS = (
        ["Standard Fixed"] + list(TEMPORARY_BUYDOWN_STRUCTURES.keys()) + ["Permanent Buydown (Discount Points)"]
    )
    # Rate presets refresh once a day: a live pull from mortgagenewsdaily.com
    # when reachable, illustrative fallback benchmarks otherwise (always the
    # fallback path in this dev sandbox -- see pipeline/fetch_mortgage_rates.py).
    _today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    live_rates, rate_source, rate_fetched_at = get_rate_presets(_today)
    RATE_PRESETS: dict[str, float | None] = {"Custom (enter below)": None, **live_rates}

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

            rate_preset_label = (
                "Rate preset (live from mortgagenewsdaily.com)" if rate_source == "live"
                else "Rate preset (illustrative benchmark)"
            )
            rate_preset = st.selectbox(
                rate_preset_label, options=list(RATE_PRESETS.keys()),
                help=(
                    f"Refreshed daily from mortgagenewsdaily.com (last fetched {rate_fetched_at})."
                    if rate_source == "live" else
                    "Live fetch from mortgagenewsdaily.com is unavailable right now, so these are "
                    "illustrative typical rates by loan type instead. The app retries the live "
                    "fetch daily. Check current rates at mortgagenewsdaily.com directly and use "
                    "\"Custom\" to enter your own number below if these look stale."
                ),
            )
            preset_value = RATE_PRESETS[rate_preset]
            note_rate = st.number_input(
                "Note rate (%)", min_value=0.0, max_value=15.0,
                value=preset_value if preset_value is not None else 6.5, step=0.125,
                key=f"note_rate_{rate_preset}",
            )
            if preset_value is not None:
                if rate_source == "live":
                    st.caption(
                        f"🟢 Live rate from [mortgagenewsdaily.com](https://www.mortgagenewsdaily.com/) "
                        f"-- fetched {rate_fetched_at}, refreshes daily."
                    )
                else:
                    st.caption(
                        "🟠 Illustrative benchmark, not a live rate feed right now -- see "
                        "[mortgagenewsdaily.com](https://www.mortgagenewsdaily.com/) "
                        "for today's actual rates. The app retries the live fetch daily."
                    )

            financing_type = st.radio("Financing type", FINANCING_OPTIONS, index=2)
            points = 2.0
            if financing_type == "Permanent Buydown (Discount Points)":
                points = st.slider(
                    "Discount points purchased", min_value=0.0, max_value=5.0, value=2.0, step=0.25,
                    help="1 point = 1% of the loan amount, paid upfront, for a permanent rate reduction.",
                )

    principal = home_price - down_usd
    standard_payment = monthly_payment(principal, note_rate, term_years)

    tb_result = None
    pb_result = None
    if financing_type in TEMPORARY_BUYDOWN_STRUCTURES:
        effective_steps = TEMPORARY_BUYDOWN_STRUCTURES[financing_type][:term_years]
        tb_result = temporary_buydown(principal, note_rate, term_years, effective_steps)
    elif financing_type == "Permanent Buydown (Discount Points)":
        pb_result = permanent_buydown(principal, note_rate, term_years, points=points)

    with summary_col:
        with st.container(border=True):
            st.markdown("**PAYMENT SUMMARY**")

            if tb_result is not None:
                periods = [(y.label, y.rate_pct, y.payment) for y in tb_result.schedule]
                n_discounted = len(tb_result.schedule)
                if term_years > n_discounted:
                    start = n_discounted + 1
                    label = f"Year {start}" if term_years == start else f"Year {start}-{term_years}"
                    periods.append((label, tb_result.note_rate_pct, tb_result.note_payment))
                st.table(pd.DataFrame(
                    [{"Year": p, "Rate": f"{r:.2f}%", "Monthly Payment": f"${m:,.0f}"} for p, r, m in periods]
                ))

                savings_bits = [f"\\${y.monthly_savings_vs_note:,.0f}/mo in {y.label}" for y in tb_result.schedule]
                if len(savings_bits) > 1:
                    savings_sentence = "Buyer saves " + ", ".join(savings_bits[:-1]) + f", and {savings_bits[-1]}"
                else:
                    savings_sentence = "Buyer saves " + savings_bits[0]
                savings_sentence += f" -- roughly \\${tb_result.total_subsidy:,.0f} total"
                savings_sentence += (
                    " before the rate resets." if term_years > n_discounted
                    else f" over the life of this {term_years}-year loan."
                )
                st.success(savings_sentence, icon="✅")

            elif pb_result is not None:
                st.table(pd.DataFrame([
                    {"Item": "Note rate (no buydown)", "Rate": f"{pb_result.note_rate_pct:.2f}%", "Monthly Payment": f"${pb_result.note_payment:,.0f}"},
                    {"Item": f"Effective rate ({points:g} pts bought)", "Rate": f"{pb_result.effective_rate_pct:.2f}%", "Monthly Payment": f"${pb_result.effective_payment:,.0f}"},
                ]))
                pb_c1, pb_c2 = st.columns(2)
                pb_c1.metric("Monthly savings", f"${pb_result.monthly_savings:,.0f}")
                pb_c2.metric("Upfront points cost", f"${pb_result.points_cost:,.0f}")
                if pb_result.breakeven_months:
                    st.success(
                        f"Breakeven: ~{pb_result.breakeven_months:.0f} months "
                        f"(~{pb_result.breakeven_months / 12:.1f} years) of staying in the "
                        "loan to recoup the points cost via monthly savings, for the rest "
                        "of the loan after that.",
                        icon="✅",
                    )
                else:
                    st.warning(
                        "No monthly savings at this rate-reduction assumption -- the points "
                        "cost would never break even.",
                        icon="⚠️",
                    )

            else:  # Standard Fixed
                st.table(pd.DataFrame([{"Year": f"1-{term_years}", "Rate": f"{note_rate:.2f}%", "Monthly Payment": f"${standard_payment:,.0f}"}]))
                st.info(
                    f"Standard fixed loan -- \\${standard_payment:,.0f}/mo for all {term_years} years, "
                    "no rate reduction. Pick a buydown type above to see payment relief.",
                    icon="ℹ️",
                )
            st.caption(f"Financed amount: \\${principal:,.0f} ({100 - down_pct}% of \\${home_price:,.0f})")

    with st.container(border=True):
        st.markdown("**MONTHLY PAYMENT OVER TIME**")
        st.caption(f"{term_years}-year fixed loan · {down_pct}% down · \\${principal:,.0f} principal")

        fig_pay = go.Figure()
        if tb_result is not None:
            chart_years = min(5, term_years)
            x_years = list(range(1, chart_years + 1))
            n_discounted = len(tb_result.schedule)
            y_buydown = [
                tb_result.schedule[y - 1].payment if y <= n_discounted else tb_result.note_payment
                for y in x_years
            ]
            y_standard = [standard_payment] * len(x_years)
            fig_pay.add_trace(go.Scatter(
                x=x_years, y=y_buydown, name=financing_type, mode="lines+markers",
                line=dict(color="#c1873b", width=3), marker=dict(size=8),
            ))
            fig_pay.add_trace(go.Scatter(
                x=x_years, y=y_standard, name="Standard Fixed", mode="lines",
                line=dict(color="#555555", width=2, dash="dash"),
            ))
            if term_years > n_discounted:
                reset_x = n_discounted + 0.5
                fig_pay.add_vline(x=reset_x, line_width=1, line_dash="dot", line_color="gray")
                fig_pay.add_annotation(x=reset_x, y=max(y_buydown + y_standard), text="Rate resets", showarrow=False, yshift=12, font=dict(size=10, color="gray"))
                st.caption(f"Rate and payment return to the note rate in Year {n_discounted + 1} and hold there for the rest of the loan.")
            fig_pay.update_layout(xaxis=dict(title="Year", tickmode="array", tickvals=x_years))

        elif pb_result is not None:
            x_years = list(range(1, min(10, term_years) + 1))
            fig_pay.add_trace(go.Scatter(
                x=x_years, y=[pb_result.effective_payment] * len(x_years),
                name=f"Permanent Buydown ({points:g} pts)", mode="lines+markers",
                line=dict(color="#c1873b", width=3), marker=dict(size=6),
            ))
            fig_pay.add_trace(go.Scatter(
                x=x_years, y=[standard_payment] * len(x_years), name="Standard Fixed", mode="lines",
                line=dict(color="#555555", width=2, dash="dash"),
            ))
            fig_pay.update_layout(xaxis=dict(title="Year", tickmode="array", tickvals=x_years))
            st.caption("The permanent rate reduction holds for the full loan term -- no reset.")

        else:  # Standard Fixed
            x_years = list(range(1, min(5, term_years) + 1))
            fig_pay.add_trace(go.Scatter(
                x=x_years, y=[standard_payment] * len(x_years), name="Standard Fixed", mode="lines+markers",
                line=dict(color="#555555", width=3), marker=dict(size=8),
            ))
            fig_pay.update_layout(xaxis=dict(title="Year", tickmode="array", tickvals=x_years))

        fig_pay.update_layout(
            height=340, margin=dict(l=0, r=0, t=10, b=0),
            yaxis_title="Monthly payment ($)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        )
        st.plotly_chart(fig_pay, use_container_width=True)

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
Zillow Research (ZHVI/ZORI). CoStar/RCA are explicitly **not** used. Every
field below carries one of three provenance labels -- these are not the
same thing, and conflating them would misrepresent the data:
"""
    )
    c1, c2, c3 = st.columns(3)
    c1.success("**live**\n\nFetched from the source API this session.", icon="🟢")
    c2.info(
        "**published**\n\nA real, publicly-published statistic (Census ACS) -- "
        "just not fetched live this run. Not modeled or guessed.",
        icon="🔵",
    )
    c3.warning(
        "**synthetic**\n\nA modeled estimate. No free, metro-level public "
        "source exists for this field at all.",
        icon="🟠",
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
vacancy/collection loss %, units/acre (zoning policy input), permit
velocity / regulatory-friction index, and AMI (derived from the published
household-income anchor with modeled noise, since metro-level HUD AMI
figures aren't hand-compiled here).

**Published fields** (real Census ACS-grounded figures, not modeled; see
`pipeline/anchors.py`): median home price and median household income --
and therefore the Price-to-Income Ratio computed from them. These are
live-eligible (the pipeline will overwrite them with a fresh live pull
when run with network access) but are **not synthetic** even before that
happens -- they're real published numbers from general knowledge of ACS
statistics (vintage noted in the data vintage caption above), just not
re-verified against the live API this session. Treat them as directionally
accurate, not penny-precise, until a live refresh runs.

**Other live-eligible fields** (synthetic/modeled fallback until a live
refresh runs, since no reliable per-metro published anchor was compiled
for these): population growth, permits per 1,000 units, rental & homeowner
vacancy, 3-year rent growth, 3-year income growth.
"""
    )
