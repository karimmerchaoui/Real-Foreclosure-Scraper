# State & County definitions
COUNTIES_BY_STATE = {
    "CO": ["denver", "eage", "elpasoco", "larimer", "mesa", "summit", "weld"],
    "FL": [
        "alachua", "bay", "broward", "calhoun", "citrus", "clay", "duval", "escambia",
        "flagler", "gilchrist", "hillsborough", "gulf", "indian-river", "jackson",
        "lee", "leon", "manatee", "marion", "martin", "miamidade", "nassauclerk",
        "okaloosa", "okeechobee", "myorangeclerk", "palmbeach", "pasco", "pinellas",
        "polk", "putnam", "saintjohns", "santarosa", "seminole", "stlucie", "volusia", "sarasota"
    ],
    "NJ": ["hardystonnj", "newarknj"]
}

# Date presets
PRESET_RANGES = {
    "Next 2 Weeks": 14,
    "Next Month": 30,
    "Next 2 Months": 60,
    "Next 3 Months": 90,
    "Next 6 Months": 180
}

from dotenv import load_dotenv
import os

load_dotenv()
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")