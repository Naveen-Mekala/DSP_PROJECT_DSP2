
"""Define Great Expectations for the athlete recovery dataset."""

import great_expectations as gx


def main():
    # Load the existing Great Expectations context.
    context = gx.get_context(context_root_dir="gx/gx")
    suite_name = "athlete_suite"

    # Retrieve the existing suite or create it.
    try:
        suite = context.suites.get(name=suite_name)
    except Exception:
        suite = gx.ExpectationSuite(name=suite_name)
        suite = context.suites.add(suite)

    # Clear existing expectations before rebuilding the suite.
    suite.expectations = []

    expectations = [
        # Athlete_ID must exist and cannot be missing.
        gx.expectations.ExpectColumnToExist(
            column="Athlete_ID"
        ),
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="Athlete_ID"
        ),

        # Age must be between 18 and 60.
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="Age",
            min_value=18,
            max_value=60,
        ),

        # Recovery score must be between 0 and 100.
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="Recovery_Score",
            min_value=0,
            max_value=100,
        ),

        # Gender must match an allowed category.
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="Gender",
            value_set=["Male", "Female", "Non-binary"],
        ),

        # Sleep duration must be between 0 and 24 hours.
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="Sleep_Duration_Hours",
            min_value=0,
            max_value=24,
        ),

        # Missing sleep values are checked separately.
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="Sleep_Duration_Hours"
        ),

        # Mood score must be between 1 and 10.
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="Mood_Score",
            min_value=1,
            max_value=10,
        ),

        # Training duration must be between 1 and 300 minutes.
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="Training_Duration_Min",
            min_value=1,
            max_value=300,
        ),
    ]

    # Add all expectations to the suite.
    for expectation in expectations:
        suite.add_expectation(expectation)

    # Save the updated suite.
    context.suites.add_or_update(suite)

    # Reload the suite to verify persistence.
    verified_suite = context.suites.get(name=suite_name)

    print(f"Expectation suite '{suite_name}' updated.")
    print(f"Expectations defined: {len(expectations)}")
    print(f"Expectations saved: {len(verified_suite.expectations)}")
    print("Athlete_ID uniqueness check intentionally omitted.")


if __name__ == "__main__":
    main()

