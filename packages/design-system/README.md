# Design system — `packages/design-system`

Single source of the colors, fonts, sizes, radii, spacing and shadows of Phanex. If a value changes, it is changed **only** in `tokens.json` and the theme is regenerated.

## Contents

| File | What it is |
|---|---|
| `tokens.json` | Design tokens (copied as is): interface colors (`color.ui`), data palettes (`color.data`: qualitative Okabe-Ito, sequential Viridis, diverging RdBu, highlight and muted gray), fonts, sizes, weights, radii, spacing and shadows. |
| `scripts/build_themes.py` | Power BI theme generator. It reads `tokens.json`, builds the theme, validates it against an allow-list of keys from the official theme schema (Report Theme JSON Schema 2.159) and writes it. It only uses the Python standard library. |

The generated theme is saved to `apps/bi-dashboard/theme/ecbd-theme.json`. **It is not edited by hand**: any change is made in `tokens.json` (or in the generator's mapping) and the theme is regenerated.

## How to regenerate the theme

From the repository root:

```powershell
python scripts/build_themes.py
```

The command ends with exit code 0 and writes `apps/bi-dashboard/theme/ecbd-theme.json`. The output is deterministic: two runs with the same tokens give an identical file (UTF-8 without BOM, LF line endings, keys in a fixed order).

Options (useful for testing):

```powershell
python scripts/build_themes.py --tokens <path/to/tokens.json> --output <path/to/theme.json>
```

If `tokens.json` is missing, is not valid JSON or lacks a token, the generator ends with exit code 1 and a message that names the file (or the token).

## What the theme contains

- `name`: "ECBD Olist Insights".
- `dataColors`: the 8 Okabe-Ito colors in token order.
- `good` / `neutral` / `bad`: ends and center of RdBu (`#2166AC`, `#F7F7F7`, `#B2182B`).
- `minimum` / `center` / `maximum`: Viridis (`#440154`, `#21918C`, `#FDE725`); `null`: `#BFBFBF`.
- Foreground and backgrounds: `ink`, `slate`, `steel`, `canvas`, `surface`, `hairline`; `tableAccent`: `accent`.
- `textClasses`: `callout` 32 pt, `title` 14 pt, `header` 12 pt (Segoe UI Semibold) and `label` 10 pt (Segoe UI). These sizes come from the tokens and take precedence over any other size suggestion.
- `visualStyles`: `hairline` border with radius 12, no shadow and left-aligned title on every visual; page background `surface`.

## How to import it into Power BI

*View → Themes → Browse for themes* → `apps/bi-dashboard/theme/ecbd-theme.json`. If Power BI rejects a `visualStyles` property, it is removed from the generator (not from the JSON by hand), the theme is regenerated, the property is applied by hand in the visual's format pane and this is documented in the dashboard README.

The Matplotlib style is applied in memory by `ecbd_viz.style`; this package does not emit an `ecbd.mplstyle` file.
