# Phanex — Power BI dashboard

Interactive executive dashboard that answers: *how much does it cost Olist to miss the promised delivery date, and where does it happen?*

Deliverables in this folder:

| File | Content |
| :-- | :-- |
| `ECBD_Olist_Dashboard.pbip` (+ `.Report/`, `.SemanticModel/`) | Power BI project: source of truth, text-based (TMDL + PBIR) |
| `IT91_Olist_Dashboard_Power_Bi_Final_Project_ECBD.pbix` | Single-file export of the same report (about 19 MB), exported from the `ECBD_Olist_Dashboard.pbip` project, named with the team's delivery name |
| `dax/measures.dax` | Every DAX measure with a comment (what, grain, denominator) |
| `theme/ecbd-theme.json` | Report theme generated from `packages/design-system/tokens.json` |
| `validation/kpi_reference.csv` | KPI reference computed in Python (`scripts/kpi_reference.py`) |
| `screenshots/` | 01 overview, 02 logistics, 03 geography and product, 04 model view, 05 Power Query, 06 drill-through |

## Environment

| Item | Value |
| :-- | :-- |
| Power BI Desktop | 2.159.1231.0 (Microsoft Store) |
| Power BI Project (`.pbip`) | Available; not listed under preview features (generally available in this version) |
| Semantic model format | TMDL (`ECBD_Olist_Dashboard.SemanticModel/definition/*.tmdl`) |
| Report format | PBIR (`ECBD_Olist_Dashboard.Report/definition/`) |
| TMDL view and DAX query view | Available (not listed as preview features) |
| Azure Maps visual | Available in the Visualizations pane; no separate switch under Options → Security in this version |
| Bing map / filled map and ArcGIS visuals | Disabled (not used) |
| "Detect and reload external PBIP changes" (preview) | Enabled |
| Auto date/time (current file) | Disabled — `dim_date` is the only date table |
| Type detection for unstructured sources (current file) | Disabled — types are set explicitly in Power Query |

Computer use was not available in the authoring session, so the Power Query steps were performed by hand in Power BI Desktop by the dashboard lead (Role 2), following the step-by-step guide prepared for task T3.

## Data source

All queries read the star schema CSV files from `data/processed/` through the required text parameter `DataPath` (UTF-8, code page 65001, `en-US` culture for type conversion; empty strings are converted to null).

