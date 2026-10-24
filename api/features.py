"""Shared feature schema and preprocessing for inference requests."""
import pandas as pd
from fastapi import HTTPException

FEATURE_COLUMNS = [
    "Age", "Gender", "Sport_Type", "Training_Type", "Training_Duration_Min",
    "Training_Intensity", "Sleep_Duration_Hours", "Caffeine_Intake_mg",
    "Stress_Level", "Resting_Heart_Rate", "HRV_ms", "Mood_Score",
    "Muscle_Soreness", "Energy_Level",
]


def feature_frame(records):
    """Prepare rows without changing the categorical values used during training."""
    df = pd.DataFrame(records)
    for ignored in ("Athlete_ID", "Recovery_Score"):
        if ignored in df.columns:
            df = df.drop(columns=[ignored])
    for temporal, default in (("Day", 1), ("Week", 1), ("Day_of_Week", "Monday")):
        if temporal not in df.columns:
            df[temporal] = default
    # Stress_Level is categorical in the source data (Low/Medium/High); preserve labels.
    missing = [column for column in FEATURE_COLUMNS if column not in df.columns]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required feature columns: {missing}")
    return df
