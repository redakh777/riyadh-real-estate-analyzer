import os
import re
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Set visual style for professional portfolio plots
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'figure.autolayout': True})

def clean_and_analyze(input_file="riyadh_raw_listings.csv", output_file="riyadh_district_price_analysis.csv", cleaned_output_file="riyadh_cleaned_listings.csv"):
    if not os.path.isfile(input_file):
        raise FileNotFoundError(
            f"{input_file} not found. Run the scraper first or provide the raw listings file."
        )

    print("📂 Loading raw dataset...")
    try:
        df = pd.read_csv(input_file)
        print(f"   -> Loaded {len(df)} total rows from {input_file}.")
    except Exception as e:
        print(f"❌ Error reading {input_file}: {e}")
        return

    # 1. Drop macro summary rows where area_sqm is missing/NaN
    df = df.dropna(subset=['area_sqm']).copy()

    # 2. Extract real district names from raw_info text safely
    print("🏙️ Extracting neighborhood and district names...")
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

    # 3. Clean numeric columns safely & filter out anomalies
    print("🧹 Cleaning numeric bounds and outliers...")
    df['price_clean'] = pd.to_numeric(df['price_sar'], errors='coerce')
    df['area_clean'] = pd.to_numeric(df['area_sqm'], errors='coerce')

    df = df.dropna(subset=['price_clean', 'area_clean']).copy()
    df = df[(df['area_clean'] >= 10) & (df['area_clean'] <= 100000)]
    df = df[df['price_clean'] >= 1000]

    if len(df) == 0:
        raise ValueError("No valid listings passed the general-analysis cleaning filters.")

    print(f"   -> Processing {len(df)} valid property listings...")

    # 4. Feature Engineering: Price per Square Meter
    df['sar_per_sqm'] = df['price_clean'] / df['area_clean']

    # Map back standard column names for the cleaned dataset export
    df['price_sar'] = df['price_clean']
    df['area_sqm'] = df['area_clean']
    df['price_per_sqm'] = df['sar_per_sqm']

    # Save master cleaned dataset
    df.to_csv(cleaned_output_file, index=False, encoding="utf-8-sig")
    print(f"💾 Cleaned master dataset saved to {cleaned_output_file}")

    # 5. Group by District and aggregate statistics (Matching your exact schema)
    summary = df.groupby('district').agg(
        total_listings=('sar_per_sqm', 'count'),
        avg_price_sar=('price_clean', 'mean'),
        avg_area_sqm=('area_clean', 'mean'),
        avg_price_per_sqm=('sar_per_sqm', 'mean'),
        median_price_per_sqm=('sar_per_sqm', 'median')
    ).reset_index()

    summary = summary.round(2).sort_values(by='total_listings', ascending=False)
    summary.to_csv(output_file, index=False, encoding="utf-8-sig")

    print(f"\n📊 Summary Statistics & District Analysis saved to {output_file}:")
    print(summary.head(10).to_string(index=False))

    # 6. Generating Visualizations for your GitHub README
    print("\n📈 Generating portfolio visualization charts...")

    # Chart 1: Price Distribution Histogram (Excluding Top 5% Outliers for readability)
    plt.figure(figsize=(10, 6))
    price_cap = df["price_clean"].quantile(0.95)
    sns.histplot(df[df["price_clean"] <= price_cap]["price_clean"], kde=True, color="teal")
    plt.title("Riyadh Real Estate Price Distribution (Excl. Top 5% Outliers)", fontsize=14, fontweight="bold")
    plt.xlabel("Price (SAR)", fontsize=12)
    plt.ylabel("Number of Listings", fontsize=12)
    plt.savefig("riyadh_price_distribution.png", dpi=300)
    plt.close()

    # Chart 2: Top Districts by Average Price Bar Chart (Filtering for sample size >= 2)
    top_districts = summary[summary["total_listings"] >= 2].sort_values(by="avg_price_sar", ascending=False).head(10)

    plt.figure(figsize=(12, 6))
    ax = sns.barplot(data=top_districts, x="avg_price_sar", y="district", palette="viridis")
    plt.title("Top Districts in Riyadh by Average Price", fontsize=14, fontweight="bold")
    plt.xlabel("Average Price (SAR)", fontsize=12)
    plt.ylabel("District", fontsize=12)
    
    # Annotate values on bars
    for p in ax.patches:
        width = p.get_width()
        if width > 0:
            ax.annotate(f"SAR {width:,.0f}",
                        (width, p.get_y() + p.get_height() / 2.),
                        xytext=(5, 0), textcoords="offset points",
                        ha="left", va="center", fontsize=9, fontweight="bold")

    plt.savefig("riyadh_top_districts.png", dpi=300)
    plt.close()

    print("🖼️ Charts successfully generated and saved: 'riyadh_price_distribution.png' & 'riyadh_top_districts.png'")
    print("\n✨ Pipeline Complete! All datasets and visual assets ready for GitHub.")

if __name__ == "__main__":
    clean_and_analyze()