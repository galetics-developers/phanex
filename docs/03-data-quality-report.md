# 03 — Data quality report

Explains the 45 rules of the `data/processed/data_quality_report.csv` log (reason, action, unit and count of the last run), records the time and size of the runs together with the compression decision for `analytics_flat` (A13), and documents the cross-cutting checks: ad hoc queries Q1–Q30, integrity of `data/raw/` (RF-18), forced failure on missing inputs (RF-19) and Git security checks (RNF-3). The columns of each file are in [`02-data-dictionary.md`](02-data-dictionary.md) and the relationships in [`04-star-schema.md`](04-star-schema.md).

Nothing here is reported as passed without having been run: every check states its real result. The checks that were not run are listed in section 9.

> **English migration note (2026-11-11).** The ETL label values were translated to English (month and weekday names, `delay_band` labels, payment and status labels, macro categories and commercial events) and the columns `payment_label_es` and `status_label_es` were renamed to `payment_label` and `status_label`. The label literals in the code of Q15, Q21 and Q24 and the label values shown in the outputs of Q18 and Q21 are written here with the new English values; the counts and results are those of the reference run of 2026-11-08, which used the previous labels. The SHA-256 hashes in sections 4, 5 and 10 also belong to the runs made before the migration, so they do not match the files produced after it.

## 0. Reference run

| Item | Value |
| :-- | :-- |
| Date | 2026-11-08 |
| Command | `python scripts/run_pipeline.py`, from a clean state (no `data/interim/` before starting) |
| Exit code | `0` |
| Environment (E1) | Windows 11, Python 3.14.7, pandas 3.1.1, numpy 2.5.4 (`pip freeze` of the `.venv`) |
| GeoJSON | Present since 2026-11-08 (Code for America, `click_that_hood`, MIT): 27 UF, no differences. The runs documented before that date were made without it and printed the RF-20 warning |
| `data/interim/` | Did not exist before and does not exist after |
| Log | 45 rows; the 14 `validate` rules at 0 (`validated`) |
| Outputs | The 10 files of D9 in `data/processed/` |

Every count in this document comes from the log of that run. The failure log (`data/interim/data_quality_report_failed.csv`), when it exists, belongs to the last run that reached `validate` and failed; a successful run deletes it after `load`, and a run that fails before `validate` (missing inputs, duplicated natural key) does not touch it. That folder is kept out of Git on purpose.

## 1. Units of `rows_affected`

The unit depends on the rule; it is fixed in the plan and in the code (`quality.py`):

| Unit | Rules |
| :-- | :-- |
| Order lines | `exact_duplicates_items`, the 8 exclusion rules (D3), `zip_without_geolocation`, `null_delivered_date_key`, `null_payment_type_key`, `null_review_score`; in `validate`, the failing rows of the fact table |
| Source rows | `exact_duplicates_other`, `coordinates_outside_box`, `review_score_out_of_range`, `review_extra_per_order`, `payment_not_defined`, `payment_installments_zero` |
| Values | `unparseable_dates` (non-empty date cells that could not be parsed) |
| Orders | `orders_without_items`, `orders_without_payment` and the 4 delivery rules of D4 |
| Products | `product_dims_imputed`, `null_photos_qty` (rows of `dim_product`) |
| States (UF) | `state_without_centroid`, `geojson_state_mismatch` |
| Problems | `inputs_valid` (input problems of D1) |

**D3 rules 6 to 8** (`estimated_date_missing`, `purchase_outside_period`, `customer_state_invalid`): they are evaluated per order but count **lines**, and only the order's lines that were not already counted by another rule. Each line is counted once, in the first rule it fails.

## 2. The 45 rules

### 2.1 `extract` (2)

| Rule | Action | Unit | Count | Reason and treatment |
| :-- | :-- | :-- | --: | :-- |
| `inputs_valid` | `validated` | problems | 0 | Checks that the 12 mandatory inputs exist (9 Olist CSV files, IBGE, calendar, category map), their headers and the D1 validations (27 UF with an integer population > 0; unique calendar dates within range; map with 3 columns and ≤ 8 macro categories). If there is any problem the pipeline stops before transforming (RF-19), so in a log it is always 0 |
| `geojson_state_mismatch` | `reported` | states | 0 | UF of the optional GeoJSON that do not match the 27 expected ones; it only warns. It is 0: the 27 UF of `brazil-states.geojson` (property `sigla`) match the expected ones; compared on 2026-11-08 when the file was added (only the notebook uses it) |

### 2.2 `clean` (19)

| Rule | Action | Unit | Count | Reason and treatment |
| :-- | :-- | :-- | --: | :-- |
| `exact_duplicates_items` | `excluded` | lines | 0 | An item line identical in all its columns would inflate the GMV; the first one is kept. It is counted separately from the rest because it enters the `fact_rows_preserved` formula |
| `exact_duplicates_other` | `excluded` | source rows | 0 | Exact duplicates of orders, payments, reviews, customers, sellers, products and translation. Geolocation is exempt: its median per ZIP uses all rows (RF-38) |
| `unparseable_dates` | `nullified` | values | 0 | The 8 source date columns are read with the explicit format `YYYY-MM-DD HH:MM:SS`; a non-empty value that does not fit becomes null and is counted (RF-23) |
| `coordinates_outside_box` | `excluded` | source rows | 42 | Geolocation rows outside the Brazil bounding box (lat −34..6, lng −74..−34): they are wrong coordinates that would shift the medians. They are discarded before computing the ZIP and state centroids |
| `items_without_order` | `excluded` | lines | 0 | D3 rule 1: line whose `order_id` does not exist in orders |
| `orphan_reference` | `excluded` | lines | 0 | Rule 2: the order's customer, the seller or the product does not exist in its table; without that reference there would be no valid foreign key |
| `price_not_positive` | `excluded` | lines | 0 | Rule 3: null price or price ≤ 0; only that line is excluded |
| `freight_negative` | `excluded` | lines | 0 | Rule 4: null freight or freight < 0 (freight 0 is valid); only that line |
| `seller_state_invalid` | `excluded` | lines | 0 | Rule 5: seller UF outside the 27; only that line |
| `estimated_date_missing` | `excluded` | lines | 0 | Rule 6 (per order): without an estimated date there is no delay and no `estimated_date_key`, which can never be null; the remaining lines of the order are excluded |
| `purchase_outside_period` | `excluded` | lines | 371 | Rule 7 (per order): purchase null or outside 2017-01-01 00:00:00 .. 2018-08-31 23:59:59. These are the 371 lines of 313 orders: 312 from 2016 (September to December) and 1 from September 2018 |
| `customer_state_invalid` | `excluded` | lines | 0 | Rule 8 (per order): customer UF outside the 27 |
| `orders_without_items` | `reported` | orders | 1 088 | Orders left without any line, which disappear from the following stages: 775 have no items in the source (603 `unavailable`, 164 `canceled`, 5 `created`, 2 `invoiced`, 1 `shipped`) and 313 lost all their lines through rule 7. That is why `unavailable` and `created` do not appear in the fact table |
| `review_score_out_of_range` | `excluded` | source rows | 0 | Reviews with a null score or a score outside 1–5; they are discarded before choosing the order's review (RF-31) |
| `review_extra_per_order` | `excluded` | source rows | 551 | An order with several reviews keeps only the most recent one (`review_creation_date`, then `review_answer_timestamp`, then `review_id`); the others are discarded so the order's satisfaction is not duplicated (D5) |
| `payment_not_defined` | `excluded` | source rows | 3 | Payments of type `not_defined`: they do not belong to the catalog of 4 payment types |
| `payment_installments_zero` | `imputed` | source rows | 2 | Payments with 0 installments become 1 (a purchase always has at least one installment) |
| `orders_without_payment` | `reported` | orders | 0 | Orders kept without valid payments: they would have null `payment_type_key`, `payment_value_order` and `installments`. There are none in the period |
| `product_dims_imputed` | `imputed` | products | 6 | Products referenced by the fact table with a missing weight (or a 0 g weight) or missing dimensions, imputed with the median of their category (or of the catalog); they get `dims_imputed = 1` |

### 2.3 `enrich` (5)

| Rule | Action | Unit | Count | Reason and treatment |
| :-- | :-- | :-- | --: | :-- |
| `non_delivered_with_delivery_date` | `nullified` | orders | 1 | Undelivered order (here, `canceled`) with a delivery date: that date is ignored and all its delivery metrics are null; the flag stays at 0 and the order stays in the fact table |
| `delivered_missing_date` | `flagged` | orders | 8 | `delivered` orders without a delivery date: `delivery_data_missing = 1`, null delivery metrics, and the order and its GMV are kept (A3, A5) |
| `delivered_before_purchase` | `flagged` | orders | 0 | `delivered` orders with a delivery earlier than the purchase: same treatment as the previous rule (deviation from guide section 6.2, which excludes them) |
| `estimated_before_purchase` | `nullified` | orders | 0 | Estimated date earlier than the purchase: null `promised_days`; it does not affect `delay_days` or the flag |
| `zip_without_geolocation` | `nullified` | lines | 555 | Lines whose customer or seller ZIP has no centroid (ZIP missing from the geolocation, or with all its coordinates outside the bounding box): null `distance_km` and null coordinates, never 0 (A8) |

### 2.4 `model` (5)

| Rule | Action | Unit | Count | Reason and treatment |
| :-- | :-- | :-- | --: | :-- |
| `null_delivered_date_key` | `reported` | lines | 2 407 | Lines without a valid delivery (undelivered or with flag 1): null `delivered_date_key`, allowed by Decision 4; not an orphan |
| `null_payment_type_key` | `reported` | lines | 0 | Lines of orders without valid payments (null `payment_type_key` allowed) |
| `null_review_score` | `reported` | lines | 936 | Lines of the 744 orders without a valid review; null `review_score` and `is_negative_review` (not a foreign key) |
| `null_photos_qty` | `reported` | products | 610 | `dim_product` products without `photos_qty` in the source; kept null, not imputed (RF-36). They are the products without a category |
| `state_without_centroid` | `reported` | states | 0 | UF without any geolocation row inside the bounding box: null centroid. All 27 have a centroid |

### 2.5 `validate` (14)

All of them are evaluated before deciding (RF-61); if any is > 0, the 45-row failure log is written to `data/interim/`, the pipeline ends with exit code 1 naming the failed rules and `load` is not run (RF-62). `rows_affected` = failing rows; 0 = pass.

