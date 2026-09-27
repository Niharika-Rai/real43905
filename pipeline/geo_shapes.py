"""
Fully offline US state boundary geometry, so the app's maps never depend on
fetching basemap shapes from a CDN at render time (Plotly's `scope="usa"`
geo traces fetch topojson from `cdn.plot.ly`, which fails identically to
Census/Zillow/FHFA in network-restricted environments -- see README).

Source: the `plotly-geo` PyPI package, which bundles a Census cartographic
boundary shapefile (`cb_2016_us_state_500k`, 1:500,000 scale) as local
package data -- no network access needed to read it.
"""

from __future__ import annotations

import os
from functools import lru_cache

import _plotly_geo
import shapefile

_PACKAGE_DATA_DIR = os.path.join(os.path.dirname(_plotly_geo.__file__), "package_data")
_STATE_SHAPEFILE = os.path.join(_PACKAGE_DATA_DIR, "cb_2016_us_state_500k")


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
