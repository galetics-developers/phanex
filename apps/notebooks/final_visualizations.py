# # ECBD Olist Insights - Final visualizations
# 
# **Question:** How much does missing the promised delivery date cost Olist, and where does it happen?
# 
# **Data:** Olist Brazilian E-Commerce (Kaggle, CC BY-NC-SA 4.0), IBGE 2018 population, Brazil states GeoJSON (Code for America, MIT). Purchases from 2017-01-01 to 2018-08-31, values in R$.

# ## 1. Setup
# 
# Imports, fixed parameters and helper functions.

# STAGE 1: SETUP
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns

try:
    from ecbd_viz import export, palettes, plotly_template, style
except ImportError as error:
    raise ImportError("ecbd_viz is not installed: run pip install -r requirements.txt") from error

SEED = 42
np.random.seed(SEED)

# --- 1.1 Fixed analysis parameters ---
N_BOOT = 1000
CI_LEVEL = 0.95
MIN_ORDERS = 30
SAMPLE_SIZE = 5000
KDE_MAX_DAYS = 60
FREIGHT_RATIO_YMAX = 2.0
TOP_N_ACCENT = 3
TOP_N_MACRO = 4
GEO_RANK_N = 8
TOLERANCE = 0.001
CANCELED = "canceled"
BAND_LABELS = {
    1: "<= -10 (very early)",
    2: "-9 to -1 (early)",
    3: "0 to 3 (on time / slight)",
    4: "4 to 10 (late)",
    5: "> 10 (very late)",
}
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


# --- 1.2 Helpers ---
def print_banner(title):
    """Print a section banner."""
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def find_root(start):
    """Return the first folder at or above start with requirements.txt and packages/viz-kit."""
    for folder in [start, *start.parents]:
        if (folder / "requirements.txt").is_file() and (folder / "packages" / "viz-kit").is_dir():
            return folder
    raise FileNotFoundError(
        f"Repository root not found from {start}: open the notebook inside the repository."
    )


def require_file(path, hint):
    """Return path if it exists, else stop with a message that names the file and the fix."""
    if not path.is_file():
        raise FileNotFoundError(f"Required input file not found: {path}. {hint}")
    return path


# --- 1.3 Paths, style and data ---
ROOT = find_root(Path.cwd())
DATA_PATH = ROOT / "data" / "processed" / "analytics_flat.csv.gz"
GEOJSON_PATH = ROOT / "data" / "reference" / "brazil-states.geojson"
OUT_FIGURES = ROOT / "outputs" / "figures"
OUT_HTML = ROOT / "outputs" / "interactive"
KPI_REFERENCE = ROOT / "apps" / "bi-dashboard" / "validation" / "kpi_reference.csv"

style.apply()
plotly_template.register_template()

require_file(DATA_PATH, "Run python scripts/run_pipeline.py to generate data/processed/.")
require_file(GEOJSON_PATH, "Restore the GeoJSON of the Brazilian states in data/reference/.")

lines = pd.read_csv(
    DATA_PATH,
    compression="gzip",
    parse_dates=["purchase_date", "delivered_date", "estimated_date"],
    dtype={"customer_zip_prefix": "str"},
)
lines["customer_zip_prefix"] = lines["customer_zip_prefix"].str.zfill(5)
geojson = json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))

print_banner("1. Setup")
print(f"Repository root: {ROOT.name}")
print(f"Order lines loaded: {len(lines):,}")
print(f"GeoJSON features loaded: {len(geojson['features'])}")


# ## 2. Data profile and KPIs
# 
# Profile of the flat table, order-level table (one row per `order_id`) and the four headline KPIs: GMV, Orders, Late Rate % and Avg Review (canceled orders excluded, S0 filter).

# STAGE 2: DATA PROFILE
# --- 2.1 Shape, observed period, statistics and nulls ---
print_banner("2. Data profile")

print(f"Shape (rows, columns): {lines.shape}")
period = (lines["purchase_date"].min(), lines["purchase_date"].max())
print(f"Observed purchase period: {period[0]} -> {period[1]}")
print("\nDescriptive statistics of the numeric columns:")
print(lines.describe(include="number").T.round(3).to_string())
nulls = lines.isna().sum()
nulls = nulls[nulls > 0].sort_values(ascending=False)
print("\nNull values per column (only columns with nulls):")
print(nulls.to_string())


# --- 2.2 Order-level table ---
SUM_COLUMNS = ["price", "freight_value", "item_total", "weight_g", "volume_cm3"]
SINGLE_NUMERIC = [
    "payment_value_order", "installments", "review_score", "is_negative_review", "is_late",
    "delay_days", "delay_band_order", "delivery_days", "promised_days", "purchase_hour",
    "weekday_number", "customer_lat", "customer_lng",
]
SINGLE_OTHER = [
    "order_status", "delay_band", "purchase_date", "delivered_date", "estimated_date",
    "commercial_event", "customer_id", "customer_unique_id", "customer_zip_prefix",
    "customer_city", "uf", "state_name", "region",
]


def single_value_violations(df, columns):
    """Return, per column, how many orders have more than one non-null value."""
    counts = df.groupby("order_id", sort=True)[columns].nunique(dropna=True)
    return (counts > 1).sum()


def build_orders(df):
    """Return one row per order_id with the order-level aggregation rules (Def-2)."""
    grouped = df.groupby("order_id", sort=True)
    orders = grouped[SUM_COLUMNS].sum(min_count=1)
    orders["freight_ratio"] = orders["freight_value"] / orders["price"].where(orders["price"] > 0)
    orders["distance_km"] = grouped["distance_km"].max()
    orders = orders.join(grouped[SINGLE_NUMERIC].max()).join(grouped[SINGLE_OTHER].first())
    top_line = df.sort_values(
        ["order_id", "item_total", "order_item_id"], ascending=[True, False, True]
    ).drop_duplicates("order_id")
    orders["top_category_en"] = top_line.set_index("order_id")["category_en"]
    return orders.reset_index()


orders = build_orders(lines)
violations = single_value_violations(lines, SINGLE_NUMERIC + SINGLE_OTHER)
same_price = np.isclose(orders["price"].sum(), lines["price"].sum())
print(f"Order-level table rows: {len(orders):,}")
print(f"Distinct orders in the line table: {lines['order_id'].nunique():,}")
print(f"Single-value violations (orders with more than one value): {int(violations.sum())}")
print(f"Sum of order price equals sum of line price: {same_price}")


# --- 2.3 Headline KPIs and derived tables ---
def compute_kpis(df, order_table, canceled):
    """Return GMV, Freight, Orders, Late Rate % (fraction), Avg Review and Evaluated Orders."""
    commercial = df.loc[df["order_status"] != canceled]
    evaluated = int(order_table["is_late"].notna().sum())
    late = int((order_table["is_late"] == 1).sum())
    return {
        "GMV": float(commercial["price"].sum()),
        "Freight": float(commercial["freight_value"].sum()),
        "Orders": float(commercial["order_id"].nunique()),
        "Late Rate %": late / evaluated,
        "Avg Review": float(order_table["review_score"].mean()),
        "Evaluated Orders": float(evaluated),
    }


kpis = compute_kpis(lines, orders, CANCELED)
commercial_lines = lines.loc[lines["order_status"] != CANCELED]
commercial_orders = orders.loc[orders["order_status"] != CANCELED]
evaluated_orders = orders.loc[orders["is_late"].notna()]
reviewed_orders = orders.loc[orders["review_score"].notna()]

print(f"GMV (R$): {kpis['GMV']:,.2f}")
print(f"Orders: {kpis['Orders']:,.0f}")
print(f"Late Rate % (fraction): {kpis['Late Rate %']:.6f}")
print(f"Avg Review: {kpis['Avg Review']:.6f}")
print(f"\nCommercial lines (S0): {len(commercial_lines):,}")
print(f"Commercial orders (S0): {len(commercial_orders):,}")
print(f"Evaluated orders (is_late not null): {len(evaluated_orders):,}")
print(f"Reviewed orders: {len(reviewed_orders):,}")


# ## 3. Amounts
# 
# **01a - GMV by macro category.** Bars from 0, top three highlighted. Finding: GMV is concentrated in four macro categories, led by fashion and beauty and by home and furniture.
# 
# **01b - Late Rate % by state.** States with at least 30 evaluated orders; dashed line = national rate. Finding: the highest late rates are in the Northeast and in Rio de Janeiro.

# STAGE 3: AMOUNTS
# --- 3a GMV by macro category ---
print_banner("3. Amounts")


def rank_table(df, value, tiebreak):
    """Sort by value descending, then by the (column, ascending) tie-breaks."""
    columns = [value] + [name for name, _ in tiebreak]
    ascending = [False] + [asc for _, asc in tiebreak]
    return df.sort_values(columns, ascending=ascending, kind="mergesort").reset_index(drop=True)


