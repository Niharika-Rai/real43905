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
    """Every U.S. county/county-equivalent: name, state, bbox midpoint, and bbox extent.

    `lat`/`lon` are the bounding-box midpoint of each county's shape, not a
    true area-weighted geometric centroid (that would need a geometry
    library like shapely, which this project avoids to keep the dependency
    footprint small). `counties_by_ring` below uses the fuller bbox extent
    (`xmin`/`ymin`/`xmax`/`ymax`), not just this midpoint, to bucket a
    county by its *nearest* edge to the metro's point rather than its
    center -- the midpoint alone can be noticeably off for a large or
    elongated county, placing it in a farther ring than any part of it
    actually reaches. That nearest-edge distance is still only an
    approximation of true distance-to-boundary (a rectangle standing in
    for the county's real, irregular shape), not a geometric centroid --
    a documented limitation, not a silent one (surfaced in the app's ring
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
                "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
            }
        )
    return pd.DataFrame(rows)


def _haversine_miles(lat1, lon1, lat2, lon2):
    lat1r, lon1r, lat2r, lon2r = (np.radians(v) for v in (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2r - lat1r, lon2r - lon1r
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2) ** 2
    return _EARTH_RADIUS_MILES * 2 * np.arcsin(np.sqrt(a))


@lru_cache(maxsize=1)
def _county_geometries() -> list[dict]:
    """Every county's name, state, bounding box, and full ring geometry.

    Unlike `county_centroids()` (bbox-midpoint only, used for the coarser
    ring-distance bucketing below), this keeps the actual polygon rings so
    `_home_county()` can test true point-in-polygon containment -- the
    bbox-midpoint approximation is specifically unreliable for large or
    oddly-shaped counties, which is exactly when a metro's own "home"
    county would otherwise wrongly drop out of the Urban Core ring.
    """
    sf = shapefile.Reader(_COUNTY_SHAPEFILE)
    fp_to_postal = _statefp_to_postal()
    out = []
    for sr in sf.iterShapeRecords():
        postal = fp_to_postal.get(sr.record["STATEFP"])
        if postal is None:
            continue
        out.append(
            {
                "county": sr.record["NAME"],
                "state": postal,
                "bbox": sr.shape.bbox,  # (xmin, ymin, xmax, ymax)
                "rings": _shape_to_rings(sr.shape),
            }
        )
    return out


def _point_in_ring(lon: float, lat: float, ring: list[tuple[float, float]]) -> bool:
    """Standard even-odd ray-casting point-in-polygon test for one ring."""
    inside = False
    n = len(ring)
    x1, y1 = ring[0]
    for i in range(1, n + 1):
        x2, y2 = ring[i % n]
        if ((y1 > lat) != (y2 > lat)) and (lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1):
            inside = not inside
        x1, y1 = x2, y2
    return inside


def _home_county(lat: float, lon: float) -> str | None:
    """The one county whose boundary actually contains (lat, lon), if any.

    Checked via true point-in-polygon, not distance to an approximate
    center -- a metro's coordinate is, by construction, inside its own
    county, regardless of how large or irregularly shaped that county is
    or where its bounding-box midpoint happens to fall. Bounding boxes
    first narrow the ~3,233 counties down to the handful whose box could
    possibly contain the point (cheap), before the exact ring test (only
    run on those few candidates).
    """
    candidates = [
        c for c in _county_geometries()
        if c["bbox"][0] <= lon <= c["bbox"][2] and c["bbox"][1] <= lat <= c["bbox"][3]
    ]
    for c in candidates:
        if any(_point_in_ring(lon, lat, ring) for ring in c["rings"]):
            return f"{c['county']}, {c['state']}"
    return None


def counties_by_ring(
    center_lat: float, center_lon: float, ring_bounds: dict[str, tuple[float, float]]
) -> dict[str, list[str]]:
    """Real county names whose approximate extent falls in each ring's radius band.

    `ring_bounds` maps tier name -> (inner_miles, outer_miles), e.g. from
    pipeline.subareas.ring_bounds_miles(). Distance is true great-circle
    (haversine) distance from (center_lat, center_lon), not the
    degree-based approximation used for the schematic ring circles drawn
    on the map (see pipeline/subareas.ring_circle_points) -- this listing
    is meant to be a real, checkable answer, not just a visual aid.

    Each county is bucketed by its distance from (center_lat, center_lon) to
    the *nearest point on that county's bounding box* -- 0 for a county
    whose box contains the metro's point, otherwise the distance to the
    box's near edge/corner -- rather than to the box's midpoint. A bbox
    midpoint can sit far from a metro that's actually adjacent to (or just
    inside) a large or elongated county; nearest-edge distance tracks each
    county's true extent much more closely while still needing no new
    geometry dependency. On top of that, the one county whose boundary
    *actually contains* the metro's own point (almost always its "home"
    county -- e.g. Santa Clara County for San Jose) is found via exact
    point-in-polygon (_home_county) and guaranteed a spot in the ring
    covering distance 0, even on the rare case a bbox-edge distance alone
    would disagree.
    """
    df = county_centroids().copy()
    clamped_lon = np.clip(center_lon, df["xmin"].to_numpy(), df["xmax"].to_numpy())
    clamped_lat = np.clip(center_lat, df["ymin"].to_numpy(), df["ymax"].to_numpy())
    df["dist_mi"] = _haversine_miles(center_lat, center_lon, clamped_lat, clamped_lon)
    out: dict[str, list[str]] = {}
    for tier, (lo, hi) in ring_bounds.items():
        sel = df[(df["dist_mi"] >= lo) & (df["dist_mi"] < hi)]
        out[tier] = sorted({f"{r.county}, {r.state}" for r in sel.itertuples()})

    home = _home_county(center_lat, center_lon)
    if home is not None:
        zero_tier = next((tier for tier, (lo, _hi) in ring_bounds.items() if lo == 0), None)
        if zero_tier is not None:
            # the home county belongs in the zero-distance ring alone -- drop
            # it from any other ring its (less reliable) centroid distance
            # placed it in, so it isn't shown twice at two different rings
            for tier in out:
                if tier != zero_tier and home in out[tier]:
                    out[tier] = [c for c in out[tier] if c != home]
            out[zero_tier] = sorted(set(out[zero_tier]) | {home})
    return out
