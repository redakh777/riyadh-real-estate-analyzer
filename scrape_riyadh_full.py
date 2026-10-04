import os
import random
import time
import re
import argparse
import getpass
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote
import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests as cf_requests

MAX_ATTEMPTS = 5


def retry_after_seconds(value):
    if not value:
        return None
    try:
        return max(0, int(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0, int((retry_at - datetime.now(timezone.utc)).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return None


def save_checkpoint(new_listings, filename="riyadh_raw_listings.csv", overwrite=False):
    if not new_listings:
        return
    df = pd.DataFrame(new_listings)
    file_exists = os.path.isfile(filename) and not overwrite
    df.to_csv(
        filename,
        mode="a" if file_exists else "w",
        index=False,
        header=not file_exists,
        encoding="utf-8-sig",
    )
    print(f"Checkpoint saved: Wrote {len(df)} records to {filename}", flush=True)

def run_full_scraper(max_pages=50):
    api_key = os.getenv("SCRAPER_API_KEY")
    if not api_key and sys.stdin.isatty():
        api_key = getpass.getpass("ScraperAPI key (input hidden): ").strip()
    if not api_key:
        raise RuntimeError(
            "SCRAPER_API_KEY is not set. Set it in the environment, or run locally "
            "in an interactive terminal to enter it securely."
        )

    output_filename = "riyadh_raw_listings.csv"
    # Configure proxy session using ScraperAPI's proxy endpoint
    session = cf_requests.Session(impersonate="chrome124")
    proxy_url = f"http://scraperapi:{quote(api_key, safe='')}@proxy-server.scraperapi.com:8001"
    session.proxies = {
        "http": proxy_url,
        "https": proxy_url,
    }

    batch_listings = []
    output_initialized = False

    for page_num in range(1, max_pages + 1):
        target_url = (
            f"https://sa.aqar.fm/en/all/riyadh/{page_num}"
            if page_num > 1
            else "https://sa.aqar.fm/en/all/riyadh"
        )

        success = False
        attempts = 0

        while not success and attempts < MAX_ATTEMPTS:
            attempts += 1
            print(f"\n--- Scraping Page {page_num} (Attempt #{attempts}): {target_url} ---", flush=True)

            try:
                headers = {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
                    "Connection": "keep-alive",
                }

                # Direct request to target URL; traffic automatically tunnels through ScraperAPI proxy
                response = session.get(target_url, headers=headers, timeout=90)
                print(f"   -> Status Code: {response.status_code}", flush=True)

                if response.status_code == 407:
                    raise RuntimeError(
                        "ScraperAPI proxy returned HTTP 407 (proxy authentication failed). "
                        "Check that SCRAPER_API_KEY is valid and that your account supports proxy access."
                    )

                if response.status_code in (401, 403):
                    raise RuntimeError(
                        f"Request denied with HTTP {response.status_code} on page {page_num}; "
                        "check your ScraperAPI account and whether the target site permits access."
                    )

                if response.status_code == 429:
                    if attempts >= MAX_ATTEMPTS:
                        raise RuntimeError(
                            f"Rate limit persisted after {MAX_ATTEMPTS} attempts on page {page_num}; stopping."
                        )
                    delay = retry_after_seconds(response.headers.get("Retry-After"))
                    if delay is None:
                        delay = min(60 * (2 ** (attempts - 1)), 900)
                    print(f"Rate limited. Waiting {delay}s before retrying...", flush=True)
                    time.sleep(delay)
                    continue

                if response.status_code >= 500:
                    if attempts >= MAX_ATTEMPTS:
                        raise RuntimeError(
                            f"Server returned HTTP {response.status_code} after "
                            f"{MAX_ATTEMPTS} attempts on page {page_num}; stopping."
                        )
                    delay = min(15 * (2 ** (attempts - 1)), 300)
                    print(f"Server error. Waiting {delay}s before retrying...", flush=True)
                    time.sleep(delay)
                    continue

                if response.status_code != 200:
                    raise RuntimeError(
                        f"Unexpected HTTP {response.status_code} on page {page_num}; stopping."
                    )

                soup = BeautifulSoup(response.text, "html.parser")
                listing_links = soup.select('a[href*="/riyadh/"]')
                if not listing_links:
                    raise RuntimeError(
                        f"Received HTTP 200 but found no listing links on page {page_num}; "
                        "the page may have changed or returned a challenge page."
                    )
                
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
                print(f"   -> Successfully captured {page_count} items from page {page_num}.", flush=True)
                success = True
                break

            except cf_requests.exceptions.RequestException as e:
                if attempts >= MAX_ATTEMPTS:
                    error = str(e).replace(quote(api_key, safe=""), "[REDACTED]")
                    error = error.replace(api_key, "[REDACTED]")
                    raise RuntimeError(
                        f"Request failed after {MAX_ATTEMPTS} attempts on page {page_num} "
                        f"({type(e).__name__}: {error}); stopping."
                    ) from None
                delay = min(15 * (2 ** (attempts - 1)), 300)
                error = str(e).replace(quote(api_key, safe=""), "[REDACTED]")
                error = error.replace(api_key, "[REDACTED]")
                print(
                    f"Connection error on Page {page_num} ({type(e).__name__}: {error}). "
                    f"Waiting {delay}s before retrying...",
                    flush=True,
                )
                time.sleep(delay)

        if not success:
            raise RuntimeError(
                f"Page {page_num} was not scraped successfully after {MAX_ATTEMPTS} attempts; stopping."
            )

        if page_num % 10 == 0 and batch_listings:
            save_checkpoint(
                batch_listings,
                output_filename,
                overwrite=not output_initialized,
            )
            output_initialized = True
            batch_listings = []
            time.sleep(3.0)

        sleep_time = random.uniform(10.0, 20.0)
        print(f"Resting {sleep_time:.1f}s...", flush=True)
        time.sleep(sleep_time)

    if batch_listings:
        save_checkpoint(
            batch_listings,
            output_filename,
            overwrite=not output_initialized,
        )

    print("\nScraping session complete!", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Riyadh property listings.")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Maximum pages to scrape (default: 50; use 1 for a quick test).",
    )
    args = parser.parse_args()
    if args.max_pages < 1:
        parser.error("--max-pages must be at least 1")

    run_full_scraper(max_pages=args.max_pages)

    if os.path.isfile("riyadh_raw_listings.csv"):
        df = pd.read_csv("riyadh_raw_listings.csv")
        if not df.empty:
            df = df.drop_duplicates(subset=["link"])
            df.to_csv("riyadh_raw_listings.csv", index=False, encoding="utf-8-sig")
            print(f"Cleaned duplicates. Final dataset size: {len(df)} rows.", flush=True)