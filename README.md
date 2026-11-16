# Phanex

**Phanex** is the official name of the final project for the **Data Base Knowledge Extraction** course (ECBD: *Enterprise Multi-Modal Data Visualization and Storytelling*). It analyzes the public **Brazilian E-Commerce Public Dataset by Olist** to answer one question:

> **How much does missing the promised delivery date cost Olist, and where does it happen?**

This repository contains a reproducible Python ETL pipeline that builds a star schema, a flat table for analysis and a quality log. The Power BI dashboard, the `final_visualizations.ipynb` notebook and the executive presentation (November 24, 2026) are built on top of it.

- **Analysis period:** purchases from 2017-01-01 00:00:00 to 2018-08-31 23:59:59 (both inclusive).
- **Currency:** Brazilian real (BRL, R$), not converted.
- **Fact table grain:** one order line (`fact_order_items`, 112 279 rows in the last run).

**Quick start:** follow [`docs/08-setup-and-run.md`](docs/08-setup-and-run.md) to set up the environment, extract the Olist data and run the pipeline.

---

## Documentation

| Document | Contents |
| :-- | :-- |
| [`docs/01-project-manual.md`](docs/01-project-manual.md) | Deviations from the project guide and team principles applied |
| [`docs/02-data-dictionary.md`](docs/02-data-dictionary.md) | Every column of the model with its source and formula |
| [`docs/03-data-quality-report.md`](docs/03-data-quality-report.md) | Quality rules, checks and ad hoc queries |
| [`docs/04-star-schema.md`](docs/04-star-schema.md) | Star schema relationships, cardinalities and keys |
| [`docs/05-design-system.md`](docs/05-design-system.md) | Colors, scales, declutter rules and the rules of the deck template |
| [`docs/06-storytelling.md`](docs/06-storytelling.md) | Narrative arc (Setup, Conflict, Resolution) with the notebook findings and their lineage |
| [`docs/07-qa-checklist.md`](docs/07-qa-checklist.md) | QA and integration checklist, accessibility, version control and final submission |
| [`docs/08-setup-and-run.md`](docs/08-setup-and-run.md) | Requirements, installation, Olist data extraction, pipeline run and notebook run (PowerShell) |
| [`docs/09-repository-structure.md`](docs/09-repository-structure.md) | Annotated tree of the repository |
| [`apps/bi-dashboard/README.md`](apps/bi-dashboard/README.md) | Opening the Power BI dashboard, setting `DataPath` and the KPI cross-check |
| [`apps/notebooks/README.md`](apps/notebooks/README.md) | Running the `final_visualizations.ipynb` notebook and its script twin, sections, exports and offline limitation |
| [`apps/presentation/README.md`](apps/presentation/README.md) | The executive deck: its slides, the Canva link and the PDF export |
| [`packages/design-system/README.md`](packages/design-system/README.md) | Color rules and the Power BI theme |

---

## Credits and data sources

| Source | Use | License / origin |
| :-- | :-- | :-- |
| Olist, *Brazilian E-Commerce Public Dataset by Olist* (Kaggle, `olistbr/brazilian-ecommerce`) | Orders, lines, payments, reviews, customers, sellers, products, categories and geolocation | CC BY-NC-SA 4.0; origin: Kaggle ([`olistbr/brazilian-ecommerce`](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)); original archive included in `data/raw/olist/` |
| IBGE, 2018 resident population estimates (SIDRA, table 6579, variable 9324) | `population_2018` and `orders_per_100k` by state | IBGE public data |
| GeoJSON of the Brazilian states (property `sigla`) | Notebook maps (optional for the pipeline) | Code for America, [`click_that_hood`](https://github.com/codeforamerica/click_that_hood) (`public/data/brazil-states.geojson`), MIT license |
| Commercial calendar (`commercial_calendar.csv`) | `commercial_event` of `dim_date` | Authored by the team |
| Category map (`category_macro_map.csv`) | `category_en` and `macro_category` | Authored by the team (proposal pending team review) |

Phanex team (5 members): Data Architect and Cleaner, BI Dashboard Lead, Python Visualization Specialist, Narrative and Storytelling Lead, and QA and Integration Lead.

---

## Licenses

- **Code:** MIT, holder "Phanex Team" (see [`LICENSE`](LICENSE)).
- **Processed data (`data/processed/`):** CC BY-NC-SA 4.0, with attribution to Olist, because it derives from its dataset (see [`data/LICENSE`](data/LICENSE)).
- **Original Olist data (`data/raw/olist/IT91_CSV_Olist_Data_Original_ECBD.zip`):** redistributed only as the original, unmodified archive, under CC BY-NC-SA 4.0 with attribution to Olist; the extracted CSV files are not versioned.
