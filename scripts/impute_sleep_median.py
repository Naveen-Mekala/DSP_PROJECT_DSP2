"""Median imputation of missing Sleep_Duration_Hours in the clean dataset.

Source of truth: backups/data_before_imputation/athlete_recovery_synthetic.csv
Only Sleep_Duration_Hours is modified. Training_Intensity (1 null) is left as-is.
The corrupted dataset is not touched.
"""
import pandas as pd

SRC = "backups/data_before_imputation/athlete_recovery_synthetic.csv"
DST = "data/clean/athlete_recovery_synthetic.csv"
COL = "Sleep_Duration_Hours"

orig = pd.read_csv(SRC)
df = orig.copy()
median = df[COL].median()
n_missing = int(df[COL].isna().sum())
df[COL] = df[COL].fillna(median)
df.to_csv(DST, index=False)

# Verification
new = pd.read_csv(DST)
others = [c for c in orig.columns if c != COL]
assert new.shape == orig.shape, "shape changed"
assert new[others].equals(orig[others]), "other columns changed"
mask = orig[COL].notna()
assert (new.loc[mask, COL] == orig.loc[mask, COL]).all(), "existing sleep values changed"
assert (new.loc[~mask, COL] == median).all(), "imputed values wrong"
assert new[COL].isna().sum() == 0, "nulls remain"
print(f"Imputed {n_missing} values in {COL} with median {median}")
print("Shape:", new.shape, "| other 18 columns identical | existing values unchanged")
print("Remaining nulls:", new.isna().sum()[new.isna().sum() > 0].to_dict())