To open the project on another computer, change the parameter value: **Home → Transform data → Manage parameters → `DataPath`**, set it to the absolute path of your local `data\processed\` folder **ending with a backslash**, then **Close & Apply**.

Imported tables (8): `fact_order_items`, `dim_date`, `dim_customer`, `dim_seller`, `dim_product`, `dim_state`, `dim_payment_type`, `dim_order_status`. `analytics_flat.csv.gz` and `data_quality_report.csv` are not imported.

Row counts checked in the DAX query view against the CSV files: 112,279 · 1,096 · 98,353 · 3,068 · 32,787 · 27 · 4 · 8; `delivered_date_key` blank = 2,407; `delay_band` blank = `is_late` blank = 2,407.

## Version control

The whole `.pbip` folder is versioned. Local caches and settings under `.pbi/` (`cache.abf`, `localSettings.json`, `editorSettings.json`) are ignored by the repository `.gitignore`.

## Manual edits log (TMDL/JSON edited with Power BI Desktop closed)

| Date | Files | Change | Verified by reopening |
| :-- | :-- | :-- | :-- |
| 2026-11-11 | `definition/model.tmdl`, `definition/relationships.tmdl`, `definition/tables/dim_date.tmdl`; removed `tables/LocalDateTable_*.tmdl` and `tables/DateTableTemplate_*.tmdl` | Removed the auto date/time tables and their relationship/variation left by the auto date/time option; `__PBI_TimeIntelligenceEnabled = 0` | Yes (2026-11-11) |
| 2026-11-11 | `definition/relationships.tmdl` | T4-A: kept the 6 auto-detected dimension relationships (fact → dim, single direction) and added the 3 `dim_date[date_key]` relationships: `purchase_date_key` active, `delivered_date_key` and `estimated_date_key` inactive (`isActive: false`). Total 9, none bidirectional, none between dimensions | Yes (2026-11-11) |
| 2026-11-11 | `definition/tables/dim_date.tmdl` | T4-A: marked as date table (`dataCategory: Time`, `isKey` on `date`); `month_name` sorted by `month_number`, `weekday_name` by `weekday_number`. T4-B: `date_key` hidden; hierarchy `Date hierarchy` (`year` → `quarter` → `month_name` → `date`) | Yes (2026-11-11) |
| 2026-11-11 | `definition/tables/fact_order_items.tmdl` | T4-A: `delay_band` sorted by `delay_band_order`. T4-B: `order_item_key` and the 9 foreign keys hidden (`is_late` stays visible); column formats: `price`, `freight_value`, `item_total`, `payment_value_order` → R$ without decimals (pt-BR), `delivery_days`, `promised_days`, `distance_km` → 1 decimal, `freight_ratio` → percentage with 1 decimal | Yes (2026-11-11) |
| 2026-11-11 | `definition/tables/dim_customer.tmdl` | T4-B: calculated columns `state_name = LOOKUPVALUE(dim_state[state_name], dim_state[uf], dim_customer[state])` and `state_full = dim_customer[state_name] & ", Brazil"` (E-13); data categories `state`, `state_name`, `state_full` → State or Province, `city` → City, `lat`/`lng` → Latitude/Longitude; `customer_key` hidden; hierarchy `Customer geography` (`region` → `state_full` → `city`) | Yes (2026-11-11) |
| 2026-11-11 | `definition/tables/dim_seller.tmdl`, `dim_product.tmdl`, `dim_payment_type.tmdl`, `dim_order_status.tmdl` | T4-B: surrogate keys hidden; seller `lat`/`lng` → Latitude/Longitude; hierarchy `Product` (`macro_category` → `category_en`) | Yes (2026-11-11) |
| 2026-11-11 | `definition/tables/dim_state.tmdl` | T4-B: table and all its columns hidden in report view (it only feeds population for per-capita measures) | Yes (2026-11-11) |
| 2026-11-11 | `definition/tables/_Measures.tmdl` (new) | T5-A: calculated table `_Measures` (`ROW ( "x", 0 )`, column `x` hidden) with the 34 KPI measures in the display folders Commercial, Penetration, Logistics, Satisfaction, Cost, Time and Target; every measure has a format string and an English description (`///`); own filters wrapped in `KEEPFILTERS`; Repeat Customer Rate (P2) included; no GMV MTD | Yes (2026-11-12) |
| 2026-11-11 | `definition/tables/Late Rate Target.tmdl` (new) | T5-A: numeric-range parameter as a calculated table, `SELECTCOLUMNS ( GENERATESERIES ( 0, 20, 1 ), "Value", [Value] / 100 )`, single column `Target` (0%, `ParameterMetadata` extended property); no auto-generated measure (the `Late Rate Target` measure lives in `_Measures`, folder Target, default 8%) | Yes (2026-11-12) |
| 2026-11-11 | `definition/model.tmdl` | T5-A: added `ref table _Measures` and `ref table 'Late Rate Target'`; model culture unchanged (`es-MX`) | Yes (2026-11-12) |
| 2026-11-11 | `definition/expressions.tmdl` | Housekeeping: M step `Origen` renamed to `Source` in the `DataPath` parameter; the path value is unchanged | Yes (2026-11-12) |
| 2026-11-11 | `DAXQueries/Consulta 1.dax` → `DAXQueries/Row counts.dax`; `DAXQueries/.pbi/daxQueries.json` (git-ignored) | Housekeeping: DAX query file renamed and its labels translated (`null delivered_date_key`, `null delay_band`, `null is_late`); the local tab list points to the new name | Yes (2026-11-12) |
| 2026-11-11 | `definition/tables/_Measures.tmdl`; `apps/bi-dashboard/dax/measures.dax` (new) | T5-B: 34 presentation measures in the display folder Presentation (Late Rate Status, late-filter badge, State Detail Title, State Late Rank and top-3 flags, notes, symmetric scale measures, Black Friday points and the 16 `<Visual> Subtitle` measures); none returns a colour; every `FORMAT` passes `"en-US"`. `measures.dax` is a commented copy of all 68 measures (expressions identical to the TMDL, checked by script) | Yes (2026-11-12) |
| 2026-11-12 | `definition/tables/_Measures.tmdl`; `apps/bi-dashboard/dax/measures.dax` | T5-C fix: `Avg Review On Time` and `Negative Review % On Time` filter `fact_order_items[is_late] == 0` (strict equality). With `= 0`, DAX treats BLANK as 0 and the 2,407 non-evaluated orders were counted as on time (Avg Review On Time 4.234 instead of 4.291). Backup: session scratchpad `backup_20261112_154029` | Yes (2026-11-12; the 8 values re-checked) |
| 2026-11-12 | `ECBD_Olist_Dashboard.Report/definition/` (`report.json`, `pages/pages.json`, `pages/p1_summary`, `pages/p2_logistics`, `pages/p3_geo_product`); `StaticResources/RegisteredResources/ecbd-theme.json` (new); removed the default page `Página 1` and its empty Azure Maps visual | T6-A: custom theme `ecbd-theme.json` registered (`themeCollection.customTheme` + `RegisteredResources` package); 3 pages of 1280 × 720 with the common layout: navy band (64 px) with title and subtitle, `Late Filter Badge` button (fill rule on `Late Filter Active`: 1 → accent, else band navy), 3 navigation buttons (radius 8, active page in accent), 240 px filter panel with the synced slicers Date (Between), Year (2017–2018), Quarter, Region, Macro category, Payment type, Late rate target (single select, visible on page 1 only) and the hidden `is_late` slicer. All JSON files validated against the published schemas (report 3.3.0, page 2.1.0, pagesMetadata 1.1.0, visualContainer 2.13.0) | Yes (2026-11-12): opened without errors; layout defects found and fixed in the next row |

