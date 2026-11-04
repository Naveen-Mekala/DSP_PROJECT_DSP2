"""Inject data-quality errors into a clean dataset, with a configurable probability per error type.

Error types (and the data-quality category each one tests):
  missing    -> completeness : a random required value is emptied
  range      -> validity     : a numeric value outside its allowed range (e.g. Age 200, Mood -5)
  category   -> validity     : an unknown category (e.g. Gender "Alien", Stress_Level "Extreme")
  type       -> type         : text in a numeric column (e.g. HRV_ms "seventy")
  duplicate  -> consistency  : a copy of an existing (Athlete_ID, Day) record
  outlier    -> validity     : physiologically impossible value (e.g. Resting_Heart_Rate 300)
Missing columns (schema) are a file-level error: see split_dataset.py --p-missing-column.

Example:
  python scripts/generate_errors.py --input data/clean/athlete_recovery_synthetic.csv \
      --output data/corrupted/athlete_recovery_corrupted.csv --p-missing 0.03 --p-type 0.01 --seed 7
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RANGE_ERRORS = {"Age": [200, -3], "Recovery_Score": [150, -20], "Sleep_Duration_Hours": [30, -1],
                "Mood_Score": [-5, 15], "Training_Duration_Min": [-60, 900], "Training_Intensity": [12, -2]}
CATEGORY_ERRORS = {"Gender": ["Alien", "M"], "Stress_Level": ["Extreme", "5"],
                   "Sport_Type": ["Chess"], "Training_Type": ["Napping"]}
TYPE_ERRORS = {"HRV_ms": ["seventy"], "Age": ["twenty"], "Caffeine_Intake_mg": ["a lot"],
               "Energy_Level": ["high"]}
OUTLIERS = {"Resting_Heart_Rate": [300, 5], "HRV_ms": [900], "Caffeine_Intake_mg": [5000]}
NULLABLE = ["Age", "Gender", "Sleep_Duration_Hours", "Training_Intensity", "Mood_Score",
            "Stress_Level", "Energy_Level", "Recovery_Score"]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/clean/athlete_recovery_synthetic.csv")
    p.add_argument("--output", default="data/corrupted/athlete_recovery_corrupted.csv")
    p.add_argument("--p-missing", type=float, default=0.02, help="probability per row (completeness)")
    p.add_argument("--p-range", type=float, default=0.02, help="probability per row (validity)")
    p.add_argument("--p-category", type=float, default=0.01, help="probability per row (validity)")
    p.add_argument("--p-type", type=float, default=0.005, help="probability per row (type)")
    p.add_argument("--p-duplicate", type=float, default=0.003, help="probability per row (consistency)")
    p.add_argument("--p-outlier", type=float, default=0.005, help="probability per row (validity)")
    p.add_argument("--seed", type=int, default=None, help="random seed (default: different every run)")
    return p.parse_args(argv)


def inject_errors(df, p_missing=0.02, p_range=0.02, p_category=0.01, p_type=0.005,
                  p_duplicate=0.003, p_outlier=0.005, seed=None):
    """Return (corrupted_df, counts). Each row gets each error type with its own probability."""
    rng = np.random.default_rng(seed)
    out = df.copy().astype(object)          # object dtype so text can be placed in numeric columns
    counts = {}

    def rows(p):
        return np.flatnonzero(rng.random(len(out)) < p)

    def apply(name, p, choices):
        picked = rows(p)
        for i in picked:
            col = rng.choice(list(choices))
            out.iat[i, out.columns.get_loc(col)] = rng.choice(choices[col])
        counts[name] = len(picked)

    picked = rows(p_missing)
    for i in picked:
        out.iat[i, out.columns.get_loc(rng.choice(NULLABLE))] = None
    counts["missing"] = len(picked)
    apply("range", p_range, RANGE_ERRORS)
    apply("category", p_category, CATEGORY_ERRORS)
    apply("type", p_type, TYPE_ERRORS)
    apply("outlier", p_outlier, OUTLIERS)
    dup = rows(p_duplicate)
    counts["duplicate"] = len(dup)
    if len(dup):
        # Insert each copy right after its original, as duplicated submissions usually arrive together.
        order = np.concatenate([np.arange(len(out)), dup])
        position = np.concatenate([np.arange(len(out), dtype=float), dup + 0.5])
        out = out.iloc[order[np.argsort(position, kind="stable")]].reset_index(drop=True)
    return out, counts


def main(argv=None):
    args = parse_args(argv)
    df = pd.read_csv(args.input)
    corrupted, counts = inject_errors(df, args.p_missing, args.p_range, args.p_category, args.p_type,
                                      args.p_duplicate, args.p_outlier, args.seed)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    corrupted.to_csv(args.output, index=False)
    print(f"Read {len(df)} rows from {args.input}")
    for name, n in counts.items():
        print(f"  {name:<10} errors injected: {n}")
    print(f"Wrote {len(corrupted)} rows to {args.output}")


if __name__ == "__main__":
    main()
