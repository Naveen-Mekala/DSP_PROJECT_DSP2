"""Great Expectations checkpoint helper for dataframe-based ingestion batches."""
import os
import pandas as pd
import great_expectations as gx

GX_CONTEXT_ROOT_DIR = os.getenv("GX_CONTEXT_ROOT_DIR", "/opt/airflow/project/gx/gx")
CHECKPOINT_NAME = "athlete_checkpoint"
_CONTEXT = None


def get_context():
    global _CONTEXT
    if _CONTEXT is None:
        _CONTEXT = gx.get_context(context_root_dir=GX_CONTEXT_ROOT_DIR)
    return _CONTEXT


def run_validation(df: pd.DataFrame) -> dict:
    """Run the configured GX suite, update Data Docs and return failed row indices."""
    context = get_context()
    checkpoint = context.checkpoints.get(CHECKPOINT_NAME)
    checkpoint_result = checkpoint.run(batch_parameters={"dataframe": df})
    validation_result = next(iter(checkpoint_result.run_results.values()))
    invalid_indices = set()
    error_counts = {}
    total_rows = len(df)
    missing_columns = False

    for item in validation_result["results"]:
        if item.get("success", False):
            continue
        config = item.get("expectation_config", {})
        expectation_type = config.get("type", "unknown_expectation")
        kwargs = config.get("kwargs", {})
        if expectation_type == "expect_table_columns_to_match_set":
            missing_columns = True
            continue
        result = item.get("result", {}) or {}
        count = result.get("unexpected_count", total_rows)
        indices = result.get("partial_unexpected_index_list") or list(df.index)
        invalid_indices.update(indices)
        error_counts[expectation_type] = error_counts.get(expectation_type, 0) + int(count or 0)

    invalid_pct = len(invalid_indices) / total_rows * 100 if total_rows else 0.0
    if missing_columns or invalid_pct > 50:
        criticality = "High"
    elif invalid_pct >= 10:
        criticality = "Medium"
    elif invalid_pct > 0:
        criticality = "Low"
    else:
        criticality = "None"
    try:
        docs = context.get_docs_sites_urls()
        docs_url = docs[0].get("site_url", "") if docs else ""
    except Exception:
        docs_url = ""
    return {
        "invalid_row_indices": sorted(invalid_indices),
        "error_counts": error_counts,
        "missing_columns": missing_columns,
        "criticality": criticality,
        "invalid_percentage": round(invalid_pct, 2),
        "data_docs_path": docs_url,
        "success": not missing_columns and not invalid_indices,
    }