Note on the date hierarchy name: the spec name is "Date", but in a tabular model hierarchy names share the table namespace with columns (case-insensitive) and `dim_date` already has a `date` column, so the hierarchy is named `Date hierarchy` (confirmed when the project was reopened after T4).
| 2026-11-12 | `ECBD_Olist_Dashboard.Report/definition/pages/` (all 3 pages regenerated) | T6-A fixes after the first reopen: title and subtitle in one text box (18 pt / 11 pt, no overlap or truncation); badge without fill (white text only while the late-only filter is active; the rule-based fill rendered as a white bar); navigation labels Summary / Logistics / Geography; all slicers as drop-downs with 11 pt text, a "Filters" heading and 8 px spacing; Date slicer limited to 2017-01-01 – 2018-08-31; `(Blank)` removed from Quarter, Region, Macro category and Payment type (the blank member of `dim_date` comes from the 2,407 blank `delivered_date_key` of the inactive relationship); Late rate target defaults to 8 % and single select is no longer strict (strict mode forced 0 % and a value on the hidden `is_late` slicer). T6-B/T6-C: page 1 visuals — KPI card (new card, Late rate in red when the variance is negative, `Late Rate Status` tile), "Cost of the broken promise" card, monthly GMV and Late rate lines by `year_month` (drill to `year`; Black Friday 2017 annotation series in `#D55E00`, C-13 fallback), censoring note, Azure Maps filled layer of Orders per 100k (Viridis, state border `#C8C4BE`), top 10 states by late rate (`State Late Rank` 1–10, worst 3 in `#D55E00`, others `#BFBFBF`, axis from 0) and Late Rate Variance by region (RdBu centred on 0, fixed symmetric axis ±15 pp, C-16 fallback). Backup: `backup_20261112_160835`. 62 JSON files validated | Yes (2026-11-12): opened; visual quality and English values reworked in the next rows |
| 2026-11-12 | `tables/dim_customer.tmdl`, `dim_product.tmdl`, `dim_payment_type.tmdl`, `dim_date.tmdl`, `fact_order_items.tmdl` | User decision (2026-11-12): every value shown in slicers, axes and legends must be in English. Calculated display columns: `dim_customer[region_name]` (Norte North, Nordeste Northeast, Centro-Oeste Central-West, Sudeste Southeast, Sul South), `dim_product[macro_name]` (uncategorized as Uncategorized), `dim_product[category_name]` (`category_en` without underscores, capital first letter), `dim_payment_type[payment_name]` (Boleto as Bank slip (boleto)), `dim_date[month_label]` (e.g. Nov 2017, sorted by `year_month`), `dim_date[quarter_label]` (Q1 to Q4) and `fact_order_items[delay_band_name]` (10+ days early to Over 10 days late, sorted by `delay_band_order`). Hierarchies now use them and have English level names: Customer geography = Region, State, City; Product = Macro category, Category; Date hierarchy = Year, Quarter, Month, Date. `dim_customer[region]` hidden. State and city names stay as proper nouns. Source data, ETL and KPI measures are unchanged. Backup: `backup_20261112_163626` (new session scratchpad) | Yes (2026-11-12): opened, data in all pages, user feedback applied in the next row |
| 2026-11-12 | `tables/_Measures.tmdl`, `dax/measures.dax` | Presentation measures: `State Late Rank`, `Eligible Late States`, `Variance Scale Max` and `Review Gap Scale Max` use `dim_customer[region_name]` (the hierarchy level); texts without special symbols: separators ` \| ` instead of middle dots, "at least" instead of the greater-or-equal sign, `Late Rate Status` = "Above target: +x.x pp" / "Below target: -x.x pp", `Late GMV Note` = "Share of delivered GMV, excludes deliveries without a valid date". `measures.dax` matches the TMDL (68 measures, script check) | Yes (2026-11-12): opened, data in all pages, user feedback applied in the next row |
| 2026-11-12 | `ECBD_Olist_Dashboard.Report/definition/` (pages and bookmarks regenerated) | Redesign and T7, T8: page names without dashes (Executive summary; Logistics and satisfaction; Geography, freight and product; State detail; Tooltip). White rounded cards on the light surface, white filter card with 11 pt slicers, accent colour only on controls. Page 1: one KPI card of 10 tiles in 2 rows (row 2 = cost of the broken promise), 2 monthly lines by `month_label`, filled map, top 10 states, region variance. Page 2: hour x weekday heatmap matrix (Viridis background, cell values printed), review by delay band (axis 0 to 5), delay vs review scatter by category, delay map (inverted RdBu, ±21 days), review gap bars (RdBu, ±0.5 stars). Page 3: seller bubble map (one colour), GMV treemap (macro category to category), distance vs freight scatter by state, 100% stacked payment mix by region, top 10 categories matrix with GMV data bars. Hidden drill-through page State detail (field `state_full`, keeps all filters, Back button, hidden synced slicer copies, card, line, top 10 categories, top 10 cities) and hidden 320 x 240 Tooltip page used by the maps and scatters. Maps filter the other visuals of their page. Bookmarks LateOn, LateOff and Reset (group Interaction) with the buttons Late only, All orders and Reset filters. 100 JSON files validated; no visual outside the canvas and no overlaps (script check) | Yes (2026-11-12): opened, data in all pages, user feedback applied in the next row |
| 2026-11-12 | `_Measures.tmdl`, `measures.dax`, `dim_date.tmdl`, `ECBD_Olist_Dashboard.Report/definition/` | Second review by the user: KPI card split into two cards of 5 tiles (Key figures; Cost of the broken promise) so no value is truncated; all buttons have explicit fill and text colours for the default, hover, press and selected states (the text disappeared on hover); header subtitles 12 pt in `#DCE1EC`; Year and Quarter as tile slicers; display units off on axes and labels (Desktop wrote localised suffixes); RdBu colour scales saturate at 5 pp (region variance) and 0.25 stars (review gap) with symmetric axes of 10 pp and 0.5 stars so small differences stay visible; page 2 rebalanced in a 3 x 2 grid; heatmap uses the new `dim_date[weekday_short]` (Mon to Sun) so all 7 days fit; page 3 matrix wider; `Top10 Late Subtitle` and `Delay Map Subtitle` shortened; bookmarks LateOn, LateOff and Reset now hold the slicer state of every page and do not change page; Reset applies to all visuals so cross-filter selections are cleared too. Backup: `backup_20261112_170458` | Yes (2026-11-12): cards still clipped and Reset not clearing, fixed in the next row |
| 2026-11-12 | `_Measures.tmdl`, `measures.dax`, `ECBD_Olist_Dashboard.Report/definition/` | Third review by the user: page 1 KPI card reduced to one row of 6 tiles (GMV, Orders, Late rate, Late GMV, Late GMV share, Stars lost when late; user decision: Avg Ticket, Avg Delivery Days and Avg Review stay on State detail and the tooltip), 136 px high, values without display units; the late rate status moved to the card subtitle (`KPI Card Subtitle` = orders, late rate, `Late Rate Status` and target; `Late Rate Status` now reads "below target by 1.2 pp"); State detail card 136 px high. Bookmarks: a cleared slicer is written as a slicer filter with an empty `Where` plus empty `filters.byExpr` (removing the property was ignored by Desktop). Backups: `backup_20261112_170458`, `backup_20261112_171751` | Yes (2026-11-12): cards fixed; Reset cleared slicers but also visual filters and drill levels, fixed in the next row |
| 2026-11-12 | `ECBD_Olist_Dashboard.Report/definition/` (regenerated) | Reset filters only targets the 8 slicers (`applyOnlyToTargetVisuals`) and no longer writes an empty `filters.byExpr`: applied to every visual it had removed visual-level filters (year range, not-blank, top N) and drill levels. All visuals regenerated to their designed state. Backup taken before the change | Yes (2026-11-12): visuals restored; Reset still dropped the slicers' own filters, fixed in the next row |
| 2026-11-12 | `ECBD_Olist_Dashboard.Report/definition/` (regenerated) | Reset bookmark repeats each slicer's visual-level filters (`filters.byName`: date range, year 2017-2018, not blank) so applying it no longer brings back 2016 or (Blank); bar labels outside the bars; KPI values 16 pt so the full GMV fits | Yes (2026-11-12): Reset tested by the user on the 3 pages |
| 2026-11-12 | `_Measures.tmdl`, `measures.dax`, `ECBD_Olist_Dashboard.Report/definition/` | T9 clean-up: removed 7 unused measures (`Variance/Delay/Review Gap Scale Max/Min`, fixed symmetric scales were used instead, C-16 fallback; `Top 3 Late Label`, data labels are shown on every bar); 61 measures remain and `measures.dax` matches. Outline of the white Late only / All orders buttons darkened to `#787671` (4.5:1, WCAG non-text contrast); KPI tile label "% of delivered GMV"; `Late GMV Note` is the subtitle of the State detail card. Backup `backup_20261112_173916` | Yes (2026-11-12): `.pbix` saved by the user |
| 2026-11-12 | `ECBD_Olist_Dashboard.Report/definition/` (regenerated) | Final check of the screenshots: visuals without a subtitle now hide it explicitly (Desktop had added automatic subtitles in its UI language, e.g. "por"); State detail card without display units; Back button 64 px wide and shorter State detail subtitle; page 1 KPI values 14 pt so the full GMV fits | Yes (confirmed by the user on 2026-11-13): `.pbix` re-saved and exported as `IT91_Olist_Dashboard_Power_Bi_Final_Project_ECBD.pbix`; `06_drillthrough.png` retaken |