def place_reference(ax, x, text):
    """Draw a dashed neutral reference line at x with a label at the top of the axes."""
    ax.axvline(x, color=palettes.REFERENCE, linestyle="--", linewidth=1.2)
    ax.text(
        x, 1.0, f" {text}", color=palettes.REFERENCE, va="top", transform=ax.get_xaxis_transform()
    )


gmv_macro = commercial_lines.groupby("macro_category", sort=True)["price"].sum()
gmv_macro = gmv_macro.reset_index(name="gmv")
gmv_macro = rank_table(gmv_macro, "gmv", [("macro_category", True)])
top_share = gmv_macro["gmv"].head(TOP_N_ACCENT).sum() / gmv_macro["gmv"].sum()

fig, ax = plt.subplots(figsize=(10, 5.5))
bars = ax.barh(
    gmv_macro["macro_category"], gmv_macro["gmv"],
    color=palettes.accent_colors(len(gmv_macro), TOP_N_ACCENT),
)
ax.bar_label(bars, labels=[f"R$ {v / 1e6:,.2f} M" for v in gmv_macro["gmv"]], padding=4)
ax.invert_yaxis()
ax.set_xlim(left=0, right=gmv_macro["gmv"].max() * 1.18)
ax.xaxis.set_major_formatter(style.brl_formatter())
ax.set(
    title=f"The top {TOP_N_ACCENT} macro categories make {top_share:.1%} of GMV",
    xlabel="GMV (R$, sum of item price, canceled orders excluded)",
    ylabel="Macro category",
)
export.save_fig(fig, "01a_amounts_gmv_by_macro_category", OUT_FIGURES)

print("GMV by macro category (ranking order):")
gmv_macro["share"] = gmv_macro["gmv"] / gmv_macro["gmv"].sum()
print(gmv_macro.round(4).to_string(index=False))
print(f"\nSum of bars (R$): {gmv_macro['gmv'].sum():,.2f}")
print(f"GMV KPI of section 2 (R$): {kpis['GMV']:,.2f}")
print(f"Sum of bars equals the GMV KPI: {bool(np.isclose(gmv_macro['gmv'].sum(), kpis['GMV']))}")
accented = gmv_macro["macro_category"].head(TOP_N_ACCENT).tolist()
print(f"Accented bars (top {TOP_N_ACCENT}): {accented}")
print(f"Share of GMV of the accented bars: {top_share:.4f}")


# --- 3b Late Rate % by state ---
def state_table(df, order_table, canceled):
    """Return one row per uf with orders, Late Rate %, avg delay and orders per 100k."""
    commercial = order_table.loc[order_table["order_status"] != canceled]
    evaluated = order_table.loc[order_table["is_late"].notna()]
    states = df.groupby("uf", sort=True).agg(
        state_name=("state_name", "first"),
        region=("region", "first"),
        orders_per_100k=("orders_per_100k", "first"),
    )
    states["orders"] = commercial.groupby("uf")["order_id"].nunique()
    states["evaluated_orders"] = evaluated.groupby("uf")["order_id"].nunique()
    states["late_rate"] = evaluated.groupby("uf")["is_late"].mean()
    states["avg_delay_days"] = evaluated.groupby("uf")["delay_days"].mean()
    counts = ["orders", "evaluated_orders"]
    states[counts] = states[counts].fillna(0).astype(int)
    return states.reset_index()


states = state_table(lines, orders, CANCELED)
late_states = states.loc[states["evaluated_orders"] >= MIN_ORDERS]
late_states = rank_table(
    late_states, "late_rate", [("evaluated_orders", False), ("state_name", True)]
)
excluded_states = states.loc[states["evaluated_orders"] < MIN_ORDERS]
national_late = kpis["Late Rate %"]

fig, ax = plt.subplots(figsize=(10, 8.5))
ax.barh(
    late_states["state_name"], late_states["late_rate"] * 100,
    color=palettes.accent_colors(len(late_states), TOP_N_ACCENT),
)
place_reference(ax, national_late * 100, f"National: {national_late:.1%}")
ax.invert_yaxis()
ax.set_xlim(left=0)
leader = late_states.iloc[0]
ax.set(
    title=(
        f"{leader['state_name']} breaks the delivery promise most often: "
        f"{leader['late_rate']:.1%} late"
    ),
    xlabel="Late Rate (% of evaluated orders delivered after the promised date)",
    ylabel="Customer state",
)
export.save_fig(fig, "01b_amounts_late_rate_by_state", OUT_FIGURES)

print("Late Rate % by state (ranking order, eligible states):")
state_columns = ["uf", "state_name", "region", "evaluated_orders", "late_rate"]
print(late_states[state_columns].round(4).to_string(index=False))
print(f"\nEligible states (>= {MIN_ORDERS} evaluated orders): {len(late_states)}")
print(f"States excluded by the minimum: {len(excluded_states)}")
if len(excluded_states):
    print(excluded_states[["uf", "state_name", "evaluated_orders"]].to_string(index=False))
print(f"Accented bars (top {TOP_N_ACCENT}): {late_states['uf'].head(TOP_N_ACCENT).tolist()}")
print(f"National Late Rate % (fraction): {national_late:.6f}")


# ## 4. Distributions
# 
# **02 - Item price (log scale).** Finding: most lines are low-priced, with a long right tail.
# 
# **03 - Delivery time by region.** Dashed line = average promised time. Finding: the Southeast delivers fastest; North and Northeast are slower and wider.
# 
# **04 - Review by delay band.** Notch = 95% CI of the median, diamond = mean with bootstrap 95% CI. Finding: reviews collapse once the order is late.
# 
# **04b - Freight ratio by region.** Axis cut at `FREIGHT_RATIO_YMAX`. Finding: North and Northeast pay a larger share of the order value in freight.

# STAGE 4: DISTRIBUTIONS
# --- 4.1 Histogram and KDE of the line price (log scale) ---
print_banner("4. Distributions")
REGIONS = sorted(orders["region"].dropna().unique())
REGION_COLORS = dict(zip(REGIONS, palettes.qualitative(len(REGIONS))))


def top_macros(df, n):
    """Return the n macro categories with the most distinct orders (ties by name)."""
    counts = df.groupby("macro_category", sort=True)["order_id"].nunique()
    counts = counts.reset_index(name="orders")
    return rank_table(counts, "orders", [("macro_category", True)]).head(n)


top_macro_table = top_macros(commercial_lines, TOP_N_MACRO)
top_macro_names = top_macro_table["macro_category"].tolist()
price_lines = commercial_lines.assign(
    price_group=commercial_lines["macro_category"].where(
        commercial_lines["macro_category"].isin(top_macro_names), "Other"
    )
)
price_palette = dict(zip(top_macro_names, palettes.qualitative(TOP_N_MACRO)))
price_palette["Other"] = palettes.MUTED
median_price = float(price_lines["price"].median())

fig, ax = plt.subplots(figsize=(11, 5.5))
sns.histplot(
    data=price_lines, x="price", hue="price_group", hue_order=[*top_macro_names, "Other"],
    palette=price_palette, log_scale=True, kde=True, element="step", fill=False, bins=60,
    linewidth=1, ax=ax,
)
place_reference(ax, median_price, f"Median of all lines: R$ {median_price:,.2f}")
ax.xaxis.set_major_formatter(style.brl_formatter())
ax.tick_params(axis="x", which="minor", labelbottom=False)
ax.set_ylim(bottom=0)
ax.get_legend().set_title("Macro category")
ax.set(
    title=f"Half of the order lines cost less than R$ {median_price:,.2f}",
    xlabel="Item price per order line (R$, log scale)",
    ylabel="Order lines",
)
export.save_fig(fig, "02_hist_price_log", OUT_FIGURES)

print(f"Top {TOP_N_MACRO} macro categories by distinct orders (S0):")
print(top_macro_table.to_string(index=False))
print(f"\nLines drawn (S0): {len(price_lines):,}")
print(f"Lines in 'Other': {int((price_lines['price_group'] == 'Other').sum()):,}")
print(f"Median price of all S0 lines (R$): {median_price:,.2f}")


# --- 4.2 KDE of the delivery time by region ---
delivered_orders = orders.loc[orders["delivery_days"].notna()]
avg_promised = float(delivered_orders["promised_days"].mean())
beyond_max = int((delivered_orders["delivery_days"] > KDE_MAX_DAYS).sum())

fig, ax = plt.subplots(figsize=(11, 5.5))
sns.kdeplot(
    data=delivered_orders, x="delivery_days", hue="region", hue_order=REGIONS,
    palette=REGION_COLORS, fill=True, common_norm=False, alpha=0.2, linewidth=1.5, ax=ax,
)
place_reference(ax, avg_promised, f"Average promised time: {avg_promised:.1f} days")
ax.set_xlim(0, KDE_MAX_DAYS)
ax.set_ylim(bottom=0)
ax.get_legend().set_title("Region")
ax.set(
    title="Orders arrive well before the promise, but the north waits longer",
    xlabel=f"Delivery time (days from purchase to delivery, drawn up to {KDE_MAX_DAYS})",
    ylabel="Density (each region normalized separately)",
)
export.save_fig(fig, "03_kde_delivery_by_region", OUT_FIGURES)

