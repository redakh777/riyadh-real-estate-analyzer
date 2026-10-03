import time
import pandas as pd
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth  # Updated import

listings_data = []


def handle_response(response):
    if "listings" in response.url and response.status == 200:
        try:
            json_data = response.json()
            items = json_data.get("listings", []) or json_data.get(
                "props", {}
            ).get("pageProps", {}).get("listings", [])
            for item in items:
                listings_data.append(
                    {
                        "id": item.get("id"),
                        "district": item.get("district_name")
                        or item.get("location", {}).get("district"),
                        "price_sar": item.get("price"),
                        "area_sqm": item.get("area"),
                    }
                )
        except Exception:
            pass


def run():
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
            locale="ar-SA",
            viewport=None,
        )

        page = context.new_page()

        # Apply stealth configuration with the new v2.x syntax
        stealth = Stealth()
        stealth.apply_stealth_sync(page)

        page.on("response", handle_response)

        print("Navigating to target page...")
        page.goto("https://sa.aqar.fm/عقارات/الرياض", wait_until="domcontentloaded")

        time.sleep(5)

        for i in range(5):
            page.evaluate("window.scrollBy(0, 800)")
            print(f"Scrolled iteration {i+1}...")
            time.sleep(2.5)

        browser.close()


if __name__ == "__main__":
    run()
    df = pd.DataFrame(listings_data)
    if not df.empty:
        df.to_csv("riyadh_raw_listings.csv", index=False, encoding="utf-8-sig")
        print(
            f"Successfully captured {len(df)} listings to 'riyadh_raw_listings.csv'."
        )
    else:
        print("No listings captured. Verify browser window manually.")