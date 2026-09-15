"""
Reference table of the top 50 U.S. metropolitan statistical areas (by population).

This is the fixed universe of metros the app ranks. CBSA codes are used to
query the Census Bureau APIs (ACS, Building Permits Survey, PEP) and FHFA's
MSA-level HPI file. Population figures are approximate mid-2020s estimates
used only for ranking/display context, not as a scoring input.

NOTE: A handful of CBSA codes below should be double-checked against the
Census Bureau's current MSA delineation file before relying on live API
pulls in production -- a wrong code simply yields no rows for that metro,
and the pipeline (see pipeline/build_dataset.py) falls back to synthetic
data for that metro rather than failing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Metro:
    cbsa: str          # 5-digit Core-Based Statistical Area code
    name: str           # official CBSA name
    short_name: str     # short display name, "City, ST"
    principal_state: str
    lat: float
    lon: float
    population: int     # approx., for display/ranking context only
    tier: str           # stratification tag used by the synthetic generator


# tiers used to give the synthetic generator realistic, internally-consistent
# regional patterns (coastal superstar metros vs. sunbelt growth metros vs.
# midwest/legacy metros vs. mixed northeast/mid-atlantic metros)
SUPERSTAR_COASTAL = "superstar_coastal"
SUNBELT_GROWTH = "sunbelt_growth"
MIDWEST_LEGACY = "midwest_legacy"
MIXED_NORTHEAST = "mixed_northeast_midatlantic"

TOP_50_METROS: list[Metro] = [
    Metro("35620", "New York-Newark-Jersey City, NY-NJ", "New York, NY", "NY", 40.7128, -74.0060, 19_600_000, SUPERSTAR_COASTAL),
    Metro("31080", "Los Angeles-Long Beach-Anaheim, CA", "Los Angeles, CA", "CA", 34.0522, -118.2437, 12_800_000, SUPERSTAR_COASTAL),
    Metro("16980", "Chicago-Naperville-Elgin, IL-IN-WI", "Chicago, IL", "IL", 41.8781, -87.6298, 9_300_000, MIDWEST_LEGACY),
    Metro("19100", "Dallas-Fort Worth-Arlington, TX", "Dallas-Fort Worth, TX", "TX", 32.7767, -96.7970, 8_100_000, SUNBELT_GROWTH),
    Metro("26420", "Houston-The Woodlands-Sugar Land, TX", "Houston, TX", "TX", 29.7604, -95.3698, 7_500_000, SUNBELT_GROWTH),
    Metro("47900", "Washington-Arlington-Alexandria, DC-VA-MD-WV", "Washington, DC", "DC", 38.9072, -77.0369, 6_400_000, SUPERSTAR_COASTAL),
    Metro("33100", "Miami-Fort Lauderdale-Pompano Beach, FL", "Miami, FL", "FL", 25.7617, -80.1918, 6_500_000, SUNBELT_GROWTH),
    Metro("12060", "Atlanta-Sandy Springs-Alpharetta, GA", "Atlanta, GA", "GA", 33.7490, -84.3880, 6_300_000, SUNBELT_GROWTH),
    Metro("37980", "Philadelphia-Camden-Wilmington, PA-NJ-DE-MD", "Philadelphia, PA", "PA", 39.9526, -75.1652, 6_200_000, MIXED_NORTHEAST),
    Metro("38060", "Phoenix-Mesa-Chandler, AZ", "Phoenix, AZ", "AZ", 33.4484, -112.0740, 5_000_000, SUNBELT_GROWTH),
    Metro("14460", "Boston-Cambridge-Newton, MA-NH", "Boston, MA", "MA", 42.3601, -71.0589, 4_900_000, SUPERSTAR_COASTAL),
    Metro("40140", "Riverside-San Bernardino-Ontario, CA", "Riverside, CA", "CA", 33.9533, -117.3962, 4_650_000, SUNBELT_GROWTH),
    Metro("41860", "San Francisco-Oakland-Berkeley, CA", "San Francisco, CA", "CA", 37.7749, -122.4194, 4_600_000, SUPERSTAR_COASTAL),
    Metro("19820", "Detroit-Warren-Dearborn, MI", "Detroit, MI", "MI", 42.3314, -83.0458, 4_300_000, MIDWEST_LEGACY),
    Metro("42660", "Seattle-Tacoma-Bellevue, WA", "Seattle, WA", "WA", 47.6062, -122.3321, 4_000_000, SUPERSTAR_COASTAL),
    Metro("33460", "Minneapolis-St. Paul-Bloomington, MN-WI", "Minneapolis, MN", "MN", 44.9778, -93.2650, 3_700_000, MIDWEST_LEGACY),
    Metro("45300", "Tampa-St. Petersburg-Clearwater, FL", "Tampa, FL", "FL", 27.9506, -82.4572, 3_300_000, SUNBELT_GROWTH),
    Metro("41740", "San Diego-Chula Vista-Carlsbad, CA", "San Diego, CA", "CA", 32.7157, -117.1611, 3_300_000, SUPERSTAR_COASTAL),
    Metro("19740", "Denver-Aurora-Lakewood, CO", "Denver, CO", "CO", 39.7392, -104.9903, 3_000_000, SUNBELT_GROWTH),
    Metro("12580", "Baltimore-Columbia-Towson, MD", "Baltimore, MD", "MD", 39.2904, -76.6122, 2_840_000, MIXED_NORTHEAST),
    Metro("41180", "St. Louis, MO-IL", "St. Louis, MO", "MO", 38.6270, -90.1994, 2_800_000, MIDWEST_LEGACY),
    Metro("36740", "Orlando-Kissimmee-Sanford, FL", "Orlando, FL", "FL", 28.5383, -81.3792, 2_700_000, SUNBELT_GROWTH),
    Metro("16740", "Charlotte-Concord-Gastonia, NC-SC", "Charlotte, NC", "NC", 35.2271, -80.8431, 2_800_000, SUNBELT_GROWTH),
    Metro("41700", "San Antonio-New Braunfels, TX", "San Antonio, TX", "TX", 29.4241, -98.4936, 2_700_000, SUNBELT_GROWTH),
    Metro("38900", "Portland-Vancouver-Hillsboro, OR-WA", "Portland, OR", "OR", 45.5152, -122.6784, 2_500_000, SUPERSTAR_COASTAL),
    Metro("40900", "Sacramento-Roseville-Folsom, CA", "Sacramento, CA", "CA", 39.7392, -121.4419, 2_400_000, SUNBELT_GROWTH),
    Metro("38300", "Pittsburgh, PA", "Pittsburgh, PA", "PA", 40.4406, -79.9959, 2_300_000, MIDWEST_LEGACY),
    Metro("12420", "Austin-Round Rock-Georgetown, TX", "Austin, TX", "TX", 30.2672, -97.7431, 2_400_000, SUNBELT_GROWTH),
    Metro("29820", "Las Vegas-Henderson-Paradise, NV", "Las Vegas, NV", "NV", 36.1699, -115.1398, 2_300_000, SUNBELT_GROWTH),
    Metro("17140", "Cincinnati, OH-KY-IN", "Cincinnati, OH", "OH", 39.1031, -84.5120, 2_200_000, MIDWEST_LEGACY),
    Metro("28140", "Kansas City, MO-KS", "Kansas City, MO", "MO", 39.0997, -94.5786, 2_200_000, MIDWEST_LEGACY),
    Metro("18140", "Columbus, OH", "Columbus, OH", "OH", 39.9612, -82.9988, 2_100_000, MIDWEST_LEGACY),
    Metro("26900", "Indianapolis-Carmel-Anderson, IN", "Indianapolis, IN", "IN", 39.7684, -86.1581, 2_100_000, MIDWEST_LEGACY),
    Metro("17460", "Cleveland-Elyria, OH", "Cleveland, OH", "OH", 41.4993, -81.6944, 2_050_000, MIDWEST_LEGACY),
    Metro("41940", "San Jose-Sunnyvale-Santa Clara, CA", "San Jose, CA", "CA", 37.3382, -121.8863, 2_000_000, SUPERSTAR_COASTAL),
    Metro("34980", "Nashville-Davidson--Murfreesboro--Franklin, TN", "Nashville, TN", "TN", 36.1627, -86.7816, 2_100_000, SUNBELT_GROWTH),
    Metro("47260", "Virginia Beach-Norfolk-Newport News, VA-NC", "Virginia Beach, VA", "VA", 36.8529, -75.9780, 1_800_000, MIXED_NORTHEAST),
    Metro("39300", "Providence-Warwick, RI-MA", "Providence, RI", "RI", 41.8240, -71.4128, 1_680_000, MIXED_NORTHEAST),
    Metro("33340", "Milwaukee-Waukesha, WI", "Milwaukee, WI", "WI", 43.0389, -87.9065, 1_580_000, MIDWEST_LEGACY),
    Metro("27260", "Jacksonville, FL", "Jacksonville, FL", "FL", 30.3322, -81.6557, 1_700_000, SUNBELT_GROWTH),
    Metro("36420", "Oklahoma City, OK", "Oklahoma City, OK", "OK", 35.4676, -97.5164, 1_470_000, SUNBELT_GROWTH),
    Metro("39580", "Raleigh-Cary, NC", "Raleigh, NC", "NC", 35.7796, -78.6382, 1_510_000, SUNBELT_GROWTH),
    Metro("32820", "Memphis, TN-MS-AR", "Memphis, TN", "TN", 35.1495, -90.0490, 1_340_000, MIDWEST_LEGACY),
    Metro("40060", "Richmond, VA", "Richmond, VA", "VA", 37.5407, -77.4360, 1_350_000, MIXED_NORTHEAST),
    Metro("31140", "Louisville/Jefferson County, KY-IN", "Louisville, KY", "KY", 38.2527, -85.7585, 1_370_000, MIDWEST_LEGACY),
    Metro("35380", "New Orleans-Metairie, LA", "New Orleans, LA", "LA", 29.9511, -90.0715, 1_270_000, MIXED_NORTHEAST),
    Metro("41620", "Salt Lake City, UT", "Salt Lake City, UT", "UT", 40.7608, -111.8910, 1_270_000, SUNBELT_GROWTH),
    Metro("25540", "Hartford-East Hartford-Middletown, CT", "Hartford, CT", "CT", 41.7658, -72.6734, 1_200_000, MIXED_NORTHEAST),
    Metro("15380", "Buffalo-Cheektowaga, NY", "Buffalo, NY", "NY", 42.8864, -78.8784, 1_160_000, MIDWEST_LEGACY),
    Metro("13820", "Birmingham-Hoover, AL", "Birmingham, AL", "AL", 33.5207, -86.8025, 1_190_000, MIDWEST_LEGACY),
]

assert len(TOP_50_METROS) == 50
assert len({m.cbsa for m in TOP_50_METROS}) == 50

TOP_20_CBSAS = {m.cbsa for m in TOP_50_METROS[:20]}


def metros_frame():
    """Return the metro reference table as a pandas DataFrame."""
    import pandas as pd

    return pd.DataFrame(
        {
            "cbsa": m.cbsa,
            "metro": m.short_name,
            "cbsa_name": m.name,
            "state": m.principal_state,
            "lat": m.lat,
            "lon": m.lon,
            "population": m.population,
            "tier": m.tier,
        }
        for m in TOP_50_METROS
    )
