# Affordable Housing Opportunity Explorer

This repository is for the Real Estate Industry Project Class (REAL 43905).

The U.S. is short more than 7 million affordable housing units, but developers,
CDFIs, and housing authorities have no fast way to cross-reference "where
housing is underserved" against "where building actually pencils out
financially." This app ranks the top U.S. metro areas by an **Opportunity
Score**, derived from a **Shortage Score** (need signal) and a **Feasibility
Score** (can-it-be-built-without-subsidy signal), so a developer can screen
sites before commissioning a full pro forma. It also includes an illustrative
homebuyer buy-down calculator.

Live app: deploy to [Render](https://render.com) using `render.yaml` (see
**Deploying to Render** below).

## What's in the app

- **Ranked Table** — all metros sorted by Opportunity Score, downloadable as CSV
- **Map** — metros plotted on a real U.S. basemap (land, state borders, coastlines), bubble size = population, color = Opportunity Score
- **Metro Breakdown** — per-metro Shortage component z-scores, a Feasibility cost waterfall, and a **sub-metro "zoom in"**: every metro is broken into four illustrative submarket rings (Urban Core, Inner Suburbs, Outer Suburbs, Exurban / Micropolitan Fringe) ranked against each other so a developer can see *where within the metro* the numbers work best, not just which metro nationally ranks highest
- **Buy-Down Calculator** — a metro-linked 2-1 temporary buy-down calculator: Loan Inputs / Payment Summary cards, a savings callout, a monthly-payment-over-time comparison chart (2-1 buydown vs. standard fixed), and metro-context stat tiles (median home price, price-to-income, Opportunity Score). Illustrative only, not a loan product.
- **Data Sources** — a transparency table showing which fields are live-sourced vs. synthetic estimates, for every field in the current view

Sidebar controls: metro universe (top 20 / top 50), Opportunity Score weight
(α/β), Shortage component weights, Feasibility component weights, AMI
affordability tier, zoning/density tier, unit size, and soft-cost %.

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
- Land Cost/Unit = Land cost per acre ÷ assumed units per acre (density/zoning tier)
- Hard Cost/Unit = Construction $/SF × Unit Size (SF)
- Soft Costs = 20% default × (Land Cost/Unit + Hard Cost/Unit)
- Development Cost/Unit = Land + Hard + Soft
- Effective Gross Income = Achievable Rent × 12 × (1 − Vacancy/Collection Loss %)
- NOI = EGI − Operating Expenses (per unit)
- Supportable Value = NOI ÷ Cap Rate
- Feasibility Gap = Supportable Value − Development Cost (positive = buildable without subsidy)
- Feasibility Score = 100 × normalize(v1·z(Feasibility Gap) − v2·z(Permit Velocity)); weights start equal, adjustable in the app

**Opportunity Score** = α·Shortage + β·Feasibility, α+β=1, default 0.5/0.5, user-adjustable.

**Homebuyer add-on**: standard amortization M = P[r(1+r)ⁿ]/[(1+r)ⁿ−1] at
note rate vs. a 2-1 temporary buy-down, showing the payment delta.
Illustrative only, not a loan product.

The exact formulas are implemented in `scoring.py` and `finance.py`.

### Sub-metro zoom-in rings

Site selection happens below the metro level, so the Metro Breakdown tab
also scores four illustrative submarket rings *within* the selected metro:
Urban Core, Inner Suburbs, Outer Suburbs, and Exurban / Micropolitan Fringe.
Every metro uses the same four generic rings rather than specific named
places or counties — there is no free, sub-metro-level public dataset for
the feasibility-side inputs (same reason those fields are synthetic at the
metro level), and fabricating precise county/neighborhood detail for 50
metros without a verified source would trade a defensible estimate for an
unverifiable one.

Each ring applies documented, real-estate-standard core-vs-periphery
adjustments to the parent metro's data (see `pipeline/subareas.py` for the
exact factors): land cost and construction cost step down sharply from
Urban Core to Exurban Fringe, permitting friction eases, and vacancy loosens
slightly; HUD Area Median Income is held constant across rings (HUD
publishes one income-limit schedule per metro), so only the cost side of
the feasibility math changes ring to ring, not the achievable-rent side.
Shortage/Feasibility/Opportunity scores for the four rings are z-scored
*within that one metro's four rings*, not against the national 50-metro
set — they answer "which ring is relatively best to site in, within this
metro," not "how does this ring compare to a different metro."

Below the ring table/chart, the Metro Breakdown tab also plots the metro's
home state (drawn offline -- see `pipeline/geo_shapes.py`) with a star at
the metro's center and the four rings as concentric shaded bands around it
(via `pipeline.subareas.ring_circle_points`), colored by each ring's local
Opportunity Score. Ring radii (8 / 20 / 40 / 70 miles) are fixed, stylized
bands applied the same way to every metro -- they visualize "closer in vs.
farther out," not a surveyed commute-shed or neighborhood boundary for any
specific place.

## Data sources & what's synthetic

Per the charter, real inputs are pulled from **public APIs and bulk data
files only** — Census, ACS, Census Building Permits Survey (BPS), FRED, FHFA
HPI, and Zillow Research (ZHVI/ZORI). CoStar/RCA are explicitly not used.

