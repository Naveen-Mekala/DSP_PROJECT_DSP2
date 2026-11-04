"""Endpoint tests: startup without a model, predictions, history and the Depends() DB session."""
import io

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import api.main as main

ROW = {
    "Age": 25, "Gender": "Male", "Sport_Type": "Endurance", "Training_Type": "Cardio",
    "Training_Duration_Min": 90, "Training_Intensity": 7.5, "Sleep_Duration_Hours": 8,
    "Caffeine_Intake_mg": 100, "Stress_Level": "Medium", "Resting_Heart_Rate": 60,
    "HRV_ms": 85, "Mood_Score": 8, "Muscle_Soreness": 2, "Energy_Level": 9,
}


class StubModel:
    def predict(self, frame):
        return np.full(len(frame), 70.0)


@pytest.fixture()
def client():
    with TestClient(main.app) as c:     # runs the lifespan (DB migration + model loading)
        yield c


def test_api_starts_without_any_model(client):
    body = client.get("/health").json()
    assert body["status"] == "healthy" and body["model_loaded"] is False
    assert client.post("/predict", json=ROW).status_code == 503


def test_predict_single_batch_and_history(client, monkeypatch):
    monkeypatch.setattr(main, "model", StubModel())
    monkeypatch.setattr(main, "model_version", "test")
    assert client.post("/predict", json=ROW).json() == {"prediction": 70.0, "model_version": "test"}
    batch = client.post("/predict", json={"features": [ROW, ROW], "source": "scheduled"}).json()
    assert batch["count"] == 2
    history = client.get("/past-predictions", params={"source": "scheduled"}).json()
    assert len(history) >= 2 and all(r["source"] == "scheduled" for r in history)
    assert history[0]["features"]["Training_Intensity"] == 7.5


def test_batch_predict_csv(client, monkeypatch):
    monkeypatch.setattr(main, "model", StubModel())
    csv = pd.DataFrame([ROW, ROW, ROW]).to_csv(index=False).encode()
    response = client.post("/batch-predict", files={"file": ("rows.csv", io.BytesIO(csv), "text/csv")})
    assert response.status_code == 200
    out = pd.read_csv(io.BytesIO(response.content))
    assert out["Predicted_Recovery_Score"].tolist() == [70.0, 70.0, 70.0]


def test_past_predictions_rejects_inverted_dates(client):
    r = client.get("/past-predictions", params={"start_date": "2026-11-05", "end_date": "2026-11-01"})
    assert r.status_code == 422


def test_monitoring_summary(client):
    body = client.get("/monitoring/summary").json()
    assert set(body) == {"ingestion", "drift"}
