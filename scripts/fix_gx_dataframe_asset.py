import great_expectations as gx
from great_expectations.datasource.fluent.pandas_datasource import DataFrameAsset
from great_expectations.datasource.fluent.interfaces import BatchDefinition

CONTEXT_DIR = "/opt/airflow/project/gx/gx"

ASSET_NAME = "athlete_dataset"
ASSET_ID = "8459ece9-e153-4952-ba0a-7efd4bfe5d66"

BATCH_NAME = "athlete_batch"
BATCH_ID = "4e2f6ace-416c-43d2-9bc4-7d955d0149e4"

print("Loading Great Expectations context...")
context = gx.get_context(context_root_dir=CONTEXT_DIR)

datasource = context.data_sources.get("athlete_datasource")
old_asset = datasource.get_asset(ASSET_NAME)

if str(old_asset.id) != ASSET_ID:
    raise RuntimeError("Asset ID mismatch. Migration aborted.")

if type(old_asset).__name__ != "CSVAsset":
    raise RuntimeError("Expected CSVAsset. Migration aborted.")

print("Preparing replacement DataFrameAsset...")

new_asset = DataFrameAsset(
    name=ASSET_NAME,
    id=ASSET_ID,
)

batch_definition = BatchDefinition(
    id=BATCH_ID,
    name=BATCH_NAME,
)

new_asset.batch_definitions.append(batch_definition)

print("Replacing existing asset...")
datasource.delete_asset(name=ASSET_NAME)
datasource._add_asset(asset=new_asset)

print("Saving datasource...")
context.update_datasource(datasource)

print("Reloading context...")
context = gx.get_context(context_root_dir=CONTEXT_DIR)

datasource = context.data_sources.get("athlete_datasource")
asset = datasource.get_asset(ASSET_NAME)
batch = asset.get_batch_definition(BATCH_NAME)

assert type(asset).__name__ == "DataFrameAsset"
assert str(asset.id) == ASSET_ID
assert str(batch.id) == BATCH_ID

print("\nSUCCESS: Migration verified!")
print("Asset type:", type(asset).__name__)
print("Asset ID:", asset.id)
print("Batch:", batch.name)
print("Batch ID:", batch.id)
