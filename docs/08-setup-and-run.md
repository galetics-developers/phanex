# 08 — Setup and run

How to prepare the environment, extract the Olist source data, run the ETL pipeline and run the notebook on Windows 11 with PowerShell. Every command is run from the repository root. The folder layout is described in [`09-repository-structure.md`](09-repository-structure.md).

## 1. Requirements

| Tool | Version | Purpose |
| :-- | :-- | :-- |
| Windows 11 with PowerShell | — | The team's operating system; every command in this document is PowerShell |
| Python | 3.10 or later | ETL pipeline and notebook |
| Git | Any recent version | Clone the repository |
| Power BI Desktop | 2.159 or later | Only for the dashboard |

## 2. Python dependencies

All Python dependencies are listed in `requirements.txt` and are installed with a single command:

- `pandas>=2.2`
- `numpy>=1.26`
- `matplotlib`
- `seaborn`
- `plotly`
- `jupyter`
- `ruff`
- `-e packages/etl` (the local `ecbd_etl` package, installed in editable mode)
- `-e packages/viz-kit` (the local `ecbd_viz` package with the palettes, the Matplotlib style, the Plotly template and the exporters of the notebook, installed in editable mode)

> **Note on Python 3.14 and pandas.** The project supports Python 3.10+ with pandas 2.2+ and numpy 1.26+, with no upper bound. Python 3.14 requires pandas 2.3.3 or later (or pandas 3.x); pandas 2.2.x cannot be installed on 3.14 and needs a 3.10–3.13 interpreter. With Python 3.10–3.13, `pip` resolves a compatible pandas version.
>
> Verified environment: Python 3.14.7 with pandas 3.1.1 (the full pipeline ends with exit code 0). Compatibility with pandas 2.2–2.x is declared but has not been checked with a run.

No credentials and no Kaggle account are needed: the pipeline reads no API token or environment variable. `.env.example` only holds a placeholder.

## 3. Installation (PowerShell)

```powershell
git clone <repository-URL>
cd <repository-folder>

py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> **If activation is blocked** with an error saying that running scripts is disabled, run this once for your user and activate again:
>
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> .venv\Scripts\Activate.ps1
> ```

## 4. Olist source data

The archive `data/raw/olist/IT91_CSV_Olist_Data_Original_ECBD.zip` (42.6 MiB) is included in the clone. Extract it **into** `data/raw/olist/` so that the 9 CSV files sit directly in that folder, with no subfolder:

- **PowerShell:**

  ```powershell
  Expand-Archive -Path data\raw\olist\IT91_CSV_Olist_Data_Original_ECBD.zip -DestinationPath data\raw\olist -Force
  ```

- **File Explorer:** right-click the archive, choose *Extract All…* and edit the destination to `data\raw\olist`. The wizard proposes a subfolder named after the archive; remove it from the path.

After extraction, `data/raw/olist/` contains these 9 files:

```text
olist_orders_dataset.csv            olist_customers_dataset.csv
olist_order_items_dataset.csv       olist_sellers_dataset.csv
olist_order_payments_dataset.csv    olist_products_dataset.csv
olist_order_reviews_dataset.csv     olist_geolocation_dataset.csv
product_category_name_translation.csv
```

Keep the archive. The extracted CSV files are ignored by Git and are not versioned.