print(f"Orders with a valid delivery time: {len(delivered_orders):,}")
print(f"National average promised time (days): {avg_promised:.2f}")
print(f"Orders delivered after more than {KDE_MAX_DAYS} days (outside the drawing): {beyond_max:,}")
print("\nMedian delivery days by region:")
print(delivered_orders.groupby("region")["delivery_days"].median().to_string())


# --- 4.3 Box plot of the review score by delay band, with confidence intervals ---
band_orders = orders.loc[orders["delay_band_order"].notna()]
box_orders = band_orders.loc[band_orders["review_score"].notna()].assign(
    band_label=lambda df: df["delay_band_order"].map(BAND_LABELS)
)
band_order = [BAND_LABELS[key] for key in sorted(BAND_LABELS)]
band_means = box_orders.groupby("delay_band_order")["review_score"].agg(["count", "mean", "median"])
review_drop = band_means.loc[3, "mean"] - band_means.loc[5, "mean"]

fig, ax = plt.subplots(figsize=(11, 5.5))
sns.boxplot(
    data=box_orders, x="band_label", y="review_score", order=band_order, hue="band_label",
    hue_order=band_order, palette=palettes.sequential_colors(len(band_order)), legend=False,
    notch=True, showfliers=False, width=0.55, ax=ax,
)
sns.pointplot(
    data=box_orders, x="band_label", y="review_score", order=band_order, estimator="mean",
    errorbar=("ci", CI_LEVEL * 100), n_boot=N_BOOT, seed=SEED, color=palettes.REFERENCE,
    linestyle="none", markers="D", capsize=0.15, markersize=9, markeredgecolor=palettes.CANVAS,
    zorder=4, err_kws={"linewidth": 1.2, "zorder": 3}, ax=ax,
)
ax.set_ylim(0, 5.3)
ax.set(
    title=(
        f"Very late orders score {review_drop:.1f} points below the 0 to 3 days band\n"
        "Boxes: median with notch (95% CI); diamonds: mean with bootstrap 95% CI"
    ),
    xlabel="Delivery date vs promised date (delay band, days)",
    ylabel="Review score (1 to 5)",
)
export.save_fig(fig, "04_box_review_by_delay_ci", OUT_FIGURES)

print("Review score by delay band (orders with band and review):")
print(band_means.assign(label=[BAND_LABELS[k] for k in band_means.index]).round(4).to_string())
print(f"\nMean drop 0 to 3 days band (band 3) -> very late (band 5): {review_drop:.4f}")
print(f"Orders with a delay band: {len(band_orders):,}")
no_review = len(band_orders) - len(box_orders)
print(f"Orders with a delay band but without review (left out of the box plot): {no_review:,}")


# --- 4.4 Violin of the freight ratio by region ---
ratio_orders = commercial_orders.loc[commercial_orders["freight_ratio"].notna()]
above_ymax = int((ratio_orders["freight_ratio"] > FREIGHT_RATIO_YMAX).sum())
ratio_summary = ratio_orders.groupby("region")["freight_ratio"].describe()
ratio_summary = ratio_summary[["count", "min", "25%", "50%", "75%", "max"]]

fig, ax = plt.subplots(figsize=(11, 5.5))
sns.violinplot(
    data=ratio_orders, x="region", y="freight_ratio", order=REGIONS, hue="region",
    hue_order=REGIONS, palette=REGION_COLORS, legend=False, cut=0, inner="quart", linewidth=1,
    ax=ax,
)
ax.set_ylim(0, FREIGHT_RATIO_YMAX)
highest = ratio_summary["50%"].idxmax()
ax.set(
    title=(
        f"{highest} pays the most freight per real of product "
        f"(median {ratio_summary.loc[highest, '50%']:.2f})"
    ),
    xlabel="Customer region",
    ylabel=f"Freight ratio (order freight / order price, axis cut at {FREIGHT_RATIO_YMAX})",
)
export.save_fig(fig, "04b_violin_freight_ratio", OUT_FIGURES)

print(f"Orders drawn (S0, freight ratio not null): {len(ratio_orders):,}")
print(f"Orders above the visible range (freight ratio > {FREIGHT_RATIO_YMAX}): {above_ymax:,}")
print("\nFreight ratio by region (observed range and quartiles):")
print(ratio_summary.round(4).to_string())


# ## 5. Uncertainty
# 
# Bootstrap 95% confidence intervals (`N_BOOT` resamples, `SEED`).
# 
# **05 - Weekly average ticket.** Partial first and last weeks excluded. Finding: the ticket is stable; Black Friday 2017 adds orders, not value per order.
# 
# **06 - Late Rate % by region.** Finding: the Northeast is clearly above every other region; Centro-Oeste, Sudeste and Sul overlap.

# STAGE 5: UNCERTAINTY
# --- 5.1 Weekly average ticket with a bootstrap 95% CI band ---
print_banner("5. Uncertainty")


def bootstrap_mean_ci(values, n_boot, seed, level):
    """Return the mean and the percentile bootstrap CI of values (new generator per call)."""
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    for i in range(n_boot):
        means[i] = rng.choice(values, size=values.size, replace=True).mean()
    tail = (1 - level) / 2 * 100
    low, high = np.percentile(means, [tail, 100 - tail])
    return float(values.mean()), float(low), float(high)


def week_start(dates):
    """Return the Monday (normalized) of the ISO week of each date."""
    days = dates.dt.normalize()
    return days - pd.to_timedelta(days.dt.day_of_week, unit="D")


def partial_weeks(dates):
    """Return the week starts whose 7 days are not all covered by the observed dates (D38)."""
    first, last = dates.min().normalize(), dates.max().normalize()
    starts = pd.Series(week_start(dates).unique())
    partial = starts[(starts < first) | (starts + pd.Timedelta(days=6) > last)]
    return set(partial)


def iso_label(start):
    """Return the ISO week label (YYYY-Www) of a week start."""
    year, week, _ = start.isocalendar()
    return f"{year}-W{week:02d}"


excluded_weeks = partial_weeks(lines["purchase_date"])
ticket_orders = commercial_orders.assign(week=week_start(commercial_orders["purchase_date"]))
in_partial = ticket_orders["week"].isin(excluded_weeks)
kept_orders = ticket_orders.loc[~in_partial]
weekly = pd.DataFrame(
    [
        (week, *bootstrap_mean_ci(group["item_total"], N_BOOT, SEED, CI_LEVEL), len(group))
        for week, group in kept_orders.groupby("week", sort=True)
    ],
    columns=["week", "avg_ticket", "ci_low", "ci_high", "orders"],
)

week_lines = commercial_lines.assign(week=week_start(commercial_lines["purchase_date"]))
week_kpis = week_lines.groupby("week", sort=True).agg(
    gmv=("price", "sum"), freight=("freight_value", "sum"), orders=("order_id", "nunique")
)
avg_ticket_kpi = (week_kpis["gmv"] + week_kpis["freight"]) / week_kpis["orders"]
max_diff = float((weekly.set_index("week")["avg_ticket"] - avg_ticket_kpi).abs().max())

is_black_friday = (lines["commercial_event"] == "Black Friday") & (
    lines["purchase_date"].dt.year == 2017
)
bf_week = week_start(lines.loc[is_black_friday, "purchase_date"]).min()
bf_row = weekly.loc[weekly["week"] == bf_week].iloc[0]
median_ticket = float(weekly["avg_ticket"].median())
line_color = palettes.qualitative(1)[0]

fig, ax = plt.subplots(figsize=(12, 5.5))
ax.fill_between(
    weekly["week"], weekly["ci_low"], weekly["ci_high"], color=line_color, alpha=0.25,
    linewidth=0, label="Bootstrap 95% CI",
)
ax.plot(weekly["week"], weekly["avg_ticket"], color=line_color, linewidth=1.8,
        label="Average ticket per order")
ax.annotate(
    f"Black Friday 2017 week\n{bf_row['orders']:,} orders, R$ {bf_row['avg_ticket']:,.2f}",
    xy=(bf_week, bf_row["avg_ticket"]), xytext=(40, 70), textcoords="offset points",
    color=palettes.REFERENCE, arrowprops={"arrowstyle": "->", "color": palettes.REFERENCE},
)
ax.yaxis.set_major_formatter(style.brl_formatter())
ax.legend(loc="upper right")
ax.set(
    title=(
        f"The weekly average ticket moves around R$ {median_ticket:,.2f}; "
        f"the Black Friday 2017 week has {bf_row['orders'] / weekly['orders'].median():.1f}x "
        "the median orders"
    ),
    xlabel="ISO purchase week (Monday start; partial first and last weeks excluded)",
    ylabel="Average ticket per order (R$, price + freight)",
)
export.save_fig(fig, "05_ci_band_weekly_ticket", OUT_FIGURES)

