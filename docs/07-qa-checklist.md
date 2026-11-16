# 07 — QA and integration checklist

This is the list the QA and Integration Lead runs before a change is merged and before the
final submission. Every row says who runs it and with which command, when there is one. A row
that cannot be run is reported as not verified; it is never reported as passed.

Tolerance used across the project: a figure shown in two deliverables may differ by at most
0.1% in relative terms.

## 1. How to use it

| Gate | When | Who |
| :-- | :-- | :-- |
| Section 2 to 6 | Before opening a pull request | The role that owns the change |
| Section 7 | On the pull request | The reviewer, from another role when possible |
| Section 8 | Before the submission date | QA and Integration Lead |

## 2. Code and environment

| # | Check | Command | Owner |
| :-- | :-- | :-- | :-- |
| 2.1 | Linter clean, 0 errors | `ruff check .` | Author |
| 2.2 | Dependencies install from a clean environment | `python -m venv .venv` then `pip install -r requirements.txt` | Author |
| 2.3 | Every new dependency is justified in writing in the pull request | — | Author |
| 2.4 | No credentials, tokens or personal data in the change | `git diff` review | Author |

## 3. Data and pipeline

| # | Check | Command | Owner |
| :-- | :-- | :-- | :-- |
| 3.1 | The pipeline runs end to end with no manual step | `python scripts/run_pipeline.py` | Data Architect |
| 3.2 | The validate stage reports unique keys and no orphans | output of 3.1 | Data Architect |
| 3.3 | `data/processed/data_quality_report.csv` is complete, including the rules with zero violations | file review | Data Architect |
| 3.4 | `data/raw/` was not edited and the loose CSV files are not versioned | `git status` | Data Architect |

## 4. Notebook

| # | Check | Command | Owner |
| :-- | :-- | :-- | :-- |
| 4.1 | Exact name `final_visualizations.ipynb` | — | Python Visualization Specialist |
| 4.2 | Restart and run all, with no error and with visible output | `python scripts/run_notebook.py` | Python Visualization Specialist |
| 4.3 | The script twin matches a fresh export of the notebook | output of 4.2 | Python Visualization Specialist |
| 4.4 | Histogram, KDE, box plot with confidence interval, error bars, Seaborn correlation heatmap, Plotly scatter and bubbles are all present | notebook review | Python Visualization Specialist |
| 4.5 | Cartesian, geographic and polar coordinates are all used | notebook review | Python Visualization Specialist |
| 4.6 | 15 figures as PNG at 300 dpi plus SVG, and 7 self-contained HTML files | output of 4.2 | Python Visualization Specialist |

## 5. Dashboard

| # | Check | Command | Owner |
| :-- | :-- | :-- | :-- |
| 5.1 | Star schema with single-direction one-to-many relationships and the date table marked | Power BI model view | BI Dashboard Lead |
| 5.2 | Every bar chart starts at zero, visual by visual | Power BI, Y axis minimum | BI Dashboard Lead |
| 5.3 | Sequential, diverging and qualitative palettes used where they belong | `docs/05-design-system.md` section 3 | BI Dashboard Lead |
| 5.4 | Cross filtering, date slicer, drill-down, drill-through and tooltips all tested | manual run | BI Dashboard Lead |
| 5.5 | GMV, Orders, Late Rate and Avg Review match the notebook within 0.1% | `apps/bi-dashboard/validation/kpi_reference.csv` against notebook section 10 | BI Dashboard Lead |
| 5.6 | The `.pbix` stays under the GitHub file size limit | `git status` and file size | BI Dashboard Lead |

## 6. Presentation

The deck is handed in as a file and keeps being edited in Canva, so these checks are run on the
deck itself, slide by slide.

