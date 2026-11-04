"""Model training pipeline steps, used by the Airflow training DAG (one function per task).

Fair comparison protocol
------------------------
A fixed holdout of athletes (Athlete_ID % HOLDOUT_MODULO == 0) is never used for training.
Candidate and champion are both scored on the same holdout rows, so neither has seen them.
Champions trained before this protocol (no `holdout_protocol` tag) are not comparable and
are replaced by the first protocol-compliant candidate.

Training data = clean baseline dataset + newly validated data in good_data (deduplicated),
excluding the holdout athletes. If no champion exists yet, the baseline alone bootstraps v1.
"""
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(os.getenv("DSP_PROJECT_DIR", Path(__file__).resolve().parents[1]))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET = "Recovery_Score"
DROP_COLUMNS = ["Athlete_ID", "Day", "Week", "Day_of_Week"]
MODEL_NAME = os.getenv("MLFLOW_REGISTERED_MODEL", "AthleteRecoveryModel")
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
MLFLOW_UI_URL = os.getenv("MLFLOW_UI_URL", "http://localhost:5001").rstrip("/")
EXPERIMENT = "athlete-recovery-training"
PROTOCOL = "athlete-holdout-v1"
HOLDOUT_MODULO = int(os.getenv("HOLDOUT_MODULO", "5"))
MIN_NEW_ROWS = int(os.getenv("MIN_NEW_TRAINING_ROWS", "100"))
MAX_INFERENCE_MS = float(os.getenv("MAX_INFERENCE_MS_PER_ROW", "10"))
RMSE_TOLERANCE = float(os.getenv("PROMOTION_RMSE_TOLERANCE", "0.0"))

CLEAN_DIR = ROOT / "data" / "clean"
GOOD_DIR = ROOT / "data" / "good_data"
ARCHIVE_DIR = ROOT / "data" / "archived_data"
RUNS_DIR = ROOT / "data" / "training_runs"


def _client():
    import mlflow
    from mlflow.tracking import MlflowClient
    mlflow.set_tracking_uri(TRACKING_URI)
    return MlflowClient(tracking_uri=TRACKING_URI)


def get_champion():
    try:
        return _client().get_model_version_by_alias(MODEL_NAME, "champion")
    except Exception:
        return None


def is_holdout(athlete_ids: pd.Series) -> pd.Series:
    return pd.to_numeric(athlete_ids, errors="coerce").fillna(-1).astype(int) % HOLDOUT_MODULO == 0


# ---------------------------------------------------------------- 0. enough new data?
def check_for_new_data(min_rows: int = MIN_NEW_ROWS) -> dict:
    """Return the files to train on, or {'ready': False, 'reason': ...}."""
    good_files = sorted(GOOD_DIR.glob("*.csv"))
    new_rows = sum(len(pd.read_csv(p)) for p in good_files)
    champion = get_champion()
    if champion is None:
        return {"ready": True, "bootstrap": True, "good_files": [p.name for p in good_files],
                "new_rows": new_rows, "reason": "no champion yet: bootstrap from the baseline dataset"}
    if new_rows < min_rows:
        return {"ready": False, "bootstrap": False, "good_files": [], "new_rows": new_rows,
                "reason": f"only {new_rows} new validated rows (< {min_rows})"}
    return {"ready": True, "bootstrap": False, "good_files": [p.name for p in good_files],
            "new_rows": new_rows, "reason": f"{new_rows} new validated rows"}


# ---------------------------------------------------------------- 1. load data
def load_data(plan: dict) -> dict:
    frames = [pd.read_csv(p) for p in sorted(CLEAN_DIR.glob("*.csv"))]
    frames += [pd.read_csv(GOOD_DIR / name) for name in plan["good_files"] if (GOOD_DIR / name).exists()]
    if not frames:
        raise FileNotFoundError("No training data in data/clean or data/good_data")
    df = pd.concat(frames, ignore_index=True)
    df = df.drop(columns=[c for c in df.columns if c == "dq_errors"]).drop_duplicates()
    df = df.dropna(subset=[TARGET])
    holdout = is_holdout(df["Athlete_ID"])
    run_dir = RUNS_DIR / datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    train_path, test_path = run_dir / "train.csv", run_dir / "holdout.csv"
    df[~holdout].to_csv(train_path, index=False)
    df[holdout].to_csv(test_path, index=False)
    return {**plan, "train_path": str(train_path), "test_path": str(test_path),
            "train_rows": int((~holdout).sum()), "test_rows": int(holdout.sum())}


