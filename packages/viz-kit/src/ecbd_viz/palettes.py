"""Color and font constants read from ``packages/design-system/tokens.json``."""

import json
from functools import lru_cache
from pathlib import Path

import matplotlib
from matplotlib.colors import to_hex

# ecbd_viz -> src -> viz-kit -> packages (editable install)
TOKENS_PATH = Path(__file__).resolve().parents[3] / "design-system" / "tokens.json"
CSS_ONLY_FAMILIES = {"system-ui"}


@lru_cache(maxsize=None)
def load_tokens(path=TOKENS_PATH):
    """Return the design tokens as a dict (cached per path)."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Design tokens not found: {path}. "
            "Run pip install -r requirements.txt from the repo root."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def parse_families(spec):
    """Return the font family list of a CSS font stack, without quotes or CSS-only names."""
    names = [name.strip().strip("'\"") for name in spec.split(",")]
    return [name for name in names if name and name not in CSS_ONLY_FAMILIES]


# --- Constants derived from the tokens (no color literals here, RF-43) ---
_TOKENS = load_tokens()
_DATA = _TOKENS["color"]["data"]
_UI = _TOKENS["color"]["ui"]

OKABE_ITO = list(_DATA["qualitative"])
SEQUENTIAL = _DATA["sequential"]
DIVERGING = _DATA["diverging"]
DIVERGING_R = DIVERGING + "_r"
HIGHLIGHT = _DATA["highlight"]
MUTED = _DATA["muted"]

REFERENCE = _UI["charcoal"]
TEXT = _UI["ink"]
GRID = _UI["hairline"]
CANVAS = _UI["canvas"]

FONT_FAMILIES = parse_families(_TOKENS["font"]["family"])
FONT_SIZES = dict(_TOKENS["font"]["size"])


def sequential_colors(n):
    """Return ``n`` hex colors sampled evenly from the sequential colormap."""
    if n < 1:
        raise ValueError("n must be at least 1")
    cmap = matplotlib.colormaps[SEQUENTIAL].resampled(n)
    return [to_hex(cmap(i)) for i in range(n)]


def qualitative(n):
    """Return the first ``n`` Okabe-Ito colors (at most 8)."""
    if not 1 <= n <= len(OKABE_ITO):
        raise ValueError(f"n must be between 1 and {len(OKABE_ITO)}")
    return OKABE_ITO[:n]


def accent_colors(n_bars, n_accent=3):
    """Return HIGHLIGHT for the first ``n_accent`` ranked bars and MUTED for the rest."""
    n_top = min(n_accent, n_bars)
    return [HIGHLIGHT] * n_top + [MUTED] * (n_bars - n_top)
