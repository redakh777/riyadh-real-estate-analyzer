import re
import time
import pandas as pd
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth


def run_full_scraper(max_pages=2):
    all_listings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="en-US",
            viewport=None,
        )

        page = context.new_page()

        stealth = Stealth()
        stealth.apply_stealth_sync(page)

        for page_num in range(1, max_pages + 1):
            target_url = (
                f"https://sa.aqar.fm/en/all/riyadh/{page_num}"
                if page_num > 1
                else "https://sa.aqar.fm/en/all/riyadh"
            )

            print(f"Scraping Page {page_num}: {target_url}...")
            page.goto(target_url, wait_until="domcontentloaded")

            # Wait for elements
            try:
                page.wait_for_selector('a[href*="/riyadh/"]', timeout=15000)
            except Exception:
                print(f"Timeout waiting for elements on page {page_num}.")
                continue

            # Scroll to hydrate
            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(2)

            listing_links = page.locator('a[href*="/riyadh/"]').all()

            for link in listing_links:
                try:
                    raw_text = link.text_content().strip()
                    href = link.get_attribute("href")

                    if not raw_text or not href:
                        continue

                    # Extract price via Regex (looks for numbers near SAR / SR or digits)
                    price_match = re.search(
                        r"(?:SAR|SR|\b)\s*([\d,]+)\s*(?:SAR|SR|\b)", raw_text
                    )
                    price = (
                        int(price_match.group(1).replace(",", ""))
                        if price_match
                        else None
                    )

                    # Extract area via Regex (looks for numbers near sqm / m²)
                    area_match = re.search(
                        r"([\d,]+)\s*(?:sqm|m²|m2)", raw_text, re.IGNORECASE
                    )
                    area = (
                        float(area_match.group(1).replace(",", ""))
                        if area_match
                        else None
                    )

                    # Extract District Name from URL path (e.g. /en/riyadh/al-malqa/...)
                    district = "Riyadh"
                    path_parts = href.strip("/").split("/")
                    if len(path_parts) >= 2:
                        # District slug is typically after 'riyadh' in the URL path
                        district_slug = path_parts[1].replace("-", " ").title()
                        if district_slug.lower() not in [
                            "all",
                            "properties",
                            "real-estate",
                        ]:
                            district = district_slug

                    all_listings.append(
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
                except Exception:
                    continue

            time.sleep(2)

        browser.close()

    return all_listings


if __name__ == "__main__":
    data = run_full_scraper(max_pages=3)
    df = pd.DataFrame(data)

    if not df.empty:
        df = df.drop_duplicates(subset=["link"])
        df.to_csv("riyadh_raw_listings.csv", index=False, encoding="utf-8-sig")
        print(f"\nCaptured {len(df)} unique listings into 'riyadh_raw_listings.csv'.")