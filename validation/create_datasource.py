import great_expectations as gx

print("=" * 60)
print("Creating Data Source")
print("=" * 60)

context = gx.get_context(project_root_dir="gx")

datasource = context.data_sources.add_pandas(
    name="athlete_datasource"
)

print("\nDatasource created successfully!")
print(datasource)