| Rule | Action | Unit | Count | Reason and treatment |
| :-- | :-- | :-- | --: | :-- |
| `dim_keys_unique` | `validated` | dimension rows | 0 | Surrogate key and natural key of the 7 dimensions non-null and not repeated (1:* relationships in Power BI) |
| `fact_item_key_unique` | `validated` | lines | 0 | `order_item_key` unique and non-null |
| `fact_order_item_unique` | `validated` | lines | 0 | `order_id` + `order_item_id` unique: the grain of the fact table (RF-49) |
| `fact_no_orphans` | `validated` | lines | 0 | The 9 foreign keys exist in their dimension; only `delivered_date_key` (no valid delivery, null `delivery_days`) and `payment_type_key` (no valid payments, null `payment_value_order`) can be null; a non-null payment type outside the catalog counts as an orphan |
| `fact_rows_preserved` | `validated` | lines | 0 | Source lines (112 650) = fact rows (112 279) + `exact_duplicates_items` (0) + the 8 D3 rules (371). Guarantees that no line is lost without a record; value = absolute difference |
| `csp_dims_only_used_keys` | `validated` | dimension rows | 0 | `dim_customer`, `dim_seller` and `dim_product` only contain keys used by the fact table (Decision 10) |
| `fact_within_period` | `validated` | lines | 0 | Every `purchase_date_key` within 20170101..20180831 |
| `dim_date_coverage` | `validated` | rows | 0 | `dim_date` continuous 2016-01-01..2018-12-31 without repeats; `purchase_date_key` and `estimated_date_key` non-null and, like `delivered_date_key` when it is not null, present in `dim_date` |
| `is_late_consistent` | `validated` | lines | 0 | `is_late` = `delay_days > 0`, and null exactly when `delay_days` is null |
| `delivery_nulls_consistent` | `validated` | lines | 0 | With a valid delivery, every delivery metric exists; without it, all are null; the flag is 0/1 and 0 outside `delivered` (D4) |
| `categories_mapped` | `validated` | products | 0 | Every product has `category_en` and `macro_category` from the map (D2) |
| `macro_categories_max_8` | `validated` | extra macro categories | 0 | At most 8 macro categories (there are exactly 8, including `uncategorized`) |
| `dim_state_27` | `validated` | states | 0 | `dim_state` has exactly the 27 UF, without repeats or extras |
| `fact_min_rows` | `validated` | missing lines | 0 | At least 5 000 rows in the fact table (R4); value = shortfall against 5 000 |

## 3. Time, size and compression decision (A13, RF-73, RNF-5)

| Measurement | First full run (T8) | Reference run (section 0) |
| :-- | --: | --: |
| Time (`Measure-Command`) | 17.9 s | 19.1 s |
| Time printed by the pipeline | — | 17.6 s |
| `analytics_flat.csv` uncompressed | 77 557 724 B | — |
| `analytics_flat.csv.gz` | 25 799 405 B | 25 799 405 B |

