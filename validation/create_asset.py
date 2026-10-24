import great_expectations as gx

print("=" * 60)
print("Creating Data Asset")
print("=" * 60)

# Load context
context = gx.get_context(project_root_dir="gx")

# Get datasource
datasource = context.data_sources.get("athlete_datasource")

# Add CSV asset
asset = datasource.add_csv_asset(
    name="athlete_dataset",
    filepath_or_buffer="data/corrupted/athlete_recovery_corrupted.csv"
)

print("\nData Asset Created Successfully!")
print(asset)