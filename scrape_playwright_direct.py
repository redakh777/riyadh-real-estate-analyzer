import json
import time
from playwright.sync_api import sync_playwright
import pandas as pd

listings_data = []

def handle_response(response):
    # Intercept network API calls returned directly by the site
    if "listings" in response.url and response.status == 200:
        try:
            json_data = response.json()
            # Extract listings list if available in payload
            items = json_data.get("listings", []) or json_data.get("props", {}).get("pageProps", {}).get("listings", [])
            for item in items:
                listings_data.append({
                    "id": item.get("id"),
                    "district": item.get("district_name") or item.get("location", {}).get("district"),
                    "price_sar": item.get("price"),
                    "area_sqm": item.get("area"),
                })
        except Exception:
            pass

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Visible browser
        context = browser.new_context(locale="ar-SA")
        page = context.new_page()

        page.on("response", handle_response)

        print("Navigating to Aqar Riyadh listings...")
        page.goto("https://sa.aqar.fm/عقارات/الرياض", wait_until="domcontentloaded", timeout=60000)
        
        # Scroll down to trigger background API fetches
        for _ in range(3):
            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(2)

        browser.close()

if __name__ == "__main__":
    run()
    df = pd.DataFrame(listings_data)
    df.to_csv("riyadh_raw_listings.csv", index=False, encoding="utf-8-sig")
    print(f"Captured {len(df)} listings to 'riyadh_raw_listings.csv'.")