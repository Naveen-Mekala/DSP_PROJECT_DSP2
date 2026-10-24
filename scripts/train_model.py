"""Train, evaluate, track in MLflow, register, and promote an improved model."""
import json
import os
import sys
from pathlib import Path
import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.tracking import MlflowClient
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TARGET = "Recovery_Score"
MODEL_NAME = os.getenv("MLFLOW_REGISTERED_MODEL", "AthleteRecoveryModel")
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
ARTIFACT_PATH = ROOT / "models" / "candidate_model.pkl.gz"
DROP_COLUMNS = ["Athlete_ID", "Day", "Week", "Day_of_Week"]


def find_dataset():
    paths = sorted((ROOT / "data" / "clean").glob("*.csv"))
    paths += sorted((ROOT / "data" / "good_data").glob("*.csv"))
    if not paths:
        raise FileNotFoundError("No clean training CSV in data/clean or data/good_data")
    df = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True).drop_duplicates()
    if TARGET not in df:
        raise ValueError(f"Missing target column: {TARGET}")
    return df.dropna(subset=[TARGET]).copy()


def persist_training_stats(X, version):
    from database.database import Base, SessionLocal, engine
    from database.models import TrainingStats
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for name in X.columns:
            series = X[name]
            if pd.api.types.is_numeric_dtype(series):
                values = pd.to_numeric(series, errors="coerce").dropna()
                hist_counts, hist_edges = np.histogram(values, bins=10) if len(values) else ([], [])
                distribution = {"histogram_counts": hist_counts.tolist(), "histogram_edges": hist_edges.tolist()} if len(values) else {}
                row = TrainingStats(model_version=str(version), feature_name=name, feature_type="numeric",
                    mean_value=float(values.mean()) if len(values) else None,
                    std_value=float(values.std()) if len(values) > 1 else 0.0,
                    min_value=float(values.min()) if len(values) else None,
                    max_value=float(values.max()) if len(values) else None,
                    median_value=float(values.median()) if len(values) else None,
                    distribution_json=distribution)
            else:
                counts = series.fillna("<missing>").astype(str).value_counts(normalize=True).head(30)
                row = TrainingStats(model_version=str(version), feature_name=name, feature_type="categorical",
                    distribution_json={str(k): float(v) for k, v in counts.items()})
            db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    df = find_dataset()
    y = pd.to_numeric(df[TARGET], errors="raise")
    X = df.drop(columns=[TARGET] + [c for c in DROP_COLUMNS if c in df.columns])
    categorical = X.select_dtypes(include=["object", "category", "bool"]).columns.tolist()
    numeric = [c for c in X.columns if c not in categorical]
    preprocessor = ColumnTransformer([
        ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), numeric),
        ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")),
                          ("encoder", OneHotEncoder(handle_unknown="ignore"))]), categorical),
    ])
    pipeline = Pipeline([("preprocessor", preprocessor),
                         ("model", RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1))])
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    pipeline.fit(X_train, y_train)
    pred = pipeline.predict(X_test)
    metrics = {"mae": float(mean_absolute_error(y_test, pred)),
               "rmse": float(mean_squared_error(y_test, pred) ** 0.5),
               "r2": float(r2_score(y_test, pred))}
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, ARTIFACT_PATH, compress=3)

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("athlete-recovery-training")
    with mlflow.start_run() as run:
        mlflow.log_params({"algorithm": "RandomForestRegressor", "n_estimators": 200,
                           "random_state": 42, "train_rows": len(X_train), "test_rows": len(X_test)})
        mlflow.log_metrics(metrics)
        mlflow.set_tags({"target": TARGET, "dataset_rows": len(df), "project": "athlete-recovery"})
        mlflow.sklearn.log_model(pipeline, artifact_path="model", registered_model_name=MODEL_NAME)
        mlflow.log_artifact(str(ARTIFACT_PATH), artifact_path="fallback")
        run_id = run.info.run_id

    client = MlflowClient(tracking_uri=TRACKING_URI)
    versions = client.search_model_versions(f"name='{MODEL_NAME}'")
    candidate = max(versions, key=lambda v: int(v.version))
    promote = True
    try:
        champion = client.get_model_version_by_alias(MODEL_NAME, "champion")
        champion_rmse = client.get_run(champion.run_id).data.metrics.get("rmse", float("inf"))
        promote = metrics["rmse"] <= champion_rmse
    except Exception:
        promote = True
    if promote:
        client.set_registered_model_alias(MODEL_NAME, "champion", candidate.version)
        client.set_model_version_tag(MODEL_NAME, candidate.version, "promotion_status", "champion")
    else:
        client.set_model_version_tag(MODEL_NAME, candidate.version, "promotion_status", "not_promoted_rmse_worse")
    active = client.get_model_version_by_alias(MODEL_NAME, "champion")
    persist_training_stats(X, active.version)
    print(json.dumps({"rows": len(df), "metrics": metrics, "run_id": run_id,
        "registered_model": MODEL_NAME, "candidate_version": candidate.version,
        "production_version": active.version, "promoted": promote}, indent=2))


if __name__ == "__main__":
    main()
