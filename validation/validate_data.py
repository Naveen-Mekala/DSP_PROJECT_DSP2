import great_expectations as gx

print("=" * 50)
print("Great Expectations Version")
print("=" * 50)

print(gx.__version__)

print("\nCreating GX Context...")

context = gx.get_context()

print("Context created successfully!")

print(type(context))