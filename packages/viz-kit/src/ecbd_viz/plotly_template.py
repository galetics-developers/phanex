"""Plotly template "ecbd" built from the design tokens."""

import plotly.graph_objects as go
import plotly.io as pio

from ecbd_viz import palettes

TEMPLATE_NAME = "ecbd"
BASE_TEMPLATE = "plotly_white"


def register_template():
    """Register the "ecbd" template and make it the Plotly default."""
    pio.templates[TEMPLATE_NAME] = go.layout.Template(
        layout={
            "colorway": palettes.OKABE_ITO,
            "font": {"family": ", ".join(palettes.FONT_FAMILIES), "color": palettes.TEXT},
            "paper_bgcolor": palettes.CANVAS,
            "plot_bgcolor": palettes.CANVAS,
            "title": {"x": 0, "xanchor": "left"},
            "colorscale": {
                "sequential": palettes.SEQUENTIAL,
                "diverging": palettes.DIVERGING,
            },
        }
    )
    pio.templates.default = f"{BASE_TEMPLATE}+{TEMPLATE_NAME}"