excluded_table = (
    ticket_orders.loc[in_partial].groupby("week", sort=True).size().reset_index(name="orders")
)
excluded_table["iso_week"] = excluded_table["week"].map(iso_label)
print(f"Partial weeks excluded: {len(excluded_weeks)}")
print(excluded_table[["iso_week", "week", "orders"]].to_string(index=False))
print(f"Orders excluded with the partial weeks (S0): {int(in_partial.sum()):,}")
print(f"\nWeeks represented: {len(weekly)}")
print(f"Orders represented (S0): {int(weekly['orders'].sum()):,}")
print(f"Black Friday 2017 week (commercial_event): {iso_label(bf_week)}, from {bf_week.date()}")
print(f"Black Friday 2017 week excluded as partial: {bf_week in excluded_weeks}")
print(f"Median weekly average ticket (R$): {median_ticket:,.2f}")
print(f"Max abs diff weekly mean vs (GMV + Freight) / Orders: {max_diff:.3e}")
print(f"Max abs diff <= 1e-9: {max_diff <= 1e-9}")
print("\nWeekly average ticket with bootstrap 95% CI (R$):")
weekly_print = weekly.assign(iso_week=weekly["week"].map(iso_label))
print(weekly_print[["iso_week", "orders", "avg_ticket", "ci_low", "ci_high"]].round(4).to_string(
    index=False
))


# --- 5.2 Late Rate % by region with bootstrap 95% CI error bars ---
region_ci = pd.DataFrame(
    [
        (region, *bootstrap_mean_ci(group["is_late"], N_BOOT, SEED, CI_LEVEL), len(group))
        for region, group in evaluated_orders.groupby("region", sort=True)
    ],
    columns=["region", "late_rate", "ci_low", "ci_high", "evaluated_orders"],
)
region_ci = rank_table(region_ci, "late_rate", [("region", True)])
late_counts = evaluated_orders.loc[evaluated_orders["is_late"] == 1].groupby("region").size()
direct_rate = late_counts / evaluated_orders.groupby("region").size()
direct_rate = direct_rate[region_ci["region"]].to_numpy()
bars_match = bool(np.allclose(region_ci["late_rate"].to_numpy(), direct_rate))

fig, ax = plt.subplots(figsize=(10, 5.5))
heights = region_ci["late_rate"] * 100
errors = [heights - region_ci["ci_low"] * 100, region_ci["ci_high"] * 100 - heights]
bars = ax.bar(
    region_ci["region"], heights, yerr=errors, capsize=8,
    color=[REGION_COLORS[region] for region in region_ci["region"]],
    error_kw={"ecolor": palettes.REFERENCE, "elinewidth": 1.2},
)
for bar, value in zip(bars, region_ci["late_rate"]):
    ax.text(bar.get_x() + bar.get_width() / 2, 0.3, f"{value:.1%}", ha="center", va="bottom")
ax.axhline(national_late * 100, color=palettes.REFERENCE, linestyle="--", linewidth=1.2,
           label=f"National: {national_late:.1%}")
ax.set_ylim(bottom=0, top=(region_ci["ci_high"].max() * 100) * 1.2)
ax.legend(loc="upper right")
leader = region_ci.iloc[0]
ax.set(
    title=(
        f"{leader['region']} has the highest Late Rate % ({leader['late_rate']:.1%}); "
        "error bars: bootstrap 95% CI"
    ),
    xlabel="Customer region",
    ylabel="Late Rate (% of evaluated orders)",
)
export.save_fig(fig, "06_errorbars_late_rate_region", OUT_FIGURES)

print("Late Rate % by region with bootstrap 95% CI (fractions):")
print(region_ci.round(6).to_string(index=False))
print(f"\nBar height equals the direct Late Rate % of each region: {bars_match}")
print(f"National Late Rate % (fraction): {national_late:.6f}")


# ## 6. Relationships and correlation
# 
# **07a / 07b - Correlation heatmaps (Pearson and Spearman).** RdBu centered at 0. Finding: the review depends on delivery time and delay, not on price or freight.
# 
# **08 / 08s - Distance vs freight.** Random sample of 5,000 orders, so its rho can differ slightly from the value over all orders printed in section 10. Finding: freight rises with distance, with a wide spread.
# 
# **09 / 09s - Delay vs review by category.** Bubble area = GMV; categories with at least 30 orders. Finding: low reviews belong to specific categories, not to the average delay.

# STAGE 6: RELATIONSHIPS AND CORRELATION
# --- 6.1 Correlation heatmaps (Pearson and Spearman) ---
print_banner("6. Relationships and correlation")
CORR_COLUMNS = [
    "price", "freight_value", "freight_ratio", "weight_g", "volume_cm3", "distance_km",
    "promised_days", "delivery_days", "delay_days", "installments", "review_score",
]


def strongest_pair(corr):
    """Return the (row, column, value) of the largest absolute off-diagonal coefficient."""
    lower = corr.where(np.tril(np.ones_like(corr, dtype=bool), k=-1)).stack()
    row, column = lower.abs().idxmax()
    return row, column, float(lower[(row, column)])


def draw_corr(corr, coefficient):
    """Draw the lower triangle of corr with a fixed -1..1 diverging scale centered at 0."""
    fig, ax = plt.subplots(figsize=(10, 8.5))
    sns.heatmap(
        corr, mask=np.triu(np.ones_like(corr, dtype=bool), k=1), cmap=palettes.DIVERGING,
        vmin=-1, vmax=1, center=0, annot=True, fmt=".2f", square=True,
        cbar_kws={"label": coefficient, "shrink": 0.8}, ax=ax,
    )
    row, column, value = strongest_pair(corr)
    ax.set(
        title=f"{coefficient}: the strongest pair is {row} vs {column} ({value:.2f})",
        xlabel="Order-level variable",
        ylabel="Order-level variable",
    )
    return fig


corr_orders = commercial_orders[CORR_COLUMNS]
pearson = corr_orders.corr(method="pearson")
spearman = corr_orders.corr(method="spearman")

fig = draw_corr(pearson, "Pearson r")
export.save_fig(fig, "07a_corr_heatmap_pearson", OUT_FIGURES)
fig = draw_corr(spearman, "Spearman rho")
export.save_fig(fig, "07b_corr_heatmap_spearman", OUT_FIGURES)

print(f"Orders used (S0): {len(corr_orders):,}")
missing_distance = int(corr_orders["distance_km"].isna().sum())
print(f"Orders without distance_km (left out of its pairs): {missing_distance:,}")
print(f"Orders without delivery_days: {int(corr_orders['delivery_days'].isna().sum()):,}")
print(f"Orders without review_score: {int(corr_orders['review_score'].isna().sum()):,}")
print("\nPearson r:")
print(pearson.round(2).to_string())
print("\nSpearman rho:")
print(spearman.round(2).to_string())
print(f"\nSpearman rho distance vs freight: {spearman.loc['distance_km', 'freight_value']:.2f}")
print(f"Spearman rho delay_days vs review_score: {spearman.loc['delay_days', 'review_score']:.2f}")


# --- 6.2 Distance vs freight (interactive scatter) ---
scatter_pool = commercial_orders.dropna(subset=["distance_km", "freight_value"])
scatter_sample = scatter_pool.sample(n=SAMPLE_SIZE, random_state=SEED)
sample_rho = scatter_sample[["distance_km", "freight_value"]].corr(method="spearman").iloc[0, 1]
scatter_title = (
    f"Freight grows with distance (Spearman rho {sample_rho:.2f} "
    f"in a random sample of {SAMPLE_SIZE:,} orders)"
)
scatter_labels = {
    "distance_km": "Seller-customer distance (km)",
    "freight_value": "Order freight (R$)",
    "region": "Region",
    "top_category_en": "Top line category",
    "state_name": "Customer state",
    "delivery_days": "Delivery days",
}

scatter_fig = px.scatter(
    scatter_sample, x="distance_km", y="freight_value", color="region",
    category_orders={"region": REGIONS}, color_discrete_map=REGION_COLORS, opacity=0.6,
    hover_data={"top_category_en": True, "state_name": True, "delivery_days": True},
    labels=scatter_labels, title=scatter_title,
)
scatter_fig.update_traces(marker={"size": 5})
scatter_fig.update_xaxes(rangemode="tozero")
scatter_fig.update_yaxes(rangemode="tozero")
export.save_html(scatter_fig, "08_scatter_distance_freight", OUT_HTML)

print(f"Orders available (S0 with distance and freight): {len(scatter_pool):,}")
print(f"Sample size: {len(scatter_sample):,} (random_state={SEED})")
print(f"Spearman rho distance vs freight in the sample: {sample_rho:.4f}")
print("Sample orders by region:")
print(scatter_sample["region"].value_counts().sort_index().to_string())
scatter_fig