- **Alternative download:** GitHub Release `data-v1.0`, asset `IT91_CSV_Olist_Data_Original_ECBD.zip` (<https://github.com/CesarSanchez19/Database_Knowledge_Extraction_Final_Project/releases/tag/data-v1.0>). Place the downloaded file in `data/raw/olist/` and extract it the same way.
- **Original source:** Kaggle, [`olistbr/brazilian-ecommerce`](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), CC BY-NC-SA 4.0. The archive holds the original, unmodified CSV files of that dataset.

### Verify integrity

```powershell
Get-FileHash -Algorithm SHA256 data\raw\olist\IT91_CSV_Olist_Data_Original_ECBD.zip
```

The command must return `967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784` (PowerShell prints it in uppercase; the comparison is not case-sensitive). The SHA-256 hashes of the extracted CSV files are listed in [`03-data-quality-report.md`](03-data-quality-report.md#4-dataraw-is-not-modified) and can be checked the same way, for example `Get-FileHash -Algorithm SHA256 data\raw\olist\*.csv`. A different hash means a corrupted or altered download: download it again.

## 5. Other inputs

The other inputs are already versioned: the IBGE 2018 population (`data/raw/external/ibge_population_2018.csv`), the commercial calendar (`data/raw/external/commercial_calendar.csv`) and the category map (`data/reference/category_macro_map.csv`). The states GeoJSON (`data/reference/brazil-states.geojson`) is optional: only the notebook uses it, and the pipeline continues with a warning if it is missing.

## 6. Running the pipeline

```powershell
python scripts/run_pipeline.py
```

The command runs `extract → clean → enrich → model → validate → load`, prints a banner and the counts of each stage, and ends with exit code 0 (about 18 s in the first measured run). The pipeline never modifies `data/raw/`.

| Outcome | What happens |
| :-- | :-- |
| **Success** | Writes the 10 model files to `data/processed/`: `fact_order_items.csv`, seven `dim_*.csv` dimensions, `analytics_flat.csv.gz` (flat table compressed with gzip because the plain CSV exceeded 50 MB) and `data_quality_report.csv` (log of 45 rules with columns `stage, rule, rows_affected, action`) |
| **An input is missing** | The pipeline stops at `extract`, lists every problem and the expected folder (for example `data/raw/olist/`) and writes nothing. |
| **A `validate` rule fails** | `data/processed/` is not touched; the full log is written to `data/interim/data_quality_report_failed.csv` (not versioned) and the exit code is non-zero, naming the failed rules |

## 7. Reading the flat table

```python
import pandas as pd

flat = pd.read_csv(
    "data/processed/analytics_flat.csv.gz",
    compression="gzip",
    dtype={"customer_zip_prefix": str},
)
```

Each column is described in [`02-data-dictionary.md`](02-data-dictionary.md) and the model relationships in [`04-star-schema.md`](04-star-schema.md).

## 8. Lint and helper commands

| Command | What it does |
| :-- | :-- |
| `ruff check .` | Lints the whole repository with the rules in `ruff.toml` (0 errors expected) |
| `python scripts/build_themes.py` | Regenerates the Power BI theme (`apps/bi-dashboard/theme/ecbd-theme.json`) from `packages/design-system/tokens.json` |
| `python scripts/kpi_reference.py` | Computes the dashboard KPIs from `data/processed/` and writes `apps/bi-dashboard/validation/kpi_reference.csv` |
| `python scripts/run_notebook.py` | Executes the notebook, regenerates its script twin and runs the final checks |

`scripts/build_ibge_population.py` is the helper that generated the IBGE population file; it needs network access and is not part of the pipeline.

## 9. Opening the dashboard

See [`apps/bi-dashboard/README.md`](../apps/bi-dashboard/README.md#opening-the-project) (including how to set `DataPath`).

## 10. Running the notebook

The notebook `apps/notebooks/final_visualizations.ipynb` reads `data/processed/analytics_flat.csv.gz`, `data/reference/brazil-states.geojson` and `apps/bi-dashboard/validation/kpi_reference.csv`, which are already versioned, so it does not need the extracted Olist CSV files. Its sections, exports and details are in [`apps/notebooks/README.md`](../apps/notebooks/README.md).

```powershell
python scripts/run_notebook.py
```

The launcher executes the notebook in place (with no cell timeout), regenerates the script twin `apps/notebooks/final_visualizations.py` as its last writing step and then runs four read-only checks: ASCII in the notebook sources, the twin, the README of the notebook, `ecbd_viz` and the launcher itself; the twin matches the notebook; the closed list of 15 static figures (PNG at 300 dpi and SVG) and 7 HTML files exists in `outputs/`; and the text of the SVG files. It ends with exit code 0 only if every check passes. If the execution fails, the twin is not regenerated and the exit code is non-zero.

| Command | What it does |
| :-- | :-- |
| `python scripts/run_notebook.py` | Executes the notebook, regenerates the twin and runs the checks |
| `python scripts/run_notebook.py --check-only` | Runs only the checks, without executing the notebook |
| `python apps/notebooks/final_visualizations.py` | Runs the script twin without Jupyter; it writes the same exports to `outputs/` |
| `jupyter notebook` | Opens Jupyter; open the notebook and choose *Kernel > Restart & Run All*, then run `python scripts/run_notebook.py` so the twin stays in sync |

The twin is generated with `jupyter nbconvert --to script` and is never edited by hand.

**Offline limitation.** The HTML files in `outputs/interactive/` embed plotly.js, so `08_scatter_distance_freight.html`, `09_bubble_category_delay_review.html`, `10_treemap_gmv.html` and `15_polar_hour.html` show their data without an internet connection. The maps may need internet to display completely: `11_choropleth_orders_per_100k.html` and `12_choropleth_delay.html` can depend on geographic layers that Plotly downloads (`13_density_customers.html` uses the same embedded state outlines and no map tiles). This is a known limitation that does not block the delivery. For an offline presentation, use the PNG backups in `outputs/figures/png/`:

| Interactive | PNG backup |
| :-- | :-- |
| `11_`, `12_` and `13_` (maps) | `14_geo_rank_states.png` (static geographic view) |
| `08_scatter_distance_freight.html` | `08s_scatter_distance_freight.png` |
| `09_bubble_category_delay_review.html` | `09s_bubble_category_delay_review.png` |
| `15_polar_hour.html` | `15a_polar_orders_by_hour.png` and `15b_polar_orders_by_weekday.png` |
