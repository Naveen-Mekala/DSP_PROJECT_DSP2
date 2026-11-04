import os
from datetime import date, timedelta
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Past Predictions", page_icon="📜", layout="wide")
st.title("📜 Past Predictions")
api_url = os.getenv("API_URL", "http://fastapi:8000")
today = date.today()
with st.form("prediction_filters"):
    col1, col2, col3 = st.columns(3)
    start_date = col1.date_input("Start date", value=today - timedelta(days=30))
    end_date = col2.date_input("End date", value=today)
    source = col3.selectbox("Prediction source", ["all", "webapp", "scheduled"])
    limit = st.number_input("Maximum records", min_value=1, max_value=1000, value=100)
    submitted = st.form_submit_button("Load predictions")

if submitted:
    if end_date < start_date:
        st.error("End date must be on or after start date.")
    else:
        try:
            response = requests.get(
                f"{api_url}/past-predictions",
                params={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "source": source,
                    "limit": int(limit)},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            if not data:
                st.info("No predictions match these filters.")
            else:
                df = pd.DataFrame(data)
                st.metric("Predictions returned", len(df))
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.download_button(
                    "Download results CSV",
                    df.to_csv(
                        index=False),
                    "past_predictions.csv",
                    "text/csv")
        except requests.RequestException as exc:
            st.error(f"Could not retrieve predictions from the API: {exc}")
        except (ValueError, TypeError) as exc:
            st.error(f"The API returned an unexpected response: {exc}")
else:
    st.caption("Choose a date range and source, then select Load predictions.")