def _xy(path):
    df = pd.read_csv(path)
    y = pd.to_numeric(df[TARGET], errors="raise")
    X = df.drop(columns=[TARGET] + [c for c in DROP_COLUMNS if c in df.columns])
    # Numeric features as float64: the MLflow signature then declares `double`, and integer
    # inputs sent to the API are converted safely (int -> double) by schema enforcement.
    numeric = X.select_dtypes(include="number").columns
    X[numeric] = X[numeric].astype("float64")
    return X, y


def _metrics(y_true, y_pred):
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    return {"mae": float(mean_absolute_error(y_true, y_pred)),
            "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
            "r2": float(r2_score(y_true, y_pred))}


# ---------------------------------------------------------------- 2. train + log to MLflow
def train_model(data: dict) -> dict:
    import mlflow
    import mlflow.sklearn
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    X, y = _xy(data["train_path"])
    X_test, y_test = _xy(data["test_path"])
    categorical = X.select_dtypes(include=["object", "category", "bool"]).columns.tolist()
    numeric = [c for c in X.columns if c not in categorical]
    pipeline = Pipeline([
        ("preprocessor", ColumnTransformer([
            ("num", SimpleImputer(strategy="median"), numeric),
            ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")),
                              ("encoder", OneHotEncoder(handle_unknown="ignore"))]), categorical),
        ])),
        ("model", RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)),
    ])
    pipeline.fit(X, y)
    metrics = _metrics(y_test, pipeline.predict(X_test))

    _client()
    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run() as run:
        mlflow.log_params({"algorithm": "RandomForestRegressor", "n_estimators": 200, "random_state": 42,
                           "train_rows": data["train_rows"], "holdout_rows": data["test_rows"],
                           "new_validated_rows": data["new_rows"], "bootstrap": data["bootstrap"],
                           "holdout_rule": f"Athlete_ID % {HOLDOUT_MODULO} == 0"})
        mlflow.log_metrics(metrics)
        mlflow.set_tags({"target": TARGET, "project": "athlete-recovery", "holdout_protocol": PROTOCOL})
        info = mlflow.sklearn.log_model(pipeline, artifact_path="model", registered_model_name=MODEL_NAME,
                                        input_example=X.head(2))
        run_id = run.info.run_id
        experiment_id = run.info.experiment_id
    client = _client()
    version = str(info.registered_model_version) if getattr(info, "registered_model_version", None) else \
        max(client.search_model_versions(f"run_id='{run_id}'"), key=lambda v: int(v.version)).version
    client.set_model_version_tag(MODEL_NAME, version, "holdout_protocol", PROTOCOL)
    client.set_model_version_tag(MODEL_NAME, version, "promotion_status", "candidate")
    return {**data, "run_id": run_id, "experiment_id": experiment_id, "version": str(version),
            "metrics": metrics, "run_url": f"{MLFLOW_UI_URL}/#/experiments/{experiment_id}/runs/{run_id}"}


# ---------------------------------------------------------------- 3. training statistics
def save_training_stats(candidate: dict) -> dict:
    """Persist feature distributions of the candidate's training data (drift baseline)."""
    from database.database import Base, SessionLocal, engine
    from database.models import TrainingStats

    X, _ = _xy(candidate["train_path"])
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for name in X.columns:
            series = X[name]
            if pd.api.types.is_numeric_dtype(series):
                values = pd.to_numeric(series, errors="coerce").dropna()
                counts, edges = np.histogram(values, bins=10) if len(values) else (np.array([]), np.array([]))
                db.add(TrainingStats(
                    model_version=candidate["version"], feature_name=name, feature_type="numeric",
                    mean_value=float(values.mean()) if len(values) else None,
                    std_value=float(values.std()) if len(values) > 1 else 0.0,
                    min_value=float(values.min()) if len(values) else None,
                    max_value=float(values.max()) if len(values) else None,
                    median_value=float(values.median()) if len(values) else None,
                    distribution_json={"histogram_counts": counts.tolist(), "histogram_edges": edges.tolist()}))
            else:
                share = series.fillna("<missing>").astype(str).value_counts(normalize=True).head(30)
                db.add(TrainingStats(model_version=candidate["version"], feature_name=name,
                                     feature_type="categorical",
                                     distribution_json={str(k): float(v) for k, v in share.items()}))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return candidate


