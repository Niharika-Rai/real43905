"""
Real anchor values for median home price and median household income by
metro -- these are the two inputs behind each metro's Price-to-Income
Ratio, so getting them right matters more than any other synthetic field
in this app.

Provenance: these are **published figures** (grounded in Census ACS
5-Year home-value and household-income statistics, vintage roughly
2022-2023), based on general knowledge rather than a live API pull from
this session -- this sandbox's network egress is restricted the same way
for Census as it is for every other live source (see README). They are
NOT modeled/estimated the way feasibility-side fields (land cost, cap
rate, etc.) are -- there is no free public source for those, which is why
those fields are synthetic. Home price and household income, by contrast,
ARE public, published numbers; these values just weren't fetched live
this run. The app's Data Sources tab labels this distinction explicitly
as "published" vs. "synthetic" (see pipeline/build_dataset.py).

Treat these as directionally accurate and reasonably close, not
penny-precise -- they have not been individually verified against the
current ACS release. Replace with a live pull (`ENABLE_LIVE_FETCH=1
python -m pipeline.build_dataset`, run somewhere with network access) for
production use; see pipeline/fetch_census.py.

Values are in whole dollars.
"""

from __future__ import annotations

# cbsa -> (median_home_price_usd, median_household_income_usd)
ANCHORS: dict[str, tuple[int, int]] = {
    # ---- original top 50 ----
    "35620": (650_000, 92_000),   # New York
    "31080": (880_000, 86_000),   # Los Angeles
    "16980": (310_000, 78_000),   # Chicago
    "19100": (370_000, 80_000),   # Dallas-Fort Worth
    "26420": (310_000, 74_000),   # Houston
    "47900": (570_000, 115_000),  # Washington, DC
    "33100": (480_000, 68_000),   # Miami
    "12060": (370_000, 78_000),   # Atlanta
    "37980": (320_000, 82_000),   # Philadelphia
    "38060": (430_000, 74_000),   # Phoenix
    "14460": (650_000, 105_000),  # Boston
    "40140": (520_000, 78_000),   # Riverside
    "41860": (1_100_000, 130_000),  # San Francisco
    "19820": (230_000, 65_000),   # Detroit
    "42660": (650_000, 105_000),  # Seattle
    "33460": (350_000, 90_000),   # Minneapolis
    "45300": (370_000, 66_000),   # Tampa
    "41740": (850_000, 92_000),   # San Diego
    "19740": (550_000, 92_000),   # Denver
    "12580": (330_000, 90_000),   # Baltimore
    "41180": (230_000, 70_000),   # St. Louis
    "36740": (380_000, 68_000),   # Orlando
    "16740": (380_000, 76_000),   # Charlotte
    "41700": (290_000, 66_000),   # San Antonio
    "38900": (530_000, 84_000),   # Portland
    "40900": (530_000, 84_000),   # Sacramento
    "38300": (220_000, 68_000),   # Pittsburgh
    "12420": (450_000, 88_000),   # Austin
    "29820": (410_000, 68_000),   # Las Vegas
    "17140": (250_000, 70_000),   # Cincinnati
    "28140": (280_000, 72_000),   # Kansas City
    "18140": (290_000, 72_000),   # Columbus
    "26900": (240_000, 68_000),   # Indianapolis
    "17460": (210_000, 62_000),   # Cleveland
    "41940": (1_400_000, 155_000),  # San Jose
    "34980": (430_000, 76_000),   # Nashville
    "47260": (300_000, 72_000),   # Virginia Beach
    "39300": (420_000, 82_000),   # Providence
    "33340": (280_000, 68_000),   # Milwaukee
    "27260": (330_000, 68_000),   # Jacksonville
    "36420": (230_000, 62_000),   # Oklahoma City
    "39580": (410_000, 82_000),   # Raleigh
    "32820": (220_000, 58_000),   # Memphis
    "40060": (330_000, 78_000),   # Richmond
    "31140": (240_000, 64_000),   # Louisville
    "35380": (250_000, 55_000),   # New Orleans
    "41620": (530_000, 86_000),   # Salt Lake City
    "25540": (280_000, 82_000),   # Hartford
    "15380": (220_000, 62_000),   # Buffalo
    "13820": (210_000, 58_000),   # Birmingham
    # ---- next ~100 (ranks ~51-150) ----
    "35300": (290_000, 78_000),   # New Haven
    "14860": (650_000, 110_000),  # Bridgeport-Stamford-Norwalk
    "23420": (390_000, 64_000),   # Fresno
    "46060": (330_000, 60_000),   # Tucson
    "24340": (320_000, 68_000),   # Grand Rapids
    "46140": (220_000, 58_000),   # Tulsa
    "49340": (420_000, 85_000),   # Worcester
    "36540": (270_000, 70_000),   # Omaha
    "10740": (320_000, 62_000),   # Albuquerque
    "12540": (350_000, 66_000),   # Bakersfield
    "10580": (300_000, 78_000),   # Albany
    "28940": (320_000, 62_000),   # Knoxville
    "21340": (210_000, 54_000),   # El Paso
    "10900": (300_000, 72_000),   # Allentown
    "12940": (240_000, 58_000),   # Baton Rouge
    "35840": (430_000, 66_000),   # North Port-Sarasota
    "32580": (160_000, 46_000),   # McAllen
    "17900": (270_000, 62_000),   # Columbia, SC
    "24860": (310_000, 64_000),   # Greenville, SC
    "29460": (300_000, 58_000),   # Lakeland
    "19380": (200_000, 60_000),   # Dayton
    "15980": (370_000, 62_000),   # Cape Coral-Fort Myers
    "44700": (500_000, 72_000),   # Stockton
    "24660": (270_000, 58_000),   # Greensboro
    "14260": (460_000, 72_000),   # Boise City
    "30780": (220_000, 58_000),   # Little Rock
    "17820": (460_000, 78_000),   # Colorado Springs
    "39340": (470_000, 82_000),   # Provo-Orem
    "19780": (260_000, 72_000),   # Des Moines
    "36260": (440_000, 78_000),   # Ogden-Clearfield
    "31540": (370_000, 78_000),   # Madison
    "10420": (180_000, 58_000),   # Akron
    "44140": (300_000, 68_000),   # Springfield, MA
    "19660": (320_000, 58_000),   # Deltona-Daytona Beach
    "20500": (380_000, 72_000),   # Durham-Chapel Hill
    "39100": (400_000, 88_000),   # Poughkeepsie-Newburgh
    "49180": (240_000, 56_000),   # Winston-Salem
    "45780": (160_000, 54_000),   # Toledo
    "48620": (210_000, 58_000),   # Wichita
    "45060": (200_000, 62_000),   # Syracuse
    "27140": (190_000, 52_000),   # Jackson, MS
    "12260": (230_000, 56_000),   # Augusta
    "37340": (330_000, 62_000),   # Palm Bay-Melbourne
    "44060": (390_000, 64_000),   # Spokane
    "16860": (280_000, 56_000),   # Chattanooga
    "25420": (260_000, 68_000),   # Harrisburg
    "22220": (310_000, 62_000),   # Fayetteville-Springdale, AR
    "34820": (300_000, 52_000),   # Myrtle Beach
    "29540": (280_000, 68_000),   # Lancaster, PA
    "38860": (440_000, 72_000),   # Portland, ME
    "29620": (220_000, 58_000),   # Lansing
    "30460": (280_000, 62_000),   # Lexington
    "22180": (220_000, 56_000),   # Fayetteville, NC
    "49660": (130_000, 50_000),   # Youngstown
    "47300": (340_000, 58_000),   # Visalia
    "11700": (420_000, 58_000),   # Asheville
    "39900": (500_000, 70_000),   # Reno
    "44180": (210_000, 52_000),   # Springfield, MO
    "26620": (290_000, 68_000),   # Huntsville
    "37860": (280_000, 56_000),   # Pensacola
    "28660": (230_000, 58_000),   # Killeen-Temple
    "29180": (220_000, 56_000),   # Lafayette, LA
    "42340": (320_000, 56_000),   # Savannah
    "23060": (210_000, 58_000),   # Fort Wayne
    "18580": (220_000, 56_000),   # Corpus Christi
    "37900": (160_000, 58_000),   # Peoria
    "43340": (180_000, 50_000),   # Shreveport-Bossier City
    "45940": (400_000, 90_000),   # Trenton-Princeton
    "33860": (190_000, 52_000),   # Montgomery
    "31700": (430_000, 82_000),   # Manchester-Nashua
    "49620": (260_000, 68_000),   # York, PA
    "33660": (190_000, 52_000),   # Mobile
    "41420": (380_000, 64_000),   # Salem, OR
    "43780": (180_000, 54_000),   # South Bend
    "40420": (170_000, 56_000),   # Rockford
    "26580": (140_000, 46_000),   # Huntington-Ashland
    "17300": (240_000, 56_000),   # Clarksville
    "42220": (750_000, 90_000),   # Santa Rosa-Petaluma
    "46700": (530_000, 84_000),   # Vallejo
    "37100": (780_000, 92_000),   # Oxnard-Thousand Oaks-Ventura
    "41500": (700_000, 72_000),   # Salinas
    "33700": (440_000, 66_000),   # Modesto
    "42200": (850_000, 76_000),   # Santa Maria-Santa Barbara
    "38940": (350_000, 62_000),   # Port St. Lucie
    "36100": (260_000, 50_000),   # Ocala
    "34940": (550_000, 74_000),   # Naples-Marco Island
    "45220": (260_000, 56_000),   # Tallahassee
    "23540": (280_000, 50_000),   # Gainesville, FL
    "25860": (200_000, 50_000),   # Hickory-Lenoir-Morganton
    "48900": (350_000, 58_000),   # Wilmington, NC
    "24580": (250_000, 66_000),   # Green Bay
    "21660": (420_000, 62_000),   # Eugene-Springfield
    "15940": (170_000, 58_000),   # Canton-Massillon
    "17980": (190_000, 52_000),   # Columbus, GA
    "47380": (230_000, 54_000),   # Waco
    "17780": (260_000, 56_000),   # College Station-Bryan
    "13140": (170_000, 54_000),   # Beaumont-Port Arthur
    "15180": (140_000, 42_000),   # Brownsville-Harlingen
    "11100": (190_000, 54_000),   # Amarillo
    "31180": (190_000, 54_000),   # Lubbock
}