## KPI cross-check (T5-C, RF-93)

Run on 2026-11-12 against `validation/kpi_reference.csv` with read-only DAX queries (Power BI Modeling MCP, `--readonly`, connected to the open Desktop session). Every value is `FORMAT ( <measure>, "0.000000", "en-US" )` (unrounded); the relative difference is \|PBI − ref\| ÷ \|ref\|; tolerance 0.1 %. Scenarios: S0 no filter, S1 `dim_customer[region] = "Nordeste"`, S2 `dim_date[year] = 2018`, S3 `dim_product[macro_category] = "Fashion & Beauty"` (taken from the reference file).

**Result: 87 / 87 within tolerance** (60 KPI values + 27 states; maximum relative difference 0.00002 %). The first run found 8 mismatches in `Avg Review On Time` and `Review Drop Late` (1.1–3.8 %): the filter `is_late = 0` also kept the non-evaluated orders because in DAX `BLANK = 0` is true. The filter was changed to the strict `is_late == 0` (also in `Negative Review % On Time`) and the 8 values were re-run; the reference was not adjusted.

| KPI | S0 Power BI | S1 Power BI | S2 Power BI | S3 Power BI | Max rel. diff |
| :-- | --: | --: | --: | --: | --: |
| GMV | 13,449,529.680000 | 1,532,195.960000 | 7,341,037.410000 | 3,178,117.110000 | 0.00000 % |
| Orders | 97,905.000000 | 9,272.000000 | 53,530.000000 | 20,875.000000 | 0.00000 % |
| Customers | 95,121.000000 | 9,056.000000 | 52,565.000000 | 20,534.000000 | 0.00000 % |
| Avg Ticket | 160.193100 | 201.172700 | 160.529400 | 171.710700 | 0.00002 % |
| Late Rate % | 0.067888 | 0.127565 | 0.077269 | 0.069783 | 0.00000 % |
| Avg Delivery Days | 12.538461 | 19.986712 | 12.137693 | 12.142774 | 0.00000 % |
| Avg Delay Days | -11.807969 | -11.241597 | -11.374538 | -12.060463 | 0.00000 % |
| Avg Review | 4.105933 | 3.906782 | 4.099019 | 4.159539 | 0.00000 % |
| Negative Review % | 0.141514 | 0.184916 | 0.145139 | 0.132340 | 0.00000 % |
| Late GMV | 985,618.470000 | 198,776.790000 | 599,254.840000 | 229,069.830000 | 0.00000 % |
| Late GMV % | 0.074783 | 0.133236 | 0.083032 | 0.073571 | 0.00000 % |
| Avg Review On Time | 4.291045 | 4.223997 | 4.298155 | 4.353601 | 0.00000 % |
| Avg Review Late | 2.270931 | 2.180196 | 2.242614 | 2.283465 | 0.00000 % |
| Review Drop Late | 2.020114 | 2.043801 | 2.055542 | 2.070137 | 0.00000 % |
| Repeat Customer Rate | 0.030348 | 0.023707 | 0.021190 | 0.018475 | 0.00000 % |

