"""Create or update the Great Expectations suites, validation definitions and checkpoints.

Idempotent: existing expectations are kept (same IDs); only missing ones are added.
All data-quality rules of the project live here, not in the Airflow DAG code.

Two suites validate every ingested file:
  - athlete_schema_suite : schema (column set) and value types, on the raw file
  - athlete_suite        : completeness, validity and consistency, on the typed file

Run from the project root:  python validation/build_suites.py
"""
from pathlib import Path

import great_expectations as gx
import great_expectations.expectations as gxe

ROOT = Path(__file__).resolve().parents[1]
GX_DIR = ROOT / "gx" / "gx"

COLUMNS = [
    "Athlete_ID", "Day", "Day_of_Week", "Week", "Age", "Gender", "Sport_Type",
    "Training_Type", "Training_Duration_Min", "Training_Intensity", "Sleep_Duration_Hours",
    "Caffeine_Intake_mg", "Stress_Level", "Resting_Heart_Rate", "HRV_ms", "Mood_Score",
    "Muscle_Soreness", "Energy_Level", "Recovery_Score",
]
STRING_COLUMNS = ["Gender", "Sport_Type", "Training_Type", "Stress_Level"]
NUMERIC_COLUMNS = [c for c in COLUMNS if c not in STRING_COLUMNS]
NUMERIC_TYPES = ["int", "float", "int64", "float64", "int32", "float32"]

RANGES = {  # column: (min, max) — business rules for the athlete dataset
    "Day": (1, 366), "Day_of_Week": (1, 7), "Week": (1, 53),
    "Age": (18, 60), "Training_Duration_Min": (1, 300), "Training_Intensity": (0, 10),
    "Sleep_Duration_Hours": (0, 24), "Caffeine_Intake_mg": (0, 1000),
    "Resting_Heart_Rate": (30, 220), "HRV_ms": (0, 300), "Mood_Score": (1, 10),
    "Muscle_Soreness": (0, 10), "Energy_Level": (0, 10), "Recovery_Score": (0, 100),
}
CATEGORIES = {
    "Gender": ["Male", "Female", "Non-binary"],
    "Sport_Type": ["Combat", "Endurance", "Mixed", "Strength", "Team Sport"],
    "Training_Type": ["Cardio", "HIIT", "Rest", "Strength", "Yoga"],
    "Stress_Level": ["Low", "Medium", "High"],
}


def _key(exp):
    kw = exp.configuration.kwargs if hasattr(exp, "configuration") else exp.kwargs
    col = kw.get("column") or ",".join(kw.get("column_list") or []) or "table"
    return (exp.expectation_type, col)


def _add_missing(suite, expectations):
    existing = {_key(e) for e in suite.expectations}
    added = 0
    for exp in expectations:
        if _key(exp) not in existing:
            suite.add_expectation(exp)
            added += 1
    return added


def content_expectations():
    exps = [gxe.ExpectColumnToExist(column="Athlete_ID")]
    exps += [gxe.ExpectColumnValuesToNotBeNull(column=c) for c in COLUMNS]               # completeness
    exps += [gxe.ExpectColumnValuesToBeBetween(column=c, min_value=lo, max_value=hi)     # validity
             for c, (lo, hi) in RANGES.items()]
    exps += [gxe.ExpectColumnValuesToBeInSet(column=c, value_set=v) for c, v in CATEGORIES.items()]
    exps += [gxe.ExpectCompoundColumnsToBeUnique(column_list=["Athlete_ID", "Day"])]     # consistency
    return exps


def schema_expectations():
    exps = [gxe.ExpectTableColumnsToMatchSet(column_set=COLUMNS, exact_match=True)]      # schema
    exps += [gxe.ExpectColumnValuesToBeInTypeList(column=c, type_list=NUMERIC_TYPES)     # type
             for c in NUMERIC_COLUMNS]
    exps += [gxe.ExpectColumnValuesToBeInTypeList(column=c, type_list=["str"]) for c in STRING_COLUMNS]
    return exps


def _get_or_create_suite(ctx, name):
    try:
        return ctx.suites.get(name)
    except Exception:
        return ctx.suites.add(gx.ExpectationSuite(name=name))


def _ensure_validation(ctx, name, suite, batch_definition):
    try:
        return ctx.validation_definitions.get(name)
    except Exception:
        return ctx.validation_definitions.add(
            gx.ValidationDefinition(name=name, data=batch_definition, suite=suite))


def _ensure_checkpoint(ctx, name, validation):
    try:
        return ctx.checkpoints.get(name)
    except Exception:
        return ctx.checkpoints.add(gx.Checkpoint(
            name=name, validation_definitions=[validation], result_format="COMPLETE",
            actions=[gx.checkpoint.UpdateDataDocsAction(name="update_data_docs")]))


def main():
    ctx = gx.get_context(mode="file", project_root_dir=str(GX_DIR.parent))
    batch = ctx.data_sources.get("athlete_datasource").get_asset(
        "athlete_dataset").get_batch_definition("athlete_batch")

    content = _get_or_create_suite(ctx, "athlete_suite")
    n_content = _add_missing(content, content_expectations())
    content.save()
    schema = _get_or_create_suite(ctx, "athlete_schema_suite")
    n_schema = _add_missing(schema, schema_expectations())
    schema.save()

    content_vd = _ensure_validation(ctx, "athlete_validation", content, batch)
    schema_vd = _ensure_validation(ctx, "athlete_schema_validation", schema, batch)
    _ensure_checkpoint(ctx, "athlete_checkpoint", content_vd)
    _ensure_checkpoint(ctx, "athlete_schema_checkpoint", schema_vd)
    ctx.build_data_docs()
    print(f"athlete_suite: {len(content.expectations)} expectations (+{n_content} added)")
    print(f"athlete_schema_suite: {len(schema.expectations)} expectations (+{n_schema} added)")


if __name__ == "__main__":
    main()
