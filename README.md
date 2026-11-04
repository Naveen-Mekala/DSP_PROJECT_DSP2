# Athlete Recovery Prediction — DSP MLOps Platform

An end-to-end ML application that predicts an athlete's recovery score (0–100) from training, sleep
and biometric data. New data is ingested and validated continuously, predictions are made on a
schedule and on demand, the model is retrained and promoted only when it is better, and data quality
and model behaviour are monitored with dashboards and Microsoft Teams alerts.

## Architecture

```mermaid
flowchart LR
  RAW[raw_data] -->|every 5 min| ING[Ingestion DAG]
  ING -->|GX: 2 suites, 59 rules| GOOD[good_data]
  ING --> BAD[bad_data]
  ING -->|statistics| DB[(PostgreSQL)]
  ING -->|Medium/High| TEAMS[Teams]
  ING --> DOCS[GX Data Docs] --> NGINX[nginx :8088]
  GOOD -->|every 5 min, new files only| PRED[Prediction DAG] --> API[FastAPI]
  UI[Streamlit] --> API
  API -->|predictions + features| DB
  GOOD --> TRAIN[Training DAG] --> MLF[MLflow registry]
  TRAIN -->|training stats| DB
  TRAIN -->|not promoted| TEAMS
  TRAIN -->|promoted: /reload-model| API
  TRAIN -->|used data| ARCH[archived_data]
  MLF -->|@champion| API
  DRIFT[Drift DAG] --> DB
  DB --> GRAF[Grafana: 2 dashboards + alerts] --> TEAMS
```

| Job | Tasks | Schedule |
|---|---|---|
| `athlete_data_ingestion` | `read_data → validate_data → send_alerts / save_file / save_statistics` | every 5 min |
| `athlete_prediction_job` | `check_for_new_data → make_predictions` | every 5 min |
| `athlete_model_retraining` | `check_for_new_data → load_data → train_model → save_training_stats → evaluate_candidate → promote_to_champion → notify_api_reload + archive_data` or `send_ml_alert` | hourly (skips without enough new data) |
| `athlete_drift_monitoring` | `calculate_drift` | every 15 min |

Schedules are environment variables (`INGESTION_SCHEDULE`, …) — e.g. set `INGESTION_SCHEDULE=* * * * *` in `.env` for a faster demo.

## Services and local URLs

| Service | URL | Login |
|---|---|---|
| Streamlit web app | http://localhost:8502 | — |
| FastAPI (Swagger) | http://localhost:8001/docs | — |
| Airflow 3 | http://localhost:8080 | `admin` / generated password (see below) |
| MLflow | http://localhost:5001 | — |
| Grafana | http://localhost:3000 | `admin` / `GRAFANA_PASSWORD` (default `admin`) |
| GX Data Docs (nginx) | http://localhost:8088 | — |
| PostgreSQL | localhost:5432 | from `.env` |

Airflow password: `docker compose exec airflow-apiserver cat /opt/airflow/simple_auth_manager_passwords.json.generated`

## Start the project

```bash
cp .env.example .env          # set passwords; add Teams webhooks to receive alerts
docker compose up --build -d
docker compose ps             # every service up; airflow-init and db-bootstrap "Exited (0)"
```

On a fresh setup the API starts with the committed fallback model `models/model.pkl.gz`. If that file
is missing the API still starts (`/health` → `model_loaded: false`): trigger the
`athlete_model_retraining` DAG once — with no champion it bootstraps v1 from `data/clean`, promotes it
and reloads the API. Never use `docker compose down -v` (it deletes the database and MLflow volumes).

## Data flow

| Folder | Content |
|---|---|
| `data/clean/` | baseline labelled dataset (training baseline) |
| `data/raw_data/` | incoming files; each file is removed once the ingestion job has read it |
| `data/good_data/` | rows without problems — scored by the prediction job, used for retraining |
| `data/bad_data/` | rows with problems, with a `dq_errors` column giving the reason per row |
| `data/archived_data/` | good data already used to train a promoted model |
| `data/demo/` | the defense demo files (see below) |

Generate data:

```bash
python scripts/generate_errors.py --input data/clean/athlete_recovery_synthetic.csv \
    --output data/corrupted/athlete_recovery_corrupted.csv --p-missing 0.02 --p-range 0.02 \
    --p-category 0.01 --p-type 0.005 --p-duplicate 0.003 --p-outlier 0.005          # --seed N optional
python scripts/split_dataset.py --dataset data/corrupted/athlete_recovery_corrupted.csv \
    --raw-data data/raw_data --num-files 800 --p-missing-column 0.02
```

## Data quality

All rules live in Great Expectations (`validation/build_suites.py` creates them; `gx/gx/` stores them).
Each file is validated in two passes, each producing a Data Docs report:

