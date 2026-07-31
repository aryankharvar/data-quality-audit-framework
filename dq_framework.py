"""
dq_framework.py

A reusable data quality auditing toolkit — completeness, uniqueness,
validity, referential integrity, and outlier detection. Works against
any Pandas DataFrame, so it can audit any dataset: a CSV, a SQL table,
or (as used here) your own live project databases.

Requires: pandas, numpy
    pip install pandas numpy
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class CheckResult:
    check_name: str
    column: str
    issue_count: int
    total_rows: int
    detail: str = ""

    @property
    def issue_pct(self) -> float:
        return round(100 * self.issue_count / self.total_rows, 2) if self.total_rows else 0.0

    @property
    def passed(self) -> bool:
        return self.issue_count == 0


def check_completeness(df: pd.DataFrame, columns: list[str] | None = None) -> list[CheckResult]:
    """Flags null/missing values per column."""
    columns = columns or df.columns.tolist()
    results = []
    for col in columns:
        null_count = int(df[col].isna().sum())
        results.append(CheckResult(
            check_name="Completeness",
            column=col,
            issue_count=null_count,
            total_rows=len(df),
            detail=f"{null_count} missing value(s)",
        ))
    return results


def check_uniqueness(df: pd.DataFrame, subset_cols: list[str]) -> CheckResult:
    """Flags duplicate rows based on a key column (or combination of columns)."""
    dup_count = int(df.duplicated(subset=subset_cols, keep=False).sum())
    return CheckResult(
        check_name="Uniqueness",
        column=" + ".join(subset_cols),
        issue_count=dup_count,
        total_rows=len(df),
        detail=f"{dup_count} row(s) share a duplicate key",
    )


def check_validity_range(df: pd.DataFrame, column: str, min_val=None, max_val=None) -> CheckResult:
    """Flags values outside a plausible range (e.g. negative prices, out-of-range temperatures)."""
    series = df[column].dropna()
    mask = pd.Series(False, index=series.index)
    if min_val is not None:
        mask |= series < min_val
    if max_val is not None:
        mask |= series > max_val
    issue_count = int(mask.sum())
    return CheckResult(
        check_name="Validity (Range)",
        column=column,
        issue_count=issue_count,
        total_rows=len(df),
        detail=f"{issue_count} value(s) outside [{min_val}, {max_val}]",
    )


def check_referential_integrity(df: pd.DataFrame, column: str, valid_values: set) -> CheckResult:
    """Flags values not present in an expected reference set (e.g. unknown ticker/location)."""
    invalid_mask = ~df[column].isin(valid_values)
    issue_count = int(invalid_mask.sum())
    bad_values = sorted(df.loc[invalid_mask, column].dropna().unique().tolist())
    return CheckResult(
        check_name="Referential Integrity",
        column=column,
        issue_count=issue_count,
        total_rows=len(df),
        detail=f"Unexpected values: {bad_values[:5]}" if bad_values else "All values recognized",
    )


def check_outliers_zscore(df: pd.DataFrame, column: str, threshold: float = 3.0) -> CheckResult:
    """Flags statistical outliers using a z-score threshold (default: 3 std deviations)."""
    series = df[column].dropna()
    if series.std(ddof=0) == 0 or len(series) < 3:
        return CheckResult("Outlier Detection (Z-score)", column, 0, len(df), "Not enough variance to test")
    z_scores = (series - series.mean()) / series.std(ddof=0)
    outliers = series[z_scores.abs() > threshold]
    return CheckResult(
        check_name="Outlier Detection (Z-score)",
        column=column,
        issue_count=len(outliers),
        total_rows=len(df),
        detail=f"{len(outliers)} value(s) beyond {threshold} std deviations",
    )


def compute_quality_score(results: list[CheckResult]) -> float:
    """
    Aggregate quality score (0-100). Each check contributes based on the
    fraction of rows that passed. A dataset with zero issues across all
    checks scores 100.
    """
    if not results:
        return 100.0
    per_check_scores = [100 - min(r.issue_pct, 100) for r in results]
    return round(sum(per_check_scores) / len(per_check_scores), 1)


def summarize(results: list[CheckResult]) -> pd.DataFrame:
    """Convert a list of CheckResults into a flat DataFrame for reporting/display."""
    return pd.DataFrame([
        {
            "check": r.check_name,
            "column": r.column,
            "issue_count": r.issue_count,
            "total_rows": r.total_rows,
            "issue_pct": r.issue_pct,
            "passed": r.passed,
            "detail": r.detail,
        }
        for r in results
    ])
