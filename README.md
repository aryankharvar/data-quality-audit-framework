# 🔍 Data Quality Audit Framework

A reusable Python/SQL toolkit for auditing dataset quality — completeness, uniqueness, validity, referential integrity, and statistical outlier detection — with a scorecard dashboard. Built to audit real, production data from two of my own live pipelines rather than a downloaded sample dataset.

---

## 📊 Overview

Most portfolio projects assume the input data is already clean. This one checks that assumption directly: it's a config-driven framework that scans any tabular dataset for the kinds of issues that actually break downstream analysis — missing values, duplicate keys, out-of-range values, unrecognized categories, and statistical anomalies — and produces a quality score plus a detailed, per-check breakdown.

It's applied here against the live SQLite databases behind my [Metals Price Tracker](https://github.com/aryankharvar/metals-price-tracker) and [Weather Risk Tracker](https://github.com/aryankharvar/weather-risk-tracker) projects.

## 🛠️ Tech Stack

- **Language:** Python (Pandas, NumPy)
- **Checks:** Completeness, Uniqueness, Validity (range), Referential Integrity, Outlier Detection (z-score)
- **Dashboard:** Streamlit, Plotly
- **Data sources audited:** SQLite (production databases from two other live projects)

## 🧩 Checks Implemented

| Check | What it catches | Example |
|---|---|---|
| Completeness | Missing/null values | A row with no recorded price |
| Uniqueness | Duplicate keys | Two rows for the same ticker on the same date |
| Validity (Range) | Out-of-bounds values | A negative price, a temperature of -90°C |
| Referential Integrity | Unrecognized category values | A ticker not in the expected set |
| Outlier Detection (Z-score) | Statistically anomalous values, computed per group | A price 3+ standard deviations from that ticker's mean |

Each check returns a `CheckResult` (issue count, % of rows affected, pass/fail, detail), and an overall 0-100 quality score is computed as the average pass rate across all checks.

Flagged outliers aren't treated as automatic errors — `investigate_outliers.py` pulls each flag into context (neighboring values, and whether other series were flagged on the same date) so a flag can be confirmed as either a real anomaly or a genuine, explainable event. See **Sample Findings** below for a worked example against real production data.

## ⚠️ A Known Limitation (Documented, Not Hidden)

Z-score outlier detection is unreliable on very small samples — a single extreme value inflates both the mean and standard deviation it's being measured against, which can mask the outlier from itself. This is noted directly in the code (`dq_framework.py`) rather than silently shipped as a black box. For groups under ~10 rows, treat outlier results with caution.

## 📈 Sample Findings — Real Production Data

Ran against `metal_prices.db` (528 rows, collected by the automated daily pipeline behind the Metals Price Tracker):

```
Overall Quality Score: 99.8 / 100

✅ Completeness       — 0 missing values across ticker, price_date, close_price
✅ Uniqueness         — 0 duplicate (ticker, date) pairs
✅ Validity (Range)   — 0 invalid (negative) prices
✅ Referential Integrity — all tickers recognized
⚠️ Outlier Detection  — 1 flagged value in PA=F (Palladium), 1 flagged value in PL=F (Platinum)
```

The zero-issue results across completeness, uniqueness, validity, and referential integrity are a direct validation of the deduplication logic (`UNIQUE(ticker, price_date)` constraint) built into the pipeline months earlier — it's held up cleanly across 528 rows of real, unattended daily collection.

**On the two flagged outliers:** `investigate_outliers.py` shows both occurred on the same date (2026-01-26) across Palladium (z=3.21) and Platinum (z=3.44) — two independent tickers spiking together, then reverting the next day. Since independent data errors would be expected to hit tickers randomly rather than in tandem, this cross-reference supports a genuine one-day market volatility event rather than a pipeline error. No corrective action taken.

## 🚀 How to Run

**Note:** the `.db` files aren't included in this repo — they belong to the source projects and are excluded via `.gitignore` to avoid stale, out-of-sync duplicates. Copy a fresh one in before running an audit:

```bash
pip install -r requirements.txt

# copy real data in from either live project (adjust path to where you cloned them)
cp ../metals-price-tracker/metal_prices.db .
# or
cp ../weather-risk-tracker/weather_risk.db .

# CLI audit against a specific database/table
python run_audit.py --db metal_prices.db --table metal_prices --profile metals --output metals_report.md

# Investigate any flagged outliers in context (neighboring days + cross-ticker date matching)
python investigate_outliers.py --db metal_prices.db --table metal_prices --profile metals

# Interactive dashboard
streamlit run app.py
```

To audit a new dataset, add a new entry to the `PROFILES` dict in `run_audit.py` specifying which columns to check and what "valid" looks like for that data.

## 📁 Repository Structure

```
data_quality_audit/
├── dq_framework.py           # reusable check functions (completeness, uniqueness, validity, etc.)
├── run_audit.py                # CLI runner + pre-built profiles for existing projects
├── investigate_outliers.py     # contextualizes flagged outliers — neighboring days + cross-ticker date matching
├── app.py                       # Streamlit scorecard dashboard
├── requirements.txt
└── README.md
```

## 📌 Future Improvements

- Add a SQL-native version of each check (for auditing directly inside a database without pulling data into Pandas first)
- Wire this into the Metals/Weather GitHub Actions workflows as a pre-commit validation step, so bad data gets flagged before it's ever committed
- Add trend tracking — quality score over time, not just a single snapshot

## 📄 License

MIT License

# 👨‍💻 Author

**Aryan Kharvar**

**M.Sc. Computational Sciences**

Data Analytics | Business Intelligence | Power BI | SQL | Python

💼 LinkedIn: [Aryan Kharvar](https://www.linkedin.com/in/aryankharvar)
