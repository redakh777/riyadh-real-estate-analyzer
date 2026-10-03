import os
import random
import time
import re
import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests as cf_requests

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

    # Use curl_cffi session with explicit Chrome TLS fingerprint impersonation
    session = cf_requests.Session(impersonate="chrome124")
    batch_listings = []

    for page_num in range(1, max_pages + 1):
        target_url = (
            f"https://sa.aqar.fm/en/all/riyadh/{page_num}"
            if page_num > 1
            else "https://sa.aqar.fm/en/all/riyadh"
        )

        success = False
        attempts = 0

        while not success and attempts < 5:
            attempts += 1
            print(f"\n--- Scraping Page {page_num} (Attempt #{attempts}): {target_url} ---", flush=True)

            try:
                headers = {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
                    "Referer": "https://sa.aqar.fm/",
                    "Connection": "keep-alive",
                }

                response = session.get(target_url, headers=headers, timeout=30)
                print(f"   -> Status Code: {response.status_code}", flush=True)

                if response.status_code == 403 or "blocked" in response.text.lower() or "حظر" in response.text:
                    print(f"🚨 Cloudflare block triggered on Page {page_num}!", flush=True)
                    backoff = 15 * attempts
                    print(f"💤 Sleeping for {backoff}s before retrying...", flush=True)
                    time.sleep(backoff)
                    continue

                if response.status_code != 200:
                    print(f"⚠️ Unexpected status code: {response.status_code}. Retrying...", flush=True)
                    time.sleep(5)
                    continue

                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                listing_links = soup.select('a[href*="/riyadh/"]')
                
                page_count = 0
                page_listings = []

                for link in listing_links:
                    try:
                        raw_text = link.get_text(strip=True)
                        href = link.get("href")

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
                break

            except Exception as e:
                print(f"⚠️ Connection error on Page {page_num}: {e}. Retrying...", flush=True)
                time.sleep(10)

        if page_num % 10 == 0 and batch_listings:
            save_checkpoint(batch_listings, output_filename)
            batch_listings = []
            time.sleep(5.0)

        sleep_time = random.uniform(3.0, 6.0)
        print(f"⏳ Resting {sleep_time:.1f}s...", flush=True)
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
            print(f"🧹 Cleaned duplicates. Final dataset size: {len(df)} rows.", flush=True)