# --- 6.2 Distance vs freight (static version, same sample) ---
fig, ax = plt.subplots(figsize=(11, 6))
for region in REGIONS:
    subset = scatter_sample.loc[scatter_sample["region"] == region]
    ax.scatter(
        subset["distance_km"], subset["freight_value"], s=8, alpha=0.5,
        color=REGION_COLORS[region], label=region, linewidths=0,
    )
ax.set_xlim(left=0)
ax.set_ylim(bottom=0)
ax.yaxis.set_major_formatter(style.brl_formatter())
ax.legend(title="Region", markerscale=2)
ax.set(
    title=scatter_title,
    xlabel=scatter_labels["distance_km"],
    ylabel=scatter_labels["freight_value"],
)
export.save_fig(fig, "08s_scatter_distance_freight", OUT_FIGURES)

print(f"Points drawn: {len(scatter_sample):,}")
print(f"Largest freight in the sample (R$): {scatter_sample['freight_value'].max():,.2f}")
print(f"Largest distance in the sample (km): {scatter_sample['distance_km'].max():,.1f}")


# --- 6.3 Delay vs review by category (interactive bubbles) ---
def category_table(df, order_table, canceled, min_orders):
    """Return the categories with at least min_orders S0 orders and the excluded ones."""
    commercial = df.loc[df["order_status"] != canceled]
    cats = commercial.groupby("category_en", sort=True).agg(
        macro_category=("macro_category", "first"),
        gmv=("price", "sum"),
        orders=("order_id", "nunique"),
    )
    pairs = df[["category_en", "order_id"]].drop_duplicates().merge(
        order_table[["order_id", "delay_days", "review_score"]], on="order_id", how="left"
    )
    by_category = pairs.groupby("category_en", sort=True)
    cats["avg_delay_days"] = by_category["delay_days"].mean()
    cats["avg_review"] = by_category["review_score"].mean()
    cats = cats.reset_index()
    keep = cats["orders"] >= min_orders
    return cats.loc[keep].reset_index(drop=True), cats.loc[~keep].reset_index(drop=True)


categories, small_categories = category_table(lines, orders, CANCELED, MIN_ORDERS)
MACROS = sorted(lines["macro_category"].dropna().unique())
named_macros = [name for name in MACROS if name != "uncategorized"]
MACRO_COLORS = dict(zip(named_macros, palettes.qualitative(len(named_macros))))
MACRO_COLORS["uncategorized"] = palettes.MUTED
national_review = kpis["Avg Review"]
category_rho = categories[["avg_delay_days", "avg_review"]].corr(method="spearman").iloc[0, 1]
worst = categories.loc[categories["avg_review"].idxmin()]
bubble_title = (
    f"Lowest review: {worst['category_en']} ({worst['avg_review']:.2f}); delay vs review "
    f"across {len(categories)} categories: Spearman rho {category_rho:.2f}"
)
bubble_labels = {
    "avg_delay_days": "Average delay per order (days, negative = early)",
    "avg_review": "Average review per order (1 to 5)",
    "macro_category": "Macro category",
    "category_en": "Category",
    "gmv": "GMV (R$)",
    "orders": "Orders",
}

bubble_fig = px.scatter(
    categories, x="avg_delay_days", y="avg_review", size="gmv", color="macro_category",
    category_orders={"macro_category": MACROS}, color_discrete_map=MACRO_COLORS,
    hover_name="category_en", hover_data={"gmv": ":,.2f", "orders": ":,"}, size_max=45,
    labels=bubble_labels, title=bubble_title,
)
bubble_fig.add_hline(
    y=national_review, line_dash="dash", line_color=palettes.REFERENCE,
    annotation_text=f"National Avg Review: {national_review:.2f}",
    annotation_position="bottom right",
)
export.save_html(bubble_fig, "09_bubble_category_delay_review", OUT_HTML)

print(f"Categories shown (>= {MIN_ORDERS} orders): {len(categories)}")
print(f"Categories excluded by the minimum: {len(small_categories)}")
print(f"GMV excluded with them (R$): {small_categories['gmv'].sum():,.2f}")
gmv_total = categories["gmv"].sum() + small_categories["gmv"].sum()
print(f"GMV shown + excluded equals the GMV KPI: {bool(np.isclose(gmv_total, kpis['GMV']))}")
print(small_categories[["category_en", "orders", "gmv"]].to_string(index=False))
print(f"\nSpearman rho across categories (delay vs review): {category_rho:.4f}")
print("\nCategories shown, lowest average review first:")
bubble_columns = ["category_en", "macro_category", "orders", "gmv", "avg_delay_days", "avg_review"]
print(categories.sort_values("avg_review")[bubble_columns].round(3).to_string(index=False))
bubble_fig


# --- 6.3 Delay vs review by category (static version, same data) ---
size_scale = 1500 / categories["gmv"].max()
fig, ax = plt.subplots(figsize=(12, 7))
for macro in MACROS:
    subset = categories.loc[categories["macro_category"] == macro]
    if subset.empty:
        continue
    ax.scatter(
        subset["avg_delay_days"], subset["avg_review"], s=subset["gmv"] * size_scale,
        color=MACRO_COLORS[macro], alpha=0.7, edgecolors=palettes.CANVAS, linewidths=0.8,
        label=macro,
    )
ax.axhline(national_review, color=palettes.REFERENCE, linestyle="--", linewidth=1.2)
ax.text(
    1.0, national_review, f"National Avg Review: {national_review:.2f} ", color=palettes.REFERENCE,
    ha="right", va="bottom", transform=ax.get_yaxis_transform(),
)
for _, row in categories.nsmallest(3, "avg_review").iterrows():
    ax.annotate(
        row["category_en"], xy=(row["avg_delay_days"], row["avg_review"]), xytext=(6, -10),
        textcoords="offset points", color=palettes.TEXT,
    )
color_legend = ax.legend(
    title="Macro category", loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False
)
for handle in color_legend.legend_handles:
    handle.set_sizes([60])
ax.add_artist(color_legend).set_clip_on(False)
reference_gmv = [1e5, 5e5, 1e6]
size_handles = [
    ax.scatter([], [], s=value * size_scale, color=palettes.MUTED, label=f"R$ {value / 1e6:.1f} M")
    for value in reference_gmv
]
ax.legend(
    handles=size_handles, title="GMV (bubble area)", loc="lower left", bbox_to_anchor=(1.01, 0.0),
    labelspacing=2.8, borderpad=1.2, handletextpad=1.6, frameon=False,
)
ax.set(
    title=bubble_title,
    xlabel=bubble_labels["avg_delay_days"],
    ylabel=bubble_labels["avg_review"],
)
export.save_fig(fig, "09s_bubble_category_delay_review", OUT_FIGURES)

print(f"Bubbles drawn: {len(categories)}")
print(f"Largest category by GMV: {categories.loc[categories['gmv'].idxmax(), 'category_en']}")
print("Annotated categories (lowest average review):")
lowest = categories.nsmallest(3, "avg_review")[["category_en", "avg_review"]]
print(lowest.round(3).to_string(index=False))


# ## 7. Proportions
# 
# **10 - GMV treemap (macro category -> category).** Color = average review, RdBu centered at the national Avg Review (a review has no meaningful zero). Finding: home and furniture is a large block below the national review.

# STAGE 7: PROPORTIONS
print_banner("7. Proportions")
treemap_labels = {
    "macro_category": "Macro category",
    "category_en": "Category",
    "gmv": "GMV (R$)",
    "avg_review": "Average review per order",
    "orders": "Orders",
}
drawn_gmv = float(categories["gmv"].sum())
excluded_gmv = float(small_categories["gmv"].sum())
top_macro = categories.groupby("macro_category")["gmv"].sum().idxmax()
treemap_title = (
    f"GMV by macro category -> category ({len(categories)} categories with >= "
    f"{MIN_ORDERS} orders); color: average review vs the national {national_review:.2f}"
)

treemap_fig = px.treemap(
    categories, path=["macro_category", "category_en"], values="gmv", color="avg_review",
    color_continuous_scale=palettes.DIVERGING, color_continuous_midpoint=national_review,
    hover_data={"orders": ":,", "avg_review": ":.2f"}, labels=treemap_labels,
    title=treemap_title,
)
treemap_fig.update_traces(
    hovertemplate=(
        "%{id}<br>GMV (R$): %{value:,.2f}<br>Average review: %{color:.2f}<extra></extra>"
    )
)
treemap_fig.update_layout(margin={"t": 60, "l": 10, "r": 10, "b": 10})
export.save_html(treemap_fig, "10_treemap_gmv", OUT_HTML)