Orders per 100k (S0, 27 states; reference = `orders_per_100k` of the ETL):

| State | Power BI | Reference | Rel. diff | State | Power BI | Reference | Rel. diff |
| :-- | --: | --: | --: | :-- | --: | --: | --: |
| AC | 9.318217 | 9.318217 | 0.00000 % | PB | 13.261617 | 13.261617 | 0.00000 % |
| AL | 12.308822 | 12.308822 | 0.00000 % | PE | 17.227773 | 17.227773 | 0.00000 % |
| AM | 3.602402 | 3.602402 | 0.00000 % | PI | 14.979181 | 14.979181 | 0.00000 % |
| AP | 8.197769 | 8.197769 | 0.00000 % | PR | 43.722157 | 43.722157 | 0.00000 % |
| BA | 22.548345 | 22.548345 | 0.00000 % | RJ | 73.741431 | 73.741431 | 0.00000 % |
| CE | 14.500340 | 14.500340 | 0.00000 % | RN | 13.739541 | 13.739541 | 0.00000 % |
| DF | 71.065918 | 71.065918 | 0.00000 % | RO | 13.996446 | 13.996446 | 0.00000 % |
| ES | 50.699982 | 50.699982 | 0.00000 % | RR | 7.457923 | 7.457923 | 0.00000 % |
| GO | 28.752402 | 28.752402 | 0.00000 % | RS | 47.618606 | 47.618606 | 0.00000 % |
| MA | 10.405036 | 10.405036 | 0.00000 % | SC | 50.738507 | 50.738507 | 0.00000 % |
| MG | 54.451709 | 54.451709 | 0.00000 % | SE | 15.011140 | 15.011140 | 0.00000 % |
| MS | 25.763977 | 25.763977 | 0.00000 % | SP | 90.078960 | 90.078960 | 0.00000 % |
| MT | 26.147604 | 26.147604 | 0.00000 % | TO | 17.875181 | 17.875181 | 0.00000 % |
| PA | 11.334943 | 11.334943 | 0.00000 % |  |  |  |  |

