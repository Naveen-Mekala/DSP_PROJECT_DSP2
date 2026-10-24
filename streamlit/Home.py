import streamlit as st

st.set_page_config(
    page_title="Athlete Recovery Prediction",
    page_icon="🏃",
    layout="wide"
)

st.title("🏃 Athlete Recovery Prediction System")

st.markdown("---")

st.header("Data Science in Production Project")

st.write("""
Welcome to the Athlete Recovery Prediction System.

This application predicts an athlete's recovery score using a Machine Learning model.

### Features

- 🔮 Single Athlete Prediction
- 📂 Batch CSV Prediction
- 📜 Past Predictions
- 📊 Data Validation
- 🗄 PostgreSQL Database
- ⚡ FastAPI Backend
- 🤖 Machine Learning Model
""")

st.success("Select a page from the left sidebar to begin.")