**Decision A13:** the plain CSV was 77 557 724 bytes, above the 50 000 000-byte limit (`FLAT_SIZE_LIMIT_BYTES`, GitHub's warning threshold). That is why `config.py` sets `ANALYTICS_FLAT_GZIP = True` and `load` writes `analytics_flat.csv.gz` with `compression={"method": "gzip", "mtime": 0}` (the gzip header has `mtime` = 0, checked in Q28), deletes the uncompressed variant and leaves exactly 10 files. No Git LFS and no Parquet.

Size of the 10 files of the reference run (bytes): `fact_order_items.csv` 26 294 180; `analytics_flat.csv.gz` 25 799 405; `dim_customer.csv` 13 638 183; `dim_product.csv` 3 449 649; `dim_seller.csv` 300 102; `dim_date.csv` 63 645; `dim_state.csv` 2 015; `data_quality_report.csv` 1 833; `dim_order_status.csv` 252; `dim_payment_type.csv` 147. None exceeds 50 MB.

## 4. RF-18: `data/raw/` is not modified (H)

SHA-256 of every file in `data/raw/` (with `Get-FileHash`) before and after the reference run, plus an aggregate hash of the sorted `hash  path` list. Script used (outside the repository):

```powershell
param([string]$Dir, [string]$Out)
$root = (Resolve-Path $Dir).Path
$rows = Get-ChildItem -LiteralPath $root -Recurse -File -Force | Sort-Object FullName | ForEach-Object {
  $rel = $_.FullName.Substring($root.Length).TrimStart('\').Replace('\','/')
  $h = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
  "$h  $rel"
}
$rows | Set-Content -LiteralPath $Out -Encoding ascii
$tmp = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tmp, (($rows -join "`n") + "`n"))
$agg = (Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash
Remove-Item $tmp
"FILES=$($rows.Count) AGGREGATE=$agg"
```

```powershell
powershell -File hash_dir.ps1 -Dir data/raw -Out raw_before.txt
python scripts/run_pipeline.py
powershell -File hash_dir.ps1 -Dir data/raw -Out raw_after.txt
# comparison of the two lists: no differences
```

Result: **identical**. 12 files, aggregate hash `A4D26DE3C84DBF5E81F2CFC8969E0E9C5EDC914E848B5472E00D6D0F9D4BBAD0` before and after; no line differs.

```text
E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855  external/.gitkeep
8F03294DFC49DCA97A3CB0E0E8EB5352D6A4E19A2E677EA5289676ABEB020FE1  external/commercial_calendar.csv
7EAB5FBF16CA5F5953B71B142375C646C4808290D7FA9116B9DD67676EC6D10B  external/ibge_population_2018.csv
983A422239E1712DED753B3BF9ECF47DC73F144D306029DCFA99E70A226883D2  olist/olist_customers_dataset.csv
B514F6FC991B9566AEBA02AA5D67E2C3630F034B60A0E05AA0D082A3B66D88D6  olist/olist_geolocation_dataset.csv
0BC4D068C4FE38CBB01BD90E8746E3C613FE7B4BAEF75FAB7B0E329701C3E279  olist/olist_order_items_dataset.csv
4F713964F2815DBBAA40B9488268C55AAC3627BFCE5AA96CF58D1F3616DE3CC0  olist/olist_order_payments_dataset.csv
012B61C7593E34F51FA614EFDF802B9C7056CE6AAE5307DDB93236E7CFC797D7  olist/olist_order_reviews_dataset.csv
8DF58EF3D2D7E9944010F7BEECD9B75367F5588EC6E3C91CEC19AE3345EF9ECF  olist/olist_orders_dataset.csv
3E6569628A17FBC75FD206EE357B59E20364B9AFA90F5B6CD5B4D624C58AA9CC  olist/olist_products_dataset.csv
1F643D2B950373B85735E7794B20986F528D7A000432E7C6F9BCBB44D0846A0E  olist/olist_sellers_dataset.csv
A81F0D1F27B27E7293F761BC79E3CE8F348EE39C4B3ED3E49BDE38F478586278  olist/product_category_name_translation.csv
```

## 5. RF-19: forced failure with data, in a copy (F)

Procedure (plan section 1.b): a copy of the repository in a temporary folder outside it, without `.git` or `.venv` (and without caches or local AI configuration); two mandatory inputs are removed from **the copy** and the copy's pipeline is run with the interpreter of the real `.venv`. `scripts/run_pipeline.py` puts the copy's `src` first on `sys.path`, and the banner prints the root used.

```powershell
robocopy <repo> <tmp>\repo_copy /E /XD .git .venv __pycache__ .ruff_cache .claude .agents .codegraph
Remove-Item <tmp>\repo_copy\data\raw\olist\olist_orders_dataset.csv
Remove-Item <tmp>\repo_copy\data\raw\external\ibge_population_2018.csv
powershell -File hash_dir.ps1 -Dir <tmp>\repo_copy\data\processed -Out before.txt
cd <tmp>\repo_copy; <repo>\.venv\Scripts\python.exe scripts\run_pipeline.py
powershell -File hash_dir.ps1 -Dir <tmp>\repo_copy\data\processed -Out after.txt
Test-Path <tmp>\repo_copy\data\interim
```

Real output (the temporary path is abbreviated as `<tmp>`):

```text
========================================================================
ECBD Olist Insights - ETL pipeline
Repository root: <tmp>\repo_copy
Seed: 42
========================================================================

[1/6] Stage: extract

PIPELINE FAILED
2 input problem(s):
  - Missing input file: olist_orders_dataset.csv (expected in data/raw/olist/)
  - Missing input file: ibge_population_2018.csv (expected in data/raw/external/)

Expected locations: data/raw/olist/ (Olist CSV), data/raw/external/ (IBGE, commercial calendar), data/reference/ (category map).
Nothing was written to data/interim/ or data/processed/.
```

| Criterion | Result |
| :-- | :-- |
| The printed root is the copy, not the repository | Yes (`<tmp>\repo_copy`) |
| Exit code other than 0 | Yes: `1` |
| Lists both inputs and the expected folder | Yes: `olist_orders_dataset.csv` (`data/raw/olist/`) and `ibge_population_2018.csv` (`data/raw/external/`) |
| Stops at `extract`, before transforming | Yes: no later stage appears |
| Does not write to `data/interim/` | Yes: the folder did not exist before and does not exist after |
| Does not write to `data/processed/` | Yes: aggregate hash of the 11 files (10 outputs + `.gitkeep`) identical before and after, `F62ADA5AEA23FF1AC31AEF94C77835DC5AAB21003A99EFAE2D7565D5B924FA30` |

**Passed.**

## 6. RNF-3: Git security checks (G)

Read-only Git (no `add`, `commit` or index changes):

```bash
git ls-files
git log --all --oneline -- "*.env"
git log --all --oneline -- "kaggle.json" "data/raw/olist/*" "docs/specs/*"
git check-ignore -v data/raw/olist/olist_orders_dataset.csv data/interim/data_quality_report_failed.csv \
    .env kaggle.json .env.local docs/specs/001-estructura-y-etl/spec.md
git check-ignore -v --no-index docs/constitution.md
git check-ignore -v .env.example data/processed/fact_order_items.csv \
    data/raw/external/ibge_population_2018.csv data/reference/category_macro_map.csv
git ls-files --others --exclude-standard   # what "git add ." would add
```

| Check | Result |
| :-- | :-- |
| `git ls-files` | 3 files: `.gitignore`, `README.md`, `docs/constitution.md`. No CSV from `data/raw/olist/`, no credentials, nothing from `docs/specs/` |
| `docs/constitution.md` | **Still tracked** since the initial commit (`dc2b3a3`), although `.gitignore:23` ignores it. It is a **pending user decision** (remove it from the index or from the history); it was not touched |
| `git log --all -- "*.env"` | Empty (0 commits). Also empty for `kaggle.json`, `data/raw/olist/*` and `docs/specs/*` |
| Ignored | `data/raw/olist/` (`.gitignore:50`), `data/interim/` (`:51`), `.env` (`:27`), `.env.*` (`:28`), `kaggle.json` (`:30`), `docs/specs` (`:24`), `docs/constitution.md` (`:23`) |
| Not ignored | `.env.example` (exception `!.env.example`, `:29`), `data/processed/`, `data/raw/external/`, `data/reference/` |
| Candidates to version (`--others --exclude-standard`) | 50 files; none from `data/raw/olist/`, `data/interim/` or `docs/specs/`, and no `.env`, `kaggle.json` or AI configuration. Includes the 10 files of `data/processed/` and its `.gitkeep` |

**Passed**, with the caveat of `docs/constitution.md`, which is reported as a pending decision.

**Update (2026-11-13).** The pending decision on `docs/constitution.md` was resolved: it is no longer tracked (it remains in the earlier history). Since that date, the contents of `data/raw/olist/` stay ignored except the original Olist archive `IT91_CSV_Olist_Data_Original_ECBD.zip`, which is versioned (see row 16 of [`docs/01-project-manual.md`](01-project-manual.md)).

## 7. RNF-2: linter, absolute paths and `os.path`

`ruff check .` ends with 0 errors (`ruff.toml` includes the PTH rule, which forbids `os.path`). The search for absolute paths and `os.path` in the code is part of Q1: 0 hits in `packages/etl` and `scripts/run_pipeline.py`.

## 8. Ad hoc queries Q1–Q30

Scripts run from a temporary folder outside the repository (not versioned; plan D-15) with `python queries.py <repository root>` over the outputs of the reference run and the source CSV files (read-only). The checks recompute from the source whenever possible and set their own constants (bounding box, regions, bands, catalogs) instead of importing them from `config.py`, so the code is not validated against itself; the exceptions are noted in each query. Samples use seed 42.

Common setup:

```python
# --- setup
import gzip
import math
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(sys.argv[1]).resolve()
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw" / "olist"
SEED = 42
BOX = (-34.0, 6.0, -74.0, -34.0)  # lat_min, lat_max, lng_min, lng_max
TXT = {"dtype": str, "keep_default_na": False, "na_values": [""]}


def proc(name, **kw):
    return pd.read_csv(PROC / name, **kw)


def raw(name, **kw):
    return pd.read_csv(RAW / name, encoding="utf-8-sig", **TXT, **kw)


def ts(series):
    return pd.to_datetime(series, format="%Y-%m-%d %H:%M:%S", errors="coerce")


def report(q, ok, detail):
    print(f"{q}: {'PASS' if ok else 'DISCREPANCY'} | {detail}")


fact = proc("fact_order_items.csv")
flat = proc("analytics_flat.csv.gz", dtype={"customer_zip_prefix": str})
dcus = proc("dim_customer.csv", dtype={"zip_prefix": str})
dsel = proc("dim_seller.csv")
dprod = proc("dim_product.csv")
dstate = proc("dim_state.csv")
ddate = proc("dim_date.csv")
dpay = proc("dim_payment_type.csv")
dstat = proc("dim_order_status.csv")
log = proc("data_quality_report.csv").set_index("rule")["rows_affected"]
OUTPUTS = sorted(p.name for p in PROC.iterdir() if p.name != ".gitkeep")
```

| Query | RF | Result |
| :-- | :-- | :-- |
| Q1 | RF-10, RNF-2 | Passed (observation on a helper script) |
| Q2 | RF-22 | Passed |
| Q3 | RF-23, RF-60 | Passed |
| Q4 | RF-24 | Passed |
| Q5 | RF-25 | Passed |
| Q6 | RF-28 | Passed |
| Q7 | RF-29, RF-41 | Passed |
| Q8 | RF-30, RF-31 | Passed |
| Q9 | RF-32 | Passed |
| Q10 | RF-33 | Passed |
| Q11 | RF-34 | Passed |
| Q12 | RF-35 | Passed |
| Q13 | RF-36 | Passed |
| Q14 | RF-37, RF-38 | Passed |
| Q15 | RF-39, RF-40 | Passed |
| Q16 | RF-42, RF-43 | Passed |
| Q17 | RF-44 | Passed |
| Q18 | RF-45, RF-46 | Passed |
| Q19 | RF-47 | Passed |
| Q20 | RF-50 | Passed |
| Q21 | RF-51 | Passed |
| Q22 | RF-52, RF-53 | Passed |
| Q23 | RF-54 | Passed |
| Q24 | RF-55 | Passed |
| Q25 | RF-56 | Passed |
| Q26 | RF-58 | Passed |
| Q27 | RF-59 | Passed |
| Q28 | RF-60 | Passed, with a noted limitation (scientific notation) |
| Q29 | RF-69, RNF-6 | Passed |
| Q30 | RF-72 | Passed |

### Q1 — Configuration literals outside `config.py` (RF-10, RNF-2)

Searches all of `packages/etl/src` and `scripts/` (except `config.py`) for the period and `dim_date` dates, seed 42, the bounding-box limits, the region names, UF codes, `data/` path segments, absolute paths and `os.path`.

```python
# --- Q1 (RF-10, RNF-2): config literals, absolute paths and os.path outside config.py
patterns = {
    "period/dim_date dates": r"20(16|17|18)-(01-01|08-31|12-31)",
    "seed 42": r"(?<![\w.])42(?![\w.])",
    "bounding box": r"(?<![\w.])-?(34|74)\.0(?![\w])|(?<![\w.])6\.0(?![\w])",
    "UF -> region names": r"\b(Norte|Nordeste|Centro-Oeste|Sudeste|Sul)\b",
    "UF codes": r"[\"'](SP|RJ|MG|BA|RS|PR|SC)[\"']",
    "path segments": r"[\"'](data|raw|olist|external|reference|interim|processed)[\"/']",
    "absolute paths": r"[A-Za-z]:[\\/]|[\"']/(home|Users|tmp)",
    "os.path": r"os\.path",
}
code_files = sorted((ROOT / "packages" / "etl" / "src").rglob("*.py")) + sorted(
    (ROOT / "scripts").glob("*.py")
)
hits = []
for path in code_files:
    if path.name == "config.py":
        continue
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for label, pat in patterns.items():
            if re.search(pat, line):
                hits.append(f"{path.relative_to(ROOT).as_posix()}:{n} [{label}] {line.strip()}")
etl_hits = [h for h in hits if h.startswith("packages/") or h.startswith("scripts/run_")]
report("Q1", not etl_hits, f"{len(code_files) - 1} files scanned; ETL hits={len(etl_hits)}; "
       f"other hits={len(hits) - len(etl_hits)}")
for h in hits:
    print("   ", h)
```

```text
Output: Q1: PASS | 10 files scanned; ETL hits=0; other hits=5
    scripts/build_ibge_population.py:14 [absolute paths] URL = "https://apisidra.ibge.gov.br/values/t/6579/n3/all/v/9324/p/2018"
    scripts/build_ibge_population.py:15 [path segments] OUTPUT = Path("data/raw/external/ibge_population_2018.csv")
    scripts/build_ibge_population.py:20 [UF codes] "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    scripts/build_ibge_population.py:21 [seed 42] "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    scripts/build_ibge_population.py:21 [UF codes] "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
```

Result: **passed** for the ETL: 0 hits in the 8 `ecbd_etl` files other than `config.py` and in `scripts/run_pipeline.py`. **Observation:** the 5 hits are in `scripts/build_ibge_population.py`, the helper script that generated `ibge_population_2018.csv` (the pipeline does not call it and [`docs/09-repository-structure.md`](09-repository-structure.md) describes it that way). It repeats the path of the IBGE input as text relative to the working directory (`Path("data/raw/external/ibge_population_2018.csv")`, line 15, instead of `config.IBGE_FILE`) and contains UF codes from the IBGE API (lines 17–23; the `"42"` is the IBGE code of SC, not the seed). The "absolute path" hit on line 14 is a false positive (a URL). It is not a pipeline stage, so it does not break RF-10; it is noted and was not modified.

### Q2 — 5-digit ZIP prefixes (RF-22)

```python
# --- Q2 (RF-22): ZIP prefixes are 5-digit text
bad_dim = int((~dcus["zip_prefix"].str.fullmatch(r"\d{5}")).sum())
bad_flat = int((~flat["customer_zip_prefix"].str.fullmatch(r"\d{5}")).sum())
report("Q2", bad_dim == 0 and bad_flat == 0,
       f"dim_customer.zip_prefix bad={bad_dim}/{len(dcus)}; "
       f"analytics_flat.customer_zip_prefix bad={bad_flat}/{len(flat)}")
```

```text
Output: Q2: PASS | dim_customer.zip_prefix bad=0/98353; analytics_flat.customer_zip_prefix bad=0/112279
```

Result: **passed**.

### Q3 — Date format (RF-23, RF-60)

Checks the format of the dates written in `analytics_flat` and `dim_date`, and parses the 8 source date columns again with the explicit format.

```python
# --- Q3 (RF-23, RF-60): date formats in the outputs and in the sources
dt_re, d_re = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", r"\d{4}-\d{2}-\d{2}"
flat_txt = proc("analytics_flat.csv.gz", **TXT)
bad_out = {c: int((flat_txt[c].notna() & ~flat_txt[c].str.fullmatch(dt_re).fillna(False)).sum())
           for c in ("purchase_date", "delivered_date", "estimated_date")}
bad_out["purchase/estimated null"] = int(flat_txt[["purchase_date", "estimated_date"]]
                                         .isna().sum().sum())
bad_out["dim_date.date"] = int((~proc("dim_date.csv", **TXT)["date"].str.fullmatch(d_re)).sum())
src_cols = {"olist_orders_dataset.csv": ["order_purchase_timestamp", "order_approved_at",
                                         "order_delivered_carrier_date",
                                         "order_delivered_customer_date",
                                         "order_estimated_delivery_date"],
            "olist_order_items_dataset.csv": ["shipping_limit_date"],
            "olist_order_reviews_dataset.csv": ["review_creation_date",
                                                "review_answer_timestamp"]}
n_src_bad = 0
for name, cols in src_cols.items():
    src = raw(name, usecols=cols)
    for c in cols:
        n_src_bad += int((src[c].notna() & ts(src[c]).isna()).sum())
ok = sum(bad_out.values()) == 0 and n_src_bad == log["unparseable_dates"]
report("Q3", ok, f"output format errors={bad_out}; unparseable source values={n_src_bad} "
       f"(log unparseable_dates={log['unparseable_dates']})")
```

```text
Output: Q3: PASS | output format errors={'purchase_date': 0, 'delivered_date': 0, 'estimated_date': 0, 'purchase/estimated null': 0, 'dim_date.date': 0}; unparseable source values=0 (log unparseable_dates=0)
```

Result: **passed**: every source date fits the format (`unparseable_dates` = 0 is real, not a skipped count).

### Q4 — Cities without accents and in title case (RF-24)

```python
# --- Q4 (RF-24): cities without accents, in title case
for label, s in (("dim_customer.city", dcus["city"]), ("dim_seller.seller_city",
                                                       dsel["seller_city"])):
    s = s.dropna()
    accented = s.map(lambda v: any(unicodedata.combining(ch)
                                   for ch in unicodedata.normalize("NFKD", v)))
    not_title = s != s.str.title()
    non_ascii = s.map(lambda v: not v.isascii())
    report("Q4", int(accented.sum()) == 0 and int(not_title.sum()) == 0,
           f"{label}: accented={int(accented.sum())}, not title={int(not_title.sum())}, "
           f"other non-ASCII={int(non_ascii.sum())} {sorted(set(s[non_ascii]))[:5]}")
```

```text
Output: Q4: PASS | dim_customer.city: accented=0, not title=0, other non-ASCII=0 []
Q4: PASS | dim_seller.seller_city: accented=0, not title=0, other non-ASCII=0 []
```

Result: **passed**.

### Q5 — Order status and payment type in lower case (RF-25)

```python
# --- Q5 (RF-25): order status and payment type in lower case, inside the catalogs
vals = {"order_status": flat["order_status"], "payment_type": flat["payment_type"].dropna(),
        "dim_order_status": dstat["order_status"], "dim_payment_type": dpay["payment_type"]}
bad = {k: int((v != v.str.strip().str.lower()).sum()) for k, v in vals.items()}
src_status = set(raw("olist_orders_dataset.csv", usecols=["order_status"])["order_status"]
                 .str.strip().str.lower())
src_pay = set(raw("olist_order_payments_dataset.csv", usecols=["payment_type"])["payment_type"]
              .str.strip().str.lower())
report("Q5", sum(bad.values()) == 0, f"not lower/stripped={bad}; source statuses={sorted(src_status)}; "
       f"source payment types={sorted(src_pay)}")
```

```text
Output: Q5: PASS | not lower/stripped={'order_status': 0, 'payment_type': 0, 'dim_order_status': 0, 'dim_payment_type': 0}; source statuses=['approved', 'canceled', 'created', 'delivered', 'invoiced', 'processing', 'shipped', 'unavailable']; source payment types=['boleto', 'credit_card', 'debit_card', 'not_defined', 'voucher']
```

Result: **passed**. The normalized source values fit in the fixed catalogs except `not_defined`, which is excluded (`payment_not_defined` = 3).

### Q6 — `price > 0`, `freight_value >= 0` and line preservation (RF-28)

```python
# --- Q6 (RF-28): price > 0 and freight_value >= 0 in the whole fact table
n_price = int((~(fact["price"] > 0)).sum())
n_freight = int((~(fact["freight_value"] >= 0)).sum())
n_src = len(raw("olist_order_items_dataset.csv", usecols=["order_id"]))
d3 = ["items_without_order", "orphan_reference", "price_not_positive", "freight_negative",
      "seller_state_invalid", "estimated_date_missing", "purchase_outside_period",
      "customer_state_invalid"]
balance = n_src - (len(fact) + log["exact_duplicates_items"] + sum(log[r] for r in d3))
report("Q6", n_price == 0 and n_freight == 0 and balance == 0,
       f"price<=0 or null={n_price}; freight<0 or null={n_freight}; source lines {n_src} - "
       f"(fact {len(fact)} + dup {log['exact_duplicates_items']} + D3 "
       f"{sum(log[r] for r in d3)}) = {balance}")
```

```text
Output: Q6: PASS | price<=0 or null=0; freight<0 or null=0; source lines 112650 - (fact 112279 + dup 0 + D3 371) = 0
```

Result: **passed**; the `fact_rows_preserved` formula balances with the source lines counted again from the CSV.

### Q7 — Delivery flag against its rules (RF-29, RF-41)

```python
# --- Q7 (RF-29, RF-41): flagged orders vs the two D4 flag rules
flag_orders = flat.loc[flat["delivery_data_missing"] == 1, "order_id"].nunique()
expected = log["delivered_missing_date"] + log["delivered_before_purchase"]
metrics = ["delivered_date", "delivery_days", "delay_days", "is_late", "delay_band",
           "delay_band_order"]
invalid = flat.loc[(flat["order_status"] != "delivered") | (flat["delivery_data_missing"] == 1)]
not_null = int(invalid[metrics].notna().any(axis=1).sum())
report("Q7", flag_orders == expected and not_null == 0,
       f"orders with flag 1={flag_orders}; delivered_missing_date + delivered_before_purchase="
       f"{expected}; lines without valid delivery having a metric={not_null}/{len(invalid)}")
```

```text
Output: Q7: PASS | orders with flag 1=8; delivered_missing_date + delivered_before_purchase=8; lines without valid delivery having a metric=0/2407
```

Result: **passed**: 8 orders with flag 1 = 8 + 0; none of the 2 407 lines without a valid delivery has a delivery metric (matches `null_delivered_date_key`).

### Q8 — One review per order, the most recent (RF-30, RF-31)

Besides uniqueness, it recomputes from the source which review should be kept (D5 order, nulls first) and compares its score.

```python
# --- Q8 (RF-30, RF-31): at most one review per order, scores in 1-5, latest review kept
per_order = flat.groupby("order_id")["review_score"].nunique(dropna=True)
out_of_range = int((flat["review_score"].notna() & ~flat["review_score"].isin(range(1, 6))).sum())
rv = raw("olist_order_reviews_dataset.csv", usecols=["review_id", "order_id", "review_score",
                                                      "review_creation_date",
                                                      "review_answer_timestamp"])
rv = rv.assign(score=pd.to_numeric(rv["review_score"], errors="coerce"),
               c=ts(rv["review_creation_date"]), a=ts(rv["review_answer_timestamp"]))
rv_ok = rv.loc[rv["score"].isin(range(1, 6))]
latest = (rv_ok.sort_values(["order_id", "c", "a", "review_id"], na_position="first",
                            kind="stable").groupby("order_id").tail(1)
          .set_index("order_id")["score"])
fo = flat.drop_duplicates("order_id").set_index("order_id")["review_score"]
mismatch = int((fo.dropna() != latest.reindex(fo.dropna().index)).sum())
no_review = int(fo.isna().sum())
no_review_expected = int((~fo.index.isin(latest.index)).sum())
extra = len(rv_ok) - rv_ok["order_id"].nunique()
report("Q8", int((per_order > 1).sum()) == 0 and out_of_range == 0 and mismatch == 0
       and no_review == no_review_expected and extra == log["review_extra_per_order"],
       f"orders with >1 score={int((per_order > 1).sum())}; out of 1-5={out_of_range}; "
       f"score != latest review={mismatch}; orders without review={no_review} (expected "
       f"{no_review_expected}); extra reviews={extra} (log {log['review_extra_per_order']})")
```

```text
Output: Q8: PASS | orders with >1 score=0; out of 1-5=0; score != latest review=0; orders without review=744 (expected 744); extra reviews=551 (log 551)
```

Result: **passed**: the 744 orders without a valid review are exactly the 936 nulls of `null_review_score` (in lines).

### Q9 — Payments of 20 sample orders (RF-32)

```python
# --- Q9 (RF-32): 20 orders (seed 42) recomputed from the source payments
pay = raw("olist_order_payments_dataset.csv")
pay = pay.assign(payment_type=pay["payment_type"].str.strip().str.lower(),
                 value=pd.to_numeric(pay["payment_value"]),
                 inst=pd.to_numeric(pay["payment_installments"]))
pay = pay.loc[pay["payment_type"] != "not_defined"]
pay = pay.assign(inst=pay["inst"].where(pay["inst"] != 0, 1))
fo = flat.drop_duplicates("order_id").set_index("order_id")
sample = fo.dropna(subset=["payment_type"]).sample(20, random_state=SEED).index
diffs = []
for oid in sample:
    p = pay.loc[pay["order_id"] == oid]
    by_type = p.groupby("payment_type")["value"].sum().reset_index()
    main = by_type.sort_values(["value", "payment_type"], ascending=[False, True]).iloc[0, 0]
    row = fo.loc[oid]
    if not (math.isclose(row["payment_value_order"], p["value"].sum(), abs_tol=1e-9)
            and row["installments"] == p["inst"].max() and row["payment_type"] == main):
        diffs.append(oid)
report("Q9", not diffs, f"20 orders checked, differences={len(diffs)} {diffs}")
```

```text
Output: Q9: PASS | 20 orders checked, differences=0 []
```

Result: **passed**: sum, maximum installments (0 → 1) and main type (highest amount, tie broken by name) match in the 20 orders.

### Q10 — No `lenght` in the outputs (RF-33)

```python
# --- Q10 (RF-33): no column keeps the source spelling "lenght"
lenght = [f"{n}:{c}" for n in OUTPUTS
          for c in pd.read_csv(PROC / n, nrows=0).columns if "lenght" in c]
report("Q10", not lenght, f"{len(OUTPUTS)} files, columns with 'lenght'={lenght}")
```

```text
Output: Q10: PASS | 10 files, columns with 'lenght'=[]
```

Result: **passed**.

### Q11 — Valid and imputed weights (RF-34)

```python
# --- Q11 (RF-34): positive, non-null weights; imputed products vs the log
n_bad_w = int((~(dprod["weight_g"] > 0)).sum())
n_imp = int((dprod["dims_imputed"] == 1).sum())
report("Q11", n_bad_w == 0 and n_imp == log["product_dims_imputed"],
       f"weight_g null or <=0={n_bad_w}; dims_imputed=1: {n_imp} "
       f"(log product_dims_imputed={log['product_dims_imputed']})")
```

```text
Output: Q11: PASS | weight_g null or <=0=0; dims_imputed=1: 6 (log product_dims_imputed=6)
```

Result: **passed**.

### Q12 — Volume of non-imputed products (RF-35)

```python
# --- Q12 (RF-35): volume = length x height x width for non-imputed products
src_p = raw("olist_products_dataset.csv").set_index("product_id")
nonimp = dprod.loc[dprod["dims_imputed"] == 0].set_index("product_id")
dims = src_p.loc[nonimp.index, ["product_length_cm", "product_height_cm",
                                "product_width_cm"]].apply(pd.to_numeric)
vol = dims.prod(axis=1)
n_vol = int((~np.isclose(nonimp["volume_cm3"], vol, rtol=0, atol=1e-9)).sum())
n_w = int((~np.isclose(nonimp["weight_g"],
                       pd.to_numeric(src_p.loc[nonimp.index, "product_weight_g"]))).sum())
report("Q12", n_vol == 0 and n_w == 0,
       f"{len(nonimp)} non-imputed products: volume differences={n_vol}, weight differences={n_w}")
```

```text
Output: Q12: PASS | 32781 non-imputed products: volume differences=0, weight differences=0
```

Result: **passed**.

### Q13 — Null `photos_qty` kept (RF-36)

```python
# --- Q13 (RF-36): null photos_qty kept null and counted
n_null = int(dprod["photos_qty"].isna().sum())
src_null = int(src_p.loc[dprod["product_id"], "product_photos_qty"].isna().sum())
report("Q13", n_null == log["null_photos_qty"] == src_null,
       f"dim_product photos_qty null={n_null}; source null for the same products={src_null}; "
       f"log null_photos_qty={log['null_photos_qty']}")
```

```text
Output: Q13: PASS | dim_product photos_qty null=610; source null for the same products=610; log null_photos_qty=610
```

Result: **passed**.

### Q14 — Bounding box and centroids of 10 sample ZIPs (RF-37, RF-38)

The median is recomputed over every geolocation row of the ZIP inside the bounding box, without deduplicating.

```python
# --- Q14 (RF-37, RF-38): coordinates inside the box and 10 ZIP centroids (seed 42)
geo = raw("olist_geolocation_dataset.csv",
          usecols=["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng",
                   "geolocation_state"])
geo = geo.assign(zip=geo["geolocation_zip_code_prefix"].str.zfill(5),
                 lat=pd.to_numeric(geo["geolocation_lat"]),
                 lng=pd.to_numeric(geo["geolocation_lng"]))
inside = geo["lat"].between(BOX[0], BOX[1]) & geo["lng"].between(BOX[2], BOX[3])
outside_dims = 0
for df, la, ln in ((dcus, "lat", "lng"), (dsel, "lat", "lng")):
    c = df.dropna(subset=[la, ln])
    outside_dims += int((~(c[la].between(BOX[0], BOX[1]) & c[ln].between(BOX[2], BOX[3]))).sum())
zips = dcus.dropna(subset=["lat"]).drop_duplicates("zip_prefix").sample(10, random_state=SEED)
med = geo.loc[inside].groupby("zip")[["lat", "lng"]].median()
n_cent = int((~(np.isclose(zips["lat"], med.loc[zips["zip_prefix"], "lat"], rtol=0, atol=1e-12)
               & np.isclose(zips["lng"], med.loc[zips["zip_prefix"], "lng"], rtol=0,
                            atol=1e-12))).sum())
report("Q14", int((~inside).sum()) == log["coordinates_outside_box"] and outside_dims == 0
       and n_cent == 0,
       f"source rows outside box={int((~inside).sum())} (log {log['coordinates_outside_box']}); "
       f"dim coordinates outside box={outside_dims}; 10 sample ZIPs {list(zips['zip_prefix'])} "
       f"centroid differences={n_cent}")
```

```text
Output: Q14: PASS | source rows outside box=42 (log 42); dim coordinates outside box=0; 10 sample ZIPs ['27580', '15380', '29920', '25660', '08529', '96207', '18209', '58315', '18400', '05056'] centroid differences=0
```

Result: **passed**.

### Q15 — Delivery metrics and bands recomputed (RF-39, RF-40)

Recomputes from the dates of the orders CSV, with its own bands, for the 98 353 orders of the fact table.

```python
# --- Q15 (RF-39, RF-40): delivery metrics recomputed from the source dates
orders = raw("olist_orders_dataset.csv").set_index("order_id")
fo = flat.drop_duplicates("order_id").set_index("order_id")
o = orders.loc[fo.index]
pur, est, dlv = (ts(o["order_purchase_timestamp"]), ts(o["order_estimated_delivery_date"]),
                 ts(o["order_delivered_customer_date"]))
valid = (o["order_status"].str.strip().str.lower() == "delivered") & dlv.notna() & (dlv >= pur)
delay = (dlv.dt.normalize() - est.dt.normalize()).dt.days.where(valid)
bands = [(1, "≤ -10 (very early)"), (2, "-9 to -1 (early)"),
         (3, "0 to 3 (on time / slight)"), (4, "4 to 10 (late)"), (5, "> 10 (very late)")]
order = pd.Series(np.select([delay <= -10, delay <= -1, delay <= 3, delay <= 10, delay > 10],
                            [1, 2, 3, 4, 5], 0), index=delay.index).where(valid)
label = order.map(dict(bands))
checks = {
    "delay_days": ~((fo["delay_days"] == delay) | (fo["delay_days"].isna() & delay.isna())),
    "is_late": ~((fo["is_late"] == (delay > 0).astype(float).where(valid))
                 | (fo["is_late"].isna() & ~valid)),
    "delay_band_order": ~((fo["delay_band_order"] == order)
                          | (fo["delay_band_order"].isna() & order.isna())),
    "delay_band": ~((fo["delay_band"] == label) | (fo["delay_band"].isna() & label.isna())),
    "delivery_days": ~(np.isclose(fo["delivery_days"], ((dlv - pur) / pd.Timedelta(days=1))
                                  .where(valid), rtol=0, atol=1e-9, equal_nan=True)),
    "promised_days": ~(np.isclose(fo["promised_days"], ((est - pur) / pd.Timedelta(days=1))
                                  .where(est >= pur), rtol=0, atol=1e-9, equal_nan=True)),
}
diff = {k: int(v.sum()) for k, v in checks.items()}
report("Q15", sum(diff.values()) == 0,
       f"{len(fo)} orders ({int(valid.sum())} valid deliveries): differences={diff}")
```

```text
Output: Q15: PASS | 98353 orders (96203 valid deliveries): differences={'delay_days': 0, 'is_late': 0, 'delay_band_order': 0, 'delay_band': 0, 'delivery_days': 0, 'promised_days': 0}
```

Result: **passed**: 96 203 valid deliveries = 96 211 `delivered` − 8 flagged.

### Q16 — `item_total`, `freight_ratio`, `same_state`, `is_negative_review` (RF-42, RF-43)

Recomputes over the columns of `analytics_flat` (price, freight, customer and seller UF, score); their correspondence with the source is covered by Q6, Q8 and Q22.

```python
# --- Q16 (RF-42, RF-43): line measures recomputed
neg = (flat["review_score"] <= 2).astype(float).where(flat["review_score"].notna())
checks = {
    "item_total": ~np.isclose(flat["item_total"], flat["price"] + flat["freight_value"],
                              rtol=0, atol=1e-9),
    "freight_ratio": ~np.isclose(flat["freight_ratio"], flat["freight_value"] / flat["price"],
                                 rtol=1e-12, atol=0),
    "same_state": flat["same_state"] != (flat["uf"] == flat["seller_state"]).astype(int),
    "is_negative_review": ~((flat["is_negative_review"] == neg)
                            | (flat["is_negative_review"].isna() & neg.isna())),
}
diff = {k: int(np.asarray(v).sum()) for k, v in checks.items()}
report("Q16", sum(diff.values()) == 0, f"{len(flat)} lines: differences={diff}")
```

```text
Output: Q16: PASS | 112279 lines: differences={'item_total': 0, 'freight_ratio': 0, 'same_state': 0, 'is_negative_review': 0}
```

Result: **passed**.

### Q17 — 20 haversine distances and nulls (RF-44)

```python
# --- Q17 (RF-44): 20 haversine distances (seed 42, tolerance 0.01 km) and null coherence


def haversine(lat1, lng1, lat2, lng2, r=6371.0):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


rows = flat.dropna(subset=["distance_km"]).sample(20, random_state=SEED)
n_far = sum(abs(r.distance_km - haversine(r.seller_lat, r.seller_lng, r.customer_lat,
                                          r.customer_lng)) > 0.01 for r in rows.itertuples())
coord_null = flat[["customer_lat", "customer_lng", "seller_lat", "seller_lng"]].isna().any(axis=1)
iff = int((coord_null != flat["distance_km"].isna()).sum())
n_null = int(flat["distance_km"].isna().sum())
report("Q17", n_far == 0 and iff == 0 and n_null == log["zip_without_geolocation"],
       f"20 distances beyond 0.01 km={n_far}; null distance xor null coordinate={iff}; "
       f"null distances={n_null} (log zip_without_geolocation={log['zip_without_geolocation']})")
```

```text
Output: Q17: PASS | 20 distances beyond 0.01 km=0; null distance xor null coordinate=0; null distances=555 (log zip_without_geolocation=555)
```

Result: **passed**: `distance_km` is null if and only if a coordinate is missing, and the 555 nulls match `zip_without_geolocation`.

### Q18 — Regions of the 27 UF and macro categories (RF-45, RF-46)

UF → region map written from guide section 6.4, independent of `config.py`.

```python
# --- Q18 (RF-45, RF-46): regions of the 27 UF (guide 6.4) and macro categories
GUIDE = {"Norte": "AC AP AM PA RO RR TO", "Nordeste": "AL BA CE MA PB PE PI RN SE",
         "Centro-Oeste": "DF GO MT MS", "Sudeste": "ES MG RJ SP", "Sul": "PR RS SC"}
uf_region = {uf: reg for reg, ufs in GUIDE.items() for uf in ufs.split()}
bad_state = int((dstate["uf"].map(uf_region) != dstate["region"]).sum())
bad_cus = int((dcus["state"].map(uf_region) != dcus["region"]).sum())
bad_sel = int((dsel["seller_state"].map(uf_region) != dsel["seller_region"]).sum())
macro = dprod["macro_category"]
report("Q18", len(dstate) == 27 and bad_state + bad_cus + bad_sel == 0 and macro.notna().all()
       and macro.nunique() <= 8,
       f"dim_state rows={len(dstate)}, wrong region: state={bad_state}, customer={bad_cus}, "
       f"seller={bad_sel}; macro categories={macro.nunique()} {sorted(macro.unique())}, "
       f"null={int(macro.isna().sum())}")
```

```text
Output: Q18: PASS | dim_state rows=27, wrong region: state=0, customer=0, seller=0; macro categories=8 ['Automotive & Industry', 'Basic Consumer Goods', 'Construction & Garden', 'Fashion & Beauty', 'Home & Furniture', 'Leisure & Culture', 'Technology & Appliances', 'uncategorized'], null=0
```

Result: **passed**.

### Q19 — `orders_per_100k` of the 27 UF (RF-47)

Distinct orders with a status other than `canceled` present in the fact table, by customer UF, ÷ population × 100 000 (Decision 18), with a 1e-9 tolerance.

```python
# --- Q19 (RF-47): orders_per_100k recomputed for the 27 UF (tolerance 1e-9)
act = flat.loc[flat["order_status"] != "canceled"].groupby("uf")["order_id"].nunique()
pop = dstate.set_index("uf")["population_2018"]
expected = (act.reindex(pop.index, fill_value=0) / pop * 100_000)
observed = flat.drop_duplicates("uf").set_index("uf")["orders_per_100k"]
n_diff = int((~np.isclose(observed, expected.reindex(observed.index), rtol=0, atol=1e-9)).sum())
report("Q19", n_diff == 0 and len(observed) == 27,
       f"UF present in analytics_flat={len(observed)}; differences={n_diff}; "
       f"min={expected.min():.2f} ({expected.idxmin()}), max={expected.max():.2f} "
       f"({expected.idxmax()})")
```

```text
Output: Q19: PASS | UF present in analytics_flat=27; differences=0; min=3.60 (AM), max=90.08 (SP)
```

Result: **passed**: all 27 UF have orders and match.

### Q20 — Order statuses kept (RF-50)

```python
# --- Q20 (RF-50): order statuses of the fact table = statuses of the surviving source orders
fact_status = fact["order_status_key"].map(dstat.set_index("order_status_key")["order_status"])
surv = orders.loc[fact["order_id"].unique(), "order_status"].str.strip().str.lower()
same = (fact_status.value_counts().sort_index().to_dict()
        == orders.loc[fact["order_id"], "order_status"].str.strip().str.lower()
        .value_counts().sort_index().to_dict())
report("Q20", same and set(fact_status) == set(surv),
       f"lines per status={fact_status.value_counts().to_dict()}; "
       f"orders per status={surv.value_counts().to_dict()}")
```

```text
Output: Q20: PASS | lines per status={'delivered': 109880, 'shipped': 1174, 'canceled': 527, 'processing': 355, 'invoiced': 340, 'approved': 3}; orders per status={'delivered': 96211, 'shipped': 1097, 'canceled': 448, 'processing': 299, 'invoiced': 296, 'approved': 2}
```

Result: **passed**: the statuses of the fact table are those of the source CSV for the surviving orders (6 statuses; `created` and `unavailable` have no lines in the period, see `orders_without_items`). Independence note: the query takes the set of surviving orders from the fact table itself; that this set is the right one is backed by `fact_rows_preserved` (Q6).

### Q21 — Black Friday and English names (RF-51)

```python
# --- Q21 (RF-51): Black Friday and English names
bf = ddate.loc[ddate["date_key"] == 20171124].iloc[0]
months = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
m_ok = (ddate["month_name"] == ddate["month_number"].map(lambda m: months[m - 1])).all()
d_ok = (ddate["weekday_name"] == ddate["weekday_number"].map(lambda d: days[d - 1])).all()
wd_ok = (ddate["weekday_number"] == pd.to_datetime(ddate["date"]).dt.day_of_week + 1).all()
report("Q21", bf["commercial_event"] == "Black Friday" and m_ok and d_ok and wd_ok,
       f"2017-11-24: event={bf['commercial_event']!r}, weekday={bf['weekday_name']}; months ok="
       f"{m_ok}; weekdays ok={d_ok}; 1 = Monday ok={wd_ok}; rows={len(ddate)} "
       f"({ddate['date'].min()} .. {ddate['date'].max()}); events={int(ddate['commercial_event'].notna().sum())}")
```

```text
Output: Q21: PASS | 2017-11-24: event='Black Friday', weekday=Friday; months ok=True; weekdays ok=True; 1 = Monday ok=True; rows=1096 (2016-01-01 .. 2018-12-31); events=41
```

Result: **passed**.

### Q22 — Customer–state consistency and unique `customer_id` (RF-52, RF-53)

```python
# --- Q22 (RF-52, RF-53): customer state = dim_state UF for every fact row; unique customer_id
cs = fact["customer_key"].map(dcus.set_index("customer_key")["state"])
su = fact["customer_state_key"].map(dstate.set_index("customer_state_key")["uf"])
n_diff = int((cs != su).sum())
report("Q22", n_diff == 0 and dcus["customer_id"].is_unique,
       f"fact rows with dim_customer.state != dim_state.uf={n_diff}; customer_id unique="
       f"{dcus['customer_id'].is_unique} ({len(dcus)} rows, "
       f"{dcus['customer_unique_id'].nunique()} customer_unique_id)")
```

```text
Output: Q22: PASS | fact rows with dim_customer.state != dim_state.uf=0; customer_id unique=True (98353 rows, 95121 customer_unique_id)
```

Result: **passed**.

### Q23 — State centroids (RF-54)

```python
# --- Q23 (RF-54): state centroids non-null, inside the box, = median of source rows inside it
med = geo.loc[inside].assign(uf=geo["geolocation_state"].str.strip().str.upper()) \
    .groupby("uf")[["lat", "lng"]].median()
st = dstate.set_index("uf")
n_null = int(st[["centroid_lat", "centroid_lng"]].isna().any(axis=1).sum())
n_out = int((~(st["centroid_lat"].between(BOX[0], BOX[1])
               & st["centroid_lng"].between(BOX[2], BOX[3]))).sum())
n_med = int((~(np.isclose(st["centroid_lat"], med.loc[st.index, "lat"], rtol=0, atol=1e-12)
               & np.isclose(st["centroid_lng"], med.loc[st.index, "lng"], rtol=0,
                            atol=1e-12))).sum())
report("Q23", n_null == 0 and n_out == 0 and n_med == 0 and log["state_without_centroid"] == 0,
       f"null centroids={n_null}; outside box={n_out}; median differences={n_med}; "
       f"log state_without_centroid={log['state_without_centroid']}")
```

```text
Output: Q23: PASS | null centroids=0; outside box=0; median differences=0; log state_without_centroid=0
```

Result: **passed**.

### Q24 — Fixed catalogs (RF-55)

```python
# --- Q24 (RF-55): fixed catalogs
exp_pay = [(1, "credit_card", "Credit card"), (2, "boleto", "Boleto"),
           (3, "voucher", "Voucher"), (4, "debit_card", "Debit card")]
exp_stat = [(1, "created", "Created", 0), (2, "approved", "Approved", 0),
            (3, "invoiced", "Invoiced", 0), (4, "processing", "Processing", 0),
            (5, "shipped", "Shipped", 0), (6, "delivered", "Delivered", 1),
            (7, "unavailable", "Unavailable", 0), (8, "canceled", "Canceled", 0)]
ok_pay = list(dpay.itertuples(index=False, name=None)) == exp_pay
ok_stat = list(dstat.itertuples(index=False, name=None)) == exp_stat
report("Q24", ok_pay and ok_stat, f"dim_payment_type={len(dpay)} rows ok={ok_pay}; "
       f"dim_order_status={len(dstat)} rows ok={ok_stat}")
```

```text
Output: Q24: PASS | dim_payment_type=4 rows ok=True; dim_order_status=8 rows ok=True
```

Result: **passed**.

### Q25 — `date_key` and surrogate keys (RF-56)

```python
# --- Q25 (RF-56): date_key = YYYYMMDD of date; surrogate keys 1..n in natural-key order
dk_ok = (ddate["date_key"].astype(str) == ddate["date"].str.replace("-", "")).all()
res = {}
for name, df, key, nat in (("dim_customer", dcus, "customer_key", ["customer_id"]),
                           ("dim_seller", dsel, "seller_key", ["seller_id"]),
                           ("dim_product", dprod, "product_key", ["product_id"]),
                           ("dim_state", dstate, "customer_state_key", ["uf"]),
                           ("fact_order_items", fact, "order_item_key",
                            ["order_id", "order_item_id"])):
    by_key = df.sort_values(key)
    gapless = (by_key[key].to_numpy() == np.arange(1, len(df) + 1)).all()
    natural = list(by_key[nat].itertuples(index=False, name=None))
    res[name] = bool(gapless and natural == sorted(natural))
report("Q25", dk_ok and all(res.values()), f"date_key = YYYYMMDD: {dk_ok}; 1..n in natural-key "
       f"order: {res}")
```

```text
Output: Q25: PASS | date_key = YYYYMMDD: True; 1..n in natural-key order: {'dim_customer': True, 'dim_seller': True, 'dim_product': True, 'dim_state': True, 'fact_order_items': True}
```

Result: **passed**.

### Q26 — Header and rows of `analytics_flat` (RF-58)

```python
# --- Q26 (RF-58): analytics_flat header and rows
fk = ["purchase_date_key", "delivered_date_key", "estimated_date_key", "customer_key",
      "customer_state_key", "seller_key", "product_key", "payment_type_key", "order_status_key"]
key_cols = [c for c in flat.columns if c.endswith("_key")]
same_rows = (flat[["order_id", "order_item_id"]].equals(fact[["order_id", "order_item_id"]]))
fact_measures = [c for c in fact.columns if c not in fk and c != "order_item_key"]
report("Q26", not key_cols and same_rows and flat.columns[:20].tolist() == fact_measures,
       f"columns={flat.shape[1]}; key columns={key_cols}; rows flat={len(flat)} fact={len(fact)}; "
       f"same order_id/order_item_id sequence={same_rows}; first 20 columns = fact without keys="
       f"{flat.columns[:20].tolist() == fact_measures}")
```

```text
Output: Q26: PASS | columns=62; key columns=[]; rows flat=112279 fact=112279; same order_id/order_item_id sequence=True; first 20 columns = fact without keys=True
```

Result: **passed**: 62 columns, no keys, the same 112 279 rows in the same order as the fact table.

### Q27 — Customer attributes per row (RF-59)

For the customers (`customer_unique_id`) with orders in different cities, it compares the city and ZIP of each row with the customers CSV for that row's `customer_id`, and the coordinates with `dim_customer`.

```python
# --- Q27 (RF-59): customer attributes of each row = those of the order's customer_id
cust = raw("olist_customers_dataset.csv").set_index("customer_id")
multi = flat.groupby("customer_unique_id")["customer_city"].transform("nunique") > 1
sub = flat.loc[multi]
src = cust.loc[sub["customer_id"]]
city = (src["customer_city"].str.strip().str.normalize("NFKD")
        .str.replace(r"[̀-ͯ]", "", regex=True).str.title())
dc = dcus.set_index("customer_id").loc[sub["customer_id"]]
n_diff = int(((city.to_numpy() != sub["customer_city"].to_numpy())
              | (src["customer_zip_code_prefix"].str.zfill(5).to_numpy()
                 != sub["customer_zip_prefix"].to_numpy())
              | ~np.isclose(dc["lat"].to_numpy(), sub["customer_lat"].to_numpy(),
                            equal_nan=True)
              | ~np.isclose(dc["lng"].to_numpy(), sub["customer_lng"].to_numpy(),
                            equal_nan=True)).sum())
report("Q27", n_diff == 0,
       f"customer_unique_id with orders in several cities="
       f"{sub['customer_unique_id'].nunique()} ({len(sub)} lines); rows whose city, ZIP or "
       f"coordinates differ from their own order's customer={n_diff}")
```

```text
Output: Q27: PASS | customer_unique_id with orders in several cities=117 (287 lines); rows whose city, ZIP or coordinates differ from their own order's customer=0
```

Result: **passed**.

### Q28 — CSV format of the 10 files (RF-60)

BOM, CRLF, index column, null markers written as text, booleans outside 0/1, integers with `.0`, numbers with a thousands separator or a decimal comma, scientific notation and the `mtime` of the gzip header.

```python
# --- Q28 (RF-60): CSV format of the 10 files
BOOL = {"is_late", "delivery_data_missing", "is_negative_review", "same_state", "is_weekend",
        "is_completed", "dims_imputed"}
NUM = re.compile(r"-?\d+(\.\d+)?([eE][-+]?\d+)?")
SCI = re.compile(r"[eE][-+]?\d+$")
summary = {"bom": [], "crlf": [], "index": [], "null_tokens": 0, "bad_bool": 0,
           "int_with_.0": 0, "thousands_or_comma_decimal": 0, "scientific": {}}
for n in OUTPUTS:
    data = gzip.decompress((PROC / n).read_bytes()) if n.endswith(".gz") else \
        (PROC / n).read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        summary["bom"].append(n)
    if b"\r" in data:
        summary["crlf"].append(n)
    t = pd.read_csv(PROC / n, **TXT)
    typed = pd.read_csv(PROC / n)
    if t.columns[0] in ("", "Unnamed: 0", "index"):
        summary["index"].append(n)
    summary["null_tokens"] += int(t.isin(["nan", "NaN", "None", "<NA>", "NaT", "null"])
                                  .sum().sum())
    for c in t.columns:
        s = t[c].dropna()
        if c in BOOL:
            summary["bad_bool"] += int((~s.isin(["0", "1"])).sum())
        if pd.api.types.is_numeric_dtype(typed[c]):
            summary["thousands_or_comma_decimal"] += int((~s.str.fullmatch(NUM)).sum())
            if c.endswith("_key") or c in BOOL or c in ("installments", "review_score",
                                                        "delay_days", "photos_qty"):
                summary["int_with_.0"] += int(s.str.contains(r"\.").sum())
            n_sci = int(s.str.contains(SCI).sum())
            if n_sci:
                summary["scientific"][f"{n}:{c}"] = n_sci
gz = (PROC / "analytics_flat.csv.gz").read_bytes()
summary["gzip_mtime"] = int.from_bytes(gz[4:8], "little")
summary["files"] = len(OUTPUTS)
ok = (not summary["bom"] and not summary["crlf"] and not summary["index"]
      and summary["null_tokens"] == summary["bad_bool"] == summary["int_with_.0"]
      == summary["thousands_or_comma_decimal"] == summary["gzip_mtime"] == 0
      and summary["files"] == 10)
report("Q28", ok, f"{summary}")
```

```text
Output: Q28: PASS | {'bom': [], 'crlf': [], 'index': [], 'null_tokens': 0, 'bad_bool': 0, 'int_with_.0': 0, 'thousands_or_comma_decimal': 0, 'scientific': {'analytics_flat.csv.gz:freight_ratio': 1, 'analytics_flat.csv.gz:customer_lat': 7, 'dim_customer.csv:lat': 7, 'fact_order_items.csv:freight_ratio': 1}, 'gzip_mtime': 0, 'files': 10}
```

Result: **passed, with a noted limitation.** The whole D9 format is met. There are 8 values in **scientific notation** in the star schema (7 in `dim_customer.lat`, e.g. `-4.367379244740171e-05`, and 1 in `fact_order_items.freight_ratio`, `8.849557522123894e-05`) and the same 8 in `analytics_flat` (`customer_lat`, `freight_ratio`). It is the default representation of `to_csv` without `float_format` (`packages/etl/src/ecbd_etl/load.py:31`, options in `config.py:568`); D9 requires a dot decimal mark and no thousands separator, but it does not forbid the exponent or set `float_format`, so it is not a breach. pandas and Power BI (en-US regional settings) read them correctly; the limitation is also in `docs/02`. The code was not changed.

### Q29 — Columns of the 10 files in `docs/02` (RF-69, RNF-6)

```python
# --- Q29 (RF-69, RNF-6): every column of the 10 files appears in docs/02
doc02 = (ROOT / "docs" / "02-data-dictionary.md").read_text(encoding="utf-8")
missing = [f"{n}:{c}" for n in OUTPUTS for c in pd.read_csv(PROC / n, nrows=0).columns
           if f"`{c}`" not in doc02]
n_cols = sum(len(pd.read_csv(PROC / n, nrows=0).columns) for n in OUTPUTS)
report("Q29", not missing, f"{n_cols} columns in {len(OUTPUTS)} files; missing in docs/02="
       f"{missing}")
```

```text
Output: Q29: PASS | 146 columns in 10 files; missing in docs/02=[]
```

Result: **passed**.

### Q30 — The 45 rules in this document (RF-72)

Reads the tables of section 2 of this file and compares the action and count of each rule with the log.

```python
# --- Q30 (RF-72): the 45 rules in docs/03 with action and count of the last log
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(sys.argv[1]).resolve()
rep = pd.read_csv(ROOT / "data" / "processed" / "data_quality_report.csv")
doc03 = (ROOT / "docs" / "03-data-quality-report.md").read_text(encoding="utf-8")
rows = {}
for line in doc03.splitlines():
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if line.startswith("| `") and len(cells) >= 5:
        rows[cells[0].strip("`")] = cells
problems = []
for r in rep.itertuples():
    cells = rows.get(r.rule)
    if cells is None:
        problems.append(f"{r.rule}: missing")
    elif cells[1].strip("`") != r.action or cells[3].replace(" ", "") != str(r.rows_affected):
        problems.append(f"{r.rule}: doc {cells[1]}/{cells[3]} vs log {r.action}/{r.rows_affected}")
print(f"Q30: {'PASS' if not problems else 'DISCREPANCY'} | {len(rep)} rules in the log, "
      f"{sum(1 for r in rep.rule if r in rows)} found in docs/03 rule tables; problems={problems}")
```

```text
Output: Q30: PASS | 45 rules in the log, 45 found in docs/03 rule tables; problems=[]
```

Result: **passed**.

### Reading the log (L, RF-63, RF-65)

Compares the log with the closed list in the code (`quality.RULES`, which follows the D9 order).

```python
# --- L (RF-63, RF-65): the success log
rep = proc("data_quality_report.csv")
sys.path.insert(0, str(ROOT / "packages" / "etl" / "src"))
from ecbd_etl.quality import RULES  # noqa: E402

val = rep.loc[rep["stage"] == "validate"]
report("L", list(rep.columns) == ["stage", "rule", "rows_affected", "action"] and len(rep) == 45
       and list(rep[["stage", "rule", "action"]].itertuples(index=False, name=None)) == list(RULES)
       and len(val) == 14 and (val["rows_affected"] == 0).all()
       and (val["action"] == "validated").all()
       and not (ROOT / "data" / "interim" / "data_quality_report_failed.csv").exists(),
       f"rows={len(rep)}; stages={rep['stage'].value_counts().to_dict()}; validate rows with 0="
       f"{int((val['rows_affected'] == 0).sum())}/14; failure log exists="
       f"{(ROOT / 'data' / 'interim' / 'data_quality_report_failed.csv').exists()}")
```

```text
Output: L: PASS | rows=45; stages={'clean': 19, 'validate': 14, 'enrich': 5, 'model': 5, 'extract': 2}; validate rows with 0=14/14; failure log exists=False
```

Result: **passed**: exact columns, 45 rows, the D9 set and order (`stage`, `rule`, `action`), the 14 `validate` rules at 0 and no previous failure log.

## 9. Discrepancies, observations and checks not run

**Discrepancies in Q1–Q30:** none. No code was modified for this report.

**Observations**:

1. Scientific notation in 8 decimal values (Q28; `load.py:31`, `config.py:568`).
2. `scripts/build_ibge_population.py` repeats the path of the IBGE input and UF codes outside `config.py` (Q1); it is a helper that is not part of the pipeline.
3. `docs/constitution.md` is still in the Git index (section 6): pending user decision (resolved on 2026-11-13; see the update in section 6).
4. `brazil-states.geojson` was added to `data/reference/` on 2026-11-08 (Code for America, `click_that_hood`, MIT license). Since then the pipeline no longer prints the RF-20 warning and `geojson_state_mismatch` is 0 after comparing the 27 UF. The earlier runs of this report were made without the file.
5. Environment E1 has pandas **3.1.1** (not 3.0.x as the plan says) and numpy 2.5.4; every check in this document was made with those versions.

**Desirable** (not blocking): the H of RF-21, the forced failures of RF-20, RF-23, RF-26, RF-27 and RF-61/RF-62 and environments E2/E3 are in section 10 (E2 not run: there is no Python 3.10–3.13 on the PC).

## 10. Desirable tests (T10-B)

Desirable block of the spec (not blocking). Mechanism of plan section 1.a and section 1.b. Everything temporary (repository copies, the E3 venv, scripts) lives in a working folder outside the repository, abbreviated here as `<tmp>`. Each copy is created with `robocopy <repo> <tmp>\<case> /E /XD .git .venv __pycache__ .ruff_cache .claude .agents .codegraph .codex .cursor .gemini` and includes the repository's `data/raw/` and `data/processed/`. Except for E3, they are run with the E1 interpreter (`.venv`, Python 3.14.7, pandas 3.1.1, numpy 2.5.4). In each F case, the `Repository root:` line of the banner is checked to be the copy **before** accepting the result. The hash is SHA-256 per file plus an aggregate hash of the sorted `HASH  path` list, the same format as section 4. No code was fixed.

### Summary

| Test | RF | Status | Result |
| :-- | :-- | :-- | :-- |
| Identical hash between two consecutive runs in E1 (H) | RF-21 | Run | **Passes** |
| Without GeoJSON: warning only (F) | RF-20 | Run | **Passes** |
| Invalid date: `unparseable_dates` +1 (F) | RF-23 | Run | **Passes** |
| Duplicated line of items, of another table and of geolocation (F) | RF-26 | Run | **Passes** |
| Duplicated natural key with different content aborts; repeated `review_id` does not (F) | RF-27 | Run | **Passes** |
| Two simultaneous violations after `model` (F) | RF-61, RF-62 | Run | **Passes** |
| `payment_type` = `pix` (outside the catalog) in an order with a single payment (F) | RF-25, RF-57 | Run (after the `fact_no_orphans` fix) | **Passes**: exit code 1, `fact_no_orphans` = 1 (`null_payment_type_key` = 1), 45-row failure log, the copy's `data/processed/` intact; `order_status` = `lost` still fails the same way |
| E2: Python 3.10–3.13 + `pandas==2.2.*` | compatibility | **Not run** | `py -0p` only lists Python 3.14 (`pythoncore-3.14-64`); there is no 3.10–3.13 interpreter and no new interpreters are installed |
| E3: Python 3.14.7 + `pandas>=2.3.3,<3` | compatibility | Run (partial installation) | **Passes**: log identical to E1; 1-ULP differences in coordinates and distance |
| Integrity of the real `data/raw/` and `data/processed/` | RF-18 | Run | **Passes**: both identical before and after |

### Helper functions (outside the repository)

```python
def hash_dir(path):
    """SHA-256 (upper case) of every file under path, sorted; return (rows, aggregate)."""
    root = Path(path)
    rows = []
    for f in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = f.relative_to(root).as_posix()
        rows.append(f"{hashlib.sha256(f.read_bytes()).hexdigest().upper()}  {rel}")
    agg = hashlib.sha256(("\n".join(rows) + "\n").encode()).hexdigest().upper()
    return rows, agg


def gzip_mtime(path):
    """MTIME field of the gzip header (bytes 4-8, little endian)."""
    with open(path, "rb") as fh:
        head = fh.read(10)
    assert head[:2] == b"\x1f\x8b"
    return int.from_bytes(head[4:8], "little")


def run_pipeline(copy, python=E1_PY):
    """Run scripts/run_pipeline.py of the copy; return (code, stdout, stderr)."""
    res = subprocess.run([str(python), "scripts/run_pipeline.py"], cwd=copy,
                         capture_output=True, text=True, encoding="utf-8")
    return res.returncode, res.stdout, res.stderr


def append_line(path, line):
    """Append one line with the file's own terminator (LF, or CRLF in the reviews)."""
    data = Path(path).read_bytes()
    eol = b"\r\n" if data.endswith(b"\r\n") else b"\n"
    assert data.endswith(eol)
    Path(path).write_bytes(data + line.encode("utf-8") + eol)
```

Each F case: copy, change to **the copy**, hash of the copy's `data/processed/`, run, hash again, check of the printed root, of the exit code and of `data/interim/`, and log differences against E1 (`rule: E1 -> copy`).

### H of RF-21: two consecutive runs in E1

Two back-to-back runs of `python scripts/run_pipeline.py` in the real repository (the only runs on the real repository in T10-B), with a hash of `data/processed/` after each one and a read of the MTIME field of the gzip header.

```text
run 1: exit=0 root=<repo> is real repo=True files=10 agg=F62ADA5AEA23FF1AC31AEF94C77835DC5AAB21003A99EFAE2D7565D5B924FA30
  gzip mtime field: 0
  Done in 19.3 s
run 2: exit=0 root=<repo> is real repo=True files=10 agg=F62ADA5AEA23FF1AC31AEF94C77835DC5AAB21003A99EFAE2D7565D5B924FA30
  gzip mtime field: 0
  Done in 18.8 s
run1 == run2 (all files): True
run2 == baseline before T10-B: True
01E7CD68313A45255D5EEB296AAE0DF2279FFF713C63DE7BF23D7FE424CFC9EA  analytics_flat.csv.gz
2A3E1C3B988BA8C930FC724FE1D6BCA727A355649897A4AD1C3F1D5649C15D23  data_quality_report.csv
913685ADB4A79816706D1184D8F42B8D64B241F13071A8B0AC193ECBB00B2AC6  dim_customer.csv
2CBD7BED4A207DE9C3CFF12C2D4CB80F513001A2CB19E80C4E4AFD6E9E542CAF  dim_date.csv
F573DC6C4194ECC183F0EB713C63AAE28A95C5E5F04A212DBB9EEFD198FF4A2D  dim_order_status.csv
40D7496F8C38F4751BB3AC355B3FC9B2B9AC8793FFC848065A84E2AB5C0EB2F7  dim_payment_type.csv
58FE17E225133BB1F4BFE3D1A5A8F6C7E0575FC1925778CC4E1F2C8365111BA9  dim_product.csv
2D467ECDD7F87745C8CCF92F86115B4AF508B26D0B0B946B7BF5ADDF2AA0AF9F  dim_seller.csv
EC556F1460A96E471E764E569E5EBFE2F2FF2E508B34D0A18F21B31B26D3E58E  dim_state.csv
AFD0C8C985DC80240E64912AB70C5A72907AAA9AE9648986C8C75D85323C92A4  fact_order_items.csv
```

**Passes:** the 10 files (including `analytics_flat.csv.gz`, with MTIME 0) have the same hash in both runs and also match the state before T10-B (aggregate `F62ADA5A…`, the same as in section 5).

### F of RF-20: without GeoJSON

The copy has no `data/reference/brazil-states.geojson` (at that time it was not in the repository either); its absence is checked and the pipeline is run.

```text
Repository root: <tmp>\f_rf20
[1/6] Stage: extract
WARNING: optional file brazil-states.geojson not found in data/reference/ (only the notebook needs it).
...
[6/6] Stage: load
Done in 17.7 s
exit code: 0 | interim exists: False
log diff vs E1: {} | files differing from E1 outputs: []
```

**Passes:** warning only, exit code 0, all 6 stages, `geojson_state_mismatch` = 0 and outputs identical to E1.

### F of RF-23: invalid date

```python
# orders, first data row: order_approved_at 2017-10-02 11:07:15 -> 2017-02-30 11:07:15
lines[1] = old.replace(",2017-10-02 11:07:15,", ",2017-02-30 11:07:15,", 1)
```

```text
Repository root: <tmp>\f_rf23
exit code: 0 | interim exists: False
log diff vs E1 (rule: E1 -> copy): {'unparseable_dates': (0, 1)}
files differing from E1 outputs: ['data_quality_report.csv']
```

**Passes:** the date with the right format but that does not exist (February 30) becomes null and `unparseable_dates` goes up by exactly 1; no other rule or output changes.

### F of RF-26: exact duplicates

An exact repeat of the first data row is appended at the end of three CSV files of the copy:

```text
duplicated in olist_order_items_dataset.csv: "00010242fe8c5a6d1ba2dd792cb16214",1,"4244733e06e7ecb4970a6e2683c13e61","48436dade18ac8b2bce089ec2a041202",2017-09-19 09:45:35,58.90,13.29
duplicated in olist_sellers_dataset.csv: "3442f8959a84dea7ee197c632cb2df15","13023",campinas,SP
duplicated in olist_geolocation_dataset.csv: "01037",-23.54562128115268,-46.63929204800168,sao paulo,SP
Repository root: <tmp>\f_rf26
exit code: 0 | interim exists: False
log diff vs E1 (rule: E1 -> copy): {'exact_duplicates_items': (0, 1), 'exact_duplicates_other': (0, 1)}
files differing from E1 outputs: ['analytics_flat.csv.gz', 'data_quality_report.csv', 'dim_customer.csv', 'fact_order_items.csv']
fact_order_items.csv rows E1/copy: 112279 112279 | differing rows: 4 | columns: ['distance_km']
dim_customer.csv rows E1/copy: 98353 98353 | differing rows: 3 | columns: ['lat', 'lng']
```

**Passes:** the items line counts in `exact_duplicates_items` (1) and the sellers line in `exact_duplicates_other` (1); the geolocation line does **not** count (if it were deduplicated, `exact_duplicates_other` would be 2). The fact table keeps 112 279 rows and `fact_rows_preserved` = 0. The only output differences are the ones expected from the exemption: the repeated row weighs in the median of ZIP 01037, whose centroid becomes `-23.54562128115268, -46.63929204800168` for the 3 customers of that ZIP (and in their 4 distances).

### F of RF-27: duplicated natural key and repeated `review_id`

Case A (aborts): same `seller_id` as the first row of sellers, with a different city.

```text
appended to sellers: "3442f8959a84dea7ee197c632cb2df15","13023",valinhos,SP
Repository root: <tmp>\f_rf27_key
[1/6] Stage: extract
[2/6] Stage: clean

PIPELINE FAILED
DuplicateKeyError: Natural key (seller_id) of olist_sellers_dataset.csv is duplicated with different content in 1 key value(s) (2 rows), e.g. seller_id=3442f8959a84dea7ee197c632cb2df15. Fix the source file; nothing was written.
exit code: 1 | interim exists: False | processed hash unchanged: True
```

Case B (does not abort): `review_id` of the first review with the `order_id` of the second, score 3 and dates earlier than the existing review of that order (the reviews CSV uses CRLF and the line is appended with CRLF).

```text
appended to reviews: "7bc2406110b926393aa56f80a40eba40","a548910a1c6147796b98fdf73dbeba33",3,,,2018-03-01 00:00:00,2018-03-02 00:00:00
Repository root: <tmp>\f_rf27_review
exit code: 0 | interim exists: False
log diff vs E1 (rule: E1 -> copy): {'review_extra_per_order': (551, 552)}
files differing from E1 outputs: ['data_quality_report.csv']
```

**Passes:** A stops at `clean` with a message that names the table, the key and the value, exit code 1 and no log (`data/interim/` is not created and the hash of `data/processed/` does not change). B ends with exit code 0: the repeated review does not abort, and D5 discards it because it is the oldest of the order (`review_extra_per_order` +1).

### F of RF-61/RF-62: two simultaneous violations after `model`

Ad hoc script run with the E1 interpreter that imports `ecbd_etl` **from the copy** (it checks `pipeline.__file__` and `config.ROOT`):

```python
copy = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(copy / "packages" / "etl" / "src"))
import pandas as pd
from ecbd_etl import config, pipeline
from ecbd_etl.quality import QualityLog

