"""Exporters for static figures (PNG + SVG) and interactive HTML; they never delete files."""

from pathlib import Path

PNG_DPI = 300

# Redraw once the page is laid out: a late scrollbar can leave map canvases blank
RESIZE_SCRIPT = (
    "window.addEventListener('load', function () {"
    " setTimeout(function () {"
    " Plotly.Plots.resize(document.getElementById('{plot_id}'));"
    " }, 300); });"
)


def save_fig(fig, name, out_dir):
    """Save a Matplotlib figure as ``png/<name>.png`` and ``svg/<name>.svg``; return both paths."""
    out_dir = Path(out_dir)
    png_path = out_dir / "png" / f"{name}.png"
    svg_path = out_dir / "svg" / f"{name}.svg"
    png_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=PNG_DPI, bbox_inches="tight")
    # No date in the SVG so repeated runs give the same bytes (RF-36)
    fig.savefig(svg_path, bbox_inches="tight", metadata={"Date": None})
    return png_path, svg_path


def save_html(fig, name, out_dir):
    """Save a Plotly figure as a self-contained ``<name>.html`` with plotly.js embedded."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{name}.html"
    fig.write_html(
        html_path, include_plotlyjs=True, full_html=True,
        config={"responsive": True}, post_script=RESIZE_SCRIPT,
    )
    return html_path
