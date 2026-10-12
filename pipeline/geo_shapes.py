"""
Fully offline US state and county boundary geometry, so the app's maps
never depend on fetching basemap shapes from a CDN at render time
(Plotly's `scope="usa"` geo traces fetch topojson from `cdn.plot.ly`,
which fails identically to Census/Zillow/FHFA in network-restricted
environments -- see README), and so the sub-metro ring membership in the
Metro Breakdown tab lists real county names rather than guessing them.

Source: the `plotly-geo` PyPI package, which bundles two Census
cartographic boundary shapefiles (`cb_2016_us_state_500k` and
`cb_2016_us_county_500k`, both 1:500,000 scale) as local package data --
no network access needed to read either.
"""

from __future__ import annotations

import os
from functools import lru_cache

import _plotly_geo
import numpy as np
import pandas as pd
import shapefile

_PACKAGE_DATA_DIR = os.path.join(os.path.dirname(_plotly_geo.__file__), "package_data")
_STATE_SHAPEFILE = os.path.join(_PACKAGE_DATA_DIR, "cb_2016_us_state_500k")
_COUNTY_SHAPEFILE = os.path.join(_PACKAGE_DATA_DIR, "cb_2016_us_county_500k")
_EARTH_RADIUS_MILES = 3958.8


def _shape_to_rings(shp) -> list[list[tuple[float, float]]]:
    """Split a pyshp Polygon shape into its constituent rings (lon, lat)."""
    parts = list(shp.parts) + [len(shp.points)]
    return [shp.points[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]


@lru_cache(maxsize=1)
def _load_states() -> dict[str, list[list[tuple[float, float]]]]:
    """Postal code -> list of rings (each a list of (lon, lat) tuples)."""
    sf = shapefile.Reader(_STATE_SHAPEFILE)
    out: dict[str, list[list[tuple[float, float]]]] = {}
    for sr in sf.iterShapeRecords():
        postal = sr.record["STUSPS"]
        out.setdefault(postal, [])
        out[postal].extend(_shape_to_rings(sr.shape))
    return out


def state_rings(postal_code: str, min_points: int = 8) -> list[list[tuple[float, float]]]:
    """Rings (lon, lat) for one state, e.g. state_rings("CA").

    Rings with fewer than `min_points` vertices (tiny offshore slivers at
    this shapefile's resolution) are dropped.
    """
    return [r for r in _load_states().get(postal_code.upper(), []) if len(r) >= min_points]


# territories excluded from the stylized national map (outside CONUS, and
# none of the top-50 metros the app ranks fall in them or in AK/HI)
_NATIONAL_MAP_EXCLUDE = {"AS", "GU", "MP", "PR", "VI", "AK", "HI"}


@lru_cache(maxsize=1)
def national_background_rings(min_points: int = 50) -> list[list[tuple[float, float]]]:
    """Simplified CONUS state outlines for the app's national map background.

    Filters out territories/AK/HI (off the CONUS extent this map is
    cropped to) and rings below `min_points` vertices (small offshore
    islands/slivers that are imperceptible at this map's zoom level) to
    keep the trace count low -- unfiltered, the full shapefile has 1,400+
    disjoint rings (Alaska alone contributes nearly 600 for its islands).
    """
    rings = []
    for postal, state_ring_list in _load_states().items():
        if postal in _NATIONAL_MAP_EXCLUDE:
            continue
        rings.extend(r for r in state_ring_list if len(r) >= min_points)
    return rings


@lru_cache(maxsize=1)
def _statefp_to_postal() -> dict[str, str]:
    """Census state FIPS code -> 2-letter postal abbreviation."""
    sf = shapefile.Reader(_STATE_SHAPEFILE)
    return {r["STATEFP"]: r["STUSPS"] for r in sf.records()}


@lru_cache(maxsize=1)
def county_centroids() -> pd.DataFrame:
    """Every U.S. county/county-equivalent: name, state, and an approximate center point.

    "Centroid" here is the bounding-box midpoint of each county's shape,
    not a true area-weighted geometric centroid (that would need a
    geometry library like shapely, which this project avoids to keep the
    dependency footprint small). For the reasonably compact counties
    found near most metros this is a fine approximation for "which ring
    is this county roughly in"; it can be noticeably off for a handful of
    very large or oddly-shaped counties, mostly in the rural West -- a
    documented limitation, not a silent one (surfaced in the app's ring
    methodology note).
    """
    sf = shapefile.Reader(_COUNTY_SHAPEFILE)
    fp_to_postal = _statefp_to_postal()
    rows = []
    for sr in sf.iterShapeRecords():
        postal = fp_to_postal.get(sr.record["STATEFP"])
        if postal is None:
            continue
        xmin, ymin, xmax, ymax = sr.shape.bbox
        rows.append(
            {
                "county": sr.record["NAME"],
                "state": postal,
                "lon": (xmin + xmax) / 2,
                "lat": (ymin + ymax) / 2,
            }
        )
    return pd.DataFrame(rows)


def _haversine_miles(lat1, lon1, lat2, lon2):
    lat1r, lon1r, lat2r, lon2r = (np.radians(v) for v in (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2r - lat1r, lon2r - lon1r
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2) ** 2
    return _EARTH_RADIUS_MILES * 2 * np.arcsin(np.sqrt(a))


def counties_by_ring(
    center_lat: float, center_lon: float, ring_bounds: dict[str, tuple[float, float]]
) -> dict[str, list[str]]:
    """Real county names whose approximate center falls in each ring's radius band.

    `ring_bounds` maps tier name -> (inner_miles, outer_miles), e.g. from
    pipeline.subareas.ring_bounds_miles(). Distance is true great-circle
    (haversine) distance from (center_lat, center_lon), not the
    degree-based approximation used for the schematic ring circles drawn
    on the map (see pipeline/subareas.ring_circle_points) -- this listing
    is meant to be a real, checkable answer, not just a visual aid.
    """
    df = county_centroids().copy()
    df["dist_mi"] = _haversine_miles(center_lat, center_lon, df["lat"].to_numpy(), df["lon"].to_numpy())
    out: dict[str, list[str]] = {}
    for tier, (lo, hi) in ring_bounds.items():
        sel = df[(df["dist_mi"] >= lo) & (df["dist_mi"] < hi)]
        out[tier] = sorted(f"{r.county}, {r.state}" for r in sel.itertuples())
    return out