# ---------------------------------------------------------------- 4. candidate vs champion
def evaluate_candidate(candidate: dict) -> dict:
    import mlflow
    import mlflow.sklearn

    client = _client()
    X_test, y_test = _xy(candidate["test_path"])
    # sklearn flavor: compares the raw pipelines, independent of older models' signatures
    model = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}/{candidate['version']}")
    start = time.perf_counter()
    cand_pred = model.predict(X_test)
    inference_ms = (time.perf_counter() - start) * 1000 / max(len(X_test), 1)
    cand = _metrics(y_test, cand_pred)

    champion = get_champion()
    champ = None
    if champion is None:
        promote, reason = True, "no champion yet"
    elif (champion.tags or {}).get("holdout_protocol") != PROTOCOL:
        promote, reason = True, f"champion v{champion.version} predates the fair holdout protocol"
    else:
        champ_model = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}@champion")
        champ = _metrics(y_test, champ_model.predict(X_test))
        better = cand["rmse"] <= champ["rmse"] * (1 + RMSE_TOLERANCE)
        promote = better and inference_ms <= MAX_INFERENCE_MS
        reason = (f"candidate RMSE {cand['rmse']:.3f} vs champion v{champion.version} {champ['rmse']:.3f}; "
                  f"inference {inference_ms:.3f} ms/row (max {MAX_INFERENCE_MS})")
    if inference_ms > MAX_INFERENCE_MS:
        promote = False
        reason += f"; too slow: {inference_ms:.3f} ms/row > {MAX_INFERENCE_MS}"

    with mlflow.start_run(run_id=candidate["run_id"]):
        mlflow.log_metrics({"holdout_rmse_candidate": cand["rmse"], "inference_ms_per_row": inference_ms,
                            **({"holdout_rmse_champion": champ["rmse"]} if champ else {})})
        mlflow.set_tags({"promotion_decision": "promote" if promote else "reject", "promotion_reason": reason,
                         "compared_with_champion": champion.version if champion else "none"})
    client.set_model_version_tag(MODEL_NAME, candidate["version"], "evaluation", reason)
    return {**candidate, "promote": promote, "reason": reason, "candidate_metrics": cand,
            "champion_metrics": champ, "champion_version": champion.version if champion else None,
            "inference_ms_per_row": inference_ms}


# ---------------------------------------------------------------- 5. promotion
def promote_to_champion(evaluation: dict) -> dict:
    client = _client()
    if evaluation["promote"]:
        client.set_registered_model_alias(MODEL_NAME, "champion", evaluation["version"])
        client.set_model_version_tag(MODEL_NAME, evaluation["version"], "promotion_status", "champion")
    else:
        client.set_model_version_tag(MODEL_NAME, evaluation["version"], "promotion_status", "rejected")
    return evaluation


# ---------------------------------------------------------------- 6. archive used data
def archive_data(evaluation: dict) -> list:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    moved = []
    for name in evaluation["good_files"]:
        src, dst = GOOD_DIR / name, ARCHIVE_DIR / name
        if src.exists():
            if dst.exists():
                dst = ARCHIVE_DIR / f"{src.stem}_{datetime.now():%Y%m%dT%H%M%S}.csv"
            shutil.move(str(src), str(dst))
            moved.append(dst.name)
    return moved


def run_all():
    """Run every step in-process (manual bootstrap: python scripts/train_model.py)."""
    plan = check_for_new_data(min_rows=0)
    evaluation = evaluate_candidate(save_training_stats(train_model(load_data(plan))))
    promote_to_champion(evaluation)
    if evaluation["promote"]:
        archive_data(evaluation)
    print(json.dumps({k: evaluation[k] for k in ("version", "promote", "reason", "candidate_metrics",
                                                 "champion_metrics", "run_url")}, indent=2, default=str))
    return evaluation