assert Path(pipeline.__file__).resolve().is_relative_to(copy)
assert config.ROOT.resolve() == copy
pipeline.print_banner()
log = QualityLog()
tables, n_lines = pipeline.run_stages(log)
# Violation 1: duplicated key in dim_seller.
ds = tables["dim_seller"]
tables["dim_seller"] = pd.concat([ds, ds.iloc[[0]]], ignore_index=True)
# Violation 2: orphan product_key on a product used by more than one line.
fact = tables["fact_order_items"].copy()
counts = fact["product_key"].value_counts()
row = fact.index[fact["product_key"].isin(counts[counts > 1].index)][0]
fact.loc[row, "product_key"] = int(tables["dim_product"]["product_key"].max()) + 1000
tables["fact_order_items"] = fact
sys.exit(pipeline.validate_and_load(tables, log, n_lines))
```

```text
Repository root: <tmp>\f_rf61_62
INJECTED: dim_seller +1 duplicated row (seller_key=1); fact row 0 product_key -> 33787
[5/6] Stage: validate
  dim_keys_unique: 2 rows affected
  fact_no_orphans: 1 rows affected
  (the other 12 rules: 0 rows affected)

VALIDATION FAILED
2 validate rule(s) violated: dim_keys_unique, fact_no_orphans
Failure log written to data/interim/data_quality_report_failed.csv; load was not run and data/processed/ was not touched.
exit code: 1
processed hash unchanged: True F62ADA5AEA23FF1AC31AEF94C77835DC5AAB21003A99EFAE2D7565D5B924FA30 11
failure log rows: 45 | columns: ['stage', 'rule', 'rows_affected', 'action']
validate rules > 0: [{'rule': 'dim_keys_unique', 'rows_affected': 2}, {'rule': 'fact_no_orphans', 'rows_affected': 1}]
```

**Passes** (expected result of RF-62): exit code other than 0, both rules named (the first violation does not stop the evaluation, RF-61), a 45-row failure log with both rules > 0 and the copy's `data/processed/` unchanged. `dim_keys_unique` is 2 because it counts every dimension row with a repeated key (the original and the copy), consistent with its "dimension rows" unit (section 2.5).

### E2: Python 3.10–3.13 + `pandas==2.2.*`

**Not run.** `py -0p` only returns `-V:3.14[-64] * C:\Users\lordd\AppData\Local\Python\pythoncore-3.14-64\python.exe`: there is no 3.10–3.13 interpreter on the PC and the task does not install new interpreters. Compatibility with pandas 2.2 remains **not verified** (not blocking).

### E3: Python 3.14.7 + `pandas>=2.3.3,<3`

```powershell
py -3.14 -m venv <tmp>\venv_e3
cd <tmp>\e3_copy
<tmp>\venv_e3\Scripts\python.exe -m pip install -r requirements.txt   # fails on jupyterlab, see below
<tmp>\venv_e3\Scripts\python.exe -m pip install "pandas>=2.3.3,<3"     # pandas 2.3.3, numpy 2.5.4
<tmp>\venv_e3\Scripts\python.exe scripts\run_pipeline.py
```

`pip install -r requirements.txt` ended with an error while installing jupyterlab (`OSError: [Errno 2] No such file or directory: ...\venv_e3\Lib\site-packages\jupyterlab\galata\...`, with pip's hint about *Windows Long Path support*): the cause is the length of the temporary path added to that of the jupyterlab files, not the project. The pipeline dependencies were installed (Python 3.14.7, pandas 2.3.3, numpy 2.5.4) and `scripts/run_pipeline.py` uses the copy's `src`, so the run is valid for the ETL; the full installation of `requirements.txt` in E3 remains **not verified**.

```text
root is copy: True | exit: 0
WARNING: optional file brazil-states.geojson not found in data/reference/ (only the notebook needs it).
Done in 20.7 s
quality report diff vs E1: {}
  analytics_flat.csv.gz: hash differs; text cells differ in 58288 rows, cols ['customer_lat', 'customer_lng', 'distance_km', 'seller_lat', 'seller_lng']
  data_quality_report.csv: identical hash
  dim_customer.csv: hash differs; text cells differ in 31558 rows, cols ['lat', 'lng']
  dim_date.csv, dim_order_status.csv, dim_payment_type.csv, dim_product.csv: identical hash
  dim_seller.csv: hash differs; text cells differ in 1011 rows, cols ['lat', 'lng']
  dim_state.csv: hash differs; text cells differ in 7 rows, cols ['centroid_lat', 'centroid_lng']
  fact_order_items.csv: hash differs; text cells differ in 51307 rows, cols ['distance_km']
