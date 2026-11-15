"""Single entry point of the ETL: ``python scripts/run_pipeline.py``."""

import sys
from pathlib import Path

# Prefer the sibling source tree so a copy of the repository uses its own code.
SRC_DIR = Path(__file__).resolve().parents[1] / "packages" / "etl" / "src"


def main():
    sys.path.insert(0, str(SRC_DIR))
    from ecbd_etl.pipeline import run

    return run()


if __name__ == "__main__":
    sys.exit(main())
