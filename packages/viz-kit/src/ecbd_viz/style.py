"""Matplotlib style of the project (rcParams from the design tokens)."""

import matplotlib as mpl
from cycler import cycler
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter

from ecbd_viz import palettes

GENERIC_FAMILIES = {"serif", "sans-serif", "cursive", "fantasy", "monospace"}
SVG_HASH_SALT = "ecbd-olist-insights"


def pick_font_family(families=None):
    """Return the first installed font family of the tokens, else ``"sans-serif"``."""
    installed = {font.name for font in font_manager.fontManager.ttflist}
    for name in families or palettes.FONT_FAMILIES:
        if name not in GENERIC_FAMILIES and name in installed:
            return name
    return "sans-serif"


def apply():
    """Set the project rcParams for every Matplotlib and seaborn figure."""
    sizes = palettes.FONT_SIZES
    mpl.rcParams.update(
        {
            "font.family": [pick_font_family()],
            "font.size": sizes["label"],
            "axes.titlesize": sizes["title"],
            "axes.titlelocation": "left",
            "axes.labelsize": sizes["label"],
            "xtick.labelsize": sizes["caption"],
            "ytick.labelsize": sizes["caption"],
            "legend.fontsize": sizes["caption"],
            "figure.titlesize": sizes["title"],
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": palettes.GRID,
            "axes.labelcolor": palettes.TEXT,
            "axes.titlecolor": palettes.TEXT,
            "text.color": palettes.TEXT,
            "xtick.color": palettes.TEXT,
            "ytick.color": palettes.TEXT,
            "grid.color": palettes.GRID,
            "figure.facecolor": palettes.CANVAS,
            "axes.facecolor": palettes.CANVAS,
            "savefig.facecolor": palettes.CANVAS,
            "axes.prop_cycle": cycler(color=palettes.OKABE_ITO),
            # ASCII minus, live SVG text, literal "$" (D32, D42, D44)
            "axes.unicode_minus": False,
            "svg.fonttype": "none",
            "svg.hashsalt": SVG_HASH_SALT,
            "text.parse_math": False,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
        }
    )


def brl_formatter(decimals=0):
    """Return a tick formatter like "R$ 1,234" with ASCII separators."""
    return FuncFormatter(lambda x, _pos: f"R$ {x:,.{decimals}f}")
