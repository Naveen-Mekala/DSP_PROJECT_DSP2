"""Pydantic request and response contracts for prediction endpoints."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class AthleteInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    Age: int = Field(ge=0, le=120)
    Gender: Literal["Male", "Female", "Non-binary"]
    Sport_Type: str
    Training_Type: str
    Training_Duration_Min: float = Field(ge=0, le=1440)
    Training_Intensity: float = Field(ge=0, le=10)
    Sleep_Duration_Hours: float = Field(ge=0, le=24)
    Caffeine_Intake_mg: float = Field(ge=0, le=3000)
    Stress_Level: Literal["Low", "Medium", "High"]
    Resting_Heart_Rate: float = Field(ge=20, le=250)
    HRV_ms: float = Field(ge=0, le=500)
    Mood_Score: float = Field(ge=0, le=10)
    Muscle_Soreness: float = Field(ge=0, le=10)
    Energy_Level: float = Field(ge=0, le=10)


class PredictRequest(BaseModel):
    features: list[AthleteInput] = Field(min_length=1)
    source: Literal["webapp", "scheduled"] = "webapp"


class PredictionResult(BaseModel):
    features: dict[str, Any]
    prediction: float
    model_version: str


class PredictResponse(BaseModel):
    count: int
    model_version: str
    results: list[PredictionResult]


class SinglePredictResponse(BaseModel):
    prediction: float
    model_version: str
