from sqlalchemy import Column, Integer, Float, String, DateTime, JSON, Text
from sqlalchemy.sql import func
from database.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    Age = Column(Integer)
    Gender = Column(String)
    Sport_Type = Column(String)
    Training_Type = Column(String)
    Training_Duration_Min = Column(Float)
    Training_Intensity = Column(Integer)
    Sleep_Duration_Hours = Column(Float)
    Caffeine_Intake_mg = Column(Float)
    Stress_Level = Column(String)
    Resting_Heart_Rate = Column(Float)
    HRV_ms = Column(Float)
    Mood_Score = Column(Float)
    Muscle_Soreness = Column(Float)
    Energy_Level = Column(Float)
    Prediction = Column(Float, nullable=False)
    prediction_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source = Column(String(20), nullable=False, default="webapp", index=True)
    model_version = Column(String(100), nullable=False, default="local-pickle")
    input_features = Column(JSON, nullable=True)


class IngestionStats(Base):
    __tablename__ = "ingestion_stats"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    ingestion_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    total_rows = Column(Integer, default=0)
    valid_rows = Column(Integer, default=0)
    invalid_rows = Column(Integer, default=0)
    invalid_percentage = Column(Float, default=0.0)
    missing_values = Column(Integer, default=0)
    invalid_ranges = Column(Integer, default=0)
    invalid_categories = Column(Integer, default=0)
    missing_columns = Column(Integer, default=0)
    wrong_data_types = Column(Integer, default=0)
    duplicate_ids = Column(Integer, default=0)
    outliers = Column(Integer, default=0)
    criticality = Column(String, default="None")
    validation_success = Column(String, default="True")
    report_file = Column(String, nullable=True)


class TrainingStats(Base):
    __tablename__ = "training_stats"

    id = Column(Integer, primary_key=True, index=True)
    training_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    model_version = Column(String(100), nullable=False)
    feature_name = Column(String(120), nullable=False, index=True)
    feature_type = Column(String(20), nullable=False)
    mean_value = Column(Float, nullable=True)
    std_value = Column(Float, nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    median_value = Column(Float, nullable=True)
    distribution_json = Column(JSON, nullable=True)


class DriftStats(Base):
    __tablename__ = "drift_stats"

    id = Column(Integer, primary_key=True, index=True)
    measured_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    model_version = Column(String(100), nullable=False)
    feature_name = Column(String(120), nullable=False, index=True)
    metric_name = Column(String(50), nullable=False, default="psi")
    metric_value = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False, default=0.2)
    is_drifted = Column(Integer, nullable=False, default=0)
    details = Column(Text, nullable=True)
