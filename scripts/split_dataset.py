from pathlib import Path
import pandas as pd

# ==========================================
# INPUT FILE
# ==========================================

input_file = Path("data/corrupted/athlete_recovery_corrupted.csv")

if not input_file.exists():
    raise FileNotFoundError(f"{input_file} not found!")

print(f"Reading: {input_file}")

df = pd.read_csv(input_file)

print(f"Total Rows: {len(df)}")

# ==========================================
# OUTPUT FOLDER
# ==========================================

output_folder = Path("data/raw_data")
output_folder.mkdir(parents=True, exist_ok=True)

# Remove old batch files
for file in output_folder.glob("batch_*.csv"):
    file.unlink()

# ==========================================
# SPLIT INTO 10 ROW FILES
# ==========================================

batch_size = 10

batch_number = 1

for start in range(0, len(df), batch_size):

    end = start + batch_size

    batch = df.iloc[start:end]

    filename = output_folder / f"batch_{batch_number:03d}.csv"

    batch.to_csv(filename, index=False)

    print(f"Created {filename.name} ({len(batch)} rows)")

    batch_number += 1

print("\n===================================")
print(f"Total Batch Files : {batch_number-1}")
print("===================================")