"""Build the Power BI report theme from the design tokens.

Reads ``packages/design-system/tokens.json`` (the single source of colors, fonts and sizes)
and writes ``apps/bi-dashboard/theme/ecbd-theme.json``. Standard library only; the output
is deterministic (fixed key order, 2-space indent, UTF-8 without BOM, LF newlines).

This generator does not produce ``ecbd.mplstyle``: that file is out of scope for this spec.
"""

import argparse
import json
import re
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_DIR.parents[1]
DEFAULT_TOKENS = PACKAGE_DIR / "tokens.json"
DEFAULT_OUTPUT = REPO_ROOT / "apps" / "bi-dashboard" / "theme" / "ecbd-theme.json"

THEME_NAME = "ECBD Olist Insights"

# Top-level keys emitted, in output order. Every key exists in the public Report Theme JSON
# Schema 2.159 (root object with additionalProperties = false).
ALLOWED_TOP_LEVEL_KEYS = (
    "name",
    "dataColors",
    "foreground",
    "foregroundNeutralSecondary",
    "foregroundNeutralTertiary",
    "background",
    "backgroundLight",
    "backgroundNeutral",
    "tableAccent",
    "good",
    "neutral",
    "bad",
    "maximum",
    "center",
    "minimum",
    "null",
    "textClasses",
    "visualStyles",
)

# Top-level keys whose value is a single hex color.
COLOR_KEYS = (
    "foreground",
    "foregroundNeutralSecondary",
    "foregroundNeutralTertiary",
    "background",
    "backgroundLight",
    "backgroundNeutral",
    "tableAccent",
    "good",
    "neutral",
    "bad",
    "maximum",
    "center",
    "minimum",
    "null",
)

DATA_COLOR_COUNT = 8
TEXT_CLASSES = ("callout", "title", "header", "label")
TEXT_CLASS_PROPERTIES = ("fontSize", "fontFace", "color")
MIN_FONT_SIZE = 10
MAX_FONT_SIZE = 60  # schema upper bound for textClass.fontSize
TITLE_ALIGNMENTS = ("left", "center", "right")

# visual -> style -> card -> allowed properties (checked against schema 2.159).
ALLOWED_VISUAL_STYLES = {
    "*": {
        "*": {
            "border": ("show", "color", "radius"),
            "dropShadow": ("show",),
            "title": ("alignment", "fontFamily"),
        }
    },
    "page": {
        "*": {
            "background": ("color", "transparency"),
        }
    },
}

HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class TokensError(Exception):
    """Raised when the tokens file is missing, unreadable or not valid JSON."""


def load_tokens(path: Path) -> dict:
    """Read and parse the tokens file; raise TokensError naming the path on failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise TokensError(f"tokens file not found: {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise TokensError(f"cannot read tokens file {path}: {exc}") from exc
    try:
        tokens = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TokensError(
            f"invalid JSON in tokens file {path}: {exc.msg} (line {exc.lineno}, column {exc.colno})"
        ) from exc
    if not isinstance(tokens, dict):
        raise TokensError(f"tokens file {path} must contain a JSON object at the top level")
    return tokens


def get_token(tokens: dict, *path):
    """Return the token at ``path`` (keys or list indices); raise KeyError with the dotted path."""
    node = tokens
    for step in path:
        try:
            node = node[step]
        except (KeyError, IndexError, TypeError):
            raise KeyError(".".join(str(part) for part in path)) from None
    return node


def solid(color: str) -> dict:
    """Wrap a hex color in the theme's solid fill structure."""
    return {"solid": {"color": color}}


def text_class(font_face: str, font_size, color: str) -> dict:
    """Build one textClasses entry with a fixed key order."""
    return {"fontSize": font_size, "fontFace": font_face, "color": color}


