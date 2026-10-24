"""Prediction history dashboard backed exclusively by the FastAPI service."""
import os
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
st.title("📊 Prediction Dashboard")
api_url = os.getenv("API_URL", "http://fastapi:8000")

try:
    response = requests.get(f"{api_url}/past-predictions", params={"limit": 1000}, timeout=15)
    response.raise_for_status()
    data = response.json()
except requests.RequestException as exc:
    st.error(f"Could not connect to the prediction API: {exc}")
    st.stop()
except ValueError as exc:
    st.error(f"The prediction API returned invalid JSON: {exc}")
    st.stop()

if not data:
    st.info("No predictions have been recorded yet.")
    st.stop()

df = pd.DataFrame(data)
if "Prediction" not in df.columns:
    st.error("The API response is missing the Prediction column.")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Total Predictions", len(df))
col2.metric("Average Prediction", round(df["Prediction"].mean(), 2))
col3.metric("Highest Prediction", round(df["Prediction"].max(), 2))

st.divider()
st.subheader("Prediction Distribution")
st.plotly_chart(px.histogram(df, x="Prediction", nbins=20, title="Recovery Score Distribution"), use_container_width=True)

if "Sport_Type" in df.columns:
    st.subheader("Sport Type")
    st.plotly_chart(px.pie(df, names="Sport_Type", title="Sport Type Distribution"), use_container_width=True)

if "Gender" in df.columns:
    st.subheader("Gender Distribution")
    gender_counts = df["Gender"].value_counts().rename_axis("Gender").reset_index(name="Count")
    st.plotly_chart(px.bar(gender_counts, x="Gender", y="Count", title="Gender Count"), use_container_width=True)

st.subheader("Prediction Table")
st.dataframe(df, use_container_width=True, hide_index=True)
