import os
import time
import json
import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Optional, List
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup
from lxml import etree
import nodriver as uc
from nodriver.core.connection import ProtocolException
from websockets.exceptions import InvalidStatus

from utils.helpers import build_url, get_base_url
from utils.exporters import save_final_dict_to_excel
from core.zillow import get_zillow_infos

all_tables = []

def log_message(app, message: str):
    """Safely append messages to the GUI log textbox or print if headless/no app."""
    if not app or not hasattr(app, "log_textbox"):
        print(message)
        return

    def append_log():
        app.log_textbox.configure(state="normal")
        app.log_textbox.insert("end", message + "\n")
        app.log_textbox.see("end")
        app.log_textbox.configure(state="disabled")

    app.after(0, append_log)

def update_gui_progress(app, current: int, total: int):
    """Safely update GUI progress bar and label if app is provided."""
    if not app or not hasattr(app, "progress_bar"):
        return
    progress = current / total if total > 0 else 0
    app.after(0, lambda: app.progress_bar.set(progress))
    app.after(0, lambda: app.progress_label.configure(text=f"{current}/{total}"))

async def wait_for_page_load(page, target_url, timeout=15, check_interval=0.5):
    """Wait for target URL and complete ready state without pushing timeouts continuously."""
    start_time = asyncio.get_event_loop().time()
    print(f"wait_for_page_load ")
    while True:
        try:
            current_url = await page.evaluate("window.location.href")
            state = await page.evaluate("document.readyState")
            
            # Match target URL (or base domain path) and verify complete load
            if current_url == target_url and state == "complete":
                return page
            
            # If on the wrong page after initial wait, trigger reload
            if current_url != target_url and (asyncio.get_event_loop().time() - start_time) > 5:
                await page.reload()

            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"Page did not fully load or reach {target_url} in {timeout}s")
                
        except ProtocolException:
            print("⚠️ ProtocolException while checking page load, retrying...")
            
        await asyncio.sleep(check_interval)

async def wait_for_element(page, selector, timeout=5, poll_interval=0.5):
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            element = await page.select(selector, timeout=timeout)
        except ProtocolException:
            time.sleep(1)
            continue
        if element:
            return element
        await asyncio.sleep(poll_interval)
    return None

async def wait_for_specific_element(page, selector: str, timeout: int = 10):
    try:
        await page.wait_for(selector, timeout=timeout)
        print(f"Element '{selector}' found!")
        return True
    except Exception as e:
        print(f"Element '{selector}' not found within {timeout} seconds: {e}")
        return False

async def wait_for_full_page_load(page, check_interval=0.5, max_wait=20):
    """Wait for document.readyState == 'complete' with a hard upper bound."""
    start_time = time.time()
    print(f"wait_for_full_page_load")
    while time.time() - start_time < max_wait:
        try:
            ready_state = await page.evaluate("document.readyState")
            if ready_state == "complete":
                # Small buffer to allow dynamic DOM scripts to run
                await asyncio.sleep(1)
                return
        except Exception:
            pass
            
        await asyncio.sleep(check_interval)
        
    print("⚠️ Page load wait timed out, continuing anyway...")
async def extract_party_table(page):
    try:
        rows = await page.xpath('//*[@id="mgTab1"]/div/div[5]//table//tr', timeout=10)
        party_data = []
        for row in rows:
            soup = BeautifulSoup(str(row), "html.parser")
            cols = [td.get_text(strip=True) for td in soup.find_all("td")]
            if len(cols) >= 2:
                party_type = (cols[0]).strip()
                name = (cols[1]).strip()
                if name or party_type:
                    party_data.append((name, party_type))
        return party_data[:15]
    except Exception:
        traceback.print_exc()
        return []

async def day_exists_in_calendar(browser, date_obj, county):
    year = date_obj.strftime("%Y")
    month = date_obj.strftime("%m")
    day = date_obj.strftime("%d")
    url = f"https://{county}.realforeclose.com/index.cfm?zaction=user&zmethod=calendar&selCalDate=%7Bts%20%27{year}-{month}-01%2000%3A00%3A00%27%7D"
    page = await browser.get(url)
    await wait_for_full_page_load(page)
    time.sleep(0.5)
    html_content = await page.get_content()
    soup = BeautifulSoup(html_content, 'html.parser')
    try:
        dayid_element = soup.find('div', attrs={'dayid': f"{month}/{day}/{year}"})
        return dayid_element is not None
    except Exception:
        return False