def build_powerbi_theme(tokens: dict) -> dict:
    """Map design tokens to the Power BI theme (spec Def-6, guide 8.5, decision P-1)."""
    ui = ("color", "ui")
    data = ("color", "data")
    title_font = get_token(tokens, "font", "powerbi", "title")
    body_font = get_token(tokens, "font", "powerbi", "body")
    size = ("font", "size")
    return {
        "name": THEME_NAME,
        "dataColors": list(get_token(tokens, *data, "qualitative")),
        "foreground": get_token(tokens, *ui, "ink"),
        "foregroundNeutralSecondary": get_token(tokens, *ui, "slate"),
        "foregroundNeutralTertiary": get_token(tokens, *ui, "steel"),
        "background": get_token(tokens, *ui, "canvas"),
        "backgroundLight": get_token(tokens, *ui, "surface"),
        "backgroundNeutral": get_token(tokens, *ui, "hairline"),
        "tableAccent": get_token(tokens, *ui, "accent"),
        "good": get_token(tokens, *data, "diverging-stops", "positive"),
        "neutral": get_token(tokens, *data, "diverging-stops", "center"),
        "bad": get_token(tokens, *data, "diverging-stops", "negative"),
        "maximum": get_token(tokens, *data, "sequential-stops", 4),
        "center": get_token(tokens, *data, "sequential-stops", 2),
        "minimum": get_token(tokens, *data, "sequential-stops", 0),
        "null": get_token(tokens, *data, "muted"),
        "textClasses": {
            "callout": text_class(
                title_font, get_token(tokens, *size, "kpi"), get_token(tokens, *ui, "ink")
            ),
            "title": text_class(
                title_font, get_token(tokens, *size, "title"), get_token(tokens, *ui, "ink")
            ),
            "header": text_class(
                title_font, get_token(tokens, *size, "subtitle"), get_token(tokens, *ui, "charcoal")
            ),
            "label": text_class(
                body_font, get_token(tokens, *size, "label"), get_token(tokens, *ui, "slate")
            ),
        },
        "visualStyles": {
            "*": {
                "*": {
                    "border": [
                        {
                            "show": True,
                            "color": solid(get_token(tokens, *ui, "hairline")),
                            "radius": get_token(tokens, "radius", "card"),
                        }
                    ],
                    "dropShadow": [{"show": False}],
                    "title": [{"alignment": "left", "fontFamily": title_font}],
                }
            },
            "page": {
                "*": {
                    "background": [
                        {"color": solid(get_token(tokens, *ui, "surface")), "transparency": 0}
                    ]
                }
            },
        },
    }


def _is_hex(value) -> bool:
    return isinstance(value, str) and HEX_COLOR.match(value) is not None


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_fill(value, where: str) -> list:
    """Check a {"solid": {"color": "#RRGGBB"}} fill."""
    color = value.get("solid", {}).get("color") if isinstance(value, dict) else None
    if not _is_hex(color):
        return [f"{where}: expected a solid fill with a #RRGGBB color, got {value!r}"]
    return []


def _validate_card_property(prop: str, value, where: str) -> list:
    """Type checks for the visualStyles properties this generator emits."""
    if prop == "show" and not isinstance(value, bool):
        return [f"{where}: 'show' must be a boolean"]
    if prop == "color":
        return _validate_fill(value, where)
    if prop in ("radius", "transparency") and not _is_number(value):
        return [f"{where}: '{prop}' must be a number"]
    if prop == "alignment" and value not in TITLE_ALIGNMENTS:
        return [f"{where}: 'alignment' must be one of {', '.join(TITLE_ALIGNMENTS)}"]
    if prop == "fontFamily" and not (isinstance(value, str) and value):
        return [f"{where}: 'fontFamily' must be a non-empty string"]
    return []


def _validate_visual_styles(visual_styles) -> list:
    if not isinstance(visual_styles, dict):
        return ["visualStyles: must be an object"]
    problems = []
    for visual, styles in visual_styles.items():
        allowed_styles = ALLOWED_VISUAL_STYLES.get(visual)
        if allowed_styles is None:
            problems.append(f"visualStyles: visual '{visual}' is not in the allow list")
            continue
        for style, cards in styles.items():
            allowed_cards = allowed_styles.get(style)
            if allowed_cards is None:
                problems.append(f"visualStyles.{visual}: style '{style}' is not in the allow list")
                continue
            for card, entries in cards.items():
                where = f"visualStyles.{visual}.{style}.{card}"
                allowed_props = allowed_cards.get(card)
                if allowed_props is None:
                    problems.append(f"{where}: card is not in the allow list")
                    continue
                if not isinstance(entries, list) or not entries:
                    problems.append(f"{where}: must be a non-empty list of objects")
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        problems.append(f"{where}: entries must be objects")
                        continue
                    for prop, value in entry.items():
                        if prop not in allowed_props:
                            problems.append(f"{where}: property '{prop}' is not in the allow list")
                        else:
                            problems.extend(_validate_card_property(prop, value, where))
    return problems


