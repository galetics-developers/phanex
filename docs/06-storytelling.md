# 06 — Storytelling: narrative arc and findings

This document gathers the findings of the `final_visualizations.ipynb` notebook in the three blocks of the executive narrative arc: **Setup**, **Conflict** and **Resolution**. It is the input of the Narrative and Storytelling Lead for the deck and the script of the presentation, and it answers the business question of the project:

> **How much does missing the promised delivery date cost Olist, and where does it happen?**

**Origin of the figures.** Every number in this document is copied from the output of section 10 (*Findings and KPI cross-check*) of the executed notebook, with the same value and the same rounding. When the data or the notebook change, regenerate the notebook with `python scripts/run_notebook.py` and update this document in the same change. Currency: Brazilian real (R$), not converted. Region names (`Nordeste`, `Norte`, `Centro-Oeste`, `Sudeste`) are source values and are not translated; states are named by their code (`uf`), as printed in section 10.

**How to read the tables.** Each finding lists its figures, the exported figure that supports it (PNG in `outputs/figures/png/`, interactive HTML in `outputs/interactive/`), the section of the [notebook](../apps/notebooks/final_visualizations.ipynb) that computes it and the source columns of `analytics_flat` (described in [`02-data-dictionary.md`](02-data-dictionary.md)). Unless a row says otherwise, the population is the non-canceled orders of the analysis period (the S0 filter of the KPI reference), with the order-level aggregation of section 2 of the notebook.

## KPI cross-check

Before the story, section 10 compares the four headline KPIs of the notebook with the S0 rows of `apps/bi-dashboard/validation/kpi_reference.csv`, the same reference the Power BI dashboard was validated against (an indirect check with Power BI). The tolerance is an absolute relative difference of at most 0.1%.

| KPI | Notebook | Status |
| :-- | :-- | :-- |
| GMV (R$) | 13,449,529.68 | PASS |
| Orders | 97,905 | PASS |
| Late Rate % | 6.8% | PASS |
| Avg Review | 4.11 | PASS |

Result: **KPIs with PASS: 4 of 4.** The full table, with the reference value and the relative difference of each KPI, is printed in [Section 10.1](../apps/notebooks/final_visualizations.ipynb).

## Setup

*The size of the business and how often the promise is broken.*

| Finding | Figures | Figure | Notebook | Source columns |
| :-- | :-- | :-- | :-- | :-- |
| Olist sold R$ 13,449,529.68 of merchandise (GMV, freight not included) in 97,905 orders during the analysis period | GMV (R$) 13,449,529.68; Orders 97,905 | [`01a_amounts_gmv_by_macro_category`](../outputs/figures/png/01a_amounts_gmv_by_macro_category.png), [`10_treemap_gmv`](../outputs/interactive/10_treemap_gmv.html) | [Section 2](../apps/notebooks/final_visualizations.ipynb), [Section 3](../apps/notebooks/final_visualizations.ipynb), [Section 7](../apps/notebooks/final_visualizations.ipynb) | `order_id`, `order_status`, `price`, `macro_category`, `category_en` |
| Customers are generally satisfied | Avg Review 4.11 | [`04_box_review_by_delay_ci`](../outputs/figures/png/04_box_review_by_delay_ci.png) | [Section 2](../apps/notebooks/final_visualizations.ipynb) | `order_id`, `review_score` |
| Even so, a share of the evaluated orders arrives after the promised date | Late Rate % 6.8% | [`06_errorbars_late_rate_region`](../outputs/figures/png/06_errorbars_late_rate_region.png) | [Section 2](../apps/notebooks/final_visualizations.ipynb) | `order_id`, `is_late` (evaluated orders: `is_late` not null) |
| The largest peak of orders is the Black Friday 2017 week (2017-W47, from 2017-11-20) | Black Friday 2017 week orders 2,972 | [`05_ci_band_weekly_ticket`](../outputs/figures/png/05_ci_band_weekly_ticket.png) | [Section 5.1](../apps/notebooks/final_visualizations.ipynb) | `order_id`, `purchase_date`, `commercial_event` |

## Conflict

*What a late delivery costs and where it happens.*

| Finding | Figures | Figure | Notebook | Source columns |
| :-- | :-- | :-- | :-- | :-- |
| A late order loses about two points of review: on-time orders average 4.29 and late orders 2.27 | Avg Review on time 4.29; late 2.27; drop 2.02 points | [`04_box_review_by_delay_ci`](../outputs/figures/png/04_box_review_by_delay_ci.png) | [Section 4.3](../apps/notebooks/final_visualizations.ipynb), [Section 10.2](../apps/notebooks/final_visualizations.ipynb) | `order_id`, `is_late`, `delay_band`, `delay_band_order`, `review_score` |
| The merchandise value of the late orders is the revenue exposed to unhappy customers | Late GMV (R$) 985,618.47; Late GMV % (of evaluated GMV) 7.5% | [`06_errorbars_late_rate_region`](../outputs/figures/png/06_errorbars_late_rate_region.png) | [Section 10.2](../apps/notebooks/final_visualizations.ipynb) | `order_id`, `order_status`, `price`, `is_late` |
| The delays are concentrated in the North and Northeast: Nordeste is clearly the worst region, followed by Norte and Centro-Oeste | Late Rate %: Nordeste 12.8%, Norte 8.6%, Centro-Oeste 6.5% | [`06_errorbars_late_rate_region`](../outputs/figures/png/06_errorbars_late_rate_region.png), [`12_choropleth_delay`](../outputs/interactive/12_choropleth_delay.html) | [Section 5.2](../apps/notebooks/final_visualizations.ipynb), [Section 8.2](../apps/notebooks/final_visualizations.ipynb) | `order_id`, `region`, `is_late`, `delay_days` |
| The three states with the highest Late Rate % are in the Northeast | Late Rate %: AL 21.5%, MA 17.5%, SE 15.4% | [`01b_amounts_late_rate_by_state`](../outputs/figures/png/01b_amounts_late_rate_by_state.png), [`14_geo_rank_states`](../outputs/figures/png/14_geo_rank_states.png) | [Section 3](../apps/notebooks/final_visualizations.ipynb), [Section 8.4](../apps/notebooks/final_visualizations.ipynb) | `order_id`, `uf`, `state_name`, `is_late` |