| Field group | Source | Status |
|---|---|---|
| Population growth, median household income, median home price, vacancy rates, 3yr rent growth | Census ACS / PEP, Zillow ZORI | Live-eligible (`pipeline/fetch_census.py`, `pipeline/fetch_zillow.py`) |
| Permits per 1,000 units | Census Building Permits Survey | Live-eligible (`pipeline/fetch_permits.py`) |
| Home price growth (cross-check) | FHFA HPI | Live-eligible (`pipeline/fetch_fhfa.py`) |
| 10-yr Treasury (cap-rate benchmark) | FRED DGS10 | Live-eligible (`pipeline/fetch_fred.py`) |
| Land cost/acre, construction $/SF, cap rate, operating expenses/unit, vacancy/collection loss %, units/acre, permit velocity | — | **Always synthetic** — no free, metro-level public source exists (per charter) |

"Live-eligible" fields fall back to a tier-calibrated synthetic estimate
(`pipeline/synthetic.py`) whenever a live pull fails, is rate-limited, or the
pipeline is run without network access. The app's **Data Sources** tab shows,
per field, whether the value currently on screen is `live` or `synthetic`.

### Why the bundled dataset is synthetic today

This app ships with `data/metro_dataset.csv` already generated so it works
immediately with zero setup. It was built by running
`python -m pipeline.build_dataset` in a development sandbox whose outbound
network access is restricted to a small allowlist (PyPI, npm, GitHub, etc.) —
Census, Zillow, FHFA, and FRED are not reachable from there, so every field
fell back to the synthetic generator. The live-fetch code is fully
implemented and will populate real values the moment it runs somewhere with
normal internet access (a laptop, CI, or a Render service/cron job) — see
**Scheduled batch refresh** below.

Synthetic values are not random noise: each metro is tagged with a regional
tier (`superstar_coastal`, `sunbelt_growth`, `midwest_legacy`,
`mixed_northeast_midatlantic` — see `metros.py`), and every generated field
is drawn from a tier-calibrated distribution anchored to real, well-known
median home price / household income figures per metro (`pipeline/anchors.py`),
so the cross-metro pattern (expensive/tight coastal metros, high-growth
Sunbelt metros, low-cost Midwest metros) looks like a real market
cross-section. It is still an estimate, not observed data, and is labeled as
such everywhere in the app.

## Project structure

```
app.py                      Streamlit app (entry point)
metros.py                   Top-50 metro reference table (CBSA, lat/lon, tier)
scoring.py                  Shortage / Feasibility / Opportunity score formulas
finance.py                  Mortgage amortization + 2-1 buy-down calculator
pipeline/
  anchors.py                 Real home-price/income anchors used by the synthetic generator
  synthetic.py                Tier-calibrated synthetic data generator + density/AMI tier constants
  fetch_census.py             Live Census ACS / PEP pulls
  fetch_permits.py            Live Census Building Permits Survey pulls
  fetch_fhfa.py                Live FHFA HPI pulls
  fetch_zillow.py              Live Zillow ZORI/ZHVI bulk CSV pulls
  fetch_fred.py                 Live FRED series pulls
  subareas.py                  Sub-metro submarket ring generator (Urban Core / Inner Suburbs / Outer Suburbs / Exurban Fringe)
  build_dataset.py             Orchestrator: live-first, synthetic-fallback, writes data/metro_dataset.csv
data/metro_dataset.csv        Bundled dataset (50 metros) shipped with the app
tests/test_scoring.py         Unit tests for scoring math and finance calculator
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
# or attempt a live pull first, falling back to synthetic per-field:
ENABLE_LIVE_FETCH=1 python -m pipeline.build_dataset

streamlit run app.py
```

Then open the URL Streamlit prints (defaults to http://localhost:8501).

**Note on the maps**: both the national map and the per-metro state map
render state boundaries from an **offline** shapefile (`cb_2016_us_state_500k`,
bundled by the `plotly-geo` PyPI package) via `pipeline/geo_shapes.py`, not
from Plotly's default `scope="usa"` geo trace. That default fetches basemap
shapes from Plotly's public CDN (`cdn.plot.ly`) at render time, which failed
outright in this project's restricted-egress dev sandbox and would fail the
same way for any viewer whose network blocks that CDN (a locked-down
corporate proxy, for instance). Building the state polygons from local
shapefile data instead removes that dependency entirely -- neither map
needs any network access to render. See `pipeline/geo_shapes.py` for how
the shapefile is read and simplified.

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

## MVP scope (per charter)

**In:** top 20+ U.S. metros; Shortage, Feasibility, Opportunity scores;
ranked table and map; per-metro score breakdown; α/β and AMI-tier
configuration sliders; buy-down calculator; scheduled batch data refresh.
The final product covers all top 50 U.S. metros (this app defaults to 50,
with a toggle back to 20).

**Deferred:** sub-metro/parcel-level siting; licensed CoStar/RCA integration;
live (real-time) data refresh; full underwriting outputs (IRR, debt sizing);
actual loan origination workflow; coverage beyond top 50 metros; developer
user accounts for personalization.

## Disclaimer

This tool is a screening aid for illustrative and educational purposes. It is
not investment, financial, or legal advice, and the buy-down calculator is
not a loan product or offer of credit. Feasibility-side inputs (land cost,
construction cost, cap rate, operating expenses, vacancy/collection loss, and
permit velocity) are synthetic estimates, not observed market data — always
validate with a full local pro forma before making a development decision.
