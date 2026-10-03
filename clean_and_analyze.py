import pandas as pd
import re

def clean_and_analyze(input_file="riyadh_raw_listings.csv", output_file="riyadh_district_price_analysis.csv"):
    try:
        df = pd.read_csv(input_file)
        print(f"Loaded {len(df)} total rows from {input_file}.")
    except Exception as e:
        print(f"Error reading {input_file}: {e}")
        return

    # 1. Drop macro summary rows where area_sqm is missing/NaN
    df = df.dropna(subset=['area_sqm']).copy()

    # 2. Extract real district names from raw_info text safely
    def extract_district(row):
        raw_info = str(row.get('raw_info', ''))
        match = re.search(r'in Riyadh\s+([A-Za-z\s]+?)(?:\s+[§$¥€\d]|\s+at|\s+-\s+|$)', raw_info)
        if match:
            d_name = match.group(1).strip()
            d_name = re.sub(r'\s+(for\s+sale|for\s+rent|apartment|villa|floor|land).*$', '', d_name, flags=re.IGNORECASE).strip()
            if d_name and len(d_name) < 30:
                return d_name
        return "Riyadh General"

    df['district'] = df.apply(extract_district, axis=1)

    # 3. Clean numeric columns safely
    df['price_clean'] = pd.to_numeric(df['price_sar'], errors='coerce')
    df['area_clean'] = pd.to_numeric(df['area_sqm'], errors='coerce')

    # Drop missing values and filter out unreasonable anomalies/corruption bounds
    df = df.dropna(subset=['price_clean', 'area_clean']).copy()
    df = df[(df['area_clean'] >= 10) & (df['area_clean'] <= 100000)]
    df = df[df['price_clean'] >= 1000]

    if len(df) == 0:
        print("Warning: No valid rows passed the cleaning filters.")
        return

    print(f"Processing {len(df)} valid property listings...")

    # 4. Calculate Price per Square Meter
    df['sar_per_sqm'] = df['price_clean'] / df['area_clean']

    # 5. Group by District and aggregate statistics
    summary = df.groupby('district').agg(
        total_listings=('sar_per_sqm', 'count'),
        avg_price_sar=('price_clean', 'mean'),
        avg_area_sqm=('area_clean', 'mean'),
        avg_price_per_sqm=('sar_per_sqm', 'mean'),
        median_price_per_sqm=('sar_per_sqm', 'median')
    ).reset_index()

    summary = summary.round(2).sort_values(by='total_listings', ascending=False)
    summary.to_csv(output_file, index=False)

    print(f"\nSuccess! Saved results to {output_file}:")
    print(summary.to_string())

if __name__ == "__main__":
    clean_and_analyze()