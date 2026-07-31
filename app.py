"""
app.py — Data Quality Scorecard Dashboard

Runs the audit live against your chosen database/profile and displays
results. Point DB_PATH at metal_prices.db or weather_risk.db (copy the
relevant .db file into this project folder, or adjust the path).

Requires: streamlit, pandas, plotly
Run locally with: streamlit run app.py
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from run_audit import run_audit, PROFILES
from dq_framework import compute_quality_score, summarize

st.set_page_config(page_title="Data Quality Scorecard", layout="wide")
st.title("🔍 Data Quality Scorecard")
st.caption("Automated completeness, uniqueness, validity, referential integrity, and outlier checks — reusable across any project database.")

with st.sidebar:
    st.markdown("### Select Dataset")
    dataset = st.selectbox("Which project to audit?", ["Metals Price Tracker", "Weather Risk Tracker"])
    db_map = {
        "Metals Price Tracker": ("metal_prices.db", "metal_prices", "metals"),
        "Weather Risk Tracker": ("weather_risk.db", "weather_snapshots", "weather"),
    }
    db_file, table_name, profile_key = db_map[dataset]
    st.caption(f"Table: `{table_name}` from `{db_file}`")

db_path = Path(__file__).parent / db_file

if not db_path.exists():
    st.warning(f"`{db_file}` not found in this folder. Copy it here from your {dataset} project repo to audit real data.")
else:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    conn.close()

    results = run_audit(df, PROFILES[profile_key])
    score = compute_quality_score(results)
    summary = summarize(results)

    col1, col2, col3 = st.columns(3)
    col1.metric("Overall Quality Score", f"{score} / 100")
    col2.metric("Rows Audited", len(df))
    col3.metric("Checks Failed", int((~summary["passed"]).sum()))

    st.divider()

    tab1, tab2 = st.tabs(["📋 Full Scorecard", "📊 Issues by Check Type"])

    with tab1:
        display_df = summary.copy()
        display_df.insert(0, "status", display_df["passed"].map({True: "✅", False: "❌"}))
        display_df = display_df.drop(columns=["passed"])
        st.dataframe(display_df, width="stretch", hide_index=True)

    with tab2:
        chart_df = summary.groupby("check", as_index=False)["issue_count"].sum()
        fig = px.bar(
            chart_df,
            x="check",
            y="issue_count",
            color="check",
            labels={"issue_count": "Total Issues Found", "check": "Check Type"},
            title="Issues Found by Check Type",
        )
        st.plotly_chart(fig, width="stretch")

    if (~summary["passed"]).any():
        st.error(f"⚠️ {int((~summary['passed']).sum())} check(s) found data quality issues — see the scorecard above.")
    else:
        st.success("✅ All checks passed — no data quality issues found.")