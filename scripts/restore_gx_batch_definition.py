import great_expectations as gx
from great_expectations.datasource.fluent.interfaces import BatchDefinition

CONTEXT_DIR = "/opt/airflow/project/gx/gx"
BATCH_ID = "4e2f6ace-416c-43d2-9bc4-7d955d0149e4"
BATCH_NAME = "athlete_batch"

context = gx.get_context(context_root_dir=CONTEXT_DIR)
datasource = context.data_sources.get("athlete_datasource")
asset = datasource.get_asset("athlete_dataset")

if type(asset).__name__ != "DataFrameAsset":
    raise RuntimeError("Expected DataFrameAsset. Aborting.")

if any(b.name == BATCH_NAME for b in asset.batch_definitions):
    raise RuntimeError("Batch already exists. Aborting.")

batch = BatchDefinition(
    id=BATCH_ID,
    name=BATCH_NAME,
)
batch.set_data_asset(asset)

# Register the batch with the asset before saving the datasource.
asset.batch_definitions.append(batch)
asset.update_batch_definition_field_set()

print("Saving batch definition...")
datasource.add_batch_definition(batch)

print("Reloading context...")
context = gx.get_context(context_root_dir=CONTEXT_DIR)
datasource = context.data_sources.get("athlete_datasource")
asset = datasource.get_asset("athlete_dataset")
restored = asset.get_batch_definition(BATCH_NAME)

assert str(restored.id) == BATCH_ID

print("\nSUCCESS")
print("Asset:", type(asset).__name__, asset.id)
print("Batch:", restored.name, restored.id)