## Measure tests (T5-D, RF-33 to RF-33b)

Read-only DAX queries on 2026-11-12 (no temporary visuals were created):

| # | Test | Result |
| :-- | :-- | :-- |
| 1 | `Late Rate Target` with nothing selected; `GMV MTD` must not exist | 8 %; no `GMV MTD` measure — pass |
| 2 | Orders by Delivery / Estimated Date differ from Orders (Nov 2017) | 7,421 vs 4,670 vs 4,598 — pass |
| 3 | `order_status = shipped`: Late Rate %, Late GMV %, Avg Delivery Days, Late Rate Variance | all blank — pass |
| 4 | `is_late = 0`: Late Rate %, Late GMV % | 0 % and 0 % — pass |
| 5 | `is_late = 1`: Late Rate %, Late GMV %, Avg Review On Time, Review Drop Late | 100 %, 100 %, blank, blank — pass |
| 6 | Year 2016 and 2017 (no previous year): GMV YoY % | blank (never −100 %); 2018 = +20.2 % — pass |
| 7 | Only `canceled` orders: Repeat Customer Rate | blank (448 canceled orders) — pass |

## Pages

| Page | Visuals | Colour and axis rules |
| :-- | :-- | :-- |
| Executive summary | KPI card (GMV, Orders, Late rate, Late GMV, % of delivered GMV, Stars lost when late; the subtitle states the late rate against the target); monthly GMV and late rate lines with the Black Friday 2017 point; filled map of orders per 100k people; top 10 states by late rate; late rate variance by region | Lines `#0072B2`, Black Friday `#D55E00`; map Viridis; top 10 worst 3 in `#D55E00`, others `#BFBFBF`, axis from 0; variance RdBu centred on 0, symmetric axis ±10 pp |
| Logistics and satisfaction | Heatmap matrix of orders by purchase hour and weekday; average review by delivery band; delay vs review scatter by category; filled map of average delay by state; review gap vs national by state | Heatmap Viridis with printed values; review columns axis 0 to 5; delay map inverted RdBu centred on 0 (blue early, red late); review gap RdBu centred on 0, symmetric axis ±0.5 stars |
| Geography, freight and product | Seller bubble map (one colour); GMV treemap by macro category and category; distance vs freight ratio scatter by state; 100% stacked payment mix by region; top 10 categories matrix | Bubbles `#0072B2`; Okabe-Ito for categories, regions and payment types; payment axis 0 to 100 %; GMV data bars `#3B528B` from 0 |
| State detail (hidden) | Drill-through on `dim_customer[state_full]`, keeps all filters; key figures card (with Repeat Customer Rate), monthly late rate, top 10 cities, top 10 categories by GMV; Back button | Line and bars `#0072B2`, bars from 0 |
| Tooltip (hidden) | 320 x 240 report-page tooltip with GMV, Orders, Late rate and Average review | Used by the 3 maps and the 2 scatters |

