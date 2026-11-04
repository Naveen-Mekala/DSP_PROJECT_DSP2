"""Small deterministic helpers used by the ingestion pipeline and unit tests."""
import pandas as pd


def calculate_criticality(invalid_percentage: float, missing_columns: bool = False) -> str:
    if missing_columns or invalid_percentage > 50:
        return "High"
    if invalid_percentage >= 10:
        return "Medium"
    if invalid_percentage > 0:
        return "Low"
    return "None"


def split_valid_invalid(df: pd.DataFrame, invalid_mask: pd.Series):
    if len(df) != len(invalid_mask):
        raise ValueError("invalid_mask length must match dataframe length")
    mask = invalid_mask.fillna(True).astype(bool)
    return df.loc[~mask].copy(), df.loc[mask].copy()


def compute_ingestion_stats(total_rows: int, invalid_rows: int) -> dict:
    if total_rows < 0 or invalid_rows < 0 or invalid_rows > total_rows:
        raise ValueError("Row counts must satisfy 0 <= invalid_rows <= total_rows")
    pct = (invalid_rows / total_rows * 100) if total_rows else 0.0
    return {
        "total_rows": total_rows,
        "invalid_rows": invalid_rows,
        "valid_rows": total_rows - invalid_rows,
        "invalid_percentage": round(pct, 2),
        "criticality": calculate_criticality(pct),
    }


# The 5 data-quality error categories shown in Grafana and stored per ingested file.
CATEGORIES = ("completeness", "validity", "consistency", "schema", "type")


def categorize_expectation(expectation_type: str) -> str:
    """Map a GX expectation type to one of the 5 data-quality categories."""
    name = str(expectation_type).lower()
    if "table_columns" in name or "column_to_exist" in name:
        return "schema"
    if "type" in name:
        return "type"
    if "not_be_null" in name:
        return "completeness"
    if "unique" in name:
        return "consistency"
    return "validity"     # ranges (be_between) and allowed categories (be_in_set)


def summarize_validation_errors(error_counts: dict, missing_columns: int = 0) -> dict:
    """Map Great Expectations failures into the database monitoring categories."""
    summary = {
        "missing_values": 0,
        "invalid_ranges": 0,
        "invalid_categories": 0,
        "missing_columns": int(missing_columns),
        "wrong_data_types": 0,
        "duplicate_ids": 0,
        "outliers": 0,
    }
    for expectation_type, count in (error_counts or {}).items():
        name = str(expectation_type).lower()
        count = max(0, int(count or 0))
        if "not_be_null" in name:
            summary["missing_values"] += count
        elif "unique" in name:
            summary["duplicate_ids"] += count
        elif "table_columns" in name or "column_to_exist" in name:
            continue  # counted through the missing_columns argument
        elif "type" in name:
            summary["wrong_data_types"] += count
        elif "be_in_set" in name:
            summary["invalid_categories"] += count
        elif "be_between" in name:
            summary["invalid_ranges"] += count
        elif "be_of_type" in name or "type" in name:
            summary["wrong_data_types"] += count
        elif "outlier" in name:
            summary["outliers"] += count
    return summary