print(f"Categories drawn (>= {MIN_ORDERS} orders): {len(categories)}")
print(f"Categories excluded by the minimum: {len(small_categories)}")
print(f"GMV drawn (R$): {drawn_gmv:,.2f}")
print(f"GMV excluded (R$): {excluded_gmv:,.2f}")
print(f"GMV drawn + excluded (R$): {drawn_gmv + excluded_gmv:,.2f}")
print(f"GMV KPI of section 2 (R$): {kpis['GMV']:,.2f}")
gmv_matches = bool(np.isclose(drawn_gmv + excluded_gmv, kpis["GMV"]))
print(f"Drawn + excluded equals the GMV KPI: {gmv_matches}")
print(f"Color midpoint (national Avg Review): {national_review:.6f}")
print(f"Macro category with the largest GMV: {top_macro}")
macro_view = categories.assign(weighted=categories["avg_review"] * categories["gmv"])
macro_view = macro_view.groupby("macro_category", sort=True)[["gmv", "weighted"]].sum()
macro_view["avg_review_weighted"] = macro_view["weighted"] / macro_view["gmv"]
macro_view["gmv_share"] = macro_view["gmv"] / drawn_gmv
print("\nMacro categories (GMV-weighted average review, as colored by Plotly):")
print(macro_view[["gmv", "gmv_share", "avg_review_weighted"]].round(4).to_string())
below = categories.loc[categories["avg_review"] < national_review]
print(f"\nCategories below the national review: {len(below)} of {len(categories)}")
print(f"Share of drawn GMV below the national review: {below['gmv'].sum() / drawn_gmv:.4f}")
treemap_fig


# ## 8. Geospatial
# 
# States with at least 30 orders. All maps draw state outlines from the embedded GeoJSON and work offline.
# 
# **11 - Orders per 100k inhabitants.** Finding: the market is most developed in the Southeast, the South and the Distrito Federal.
# 
# **12 - Average delay by state.** RdBu centered at 0 (0 = promised date). Finding: no state is late on average; the Northeast is closest to the promise.
# 
# **13 - Point density of customer orders.** Orders grouped in 0.5 degree cells, color = orders (log scale). Finding: orders concentrate in the Southeast and along the coast.
# 
# **14 - Late Rate % ranking.** Eight worst and eight best states. Finding: the worst block is mostly northeastern.

# STAGE 8: GEOSPATIAL
# --- 8.1 Choropleth of orders per 100k inhabitants ---
print_banner("8. Geospatial")

geo_labels = {
    "uf": "State code",
    "state_name": "State",
    "orders_per_100k": "Orders per 100k inhabitants",
    "orders": "Orders",
    "evaluated_orders": "Evaluated orders",
    "late_rate_pct": "Late Rate (%)",
    "avg_delay_days": "Average delay per order (days)",
}
geo_states = states.assign(late_rate_pct=states["late_rate"] * 100)
market_states = geo_states.loc[geo_states["orders"] >= MIN_ORDERS]
market_leader = market_states.loc[market_states["orders_per_100k"].idxmax()]
geojson_codes = {feature["properties"]["sigla"] for feature in geojson["features"]}

orders_map = px.choropleth(
    market_states, geojson=geojson, locations="uf", featureidkey="properties.sigla",
    color="orders_per_100k", color_continuous_scale=palettes.SEQUENTIAL,
    hover_name="state_name", hover_data={"uf": False, "orders": ":,", "orders_per_100k": ":.1f"},
    labels=geo_labels,
    title=(
        f"Orders per 100k inhabitants: {market_leader['state_name']} leads with "
        f"{market_leader['orders_per_100k']:,.1f}"
    ),
)
orders_map.update_geos(fitbounds="locations", visible=False)
orders_map.update_layout(margin={"t": 60, "l": 10, "r": 10, "b": 10})
export.save_html(orders_map, "11_choropleth_orders_per_100k", OUT_HTML)

print(f"States represented (>= {MIN_ORDERS} orders): {len(market_states)}")
print(f"States excluded by the minimum: {int((geo_states['orders'] < MIN_ORDERS).sum())}")
print(f"States without a GeoJSON polygon: {sorted(set(market_states['uf']) - geojson_codes)}")
geo_layout = orders_map.layout.geo
print(f"Geo fitbounds: {geo_layout.fitbounds}, base map visible: {geo_layout.visible}")
print("\nOrders per 100k inhabitants by state (highest first):")
print(
    market_states.sort_values("orders_per_100k", ascending=False)[
        ["uf", "state_name", "orders", "orders_per_100k"]
    ].round(2).to_string(index=False)
)
orders_map


# --- 8.2 Choropleth of the average delay per order ---
delay_states = geo_states.loc[geo_states["evaluated_orders"] >= MIN_ORDERS]
closest = delay_states.loc[delay_states["avg_delay_days"].idxmax()]
delay_map = px.choropleth(
    delay_states, geojson=geojson, locations="uf", featureidkey="properties.sigla",
    color="avg_delay_days", color_continuous_scale=palettes.DIVERGING_R,
    color_continuous_midpoint=0, hover_name="state_name",
    hover_data={
        "uf": False, "avg_delay_days": ":.2f", "late_rate_pct": ":.2f", "orders": ":,",
        "evaluated_orders": ":,",
    },
    labels=geo_labels,
    title=(
        f"Average delay per order (days, negative = early): closest to the promise is "
        f"{closest['state_name']} ({closest['avg_delay_days']:.1f} days)"
    ),
)
delay_map.update_geos(fitbounds="locations", visible=False)
delay_map.update_layout(margin={"t": 60, "l": 10, "r": 10, "b": 10})
export.save_html(delay_map, "12_choropleth_delay", OUT_HTML)

print(f"States represented (>= {MIN_ORDERS} evaluated orders): {len(delay_states)}")
excluded_delay = int((geo_states["evaluated_orders"] < MIN_ORDERS).sum())
print(f"States excluded by the minimum: {excluded_delay}")
late_on_average = int((delay_states["avg_delay_days"] > 0).sum())
print(f"States with a positive average delay (late on average): {late_on_average}")
print(f"Color midpoint: {delay_map.layout.coloraxis.cmid}")
print("\nAverage delay per order by state (closest to the promise first):")
print(
    delay_states.sort_values("avg_delay_days", ascending=False)[
        ["uf", "state_name", "evaluated_orders", "avg_delay_days", "late_rate"]
    ].round(4).to_string(index=False)
)
delay_map


# --- 8.3 Point density map of customer orders ---
BRAZIL_LAT = (-34.5, 6.0)
BRAZIL_LON = (-75.0, -33.0)
GRID_STEP = 0.5
POINT_SIZE = 7
located = commercial_orders.dropna(subset=["customer_lat", "customer_lng"])
no_coordinates = len(commercial_orders) - len(located)

# Orders grouped in a grid of GRID_STEP degrees (cell center), so the map stays light
cells = (
    located.assign(
        cell_lat=(np.floor(located["customer_lat"] / GRID_STEP) + 0.5) * GRID_STEP,
        cell_lng=(np.floor(located["customer_lng"] / GRID_STEP) + 0.5) * GRID_STEP,
    )
    .groupby(["cell_lat", "cell_lng"], as_index=False)
    .agg(orders=("order_id", "size"), uf=("uf", lambda s: s.mode().iloc[0]))
    .sort_values(["orders", "cell_lat", "cell_lng"])
)
cells["log_orders"] = np.log10(cells["orders"])
max_log = float(cells["log_orders"].max())
tick_values = list(range(int(np.floor(max_log)) + 1))
tick_labels = [f"{10 ** power:,}" for power in tick_values]

# State borders from the GeoJSON (embedded, works offline) under the cells
all_codes = sorted(geojson_codes)
density_map = go.Figure()
density_map.add_trace(go.Choropleth(
    geojson=geojson, locations=all_codes, featureidkey="properties.sigla",
    z=[0] * len(all_codes), colorscale=[[0, palettes.CANVAS], [1, palettes.CANVAS]],
    showscale=False, marker_line_color=palettes.REFERENCE, marker_line_width=1.2,
    hoverinfo="skip",
))
density_map.add_trace(go.Scattergeo(
    lat=cells["cell_lat"], lon=cells["cell_lng"], mode="markers",
    marker={
        "size": POINT_SIZE, "symbol": "square", "opacity": 0.9,
        "color": cells["log_orders"], "colorscale": palettes.SEQUENTIAL,
        "cmin": 0, "cmax": max_log,
        "colorbar": {
            "title": {"text": "Orders per cell (log scale)"},
            "tickvals": tick_values, "ticktext": tick_labels,
        },
    },
    customdata=cells[["uf", "orders"]],
    hovertemplate="State: %{customdata[0]}<br>Orders: %{customdata[1]:,}<extra></extra>",
))
density_map.update_geos(
    visible=False, projection_type="mercator",
    lataxis_range=list(BRAZIL_LAT), lonaxis_range=list(BRAZIL_LON),
)
density_map.update_layout(
    title=(
        f"Customer orders by location ({len(located):,} orders in "
        f"{len(cells):,} cells of {GRID_STEP} degrees)"
    ),
    height=750, margin={"t": 60, "l": 10, "r": 10, "b": 10}, showlegend=False,
)
export.save_html(density_map, "13_density_customers", OUT_HTML)

