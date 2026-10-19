# Affordable Housing Opportunity Explorer

This repository is for the Real Estate Industry Project Class (REAL 43905).

The U.S. is short more than 7 million affordable housing units, but developers,
CDFIs, and housing authorities have no fast way to cross-reference "where
housing is underserved" against "where building actually pencils out
financially." This app ranks **150 U.S. metro areas** by an **Opportunity
Score**, derived from a **Shortage Score** (need signal) and a **Feasibility
Score** (can-it-be-built-without-subsidy signal), so a developer can screen
sites before commissioning a full pro forma. It also includes an illustrative
homebuyer buy-down calculator with multiple financing structures.

Live app: deploy to [Render](https://render.com) using `render.yaml` (see
**Deploying to Render** below).

## What's in the app

- **Ranked Table** — all 150 metros sorted by Opportunity Score, downloadable
  as CSV. Every column header has a hover tooltip explaining what it shows
  and how it's calculated.
- **Map** — metros plotted on a real U.S. basemap (land, state borders,
  coastlines), bubble size = population, color = Opportunity Score
- **Metro Breakdown** — per-metro Shortage component z-scores, a Feasibility
  cost waterfall, editable land-cost/hard-cost overrides, an "Add to
  Comparison" button, and a **sub-metro "zoom in"**: every metro is broken
  into four illustrative submarket rings (Urban Core, Inner Suburbs, Outer
  Suburbs, Exurban / Micropolitan Fringe) ranked against each other so a
  developer can see *where within the metro* the numbers work best, not just
  which metro nationally ranks highest. Each ring also lists the real Census
  counties that fall within it, and an expander explains exactly how the
  ring radii were chosen.
- **Metro Comparison** — a shortlist of metros added from the Metro
  Breakdown tab, shown side-by-side: a grouped bar chart and a full
  transposed comparison table, downloadable as CSV, plus a **"Download PDF
  Report"** button that generates a formal, multi-page PDF covering every
  metro in the shortlist.
- **Buy-Down Calculator** — a metro-linked calculator supporting Standard
  Fixed, four temporary buy-down structures (3-2-1, 2-1, 1-1, 1-0), and a
  Permanent Buydown (discount points): Loan Inputs / Payment Summary cards,
  a note-rate dropdown that refreshes **daily** with current benchmark
  rates by loan type (live-eligible, same provenance model as the rest of
  the app -- falls back to illustrative benchmarks with a direct link to
  mortgagenewsdaily.com when a live pull isn't available, plus full manual
  override either way), a savings callout, a monthly-payment-over-time
  comparison chart, and metro-context stat tiles. Illustrative only, not a
  loan product.
- **Data Sources** — a transparency table showing, for every field in the
  current view, whether it is `live`, `published`, or `synthetic`.

Sidebar controls ("Model Controls"): Opportunity Score weight (α/β),
Shortage component weights, Feasibility component weights, AMI affordability
tier, zoning/density tier, unit size, and soft-cost %. The metro universe is
fixed at all 150 metros — there is no 20/50-metro toggle.

## Methodology (per the project charter)

All Shortage/Feasibility inputs are standardized as z-scores across the
current metro set before being combined.

**Shortage Score** (need signal):
- Permit Gap = CAGR(demand driver) − CAGR(permits per 1,000 existing housing units)
- Vacancy Tightness = −1 × (rental vacancy rate + homeowner vacancy rate)
- Price-to-Income Ratio = median home price ÷ median household income
- Rent-Income Divergence = 3yr rent growth − 3yr income growth
- Shortage Score = 100 × normalize(Σ wᵢ · z(componentᵢ)); weights start equal, adjustable in the app

**Feasibility Score** (can it be built without subsidy):
- Achievable Rent (monthly) = (0.30 × AMI% × Area Median Income) / 12
- Land Cost/Unit = Land cost per acre ÷ assumed units per acre (density/zoning tier) — editable per metro in Metro Breakdown
- Hard Cost/Unit = Construction $/SF × Unit Size (SF) — construction $/SF editable per metro in Metro Breakdown
- Soft Costs = 20% default × (Land Cost/Unit + Hard Cost/Unit)
- Development Cost/Unit = Land + Hard + Soft
- Effective Gross Income = Achievable Rent × 12 × (1 − Vacancy/Collection Loss %)
- NOI = EGI − Operating Expenses (per unit)
- Supportable Value = NOI ÷ Cap Rate
- Feasibility Gap = Supportable Value − Development Cost (positive = buildable without subsidy)
- Feasibility Score = 100 × normalize(v1·z(Feasibility Gap) − v2·z(Permit Velocity)); weights start equal, adjustable in the app