interim exists: False
max |E1 - E3|: lat 7.1e-15, lng 1.4e-14, centroid_lat 3.6e-15, centroid_lng 7.1e-15, distance_km 1.6e-12; null mismatches: 0
e.g. dim_customer lat -18.707823797662655 (E1) vs -18.707823797662652 (E3)
```

**Passes** under the criterion of plan section 1.a: the log is identical to E1 (the 45 counts), the tables without coordinates have an identical hash and the differences are limited to the last digits of the coordinate and distance decimals (≤ 1.6e-12 km, same nulls), which come from the median computation in each pandas version. It is not a failure: RF-21 only requires an identical hash with the same interpreter and versions (checked by the H above).

### Integrity of the real data

Hash of the repository's `data/raw/` and `data/processed/` at the start of T10-B and at the end (after the two H runs):

| Folder | Files | Aggregate before | Aggregate after |
| :-- | --: | :-- | :-- |
| `data/raw/` | 12 | `A4D26DE3C84DBF5E81F2CFC8969E0E9C5EDC914E848B5472E00D6D0F9D4BBAD0` | identical |
| `data/processed/` | 11 | `F62ADA5AEA23FF1AC31AEF94C77835DC5AAB21003A99EFAE2D7565D5B924FA30` | identical |

The repository's `data/interim/` does not exist before or after. No F wrote to the real repository: in all of them, the printed root was its copy.

### Defects found

None. No code was modified in T10-B.
