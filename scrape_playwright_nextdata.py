import time
import pandas as pd
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth


def run():
    listings_data = []

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

        # Target English directory route for predictable structure
        target_url = "https://sa.aqar.fm/en/all/riyadh"
        print(f"Navigating to {target_url}...")

        page.goto(target_url, wait_until="domcontentloaded")

        # 1. Wait for listing items/cards to appear in the DOM
        try:
            print("Waiting for listing elements to hydrate...")
            page.wait_for_selector('a[href*="/riyadh/"]', timeout=15000)
        except Exception as e:
            print(f"Timeout waiting for elements: {e}")

        # Scroll to ensure additional listing items render
        page.evaluate("window.scrollBy(0, 1000)")
        time.sleep(3)

        # 2. Extract listing card links directly from DOM
        listing_links = page.locator('a[href*="/riyadh/"]').all()
        print(f"Found {len(listing_links)} matching listing elements on page.")

        for link in listing_links:
            try:
                text_content = link.text_content().strip()
                href = link.get_attribute("href")

                if text_content and href:
                    listings_data.append(
                        {
                            "link": f"https://sa.aqar.fm{href}"
                            if href.startswith("/")
                            else href,
                            "raw_info": text_content,
                        }
                    )
            except Exception:
                continue

        browser.close()

    return listings_data


if __name__ == "__main__":
    data = run()
    df = pd.DataFrame(data)

    if not df.empty:
        # Drop duplicates if duplicate link nodes exist in DOM
        df = df.drop_duplicates(subset=["link"])
        df.to_csv("riyadh_raw_listings.csv", index=False, encoding="utf-8-sig")
        print(
            f"Successfully captured {len(df)} listings to 'riyadh_raw_listings.csv'."
        )
    else:
        print("No listings found. Verify page URL or network connectivity.")