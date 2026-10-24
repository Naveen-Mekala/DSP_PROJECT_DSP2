import streamlit as st
import subprocess

st.set_page_config(
    page_title="Validation",
    page_icon="✅",
    layout="wide"
)

st.title("✅ Great Expectations Validation")

st.write(
    "Validate the corrupted athlete dataset using Great Expectations."
)

st.markdown("---")

if st.button("🚀 Run Validation"):

    with st.spinner("Running Great Expectations..."):

        result = subprocess.run(
            ["python", "validation/run_validation.py"],
            capture_output=True,
            text=True
        )

    if result.returncode == 0:
        st.success("Validation run completed; all expectations passed.")
    else:
        st.warning("Validation run completed with failed expectations or an execution error.")

    if result.stdout:
        st.code(result.stdout)
    if result.stderr:
        st.code(result.stderr)

st.markdown("---")

st.info(
"""
Validation Checks

✅ Athlete_ID exists

✅ Athlete_ID is not null

✅ Athlete_ID is unique

✅ Age between 18-60

✅ Recovery Score between 0-100

✅ Gender values valid

✅ Sleep Duration valid

✅ Mood Score valid

✅ Energy Level valid

✅ Training Duration valid
"""
)