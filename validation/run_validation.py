"""Validate a CSV file with the project's Great Expectations checkpoints and update Data Docs.

Usage: python validation/run_validation.py [path/to/file.csv]
       (default: data/clean/athlete_recovery_synthetic.csv)
Exit code 0 when every row passes, 2 otherwise.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gx_validation import run_validation  # noqa: E402


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / \
                "data" / "clean" / "athlete_recovery_synthetic.csv"
    result = run_validation(pd.read_csv(path))
    print("=" * 60)
    print(f"ATHLETE RECOVERY DATA VALIDATION — {path.name}")
    print("=" * 60)
    print(f"Expectations passed: {result['expectations_passed']}/{result['expectations_evaluated']}")
    print(f"Rows: {result['total_rows']} | invalid: {len(result['invalid_row_indices'])} "
          f"({result['invalid_percentage']}%) | criticality: {result['criticality']}")
    for category, count in result["category_counts"].items():
        print(f"  {category:<13} {count}")
    print(f"Data Docs report: {result['data_docs_path']}")
    sys.exit(0 if result["success"] else 2)


if __name__ == "__main__":
    main()
