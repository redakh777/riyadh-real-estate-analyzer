import os
import random
import time
import re
import pandas as pd
from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import Stealth
    STEALTH_VERSION = "v2"
except ImportError:
    try:
        from playwright_stealth import stealth_sync
        STEALTH_VERSION = "v1"
    except ImportError:
        STEALTH_VERSION = None


def save_checkpoint(new_listings, filename="riyadh_raw_listings.csv"):
    if not new_listings:
        return
    df = pd.DataFrame(new_listings)
    file_exists = os.path.isfile(filename)
    df.to_csv(
        filename,
        mode="a" if file_exists else "w",
        index=False,
        header=not file_exists,
        encoding="utf-8-sig",
    )
    print(f"💾 Checkpoint saved: Appended {len(df)} records to {filename}", flush=True)


def run_full_scraper(max_pages=50):
    output_filename = "riyadh_raw_listings.csv"

    if os.path.isfile(output_filename):
        os.remove(output_filename)

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
    ]

    if STEALTH_VERSION == "v2":
        playwright_cm = Stealth().use_sync(sync_playwright())
    else:
        playwright_cm = sync_playwright()

    with playwright_cm as p:
        batch_listings = []

        for page_num in range(1, max_pages + 1):
            target_url = (
                f"https://sa.aqar.fm/en/all/riyadh/{page_num}"
                if page_num > 1
                else "https://sa.aqar.fm/en/all/riyadh"
            )

            success = False
            total_page_attempts = 0

            while not success:
                total_page_attempts += 1
                print(f"\n--- Scraping Page {page_num} (Attempt #{total_page_attempts}): {target_url} ---", flush=True)
                
                # Cloudflare flags standard headless flags instantly; keeping headless=True 
                # with explicit anti-detection args helps avoid standard triggers.
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--start-maximized",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-infobars",
                        "--window-size=1920,1080",
                    ],
                )

                context = browser.new_context(
                    user_agent=random.choice(user_agents),
                    locale="en-US",
                    timezone_id="Asia/Riyadh",
                    viewport={"width": 1920, "height": 1080},
                    device_scale_factor=1,
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1"
                    }
                )

                # Hard override for navigator.webdriver property which Cloudflare looks for
                context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                page = context.new_page()
                
                if STEALTH_VERSION == "v1":
                    stealth_sync(page)

                try:
                    # Use networkidle to make sure Cloudflare challenge scripts fully execute
                    page.goto(target_url, wait_until="networkidle", timeout=45000)
                    
                    title = page.title()
                    print(f"   -> Page Title: {title}", flush=True)
                    
                    if "blocked" in title.lower() or "حظر" in title or "cloudflare" in title.lower():
                        print(f"🚨 Cloudflare block detected on Page {page_num}! Changing identity...", flush=True)
                        browser.close()
                        
                        backoff = min(15 * total_page_attempts, 60)
                        print(f"💤 Backing off: Sleeping for {backoff}s...", flush=True)
                        time.sleep(backoff)
                        continue

                    # Mimic natural user activity
                    page.mouse.move(random.randint(200, 600), random.randint(200, 500))
                    page.evaluate("window.scrollBy(0, window.innerHeight / 1.5)")
                    page.wait_for_timeout(random.randint(2000, 4000))
                    
                    page.wait_for_selector('a[href*="/riyadh/"]', timeout=12000)

                    listing_links = page.locator('a[href*="/riyadh/"]').all()
                    page_count = 0
                    page_listings = []

                    for link in listing_links:
                        try:
                            raw_text = link.text_content().strip()
                            href = link.get_attribute("href")

                            if not raw_text or not href:
                                continue

                            price_match = re.search(
                                r"(?:SAR|SR|\b)\s*([\d,]+)\s*(?:SAR|SR|\b)", raw_text
                            )
                            price = (
                                int(price_match.group(1).replace(",", ""))
                                if price_match
                                else None
                            )

                            area_match = re.search(
                                r"([\d,]+)\s*(?:sqm|m²|m2)", raw_text, re.IGNORECASE
                            )
                            area = (
                                float(area_match.group(1).replace(",", ""))
                                if area_match
                                else None
                            )

                            district = "Riyadh"
                            path_parts = href.strip("/").split("/")
                            if len(path_parts) >= 2:
                                district_slug = path_parts[1].replace("-", " ").title()
                                if district_slug.lower() not in [
                                    "all",
                                    "properties",
                                    "real-estate",
                                ]:
                                    district = district_slug

                            page_listings.append(
                                {
                                    "district": district,
                                    "price_sar": price,
                                    "area_sqm": area,
                                    "raw_info": raw_text,
                                    "link": f"https://sa.aqar.fm{href}"
                                    if href.startswith("/")
                                    else href,
                                }
                            )
                            page_count += 1
                        except Exception:
                            continue

                    batch_listings.extend(page_listings)
                    print(f"   -> ✅ Successfully captured {page_count} items from page {page_num}.", flush=True)
                    success = True
                    browser.close()
                    break

                except Exception as e:
                    print(f"⚠️ Error on Page {page_num}: {e}. Retrying...", flush=True)
                    browser.close()
                    time.sleep(8)

            if page_num % 10 == 0 and batch_listings:
                save_checkpoint(batch_listings, output_filename)
                batch_listings = []
                time.sleep(10.0)

            sleep_time = random.uniform(5.0, 9.0)
            print(f"⏳ Resting {sleep_time:.1f}s before next page...", flush=True)
            time.sleep(sleep_time)

        if batch_listings:
            save_checkpoint(batch_listings, output_filename)

    print("\n🎉 High-speed scraping session complete!", flush=True)


if __name__ == "__main__":
    run_full_scraper(max_pages=50)

    if os.path.isfile("riyadh_raw_listings.csv"):
        df = pd.read_csv("riyadh_raw_listings.csv")
        if not df.empty:
            df = df.drop_duplicates(subset=["link"])
            df.to_csv("riyadh_raw_listings.csv", index=False, encoding="utf-8-sig")
            print(f"🧹 Cleaned duplicates. Final unique dataset size: {len(df)} rows.", flush=True)