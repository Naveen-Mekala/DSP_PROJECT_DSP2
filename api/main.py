"""FastAPI model-serving layer. The UI and Airflow communicate only through this API."""
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from io import BytesIO
import logging
import os
from typing import Literal

import joblib
import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from api.features import FEATURE_COLUMNS, feature_frame
from api.schemas.prediction import AthleteInput, PredictRequest, PredictResponse, SinglePredictResponse
from database.database import Base, engine, get_db
from database.models import DriftStats, IngestionStats, Prediction

MODEL_PATH = os.getenv("MODEL_PATH", "models/model.pkl.gz")
MODEL_NAME = os.getenv("MLFLOW_REGISTERED_MODEL", "AthleteRecoveryModel")
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
model = None
model_version = "none"
log = logging.getLogger("athlete-api")


def _load_local_model():
    global model, model_version
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model artifact not found: {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
    model_version = "local-pickle"


def _load_production_model():
    global model, model_version
    import mlflow
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(MLFLOW_URI)
    client = MlflowClient(tracking_uri=MLFLOW_URI)
    try:
        version = client.get_model_version_by_alias(MODEL_NAME, "champion")
        model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@champion")
        model_version = str(version.version)
    except Exception:
        # Initial boot should remain available before the first registry promotion.
        _load_local_model()


_feature_frame = feature_frame


def _save_prediction(db, features, prediction, source):
    feature_values = {k: (None if pd.isna(v) else v.item() if hasattr(v, "item") else v)
                      for k, v in features.items()}
    row = Prediction(
        **{k: feature_values.get(k) for k in FEATURE_COLUMNS},
        Prediction=float(prediction), source=source, model_version=model_version,
        input_features=feature_values,
    )
    db.add(row)


def _migrate_database():
    Base.metadata.create_all(bind=engine)
    # Upgrade existing DSP 1 databases safely; create_all alone does not add columns.
    with engine.begin() as conn:
        existing = {c["name"] for c in inspect(engine).get_columns("predictions")}
        additions = {
            "prediction_time": "TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP",
            "source": "VARCHAR(20) DEFAULT 'webapp'",
            "model_version": "VARCHAR(100) DEFAULT 'local-pickle'",
            "input_features": "JSON",
        }
        for name, sql_type in additions.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE predictions ADD COLUMN {name} {sql_type}"))
        # Stress_Level is categorical (Low/Medium/High) in the source dataset.
        # Convert an older integer column safely when upgrading a DSP 1 database.
        column_types = {c["name"].lower(): str(c["type"]).lower()
                        for c in inspect(engine).get_columns("predictions")}
        if "stress_level" in column_types and "int" in column_types["stress_level"]:
            conn.execute(
                text('ALTER TABLE predictions ALTER COLUMN "Stress_Level" TYPE VARCHAR USING "Stress_Level"::text'))


def load_model_at_startup():
    """Champion from the MLflow registry -> local fallback file -> no model (API still starts).

    Starting without a model keeps the stack healthy on a fresh setup; the training DAG then
    registers a champion and calls /reload-model.
    """
    global model, model_version
    try:
        _load_production_model()
    except Exception as exc:  # no champion and no fallback file
        model, model_version = None, "none"
        log.warning("No model available yet (%s). Run the training DAG, then /reload-model.", exc)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _migrate_database()
    load_model_at_startup()
    yield


app = FastAPI(title="Athlete Recovery Prediction API", version="2.1.0", lifespan=lifespan)


def require_model():
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="No model loaded yet: run the training DAG, then POST /reload-model")
    return model


@app.get("/")
def home():
    return {"message": "Athlete Recovery Prediction API", "model_version": model_version}


@app.get("/health")
def health():
    return {"status": "healthy", "model_loaded": model is not None, "model_version": model_version}


@app.post("/predict", response_model=PredictResponse | SinglePredictResponse)
def predict(payload: PredictRequest | AthleteInput, db: Session = Depends(get_db)):
    """Accept a validated single athlete row or a validated batch of feature rows."""
    if isinstance(payload, PredictRequest):
        source = payload.source
        records = [row.model_dump() for row in payload.features]
        batch_request = True
    else:
        source = "webapp"
        records = [payload.model_dump()]
        batch_request = False
    try:
        frame = _feature_frame(records)
        predictions = require_model().predict(frame[FEATURE_COLUMNS])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Prediction failed: {exc}") from exc
    try:
        results = []
        for record, pred in zip(records, predictions):
            _save_prediction(db, record, float(pred), source)
            results.append({"features": record, "prediction": round(
                float(pred), 2), "model_version": model_version})
        db.commit()
        if not batch_request:
            return {"prediction": results[0]["prediction"], "model_version": model_version}
        return {"count": len(results), "model_version": model_version, "results": results}
    except Exception:
        db.rollback()
        raise


@app.post("/batch-predict")
def batch_predict(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Upload a CSV file")
    try:
        df = pd.read_csv(file.file)
        frame = _feature_frame(df.to_dict(orient="records"))
        predictions = require_model().predict(frame[FEATURE_COLUMNS])
        output_df = df.copy()
        output_df["Predicted_Recovery_Score"] = predictions.round(2)
        for features, pred in zip(frame.to_dict(orient="records"), predictions):
            _save_prediction(db, features, float(pred), "webapp")
        db.commit()
        buf = BytesIO()
        output_df.to_csv(buf, index=False)
        buf.seek(0)
        return StreamingResponse(buf, media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=batch_predictions.csv"})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Batch prediction failed: {exc}") from exc


@app.get("/past-predictions")
def get_past_predictions(
    start_date: date | None = None,
    end_date: date | None = None,
    source: Literal["webapp", "scheduled", "all"] = "all",
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date")
    query = db.query(Prediction)
    if start_date:
        query = query.filter(Prediction.prediction_time >= datetime.combine(start_date, time.min))
    if end_date:
        query = query.filter(
            Prediction.prediction_time < datetime.combine(
                end_date +
                timedelta(
                    days=1),
                time.min))
    if source != "all":
        query = query.filter(Prediction.source == source)
    rows = query.order_by(Prediction.prediction_time.desc()).limit(limit).all()
    return [{
        "id": r.id, "Age": r.Age, "Gender": r.Gender, "Sport_Type": r.Sport_Type,
        "Training_Type": r.Training_Type, "Prediction": round(float(r.Prediction), 2),
        "prediction_time": r.prediction_time.isoformat() if r.prediction_time else None,
        "source": r.source or "webapp", "model_version": r.model_version or "local-pickle",
        "features": r.input_features,
    } for r in rows]


@app.post("/reload-model")
def reload_model():
    try:
        _load_production_model()
        return {"status": "reloaded", "model_version": model_version}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not load registered production model: {exc}") from exc


@app.get("/monitoring/summary")
def monitoring_summary(db: Session = Depends(get_db)):
    ingestion = db.query(IngestionStats).order_by(IngestionStats.ingestion_time.desc()).limit(100).all()
    drift = db.query(DriftStats).order_by(DriftStats.measured_at.desc()).limit(100).all()
    return {
        "ingestion": [{"time": x.ingestion_time.isoformat() if x.ingestion_time else None, "total_rows": x.total_rows, "valid_rows": x.valid_rows, "invalid_rows": x.invalid_rows, "invalid_percentage": x.invalid_percentage, "criticality": x.criticality} for x in ingestion],
        "drift": [{"time": x.measured_at.isoformat() if x.measured_at else None, "feature": x.feature_name, "metric": x.metric_name, "value": x.metric_value, "threshold": x.threshold, "is_drifted": x.is_drifted, "model_version": x.model_version} for x in drift],
    }