Every title states a finding with a figure checked against the `title_fact` rows of `validation/kpi_reference.csv` (no filters); every subtitle is a measure that reflects the current filters. All visible text is in English; state and city names are proper nouns of the source data.

## Interactions and how to test them

| Interaction | How |
| :-- | :-- |
| Cross-filtering | Click a state on a map or a bar: the other visuals of the page are filtered (maps are set to filter, not highlight) |
| Date controls | Purchase date range (2017-01-01 to 2018-08-31), Year (2017, 2018) and Quarter tiles |
| Synced slicers | Date, Year, Quarter, Customer region, Product category, Payment type, Late rate target and the hidden `is_late` slicer share sync groups on the 3 pages and State detail |
| Drill-down | Top 10 states and review gap bars (Region, State, City), treemap and categories matrix (Macro category, Category), monthly lines (Year, Month) |
| Drill-through | Right-click a state on a map, the top 10 bars or the distance scatter, then Drill through, State detail; Back returns |
| Tooltip | Hover a state on a map or a point on a scatter |
| Bookmarks (group Interaction) | Late only (only late orders on every page, badge "Filter: late only"), All orders, Reset filters (clears every slicer, target back to 8 %, keeps the page) |
| Late rate target | Single-select slicer (0 to 20 %); the late rate turns red and the subtitle says "above target" when the target is lower than the rate |

Tested by the dashboard lead in Power BI Desktop on 2026-11-12: cross-filtering, slicers and sync, drill-down, drill-through, tooltip, Late only and All orders, Reset filters on the 3 pages.

Interface strings such as "Todas", "Selección múltiple", "(En blanco)" or "mill." come from the language of Power BI Desktop, not from the report. With Desktop in English (File, Options and settings, Options, Regional settings, Application language) they read "All", "Multiple selections" and "(Blank)".

## Opening the project

