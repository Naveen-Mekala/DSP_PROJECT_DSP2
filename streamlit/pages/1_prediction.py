import streamlit as st
import requests
import os
import pandas as pd

st.set_page_config(
    page_title="Athlete Prediction",
    page_icon="🔮",
    layout="wide"
)

st.title("🔮 Athlete Recovery Prediction")

st.write("Fill in the athlete details below and click **Predict**.")

st.markdown("---")

with st.form("prediction_form"):

    age = st.number_input(
        "Age",
        min_value=18,
        max_value=60,
        value=25
    )

    gender = st.selectbox(
        "Gender",
        ["Male", "Female", "Non-binary"]
    )

    sport = st.selectbox(
        "Sport Type",
        [
            "Endurance",
            "Strength",
            "Team Sport",
            "Mixed",
            "Combat"
        ]
    )

    training_type = st.selectbox(
        "Training Type",
        [
            "Cardio",
            "Strength",
            "HIIT",
            "Rest",
            "Yoga"
        ]
    )

    duration = st.number_input(
        "Training Duration (Minutes)",
        min_value=1,
        max_value=300,
        value=90
    )

    intensity = st.slider(
        "Training Intensity",
        1,
        10,
        7
    )

    sleep = st.slider(
        "Sleep Duration (Hours)",
        0.0,
        12.0,
        8.0
    )

    caffeine = st.number_input(
        "Caffeine Intake (mg)",
        min_value=0,
        max_value=500,
        value=100
    )

    stress = st.selectbox(
        "Stress Level",
        ["Low", "Medium", "High"],
        index=0,
    )

    heart_rate = st.number_input(
        "Resting Heart Rate",
        min_value=30,
        max_value=120,
        value=60
    )

    hrv = st.number_input(
        "HRV (ms)",
        min_value=10,
        max_value=200,
        value=85
    )

    mood = st.slider(
        "Mood Score",
        1,
        10,
        8
    )

    soreness = st.slider(
        "Muscle Soreness",
        1,
        10,
        2
    )

    energy = st.slider(
        "Energy Level",
        1,
        10,
        9
    )

    submit = st.form_submit_button("🚀 Predict Recovery Score")

# ---------------------------------------------------
# Prediction
# ---------------------------------------------------

if submit:

    api_url = os.getenv("API_URL", "http://fastapi:8000")
    payload = {
        "Age": age,
        "Gender": gender,
        "Sport_Type": sport,
        "Training_Type": training_type,
        "Training_Duration_Min": duration,
        "Training_Intensity": intensity,
        "Sleep_Duration_Hours": sleep,
        "Caffeine_Intake_mg": caffeine,
        "Stress_Level": stress,
        "Resting_Heart_Rate": heart_rate,
        "HRV_ms": hrv,
        "Mood_Score": mood,
        "Muscle_Soreness": soreness,
        "Energy_Level": energy
    }

    try:

        response = requests.post(
            f"{api_url}/predict",
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:

            prediction = response.json()["prediction"]
            st.success("Prediction completed successfully!")

            st.metric(
                label="🏃 Predicted Recovery Score",
                value=f"{prediction:.2f}"
            )
            result_row = {
                **payload,
                "Predicted_Recovery_Score": prediction,
                "model_version": response.json().get("model_version", "unknown"),
            }
            st.subheader("Features and prediction")
            st.dataframe(pd.DataFrame([result_row]), use_container_width=True, hide_index=True)

            if prediction >= 80:
                st.success("Excellent Recovery Expected ✅")

            elif prediction >= 60:
                st.warning("Moderate Recovery ⚠️")

            else:
                st.error("Poor Recovery Expected ❌")

        else:
            st.error("Prediction Failed")
            st.write(response.text)

    except Exception as e:
        st.error("Could not connect to FastAPI Server.")
        st.exception(e)