def validate_theme(theme: dict) -> list:
    """Return the structural problems of ``theme`` against the allow list (empty = valid)."""
    problems = []
    for key in theme:
        if key not in ALLOWED_TOP_LEVEL_KEYS:
            problems.append(f"top-level key '{key}' is not in the allow list")
    for key in ALLOWED_TOP_LEVEL_KEYS:
        if key not in theme:
            problems.append(f"top-level key '{key}' is missing")

    if not (isinstance(theme.get("name"), str) and theme.get("name")):
        problems.append("name: must be a non-empty string")

    data_colors = theme.get("dataColors")
    if not isinstance(data_colors, list) or len(data_colors) != DATA_COLOR_COUNT:
        problems.append(f"dataColors: expected {DATA_COLOR_COUNT} colors")
    else:
        for index, color in enumerate(data_colors):
            if not _is_hex(color):
                problems.append(f"dataColors[{index}]: {color!r} is not a #RRGGBB color")

    for key in COLOR_KEYS:
        if key in theme and not _is_hex(theme[key]):
            problems.append(f"{key}: {theme[key]!r} is not a #RRGGBB color")

    text_classes = theme.get("textClasses")
    if not isinstance(text_classes, dict) or set(text_classes) != set(TEXT_CLASSES):
        problems.append(f"textClasses: expected exactly {', '.join(TEXT_CLASSES)}")
    else:
        for name, entry in text_classes.items():
            where = f"textClasses.{name}"
            if not isinstance(entry, dict) or set(entry) != set(TEXT_CLASS_PROPERTIES):
                problems.append(f"{where}: expected exactly {', '.join(TEXT_CLASS_PROPERTIES)}")
                continue
            font_size = entry["fontSize"]
            if not _is_number(font_size) or not MIN_FONT_SIZE <= font_size <= MAX_FONT_SIZE:
                problems.append(
                    f"{where}.fontSize: must be a number from {MIN_FONT_SIZE} to {MAX_FONT_SIZE}"
                )
            if not (isinstance(entry["fontFace"], str) and entry["fontFace"]):
                problems.append(f"{where}.fontFace: must be a non-empty string")
            if not _is_hex(entry["color"]):
                problems.append(f"{where}.color: {entry['color']!r} is not a #RRGGBB color")

    if "visualStyles" in theme:
        problems.extend(_validate_visual_styles(theme["visualStyles"]))
    return problems


def render_json(theme: dict) -> str:
    """Serialize the theme deterministically (insertion order, 2-space indent, final LF)."""
    return json.dumps(theme, indent=2, ensure_ascii=False) + "\n"


def write_theme(text: str, path: Path) -> None:
    """Write the theme as UTF-8 without BOM and with LF newlines, creating parent folders."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Build the Power BI theme from tokens.json.")
    parser.add_argument(
        "--tokens", type=Path, default=DEFAULT_TOKENS, help="path to tokens.json"
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="path of the theme JSON to write"
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    """Command-line entry point; returns the process exit code."""
    args = parse_args(argv)
    try:
        tokens = load_tokens(args.tokens)
    except TokensError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    try:
        theme = build_powerbi_theme(tokens)
    except KeyError as exc:
        print(f"ERROR: missing token '{exc.args[0]}' in {args.tokens}", file=sys.stderr)
        return 1
    problems = validate_theme(theme)
    if problems:
        for problem in problems:
            print(f"ERROR: {problem}", file=sys.stderr)
        return 1
    try:
        write_theme(render_json(theme), args.output)
    except OSError as exc:
        print(f"ERROR: cannot write theme to {args.output}: {exc}", file=sys.stderr)
        return 1
    print(f"Theme written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
