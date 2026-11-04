"""Tests for the ingestion, alerting and training helpers added for Defense 2."""
from pathlib import Path

import pandas as pd
import pytest
import requests

from scripts import teams
from scripts.data_quality import categorize_expectation
from scripts.generate_errors import inject_errors
from scripts.gx_validation import prepare_frames, run_validation
from scripts.split_dataset import split
from scripts.training_pipeline import is_holdout

ROOT = Path(__file__).resolve().parents[1]
CLEAN = pd.read_csv(ROOT / "data" / "clean" / "athlete_recovery_synthetic.csv")


@pytest.mark.parametrize(("expectation", "category"), [
    ("expect_column_values_to_not_be_null", "completeness"),
    ("expect_column_values_to_be_between", "validity"),
    ("expect_column_values_to_be_in_set", "validity"),
    ("expect_compound_columns_to_be_unique", "consistency"),
    ("expect_table_columns_to_match_set", "schema"),
    ("expect_column_values_to_be_in_type_list", "type"),
])
def test_every_expectation_maps_to_one_of_five_categories(expectation, category):
    assert categorize_expectation(expectation) == category


def test_prepare_frames_keeps_text_for_type_check_and_nulls_it_for_content():
    df = pd.DataFrame({"HRV_ms": ["70", "seventy", "80"], "Gender": ["Male", "Female", "Male"]})
    schema_frame, content_frame = prepare_frames(df)
    assert schema_frame["HRV_ms"].tolist() == [70.0, "seventy", 80.0]
    assert content_frame["HRV_ms"].isna().tolist() == [False, True, False]


@pytest.mark.parametrize(("name", "bad", "criticality", "category"), [
    ("demo_1_all_errors.csv", 10, "High", "validity"),
    ("demo_2_clean.csv", 0, "None", None),
    ("demo_5_mixed.csv", 6, "Medium", "consistency"),
    ("demo_6_missing_column.csv", 10, "High", "schema"),
])
def test_gx_validation_on_demo_files(name, bad, criticality, category):
    result = run_validation(pd.read_csv(ROOT / "data" / "demo" / name))
    assert len(result["invalid_row_indices"]) == bad
    assert result["criticality"] == criticality
    if category:
        assert result["category_counts"][category] > 0
    assert result["data_docs_path"].startswith("http")


def test_inject_errors_is_reproducible_and_configurable():
    sample = CLEAN.head(500)
    a, counts_a = inject_errors(sample, p_duplicate=0.05, seed=1)
    b, counts_b = inject_errors(sample, p_duplicate=0.05, seed=1)
    assert counts_a == counts_b and a.equals(b)
    assert len(a) == len(sample) + counts_a["duplicate"]
    untouched, counts = inject_errors(sample, 0, 0, 0, 0, 0, 0, seed=1)
    assert sum(counts.values()) == 0 and len(untouched) == len(sample)


def test_split_dataset_files_and_missing_columns():
    chunks = list(split(CLEAN.head(100), num_files=7, p_missing_column=1.0, seed=3))
    assert len(chunks) == 7
    assert sum(len(c) for _, c in chunks) == 100
    assert all(len(c.columns) == len(CLEAN.columns) - 1 and "Athlete_ID" in c.columns for _, c in chunks)
    with pytest.raises(ValueError):
        list(split(CLEAN, num_files=0))


def test_holdout_is_a_fixed_fifth_of_athletes():
    holdout = is_holdout(CLEAN["Athlete_ID"])
    assert holdout.equals(CLEAN["Athlete_ID"] % 5 == 0)
    assert 0.15 < holdout.mean() < 0.25


def test_teams_card_payload():
    card = teams.build_card("Title", {"File": "a.csv"}, link="http://x")
    content = card["attachments"][0]["content"]
    assert card["type"] == "message" and content["type"] == "AdaptiveCard"
    assert content["actions"][0]["url"] == "http://x"


def test_teams_alert_without_webhook_is_logged_only(monkeypatch):
    monkeypatch.delenv("TEAMS_DATA_WEBHOOK_URL", raising=False)
    assert teams.send_alert("data", "t", {"a": 1}) is False


def test_teams_alert_posts_and_never_raises(monkeypatch):
    monkeypatch.setenv("TEAMS_ML_WEBHOOK_URL", "https://teams.test/hook")
    calls = []

    class Ok:
        def raise_for_status(self):
            pass

    monkeypatch.setattr(teams.requests, "post", lambda url, json, timeout: calls.append(url) or Ok())
    assert teams.send_alert("ml", "t", {"a": 1}) is True and calls == ["https://teams.test/hook"]

    def boom(*args, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(teams.requests, "post", boom)
    assert teams.send_alert("ml", "t", {"a": 1}) is False
