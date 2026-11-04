"""Data ingestion job: read -> validate (Great Expectations) -> alert / split / save statistics.

read_data       picks one random file in raw_data, reads it and removes it from raw_data
validate_data   runs the GX checkpoints (all rules live in the GX suites)
send_alerts     Teams alert (data channel) when criticality is Medium or High, with the report link
save_file       rows without problems -> good_data, rows with problems -> bad_data
save_statistics data quality statistics -> ingestion_stats table (PostgreSQL)
"""
import os
import random
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd
from airflow.exceptions import AirflowSkipException
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import dag, task

PROJECT_DIR = Path(os.getenv("DSP_PROJECT_DIR", "/opt/airflow/project"))
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
RAW_DIR = PROJECT_DIR / "data" / "raw_data"
GOOD_DIR = PROJECT_DIR / "data" / "good_data"
BAD_DIR = PROJECT_DIR / "data" / "bad_data"
GX_DIR = PROJECT_DIR / "gx" / "gx"
SCHEDULE = os.getenv("INGESTION_SCHEDULE", "*/5 * * * *")


@dag(schedule=SCHEDULE, start_date=datetime(2026, 1, 1), catchup=False,
     max_active_runs=1, tags=["athlete", "ingestion", "data-quality"])
def athlete_data_ingestion():

    @task
    def read_data():
        files = sorted(RAW_DIR.glob("*.csv"))
        if not files:
            raise AirflowSkipException("No files available in raw_data")
        selected = random.choice(files)
        content = selected.read_text()
        selected.unlink()  # the file is now owned by this run (content travels through XCom)
        return {"filename": selected.name, "content": content}

    @task
    def validate_data(batch):
        from scripts.gx_validation import run_validation

        df = pd.read_csv(StringIO(batch["content"]))
        result = run_validation(df, context_root_dir=GX_DIR)
        invalid = result["invalid_row_indices"]
        return {
            "filename": batch["filename"],
            "content": batch["content"],
            "total_rows": result["total_rows"],
            "valid_rows": result["total_rows"] - len(invalid),
            "invalid_rows": len(invalid),
            "invalid_percentage": result["invalid_percentage"],
            "criticality": result["criticality"],
            "validation_success": result["success"],
            "invalid_indices": invalid,
            "row_errors": {str(k): v for k, v in result["row_errors"].items()},
            "category_counts": result["category_counts"],
            "error_counts": result["error_counts"],
            **result["summary"],
            "report_file": result["data_docs_path"],
            "schema_report": result["schema_report_url"],
        }

    @task
    def send_alerts(result):
        from scripts.teams import send_alert

        if result["criticality"] not in ("Medium", "High"):
            print(f"No alert required. Criticality: {result['criticality']}")
            return
        cats = result["category_counts"]
        send_alert(
            "data",
            f"Data quality alert: {result['criticality']} criticality",
            {
                "File": result["filename"],
                "Invalid rows": f"{result['invalid_rows']}/{result['total_rows']} ({result['invalid_percentage']}%)",
                "Errors": ", ".join(f"{k}: {v}" for k, v in cats.items() if v) or "none",
                "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            link=result["report_file"],
            link_title="Open Data Docs report",
            severity="attention" if result["criticality"] == "High" else "warning",
        )

    @task
    def save_file(result):
        GOOD_DIR.mkdir(parents=True, exist_ok=True)
        BAD_DIR.mkdir(parents=True, exist_ok=True)
        df = pd.read_csv(StringIO(result["content"]))
        stem = Path(result["filename"]).stem
        invalid = set(result["invalid_indices"])
        bad = df.loc[df.index.isin(invalid)].copy()
        good = df.loc[~df.index.isin(invalid)]
        if not good.empty:
            good.to_csv(GOOD_DIR / f"{stem}.csv", index=False)
        if not bad.empty:
            # Keep the reason of each rejection next to the row for later analysis.
            bad["dq_errors"] = [result["row_errors"].get(str(i), "schema") for i in bad.index]
            bad.to_csv(BAD_DIR / f"{stem}.csv", index=False)
        print(f"{result['filename']}: {len(good)} rows -> good_data, {len(bad)} rows -> bad_data")

    @task
    def save_statistics(result):
        hook = PostgresHook(postgres_conn_id="postgres_default")
        hook.run("""
            CREATE TABLE IF NOT EXISTS ingestion_stats (
                id SERIAL PRIMARY KEY, filename VARCHAR NOT NULL,
                ingestion_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                total_rows INTEGER, valid_rows INTEGER, invalid_rows INTEGER, invalid_percentage FLOAT,
                missing_values INTEGER DEFAULT 0, invalid_ranges INTEGER DEFAULT 0,
                invalid_categories INTEGER DEFAULT 0, missing_columns INTEGER DEFAULT 0,
                wrong_data_types INTEGER DEFAULT 0, duplicate_ids INTEGER DEFAULT 0,
                outliers INTEGER DEFAULT 0, criticality VARCHAR, validation_success VARCHAR,
                report_file VARCHAR)
        """)
        hook.run(
            """
            INSERT INTO ingestion_stats (filename, total_rows, valid_rows, invalid_rows,
                invalid_percentage, missing_values, invalid_ranges, invalid_categories,
                missing_columns, wrong_data_types, duplicate_ids, outliers, criticality,
                validation_success, report_file)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            parameters=(
                result["filename"], result["total_rows"], result["valid_rows"], result["invalid_rows"],
                result["invalid_percentage"], result.get(
                    "missing_values", 0), result.get(
                    "invalid_ranges", 0),
                result.get("invalid_categories", 0), result.get("missing_columns", 0),
                result.get("wrong_data_types", 0), result.get("duplicate_ids", 0), result.get("outliers", 0),
                result["criticality"], str(result["validation_success"]), result.get("report_file", ""),
            ),
        )

    validated = validate_data(read_data())
    send_alerts(validated)
    save_file(validated)
    save_statistics(validated)


athlete_data_ingestion()
