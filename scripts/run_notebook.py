"""Notebook launcher: ``python scripts/run_notebook.py``.

Executes the notebook in place, regenerates its ``.py`` script twin as the
last write step and then runs the read-only final checks (ASCII, twin,
exports and SVG text).
"""

import argparse
import ast
import csv
import difflib
import gzip
import json
import re
import struct
import subprocess
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTEBOOK = ROOT / "apps" / "notebooks" / "final_visualizations.ipynb"
DATA_FILE = Path("data") / "processed" / "analytics_flat.csv.gz"
NAME_COLUMNS = ("state_name", "region", "customer_city", "seller_city", "category_pt")
MAX_BYTES = 52_428_800
PNG_DPI = 300
INCH_PER_METER = 0.0254
MINUS_SIGN = chr(0x2212)
ALLOW_MISSING_WARNING = (
    "WARNING: --allow-missing is set: missing Def-1 exports are reported as warnings, "
    "not errors. Do not use it for the final verification."
)

# --- Def-1 closed export list (duplicated on purpose from the notebook) ---
STATIC_FIGURES = [
    "01a_amounts_gmv_by_macro_category",
    "01b_amounts_late_rate_by_state",
    "02_hist_price_log",
    "03_kde_delivery_by_region",
    "04_box_review_by_delay_ci",
    "04b_violin_freight_ratio",
    "05_ci_band_weekly_ticket",
    "06_errorbars_late_rate_region",
    "07a_corr_heatmap_pearson",
    "07b_corr_heatmap_spearman",
    "08s_scatter_distance_freight",
    "09s_bubble_category_delay_review",
    "14_geo_rank_states",
    "15a_polar_orders_by_hour",
    "15b_polar_orders_by_weekday",
]
HTML_FILES = [
    "08_scatter_distance_freight",
    "09_bubble_category_delay_review",
    "10_treemap_gmv",
    "11_choropleth_orders_per_100k",
    "12_choropleth_delay",
    "13_density_customers",
    "15_polar_hour",
]


def print_banner(title):
    """Print a section banner."""
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}", flush=True)


def execute_command(python, notebook):
    """Return the nbconvert command that executes the notebook in place."""
    return [
        python, "-m", "nbconvert", "--to", "notebook", "--execute", "--inplace",
        "--ExecutePreprocessor.timeout=-1", str(notebook),
    ]


def script_command(python, notebook):
    """Return the nbconvert command that writes the script twin next to the notebook."""
    return [
        python, "-m", "nbconvert", "--to", "script",
        "--TemplateExporter.exclude_input_prompt=True", str(notebook),
    ]


def clean_twin(text):
    """Drop the nbconvert shebang and coding lines and the leading blank lines."""
    lines = text.replace("\r\n", "\n").split("\n")
    header = {"#!/usr/bin/env python", "# coding: utf-8"}
    while lines and (lines[0] in header or not lines[0].strip()):
        lines.pop(0)
    return "\n".join(lines)


def parse_args(argv):
    """Parse the command-line options."""
    parser = argparse.ArgumentParser(description="Execute the notebook and run the final checks.")
    parser.add_argument(
        "--notebook", default=str(DEFAULT_NOTEBOOK),
        help="notebook to execute (default: apps/notebooks/final_visualizations.ipynb)",
    )
    parser.add_argument(
        "--check-only", action="store_true",
        help="only run the final checks, without executing or regenerating the twin",
    )
    parser.add_argument(
        "--allow-missing", action="store_true",
        help="report missing Def-1 exports as warnings (incremental work only)",
    )
    return parser.parse_args(argv)


# --- ASCII check (RF-61, RF-68) ---
def char_label(char):
    """Return an ASCII label such as 'U+2264 LESS-THAN OR EQUAL TO'."""
    return f"U+{ord(char):04X} {unicodedata.name(char, 'UNKNOWN')}"


def non_ascii(text):
    """Return (line, column, label) for every character outside printable ASCII."""
    found = []
    for line_no, line in enumerate(text.split("\n"), start=1):
        for col_no, char in enumerate(line, start=1):
            if not (0x20 <= ord(char) <= 0x7E or char in "\r\t"):
                found.append((line_no, col_no, char_label(char)))
    return found


def read_cells(path):
    """Return the cells of a notebook file."""
    return json.loads(path.read_text(encoding="utf-8")).get("cells", [])


def cell_source(cell):
    """Return the source of a cell as one string."""
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else source


def scan_notebook(path):
    """Return non-ASCII findings in the code and Markdown cell sources (never outputs)."""
    findings = []
    for index, cell in enumerate(read_cells(path)):
        kind = cell.get("cell_type", "?")
        for line_no, col_no, label in non_ascii(cell_source(cell)):
            findings.append(f"{path}: cell {index} ({kind}) line {line_no} col {col_no}: {label}")
    return findings