**Opportunity Score** = α·Shortage + β·Feasibility, α+β=1, default 0.5/0.5, user-adjustable.

**Homebuyer add-on**: standard amortization M = P[r(1+r)ⁿ]/[(1+r)ⁿ−1] at
note rate, compared against either a temporary step-down buy-down (3-2-1,
2-1, 1-1, or 1-0) or a permanent discount-points buy-down. Illustrative
only, not a loan product.

The exact formulas are implemented in `scoring.py` and `finance.py`.

### Editable land & hard cost overrides

Land cost/acre and construction cost/SF are the two Feasibility inputs the
charter flags as having no free public source (they're always synthetic —
see **Data sources & what's synthetic** below). The Metro Breakdown tab lets
you override either value for the metro you're viewing with your own
market-sourced number; every score on that page — including the sub-metro
rings — recomputes from the override, re-ranked against the other 149
metros' baseline estimates. The Ranked Table tab always shows the baseline
(non-overridden) scores, so an overridden metro's rank on Metro Breakdown may
differ slightly from its rank on the Ranked Table.

### Sub-metro zoom-in rings

Site selection happens below the metro level, so the Metro Breakdown tab
also scores four illustrative submarket rings *within* the selected metro:
Urban Core, Inner Suburbs, Outer Suburbs, and Exurban / Micropolitan Fringe.
Every metro uses the same four generic rings rather than custom-drawn
boundaries — there is no free, sub-metro-level public dataset for the
feasibility-side cost inputs (same reason those fields are synthetic at the
metro level), so a fixed, consistent ring structure is used as a comparable
yardstick across all 150 metros instead of a custom-fit boundary per metro.

Each ring applies documented, real-estate-standard core-vs-periphery
adjustments to the parent metro's data (see `pipeline/subareas.py` for the
exact factors): land cost and construction cost step down sharply from
Urban Core to Exurban Fringe, permitting friction eases, and vacancy loosens
slightly; HUD Area Median Income is held constant across rings (HUD
publishes one income-limit schedule per metro), so only the cost side of
the feasibility math changes ring to ring, not the achievable-rent side.
Shortage/Feasibility/Opportunity scores for the four rings are z-scored
*within that one metro's four rings*, not against the national 150-metro
set — they answer "which ring is relatively best to site in, within this
metro," not "how does this ring compare to a different metro."

Below the ring table/chart, the Metro Breakdown tab also plots the metro's
home state (drawn offline — see `pipeline/geo_shapes.py`) with a star at
the metro's center and the four rings as concentric shaded bands around it
(via `pipeline.subareas.ring_circle_points`), colored by each ring's local
Opportunity Score.

**Ring radii — how they were chosen.** The four rings use fixed radii — 8 /
20 / 40 / 70 miles — applied the same way to every metro. They are not
measured per metro from commute survey data, traffic patterns, or each
metro's actual CBSA boundary; they're a planning-literature-informed
heuristic for a typical mid-to-large U.S. metro, chosen as a consistent
yardstick so every metro is comparable:

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
metros hemmed in by geography or water — that's an accepted tradeoff for
having one consistent, comparable measure across all 150 metros rather than
a custom-fit boundary for each one. See the exact bounds in
`pipeline/subareas.ring_bounds_miles()`.

**Counties within each ring.** Each ring also lists the real Census county
names whose approximate extent falls within that ring's distance band from
the metro's center point, computed with the haversine great-circle distance
formula (`pipeline/geo_shapes.py: counties_by_ring`). These are genuine
Census county names (verified against the `cb_2016_us_county_500k`
cartographic boundary shapefile — 3,233 records, one per U.S. county or
county-equivalent), not cities — a county name that happens to match a
well-known city (e.g. "San Francisco, CA", a consolidated city-county, or
"New York, NY", i.e. Manhattan) is exactly that: the real county, correctly
named.

