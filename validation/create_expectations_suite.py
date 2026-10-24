import great_expectations as gx

print("=" * 60)
print("Creating Expectation Suite")
print("=" * 60)

# Load context
context = gx.get_context(project_root_dir="gx")

# Create expectation suite
suite = context.suites.add(
    gx.ExpectationSuite(
        name="athlete_suite"
    )
)

print("\nExpectation Suite Created Successfully!")
print(suite)