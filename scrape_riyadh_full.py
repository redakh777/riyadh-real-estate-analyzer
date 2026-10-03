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
    print(f"💾 Checkpoint saved: Appended {len(df)} records to {filename}")


def run_full_scraper(max_pages=50):  # Reduced default batch size to avoid long exposure
    output_filename = "riyadh_raw_listings.csv"

    if os.path.isfile(output_filename):
        os.remove(output_filename)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-US",
            viewport={"width": 1920, "height": 1080},
        )

        page = context.new_page()
        stealth_sync(page)

        batch_listings = []

        for page_num in range(1, max_pages + 1):
            target_url = (
                f"https://sa.aqar.fm/en/all/riyadh/{page_num}"
                if page_num > 1
                else "https://sa.aqar.fm/en/all/riyadh"
            )

            print(f"Scraping Page {page_num} of {max_pages}: {target_url}...")
            
            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
                
                print(f"   -> Page Title: {page.title()}")
                
                if "blocked" in page.title().lower() or "حظر" in page.title():
                    print("🚨 Block detected by title! Pausing for 30 seconds to cool down...")
                    time.sleep(30)
                    continue

                # Simulate human mouse movement and scrolling
                page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                page.evaluate("window.scrollBy(0, window.innerHeight / 2)")
                page.wait_for_timeout(random.randint(4000, 7000))
                
                page.wait_for_selector('a[href*="/riyadh/"]', timeout=15000)
            except Exception as e:
                print(f"⚠️ Timeout or network issue on page {page_num}. Skipping... Error: {e}")
                continue

            # Heavy human-like delay between pages (10 to 20 seconds)
            sleep_time = random.uniform(10.0, 20.0)
            print(f"⏳ Waiting {sleep_time:.1f}s to mimic human reading pattern...")
            time.sleep(sleep_time)

            listing_links = page.locator('a[href*="/riyadh/"]').all()
            page_count = 0

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

                    batch_listings.append(
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

            print(f"   -> Captured {page_count} items from page {page_num}.")

            if page_num % 5 == 0 and batch_listings:
                save_checkpoint(batch_listings, output_filename)
                batch_listings = []

            if page_num % 10 == 0:
                print("☕ Taking an extended 30-second breather to remain completely undetected...")
                time.sleep(30)

        if batch_listings:
            save_checkpoint(batch_listings, output_filename)

        browser.close()

    print("\n🎉 Scraping session complete!")


if __name__ == "__main__":
    run_full_scraper(max_pages=50) # Start testing with 50 pages first

    if os.path.isfile("riyadh_raw_listings.csv"):
        df = pd.read_csv("riyadh_raw_listings.csv")
        if not df.empty:
            df = df.drop_duplicates(subset=["link"])
            df.to_csv("riyadh_raw_listings.csv", index=False, encoding="utf-8-sig")
            print(f"🧹 Cleaned duplicates. Final unique dataset size: {len(df)} rows.")