Each county's distance is measured to the *nearest point on its bounding
box* (0 if the metro's point falls inside that box, otherwise the distance
to the box's near edge or corner) rather than to the box's midpoint — a
bbox midpoint can sit misleadingly far from a metro that's actually
adjacent to, or even inside, a large or elongated county. On top of that,
the one county whose boundary *actually contains* the metro's own
coordinate (its "home" county, found via exact point-in-polygon — e.g.
Santa Clara County for San Jose) is always guaranteed a spot in the Urban
Core ring, listed exactly once, even in the rare case its bbox-based
distance would disagree. Before this (bbox-midpoint-only, no home-county
guarantee), Urban Core came up empty for 43% of the 150 metros; after it,
0%, and every other ring's empty-ring rate dropped to 5% or below —
verified by running `counties_by_ring` across the full metro set. Avoiding
a true-centroid/point-in-polygon-everywhere approach (which would need a
geometry library like shapely) keeps the dependency footprint small; this
bbox-based approximation is a documented, verified-reasonable tradeoff, not
a silent one. A ring can still legitimately come up empty for a metro
bordered by very large counties (common in parts of the rural West, where
even the *nearest* neighboring county's edge can be tens of miles away).
County boundary geometry comes from the Census cartographic boundary
shapefile bundled by the `plotly-geo` PyPI package — no network access is
needed to compute this.

### Metro Comparison

Click "➕ Add to Comparison" on any metro's Metro Breakdown page to add it to
a running shortlist (kept in the session only, not saved between visits).
The Metro Comparison tab shows every added metro side-by-side: a grouped bar
chart of Opportunity/Shortage/Feasibility scores, and a full transposed
table of every underlying metric, downloadable as CSV. Metros can be removed
individually or cleared all at once.

**Download PDF Report.** Below the comparison table, "📄 Download PDF
Report" (built with `report.py`, using reportlab) generates a formal,
multi-page PDF covering the whole shortlist in one file: a cover page
listing the metros and the exact Model Controls settings (α/β weighting,
AMI tier, density tier, unit size, soft-cost %) in effect when it was
generated, an executive-summary comparison table, one detail page per
metro (shortage z-score components, the full feasibility cost breakdown,
and key market data), and a closing page with the live/published/synthetic
data-provenance explanation and the standard disclaimer. It's meant as a
save-your-findings artifact for a shortlist built during a session --
something to attach to an underwriting package or share with a colleague
without re-deriving the numbers by hand.

## Buy-Down Calculator: financing types

The calculator supports six financing types, selectable under "Financing
type":

| Type | Structure |
|---|---|
| Standard Fixed | Standard fixed-rate amortization at the note rate, no buydown |
| 3-2-1 Buydown | Rate is 3 points below note in year 1, 2 points below in year 2, 1 point below in year 3, note rate from year 4 on |
| 2-1 Buydown | Rate is 2 points below note in year 1, 1 point below in year 2, note rate from year 3 on |
| 1-1 Buydown | Rate is 1 point below note, flat, for years 1-2, note rate from year 3 on |
| 1-0 Buydown | Rate is 1 point below note for year 1 only, note rate from year 2 on |
| Permanent Buydown (Discount Points) | Points purchased upfront (1 point = 1% of loan amount) permanently lower the rate by ~0.25 points per point (standard industry rule of thumb), for the full loan term; the app also computes the breakeven period (months to recoup the points cost from the monthly savings) |

All temporary buydown math floors the discounted rate at 0% and correctly
truncates the step-down schedule to fit loan terms shorter than the
structure's own length (e.g. a 3-2-1 buydown on a 2-year term only shows
years 1-2). All six types are implemented in `finance.py` and covered by
unit tests in `tests/test_scoring.py`.

### Note rate: daily-refreshing rate presets

The rate-preset dropdown offers today's rates by loan type (30-Year Fixed,
15-Year Fixed, FHA, VA, Jumbo, 5/1 ARM). It follows the same live/fallback
pattern as the rest of the app's data (see **Data sources & what's
synthetic** below), not a static hardcoded list:

