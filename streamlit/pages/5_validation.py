"""Run the same Great Expectations validation as the ingestion pipeline on any CSV file."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Validation", page_icon="✅", layout="wide")
st.title("✅ Great Expectations Validation")
st.write("Validate a file with exactly the rules used by the ingestion pipeline "
         "(schema & types suite + content suite).")

samples = {p.name: p for p in sorted((ROOT / "data" / "demo").glob("*.csv"))}
samples.update({p.name: p for p in sorted((ROOT / "data" / "clean").glob("*.csv"))})
uploaded = st.file_uploader("Upload a CSV file", type=["csv"])
choice = st.selectbox("…or pick a sample file", ["—"] + list(samples))

frame, label = None, None
if uploaded is not None:
    frame, label = pd.read_csv(uploaded), uploaded.name
elif choice != "—":
    frame, label = pd.read_csv(samples[choice]), choice

if frame is not None and st.button(f"🚀 Validate {label}"):
    from scripts.gx_validation import run_validation

    with st.spinner("Running Great Expectations..."):
        result = run_validation(frame)
    invalid = result["invalid_row_indices"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", result["total_rows"])
    c2.metric("Invalid rows", len(invalid), f"{result['invalid_percentage']}%", delta_color="inverse")
    c3.metric("Criticality", result["criticality"])
    c4.metric("Expectations passed", f"{result['expectations_passed']}/{result['expectations_evaluated']}")
    st.subheader("Errors by category")
    st.bar_chart(pd.Series(result["category_counts"], name="errors"))
    if invalid:
        st.subheader("Rows with problems")
        bad = frame.loc[frame.index.isin(invalid)].copy()
        bad.insert(0, "dq_errors", [result["row_errors"].get(i, "schema") for i in bad.index])
        st.dataframe(bad, use_container_width=True)
    else:
        st.success("All rows passed every expectation.")
    st.markdown(f"[Open the Data Docs report]({result['data_docs_path']})")
