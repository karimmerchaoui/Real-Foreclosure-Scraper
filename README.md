# Real Foreclosure Scraper

A desktop tool that scrapes county foreclosure auction sites and turns them into ready-to-use real estate lead lists — no manual calendar-checking required.

## Overview

Foreclosure auction data is publicly available, but only if you're willing to work for it. Across Florida, Colorado, and New Jersey, each county runs its own realforeclose.com site with its own JavaScript calendar, its own quirks, and zero export functionality. Pulling leads means clicking into every case, on every date, in every county, by hand.

**This project solves the problem of** manually collecting foreclosure auction data one county at a time. Point it at a date range — anywhere from the next 2 weeks to 6 months out — and it drives a real browser through the auction calendar for any of 44 counties across 3 states, opens every case scheduled, pulls up to 15 parties per case to identify the plaintiff/defendant, and reads the live auction status. Add in the optional Zillow enrichment step and each lead can carry up to 12 data points — case details plus valuation, home type, and listing status — before it all lands in a single de-duplicated Excel file.

## Who Would Benefit From This Tool

- Real estate wholesalers and investors sourcing pre-foreclosure and auction leads
- Real estate agencies building outreach lists for distressed properties
- Lead generation companies that sell foreclosure data
- Title companies and attorneys tracking auction schedules across counties
- Analysts researching foreclosure trends over time

## Key Features

- **44 counties, 3 states, one tool** — Florida (35 counties), Colorado (7), New Jersey (2), all defined in a single config file and easy to extend
- Custom date ranges or one-click presets, from the next 2 weeks out to 6 months
- Single-county or multi-county batch mode, with a checkbox picker for running dozens of counties in one pass
- Headless or visible browser — watch it work, or let it run in the background
- Live progress bar and log so you always know what's scraping and what's been skipped
- Optional Zillow enrichment per property: Zestimate range, home type, and listing status
- Every run outputs a de-duplicated, timestamped Excel file — no repeat leads across runs
- Background-threaded so the GUI never locks up mid-scrape
- Core utilities (URL building, exports) covered by a pytest suite

## Technologies Used

Python 3, [nodriver](https://github.com/ultrafunkamsterdam/nodriver) for undetected browser automation, BeautifulSoup4 + lxml for parsing, CustomTkinter for the GUI, pandas + openpyxl for exports, [Apify](https://apify.com/)'s Zillow actor for valuation data, requests, pytest, asyncio.

## Project Background

Built in August 2025 while working for MSV Properties, a real estate company, to solve a very concrete problem: the acquisitions team needed fresh foreclosure leads every day, across multiple counties, and doing it by hand didn't scale. What started as a one-county script grew into a 44-county, 3-state scraping pipeline with a GUI so non-technical team members could run it themselves.

## Technical Details

- **`core/scraper.py`** — the scraping engine. Runs two browser instances per county (one for the calendar, one for case pages), extracts party tables via XPath + BeautifulSoup, and reads auction status off each listing. Three entry points: `run_scraper()` (single county, GUI), `run_multi_county_scraper()` (batch, GUI), `scrape_county_data()` (headless, incremental Excel writes for scripted/scheduled runs)
- **`core/zillow.py`** — wraps the Apify Zillow actor to pull a low-end Zestimate, home status, home type, and listing details per address
- **`utils/helpers.py`** — URL construction, base-URL extraction, and a US-IP check (these county sites are geofenced to the US)
- **`utils/exporters.py`** — timestamped `.xlsx` export, de-duplicated by case number
- **`gui/gui.py`** — the CustomTkinter interface, single- and multi-county flows, wired to the async scrapers through background threads
- **`config/settings.py`** — county/state definitions, date presets, API credentials

Cookies persist to `cookies.json` between requests to cut down on repeated bot checks, and are cleared at the start of every new run.

## Installation

```bash
git clone https://github.com/<your-username>/real-foreclosure-scraper.git
cd real-foreclosure-scraper

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Set your Apify token as an environment variable rather than hardcoding it:

```bash
export APIFY_API_TOKEN="your-apify-token-here"
```

> ⚠️ `config/settings.py` currently references `APIFY_API_TOKEN` directly. Before making this repo public, move it to an env var (e.g. `python-dotenv` + a `.gitignore`'d `.env`) so no live credential ends up in git history.

```bash
python -m gui.gui                                                                   # single-county GUI
python -c "from gui.gui import create_multi_county_gui; create_multi_county_gui()"  # multi-county GUI

pytest                                                                               # run tests
```

## Output Examples

Each run produces a timestamped, de-duplicated Excel file (e.g. `realforeclose_report_20260730_14_32.xlsx`), one row per unique case:

| Date | Case #: | Name 1 | Party Type 1 | Name 2 | Party Type 2 | Auction Status | Zillow_Lowest_Zest | Zillow_Status | Zillow_HomeType |
|---|---|---|---|---|---|---|---|---|---|
| 2026-05-15 | 2026-001 | Jane Doe | plaintiff | John Smith | defendant | sold on $185,000 | 172,400 | FOR_SALE | SINGLE_FAMILY |
| 2026-05-16 | 2026-002 | ABC Bank | plaintiff | Mary Jones | defendant | starts at $210,000 | 198,750 | FOR_SALE | CONDO |