def scan_file(path):
    """Return non-ASCII findings in a whole text file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return [f"{path}: line {ln} col {col}: {label}" for ln, col, label in non_ascii(text)]


def check_ascii(root, notebook):
    """Check the notebook, its twin, ecbd_viz, the notebook README and this script for ASCII."""
    errors = []
    if notebook.is_file():
        errors += scan_notebook(notebook)
    files = [notebook.with_suffix(".py")]
    files += sorted((root / "packages" / "viz-kit").rglob("*.py"))
    files += [root / "apps" / "notebooks" / "README.md", root / "scripts" / "run_notebook.py"]
    for path in files:
        if path.is_file():
            errors += scan_file(path)
    return errors, []


# --- Twin check (RF-39) ---
def normalize(text):
    """Normalize line endings to LF."""
    return text.replace("\r\n", "\n")


def check_twin(python, notebook):
    """Compare the versioned twin with a fresh nbconvert export of the notebook."""
    twin = notebook.with_suffix(".py")
    if not twin.is_file():
        return [f"script twin not found: {twin}"], []
    with tempfile.TemporaryDirectory() as tmp:
        cmd = script_command(python, notebook)[:-1] + ["--output-dir", tmp, str(notebook)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return [f"fresh export failed (code {result.returncode}): {result.stderr.strip()}"], []
        exported = sorted(Path(tmp).glob(f"{notebook.stem}.*"))
        if not exported:
            return ["fresh export produced no file"], []
        fresh = clean_twin(exported[0].read_text(encoding="utf-8"))
    current = normalize(twin.read_text(encoding="utf-8"))
    if fresh == current:
        return [], []
    diff = difflib.unified_diff(
        current.splitlines(), fresh.splitlines(), "versioned twin", "fresh export", lineterm=""
    )
    first = list(diff)[:20]
    message = f"{twin} differs from a fresh export of {notebook.name}:\n" + "\n".join(first)
    return [message.encode("ascii", "backslashreplace").decode("ascii")], []


# --- Exports check (RF-29 to RF-33, RF-35) ---
def expected_exports():
    """Return the Def-1 static figure names and HTML names."""
    return list(STATIC_FIGURES), list(HTML_FILES)


def png_dpi(path):
    """Return the (x, y) dpi stored in the pHYs chunk of a PNG (0, 0 if absent)."""
    data = path.read_bytes()
    pos = 8
    while pos + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        if kind == b"pHYs":
            x_ppm, y_ppm, unit = struct.unpack(">IIB", data[pos + 8:pos + 17])
            if unit != 1:
                return 0, 0
            return round(x_ppm * INCH_PER_METER), round(y_ppm * INCH_PER_METER)
        if kind == b"IEND":
            break
        pos += 12 + length
    return 0, 0


def html_embeds_plotly(text):
    """Return True if the HTML embeds plotly.js and loads no plotly script from a URL."""
    external = re.search(r"<script[^>]*\bsrc\s*=\s*[\"'][^\"']*plotly", text, re.IGNORECASE)
    return "plotly.js v" in text and external is None


def exported_names(notebook):
    """Return the literal names passed to save_fig/save_html per function, plus problems."""
    names = {"save_fig": [], "save_html": []}
    problems = []
    for index, cell in enumerate(read_cells(notebook)):
        if cell.get("cell_type") != "code":
            continue
        try:
            tree = ast.parse(cell_source(cell))
        except SyntaxError as exc:
            problems.append(f"cell {index}: cannot be parsed ({exc.msg}, line {exc.lineno})")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            func_name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if func_name not in names:
                continue
            arg = node.args[1] if len(node.args) >= 2 else None
            for keyword in node.keywords:
                if keyword.arg == "name":
                    arg = keyword.value
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                names[func_name].append(arg.value)
            else:
                problems.append(
                    f"cell {index} line {node.lineno}: {func_name} name is not a string literal"
                )
    return names, problems


def check_exports(root, notebook, allow_missing):
    """Check the Def-1 closed list, the exported files, dpi, embedding and sizes."""
    errors, warnings = [], []
    static, html = expected_exports()
    png_dir = root / "outputs" / "figures" / "png"
    svg_dir = root / "outputs" / "figures" / "svg"
    html_dir = root / "outputs" / "interactive"

    names, problems = exported_names(notebook) if notebook.is_file() else ({}, [])
    errors += [f"{notebook.name}: {p}" for p in problems]
    allowed = {"save_fig": static, "save_html": html}
    other = {"save_fig": "save_html", "save_html": "save_fig"}
    for func, called in names.items():
        for name in sorted(set(called)):
            if called.count(name) > 1:
                errors.append(f"{func}('{name}') is exported {called.count(name)} times")
            if name in allowed[other[func]]:
                errors.append(f"{func}('{name}') uses a Def-1 name of {other[func]}")
            elif name not in allowed[func]:
                errors.append(f"{func}('{name}') is not in the Def-1 closed list")

    expected_files = [(png_dir / f"{n}.png", n, "save_fig") for n in static]
    expected_files += [(svg_dir / f"{n}.svg", n, "save_fig") for n in static]
    expected_files += [(html_dir / f"{n}.html", n, "save_html") for n in html]
    for path, name, func in expected_files:
        reasons = []
        if name not in names.get(func, []):
            reasons.append(f"no {func} call in the notebook")
        if not path.is_file():
            reasons.append("file not found")
        if reasons:
            message = f"missing Def-1 export {path.relative_to(root)}: {', '.join(reasons)}"
            (warnings if allow_missing else errors).append(message)
        elif path.suffix == ".png" and png_dpi(path) != (PNG_DPI, PNG_DPI):
            errors.append(f"{path.relative_to(root)}: {png_dpi(path)} dpi, expected {PNG_DPI}")
        elif path.suffix == ".html":
            if not html_embeds_plotly(path.read_text(encoding="utf-8", errors="replace")):
                errors.append(f"{path.relative_to(root)}: plotly.js is not embedded")

    expected_paths = {path for path, _, _ in expected_files}
    sized = [notebook] if notebook.is_file() else []
    for folder in (png_dir, svg_dir, html_dir):
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.is_file():
                sized.append(path)
            if path.name != ".gitkeep" and path not in expected_paths:
                warnings.append(f"extra file not in Def-1 (kept): {path.relative_to(root)}")
    for path in sized:
        if path.stat().st_size >= MAX_BYTES:
            errors.append(f"{path}: {path.stat().st_size} B >= {MAX_BYTES} B")
    return errors, warnings


# --- SVG text check (RF-69) ---
def svg_texts(path):
    """Return the text of every text element of an SVG."""
    texts = []
    for element in ET.parse(path).getroot().iter():
        if element.tag.rsplit("}", 1)[-1] == "text":
            texts.append("".join(element.itertext()))
    return texts


def allowed_names(data):
    """Return the non-ASCII proper names that come from the data."""
    names = set()
    with gzip.open(data, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            for column in NAME_COLUMNS:
                value = row.get(column) or ""
                if not value.isascii():
                    names.add(value)
    return names


def check_svg_text(root, allowed):
    """Check that every present SVG has real text that is ASCII except data names."""
    errors = []
    names = sorted(allowed, key=len, reverse=True)
    for path in sorted((root / "outputs" / "figures" / "svg").glob("*.svg")):
        label = path.relative_to(root)
        texts = svg_texts(path)
        if not texts:
            errors.append(f"{label}: no text elements (text saved as paths?)")
        for text in texts:
            if MINUS_SIGN in text:
                errors.append(f"{label}: typographic minus {char_label(MINUS_SIGN)} in text")
            rest = text.replace(MINUS_SIGN, "-")
            if rest.isascii():
                continue
            for name in names:
                rest = rest.replace(name, "")
            for char in sorted({c for c in rest if not c.isascii()}):
                errors.append(f"{label}: non-ASCII {char_label(char)} outside data names")
    return errors, []


def report(title, errors, warnings):
    """Print one check block and return True when it has no errors."""
    status = "PASS" if not errors else "FAIL"
    print_banner(f"CHECK {title}: {status}")
    for message in errors:
        print(f"ERROR: {message}")
    for message in warnings:
        print(f"WARNING: {message}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return not errors


def main(argv=None):
    """Execute the notebook, regenerate the twin and run the final checks."""
    args = parse_args(argv)
    notebook = Path(args.notebook).resolve()
    python = sys.executable
    if args.allow_missing:
        print(ALLOW_MISSING_WARNING, flush=True)
    if not notebook.is_file():
        print(f"ERROR: notebook not found: {notebook}")
        return 1

    if not args.check_only:
        print_banner(f"EXECUTE {notebook}")
        code = subprocess.run(execute_command(python, notebook)).returncode
        if code != 0:
            print("ERROR: notebook execution failed; the script twin was not regenerated")
            return code
        print_banner("REGENERATE SCRIPT TWIN")
        code = subprocess.run(script_command(python, notebook)).returncode
        if code != 0:
            print("ERROR: script twin export failed")
            return code
        twin = notebook.with_suffix(".py")
        cleaned = clean_twin(twin.read_text(encoding="utf-8"))
        twin.write_text(cleaned, encoding="utf-8", newline="\n")

    svg_dir = ROOT / "outputs" / "figures" / "svg"
    data = ROOT / DATA_FILE
    allowed = set()
    if any(svg_dir.glob("*.svg")):
        if data.is_file():
            allowed = allowed_names(data)
        else:
            print(f"WARNING: {data} not found; no data names are allowed in SVG text")

    results = {
        "check_ascii": check_ascii(ROOT, notebook),
        "check_twin": check_twin(python, notebook),
        "check_exports": check_exports(ROOT, notebook, args.allow_missing),
        "check_svg_text": check_svg_text(ROOT, allowed),
    }
    passed = {name: report(name, *found) for name, found in results.items()}

    print_banner("SUMMARY")
    for name, ok in passed.items():
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
    if args.allow_missing:
        print(ALLOW_MISSING_WARNING)
    return 0 if all(passed.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