1. Run the ETL once (`python scripts/run_pipeline.py`) or use the versioned `data/processed/` files.
2. Open `ECBD_Olist_Dashboard.pbip` (or its export `IT91_Olist_Dashboard_Power_Bi_Final_Project_ECBD.pbix`) in Power BI Desktop 2.159 or later.
3. Home, Transform data, Manage parameters, `DataPath` = your local `data\processed\` folder ending with a backslash, then Close & apply. The value stored in the project is the author's local path (C-39).
4. Azure Maps must be available (it is by default in this version; Bing and ArcGIS maps are not used).

## Accessibility

| Check | Result |
| :-- | :-- |
| Text contrast (WCAG 2.1, computed) | Ink on surface 16.0:1; ink on white 17.4:1; white on band navy 18.1:1; header subtitle `#DCE1EC` on navy 13.8:1; white on accent 6.6:1 (hover 8.8:1); slate subtitles 6.8:1; red late rate `#B2182B` 6.9:1; heatmap text 13.8:1 or more |
| Non-text contrast | White button outline `#787671` 4.5:1 (the first outline `#C8C4BE`, 1.7:1, was replaced) |
| Colour-blind simulation (Coblis) | Pages 01 to 03 checked by the dashboard lead with protanopia, deuteranopia and tritanopia on 2026-11-12; no confusion reported |
| Colour is not the only cue | Late rate status in words in the KPI subtitle; data labels on every bar; printed values in the heatmap; titles state the finding |
| Alternative text | Every visual and button has English alt text (what it shows and its finding); decorative shapes are labelled as decorative |
| Tab order | Header (title, badge, navigation), filter panel, then visuals left to right and top to bottom; band and panel shapes last |
| Font size | 10 pt minimum for labels, 12 to 13 pt titles |

## Fallbacks and decisions applied

| Topic | Decision |
| :-- | :-- |
| Authoring method | No computer use: TMDL and PBIR files written with Desktop closed and validated against the published schemas (report 3.3.0, page 2.1.0, visualContainer 2.13.0, bookmark 2.1.0); the user reopened, tested and saved |
| C-13 Black Friday | A categorical month axis has no constant X-axis line: orange point series `Black Friday GMV Point` and `Black Friday Late Rate Point` |
| C-16 symmetric diverging scales | Fixed symmetric axes (±10 pp variance, ±0.5 stars review gap, ±21 days delay map); colour saturates at ±5 pp and ±0.25 stars so small values stay visible |
| C-41 top 3 labels | Data labels on every bar (more readable); the worst 3 are highlighted by colour and named in the title |
| C-11 late toggle | Two always-visible buttons (Late only, All orders) instead of a toggle that swaps visibility |
| KPI card | One card with 6 tiles (user decision, 2026-11-12); Avg Ticket, Avg Delivery Days and Avg Review are on State detail and in the tooltip |
| English values | Display columns for region, payment type, macro category, category, month, quarter, weekday and delay band (user decision, 2026-11-12); source data and ETL unchanged |
| Page names | No dashes or special symbols (user decision): Executive summary; Logistics and satisfaction; Geography, freight and product |
| RF-70 map metric selector | Not implemented (P2) |

## Method notes

- **Authoring with Power BI Desktop closed.** Computer use is not available in the authoring sessions, so the semantic model and the report are authored directly as TMDL/PBIR files with Power BI Desktop closed (approved by the team on 2026-11-11). Every edit is listed in the manual edits log above and verified by reopening the project in Desktop.
- **Calculated tables for measures and the target parameter.** `_Measures` is the calculated table `ROW ( "x", 0 )` with its only column hidden, and the "Late rate target" parameter is the calculated table `'Late Rate Target'` with the `ParameterMetadata` extended property, instead of "Enter data" and Modeling → New parameter (fallback of plan §6.3).
- **Late Rate Variance format.** A dynamic format string cannot add a "pp" suffix while keeping a numeric value, so Late Rate Variance uses the static format `+0.0%;-0.0%;0.0%`. The value is a fraction (target − rate; + = better than target); titles, subtitles and axis titles say "pp".
- **`FORMAT` culture.** The model culture is `es-MX`, so every `FORMAT` call in the measures passes `"en-US"` as its third argument to keep the decimal point and the thousands comma.
- **Map metric selector (RF-70).** Not implemented (P2).
- **Generator.** The PBIR pages and bookmarks were produced by a local Python script that is not versioned (like the other temporary validation scripts); the versioned JSON files are the source of truth.
