"""Create the 5 defense demo files in data/demo (copy them into data/raw_data during the demo).

  demo_1_all_errors.csv  every row has at least one problem            -> 100% bad, High
  demo_2_clean.csv       no problems                                    -> 100% good
  demo_3_clean.csv       no problems                                    -> 100% good
  demo_4_clean.csv       no problems                                    -> 100% good
  demo_5_mixed.csv       one row per error category + clean rows        -> split good/bad, Medium
  demo_6_missing_column.csv (bonus) schema error: Mood_Score column missing -> whole file bad

Usage: python scripts/create_demo_files.py [--source data/clean/athlete_recovery_synthetic.csv]
"""
import argparse
from pathlib import Path

import pandas as pd

OUT = Path("data/demo")


def clean_rows(df, start, n=10):
    return df.dropna().iloc[start:start + n].reset_index(drop=True)


def build(df):
    files = {}
    bad = clean_rows(df, 0).astype(object)
    errors = [("Age", None), ("Age", 200), ("Gender", "Alien"), ("HRV_ms", "seventy"),
              ("Stress_Level", "Extreme"), ("Recovery_Score", 150), ("Sleep_Duration_Hours", -1),
              ("Resting_Heart_Rate", 300), ("Training_Type", "Napping"), ("Mood_Score", None)]
    for i, (col, value) in enumerate(errors):
        bad.at[i, col] = value
    files["demo_1_all_errors.csv"] = bad
    for n, start in ((2, 100), (3, 200), (4, 300)):
        files[f"demo_{n}_clean.csv"] = clean_rows(df, start)
    mixed = clean_rows(df, 400, n=20).astype(object)
    mixed.at[1, "Sleep_Duration_Hours"] = None          # completeness
    mixed.at[3, "Age"] = -3                             # validity (range)
    mixed.at[5, "Gender"] = "M"                         # validity (category)
    mixed.at[7, "Energy_Level"] = "high"                # type
    mixed = pd.concat([mixed, mixed.iloc[[8]]], ignore_index=True)   # consistency (duplicate)
    files["demo_5_mixed.csv"] = mixed
    files["demo_6_missing_column.csv"] = clean_rows(df, 500).drop(columns=["Mood_Score"])
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="data/clean/athlete_recovery_synthetic.csv")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, frame in build(pd.read_csv(args.source)).items():
        frame.to_csv(OUT / name, index=False)
        print(f"{name:<28} {len(frame):>3} rows")


if __name__ == "__main__":
    main()
