"""Entry point of the theme generator: ``python scripts/build_themes.py``.

Thin launcher: loads ``packages/design-system/scripts/build_themes.py`` by path (the folder
name ``design-system`` is not importable) and exits with its return code.
"""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "packages" / "design-system" / "scripts" / "build_themes.py"


def load_generator():
    """Load the generator module from its file path."""
    spec = importlib.util.spec_from_file_location("ecbd_build_themes", GENERATOR)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load theme generator from {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None):
    return load_generator().main(argv)


if __name__ == "__main__":
    sys.exit(main())
