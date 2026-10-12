"""
Reference table of U.S. metropolitan statistical areas the app ranks (top
~150 by population). CBSA codes are used to query the Census Bureau APIs
(ACS, Building Permits Survey, PEP) and FHFA's MSA-level HPI file.
Population figures are approximate mid-2020s estimates used only for
ranking/display context, not as a scoring input.

NOTE on CBSA code confidence: codes for the largest ~50 metros are
well-established and have been used successfully elsewhere in this
project. Codes for the remaining ~100 metros (added to broaden coverage
beyond the original top 50) are best-effort from general knowledge and
have NOT been individually verified against the Census Bureau's current
MSA delineation file -- a wrong code simply yields no rows for that metro
when live-fetching, and the pipeline (see pipeline/build_dataset.py) falls
back to synthetic/published data for that metro rather than failing. CBSA
codes are never shown in the app's UI; they are only an internal join key
for the live-data pipeline, so an incorrect code degrades silently rather
than displaying wrong information. Verify against the Census MSA
delineation file before depending on live fetches for a specific metro
outside the original top 50.

Alaska and Hawaii metros are intentionally excluded: the app's maps are
cropped to the continental U.S. (see pipeline/geo_shapes.py), so a metro
there would rank and score normally but never appear on either map.
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

# ---------------------------------------------------------------------------
# Original top 50 (by population)
# ---------------------------------------------------------------------------
_TOP_50 = [
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

# ---------------------------------------------------------------------------
# Next ~100 metros (ranks ~51-150), broadening coverage per user request.
# See module docstring for the CBSA-code confidence caveat.
# ---------------------------------------------------------------------------
_NEXT_100 = [
    Metro("35300", "New Haven-Milford, CT", "New Haven, CT", "CT", 41.3083, -72.9279, 860_000, MIXED_NORTHEAST),
    Metro("14860", "Bridgeport-Stamford-Norwalk, CT", "Bridgeport, CT", "CT", 41.1865, -73.1952, 960_000, SUPERSTAR_COASTAL),
    Metro("23420", "Fresno, CA", "Fresno, CA", "CA", 36.7378, -119.7871, 1_030_000, SUNBELT_GROWTH),
    Metro("46060", "Tucson, AZ", "Tucson, AZ", "AZ", 32.2226, -110.9747, 1_060_000, SUNBELT_GROWTH),
    Metro("24340", "Grand Rapids-Kentwood, MI", "Grand Rapids, MI", "MI", 42.9634, -85.6681, 1_100_000, MIDWEST_LEGACY),
    Metro("46140", "Tulsa, OK", "Tulsa, OK", "OK", 36.1540, -95.9928, 1_020_000, SUNBELT_GROWTH),
    Metro("49340", "Worcester, MA-CT", "Worcester, MA", "MA", 42.2626, -71.8023, 980_000, MIXED_NORTHEAST),
    Metro("36540", "Omaha-Council Bluffs, NE-IA", "Omaha, NE", "NE", 41.2565, -95.9345, 980_000, MIDWEST_LEGACY),
    Metro("10740", "Albuquerque, NM", "Albuquerque, NM", "NM", 35.0844, -106.6504, 920_000, SUNBELT_GROWTH),
    Metro("12540", "Bakersfield, CA", "Bakersfield, CA", "CA", 35.3733, -119.0187, 920_000, SUNBELT_GROWTH),
    Metro("10580", "Albany-Schenectady-Troy, NY", "Albany, NY", "NY", 42.6526, -73.7562, 900_000, MIDWEST_LEGACY),
    Metro("28940", "Knoxville, TN", "Knoxville, TN", "TN", 35.9606, -83.9207, 900_000, SUNBELT_GROWTH),
    Metro("21340", "El Paso, TX", "El Paso, TX", "TX", 31.7619, -106.4850, 870_000, SUNBELT_GROWTH),
    Metro("10900", "Allentown-Bethlehem-Easton, PA-NJ", "Allentown, PA", "PA", 40.6023, -75.4714, 860_000, MIXED_NORTHEAST),
    Metro("12940", "Baton Rouge, LA", "Baton Rouge, LA", "LA", 30.4515, -91.1871, 870_000, SUNBELT_GROWTH),
    Metro("35840", "North Port-Sarasota-Bradenton, FL", "North Port, FL", "FL", 27.3364, -82.5307, 880_000, SUNBELT_GROWTH),
    Metro("32580", "McAllen-Edinburg-Mission, TX", "McAllen, TX", "TX", 26.2034, -98.2300, 870_000, SUNBELT_GROWTH),
    Metro("17900", "Columbia, SC", "Columbia, SC", "SC", 34.0007, -81.0348, 860_000, SUNBELT_GROWTH),
    Metro("24860", "Greenville-Anderson, SC", "Greenville, SC", "SC", 34.8526, -82.3940, 950_000, SUNBELT_GROWTH),
    Metro("29460", "Lakeland-Winter Haven, FL", "Lakeland, FL", "FL", 28.0395, -81.9498, 820_000, SUNBELT_GROWTH),
    Metro("19380", "Dayton-Kettering, OH", "Dayton, OH", "OH", 39.7589, -84.1916, 815_000, MIDWEST_LEGACY),
    Metro("15980", "Cape Coral-Fort Myers, FL", "Cape Coral, FL", "FL", 26.6406, -81.8723, 790_000, SUNBELT_GROWTH),
    Metro("44700", "Stockton, CA", "Stockton, CA", "CA", 37.9577, -121.2908, 790_000, SUNBELT_GROWTH),
    Metro("24660", "Greensboro-High Point, NC", "Greensboro, NC", "NC", 36.0726, -79.7920, 790_000, SUNBELT_GROWTH),
    Metro("14260", "Boise City, ID", "Boise City, ID", "ID", 43.6150, -116.2023, 850_000, SUNBELT_GROWTH),
    Metro("30780", "Little Rock-North Little Rock, AR", "Little Rock, AR", "AR", 34.7465, -92.2896, 760_000, MIDWEST_LEGACY),
    Metro("17820", "Colorado Springs, CO", "Colorado Springs, CO", "CO", 38.8339, -104.8214, 770_000, SUNBELT_GROWTH),
    Metro("39340", "Provo-Orem, UT", "Provo, UT", "UT", 40.2338, -111.6585, 720_000, SUNBELT_GROWTH),
    Metro("19780", "Des Moines-West Des Moines, IA", "Des Moines, IA", "IA", 41.5868, -93.6250, 720_000, MIDWEST_LEGACY),
    Metro("36260", "Ogden-Clearfield, UT", "Ogden, UT", "UT", 41.2230, -111.9738, 720_000, SUNBELT_GROWTH),
    Metro("31540", "Madison, WI", "Madison, WI", "WI", 43.0731, -89.4012, 700_000, MIDWEST_LEGACY),
    Metro("10420", "Akron, OH", "Akron, OH", "OH", 41.0814, -81.5190, 700_000, MIDWEST_LEGACY),
    Metro("44140", "Springfield, MA", "Springfield, MA", "MA", 42.1015, -72.5898, 700_000, MIXED_NORTHEAST),
    Metro("19660", "Deltona-Daytona Beach-Ormond Beach, FL", "Deltona, FL", "FL", 29.0280, -81.0755, 700_000, SUNBELT_GROWTH),
    Metro("20500", "Durham-Chapel Hill, NC", "Durham, NC", "NC", 35.9940, -78.8986, 680_000, SUNBELT_GROWTH),
    Metro("39100", "Poughkeepsie-Newburgh-Middletown, NY", "Poughkeepsie, NY", "NY", 41.7004, -73.9210, 680_000, SUPERSTAR_COASTAL),
    Metro("49180", "Winston-Salem, NC", "Winston-Salem, NC", "NC", 36.0999, -80.2442, 690_000, SUNBELT_GROWTH),
    Metro("45780", "Toledo, OH", "Toledo, OH", "OH", 41.6528, -83.5379, 640_000, MIDWEST_LEGACY),
    Metro("48620", "Wichita, KS", "Wichita, KS", "KS", 37.6872, -97.3301, 650_000, MIDWEST_LEGACY),
    Metro("45060", "Syracuse, NY", "Syracuse, NY", "NY", 43.0481, -76.1474, 650_000, MIDWEST_LEGACY),
    Metro("27140", "Jackson, MS", "Jackson, MS", "MS", 32.2988, -90.1848, 580_000, MIDWEST_LEGACY),
    Metro("12260", "Augusta-Richmond County, GA-SC", "Augusta, GA", "GA", 33.4735, -81.9748, 620_000, SUNBELT_GROWTH),
    Metro("37340", "Palm Bay-Melbourne-Titusville, FL", "Palm Bay, FL", "FL", 28.0345, -80.6085, 630_000, SUNBELT_GROWTH),
    Metro("44060", "Spokane-Spokane Valley, WA", "Spokane, WA", "WA", 47.6588, -117.4260, 580_000, MIDWEST_LEGACY),
    Metro("16860", "Chattanooga, TN-GA", "Chattanooga, TN", "TN", 35.0456, -85.3097, 580_000, SUNBELT_GROWTH),
    Metro("25420", "Harrisburg-Carlisle, PA", "Harrisburg, PA", "PA", 40.2732, -76.8867, 590_000, MIXED_NORTHEAST),
    Metro("22220", "Fayetteville-Springdale-Rogers, AR", "Fayetteville, AR", "AR", 36.0626, -94.1574, 560_000, SUNBELT_GROWTH),
    Metro("34820", "Myrtle Beach-Conway-North Myrtle Beach, SC-NC", "Myrtle Beach, SC", "SC", 33.6891, -78.8867, 520_000, SUNBELT_GROWTH),
    Metro("29540", "Lancaster, PA", "Lancaster, PA", "PA", 40.0379, -76.3055, 550_000, MIXED_NORTHEAST),
    Metro("38860", "Portland-South Portland, ME", "Portland, ME", "ME", 43.6591, -70.2568, 550_000, MIXED_NORTHEAST),
    Metro("29620", "Lansing-East Lansing, MI", "Lansing, MI", "MI", 42.7325, -84.5555, 540_000, MIDWEST_LEGACY),
    Metro("30460", "Lexington-Fayette, KY", "Lexington, KY", "KY", 38.0406, -84.5037, 530_000, MIDWEST_LEGACY),
    Metro("22180", "Fayetteville, NC", "Fayetteville, NC", "NC", 35.0527, -78.8784, 530_000, SUNBELT_GROWTH),
    Metro("49660", "Youngstown-Warren-Boardman, OH-PA", "Youngstown, OH", "OH", 41.0998, -80.6495, 530_000, MIDWEST_LEGACY),
    Metro("47300", "Visalia, CA", "Visalia, CA", "CA", 36.3302, -119.2921, 470_000, SUNBELT_GROWTH),
    Metro("11700", "Asheville, NC", "Asheville, NC", "NC", 35.5951, -82.5515, 470_000, SUNBELT_GROWTH),
    Metro("39900", "Reno, NV", "Reno, NV", "NV", 39.5296, -119.8138, 490_000, SUNBELT_GROWTH),
    Metro("44180", "Springfield, MO", "Springfield, MO", "MO", 37.2090, -93.2923, 480_000, MIDWEST_LEGACY),
    Metro("26620", "Huntsville, AL", "Huntsville, AL", "AL", 34.7304, -86.5861, 500_000, SUNBELT_GROWTH),
    Metro("37860", "Pensacola-Ferry Pass-Brent, FL", "Pensacola, FL", "FL", 30.4213, -87.2169, 500_000, SUNBELT_GROWTH),
    Metro("28660", "Killeen-Temple, TX", "Killeen, TX", "TX", 31.1171, -97.7278, 470_000, SUNBELT_GROWTH),
    Metro("29180", "Lafayette, LA", "Lafayette, LA", "LA", 30.2241, -92.0198, 490_000, SUNBELT_GROWTH),
    Metro("42340", "Savannah, GA", "Savannah, GA", "GA", 32.0809, -81.0912, 420_000, SUNBELT_GROWTH),
    Metro("23060", "Fort Wayne, IN", "Fort Wayne, IN", "IN", 41.0793, -85.1394, 420_000, MIDWEST_LEGACY),
    Metro("18580", "Corpus Christi, TX", "Corpus Christi, TX", "TX", 27.8006, -97.3964, 420_000, SUNBELT_GROWTH),
    Metro("37900", "Peoria, IL", "Peoria, IL", "IL", 40.6936, -89.5890, 400_000, MIDWEST_LEGACY),
    Metro("43340", "Shreveport-Bossier City, LA", "Shreveport, LA", "LA", 32.5252, -93.7502, 390_000, MIDWEST_LEGACY),
    Metro("45940", "Trenton-Princeton, NJ", "Trenton, NJ", "NJ", 40.2171, -74.7429, 390_000, SUPERSTAR_COASTAL),
    Metro("33860", "Montgomery, AL", "Montgomery, AL", "AL", 32.3792, -86.3077, 380_000, MIDWEST_LEGACY),
    Metro("31700", "Manchester-Nashua, NH", "Manchester, NH", "NH", 42.9956, -71.4548, 420_000, MIXED_NORTHEAST),
    Metro("49620", "York-Hanover, PA", "York, PA", "PA", 39.9626, -76.7277, 460_000, MIXED_NORTHEAST),
    Metro("33660", "Mobile, AL", "Mobile, AL", "AL", 30.6954, -88.0399, 430_000, SUNBELT_GROWTH),
    Metro("41420", "Salem, OR", "Salem, OR", "OR", 44.9429, -123.0351, 435_000, SUNBELT_GROWTH),
    Metro("43780", "South Bend-Mishawaka, IN-MI", "South Bend, IN", "IN", 41.6764, -86.2520, 325_000, MIDWEST_LEGACY),
    Metro("40420", "Rockford, IL", "Rockford, IL", "IL", 42.2711, -89.0940, 335_000, MIDWEST_LEGACY),
    Metro("26580", "Huntington-Ashland, WV-KY-OH", "Huntington, WV", "WV", 38.4192, -82.4452, 355_000, MIDWEST_LEGACY),
    Metro("17300", "Clarksville, TN-KY", "Clarksville, TN", "TN", 36.5298, -87.3595, 320_000, SUNBELT_GROWTH),
    Metro("42220", "Santa Rosa-Petaluma, CA", "Santa Rosa, CA", "CA", 38.4404, -122.7141, 485_000, SUPERSTAR_COASTAL),
    Metro("46700", "Vallejo, CA", "Vallejo, CA", "CA", 38.1041, -122.2566, 450_000, SUPERSTAR_COASTAL),
    Metro("37100", "Oxnard-Thousand Oaks-Ventura, CA", "Oxnard, CA", "CA", 34.1975, -119.1771, 845_000, SUPERSTAR_COASTAL),
    Metro("41500", "Salinas, CA", "Salinas, CA", "CA", 36.6777, -121.6555, 435_000, SUPERSTAR_COASTAL),
    Metro("33700", "Modesto, CA", "Modesto, CA", "CA", 37.6391, -120.9969, 555_000, SUNBELT_GROWTH),
    Metro("42200", "Santa Maria-Santa Barbara, CA", "Santa Barbara, CA", "CA", 34.4208, -119.6982, 450_000, SUPERSTAR_COASTAL),
    Metro("38940", "Port St. Lucie, FL", "Port St. Lucie, FL", "FL", 27.2730, -80.3582, 500_000, SUNBELT_GROWTH),
    Metro("36100", "Ocala, FL", "Ocala, FL", "FL", 29.1872, -82.1401, 400_000, SUNBELT_GROWTH),
    Metro("34940", "Naples-Marco Island, FL", "Naples, FL", "FL", 26.1420, -81.7948, 400_000, SUNBELT_GROWTH),
    Metro("45220", "Tallahassee, FL", "Tallahassee, FL", "FL", 30.4383, -84.2807, 385_000, SUNBELT_GROWTH),
    Metro("23540", "Gainesville, FL", "Gainesville, FL", "FL", 29.6516, -82.3248, 350_000, SUNBELT_GROWTH),
    Metro("25860", "Hickory-Lenoir-Morganton, NC", "Hickory, NC", "NC", 35.7344, -81.3412, 370_000, SUNBELT_GROWTH),
    Metro("48900", "Wilmington, NC", "Wilmington, NC", "NC", 34.2257, -77.9447, 310_000, SUNBELT_GROWTH),
    Metro("24580", "Green Bay, WI", "Green Bay, WI", "WI", 44.5133, -88.0133, 325_000, MIDWEST_LEGACY),
    Metro("21660", "Eugene-Springfield, OR", "Eugene, OR", "OR", 44.0521, -123.0868, 385_000, SUPERSTAR_COASTAL),
    Metro("15940", "Canton-Massillon, OH", "Canton, OH", "OH", 40.7989, -81.3784, 400_000, MIDWEST_LEGACY),
    Metro("17980", "Columbus, GA-AL", "Columbus, GA", "GA", 32.4610, -84.9877, 320_000, SUNBELT_GROWTH),
    Metro("47380", "Waco, TX", "Waco, TX", "TX", 31.5493, -97.1467, 285_000, SUNBELT_GROWTH),
    Metro("17780", "College Station-Bryan, TX", "College Station, TX", "TX", 30.6280, -96.3344, 275_000, SUNBELT_GROWTH),
    Metro("13140", "Beaumont-Port Arthur, TX", "Beaumont, TX", "TX", 30.0802, -94.1266, 390_000, SUNBELT_GROWTH),
    Metro("15180", "Brownsville-Harlingen, TX", "Brownsville, TX", "TX", 25.9018, -97.4975, 425_000, SUNBELT_GROWTH),
    Metro("11100", "Amarillo, TX", "Amarillo, TX", "TX", 35.1991, -101.8313, 270_000, SUNBELT_GROWTH),
    Metro("31180", "Lubbock, TX", "Lubbock, TX", "TX", 33.5779, -101.8552, 325_000, SUNBELT_GROWTH),
]

ALL_METROS: list[Metro] = _TOP_50 + _NEXT_100

assert len(ALL_METROS) == 150
assert len({m.cbsa for m in ALL_METROS}) == 150, "duplicate CBSA code in metro list"


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
        for m in ALL_METROS
    )