print(f"Orders (S0): {len(commercial_orders):,}")
print(f"Orders drawn (with coordinates): {len(located):,}")
print(f"Orders left out without coordinates: {no_coordinates:,}")
print(f"Grid cells drawn ({GRID_STEP} degrees): {len(cells):,}")
print(f"Orders drawn equal located orders: {int(cells['orders'].sum()) == len(located)}")
print(f"Largest cell: {int(cells['orders'].max()):,} orders ({cells.iloc[-1]['uf']})")
print("\nOrders drawn by customer region:")
print(located["region"].value_counts().sort_index().to_string())
density_map


# --- 8.4 Geographic ranking: highest and lowest Late Rate % ---
def geo_rank(table, n):
    """Return the n highest and n lowest Late Rate % states (ranking tie-break), no repeats."""
    tiebreak = [("evaluated_orders", False), ("state_name", True)]
    top = rank_table(table, "late_rate", tiebreak).head(n).assign(block="highest")
    low = table.sort_values(
        ["late_rate", "evaluated_orders", "state_name"], ascending=[True, False, True],
        kind="mergesort",
    ).head(n)
    low = low.loc[~low["uf"].isin(top["uf"])].assign(block="lowest")
    low = low.iloc[::-1]
    return pd.concat([top, low], ignore_index=True)


LABEL_CLEARANCE = 1.5
ranked = geo_rank(late_states, GEO_RANK_N)
n_top = int((ranked["block"] == "highest").sum())
positions = np.arange(len(ranked)) + np.where(ranked["block"] == "lowest", 1, 0)
bar_colors = np.where(ranked["block"] == "highest", palettes.HIGHLIGHT, palettes.MUTED)

fig, ax = plt.subplots(figsize=(10, 8.5))
bars = ax.barh(positions, ranked["late_rate"] * 100, color=bar_colors)
# Labels that would cross the national line go inside the bar end
rate_labels = [f"{v:.1%}" for v in ranked["late_rate"]]
inside = (ranked["late_rate"] < national_late) & (
    ranked["late_rate"] * 100 + LABEL_CLEARANCE > national_late * 100
)
ax.bar_label(bars, labels=["" if f else t for f, t in zip(inside, rate_labels)], padding=4)
for position, value, text, flag in zip(positions, ranked["late_rate"], rate_labels, inside):
    if flag:
        ax.text(value * 100 - 0.15, position, text, ha="right", va="center")
ax.set_yticks(positions, labels=ranked["state_name"])
place_reference(ax, national_late * 100, f"National: {national_late:.1%}")
ax.invert_yaxis()
ax.set_xlim(left=0, right=ranked["late_rate"].max() * 100 * 1.15)
ax.legend(
    handles=[
        plt.Rectangle((0, 0), 1, 1, color=palettes.HIGHLIGHT),
        plt.Rectangle((0, 0), 1, 1, color=palettes.MUTED),
    ],
    labels=[f"Highest {n_top} Late Rate %", f"Lowest {len(ranked) - n_top} Late Rate %"],
    loc="lower right",
)
worst, best = ranked.iloc[0], ranked.iloc[-1]
ax.set(
    title=(
        f"Late Rate % goes from {best['late_rate']:.1%} ({best['state_name']}) "
        f"to {worst['late_rate']:.1%} ({worst['state_name']})"
    ),
    xlabel="Late Rate (% of evaluated orders delivered after the promised date)",
    ylabel="Customer state",
)
export.save_fig(fig, "14_geo_rank_states", OUT_FIGURES)

print(f"Eligible states (>= {MIN_ORDERS} evaluated orders): {len(late_states)}")
print(f"States shown: {len(ranked)} (highest {n_top}, lowest {len(ranked) - n_top})")
print(f"Distinct states shown: {ranked['uf'].nunique()}")
print(f"Repeated states: {int(ranked['uf'].duplicated().sum())}")
rank_columns = ["block", "uf", "state_name", "evaluated_orders", "late_rate"]
print(ranked[rank_columns].round(4).to_string(index=False))


# ## 9. Polar coordinates
# 
# **15 / 15a / 15b - Orders by hour and by weekday.** Finding: orders peak in the afternoon and at the start of the week.

# STAGE 9: POLAR COORDINATES
# --- 9a Orders by hour of the day (interactive) ---
print_banner("9. Polar coordinates")

orders_by_hour = commercial_orders.groupby("purchase_hour")["order_id"].nunique()
orders_by_hour = orders_by_hour.reindex(range(24), fill_value=0)
weekday_names = lines.groupby("weekday_number", sort=True)["weekday_name"].first()
orders_by_weekday = (
    commercial_orders.groupby("weekday_number")["order_id"].nunique().reindex(weekday_names.index)
)
hour_labels = [f"{hour:02d}h" for hour in orders_by_hour.index]
peak_hour = int(orders_by_hour.idxmax())
radial_max = float(orders_by_hour.max()) * 1.05

polar_fig = go.Figure(
    go.Barpolar(
        r=orders_by_hour.to_numpy(), theta=hour_labels,
        marker={
            "color": orders_by_hour.to_numpy(), "colorscale": palettes.SEQUENTIAL,
            "colorbar": {"title": {"text": "Orders"}}, "line": {"color": palettes.CANVAS},
        },
        hovertemplate="%{theta}: %{r:,} orders<extra></extra>",
    )
)
polar_fig.update_layout(
    title=f"Orders by purchase hour (distinct orders, S0); peak at {peak_hour:02d}h",
    polar={
        "radialaxis": {"range": [0, radial_max], "title": {"text": "Orders"}},
        "angularaxis": {"direction": "clockwise", "rotation": 90},
    },
)
export.save_html(polar_fig, "15_polar_hour", OUT_HTML)

print(f"Orders counted (distinct S0 orders): {int(orders_by_hour.sum()):,}")
print(f"Orders S0 of section 2: {kpis['Orders']:,.0f}")
print(f"Radial axis range: {list(polar_fig.layout.polar.radialaxis.range)}")
print(f"Peak hour: {peak_hour:02d}h with {int(orders_by_hour.max()):,} orders")
quiet_hour = int(orders_by_hour.idxmin())
print(f"Quietest hour: {quiet_hour:02d}h with {int(orders_by_hour.min()):,} orders")
print("\nOrders by hour:")
print(orders_by_hour.to_string())
polar_fig


# --- 9b Orders by hour and by weekday (static polar bars) ---
def polar_bars(counts, labels, title):
    """Draw counts as clockwise polar bars from the top, Viridis color and radius from 0."""
    angles = np.linspace(0, 2 * np.pi, len(counts), endpoint=False)
    norm = matplotlib.colors.Normalize(0, counts.max())
    cmap = matplotlib.colormaps[palettes.SEQUENTIAL]
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"projection": "polar"})
    ax.bar(
        angles, counts.to_numpy(), width=2 * np.pi / len(counts), bottom=0,
        color=cmap(norm(counts.to_numpy())), edgecolor=palettes.CANVAS, linewidth=1,
    )
    ax.set_theta_direction(-1)
    ax.set_theta_offset(np.pi / 2)
    ax.set_ylim(0, counts.max() * 1.05)
    ax.set_xticks(angles, labels=labels)
    ax.tick_params(axis="x", pad=8)
    # Radial labels on the edge between the shortest bar and its shorter neighbor
    values = counts.to_numpy()
    low = int(np.argmin(values))
    step = 1 if values[(low + 1) % len(values)] <= values[low - 1] else -1
    ax.set_rlabel_position(np.degrees(angles[low] + step * np.pi / len(values)))
    thousands = matplotlib.ticker.StrMethodFormatter("{x:,.0f}")
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4))
    ax.yaxis.set_major_formatter(thousands)
    colorbar = fig.colorbar(
        matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, shrink=0.7, pad=0.1
    )
    colorbar.ax.yaxis.set_major_formatter(thousands)
    colorbar.set_label("Orders (distinct, S0)")
    ax.set_title(title, pad=24)
    return fig


fig = polar_bars(
    orders_by_hour, hour_labels,
    f"Orders by purchase hour: peak at {peak_hour:02d}h, quietest at "
    f"{int(orders_by_hour.idxmin()):02d}h",
)
export.save_fig(fig, "15a_polar_orders_by_hour", OUT_FIGURES)

peak_day = weekday_names[orders_by_weekday.idxmax()]
low_day = weekday_names[orders_by_weekday.idxmin()]
fig = polar_bars(
    orders_by_weekday, weekday_names.tolist(),
    f"Orders by weekday: most on {peak_day}, fewest on {low_day}",
)
export.save_fig(fig, "15b_polar_orders_by_weekday", OUT_FIGURES)