## Resolution

*What drives the freight and the delivery pressure, as the basis for the recommendations of the deck.*

| Finding | Figures | Figure | Notebook | Source columns |
| :-- | :-- | :-- | :-- | :-- |
| The freight of an order grows with the distance between seller and customer, but distance explains only part of it | Spearman rho distance vs freight 0.59 (97,417 orders with a distance and a freight) | [`07b_corr_heatmap_spearman`](../outputs/figures/png/07b_corr_heatmap_spearman.png), [`08s_scatter_distance_freight`](../outputs/figures/png/08s_scatter_distance_freight.png), [`08_scatter_distance_freight`](../outputs/interactive/08_scatter_distance_freight.html) | [Section 6.1](../apps/notebooks/final_visualizations.ipynb), [Section 6.2](../apps/notebooks/final_visualizations.ipynb), [Section 10.2](../apps/notebooks/final_visualizations.ipynb) | `order_id`, `distance_km`, `freight_value` |
| The freight weighs most far from the Southeast: the median freight ratio is highest in Norte and lowest in Sudeste | Median freight ratio: Norte 0.36, Sudeste 0.21 | [`04b_violin_freight_ratio`](../outputs/figures/png/04b_violin_freight_ratio.png) | [Section 4.4](../apps/notebooks/final_visualizations.ipynb) | `order_id`, `region`, `price`, `freight_value` (order `freight_ratio` = order freight / order price) |
| The Black Friday 2017 week triples the orders of a median week but keeps an ordinary ticket: the event adds volume and delivery pressure, not value per order | Orders 2,972 vs median weekly orders 1,001 (3.0x); average ticket (R$) 159.02 vs median weekly average ticket (R$) 159.49 | [`05_ci_band_weekly_ticket`](../outputs/figures/png/05_ci_band_weekly_ticket.png) | [Section 5.1](../apps/notebooks/final_visualizations.ipynb), [Section 10.2](../apps/notebooks/final_visualizations.ipynb) | `order_id`, `purchase_date`, `commercial_event`, `item_total` |

**Directions for the recommendations.** The findings above support the recommendations that the deck will state with their estimated impact: calibrate the promised date where the late rate is highest (the Northeast), bring stock closer to the North and Northeast, where distance and freight weigh most, warn customers before an order is late to protect the review, and plan capacity for commercial peaks such as Black Friday, which add orders rather than value per order. The impact estimates belong to the deck and are not computed in the notebook.

## Supporting figures without numbers in this document

These figures add context to the story; their findings are written in the notebook and carry no numbers here.

| Figure | Notebook | What it shows |
| :-- | :-- | :-- |
| [`02_hist_price_log`](../outputs/figures/png/02_hist_price_log.png) | [Section 4.1](../apps/notebooks/final_visualizations.ipynb) | Item prices on a log scale for the largest macro categories |
| [`03_kde_delivery_by_region`](../outputs/figures/png/03_kde_delivery_by_region.png) | [Section 4.2](../apps/notebooks/final_visualizations.ipynb) | Delivery time by region against the average promised time |
| [`07a_corr_heatmap_pearson`](../outputs/figures/png/07a_corr_heatmap_pearson.png) | [Section 6.1](../apps/notebooks/final_visualizations.ipynb) | Linear correlations among the order measures |
| [`09s_bubble_category_delay_review`](../outputs/figures/png/09s_bubble_category_delay_review.png), [`09_bubble_category_delay_review`](../outputs/interactive/09_bubble_category_delay_review.html) | [Section 6.3](../apps/notebooks/final_visualizations.ipynb) | Average delay, average review and GMV by category |
| [`11_choropleth_orders_per_100k`](../outputs/interactive/11_choropleth_orders_per_100k.html) | [Section 8.1](../apps/notebooks/final_visualizations.ipynb) | Orders per hundred thousand inhabitants by state (`orders_per_100k`) |
| [`13_density_customers`](../outputs/interactive/13_density_customers.html) | [Section 8.3](../apps/notebooks/final_visualizations.ipynb) | Point density of customer orders (one point per customer location) |
| [`15a_polar_orders_by_hour`](../outputs/figures/png/15a_polar_orders_by_hour.png), [`15b_polar_orders_by_weekday`](../outputs/figures/png/15b_polar_orders_by_weekday.png), [`15_polar_hour`](../outputs/interactive/15_polar_hour.html) | [Section 9](../apps/notebooks/final_visualizations.ipynb) | Orders by hour of the day and by weekday |

The interactive maps (`11_`, `12_` and `13_`) may need an internet connection to display completely; for an offline presentation use the static figures, as described in [`08-setup-and-run.md`](08-setup-and-run.md#10-running-the-notebook).
