# Riyadh Real Estate Market Analyzer 🏙️️

A Python-based web scraper and data analysis pipeline that extracts real estate property listings across Riyadh, cleans numerical metrics, and calculates the average price per square meter ($\text{SAR/m}^2$) grouped by neighborhood district.

## Key Features
- **Anti-Bot WAF Clearance**: Uses Playwright browser automation and `playwright-stealth` to bypass edge firewall anti-bot challenges (Cloudflare / MXP WAF).
- **Attribute Extraction**: Parses property prices (SAR), surface area ($\text{m}^2$), listing titles, and district locations.
- **Data Cleaning & Analysis**: Cleans raw text attributes, filters invalid records, and computes average and median $\text{SAR/m}^2$ grouped by Riyadh district using Pandas.

## Repository Deliverables
- `scrape_riyadh_full.py`: Production scraper script utilizing Playwright browser automation.
- `clean_and_analyze.py`: Data cleaning pipeline calculating neighborhood price metrics.
- `riyadh_district_price_analysis.csv`: Processed output dataset grouped by district.
- `riyadh_raw_listings.csv`: Raw extracted listing dataset.
- `requirements.txt`: Python package dependency list.

## Tech Stack
- Python 3
- `playwright` & `playwright-stealth`
- `pandas` & `numpy`

## Quick Start / Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/redakh777/riyadh-real-estate-analyzer.git](https://github.com/redakh777/riyadh-real-estate-analyzer.git)
   cd riyadh-real-estate-analyzer
