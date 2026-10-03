import os
import random
import time
import re
import pandas as pd
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync


def save_checkpoint(new_listings, filename="riyadh_raw_listings.csv"):
    """Appends new batch listings safely to CSV without overwriting previous pages."""
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
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ]

    with sync_playwright() as p:
        batch_listings = []
        consecutive_blocks = 0

        for page_num in range(1, max_pages + 1):
            target_url = (
                f"https://sa.aqar.fm/en/all/riyadh/{page_num}"
                if page_num > 1
                else "https://sa.aqar.fm/en/all/riyadh"
            )

            success = False
            retries = 3

            for attempt in range(1, retries + 1):
                print(f"\n--- Scraping Page {page_num} (Attempt {attempt}/{retries}): {target_url} ---", flush=True)
                
                # Fresh browser instance per attempt to completely reset fingerprints
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--start-maximized",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )

                context = browser.new_context(
                    user_agent=random.choice(user_agents),
                    locale="en-US",
                    viewport={"width": 1920, "height": 1080},
                    device_scale_factor=1,
                )

                page = context.new_page()
                stealth_sync(page)

                try:
                    page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
                    
                    title = page.title()
                    print(f"   -> Page Title: {title}", flush=True)
                    
                    if "blocked" in title.lower() or "حظر" in title:
                        consecutive_blocks += 1
                        print(f"🚨 Block detected! (Consecutive block count: {consecutive_blocks})", flush=True)
                        browser.close()
                        
                        # If Cloudflare is heavily throttling us, trigger a heavy cool-down
                        if consecutive_blocks >= 2:
                            cooldown = 60 * consecutive_blocks
                            print(f"🛑 High block frequency detected. Deep cooling down for {cooldown}s...", flush=True)
                            time.sleep(cooldown)
                        else:
                            backoff_time = 30 * attempt
                            print(f"💤 Backing off for {backoff_time}s...", flush=True)
                            time.sleep(backoff_time)
                        continue

                    # Reset consecutive blocks on success
                    consecutive_blocks = 0

                    # Simulate human mouse movement and scrolling
                    page.mouse.move(random.randint(200, 700), random.randint(200, 700))
                    page.evaluate("window.scrollBy(0, window.innerHeight / 1.5)")
                    page.wait_for_timeout(random.randint(4000, 7000))
                    
                    page.wait_for_selector('a[href*="/riyadh/"]', timeout=15000)

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
                    print(f"   -> Successfully captured {page_count} items from page {page_num}.", flush=True)
                    success = True
                    browser.close()
                    break

                except Exception as e:
                    print(f"⚠️ Error on page {page_num} attempt {attempt}: {e}", flush=True)
                    browser.close()
                    time.sleep(15)

            if not success:
                print(f"❌ Failed to scrape page {page_num} after {retries} attempts. Moving on.", flush=True)

            # Checkpoint increment every 5 pages
            if page_num % 5 == 0 and batch_listings:
                save_checkpoint(batch_listings, output_filename)
                batch_listings = []
                print("☕ Checkpoint reached. Pausing 30s to stay under rate limits...", flush=True)
                time.sleep(30.0)

            # Safe human-like delay between pages (16 to 26 seconds to avoid sliding window triggers)
            sleep_time = random.uniform(16.0, 26.0)
            print(f"⏳ Resting {sleep_time:.1f}s before next page...", flush=True)
            time.sleep(sleep_time)

        if batch_listings:
            save_checkpoint(batch_listings, output_filename)

    print("\n🎉 Scraping session complete!", flush=True)


if __name__ == "__main__":
    run_full_scraper(max_pages=50)

    if os.path.isfile("riyadh_raw_listings.csv"):
        df = pd.read_csv("riyadh_raw_listings.csv")
        if not df.empty:
            df = df.drop_duplicates(subset=["link"])
            df.to_csv("riyadh_raw_listings.csv", index=False, encoding="utf-8-sig")
            print(f"🧹 Cleaned duplicates. Final unique dataset size: {len(df)} rows.", flush=True)