import pandas as pd
import pytest
from scripts.data_quality import calculate_criticality, compute_ingestion_stats, split_valid_invalid, summarize_validation_errors


@pytest.mark.parametrize(("pct", "expected"), [
    (0, "None"), (0.5, "Low"), (10, "Medium"), (50, "Medium"), (50.01, "High")
])
def test_criticality_thresholds(pct, expected):
    assert calculate_criticality(pct) == expected


def test_missing_columns_are_high_criticality():
    assert calculate_criticality(0, missing_columns=True) == "High"


def test_split_valid_invalid_rows():
    frame = pd.DataFrame({"value": [1, 2, 3]})
    good, bad = split_valid_invalid(frame, pd.Series([False, True, False]))
    assert good["value"].tolist() == [1, 3]
    assert bad["value"].tolist() == [2]


def test_split_rejects_wrong_mask_length():
    with pytest.raises(ValueError):
        split_valid_invalid(pd.DataFrame({"x": [1, 2]}), pd.Series([False]))


def test_ingestion_stats():
    assert compute_ingestion_stats(20, 12) == {
        "total_rows": 20, "invalid_rows": 12, "valid_rows": 8,
        "invalid_percentage": 60.0, "criticality": "High"
    }


def test_ingestion_stats_reject_invalid_counts():
    with pytest.raises(ValueError):
        compute_ingestion_stats(10, 11)


def test_summarize_validation_errors():
    result = summarize_validation_errors({
        "expect_column_values_to_not_be_null": 2,
        "expect_column_values_to_be_unique": 3,
        "expect_column_values_to_be_in_set": 4,
        "expect_column_values_to_be_between": 5,
        "expect_column_values_to_be_of_type": 6,
    }, missing_columns=1)
    assert result == {
        "missing_values": 2, "invalid_ranges": 5, "invalid_categories": 4,
        "missing_columns": 1, "wrong_data_types": 6, "duplicate_ids": 3, "outliers": 0,
    }