print(f"Orders counted by weekday: {int(orders_by_weekday.sum()):,}")
print(f"Busiest weekday: {peak_day} ({int(orders_by_weekday.max()):,} orders)")
print(f"Quietest weekday: {low_day} ({int(orders_by_weekday.min()):,} orders)")
weekend = orders_by_weekday.loc[[6, 7]].sum() / orders_by_weekday.sum()
print(f"Share of orders on Saturday and Sunday: {weekend:.4f}")
print("\nOrders by weekday:")
print(pd.DataFrame({"weekday": weekday_names, "orders": orders_by_weekday}).to_string())


# ## 10. Findings and KPI cross-check
# 
# KPIs compared with `apps/bi-dashboard/validation/kpi_reference.csv`, the same reference used by the Power BI dashboard (tolerance 0.1%), followed by the numbers of the narrative arc (Setup, Conflict, Resolution).

# STAGE 10: FINDINGS AND CROSS-CHECK
# --- 10.1 KPI cross-check against the reference ---
print_banner("10. Findings and KPI cross-check")
KPI_NAMES = ["GMV", "Orders", "Late Rate %", "Avg Review"]


def load_reference(path, names):
    """Return the kpi,S0 reference value of each name, or stop naming what is missing."""
    hint = "Run python scripts/kpi_reference.py to regenerate it."
    if not path.is_file():
        raise FileNotFoundError(f"KPI reference file not found: {path}. {hint}")
    table = pd.read_csv(path, encoding="utf-8")
    rows = table.loc[(table["section"] == "kpi") & (table["scenario"] == "S0")]
    values = rows.set_index("kpi")["value"]
    missing = [name for name in names if name not in values.index]
    if missing:
        raise ValueError(f"KPI reference {path} has no kpi,S0 row for {missing}. {hint}")
    return {name: float(values[name]) for name in names}


def cross_check(values, reference, tolerance):
    """Return the notebook value, reference, relative difference and PASS/FAIL of each KPI."""
    rows = []
    for name, expected in reference.items():
        rel_diff = (values[name] - expected) / expected
        status = "PASS" if abs(rel_diff) <= tolerance else "FAIL"
        rows.append((name, values[name], expected, rel_diff, status))
    return pd.DataFrame(rows, columns=["kpi", "notebook", "reference", "rel_diff", "status"])


print(
    "Cross-check against apps/bi-dashboard/validation/kpi_reference.csv "
    "(same reference as the Power BI dashboard)"
)
reference = load_reference(KPI_REFERENCE, KPI_NAMES)
check_values = compute_kpis(lines, orders, CANCELED)
kpi_check = cross_check(check_values, reference, TOLERANCE)
print(f"Tolerance: abs(rel_diff) <= {TOLERANCE:.1%}; Late Rate % compared as a fraction\n")
print(
    kpi_check.to_string(
        index=False,
        formatters={
            "notebook": "{:,.6f}".format,
            "reference": "{:,.6f}".format,
            "rel_diff": "{:+.6%}".format,
        },
    )
)
failed = kpi_check.loc[kpi_check["status"] == "FAIL", "kpi"].tolist()
print(f"\nKPIs with PASS: {int((kpi_check['status'] == 'PASS').sum())} of {len(kpi_check)}")
if failed:
    print(f"FAIL: {failed} exceed the tolerance; the deliverable is not approved until reviewed.")


# --- 10.2 Narrative arc: Setup, Conflict and Resolution ---
def print_block(title, rows):
    """Print one block of the narrative arc as label: value lines."""
    print(f"\n{title}")
    print("-" * len(title))
    for label, value in rows:
        print(f"- {label}: {value}")


on_time_review = float(orders.loc[orders["is_late"] == 0, "review_score"].mean())
late_review = float(orders.loc[orders["is_late"] == 1, "review_score"].mean())
evaluated_lines = commercial_lines.loc[commercial_lines["is_late"].notna()]
late_gmv = float(commercial_lines.loc[commercial_lines["is_late"] == 1, "price"].sum())
late_gmv_share = late_gmv / float(evaluated_lines["price"].sum())
top_regions = region_ci.head(TOP_N_ACCENT)
top_states = late_states.head(TOP_N_ACCENT)

rho_orders = commercial_orders.dropna(subset=["distance_km", "freight_value"])
rho_pair = rho_orders[["distance_km", "freight_value"]].corr(method="spearman")
arc_rho = float(rho_pair.loc["distance_km", "freight_value"])
heatmap_rho = float(spearman.loc["distance_km", "freight_value"])
ratio_medians = ratio_summary["50%"]
high_ratio, low_ratio = ratio_medians.idxmax(), ratio_medians.idxmin()
median_week_orders = float(weekly["orders"].median())

print_block("Setup", [
    ("GMV (R$)", f"{kpis['GMV']:,.2f}"),
    ("Orders", f"{kpis['Orders']:,.0f}"),
    ("Late Rate %", f"{kpis['Late Rate %']:.1%}"),
    ("Avg Review", f"{kpis['Avg Review']:.2f}"),
])
print_block("Conflict", [
    ("Avg Review of on-time orders", f"{on_time_review:.2f}"),
    ("Avg Review of late orders", f"{late_review:.2f}"),
    ("Review drop when late (points)", f"{on_time_review - late_review:.2f}"),
    ("Late GMV (R$)", f"{late_gmv:,.2f}"),
    ("Late GMV % (of evaluated GMV)", f"{late_gmv_share:.1%}"),
    *[
        (f"Region #{rank} by Late Rate %", f"{row.region} {row.late_rate:.1%}")
        for rank, row in enumerate(top_regions.itertuples(), start=1)
    ],
    *[
        (f"State #{rank} by Late Rate %", f"{row.state_name} ({row.uf}) {row.late_rate:.1%}")
        for rank, row in enumerate(top_states.itertuples(), start=1)
    ],
])
print_block("Resolution", [
    ("Spearman rho distance vs freight (S0 orders)", f"{arc_rho:.2f}"),
    ("Orders in that Spearman rho", f"{len(rho_orders):,}"),
    ("Highest median freight ratio", f"{high_ratio} {ratio_medians[high_ratio]:.2f}"),
    ("Lowest median freight ratio", f"{low_ratio} {ratio_medians[low_ratio]:.2f}"),
    ("Black Friday 2017 week", f"{iso_label(bf_week)} (from {bf_week.date()})"),
    ("Black Friday 2017 week orders", f"{bf_row['orders']:,.0f}"),
    ("Black Friday 2017 week average ticket (R$)", f"{bf_row['avg_ticket']:,.2f}"),
    ("Median weekly orders", f"{median_week_orders:,.0f}"),
    ("Median weekly average ticket (R$)", f"{median_ticket:,.2f}"),
    (
        "Black Friday 2017 week orders vs median week",
        f"{bf_row['orders'] / median_week_orders:.1f}x",
    ),
])
print(f"\nSpearman rho of figure 07b (distance vs freight): {heatmap_rho:.2f}")
print(f"Resolution rho equals figure 07b at 2 decimals: {f'{arc_rho:.2f}' == f'{heatmap_rho:.2f}'}")


# ## 11. Export inventory
# 
# Checks that the 37 exported files (15 PNG, 15 SVG and 7 HTML) exist.

# STAGE 11: EXPORT INVENTORY
print_banner("11. Export inventory")


def inventory(static, html, out_figures, out_html):
    """Return the expected files with size (KiB), the missing ones and the extra ones."""
    expected = [out_figures / "png" / f"{name}.png" for name in static]
    expected += [out_figures / "svg" / f"{name}.svg" for name in static]
    expected += [out_html / f"{name}.html" for name in html]
    present = [
        (path.parent.name, path.name, path.stat().st_size / 1024)
        for path in expected if path.is_file()
    ]
    missing = [f"{path.parent.name}/{path.name}" for path in expected if not path.is_file()]
    known = set(expected)
    extra = sorted(
        f"{folder.name}/{path.name}"
        for folder in [out_figures / "png", out_figures / "svg", out_html] if folder.is_dir()
        for path in folder.iterdir()
        if path.is_file() and path.name != ".gitkeep" and path not in known
    )
    table = pd.DataFrame(present, columns=["folder", "file", "size_kib"])
    return table, missing, extra


files, missing_files, extra_files = inventory(STATIC_FIGURES, HTML_FILES, OUT_FIGURES, OUT_HTML)
print(files.to_string(index=False, formatters={"size_kib": "{:,.1f}".format}))
expected_count = 2 * len(STATIC_FIGURES) + len(HTML_FILES)
print(f"\nFiles expected: {expected_count}")
print(f"Files present: {len(files)}")
print(f"Total size (KiB): {files['size_kib'].sum():,.1f}")
print(f"{len(missing_files)} missing")
print(f"{len(extra_files)} extra")
if extra_files:
    print(f"WARNING: extra files in outputs/ not exported by this notebook (kept): {extra_files}")
if missing_files:
    raise FileNotFoundError(f"Missing exports: {missing_files}. Re-run the notebook from the top.")

