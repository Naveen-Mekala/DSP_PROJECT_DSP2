"""Split a dataset into N files in raw_data, to simulate data arriving over time.

Example:
  python scripts/split_dataset.py --dataset data/corrupted/athlete_recovery_corrupted.csv \
      --raw-data data/raw_data --num-files 800 --p-missing-column 0.02
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

PROTECTED = {"Athlete_ID"}   # never dropped, so every file can still be identified


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", default="data/corrupted/athlete_recovery_corrupted.csv", help="dataset path")
    p.add_argument("--raw-data", default="data/raw_data", help="raw_data folder path")
    p.add_argument("--num-files", type=int, required=True, help="number of files to generate")
    p.add_argument("--p-missing-column", type=float, default=0.0,
                   help="probability that a file loses one required column (schema error)")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--keep-existing", action="store_true", help="do not delete existing batch_*.csv files")
    return p.parse_args(argv)


def split(df, num_files, p_missing_column=0.0, seed=None):
    """Yield (index, dataframe) chunks; some chunks lose a column with the given probability."""
    if num_files < 1:
        raise ValueError("--num-files must be at least 1")
    rng = np.random.default_rng(seed)
    droppable = [c for c in df.columns if c not in PROTECTED]
    bounds = np.linspace(0, len(df), min(num_files, len(df)) + 1).astype(int)
    for i, (start, end) in enumerate(zip(bounds[:-1], bounds[1:]), start=1):
        chunk = df.iloc[start:end]
        if p_missing_column and rng.random() < p_missing_column:
            chunk = chunk.drop(columns=[rng.choice(droppable)])
        yield i, chunk


def main(argv=None):
    args = parse_args(argv)
    df = pd.read_csv(args.dataset)
    out = Path(args.raw_data)
    out.mkdir(parents=True, exist_ok=True)
    if not args.keep_existing:
        for old in out.glob("batch_*.csv"):
            old.unlink()
    width = len(str(args.num_files))
    dropped = 0
    for i, chunk in split(df, args.num_files, args.p_missing_column, args.seed):
        dropped += int(len(chunk.columns) < len(df.columns))
        chunk.to_csv(out / f"batch_{i:0{width}d}.csv", index=False)
    print(f"Split {len(df)} rows from {args.dataset} into {min(args.num_files, len(df))} files in {out}"
          f" ({dropped} with a missing column)")


if __name__ == "__main__":
    main()
