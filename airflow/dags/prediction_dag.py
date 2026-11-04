"""Scheduled scoring for validated files; all predictions are persisted through FastAPI."""
from datetime import datetime
from pathlib import Path
import os
import pandas as pd
import requests
from airflow.exceptions import AirflowSkipException
from airflow.models import Variable
from airflow.sdk import dag, task

GOOD_DIR = Path(os.getenv("DSP_PROJECT_DIR", "/opt/airflow/project")) / "data" / "good_data"
MODEL_SERVICE_URL = os.getenv("MODEL_SERVICE_URL", "http://fastapi:8000")
PROCESSED_FILES_VARIABLE = "athlete_processed_good_data_files"


def json_safe_records(df):
    records = df.to_dict(orient="records")
    safe = []
    for record in records:
        safe.append({k: (None if pd.isna(v) else v.item() if hasattr(v, "item") else v)
                    for k, v in record.items()})
    return safe


@dag(schedule=os.getenv("PREDICTION_SCHEDULE", "*/5 * * * *"), start_date=datetime(2026, 1, 1),
     catchup=False, max_active_runs=1, tags=["athlete", "prediction"])
def athlete_prediction_job():
    @task
    def check_for_new_data():
        processed = set(Variable.get(PROCESSED_FILES_VARIABLE, default_var=[], deserialize_json=True))
        files = sorted(p.name for p in GOOD_DIR.glob("*.csv"))
        new_files = [name for name in files if name not in processed]
        if not new_files:
            raise AirflowSkipException("No new validated data available")
        return new_files

    @task
    def make_predictions(file_names):
        records = []
        for name in file_names:
            df = pd.read_csv(GOOD_DIR / name)
            records.extend(json_safe_records(df))
        if not records:
            raise AirflowSkipException("Validated files contain no rows")
        response = requests.post(
            f"{MODEL_SERVICE_URL}/predict",
            json={
                "features": records,
                "source": "scheduled"},
            timeout=120)
        response.raise_for_status()
        processed = set(Variable.get(PROCESSED_FILES_VARIABLE, default_var=[], deserialize_json=True))
        processed.update(file_names)
        Variable.set(PROCESSED_FILES_VARIABLE, sorted(processed), serialize_json=True)
        return {"files_processed": len(file_names), "rows_predicted": len(records)}

    make_predictions(check_for_new_data())


athlete_prediction_job()
