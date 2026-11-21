# 05 — Design system

This document is the visual contract of the project. It states which colors, fonts and layout
rules every deliverable follows (the Power BI dashboard, the notebook figures and the executive
deck) and how each rule is checked before a change is approved. The package that holds the
values and generates the themes is described in
[`packages/design-system/README.md`](../packages/design-system/README.md); this document explains
the rules behind them and the ones that apply to the deck.

## 1. One source of values

Every color, font, size, radius and spacing step lives in
[`packages/design-system/tokens.json`](../packages/design-system/tokens.json). Nothing in the
project writes a color by hand:

| Deliverable | How it reads the tokens |
| :-- | :-- |
| Power BI dashboard | `python scripts/build_themes.py` turns the tokens into `apps/bi-dashboard/theme/ecbd-theme.json`, which the report imports |
| Notebook figures | The `ecbd_viz` package (`packages/viz-kit`) reads the tokens and applies them as the Matplotlib style and the Plotly template |
| Executive deck | The template of `apps/presentation/template/` already carries the visual language; the deck adds no color of its own |

If a value has to change, it changes in `tokens.json` and the themes are regenerated. A color
written directly in a notebook cell, in a DAX measure or in a slide is a defect.

## 2. Interface surfaces and typography

- **Surfaces:** white canvas (`#FFFFFF`) and a light neutral surface (`#F6F5F4`) for panels and
  cards. Thin hairlines (`#E5E3DF`) instead of shadows. One dark navy band (`#0A1530`) for
  headers and the deck cover, with white text on it.
- **Text:** near-black ink (`#1A1A1A`) for values, warm gray (`#787671`) for labels.
- **Accent:** a single purple accent (`#5645D4`) for the main action, never for data.
- **Fonts:** Inter where it is available, Segoe UI in Power BI (`Segoe UI Semibold` for titles,
  `Segoe UI` for body), DejaVu Sans as the Matplotlib fallback.
- **Sizes:** 32 pt for a KPI value, 14 pt for a chart title, 12 pt for a subtitle, 10 pt for
  labels, 9 pt for captions. In the deck, the template fixes the sizes and they are not changed.
- **Shape:** 12 px radius on cards, 8 px on buttons, 8 px spacing grid, 24 px page margins.

## 3. Data color rules

These rules are mandatory. They follow the course requirements and the accessibility principle of
the team.

| Kind of data | Palette | Where it is used |
| :-- | :-- | :-- |
| Ordered magnitude (more is more intense) | **Sequential Viridis** (`#440154` to `#FDE725`) | Orders per hundred thousand inhabitants, GMV by state, review score, delay band |
| Variation around a meaningful midpoint | **Diverging RdBu** (`#B2182B` negative, `#F7F7F7` center, `#2166AC` positive) | Delay against the promised date, value against a target |
| Categories without order | **Qualitative Okabe-Ito** (8 colors, starting at `#0072B2`) | Macro category, payment type, region |
| One value that matters | Highlight `#D55E00` over muted gray `#BFBFBF` | "This is the bar to look at" |

Forbidden: red against green, rainbow or jet scales, more than eight qualitative colors, and
pastel colors for data. Red against blue stays readable for the most common kinds of color
blindness; red against green does not.

## 4. Axes and scales

- **Zero baseline:** every bar chart starts at zero, with no exception. In Power BI the Y axis
  minimum is set to 0 on each visual; in Matplotlib the limit is never cropped.
- **Diverging midpoint:** a diverging scale is centered on the value that gives it meaning,
  zero for the delay, or the national average when the comparison is against that average. The
  reason is stated next to the figure.
- **Log scale** only for a magnitude that spans several orders, such as item prices, and the
  axis says so.
- **Coordinate systems:** cartesian for orthogonal data, geographic for maps, polar for cyclic
  data such as the hour of the day.

## 5. Declutter

- No top or right frame. A faint horizontal grid only when it helps to read values.
- No redundant legend: if the color is already named in the title or on the mark, the legend goes.
- Data labels only on the values that carry the message.
- At most six or seven visuals on a dashboard page; white space is part of the design.
- Conclusive titles: "A late order loses two stars", not "Review by delay".

## 6. Deck template rules

The deck uses the team template, which holds one prototype of each slide type on a
20 x 11.25 in canvas (16:9). The design of that template is not modified: a slide only receives
its text and one visual. The font of the whole deck is Poppins, at 72 pt for a section title,
30 pt for a slide title and 16 pt for body text and for the list of sources.

| Slide type | What may change | What never changes |
| :-- | :-- | :-- |
| Cover | Presentation title, the five members, the date | Group, course name, class year, shapes and colors |
| Section block | The section title | Everything else |
| Information | Slide title and body text, plus one visual on the left | Background, seal, text boxes, fonts |
| Bibliographic sources | The list of sources | The slide title |
| Closing | Nothing | Everything |

Information slide geometry:

| Zone | Position (inches) |
| :-- | :-- |
| Visual area (visible part) | left 0.30, top 1.80, width 8.30, height 7.65 |
| Slide title | left 9.44, top 0.88, width 10.66 |
| Body text | left 9.44, top 2.28, width 10.66, height 6.54 |

Content limits that keep the text inside its frame, measured on this geometry: at most 56
characters for a title (two lines at 30 pt), between 900 and 1,600 characters of body text in two
or three paragraphs, and at most four points of 110 characters each. Nothing, text or visual,
reaches the edge of the slide: the text column keeps a margin on the right and a visual is fitted
inside the visual area without changing its aspect ratio.

Visuals are the figures and screenshots the previous deliverables already produced. They are
placed as they were exported and are never redrawn or recolored, so everything on screen has
already passed the accessibility checks of its own deliverable.

## 7. How a visual change is approved

1. The change is described in the pull request, with the rule it affects.
2. The themes are regenerated from the tokens if a value changed.
3. Each affected page or figure is exported and checked in a color blindness simulator
   ([Coblis](https://www.color-blindness.com/coblis-color-blindness-simulator/)) for protanopia,
   deuteranopia and tritanopia.
4. Text contrast is checked against WCAG AA (4.5:1) for ink on surface, white on navy and white
   on accent.
5. Bar charts are reviewed one by one for the zero baseline.
6. The result is recorded in the pull request, with before and after images when the change is
   visible.

The full list of checks, with its owner and command, is in
[`07-qa-checklist.md`](07-qa-checklist.md).
