import pandas as pd
from pathlib import Path

file = list(Path("data/clean").glob("*.csv"))[0]

df = pd.read_csv(file)

print("\nColumns:\n")
for i, col in enumerate(df.columns, start=1):
    print(f"{i}. {col}")