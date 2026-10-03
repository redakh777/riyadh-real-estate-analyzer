import time
from bs4 import BeautifulSoup
import pandas as pd
import requests

API_KEY = "12ebdc20659273de164b84c57b0e51db"  # Replace with your ScraperAPI key
API_ENDPOINT = "https://api.scraperapi.com"

# Target the public web listing directory for Riyadh real estate
BASE_TARGET_URL = "https://sa.aqar.fm/عقارات/الرياض"


def fetch_riyadh_listings_via_api(pages=3):
    raw_listings = []

    for page in range(1, pages + 1):
        # Construct public page URL (Page 1 vs Page 2+)
        target_url = (
            f"{BASE_TARGET_URL}/{page}" if page > 1 else BASE_TARGET_URL
        )
        print(f"Scraping Page {page}: {target_url} ...")

        api_params = {
            "api_key": API_KEY,
            "url": target_url,
            "render": "true",  # Renders dynamic elements & bypasses Cloudflare
            "country_code": "sa",  # Ensures Saudi Arabian residential IP routing
        }

        try:
            response = requests.get(
                API_ENDPOINT, params=api_params, timeout=60
            )

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                # Parse listing cards on the rendered HTML page
                # (Aqar uses listing cards with links containing property IDs)
                listing_cards = soup.find_all("div", class_=lambda x: x and "listing" in x.lower()) if soup.find_all("div") else []

                # Fallback link search if card class names are dynamically obfuscated
                if not listing_cards:
                    listing_cards = soup.find_all("a", href=lambda href: href and "/عرض-" in href)

                print(f"  Found {len(listing_cards)} raw listing elements on Page {page}.")

                for card in listing_cards:
                    # Extract text content cleanly
                    text_content = card.get_text(separator=" ", strip=True)

                    # Extract price, area, and district from the element text
                    raw_listings.append({
                        "raw_info": text_content,
                        "page_source": page
                    })

            else:
                print(f"  Failed Page {page}. Status Code: {response.status_code}")

        except Exception as e:
            print(f"  Error on page {page}: {e}")

        time.sleep(1.5)

    return raw_listings


if __name__ == "__main__":
    scraped_data = fetch_riyadh_listings_via_api(pages=3)
    df_raw = pd.DataFrame(scraped_data)
    df_raw.to_csv("riyadh_raw_listings.csv", index=False, encoding="utf-8-sig")
    print(f"\nDone! Saved {len(df_raw)} raw items to 'riyadh_raw_listings.csv'.")