"""Run the configured athlete Great Expectations checkpoint and update Data Docs."""
import great_expectations as gx
import sys


def main():
    context = gx.get_context(context_root_dir="gx/gx")
    checkpoint = context.checkpoints.get("athlete_checkpoint")
    result = checkpoint.run()
    validation_result = next(iter(result.run_results.values()))
    stats = validation_result.statistics
    print("=" * 60)
    print("ATHLETE RECOVERY DATA VALIDATION")
    print("=" * 60)
    print(f"Total expectations: {stats.get('evaluated_expectations', 0)}")
    print(f"Passed: {stats.get('successful_expectations', 0)}")
    print(f"Failed: {stats.get('unsuccessful_expectations', 0)}")
    print(f"Success percentage: {stats.get('success_percent', 0)}%")
    for item in validation_result.results:
        if not item.success:
            config = item.expectation_config
            print(f"FAILED: {config.type} {config.kwargs}")
    docs = context.get_docs_sites_urls()
    if docs:
        print(f"Data Docs: {docs[0].get('site_url', 'Open the nginx Data Docs URL')}")
    print(f"Overall validation success: {bool(result.success)}")
    print("Validation complete.")
    if not result.success:
        sys.exit(2)


if __name__ == "__main__":
    main()
