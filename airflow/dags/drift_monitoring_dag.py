from datetime import datetime
import os
import subprocess
from pathlib import Path
from airflow.sdk import dag, task

PROJECT_DIR = Path(os.getenv("DSP_PROJECT_DIR", "/opt/airflow/project"))

@dag(schedule="*/15 * * * *", start_date=datetime(2026, 1, 1), catchup=False,
     tags=["athlete", "monitoring", "drift"])
def athlete_drift_monitoring():
    @task
    def calculate_drift():
        env = os.environ.copy()
        env["DATABASE_URL"] = env.get("DATABASE_URL", "postgresql://athlete:athlete@postgres:5432/athlete_db")
        subprocess.run(["python", str(PROJECT_DIR / "scripts" / "calculate_drift.py")],
                       cwd=str(PROJECT_DIR), env=env, check=True)
    calculate_drift()

athlete_drift_monitoring()