async def process_single_page(url_item):
    global all_tables
    url = url_item['href']
    browser = await uc.start(headless=False)
    try:
        page = await browser.get(url)
        if os.path.exists("cookies.json"):
            await load_cookies(browser, page)
        await wait_for_page_load(page, url)
        await asyncio.sleep(2)

        party_data = await extract_party_table(page)
        if not party_data:
            return None

        html_content = await page.get_content()
        soup = BeautifulSoup(html_content, 'html.parser')
        AIC_PARENT = soup.find(id='AIC_PARENT')
        if not AIC_PARENT:
            return None

        a = AIC_PARENT.find_all(id=lambda x: x and x.startswith('AITEM'))
        if not a:
            return None

        aitem_id = a[0].get('id')
        dom = etree.HTML(str(soup))

        auction_status_labels = await page.xpath(f'//*[@id="{aitem_id}"]/div/div[1]', timeout=10)
        if auction_status_labels:
            auction_status = auction_status_labels[0].text.lower()
            status_xpath = f'//*[@id="{aitem_id}"]/div/div[2]'
            auction_status_text = dom.xpath(status_xpath)[0].text if dom.xpath(status_xpath) else ""

            if "status" in auction_status:
                auction_status = auction_status_text
            elif "sold" in auction_status:
                auction_status = f"sold on {auction_status_text}"
            elif "starts" in auction_status:
                auction_status = f"starts at {auction_status_text}"

            url_item['data']["Auction Status"] = auction_status

        first_defendant = None
        first_plaintiff = None
        for name, party_type in party_data:
            if party_type.lower() == 'defendant' and first_defendant is None:
                first_defendant = (name, party_type)
            elif party_type.lower() == 'plaintiff' and first_plaintiff is None:
                first_plaintiff = (name, party_type)
            if first_defendant and first_plaintiff:
                break

        idx = 1
        if first_plaintiff:
            url_item['data'][f"Name {idx}"] = first_plaintiff[0]
            url_item['data'][f"Party Type {idx}"] = first_plaintiff[1]
            idx += 1
        if first_defendant:
            url_item['data'][f"Name {idx}"] = first_defendant[0]
            url_item['data'][f"Party Type {idx}"] = first_defendant[1]

        all_tables.append(url_item['data'])
        return url_item['data']
    except Exception:
        traceback.print_exc()
        return None
    finally:
        await browser.stop()

async def fetch_cases(browser, url: str, state: str, county: str) -> Optional[List]:
    global all_tables
    all_tables = []
    try:
        page = await login_to_site(browser, url)
        await wait_for_main_areas(page)
        max_pages = await get_total_pages(page)
        if not max_pages:
            return all_tables

        base_url = get_base_url(page.url)
        urls = await collect_all_cases(page, state, county, base_url, max_pages)
        await process_multiple_pages(urls)
        return all_tables
    except InvalidStatus:
        browser.stop()
        browser = await uc.start(headless=False)
        return await fetch_cases(browser, url, state, county)
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return None

async def login_to_site(browser, url: str):
    logged_in = False
    while not logged_in:
        page = await browser.get(url)
        if os.path.exists("cookies.json"):
            await load_cookies(browser, page)
        await wait_for_full_page_load(page)
        if await page.xpath('//*[@id="divSysAlert"]'):
            await page.reload()
        logged_in = await login(page, browser)

    soup = await get_soup(page)
    if not soup.find(id='Area_W'):
        await check_accept_ok_buttons(page)
        page = await reload_and_wait(browser, url, page)
    return page

async def wait_for_main_areas(page):
    for attempt in range(10):
        soup = await get_soup(page)
        area_w = soup.find(id='Area_W')
        area_c = soup.find(id='Area_C')
        if is_area_ready(area_w) and is_area_ready(area_c):
            return
        if area_w and area_w.find("div", class_="Loading"):
            await page.reload()
            await asyncio.sleep(1.5)
        else:
            await page.reload()
            await asyncio.sleep(2)

