"""
investigate_outliers.py

Follow-up to run_audit.py: when an outlier is flagged, this pulls it
into context — the days immediately before/after, plus a check for
whether OTHER tickers/locations were flagged on the same date. That
context is what actually tells you whether a flag is a real market
move (multiple series moving together, then reverting) versus a
genuine data error (isolated to one row, one series).

Usage:
    python investigate_outliers.py --db metal_prices.db --table metal_prices --profile metals

Requires: pandas, numpy
"""

import argparse
import sqlite3

import pandas as pd

from dq_framework import check_outliers_zscore
from run_audit import PROFILES


def find_flagged_dates(df: pd.DataFrame, value_col: str, group_col: str, threshold: float = 3.0) -> pd.DataFrame:
    """Returns one row per flagged outlier, with its z-score, across all groups."""
    flagged_rows = []
    for group_value, group_df in df.groupby(group_col):
        series = group_df[value_col].dropna()
        if series.std(ddof=0) == 0 or len(series) < 3:
            continue
        z = (series - series.mean()) / series.std(ddof=0)
        for idx in series[z.abs() > threshold].index:
            flagged_rows.append({
                group_col: group_value,
                "row_index": idx,
                "z_score": round(z.loc[idx], 2),
            })
    return pd.DataFrame(flagged_rows)


def show_context(df: pd.DataFrame, flagged: pd.DataFrame, group_col: str, date_col: str, value_col: str, window: int = 1):
    """For each flagged row, print it alongside `window` rows before/after in the same group."""
    for _, flag in flagged.iterrows():
        group_value = flag[group_col]
        group_df = df[df[group_col] == group_value].sort_values(date_col).reset_index(drop=True)
        match_idx = group_df.index[group_df[date_col] == df.loc[flag["row_index"], date_col]]
        if len(match_idx) == 0:
            continue
        i = match_idx[0]
        lo, hi = max(0, i - window), min(len(group_df), i + window + 1)

        print(f"\n--- {group_value} — flagged {df.loc[flag['row_index'], date_col]} (z={flag['z_score']}) ---")
        print(group_df.loc[lo:hi, [date_col, value_col]].to_string(index=False))


def check_same_date_pattern(df: pd.DataFrame, flagged_all: pd.DataFrame, date_col: str, group_col: str):
    """
    Cross-references flagged rows across DIFFERENT groups (tickers/locations)
    to check whether multiple series were flagged on the same date — a strong
    signal of a real shared event rather than an isolated data error.
    """
    flagged_dates = df.loc[flagged_all["row_index"], date_col].tolist()
    date_counts = pd.Series(flagged_dates).value_counts()
    shared_dates = date_counts[date_counts > 1]

    print("\n" + "=" * 60)
    print("CROSS-REFERENCE: were multiple series flagged on the same date?")
    print("=" * 60)
    if shared_dates.empty:
        print("No shared flagged dates — each outlier is isolated to a single series.")
        print("This leans toward investigating as a possible data error.")
    else:
        for date, count in shared_dates.items():
            print(f"{date}: flagged in {count} different series — consistent with a shared market event, not an isolated data error.")


def main():
    parser = argparse.ArgumentParser(description="Investigate flagged outliers in context.")
    parser.add_argument("--db", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--profile", required=True, choices=PROFILES.keys())
    parser.add_argument("--window", type=int, default=1, help="Rows of context before/after each flag")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    df = pd.read_sql(f"SELECT * FROM {args.table}", conn)
    conn.close()

    profile = PROFILES[args.profile]
    value_col = profile["outlier_col"]
    group_col = profile["outlier_groupby"]
    date_col = [c for c in df.columns if "date" in c.lower()][0]

    flagged = find_flagged_dates(df, value_col, group_col)

    if flagged.empty:
        print("No outliers flagged — nothing to investigate.")
        return

    print(f"Found {len(flagged)} flagged outlier(s). Showing context:")
    show_context(df, flagged, group_col, date_col, value_col, window=args.window)
    check_same_date_pattern(df, flagged, date_col, group_col)


if __name__ == "__main__":
    main()