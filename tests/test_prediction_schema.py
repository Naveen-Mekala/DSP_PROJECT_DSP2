import pytest
from pydantic import ValidationError
from api.schemas.prediction import AthleteInput, PredictRequest, PredictResponse

VALID = {
    "Age": 25, "Gender": "Male", "Sport_Type": "Endurance", "Training_Type": "Cardio",
    "Training_Duration_Min": 90, "Training_Intensity": 7, "Sleep_Duration_Hours": 8,
    "Caffeine_Intake_mg": 100, "Stress_Level": "Medium", "Resting_Heart_Rate": 60,
    "HRV_ms": 85, "Mood_Score": 8, "Muscle_Soreness": 2, "Energy_Level": 9,
}


def test_athlete_input_validates():
    assert AthleteInput(**VALID).Age == 25


def test_athlete_input_rejects_out_of_range_age():
    with pytest.raises(ValidationError):
        AthleteInput(**{**VALID, "Age": 200})


def test_prediction_source_is_validated():
    assert PredictRequest(features=[VALID], source="scheduled").source == "scheduled"
    with pytest.raises(ValidationError):
        PredictRequest(features=[VALID], source="batch")


def test_prediction_response_schema():
    response = PredictResponse(count=1, model_version="1", results=[
        {"features": VALID, "prediction": 72.5, "model_version": "1"}
    ])
    assert response.count == 1
    assert response.results[0].prediction == 72.5


def test_stress_level_must_match_training_categories():
    with pytest.raises(ValidationError):
        AthleteInput(**{**VALID, "Stress_Level": 5})


def test_non_binary_gender_is_supported():
    athlete = AthleteInput(**{**VALID, "Gender": "Non-binary"})
    assert athlete.Gender == "Non-binary"