async def get_total_pages(page) -> Optional[int]:
    for attempt in range(5):
        soup = await get_soup(page)
        max_element = soup.find(id='maxWA')
        if max_element and max_element.text:
            return int(max_element.text)
        await page.reload()
        await wait_for_full_page_load(page)
        await asyncio.sleep(2)
    return None

async def collect_all_cases(page, state: str, county: str, base_url: str, max_pages: int) -> List:
    urls = []
    for page_num in range(max_pages):
        try:
            page_urls = await extract_cases_from_page(page, state, county, base_url)
            urls.extend(page_urls)
            if page_num < max_pages - 1:
                await navigate_to_next_page(page)
        except Exception as e:
            traceback.print_exc()
            continue
    return urls

async def extract_cases_from_page(page, state: str, county: str, base_url: str) -> List:
    soup = await get_soup(page)
    area_w = soup.find(id='Area_W')
    area_c = soup.find(id='Area_C')
    elements_w = area_w.find_all(id=lambda x: x and x.startswith('AITEM')) if area_w else []
    elements_c = area_c.find_all(id=lambda x: x and x.startswith('AITEM')) if area_c else []
    all_elements = elements_w + elements_c

    urls = []
    for element in all_elements:
        data = {'county': f"{state} - {county}"}
        for row in element.find_all('tr'):
            labels = row.find_all('td', class_="AD_LBL")
            values = row.find_all('td', class_="AD_DTA")
            if labels and values:
                key = labels[0].text.strip()
                value = values[0].text.strip()
                if "Parcel" not in key and "href" not in key:
                    data[key] = value

        a_tag = element.find('a', attrs={'aria-label': 'Link for property details'})
        if a_tag and a_tag.has_attr('href'):
            full_url = urljoin(base_url, a_tag['href'])
            urls.append({"data": data, "href": full_url})
    return urls

async def navigate_to_next_page(page):
    current_elem = await page.select("#curPWA")
    initial_page = int(current_elem.attributes[current_elem.attributes.index('curpg') + 1])
    next_button = await page.find('//*[@id="BID_WINDOW_CONTAINER"]/div[3]/div[3]/span[3]/img', timeout=5)

    for attempt in range(20):
        await next_button.click()
        await wait_for_full_page_load(page)
        await asyncio.sleep(0.5)
        current_elem = await page.select("#curPWA")
        current_page = int(current_elem.attributes[current_elem.attributes.index('curpg') + 1])
        if current_page != initial_page:
            return
        await asyncio.sleep(1)
    raise TimeoutError("Failed to navigate to next page")

async def process_multiple_pages(urls: List, batch_size: int = 2):
    global all_tables
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i + batch_size]
        tasks = [process_single_page(url_item) for url_item in batch]
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(1)
    return all_tables

async def get_soup(page):
    html = await page.get_content()
    return BeautifulSoup(html, 'html.parser')

def is_area_ready(area) -> bool:
    if not area:
        return False
    parent = area.parent
    if parent:
        style = parent.get('style', '')
        if 'display: none' in style or 'visibility: hidden' in style:
            return False
    return bool(area.text.strip())

async def reload_and_wait(browser, url: str, page, max_retries=5):
    """Safely reload with maximum retry attempts to prevent infinite blocking."""
    for attempt in range(max_retries):
        try:
            page = await browser.get(url)
            await page.reload()
            await asyncio.sleep(2)
            await page.xpath('//*[@id="Area_W"]', timeout=5)
            return page
        except ProtocolException:
            print(f"⚠️ Retry {attempt + 1}/{max_retries} waiting for #Area_W...")
            await asyncio.sleep(2)
            
    raise TimeoutError("Failed to reach target element #Area_W after maximum retries.")

async def save_cookies(browser):
    try:
        await browser.cookies.save("cookies.json")
    except Exception as e:
        print(f"Failed to save cookies: {e}")