| Suite | Runs on | Rules | Category |
|---|---|---|---|
| `athlete_schema_suite` (20) | the raw file | exact column set | **schema** |
| | | value types (text in a numeric column) | **type** |
| `athlete_suite` (39) | numeric columns parsed | no missing values in any column | **completeness** |
| | | ranges (e.g. Age 18–60, Recovery 0–100) and allowed categories | **validity** |
| | | unique (`Athlete_ID`, `Day`) | **consistency** |

Why two passes: a range check on a column that also contains text fails for the whole column in GX;
checking types on the raw file first keeps every result at row level. A file with a missing column is
rejected as a whole. Criticality: High (> 50 % invalid or a schema error), Medium (≥ 10 %), Low (> 0).
Medium and High files send a Teams alert with a link to that file's report on nginx.

Validate any file by hand: `python validation/run_validation.py data/demo/demo_5_mixed.csv`, or the
**validation** page in Streamlit.

Dataset decisions: the 604 missing `Sleep_Duration_Hours` of the clean dataset were imputed with the
median (7.5 h, `scripts/impute_sleep_median.py`); the one missing `Training_Intensity` was kept, so
the full clean file passes 58/59 rules and that single row goes to `bad_data`.

## Model lifecycle

- **Training data**: `data/clean` baseline + new validated rows from `good_data` (deduplicated).
  Retraining runs only when at least `MIN_NEW_TRAINING_ROWS` (100) new rows are available.
- **Fair comparison**: athletes with `Athlete_ID % 5 == 0` form a fixed holdout that no model trains
  on. Candidate and champion are scored on these same rows.
- **Promotion** (`@champion` alias) only if the candidate's holdout RMSE is ≤ the champion's **and**
  inference takes ≤ `MAX_INFERENCE_MS_PER_ROW` (10 ms). A champion trained before this protocol is
  replaced by the first compliant candidate. Comparison metrics and the decision are logged on the
  candidate's MLflow run.
- **Promoted** → API reloads the model, used files move to `archived_data`.
  **Not promoted** → Teams ML alert with a link to the MLflow run.
- Training statistics are stored per model version; drift is measured against the **champion's**.

Manual run: `docker compose exec airflow-scheduler python /opt/airflow/project/scripts/train_model.py`

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | status, `model_loaded`, active model version |
| `/predict` | POST | one athlete object, or `{"features": [...], "source": "scheduled"}` |
| `/batch-predict` | POST | CSV upload → CSV with predictions |
| `/past-predictions` | GET | `start_date`, `end_date`, `source=webapp\|scheduled\|all`, `limit` |
| `/reload-model` | POST | load the current MLflow `@champion` |
| `/monitoring/summary` | GET | recent ingestion and drift statistics |

Every prediction is stored with its input features, source and model version. Database sessions are
injected with `Depends(get_db)`; startup uses FastAPI `lifespan`.

## Monitoring and alerts

Grafana (folder *DSP Monitoring*):

- **Athlete Recovery — Data Quality** (9 panels): files and rows ingested, invalid %, High files,
  valid vs invalid rows, errors by the 5 categories, invalid % per file, files per criticality, and a
  table of ingested files with a link to each Data Docs report.
- **Athlete Recovery — Model Monitoring** (11 panels): predictions over time by source, predicted
  score over time, prediction distribution, numeric and categorical drift (PSI), and training vs
  serving tables (feature means and category shares).

Alerts go to two Teams channels — set `TEAMS_DATA_WEBHOOK_URL` and `TEAMS_ML_WEBHOOK_URL` in `.env`
(Teams channel → *Workflows* → "Post to a channel when a webhook request is received"):

| Channel | Source | When |
|---|---|---|
| Data | ingestion DAG | file with Medium/High criticality |
| Data | Grafana | > 30 % invalid rows in 15 min; High-criticality file in 10 min |
| ML | training DAG | candidate not promoted |
| ML | Grafana | feature drift (PSI ≥ 0.2); average prediction shifts by > 15 points |

Without webhooks the pipeline still runs and alerts are written to the task logs.
To change a dashboard, edit `grafana/build_dashboards.py` and run it.

## Defense demo

```bash
python scripts/create_demo_files.py            # (already committed in data/demo/)
cp data/demo/demo_5_mixed.csv data/raw_data/   # then trigger athlete_data_ingestion in Airflow
```

| File | Expected result |
|---|---|
| `demo_1_all_errors.csv` | 10/10 rows bad, High, Teams alert |
| `demo_2..4_clean.csv` | 10/10 rows good |
| `demo_5_mixed.csv` | 6/21 bad (one per category), Medium, alert |
| `demo_6_missing_column.csv` | whole file bad, schema error, High |

## Tests

```bash
pip install -r requirements.txt flake8
pytest -q        # 44 tests: GX rules on the demo files, API endpoints, alerts, scripts, drift
flake8 api database scripts tests airflow/dags streamlit validation --count --select=E9,F63,F7,F82
```

API tests use SQLite and an empty MLflow registry, so they need no running service.

## CI/CD

- `ci.yml`: on pull requests to `develop` — lint and tests as separate jobs.
- `cd.yml`: on push to `main` — semantic version tag and GitHub Release.
