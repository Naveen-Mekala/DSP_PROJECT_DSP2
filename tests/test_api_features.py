"""Regression tests for consistent training/serving feature preparation."""
import pytest

from api.features import FEATURE_COLUMNS, feature_frame


def sample_record():
    return {
        "Athlete_ID": 10,
        "Day": 3,
        "Day_of_Week": 3,
        "Week": 1,
        "Age": 24,
        "Gender": "Male",
        "Sport_Type": "Endurance",
        "Training_Type": "Cardio",
        "Training_Duration_Min": 60,
        "Training_Intensity": 7.0,
        "Sleep_Duration_Hours": 7.5,
        "Caffeine_Intake_mg": 100,
        "Stress_Level": "Medium",
        "Resting_Heart_Rate": 62,
        "HRV_ms": 80,
        "Mood_Score": 7.0,
        "Muscle_Soreness": 3.0,
        "Energy_Level": 8.0,
        "Recovery_Score": 75.0,
    }


def test_feature_frame_keeps_categorical_stress_labels():
    frame = feature_frame([sample_record()])
    assert frame.loc[0, "Stress_Level"] == "Medium"
    assert frame["Stress_Level"].dtype == object


def test_model_features_match_training_columns():
    frame = feature_frame([sample_record()])
    # The model is trained without identifiers, target, or temporal columns.
    assert frame[FEATURE_COLUMNS].columns.tolist() == FEATURE_COLUMNS
    assert len(frame[FEATURE_COLUMNS].columns) == 14


def test_missing_required_feature_returns_422():
    from fastapi import HTTPException

    record = sample_record()
    record.pop("HRV_ms")
    with pytest.raises(HTTPException) as exc:
        feature_frame([record])
    assert exc.value.status_code == 422
