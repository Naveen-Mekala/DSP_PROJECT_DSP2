"""CSV batch prediction UI. CSV bytes are parsed locally and sent as JSON records."""
import os
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Batch Prediction", page_icon="📄", layout="wide")
st.title("📄 Batch Prediction")
st.write("Upload a CSV containing athlete features. The target label is optional and ignored.")
api_url = os.getenv("API_URL", "http://fastapi:8000")
required_columns = [
    "Age", "Gender", "Sport_Type", "Training_Type", "Training_Duration_Min",
    "Training_Intensity", "Sleep_Duration_Hours", "Caffeine_Intake_mg",
    "Stress_Level", "Resting_Heart_Rate", "HRV_ms", "Mood_Score",
    "Muscle_Soreness", "Energy_Level",
]
uploaded_file = st.file_uploader("Choose CSV file", type=["csv"])
if uploaded_file is not None:
    try:
        input_df = pd.read_csv(uploaded_file)
        st.subheader("Input preview")
        st.dataframe(input_df.head(10), use_container_width=True)
        if st.button("Run batch prediction", type="primary"):
            missing = [column for column in required_columns if column not in input_df.columns]
            if missing:
                st.error(f"CSV is missing required columns: {', '.join(missing)}")
            elif input_df.empty:
                st.warning("The uploaded CSV contains no rows.")
            else:
                # Strip labels/identifiers; the API receives data, never a local file path.
                features_df = input_df.drop(columns=["Recovery_Score", "Athlete_ID"], errors="ignore")
                records = features_df.astype(object).where(
                    pd.notna(features_df), None).to_dict(
                    orient="records")
                with st.spinner("Requesting predictions from FastAPI..."):
                    response = requests.post(
                        f"{api_url}/predict",
                        json={"features": records, "source": "webapp"},
                        timeout=120,
                    )
                response.raise_for_status()
                payload = response.json()
                results = payload.get("results", [])
                if not results:
                    st.warning("The API returned no predictions.")
                else:
                    result_df = pd.DataFrame([{
                        **item.get("features", {}),
                        "Predicted_Recovery_Score": item.get("prediction"),
                        "model_version": item.get("model_version", payload.get("model_version")),
                    } for item in results])
                    st.success(f"Predicted {len(result_df)} rows")
                    st.dataframe(result_df, use_container_width=True, hide_index=True)
                    st.download_button(
                        "Download predictions CSV", result_df.to_csv(
                            index=False), "batch_predictions.csv", "text/csv")
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        st.error(f"The uploaded file is not a readable CSV: {exc}")
    except requests.RequestException as exc:
        st.error(f"The prediction API could not process this file: {exc}")
    except (ValueError, TypeError) as exc:
        st.error(f"Could not interpret the API response: {exc}")
