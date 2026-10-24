"""Scheduled retraining with MLflow tracking, promotion checks, stats and archival."""
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import requests
from airflow.exceptions import AirflowSkipException
from airflow.sdk import dag, task

PROJECT_DIR = Path(os.getenv("DSP_PROJECT_DIR", "/opt/airflow/project"))

@dag(schedule="0 3 * * 1", start_date=datetime(2026, 1, 1), catchup=False,
     tags=["athlete", "training", "mlflow"])
def athlete_model_retraining():
    @task
    def check_training_data():
        clean = sorted(p.name for p in (PROJECT_DIR / "data" / "clean").glob("*.csv"))
        good = sorted(p.name for p in (PROJECT_DIR / "data" / "good_data").glob("*.csv"))
        if not clean and not good:
            raise AirflowSkipException("No clean or validated data available for retraining")
        return {"clean_files": clean, "good_files": good}

    @task
    def train_and_register(data_files: dict):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_DIR)
        env["MLFLOW_TRACKING_URI"] = env.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        env["DATABASE_URL"] = env.get("DATABASE_URL", "postgresql://athlete:athlete_local_password@postgres:5432/athlete_db")
        subprocess.run(["python", str(PROJECT_DIR / "scripts" / "train_model.py")],
                       cwd=str(PROJECT_DIR), env=env, check=True)
        return data_files

    @task
    def reload_production_model(data_files: dict):
        api_url = os.getenv("MODEL_SERVICE_URL", "http://fastapi:8000")
        response = requests.post(f"{api_url}/reload-model", timeout=60)
        response.raise_for_status()
        print(f"FastAPI reloaded production model: {response.json()}")
        return data_files

    @task
    def calculate_drift(data_files: dict):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_DIR)
        env["DATABASE_URL"] = env.get("DATABASE_URL", "postgresql://athlete:athlete_local_password@postgres:5432/athlete_db")
        subprocess.run(["python", str(PROJECT_DIR / "scripts" / "calculate_drift.py")],
                       cwd=str(PROJECT_DIR), env=env, check=True)
        return data_files

    @task
    def archive_used_training_data(data_files: dict):
        archive_dir = PROJECT_DIR / "data" / "archived_data"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archived = []
        # Only validated files used by training are archived; clean baseline stays reusable.
        for filename in data_files["good_files"]:
            source = PROJECT_DIR / "data" / "good_data" / filename
            destination = archive_dir / filename
            if source.exists() and not destination.exists():
                shutil.move(str(source), str(destination))
                archived.append(filename)
        return {"archived_files": archived}

    archive_used_training_data(calculate_drift(reload_production_model(train_and_register(check_training_data()))))

athlete_model_retraining()
