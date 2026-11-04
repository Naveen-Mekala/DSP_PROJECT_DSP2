"""Generate the two provisioned Grafana dashboards (run after changing a panel):

    python grafana/build_dashboards.py

  dashboards/athlete-data-quality.json     ingestion monitoring (5 error categories, criticality)
  dashboards/athlete-model-monitoring.json predictions over time + training vs serving (drift)
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "dashboards"
DS = {"type": "postgres", "uid": "athlete-postgres"}
CATEGORY_COLORS = {"Completeness": "blue", "Validity": "orange", "Consistency": "purple",
                   "Schema": "red", "Type": "yellow"}
CRITICALITY_COLORS = {"None": "green", "Low": "yellow", "Medium": "orange", "High": "red"}


def target(sql, fmt="time_series"):
    return [{"refId": "A", "datasource": DS, "rawSql": " ".join(sql.split()), "format": fmt,
             "rawQuery": True, "editorMode": "code"}]


def color_overrides(colors):
    return [{"matcher": {"id": "byName", "options": name},
             "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}]}
            for name, c in colors.items()]


def stat(pid, title, sql, x, w=6, unit="short", steps=None, description=""):
    steps = steps or [{"color": "blue", "value": None}]
    return {"id": pid, "type": "stat", "title": title, "description": description, "datasource": DS,
            "gridPos": {"h": 4, "w": w, "x": x, "y": 0}, "targets": target(sql, "table"),
            "fieldConfig": {"defaults": {"unit": unit, "decimals": 1 if unit == "percent" else None,
                                         "thresholds": {"mode": "absolute", "steps": steps}}, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": "background", "graphMode": "none", "textMode": "value"}}


def timeseries(pid, title, sql, grid, unit="short", stacked=False, bars=False, overrides=None,
               threshold=None, description="", points=False):
    custom = {"drawStyle": "bars" if bars else ("points" if points else "line"), "lineWidth": 2,
              "fillOpacity": 70 if bars else 10, "pointSize": 6, "showPoints": "auto",
              "stacking": {"mode": "normal" if stacked else "none", "group": "A"}, "spanNulls": True}
    thresholds = {"mode": "absolute", "steps": [{"color": "green", "value": None}]}
    if threshold is not None:
        custom["thresholdsStyle"] = {"mode": "line+area"}
        thresholds["steps"].append({"color": "red", "value": threshold})
    return {"id": pid, "type": "timeseries", "title": title, "description": description, "datasource": DS,
            "gridPos": grid, "targets": target(sql),
            "fieldConfig": {"defaults": {"unit": unit, "min": 0, "custom": custom, "thresholds": thresholds},
                            "overrides": overrides or []},
            "options": {"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                        "tooltip": {"mode": "multi", "sort": "desc"}}}


def table(pid, title, sql, grid, overrides=None, description=""):
    return {"id": pid, "type": "table", "title": title, "description": description, "datasource": DS,
            "gridPos": grid, "targets": target(sql, "table"),
            "fieldConfig": {"defaults": {"custom": {"align": "auto", "cellOptions": {"type": "auto"}}},
                            "overrides": overrides or []},
            "options": {"showHeader": True, "footer": {"show": False}}}


def dashboard(uid, title, tags, panels, time_from="now-24h"):
    return {"uid": uid, "title": title, "tags": tags, "timezone": "browser", "schemaVersion": 39,
            "version": 1, "refresh": "30s", "editable": True, "graphTooltip": 1,
            "time": {"from": time_from, "to": "now"}, "timepicker": {},
            "annotations": {"list": []}, "templating": {"list": []}, "links": [], "panels": panels}


# ------------------------------------------------------------------ dashboard 1: data quality
data_quality = dashboard("athlete-data-quality", "Athlete Recovery — Data Quality", ["dsp", "data-quality"], [
    stat(1, "Files ingested", "SELECT count(*) AS value FROM ingestion_stats WHERE $__timeFilter(ingestion_time)", 0),
    stat(2, "Rows ingested", "SELECT COALESCE(sum(total_rows), 0) AS value FROM ingestion_stats "
         "WHERE $__timeFilter(ingestion_time)", 6),
    stat(3, "Invalid rows", "SELECT COALESCE(100.0 * sum(invalid_rows) / NULLIF(sum(total_rows), 0), 0) AS value "
         "FROM ingestion_stats WHERE $__timeFilter(ingestion_time)", 12, unit="percent",
         steps=[{"color": "green", "value": None}, {"color": "orange", "value": 10}, {"color": "red", "value": 50}]),
    stat(4, "High-criticality files", "SELECT count(*) AS value FROM ingestion_stats "
         "WHERE $__timeFilter(ingestion_time) AND criticality = 'High'", 18,
         steps=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),
    timeseries(5, "Valid vs invalid rows",
               """SELECT $__timeGroupAlias(ingestion_time, $__interval), sum(valid_rows) AS "Valid",
                  sum(invalid_rows) AS "Invalid" FROM ingestion_stats WHERE $__timeFilter(ingestion_time)
                  GROUP BY 1 ORDER BY 1""",
               {"h": 8, "w": 12, "x": 0, "y": 4}, stacked=True, bars=True,
               overrides=color_overrides({"Valid": "green", "Invalid": "red"}),
               description="Rows per interval, split by the ingestion job into good_data and bad_data."),
    timeseries(6, "Errors by category",
               """SELECT $__timeGroupAlias(ingestion_time, $__interval),
                  sum(missing_values) AS "Completeness",
                  sum(invalid_ranges + invalid_categories + outliers) AS "Validity",
                  sum(duplicate_ids) AS "Consistency", sum(missing_columns) AS "Schema",
                  sum(wrong_data_types) AS "Type"
                  FROM ingestion_stats WHERE $__timeFilter(ingestion_time) GROUP BY 1 ORDER BY 1""",
               {"h": 8, "w": 12, "x": 12, "y": 4}, stacked=True, bars=True,
               overrides=color_overrides(CATEGORY_COLORS),
               description="Completeness = missing values; Validity = out-of-range values and unknown categories; "
                           "Consistency = duplicated (Athlete_ID, Day); Schema = missing/unexpected columns; "
                           "Type = text in numeric columns."),
    timeseries(7, "Invalid rows per file (%)",
               """SELECT ingestion_time AS time, invalid_percentage AS "Invalid %" FROM ingestion_stats
                  WHERE $__timeFilter(ingestion_time) ORDER BY 1""",
               {"h": 8, "w": 12, "x": 0, "y": 12}, unit="percent", threshold=50, points=True,
               description="One point per ingested file. Above 50% the file is High criticality."),
    timeseries(8, "Files per criticality",
               """SELECT $__timeGroupAlias(ingestion_time, $__interval),
                  sum(CASE WHEN criticality = 'None' THEN 1 ELSE 0 END) AS "None",
                  sum(CASE WHEN criticality = 'Low' THEN 1 ELSE 0 END) AS "Low",
                  sum(CASE WHEN criticality = 'Medium' THEN 1 ELSE 0 END) AS "Medium",
                  sum(CASE WHEN criticality = 'High' THEN 1 ELSE 0 END) AS "High"
                  FROM ingestion_stats WHERE $__timeFilter(ingestion_time) GROUP BY 1 ORDER BY 1""",
               {"h": 8, "w": 12, "x": 12, "y": 12}, stacked=True, bars=True,
               overrides=color_overrides(CRITICALITY_COLORS),
               description="Medium and High files trigger a Teams alert on the data channel."),
    table(9, "Ingested files (latest first)",
          """SELECT ingestion_time AS "Time", filename AS "File", total_rows AS "Rows",
             invalid_rows AS "Invalid rows", invalid_percentage AS "Invalid %", criticality AS "Criticality",
             missing_values AS "Completeness", invalid_ranges + invalid_categories + outliers AS "Validity",
             duplicate_ids AS "Consistency", missing_columns AS "Schema", wrong_data_types AS "Type",
             report_file AS "Report"
             FROM ingestion_stats WHERE $__timeFilter(ingestion_time) ORDER BY ingestion_time DESC LIMIT 200""",
          {"h": 10, "w": 24, "x": 0, "y": 20},
          overrides=[
              {"matcher": {"id": "byName", "options": "Report"},
               "properties": [{"id": "links", "value": [{"title": "Open Data Docs report", "url": "${__value.raw}",
                                                         "targetBlank": True}]},
                              {"id": "custom.width", "value": 140}]},
              {"matcher": {"id": "byName", "options": "Criticality"},
               "properties": [{"id": "custom.cellOptions", "value": {"type": "color-background"}},
                              {"id": "mappings", "value": [{"type": "value", "options": {
                                  k: {"color": v, "index": i} for i, (k, v) in enumerate(CRITICALITY_COLORS.items())}}]}]},
          ],
          description="Click a Report cell to open that file's Great Expectations validation report."),
])

# ------------------------------------------------------------------ dashboard 2: model monitoring
TRAINING_VERSION = """COALESCE(
    (SELECT model_version FROM predictions WHERE model_version ~ '^[0-9]+$'
     ORDER BY prediction_time DESC LIMIT 1),
    (SELECT model_version FROM training_stats ORDER BY training_time DESC LIMIT 1))"""

model_monitoring = dashboard("athlete-model-monitoring", "Athlete Recovery — Model Monitoring",
                             ["dsp", "model", "drift"], [
                                 stat(
                                     1,
                                     "Predictions",
                                     "SELECT count(*) AS value FROM predictions WHERE $__timeFilter(prediction_time)",
                                     0),
                                 stat(2, "Model in production", "SELECT 'v' || model_version AS value FROM predictions "
                                      "ORDER BY prediction_time DESC LIMIT 1", 6, unit="string"),
                                 stat(3, "Average predicted recovery score", """SELECT COALESCE(avg("Prediction"), 0) AS value FROM predictions
         WHERE $__timeFilter(prediction_time)""", 12),
                                 stat(4, "Drifted features (latest check)", """SELECT count(*) AS value FROM drift_stats
         WHERE is_drifted = 1 AND measured_at = (SELECT max(measured_at) FROM drift_stats)""", 18,
                                      steps=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),
                                 timeseries(5, "Predictions over time",
                                            """SELECT $__timeGroupAlias(prediction_time, $__interval), source AS metric, count(*) AS value
                  FROM predictions WHERE $__timeFilter(prediction_time) GROUP BY 1, 2 ORDER BY 1""",
                                            {"h": 8, "w": 12, "x": 0, "y": 4}, stacked=True, bars=True,
                                            overrides=color_overrides(
                                                {"scheduled": "blue", "webapp": "green"}),
                                            description="scheduled = Airflow prediction job; webapp = Streamlit / API users."),
                                 timeseries(6, "Predicted recovery score over time",
                                            """SELECT $__timeGroupAlias(prediction_time, $__interval), avg("Prediction") AS "Average",
                  min("Prediction") AS "Min", max("Prediction") AS "Max" FROM predictions
                  WHERE $__timeFilter(prediction_time) GROUP BY 1 ORDER BY 1""",
                                            {"h": 8, "w": 12, "x": 12, "y": 4},
                                            overrides=color_overrides(
                                                {"Average": "blue", "Min": "light-blue", "Max": "dark-blue"}),
                                            description="A sudden change in the average prediction is an early sign of a model or data issue."),
                                 {"id": 7, "type": "barchart", "title": "Distribution of predictions", "datasource": DS,
                                  "description": "Predicted recovery scores in the selected time range, grouped in buckets of 10.",
                                  "gridPos": {"h": 8, "w": 8, "x": 0, "y": 12},
                                     "targets": target("""SELECT lpad((LEAST(floor("Prediction" / 10), 9) * 10)::int::text, 3, ' ')
                          || '–' || ((LEAST(floor("Prediction" / 10), 9) + 1) * 10)::int AS "Score",
                          count(*) AS "Predictions" FROM predictions WHERE $__timeFilter(prediction_time)
                          GROUP BY 1 ORDER BY 1""", "table"),
                                     "fieldConfig": {"defaults": {"color": {"mode": "fixed", "fixedColor": "blue"}}, "overrides": []},
                                     "options": {"xField": "Score", "orientation": "vertical", "showValue": "auto",
                                                 "legend": {"showLegend": False}}},
                                 timeseries(8, "Numeric feature drift (PSI, training vs serving)",
                                            """SELECT measured_at AS time, feature_name AS metric, metric_value AS value FROM drift_stats
                  WHERE $__timeFilter(measured_at) AND metric_name IN ('psi', 'psi_numeric') ORDER BY 1""",
                                            {"h": 8, "w": 8, "x": 8, "y": 12}, threshold=0.2,
                                            description="Population Stability Index between the champion's training data and recent "
                                            "serving inputs. Above 0.2 = significant drift."),
                                 timeseries(9, "Categorical feature drift (PSI, training vs serving)",
                                            """SELECT measured_at AS time, feature_name AS metric, metric_value AS value FROM drift_stats
                  WHERE $__timeFilter(measured_at) AND metric_name = 'psi_categorical' ORDER BY 1""",
                                            {"h": 8, "w": 8, "x": 16, "y": 12}, threshold=0.2,
                                            description="Same PSI test for Gender, Sport_Type, Training_Type and Stress_Level."),
                                 table(10, "Training vs serving — numeric features",
                                       f"""WITH t AS (SELECT DISTINCT ON (feature_name) feature_name, mean_value, std_value
                         FROM training_stats WHERE feature_type = 'numeric' AND model_version = {TRAINING_VERSION}
                         ORDER BY feature_name, training_time DESC),
                  s AS (SELECT t.feature_name, avg(NULLIF(p.input_features ->> t.feature_name, '')::float) AS m
                        FROM t CROSS JOIN predictions p WHERE $__timeFilter(p.prediction_time)
                        GROUP BY t.feature_name)
              SELECT t.feature_name AS "Feature", round(t.mean_value::numeric, 2) AS "Training mean",
                     round(s.m::numeric, 2) AS "Serving mean",
                     round((100 * (s.m - t.mean_value) / NULLIF(t.mean_value, 0))::numeric, 1) AS "Shift %"
              FROM t JOIN s USING (feature_name) ORDER BY abs((s.m - t.mean_value) / NULLIF(t.mean_value, 0)) DESC""",
                                       {"h": 9, "w": 12, "x": 0, "y": 20},
                                       overrides=[{"matcher": {"id": "byName", "options": "Shift %"},
                                                   "properties": [{"id": "custom.cellOptions", "value": {"type": "color-text"}},
                                                                  {"id": "thresholds", "value": {"mode": "absolute", "steps": [
                                                                    {"color": "green", "value": None}, {
                                                                        "color": "orange", "value": 10},
                                                                    {"color": "red", "value": 25}]}}]}],
                                       description="Mean of each feature in the champion's training data vs. in served predictions."),
                                 table(11, "Training vs serving — categories",
                                       f"""WITH t AS (SELECT DISTINCT ON (feature_name) feature_name, distribution_json FROM training_stats
                         WHERE feature_type = 'categorical' AND model_version = {TRAINING_VERSION}
                         ORDER BY feature_name, training_time DESC),
                  tc AS (SELECT t.feature_name, d.key AS category, d.value::float AS share
                         FROM t, json_each_text(t.distribution_json) d),
                  s AS (SELECT tc.feature_name, tc.category,
                               avg(CASE WHEN p.input_features ->> tc.feature_name = tc.category THEN 1.0 ELSE 0 END) AS share
                        FROM tc CROSS JOIN predictions p WHERE $__timeFilter(p.prediction_time)
                        GROUP BY 1, 2)
              SELECT tc.feature_name AS "Feature", tc.category AS "Category",
                     round((100 * tc.share)::numeric, 1) AS "Training %", round((100 * s.share)::numeric, 1) AS "Serving %",
                     round((100 * (s.share - tc.share))::numeric, 1) AS "Difference (pts)"
              FROM tc JOIN s USING (feature_name, category) ORDER BY 1, 2""",
                                       {"h": 9, "w": 12, "x": 12, "y": 20},
                                       description="Share of each category in training data vs. in served predictions."),
                                 ], time_from="now-24h")


def main():
    OUT.mkdir(exist_ok=True)
    # The "Model in production" stat shows text: reduce over string fields too.
    model_monitoring["panels"][1]["options"]["reduceOptions"]["fields"] = "/^value$/"
    for name, board in (("athlete-data-quality.json", data_quality),
                        ("athlete-model-monitoring.json", model_monitoring)):
        (OUT / name).write_text(json.dumps(board, indent=2, ensure_ascii=False) + "\n")
        print(f"{name}: {len(board['panels'])} panels")


if __name__ == "__main__":
    main()