async def perform_login(page, username, password, timeout=1):
    username_input = await wait_for_element(page, "#LogName", timeout=4)
    if not username_input:
        return True

    await username_input.clear_input()
    await username_input.send_keys(username)

    password_input = await wait_for_element(page, "#LogPass", timeout=timeout)
    if not password_input:
        return True
    await password_input.clear_input()
    await password_input.send_keys(password)

    login_button = await page.select("#LogButton")
    if login_button:
        await login_button.click()
    else:
        await password_input.send_keys("\n")
    return not (await wait_for_element(page, "#LogName"))

async def login(page, browser):
    logged_in = False
    for i in range(8):
        try:
            logged_in = await perform_login(page, "karimmerchaoui", "msv321?")
            if logged_in:
                await save_cookies(browser)
                return logged_in
            time.sleep(2)
            if i == 7:
                await page.close()
        except ProtocolException:
            pass
    return logged_in

async def load_cookies(browser, page):
    try:
        await browser.cookies.load("cookies.json")
        while True:
            try:
                await page.reload()
                break
            except ProtocolException:
                time.sleep(1)
        return True
    except Exception:
        return False

async def check_accept_ok_buttons(page):
    try:
        ok_button = await wait_for_element(page, "#BNOTOK", timeout=6)
        accept_button = await wait_for_element(page, "#BNOTACC", timeout=1)
        while ok_button or accept_button:
            if ok_button:
                try:
                    await ok_button.click()
                except ProtocolException:
                    ok_button = await wait_for_element(page, "#BNOTOK")
                    continue
            else:
                try:
                    await accept_button.click()
                except ProtocolException:
                    accept_button = await wait_for_element(page, "#BNOTACC")
                    continue
            ok_button = await wait_for_element(page, "#BNOTOK")
            accept_button = await wait_for_element(page, "#BNOTACC")
    except Exception:
        traceback.print_exc()

async def run_scraper(selection_data, app=None):
    start_date = selection_data["start_date"]
    end_date = selection_data["end_date"]
    headless = selection_data["headless"]
    state = selection_data["state"]
    county = selection_data["county"]

    if os.path.exists("cookies.json"):
        os.remove("cookies.json")

    total_days = (end_date - start_date).days + 1
    current_day = 0
    current_date = start_date

    all_data = []
    calendar_browser = await uc.start(headless=False)
    browser = await uc.start(headless=headless)

    while current_date <= end_date:
        if not await day_exists_in_calendar(calendar_browser, current_date, county):
            log_message(app, f"⏭️ Skipping {current_date.strftime('%Y-%m-%d')} (not in calendar)")
            current_day += 1
            current_date += timedelta(days=1)
            continue

        url = build_url({**selection_data, "start_date": current_date})
        log_message(app, f"Fetching {current_date.strftime('%Y-%m-%d')}")
        update_gui_progress(app, current_day, total_days)

        try:
            data = await fetch_cases(browser, url, state, county)
            if data:
                for i, record in enumerate(data):
                    data[i] = {"Date": current_date.strftime('%Y-%m-%d'), **record}
                all_data.extend(data)
                log_message(app, f"✔️ {len(data)} records fetched for {current_date.strftime('%Y-%m-%d')}")
            else:
                log_message(app, f"⚠️ No data found for {current_date.strftime('%Y-%m-%d')}")
        except Exception as e:
            log_message(app, f"❌ Error on {current_date.strftime('%Y-%m-%d')}: {e}")

        current_day += 1
        current_date += timedelta(days=1)

    final_dict = {}
    for record in all_data:
        case_number = record.get("Case #:")
        if case_number:
            final_dict[case_number] = record

    if final_dict:
        save_final_dict_to_excel(final_dict, selection_data["output_file"])
        log_message(app, f"💾 Saved {len(final_dict)} unique cases to Excel.")
    else:
        log_message(app, "⚠️ No data to save.")

    await calendar_browser.stop()
    await browser.stop()
    update_gui_progress(app, total_days, total_days)
    log_message(app, "🎉 Scraping completed successfully!")

