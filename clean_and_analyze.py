import numpy as np
import pandas as pd


def analyze_riyadh_market(file_path="riyadh_raw_listings.csv"):
    df = pd.read_csv(file_path)

    # 1. Clean Numerical Fields
    df["price_sar"] = pd.to_numeric(df["price_sar"], errors="coerce")
    df["area_sqm"] = pd.to_numeric(df["area_sqm"], errors="coerce")

    # Drop missing values
    df_clean = df.dropna(subset=["price_sar", "area_sqm", "district"]).copy()

    # Filter realistic bounds (properties > 30 sqm and price > 50k SAR)
    df_clean = df_clean[
        (df_clean["price_sar"] > 50000) & (df_clean["area_sqm"] > 30)
    ]

    # 2. Calculate SAR / m²
    df_clean["price_per_sqm"] = df_clean["price_sar"] / df_clean["area_sqm"]

    # 3. Aggregate Metrics by Neighborhood/District
    summary = (
        df_clean.groupby("district")
        .agg(
            total_listings=("price_per_sqm", "count"),
            avg_price_sar=("price_sar", "mean"),
            avg_area_sqm=("area_sqm", "mean"),
            avg_price_per_sqm=("price_per_sqm", "mean"),
            median_price_per_sqm=("price_per_sqm", "median"),
        )
        .reset_index()
    )

    # Format numbers for clean presentation
    summary["avg_price_sar"] = summary["avg_price_sar"].round(0)
    summary["avg_area_sqm"] = summary["avg_area_sqm"].round(1)
    summary["avg_price_per_sqm"] = summary["avg_price_per_sqm"].round(2)
    summary["median_price_per_sqm"] = summary["median_price_per_sqm"].round(2)

    # Sort descending by price per square meter
    summary = summary.sort_values(by="avg_price_per_sqm", ascending=False)

    return summary


if __name__ == "__main__":
    summary_df = analyze_riyadh_market()
    summary_df.to_csv(
        "riyadh_district_price_analysis.csv", index=False, encoding="utf-8-sig"
    )

    print("\n--- Riyadh District Real Estate Analysis ---")
    print(summary_df.to_string(index=False))