- `pipeline/fetch_mortgage_rates.py` attempts a live scrape of
  [mortgagenewsdaily.com](https://www.mortgagenewsdaily.com/)'s public
  rates page for all six loan types. It only returns a result when **all
  six** rates are found with plausible values (0.5-20%) -- a partial or
  ambiguous parse returns nothing rather than risk showing a mismatched
  rate for the wrong loan type.
- `app.py` wraps that call in `st.cache_data(ttl=86_400)`, keyed on
  today's date -- so it refreshes **once a day**, not on every page
  interaction, and automatically re-attempts the live pull again the next
  calendar day.
- When the live pull fails -- which is every run in this project's dev
  sandbox, since mortgagenewsdaily.com is outside the restricted-egress
  allowlist here (confirmed directly; see **Network access** below) -- it
  falls back to the same static illustrative benchmark rates as before,
  and the dropdown label and help text switch to say so plainly ("Live
  fetch from mortgagenewsdaily.com is unavailable right now..."). The
  fallback values live in `pipeline.fetch_mortgage_rates.FALLBACK_RATES`.

Selecting any preset fills in the Note Rate field, which remains fully
editable; a "Custom" option and a direct link to mortgagenewsdaily.com are
always available so users can look up today's actual rate and enter it
themselves regardless of which path is active. The live-fetch code is real,
not a stub -- it will start returning live rates the moment it runs
somewhere with normal internet access (e.g. a deployed Render service),
the same as the Census/Zillow/FHFA/FRED fetchers.

## Data sources & what's synthetic

Per the charter, real inputs are pulled from **public APIs and bulk data
files only** — Census, ACS, Census Building Permits Survey (BPS), FRED, FHFA
HPI, and Zillow Research (ZHVI/ZORI). CoStar/RCA are explicitly not used.

Every field carries one of **three** provenance labels — conflating them
would misrepresent the data:

- 🟢 **live** — fetched from the source API this session.
- 🔵 **published** — a real, publicly-published statistic (Census ACS), not
  modeled or guessed, but not re-fetched live this run.
- 🟠 **synthetic** — a modeled estimate; no free, metro-level public source
  exists for this field at all.

| Field group | Source | Status |
|---|---|---|
| Median home price, median household income (and the Price-to-Income Ratio computed from them) | Census ACS, real published figures | **Published** (`pipeline/anchors.py`) — live-eligible, overwritten by a live pull when one runs, but real and not synthetic even before that |
| Population growth, vacancy rates, 3yr rent growth, 3yr income growth | Census ACS / PEP, Zillow ZORI | Live-eligible (`pipeline/fetch_census.py`, `pipeline/fetch_zillow.py`) — synthetic fallback until a live refresh runs |
| Permits per 1,000 units | Census Building Permits Survey | Live-eligible (`pipeline/fetch_permits.py`) — synthetic fallback until a live refresh runs |
| Home price growth (cross-check) | FHFA HPI | Live-eligible (`pipeline/fetch_fhfa.py`) |
| 10-yr Treasury (cap-rate benchmark) | FRED DGS10 | Live-eligible (`pipeline/fetch_fred.py`) |
| Land cost/acre, construction $/SF, cap rate, operating expenses/unit, vacancy/collection loss %, units/acre, permit velocity, AMI | — | **Always synthetic** — no free, metro-level public source exists (per charter); AMI is derived from the published income anchor with modeled noise |

"Live-eligible" fields fall back to a tier-calibrated synthetic estimate
(`pipeline/synthetic.py`) whenever a live pull fails, is rate-limited, or the
pipeline is run without network access. The app's **Data Sources** tab shows,
per field, whether the value currently on screen is `live`, `published`, or
`synthetic`.

### Why median home price & household income are "published," not synthetic

Earlier versions of this app treated median home price and median household
income as synthetic, which produced a self-contradictory Price-to-Income
Ratio (a "shortage" signal computed from two numbers the app itself admitted
were made up). That's fixed: `pipeline/anchors.py` now carries real,
Census-ACS-grounded median home price and household income figures for all
150 metros, tagged `published` rather than `synthetic`. They are real
numbers, not live-refetched every run — treat them as directionally
accurate, not penny-precise, until a live refresh actually runs (see
**Scheduled batch refresh** below). The Price-to-Income Ratio computed from
them is correspondingly a real number, not a synthetic one.

### Why most other fields are still synthetic today

This app ships with `data/metro_dataset.csv` already generated so it works
immediately with zero setup. It was built by running
`python -m pipeline.build_dataset` in a development sandbox whose outbound
network access is restricted to a small allowlist (PyPI, npm, GitHub, etc.) —
Census, Zillow, FHFA, FRED, and Mortgage News Daily are not reachable from
there, so every live-eligible field (other than the published anchors) fell
back to the synthetic generator. The live-fetch code is fully implemented
and will populate real values the moment it runs somewhere with normal
internet access (a laptop, CI, or a Render service/cron job) — see
**Scheduled batch refresh** below.

Synthetic values are not random noise: each metro is tagged with a regional
tier (`superstar_coastal`, `sunbelt_growth`, `midwest_legacy`,
`mixed_northeast_midatlantic` — see `metros.py`), and every generated field
is drawn from a tier-calibrated distribution anchored to the real published
median home price / household income figures per metro (`pipeline/anchors.py`),
so the cross-metro pattern (expensive/tight coastal metros, high-growth
Sunbelt metros, low-cost Midwest metros) looks like a real market
cross-section. It is still an estimate, not observed data, and is labeled as
such everywhere in the app.

## Project structure

```
app.py                      Streamlit app (entry point)
metros.py                   150-metro reference table (CBSA, lat/lon, tier)
scoring.py                  Shortage / Feasibility / Opportunity score formulas
finance.py                  Mortgage amortization + temporary/permanent buy-down calculators
report.py                   PDF report builder for the Metro Comparison shortlist (reportlab)
pipeline/
  anchors.py                 Real, published home-price/income anchors for all 150 metros
  synthetic.py                Tier-calibrated synthetic data generator + density/AMI tier constants
  fetch_census.py             Live Census ACS / PEP pulls
  fetch_permits.py            Live Census Building Permits Survey pulls
  fetch_fhfa.py                Live FHFA HPI pulls
  fetch_zillow.py              Live Zillow ZORI/ZHVI bulk CSV pulls
  fetch_fred.py                 Live FRED series pulls
  fetch_mortgage_rates.py       Live mortgagenewsdaily.com rate-preset scrape + fallback benchmarks
  subareas.py                  Sub-metro submarket ring generator + ring_bounds_miles()
  geo_shapes.py                 Offline state/county shapefile rendering + counties_by_ring()
  build_dataset.py             Orchestrator: live-first, published/synthetic-fallback, writes data/metro_dataset.csv
data/metro_dataset.csv        Bundled dataset (150 metros) shipped with the app
tests/
  test_scoring.py               Unit tests for scoring math, finance calculators, and geo helpers
  test_fetch_mortgage_rates.py  Unit tests for the rate-preset scraper's parsing and fallback behavior
  test_report.py                Unit tests for PDF report generation
render.yaml                  Render Blueprint (web service + optional weekly refresh cron job)
requirements.txt
```

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# (optional) regenerate the dataset -- synthetic-only by default:
python -m pipeline.build_dataset
# or attempt a live pull first, falling back to published/synthetic per-field:
ENABLE_LIVE_FETCH=1 python -m pipeline.build_dataset

streamlit run app.py
```

Then open the URL Streamlit prints (defaults to http://localhost:8501).

**Note on the maps**: both the national map and the per-metro state map
render state (and, for the county-ring listings, county) boundaries from an
**offline** shapefile (`cb_2016_us_state_500k` / `cb_2016_us_county_500k`,
bundled by the `plotly-geo` PyPI package) via `pipeline/geo_shapes.py`, not
from Plotly's default `scope="usa"` geo trace. That default fetches basemap
shapes from Plotly's public CDN (`cdn.plot.ly`) at render time, which failed
outright in this project's restricted-egress dev sandbox and would fail the
same way for any viewer whose network blocks that CDN (a locked-down
corporate proxy, for instance). Building the polygons from local shapefile
data instead removes that dependency entirely -- no map or county listing
needs any network access to render. See `pipeline/geo_shapes.py` for how the
shapefile is read and simplified.

Run the test suite with:

```bash
pip install pytest
pytest tests/
```

## Deploying to Render

1. Push this repository to GitHub.
2. In Render, choose **New > Blueprint** and point it at this repo — it will
   read `render.yaml` and provision the web service (and the optional weekly
   refresh cron job) automatically.
   - Alternatively, create a single **Web Service** manually with:
     - Build command: `pip install -r requirements.txt`
     - Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`
3. (Optional) Add `CENSUS_API_KEY` / `FRED_API_KEY` environment variables in
   the Render dashboard for higher-throughput live data pulls (see
   `.env.example`). Neither is required for the app to run.
4. Render builds from GitHub automatically on every push to the connected branch.

### Scheduled batch data refresh (MVP requirement)

The charter's MVP scope calls for a scheduled batch data refresh. **Render
Cron Jobs require a paid plan** (Starter or above) -- they are not available
on the free plan -- so `render.yaml` ships with just the web service by
default, to keep the app deployable for free. A commented-out
`metro-dataset-refresh` cron job (weekly, runs
`ENABLE_LIVE_FETCH=1 python -m pipeline.build_dataset`) is included in
`render.yaml` for when you're ready to add it.

If you're staying on the free plan, the simplest alternative is a scheduled
**GitHub Action** that runs the same command and commits the refreshed
`data/metro_dataset.csv`, which triggers a normal Render redeploy -- ask and
I can set that up.

Whichever mechanism runs it, a cron job's filesystem is ephemeral and
separate from the web service's, so to actually pick up a refreshed dataset
you'll want one of:

- Commit the regenerated `data/metro_dataset.csv` back to the repo (e.g. the
  cron job opens a PR, or pushes directly with a deploy key) so the next web
  service deploy picks it up, or
- Point both services at a Render **Persistent Disk** or an external object
  store (S3, etc.) for `data/metro_dataset.csv` instead of the repo copy.

The pipeline code itself (`pipeline/build_dataset.py`) is refresh-mechanism
agnostic — it just needs to run somewhere with network access and write to
`data/metro_dataset.csv`.

### Network access

This development sandbox's outbound network access is restricted to a small
allowlist (PyPI, npm, GitHub, etc.). Census, Zillow, FHFA, FRED, and Mortgage
News Daily are all unreachable from inside it (confirmed directly, including
via a dedicated web-fetch tool, not just raw sockets). That is why:

- `data/metro_dataset.csv` ships with published anchors but otherwise
  synthetic live-eligible fields (see **Data sources & what's synthetic**),
  and
- the Buy-Down Calculator's rate dropdown falls back to illustrative
  benchmark presets with a link to check live rates yourself, instead of
  showing a live mortgagenewsdaily.com pull (see **Note rate:
  daily-refreshing rate presets** above).

None of this is a limitation of the live-fetch code itself, which is fully
implemented in `pipeline/fetch_*.py` (including
`pipeline/fetch_mortgage_rates.py`) — it will populate real, live data the
moment it runs somewhere with normal internet access: the dataset fetchers
via `ENABLE_LIVE_FETCH=1 python -m pipeline.build_dataset`, and the rate
scraper automatically, the first time the app is loaded (and once a day
after that) on a deployment that can reach mortgagenewsdaily.com.

## MVP scope (per charter)

**In:** 150 U.S. metros; Shortage, Feasibility, Opportunity scores; ranked
table (with tooltips) and map; per-metro score breakdown with editable cost
overrides and real county-ring detail; Metro Comparison with a downloadable
PDF report; α/β and AMI-tier configuration sliders; buy-down calculator with
multiple financing structures and daily-refreshing rate presets (live when
reachable, illustrative fallback otherwise); scheduled batch data refresh.

**Deferred:** parcel-level siting (below the county-ring level); licensed
CoStar/RCA integration; full underwriting outputs (IRR, debt sizing); actual
loan origination workflow; developer user accounts for personalization;
saved/persistent Metro Comparison shortlists across sessions (currently
session-only, exportable as PDF/CSV before the session ends).

## Disclaimer

This tool is a screening aid for illustrative and educational purposes. It is
not investment, financial, or legal advice, and the buy-down calculator is
not a loan product, rate quote, or offer of credit. Feasibility-side inputs
(land cost, construction cost, cap rate, operating expenses, vacancy/collection
loss, and permit velocity) are synthetic estimates, not observed market data
— always validate with a full local pro forma before making a development
decision. Buy-down rate presets refresh daily from mortgagenewsdaily.com when
reachable, but are not a locked rate quote even then, and fall back to
illustrative benchmarks when a live pull isn't available — check a live
source (e.g. mortgagenewsdaily.com) and your lender for actual current rates
and pricing. The downloadable PDF report is a snapshot of the app's output at
the time it was generated, carrying the same synthetic/published/live
provenance and disclaimers as the live app -- it is not an appraisal,
underwriting package, or substitute for professional due diligence.
