"""Pipeline orchestrator: extract -> clean -> enrich -> model -> validate -> load (RF-16).

The pipeline is split in three functions (plan D-4):

- ``run_stages`` runs extract to model and returns the 9 model tables together with the
  number of order-item lines read by extract (needed by ``fact_rows_preserved``);
- ``validate_and_load`` evaluates every validate rule and, only when all pass, loads the
  10 output files and deletes a previous failure log; it returns the exit code;
- ``run`` composes both for the single command and is the single exit point: any
  ``ETLError`` is caught here, reported, and turned into exit code 1.

A failure before validate (RF-19, RF-27) writes nothing to ``data/interim/`` or
``data/processed/``. A validate failure writes only the failure log to ``data/interim/``
and never calls load (RF-62).
"""

import sys
import time

from ecbd_etl import clean, config, enrich, extract, load, model, quality
from ecbd_etl.quality import ETLError, InputError, QualityLog

# Transformation stages after extract: (tables, log) -> tables, in config.STAGES order.
TRANSFORM_RUNNERS = {
    "clean": clean.run,
    "enrich": enrich.run,
    "model": model.run,
}


def print_banner():
    """Print the pipeline banner and the repository root."""
    line = "=" * 72
    print(line)
    print(config.PROJECT_NAME)
    print(f"Repository root: {config.ROOT}")
    print(f"Seed: {config.SEED}")
    print(line)


def print_stage(stage):
    """Print the banner of one stage with its position in config.STAGES."""
    index = config.STAGES.index(stage) + 1
    print(f"\n[{index}/{len(config.STAGES)}] Stage: {stage}")


def print_counts(tables):
    """Print the row count of each table."""
    for name, df in tables.items():
        print(f"  {name}: {len(df):,} rows")


def run_stages(log):
    """Run extract to model; return ``(model_tables, n_source_item_lines)``."""
    print_stage("extract")
    tables = extract.run(log)
    print_counts(tables)
    # Order-item lines as read from the source, before any cleaning (fact_rows_preserved).
    n_source_item_lines = len(tables["items"])
    for stage, runner in TRANSFORM_RUNNERS.items():
        print_stage(stage)
        tables = runner(tables, log)
        print_counts(tables)
    return tables, n_source_item_lines


def validate_and_load(tables, log, n_source_item_lines):
    """Validate every rule; load only if all pass. Return the exit code (0 = success)."""
    print_stage("validate")
    violated = quality.evaluate_rules(tables, log, n_source_item_lines)
    for rule in log.stage_rules("validate"):
        print(f"  {rule}: {log.count(rule):,} rows affected")
    if violated:
        path = quality.write_failed_log(log)
        print("\nVALIDATION FAILED", file=sys.stderr)
        print(f"{len(violated)} validate rule(s) violated: {', '.join(violated)}", file=sys.stderr)
        print(
            f"Failure log written to {extract.display_path(path)}; "
            "load was not run and data/processed/ was not touched.",
            file=sys.stderr,
        )
        return 1

    print_stage("load")
    for path, n_rows in load.write_all(tables, log):
        print(f"  {extract.display_path(path)}: {n_rows:,} rows")
    quality.clear_failed_log()
    return 0


def _report_error(exc):
    """Print a controlled failure to stderr."""
    print("\nPIPELINE FAILED", file=sys.stderr)
    if isinstance(exc, InputError):
        print(f"{len(exc.problems)} input problem(s):", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            f"\nExpected locations: {extract.display_path(config.RAW_OLIST_DIR)}/ (Olist CSV), "
            f"{extract.display_path(config.RAW_EXTERNAL_DIR)}/ (IBGE, commercial calendar), "
            f"{extract.display_path(config.REFERENCE_DIR)}/ (category map).",
            file=sys.stderr,
        )
        print("Nothing was written to data/interim/ or data/processed/.", file=sys.stderr)
    else:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)


def run():
    """Run the full pipeline and return the exit code (0 = success)."""
    started = time.perf_counter()
    print_banner()
    log = QualityLog()
    try:
        tables, n_source_item_lines = run_stages(log)
        exit_code = validate_and_load(tables, log, n_source_item_lines)
    except ETLError as exc:
        _report_error(exc)
        return 1
    status = "Done" if exit_code == 0 else "Stopped"
    print(f"\n{status} in {time.perf_counter() - started:.1f} s")
    return exit_code
