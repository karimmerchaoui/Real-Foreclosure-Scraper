from datetime import datetime
import requests

def build_url(county: str, start_date: datetime) -> str:
    day = start_date.strftime("%d")
    month = start_date.strftime("%m")
    year = start_date.strftime("%Y")
    return f"https://{county}.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=DAYLIST&AUCTIONDATE={month}/{day}/{year}"

def get_base_url(full_url: str) -> str:
    parts = full_url.split('://')
    protocol = parts[0]
    domain = parts[1].split('/')[0]
    return f"{protocol}://{domain}"

def is_us_ip() -> bool:
    try:
        response = requests.get("https://ipinfo.io/json", timeout=5)
        data = response.json()
        return data.get("country", "").upper() == "US"
    except Exception:
        return False