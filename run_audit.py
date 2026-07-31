"""
run_audit.py

Runs a full data quality audit against a SQLite database table and
produces a scorecard. Pre-configured for the two live project databases
(metals price tracker, weather risk tracker) but works against any
SQLite table via --db and --table.

Usage:
    python run_audit.py --db metal_prices.db --table metal_prices --profile metals
    python run_audit.py --db weather_risk.db --table weather_snapshots --profile weather

Requires: pandas, numpy
    pip install pandas numpy
"""

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

from dq_framework import (
    check_completeness, check_uniqueness, check_validity_range,
    check_referential_integrity, check_outliers_zscore,
    compute_quality_score, summarize,
)

# Pre-built check configurations for the two existing live projects.
# Add a new entry here to audit a different table/dataset.
PROFILES = {
    "metals": {
        "completeness_cols": ["ticker", "price_date", "close_price"],
        "unique_key": ["ticker", "price_date"],
        "validity": [("close_price", 0, None)],  # prices must be positive
        "referential": ("ticker", {"HG=F", "PL=F", "PA=F", "GC=F"}),
        "outlier_col": "close_price",
        "outlier_groupby": "ticker",
    },
    "weather": {
        "completeness_cols": ["location_name", "observation_date", "temp_c", "wind_kmh", "precip_mm"],
        "unique_key": ["location_name", "observation_date"],
        "validity": [("temp_c", -60, 55), ("wind_kmh", 0, 300), ("precip_mm", 0, None)],
        "referential": ("location_name", {"Sudbury, ON", "Thunder Bay, ON", "Vancouver, BC", "Montreal, QC", "Toronto, ON"}),
        "outlier_col": "temp_c",
        "outlier_groupby": "location_name",
    },
}


def run_audit(df: pd.DataFrame, profile: dict) -> list:
    results = []
    results += check_completeness(df, profile["completeness_cols"])
    results.append(check_uniqueness(df, profile["unique_key"]))
    for col, min_val, max_val in profile["validity"]:
        results.append(check_validity_range(df, col, min_val, max_val))
    ref_col, valid_set = profile["referential"]
    results.append(check_referential_integrity(df, ref_col, valid_set))

    # Outlier detection per group (e.g. per ticker, per location) — running
    # it globally would be misleading since different tickers/locations
    # have very different baseline scales.
    outlier_col = profile["outlier_col"]
    group_col = profile["outlier_groupby"]
    for group_value, group_df in df.groupby(group_col):
        r = check_outliers_zscore(group_df, outlier_col, threshold=3.0)
        r.column = f"{outlier_col} ({group_value})"
        results.append(r)

    return results


def main():
    parser = argparse.ArgumentParser(description="Run a data quality audit against a SQLite table.")
    parser.add_argument("--db", required=True, help="Path to the SQLite database file")
    parser.add_argument("--table", required=True, help="Table name to audit")
    parser.add_argument("--profile", required=True, choices=PROFILES.keys(), help="Which check profile to use")
    parser.add_argument("--output", default=None, help="Optional path to write the scorecard as markdown")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    df = pd.read_sql(f"SELECT * FROM {args.table}", conn)
    conn.close()

    profile = PROFILES[args.profile]
    results = run_audit(df, profile)
    score = compute_quality_score(results)
    summary_df = summarize(results)

    print(f"\n{'='*60}")
    print(f"DATA QUALITY AUDIT — {args.table} ({len(df)} rows)")
    print(f"{'='*60}")
    print(f"Overall Quality Score: {score} / 100\n")
    print(summary_df.to_string(index=False))

    failed = summary_df[~summary_df["passed"]]
    if not failed.empty:
        print(f"\n⚠️  {len(failed)} check(s) found issues — see 'detail' column above.")
    else:
        print("\n✅ All checks passed.")

    if args.output:
        with open(args.output, "w") as f:
            f.write(f"# Data Quality Audit — {args.table}\n\n")
            f.write(f"**Rows audited:** {len(df)}\n\n")
            f.write(f"**Overall Quality Score:** {score} / 100\n\n")
            # Manual markdown table (avoids the optional `tabulate` dependency
            # that pandas.to_markdown() silently requires)
            cols = summary_df.columns.tolist()
            f.write("| " + " | ".join(cols) + " |\n")
            f.write("|" + "|".join(["---"] * len(cols)) + "|\n")
            for _, row in summary_df.iterrows():
                f.write("| " + " | ".join(str(row[c]) for c in cols) + " |\n")
        print(f"\nReport written to {args.output}")


if __name__ == "__main__":
    main()