async def run_multi_county_scraper(selection_data, window=None):
    counties = selection_data['counties']
    start_date = selection_data['start_date']
    end_date = selection_data['end_date']

    total_days = ((end_date - start_date).days + 1) * len(counties)
    current_day = 0

    log_message(window, f"Starting {len(counties)} counties...")
    all_data = []

    for idx, (state, county) in enumerate(counties, 1):
        log_message(window, f"\n[{idx}/{len(counties)}] Processing {state}-{county}")

        if os.path.exists("cookies.json"):
            os.remove("cookies.json")

        current_date = start_date
        browser = await uc.start(headless=selection_data['headless'])
        calendar_browser = await uc.start(headless=False)

        while current_date <= end_date:
            update_gui_progress(window, current_day, total_days)

            if not await day_exists_in_calendar(calendar_browser, current_date, county):
                log_message(window, f"  ⏭️ Skipping {current_date.strftime('%Y-%m-%d')}")
                current_date += timedelta(days=1)
                current_day += 1
                continue

            url = f"https://{county}.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=DAYLIST&AUCTIONDATE={current_date.strftime('%m/%d/%Y')}"
            log_message(window, f"  Fetching {current_date.strftime('%Y-%m-%d')}")

            try:
                data = await fetch_cases(browser, url, state, county)
                if data:
                    for record in data:
                        record['Date'] = current_date.strftime('%Y-%m-%d')
                    all_data.extend(data)
                    log_message(window, f"  ✔️ {len(data)} cases on {current_date.strftime('%Y-%m-%d')}")
            except Exception as e:
                log_message(window, f"  ❌ Error: {e}")

            current_date += timedelta(days=1)
            current_day += 1

        try:
            await browser.stop()
            await calendar_browser.stop()
        except Exception:
            pass

        log_message(window, f"✅ Finished {state}-{county}")

    if all_data:
        final_dict = {}
        for record in all_data:
            case_num = record.get("Case #:")
            if case_num:
                final_dict[case_num] = record

        save_final_dict_to_excel(final_dict, selection_data['output_file'])
        log_message(window, f"\n🎉 Done! Saved {len(final_dict)} cases")
    else:
        log_message(window, "\n⚠️ No data found")

    update_gui_progress(window, total_days, total_days)

async def scrape_county_data(state: str, county: str, start_date_str: str, end_date_str: str, output_dir: str, headless: bool = True):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"Scrape_{state}_{county}_{timestamp}.xlsx"
    filepath = os.path.join(output_dir, filename)

    calendar_browser = await uc.start(headless=headless)
    main_browser = await uc.start(headless=headless)

    current_date = start_date
    try:
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            print(f"--- Processing {date_str} ---")

            if not await day_exists_in_calendar(calendar_browser, current_date, county):
                current_date += timedelta(days=1)
                continue

            target_url = build_url({"county": county, "start_date": current_date})
            day_results = await fetch_cases(main_browser, target_url, state, county)

            if day_results:
                enriched_records = []
                for record in day_results:
                    record_data = {"Date": date_str, **record}
                    address = record.get("Property Address") or record.get("Address")

                    if address:
                        z_data = get_zillow_infos(address)
                        if isinstance(z_data, tuple):
                            lowest, status, h_type, p_dim, agent_resp = z_data
                            record_data["Zillow_Lowest_Zest"] = lowest
                            record_data["Zillow_Status"] = status
                            record_data["Zillow_HomeType"] = h_type
                            record_data["Zillow_PropertyTypeDim"] = p_dim
                            record_data["Zillow_AgentResponsible"] = agent_resp
                        else:
                            for col in ["Zillow_Lowest_Zest", "Zillow_Status", "Zillow_HomeType",
                                        "Zillow_PropertyTypeDim", "Zillow_AgentResponsible"]:
                                record_data[col] = "N/A"

                    enriched_records.append(record_data)

                new_df = pd.DataFrame(enriched_records)
                if os.path.exists(filepath):
                    existing_df = pd.read_excel(filepath)
                    updated_df = pd.concat([existing_df, new_df], ignore_index=True)
                    updated_df.drop_duplicates(subset=['Case #:'], keep='last', inplace=True)
                else:
                    updated_df = new_df

                updated_df.to_excel(filepath, index=False, engine='openpyxl')

            current_date += timedelta(days=1)
        return True
    finally:
        await calendar_browser.stop()
        await main_browser.stop()