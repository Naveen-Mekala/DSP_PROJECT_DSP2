import random
from pathlib import Path
import pandas as pd

# ==========================================================
# SETTINGS
# ==========================================================

random.seed(42)

# ==========================================================
# LOAD CLEAN DATASET
# ==========================================================

data_folder = Path("data/clean")
csv_files = list(data_folder.glob("*.csv"))

if not csv_files:
    raise FileNotFoundError("No CSV file found inside data/clean")

dataset_path = csv_files[0]

print(f"\nLoading dataset: {dataset_path.name}")

df = pd.read_csv(dataset_path)

# Create a copy so the original dataset remains unchanged
corrupted_df = df.copy()

print(f"Rows    : {len(corrupted_df)}")
print(f"Columns : {len(corrupted_df.columns)}")

# ==========================================================
# ERROR 1 - Missing Values
# ==========================================================

rows = random.sample(range(len(corrupted_df)), 20)

corrupted_df.loc[rows, "Age"] = None

print("✓ Missing values injected into Age")

# ==========================================================
# ERROR 2 - Invalid Range
# ==========================================================

rows = random.sample(range(len(corrupted_df)), 15)

corrupted_df.loc[rows, "Recovery_Score"] = 150

print("✓ Invalid Recovery_Score values injected")

# ==========================================================
# ERROR 3 - Invalid Category
# ==========================================================

rows = random.sample(range(len(corrupted_df)), 15)

corrupted_df.loc[rows, "Gender"] = "Alien"

print("✓ Invalid Gender values injected")

# ==========================================================
# ERROR 4 - Wrong Data Type
# (Safe for Pandas 3.x)
# ==========================================================

rows = random.sample(range(len(corrupted_df)), 10)

corrupted_df["Gender"] = corrupted_df["Gender"].astype(object)

corrupted_df.loc[rows, "Gender"] = 12345

print("✓ Wrong datatype injected into Gender")

# ==========================================================
# ERROR 5 - Duplicate Athlete_ID
# ==========================================================

duplicates = corrupted_df.sample(10, random_state=42)

corrupted_df = pd.concat(
    [corrupted_df, duplicates],
    ignore_index=True
)

print("✓ Duplicate Athlete_ID records added")

# ==========================================================
# ERROR 6 - Outlier
# ==========================================================

rows = random.sample(range(len(corrupted_df)), 15)

corrupted_df.loc[rows, "Resting_Heart_Rate"] = 300

print("✓ Resting Heart Rate outliers injected")

# ==========================================================
# ERROR 7 - Negative Training Duration
# ==========================================================

rows = random.sample(range(len(corrupted_df)), 15)

corrupted_df.loc[rows, "Training_Duration_Min"] = -60

print("✓ Negative Training Duration injected")

# ==========================================================
# ERROR 8 - Invalid Sleep Hours
# ==========================================================

rows = random.sample(range(len(corrupted_df)), 10)

corrupted_df.loc[rows, "Sleep_Duration_Hours"] = 30

print("✓ Invalid Sleep Duration injected")

# ==========================================================
# ERROR 9 - Invalid Mood Score
# ==========================================================

rows = random.sample(range(len(corrupted_df)), 10)

corrupted_df.loc[rows, "Mood_Score"] = -5

print("✓ Invalid Mood Score injected")

# ==========================================================
# SAVE CORRUPTED DATASET
# ==========================================================

output_folder = Path("data/corrupted")
output_folder.mkdir(parents=True, exist_ok=True)

output_file = output_folder / "athlete_recovery_corrupted.csv"

corrupted_df.to_csv(output_file, index=False)

print("\n=====================================")
print("Corrupted dataset created successfully!")
print(f"Saved to: {output_file}")
print("=====================================")

# ==========================================================
# SUMMARY
# ==========================================================

print("\nSummary")
print("----------------------------")
print(f"Original Rows : {len(df)}")
print(f"Corrupted Rows: {len(corrupted_df)}")
print(f"Original Cols : {len(df.columns)}")
print(f"Corrupted Cols: {len(corrupted_df.columns)}")