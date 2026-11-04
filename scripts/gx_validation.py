"""Run the project's Great Expectations checkpoints on one dataframe.

Used by the Airflow ingestion DAG and the Streamlit validation page, so both apply
exactly the same rules. The rules themselves live in the GX suites
(see validation/build_suites.py); this module only runs them and reads the results.

Two passes (see build_suites.py for why):
  1. athlete_schema_checkpoint on the raw frame   -> schema + type errors
  2. athlete_checkpoint on the typed frame        -> completeness, validity, consistency
"""
import os
from pathlib import Path

import pandas as pd

from scripts.data_quality import calculate_criticality, categorize_expectation, summarize_validation_errors

DEFAULT_GX_DIR = Path(__file__).resolve().parents[1] / "gx" / "gx"
SCHEMA_CHECKPOINT = "athlete_schema_checkpoint"
CONTENT_CHECKPOINT = "athlete_checkpoint"
NUMERIC_COLUMNS = [
    "Athlete_ID", "Day", "Day_of_Week", "Week", "Age", "Training_Duration_Min",
    "Training_Intensity", "Sleep_Duration_Hours", "Caffeine_Intake_mg", "Resting_Heart_Rate",
    "HRV_ms", "Mood_Score", "Muscle_Soreness", "Energy_Level", "Recovery_Score",
]
_CONTEXTS = {}


def get_context(context_root_dir=None):
    import great_expectations as gx
    root = str(context_root_dir or os.getenv("GX_CONTEXT_ROOT_DIR", DEFAULT_GX_DIR))
    if root not in _CONTEXTS:
        _CONTEXTS[root] = gx.get_context(context_root_dir=root)
    return _CONTEXTS[root]


def _to_number(value):
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value          # keep the text so the type expectation can flag this row
    return value


def prepare_frames(df: pd.DataFrame):
    """Return (schema_frame, content_frame).

    schema_frame keeps unparseable text inside numeric columns (row-level type errors).
    content_frame converts numeric columns to numbers; unparseable values become null.
    """
    schema_frame = df.copy()
    content_frame = df.copy()
    for col in NUMERIC_COLUMNS:
        if col in df.columns and df[col].dtype == object:
            schema_frame[col] = df[col].map(_to_number)
            content_frame[col] = pd.to_numeric(df[col], errors="coerce")
    return schema_frame.reset_index(drop=True), content_frame.reset_index(drop=True)


def docs_url(context, result_identifier):
    """Turn the file:// Data Docs link of one validation run into an nginx URL."""
    base = os.getenv("DATA_DOCS_BASE_URL", "http://localhost:8088").rstrip("/")
    try:
        urls = context.get_docs_sites_urls(resource_identifier=result_identifier)
        site_url = urls[0]["site_url"] if urls else ""
    except Exception:
        site_url = ""
    marker = "local_site/"
    if marker in site_url:
        return f"{base}/{site_url.split(marker, 1)[1]}"
    return base + "/"


def _read_results(checkpoint_result):
    identifier, validation = next(iter(checkpoint_result.run_results.items()))
    return identifier, validation


def run_validation(df: pd.DataFrame, context_root_dir=None) -> dict:
    """Validate one file. Returns invalid rows, error counts per category and report links."""
    context = get_context(context_root_dir)
    schema_frame, content_frame = prepare_frames(df)
    total = len(content_frame)
    invalid = set()
    row_errors = {}
    error_counts = {}
    category_counts = {"completeness": 0, "validity": 0, "consistency": 0, "schema": 0, "type": 0}
    missing_columns = 0
    reports = {}
    evaluated = passed = 0

    for checkpoint_name, frame in ((SCHEMA_CHECKPOINT, schema_frame), (CONTENT_CHECKPOINT, content_frame)):
        result = context.checkpoints.get(checkpoint_name).run(batch_parameters={"dataframe": frame})
        identifier, validation = _read_results(result)
        reports[checkpoint_name] = docs_url(context, identifier)
        stats = validation.statistics
        evaluated += int(stats.get("evaluated_expectations", 0))
        passed += int(stats.get("successful_expectations", 0))
        for item in validation.results:
            if item.success:
                continue
            exp_type = item.expectation_config.type
            kwargs = item.expectation_config.kwargs
            column = kwargs.get("column") or "+".join(kwargs.get("column_list") or []) or "table"
            category = categorize_expectation(exp_type)
            res = item.result or {}
            if exp_type == "expect_table_columns_to_match_set":
                mismatched = (res.get("details") or {}).get("mismatched") or {}
                count = len(mismatched.get("missing") or []) + len(mismatched.get("unexpected") or []) or 1
                missing_columns += count
                category_counts["schema"] += count
                error_counts[exp_type] = error_counts.get(exp_type, 0) + count
                continue
            referenced = [kwargs["column"]] if kwargs.get("column") else list(kwargs.get("column_list") or [])
            if any(c not in frame.columns for c in referenced):
                continue  # rule on an absent column: already reported as a schema error
            indices = res.get("unexpected_index_list")
            if indices is None:
                # Column-level failure (e.g. the column is missing): no row can be trusted.
                indices = list(range(total))
            indices = [i for i in indices if isinstance(i, int)]
            count = int(res.get("unexpected_count") or len(indices))
            error_counts[exp_type] = error_counts.get(exp_type, 0) + count
            category_counts[category] = category_counts.get(category, 0) + count
            for i in indices:
                invalid.add(i)
                row_errors.setdefault(i, []).append(f"{column}:{category}")

    if missing_columns:
        invalid = set(range(total))      # a file with the wrong schema is rejected as a whole
    invalid_pct = round(len(invalid) / total * 100, 2) if total else 0.0
    return {
        "total_rows": total,
        "invalid_row_indices": sorted(invalid),
        "row_errors": {int(k): ";".join(v) for k, v in row_errors.items()},
        "error_counts": error_counts,
        "category_counts": category_counts,
        "summary": summarize_validation_errors(error_counts, missing_columns=missing_columns),
        "missing_columns": missing_columns,
        "invalid_percentage": invalid_pct,
        "criticality": calculate_criticality(invalid_pct, missing_columns=bool(missing_columns)),
        "data_docs_path": reports.get(CONTENT_CHECKPOINT, ""),
        "schema_report_url": reports.get(SCHEMA_CHECKPOINT, ""),
        "expectations_evaluated": evaluated,
        "expectations_passed": passed,
        "success": not invalid,
    }
