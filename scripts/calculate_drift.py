"""Compare recent serving inputs with persisted training distributions using PSI."""
import json
import os
import sys
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.drift_math import psi  # noqa: E402
from database.database import SessionLocal  # noqa: E402
from database.models import DriftStats, Prediction, TrainingStats  # noqa: E402

THRESHOLD = float(os.getenv("DRIFT_PSI_THRESHOLD", "0.2"))
WINDOW = int(os.getenv("DRIFT_WINDOW", "500"))


def _champion_version():
    try:
        from scripts.training_pipeline import get_champion
        champion = get_champion()
        return str(champion.version) if champion else None
    except Exception:
        return None


def main():
    db = SessionLocal()
    try:
        # Baseline = training statistics of the model currently in production (@champion).
        champion_version = _champion_version()
        query = db.query(TrainingStats)
        if champion_version and query.filter(TrainingStats.model_version == champion_version).count():
            query = query.filter(TrainingStats.model_version == champion_version)
        train_rows = query.order_by(TrainingStats.training_time.desc()).all()
        latest = {}
        for row in train_rows:
            latest.setdefault(row.feature_name, row)
        predictions = db.query(Prediction).order_by(Prediction.prediction_time.desc()).limit(WINDOW).all()
        if not latest or not predictions:
            print("Drift calculation skipped: training stats or serving predictions are missing.")
            return
        versions = [r.model_version for r in latest.values() if r.model_version]
        version = champion_version or (versions[0] if versions else "unknown")
        serving = [r.input_features or {} for r in predictions]
        for feature, baseline in latest.items():
            values = [r.get(feature) for r in serving if r.get(feature) is not None]
            if not values:
                continue
            if baseline.feature_type == "numeric" and baseline.min_value is not None and baseline.max_value is not None:
                nums = pd.to_numeric(pd.Series(values), errors="coerce").dropna().to_numpy()
                if not len(nums):
                    continue
                lo, hi = baseline.min_value, baseline.max_value
                if lo == hi:
                    lo, hi = lo - 0.5, hi + 0.5
                edges = np.linspace(lo, hi, 11)
                train_counts = np.asarray(
                    (baseline.distribution_json or {}).get(
                        "histogram_counts", [1] * 10), dtype=float)
                if len(train_counts) != 10:
                    train_counts = np.ones(10)
                serve_counts, _ = np.histogram(nums, bins=edges)
                # Values outside training range are assigned to edge bins.
                serve_counts[0] += int(np.sum(nums < lo))
                serve_counts[-1] += int(np.sum(nums > hi))
                score = psi(train_counts, serve_counts)
            else:
                expected = baseline.distribution_json or {}
                observed = Counter(str(v) for v in values)
                keys = set(expected) | set(observed)
                score = psi([expected.get(k, 0.0) for k in keys], [observed.get(k, 0)
                            for k in keys]) if keys else 0.0
            metric = "psi_numeric" if baseline.feature_type == "numeric" else "psi_categorical"
            db.add(DriftStats(model_version=version, feature_name=feature, metric_name=metric,
                              metric_value=score, threshold=THRESHOLD, is_drifted=int(score >= THRESHOLD),
                              details=json.dumps({"serving_rows": len(values), "baseline_type": baseline.feature_type})))
        db.commit()
        print(f"Stored PSI drift scores for {len(latest)} features; threshold={THRESHOLD}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
