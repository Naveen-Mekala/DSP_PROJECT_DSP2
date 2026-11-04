import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# API tests run against a throwaway SQLite database and an empty MLflow registry,
# so CI needs no PostgreSQL, MLflow server or model file.
_TMP = Path(tempfile.mkdtemp(prefix="dsp-tests-"))
os.environ["DATABASE_URL"] = (f"sqlite:///{_TMP / 'app.db'}")
os.environ["MLFLOW_TRACKING_URI"] = (f"sqlite:///{_TMP / 'mlflow.db'}")
os.environ["MODEL_PATH"] = (str(_TMP / "missing-model.pkl.gz"))