| # | Check | How | Owner |
| :-- | :-- | :-- | :-- |
| 6.1 | 16 slides in the planned order: cover, three narrative blocks with their slides, sources and closing | Open the deck | Narrative Lead |
| 6.2 | Each slide type keeps the design of the template; only text and one visual were added | Compare with the template | Narrative Lead |
| 6.3 | One visual per information slide, inside the visual area and not stretched | Open the deck | Narrative Lead |
| 6.4 | No text, title or visual reaches the edge of a slide, and no text frame overflows | Open the deck at full size | QA and Integration Lead |
| 6.5 | Poppins everywhere, with 72 pt sections, 30 pt titles and 16 pt body and sources | Select the text and read the font box | Narrative Lead |
| 6.6 | Every figure on a slide matches [`06-storytelling.md`](06-storytelling.md) in value and rounding, and appears on a single slide | Compare slide by slide | Narrative Lead |
| 6.7 | No slide refers to another slide, and the text reads at an A1 to B1 level | Read the deck aloud | Narrative Lead |
| 6.8 | The deck opens with no repair warning, in PowerPoint and after the Canva import | Open it in both | QA and Integration Lead |
| 6.9 | The talk fits in 9:30 and every member speaks between 1:40 and 2:10 | Timed rehearsal | QA and Integration Lead |
| 6.10 | The sources slide is in the deck and is not presented | Open the deck | Narrative Lead |

## 7. Accessibility

| # | Check | Tool | Owner |
| :-- | :-- | :-- | :-- |
| 7.1 | Every dashboard page and every figure reviewed for protanopia, deuteranopia and tritanopia | [Coblis](https://www.color-blindness.com/coblis-color-blindness-simulator/) | QA and Integration Lead |
| 7.2 | Text contrast of at least 4.5:1 for ink on surface, white on navy and white on accent | WebAIM Contrast Checker | QA and Integration Lead |
| 7.3 | No message depends on color alone: labels, signs or shapes carry it too | manual review | Author |
| 7.4 | Alt text set on the dashboard visuals | Power BI, Format, General, Alt text | BI Dashboard Lead |
| 7.5 | Minimum font size respected: 10 pt in the dashboard, 18 pt in the deck | `docs/05-design-system.md` section 2 | Author |

## 8. Version control and pull requests

| # | Rule |
| :-- | :-- |
| 8.1 | Branch names follow `<type>/<NNN-slug>`, for example `feat/005-final-presentation` |
| 8.2 | Commit messages follow Conventional Commits with a scope, for example `feat(etl): add haversine distance` |
| 8.3 | No change reaches `main` without a pull request |
| 8.4 | The pull request uses the repository template, says which requirement of the brief it covers and reports its verification |
| 8.5 | A visual change attaches before and after images |
| 8.6 | One approval and all checks green before merging; the reviewer is from another role when possible |
| 8.7 | Documentation is updated in the same pull request as the change it describes |

## 9. Final submission

| # | Check | State |
| :-- | :-- | :-- |
| 9.1 | Interactive BI dashboard file in the repository | `apps/bi-dashboard/IT91_Olist_Dashboard_Power_Bi_Final_Project_ECBD.pbix` |
| 9.2 | Commented notebook with its outputs in the repository | `apps/notebooks/final_visualizations.ipynb` |
| 9.3 | Executive deck in the repository | `apps/presentation/IT91_Phanex_Final_Project_Presentation_ECBD.pptx` |
| 9.4 | Deck exported to PDF | `apps/presentation/IT91_Phanex_Final_Project_Presentation_ECBD.pdf`; export it again whenever the deck changes |
| 9.5 | Canva link shared with anyone who has the link | Done; the address is in [`../apps/presentation/README.md`](../apps/presentation/README.md) |
| 9.6 | Repository link readable by the teacher | Manual step: either the repository is made public or the teacher is added as a collaborator |
| 9.7 | README links tested in a private browser window | Manual step |
| 9.8 | Timed rehearsal with the five members | Manual step |

## 10. Known limitations for the presentation day

- The interactive Plotly maps may need an internet connection to draw completely. The deck uses
  the static PNG figures, so the talk does not depend on the network.
- The deck is a PowerPoint file. Exporting it to PDF and publishing it on Canva are manual steps
  and need PowerPoint and a Canva account.
- Bring the PDF and the HTML files on a USB drive as a backup, in case the projector or the
  network fails.
