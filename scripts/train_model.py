"""Train, evaluate and (if better) promote a model in one go — manual / bootstrap entry point.

The scheduled path is the Airflow DAG `athlete_model_retraining`, which runs the same steps
from scripts/training_pipeline.py as separate tasks.

Usage (inside the Airflow container):  python scripts/train_model.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.training_pipeline import run_all  # noqa: E402

if __name__ == "__main__":
    run_all()
