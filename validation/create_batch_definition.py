import great_expectations as gx

print("=" * 60)
print("Creating Batch Definition")
print("=" * 60)

# Load context
context = gx.get_context(project_root_dir="gx")

# Get datasource
datasource = context.data_sources.get("athlete_datasource")

# Get asset
asset = datasource.get_asset("athlete_dataset")

# Create batch definition
batch_definition = asset.add_batch_definition_whole_dataframe(
    name="athlete_batch"
)

print("\nBatch Definition Created Successfully!")
print(batch_definition)