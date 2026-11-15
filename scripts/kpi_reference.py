"""KPI reference for the Power BI dashboard: ``python scripts/kpi_reference.py``.

Reads the star schema in ``data/processed/`` and computes, with exactly the same
definitions as the DAX measures (spec 002 Def-5, plan 002 section 5), the KPIs of the
scenarios S0-S3 (Def-9). The output CSV is the reference used to check the dashboard
figures within 0.1 %.

Only pandas, numpy and the standard library are used. Paths and domain constants come from
``ecbd_etl.config`` (single source of configuration); no function reads the system date.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

# Prefer the sibling source tree so a copy of the repository uses its own code.
SRC_DIR = Path(__file__).resolve().parents[1] / "packages" / "etl" / "src"
sys.path.insert(0, str(SRC_DIR))

from ecbd_etl.config import (  # noqa: E402
    CANCELED_STATUS,
    PER_CAPITA_BASE,
    PROCESSED_DIR,
    REGION_NORDESTE,
    ROOT,
    UNCATEGORIZED_MACRO,
)

DEFAULT_OUTPUT = ROOT / "apps" / "bi-dashboard" / "validation" / "kpi_reference.csv"

# Year of the S2 scenario (Def-9: purchase year = 2018).
SCENARIO_YEAR = 2018
# Maximum tolerated |relative difference| against the ETL (C-2: 0.1 %).
TOLERANCE = 0.001
NAN = float("nan")
# Title facts: default of the "Late Rate Target" parameter (team assumption, R-B8), minimum
# evaluated orders of the top 10 (C-16) and the state_full suffix of Def-4.
DEFAULT_LATE_RATE_TARGET = 0.08
MIN_EVALUATED_ORDERS = 30
STATE_FULL_SUFFIX = ", Brasil"

# KPIs of Def-9 written to the "kpi" section, in this fixed order (14 + Repeat, P2).
REFERENCE_KPIS = (
    "GMV",
    "Orders",
    "Customers",
    "Avg Ticket",
    "Late Rate %",
    "Avg Delivery Days",
    "Avg Delay Days",
    "Avg Review",
    "Negative Review %",
    "Late GMV",
    "Late GMV %",
    "Avg Review On Time",
    "Avg Review Late",
    "Review Drop Late",
    "Repeat Customer Rate",
)
CSV_COLUMNS = [
    "section",
    "scenario",
    "scenario_filter",
    "kpi",
    "member",
    "value",
    "etl_value",
    "rel_diff",
]

# File name -> {column: dtype}. Integers that may be null are read as nullable Int64 and
# text as str; only the columns used are read (usecols = the keys of each mapping).
INPUT_COLUMNS = {
    "fact_order_items.csv": {
        "order_id": "str",
        "purchase_date_key": "Int64",
        "customer_key": "Int64",
        "seller_key": "Int64",
        "product_key": "Int64",
        "payment_type_key": "Int64",
        "order_status_key": "Int64",
        "price": "float64",
        "freight_value": "float64",
        "purchase_hour": "Int64",
        "delivery_days": "float64",
        "delay_days": "Int64",
        "is_late": "Int64",
        "delay_band": "str",
        "delay_band_order": "Int64",
        "review_score": "Int64",
        "is_negative_review": "Int64",
        "distance_km": "float64",
    },
    "dim_date.csv": {
        "date_key": "Int64",
        "year": "Int64",
        "year_month": "str",
        "weekday_number": "Int64",
        "weekday_name": "str",
    },
    "dim_customer.csv": {
        "customer_key": "Int64",
        "customer_unique_id": "str",
        "state": "str",
        "region": "str",
    },
    "dim_seller.csv": {"seller_key": "Int64", "lat": "float64", "lng": "float64"},
    "dim_product.csv": {"product_key": "Int64", "category_en": "str", "macro_category": "str"},
    "dim_state.csv": {"uf": "str", "state_name": "str", "population_2018": "Int64"},
    "dim_payment_type.csv": {"payment_type_key": "Int64", "payment_label": "str"},
    "dim_order_status.csv": {"order_status_key": "Int64", "order_status": "str"},
}
FLAT_FILE = "analytics_flat.csv.gz"
FLAT_COLUMNS = {"uf": "str", "orders_per_100k": "float64"}

# Nullable integer measures converted to float before any calculation, so that mean() and
# comparisons never return pd.NA (plan 002 section 4.2, equivalence notes).
INT_MEASURE_COLUMNS = (
    "delay_days",
    "is_late",
    "review_score",
    "is_negative_review",
    "delay_band_order",
)


class ReferenceInputError(Exception):
    """Raised when an input file of the KPI reference is missing (RF-36)."""


# --------------------------------------------------------------------------------------
# Load and base table
# --------------------------------------------------------------------------------------
def load_tables(processed_dir):
    """Read the model CSV files and the flat table's (uf, orders_per_100k) columns.

    Every expected file is checked first; if any is missing, ReferenceInputError names
    each missing file and the expected folder.
    """
    processed_dir = Path(processed_dir)
    expected = [*INPUT_COLUMNS, FLAT_FILE]
    missing = [name for name in expected if not (processed_dir / name).is_file()]
    if missing:
        listed = "\n".join(f"  - {name}" for name in missing)
        raise ReferenceInputError(
            f"missing input file(s) in the expected folder {processed_dir}:\n{listed}\n"
            "Run `python scripts/run_pipeline.py` to generate data/processed/."
        )
    tables = {}
    for name, dtypes in INPUT_COLUMNS.items():
        tables[name.removesuffix(".csv")] = pd.read_csv(
            processed_dir / name, usecols=list(dtypes), dtype=dtypes, encoding="utf-8"
        )
    tables["analytics_flat"] = pd.read_csv(
        processed_dir / FLAT_FILE,
        usecols=list(FLAT_COLUMNS),
        dtype=FLAT_COLUMNS,
        encoding="utf-8",
    )
    return tables


def build_base(tables):
    """One row per fact line with the measure columns and the dimension attributes used.

    Every join is many-to-one (validate="m:1"), so the fact rows are never duplicated.
    """
    fact = tables["fact_order_items"]
    base = (
        fact.merge(
            tables["dim_order_status"], on="order_status_key", how="left", validate="m:1"
        )
        .merge(
            tables["dim_customer"].rename(columns={"state": "uf"}),
            on="customer_key",
            how="left",
            validate="m:1",
        )
        .merge(
            tables["dim_product"], on="product_key", how="left", validate="m:1"
        )
        .merge(
            tables["dim_date"].rename(columns={"date_key": "purchase_date_key"}),
            on="purchase_date_key",
            how="left",
            validate="m:1",
        )
        .merge(
            tables["dim_payment_type"], on="payment_type_key", how="left", validate="m:1"
        )
        .merge(
            tables["dim_seller"].rename(columns={"lat": "seller_lat", "lng": "seller_lng"}),
            on="seller_key",
            how="left",
            validate="m:1",
        )
    )
    for column in INT_MEASURE_COLUMNS:
        base[column] = base[column].astype("float64")
    base["year"] = base["year"].astype("float64")
    return base


def top_macro_category(base, exclude, canceled=CANCELED_STATUS):
    """S3 (C-35): macro-category with the highest non-canceled GMV, excluding ``exclude``.

    Ties are broken by name ascending. The value always comes from the data (RF-37).
    """
    commercial = base.loc[base["order_status"] != canceled]
    gmv = (
        commercial.groupby("macro_category", sort=True)
        .agg(gmv=("price", "sum"))
        .reset_index()
    )
    gmv = gmv.loc[gmv["macro_category"] != exclude]
    ranked = gmv.sort_values(["gmv", "macro_category"], ascending=[False, True])
    return str(ranked["macro_category"].iloc[0])


def scenarios(base, region, year, macro):
    """Scenarios of Def-9 as (id, filter description, boolean mask over ``base``)."""
    return [
        ("S0", "none", pd.Series(True, index=base.index)),
        ("S1", f"dim_customer[region] = {region}", base["region"] == region),
        ("S2", f"dim_date[year] = {year}", base["year"] == year),
        ("S3", f"dim_product[macro_category] = {macro}", base["macro_category"] == macro),
    ]


# --------------------------------------------------------------------------------------
# KPIs (exact replica of Def-5 / plan section 5; an empty DAX result is NaN here)
# --------------------------------------------------------------------------------------
def sum_or_nan(values):
    """SUM over no rows is BLANK in DAX, not 0."""
    return float(values.sum()) if len(values) > 0 else NAN


def count_or_nan(count):
    """DISTINCTCOUNT/COUNTROWS over no rows is BLANK in DAX, not 0."""
    return float(count) if count > 0 else NAN


def divide(numerator, denominator):
    """DAX DIVIDE: empty or 0 denominator -> empty; an empty numerator stays empty."""
    if pd.isna(denominator) or denominator == 0:
        return NAN
    return numerator / denominator


def rate(numerator, denominator):
    """Rates: empty or 0 denominator -> empty (RF-33); empty numerator -> 0 (C-18)."""
    if not denominator > 0:
        return NAN
    return (0.0 if pd.isna(numerator) else numerator) / denominator


def diff(first, second):
    """Differences are empty when either term is empty (C-29)."""
    if pd.isna(first) or pd.isna(second):
        return NAN
    return first - second


def order_level(df):
    """One row per order (all statuses) with the MAX of each order-level column.

    Replicates AVERAGEX(VALUES(order_id), CALCULATE(MAX(...))): a single value per order;
    mean() then skips NaN as AVERAGEX skips BLANK.
    """
    return df.groupby("order_id", sort=True).agg(
        is_late=("is_late", "max"),
        delivery_days=("delivery_days", "max"),
        delay_days=("delay_days", "max"),
        review_score=("review_score", "max"),
        is_negative_review=("is_negative_review", "max"),
        distance_km=("distance_km", "max"),
    )


def negative_review_rate(orders):
    """Negative Review %: orders with is_negative_review = 1 over orders with a review."""
    reviewed = count_or_nan(int(orders["review_score"].notna().sum()))
    negative = count_or_nan(int((orders["is_negative_review"] == 1).sum()))
    return rate(negative, reviewed)


def compute_kpis(df, population_by_uf, canceled, base_100k):
    """Every KPI of Def-5 needed by the reference, for the fact lines in ``df``."""
    nc = df.loc[df["order_status"] != canceled]  # commercial universe
    od = order_level(df)
    on_time = od.loc[od["is_late"] == 0]
    late = od.loc[od["is_late"] == 1]

    kpis = {}
    kpis["GMV"] = sum_or_nan(nc["price"])  # price, never item_total (C-22)
    kpis["Freight"] = sum_or_nan(nc["freight_value"])
    kpis["Orders"] = count_or_nan(nc["order_id"].nunique())
    kpis["Customers"] = count_or_nan(df["customer_unique_id"].nunique())  # all statuses
    # Partial ticket under a category context (C-36); NaN propagates like BLANK.
    kpis["Avg Ticket"] = divide(kpis["GMV"] + kpis["Freight"], kpis["Orders"])
    # States present through the fact lines, all statuses (expanded table, R-B4).
    present_ufs = sorted(df["uf"].dropna().unique())
    kpis["Population"] = sum_or_nan(population_by_uf.reindex(present_ufs).dropna())
    kpis["Orders per 100k"] = divide(kpis["Orders"] * base_100k, kpis["Population"])
    kpis["Freight Ratio"] = divide(kpis["Freight"], kpis["GMV"])

    kpis["Evaluated Orders"] = count_or_nan(int(od["is_late"].notna().sum()))
    kpis["Late Orders"] = count_or_nan(int((od["is_late"] == 1).sum()))
    kpis["Late Rate %"] = rate(kpis["Late Orders"], kpis["Evaluated Orders"])
    kpis["Avg Delivery Days"] = od["delivery_days"].mean()
    kpis["Avg Delay Days"] = od["delay_days"].mean()
    kpis["Avg Distance km"] = od["distance_km"].mean()  # max per order, nulls skipped (C-7)

    kpis["Avg Review"] = od["review_score"].mean()  # all statuses (P-2)
    kpis["Negative Review %"] = negative_review_rate(od)

    kpis["Late GMV"] = sum_or_nan(nc.loc[nc["is_late"] == 1, "price"])
    evaluated_gmv = sum_or_nan(nc.loc[nc["is_late"].notna(), "price"])  # A5
    kpis["Late GMV %"] = rate(kpis["Late GMV"], evaluated_gmv)
    kpis["Avg Review On Time"] = on_time["review_score"].mean()
    kpis["Avg Review Late"] = late["review_score"].mean()
    kpis["Review Drop Late"] = diff(kpis["Avg Review On Time"], kpis["Avg Review Late"])
    kpis["Negative Review % Late"] = negative_review_rate(late)
    kpis["Negative Review % On Time"] = negative_review_rate(on_time)

    per_customer = nc.groupby("customer_unique_id", sort=True)["order_id"].nunique()  # A6
    kpis["Repeat Customer Rate"] = rate(
        count_or_nan(int((per_customer >= 2).sum())), count_or_nan(len(per_customer))
    )
    return {name: float(value) for name, value in kpis.items()}


def orders_per_100k_check(base, population_by_uf, etl_by_uf, canceled, base_100k):
    """S0 Orders per 100k per UF, next to the ETL value and the relative difference."""
    rows = []
    for uf in sorted(population_by_uf.index):
        value = compute_kpis(base.loc[base["uf"] == uf], population_by_uf, canceled, base_100k)[
            "Orders per 100k"
        ]
        etl_value = float(etl_by_uf.get(uf, NAN))
        rows.append(
            {
                "member": uf,
                "value": value,
                "etl_value": etl_value,
                "rel_diff": divide(value - etl_value, abs(etl_value)),
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Title facts (S0 breakdowns behind the static titles; C-14, plan Duda 1; not checked)
# --------------------------------------------------------------------------------------
def grouped_kpis(df, keys, population_by_uf, canceled, base_100k):
    """compute_kpis for every group of ``keys`` (sorted), as (key tuple, kpis) pairs.

    Reusing compute_kpis keeps a single definition of every measure.
    """
    return [
        (
            key if isinstance(key, tuple) else (key,),
            compute_kpis(group, population_by_uf, canceled, base_100k),
        )
        for key, group in df.groupby(keys, sort=True, dropna=False)
    ]


def fact_row(kpi, member, value):
    """One title_fact row of the S0 scenario."""
    return {
        "section": "title_fact",
        "scenario": "S0",
        "scenario_filter": "none",
        "kpi": kpi,
        "member": member,
        "value": float(value),
        "etl_value": NAN,
        "rel_diff": NAN,
    }


def title_facts(base, population_by_uf, state_names, national, canceled, base_100k, target):
    """S0 breakdowns needed by the titles of the 16 data visuals (plan 002 section 6.4).

    ``state_names`` maps UF -> state name (dim_state); the member of state breakdowns is
    ``state_full`` = state name + ", Brasil" (Def-4). ``national`` are the S0 KPIs.
    """
    base = base.assign(state_full=base["uf"].map(state_names) + STATE_FULL_SUFFIX)

    def by(keys):
        return grouped_kpis(base, keys, population_by_uf, canceled, base_100k)

    rows = []
    month = "dim_date[year_month]"
    state = "dim_customer[state_full]"
    region = "dim_customer[region]"

    # Page 1: monthly lines (purchase month, A3).
    months = by(["year_month"])
    rows += [fact_row(f"GMV by {month}", key[0], kpis["GMV"]) for key, kpis in months]
    rows += [
        fact_row(f"Late Rate % by {month}", key[0], kpis["Late Rate %"]) for key, kpis in months
    ]

    # Page 1: map, top 10 and region variance; page 2 and 3 state visuals.
    states = by(["state_full"])
    rows += [
        fact_row(f"Orders per 100k by {state}", key[0], kpis["Orders per 100k"])
        for key, kpis in states
    ]
    eligible = [
        (key[0], kpis)
        for key, kpis in states
        if kpis["Evaluated Orders"] >= MIN_EVALUATED_ORDERS
    ]
    # Same order as State Late Rank (C-16): rate desc, evaluated desc, state name asc.
    eligible.sort(key=lambda item: (-item[1]["Late Rate %"], -item[1]["Evaluated Orders"], item[0]))
    suffix = f"(>= {MIN_EVALUATED_ORDERS} evaluated, State Late Rank order)"
    rows += [
        fact_row(f"Late Rate % by {state} {suffix}", member, kpis["Late Rate %"])
        for member, kpis in eligible
    ]
    rows += [
        fact_row(f"Evaluated Orders by {state} {suffix}", member, kpis["Evaluated Orders"])
        for member, kpis in eligible
    ]
    rows += [
        fact_row(
            f"Late Rate Variance by {region} (target {target:.0%})",
            key[0],
            diff(target, kpis["Late Rate %"]),
        )
        for key, kpis in by(["region"])
    ]

    # Page 2: review by delay band (blank band excluded, C-28), state delay and review gap,
    # orders heatmap.
    rows += [
        fact_row("Avg Review by fact_order_items[delay_band]", key[1], kpis["Avg Review"])
        for key, kpis in grouped_kpis(
            base.loc[base["delay_band"].notna()],
            ["delay_band_order", "delay_band"],
            population_by_uf,
            canceled,
            base_100k,
        )
    ]
    rows += [
        fact_row(f"Avg Delay Days by {state}", key[0], kpis["Avg Delay Days"])
        for key, kpis in states
    ]
    rows += [
        fact_row(
            f"Review Gap vs National by {state}",
            key[0],
            diff(kpis["Avg Review"], national["Avg Review"]),
        )
        for key, kpis in states
    ]
    rows += [
        fact_row(
            "Orders by dim_date[weekday_name] x fact_order_items[purchase_hour]",
            f"{key[1]} | {int(key[2]):02d}",
            kpis["Orders"],
        )
        for key, kpis in by(["weekday_number", "weekday_name", "purchase_hour"])
    ]

    # Page 3: product GMV, payment mix, distance and freight, sellers without coordinates.
    rows += [
        fact_row("GMV by dim_product[macro_category]", key[0], kpis["GMV"])
        for key, kpis in by(["macro_category"])
    ]
    rows += [
        fact_row("GMV by dim_product[category_en]", key[0], kpis["GMV"])
        for key, kpis in by(["category_en"])
    ]
    mix = by(["region", "payment_label"])
    region_orders = {}
    for key, kpis in mix:
        region_orders[key[0]] = region_orders.get(key[0], 0.0) + kpis["Orders"]
    mix_name = f"{region} x dim_payment_type[payment_label]"
    rows += [
        fact_row(f"Orders by {mix_name}", f"{key[0]} | {key[1]}", kpis["Orders"])
        for key, kpis in mix
    ]
    rows += [
        fact_row(
            f"Orders share by {mix_name}",
            f"{key[0]} | {key[1]}",
            divide(kpis["Orders"], region_orders[key[0]]),
        )
        for key, kpis in mix
    ]
    rows += [
        fact_row(f"Avg Distance km by {state}", key[0], kpis["Avg Distance km"])
        for key, kpis in states
    ]
    rows += [
        fact_row(f"Freight Ratio by {state}", key[0], kpis["Freight Ratio"])
        for key, kpis in states
    ]
    no_coords = base.loc[base["seller_lat"].isna() | base["seller_lng"].isna(), "seller_key"]
    rows.append(fact_row("Sellers Without Coords", "", no_coords.nunique()))
    return rows


# --------------------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------------------
def to_rows(kpi_results, check, title_rows=()):
    """Long table with a fixed row order: KPI section (scenario, KPI order), UFs, titles."""
    rows = []
    for scenario_id, description, kpis in kpi_results:
        for name in REFERENCE_KPIS:
            rows.append(
                {
                    "section": "kpi",
                    "scenario": scenario_id,
                    "scenario_filter": description,
                    "kpi": name,
                    "member": "",
                    "value": kpis[name],
                    "etl_value": NAN,
                    "rel_diff": NAN,
                }
            )
    for record in check.to_dict("records"):
        rows.append(
            {
                "section": "orders_per_100k",
                "scenario": "S0",
                "scenario_filter": "none",
                "kpi": "Orders per 100k",
                **record,
            }
        )
    rows.extend(title_rows)
    return pd.DataFrame(rows, columns=CSV_COLUMNS)


def write_csv(df, path):
    """Deterministic CSV: 6 decimals, UTF-8 without BOM, LF, NaN as an empty field."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(
        path,
        index=False,
        encoding="utf-8",
        lineterminator="\n",
        float_format="%.6f",
        na_rep="",
    )


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------
def parse_args(argv):
    parser = argparse.ArgumentParser(description="Compute the KPI reference of the dashboard.")
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=PROCESSED_DIR,
        help="folder with the star schema CSV files (default: data/processed)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="CSV to write (default: apps/bi-dashboard/validation/kpi_reference.csv)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        tables = load_tables(args.processed_dir)
    except ReferenceInputError as error:
        print(f"ERROR: {error}")
        return 1

    base = build_base(tables)
    macro = top_macro_category(base, UNCATEGORIZED_MACRO)
    scenario_list = scenarios(base, REGION_NORDESTE, SCENARIO_YEAR, macro)

    population_by_uf = (
        tables["dim_state"].set_index("uf")["population_2018"].astype("float64").sort_index()
    )
    etl_by_uf = (
        tables["analytics_flat"]
        .groupby("uf", sort=True)
        .agg(orders_per_100k=("orders_per_100k", "first"))["orders_per_100k"]
    )

    print(f"Base rows: {len(base)} (fact_order_items: {len(tables['fact_order_items'])})")
    kpi_results = []
    for scenario_id, description, mask in scenario_list:
        print(f"{scenario_id}: {description} ({int(mask.sum())} fact rows)")
        kpis = compute_kpis(base.loc[mask], population_by_uf, CANCELED_STATUS, PER_CAPITA_BASE)
        kpi_results.append((scenario_id, description, kpis))
    print(f"S3 macro-category (from data): {macro}")

    check = orders_per_100k_check(
        base, population_by_uf, etl_by_uf, CANCELED_STATUS, PER_CAPITA_BASE
    )
    state_names = tables["dim_state"].set_index("uf")["state_name"]
    titles = title_facts(
        base,
        population_by_uf,
        state_names,
        kpi_results[0][2],  # S0 = national context
        CANCELED_STATUS,
        PER_CAPITA_BASE,
        DEFAULT_LATE_RATE_TARGET,
    )
    rows = to_rows(kpi_results, check, titles)
    write_csv(rows, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")

    failing = check.loc[~(check["rel_diff"].abs() <= TOLERANCE)]
    if not failing.empty:
        # ETL inconsistency: report it (RF-85), never adjust the reference.
        print(f"ERROR: Orders per 100k differs from the ETL by more than {TOLERANCE:.1%} in:")
        for record in failing.to_dict("records"):
            print(
                f"  {record['member']}: reference {record['value']:.6f}, "
                f"ETL {record['etl_value']:.6f}, rel_diff {record['rel_diff']:.6f}"
            )
        return 2
    print(f"Orders per 100k: {len(check)} UF within {TOLERANCE:.1%} of the ETL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
