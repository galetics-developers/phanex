"""Model stage: star-schema dimensions, the fact table and the flat analytics table.

``run`` turns the enriched tables into the 9 model tables of D9 (column contracts of
D6, D7 and D8, defined in ``config``) and records the 5 model rules of the closed list:

- ``dim_date``: continuous calendar with ``date_key`` = YYYYMMDD and English names;
- ``dim_state``: the 27 UF in alphabetical order with population and centroid;
- ``dim_customer`` / ``dim_seller`` / ``dim_product``: only the keys used by the fact
  table; ``dim_customer`` has one row per ``customer_id``;
- ``dim_payment_type`` / ``dim_order_status``: fixed catalogs;
- ``fact_order_items``: one row per order line, sorted by ``order_id``,
  ``order_item_id``; ``order_item_key`` = position 1..n;
- ``analytics_flat``: the fact rows joined to every dimension, without keys.

Surrogate keys are integers 1..n in ascending order of the natural key. Every join is a
left join validated as many-to-one whose row count is checked, so no join can multiply
or drop rows. Every helper above ``run`` is a pure function: no I/O, no clock, and every
parameter (contracts, catalogs, names, range) arrives as an argument from ``config``.
"""

import numpy as np
import pandas as pd

from ecbd_etl import config
from ecbd_etl.quality import ETLError

# Order columns carried into the fact table (delivery metrics come from enrich).
_ORDER_FACT_COLUMNS = [
    "order_id",
    "customer_id",
    "order_status",
    "order_purchase_timestamp",
    "delivered_date",
    "order_estimated_delivery_date",
    "purchase_hour",
    "delivery_days",
    "promised_days",
    "delay_days",
    "is_late",
    "delay_band",
    "delay_band_order",
    "delivery_data_missing",
]
_ITEM_FACT_COLUMNS = [
    "order_id",
    "order_item_id",
    "product_id",
    "seller_id",
    "price",
    "freight_value",
    "item_total",
    "freight_ratio",
    "same_state",
    "distance_km",
]


# --------------------------------------------------------------------------------------
# Pure helpers: contracts, joins and keys
# --------------------------------------------------------------------------------------
def select_contract(df, columns, table):
    """Return ``df`` with exactly ``columns`` in that order; fail if any is missing."""
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ETLError(f"{table}: missing contract column(s) {', '.join(missing)}")
    selected = df[list(columns)].reset_index(drop=True)
    if list(selected.columns) != list(columns):
        raise ETLError(f"{table}: columns do not match the contract")
    return selected


def merge_lookup(left, right, on, label):
    """Left join validated as many-to-one; fail if the number of rows changes."""
    merged = left.merge(right, on=on, how="left", validate="m:1")
    if len(merged) != len(left):
        raise ETLError(f"Join with {label} changed the row count ({len(left)} -> {len(merged)})")
    return merged


def assign_surrogate_keys(df, natural_key, key_name):
    """Sort by ``natural_key`` (stable) and add ``key_name`` = 1..n in that order."""
    ordered = df.sort_values(natural_key, kind="stable").reset_index(drop=True)
    return ordered.assign(**{key_name: np.arange(1, len(ordered) + 1, dtype="int64")})


def date_key(timestamps):
    """Return the YYYYMMDD integer key of each timestamp (``Int64``; null stays null)."""
    return (
        timestamps.dt.year * 10000 + timestamps.dt.month * 100 + timestamps.dt.day
    ).astype("Int64")


def as_key(series):
    """Cast a key to ``int64`` when it has no nulls; otherwise keep it as ``Int64``.

    Keeping a null visible (instead of failing here) lets ``validate`` report it.
    """
    key = series.astype("Int64")
    return key if key.hasnans else key.astype("int64")


# --------------------------------------------------------------------------------------
# Pure builders: dimensions
# --------------------------------------------------------------------------------------
def build_dim_date(
    start,
    end,
    calendar,
    month_names,
    weekday_names,
    weekend_days,
    date_format,
    year_month_format,
    columns,
):
    """Continuous daily calendar from ``start`` to ``end`` (inclusive, D7, RF-51).

    ``weekday_number`` is 1 = Monday; names come from the fixed English tables;
    ``commercial_event`` is the calendar event of the day (null when there is none).
    """
    dates = pd.Series(pd.date_range(start, end, freq="D"), name="date")
    weekday = (dates.dt.day_of_week + 1).astype("int64")
    events = pd.Series(
        calendar["event"].str.strip().to_numpy(),
        index=date_key(pd.to_datetime(calendar["date"].str.strip(), format=date_format)),
    )
    keys = date_key(dates).astype("int64")
    dim = pd.DataFrame(
        {
            "date_key": keys,
            "date": dates,
            "year": dates.dt.year.astype("int64"),
            "quarter": dates.dt.quarter.astype("int64"),
            "month_number": dates.dt.month.astype("int64"),
            "month_name": dates.dt.month.map(month_names),
            "year_month": dates.dt.strftime(year_month_format),
            "weekday_number": weekday,
            "weekday_name": weekday.map(weekday_names),
            "is_weekend": weekday.isin(weekend_days).astype("int64"),
            "commercial_event": keys.map(events),
        }
    )
    return select_contract(dim, columns, "dim_date")


def build_dim_state(ibge, state_centroids, columns):
    """The 27 UF with population, region and centroid (D7, RF-54).

    Returns ``(dim_state, n_without_centroid)``; a UF without geolocation inside the box
    keeps a null centroid.
    """
    states = ibge[["uf", "state_name", "region", "population_2018"]].merge(
        state_centroids[["uf", "centroid_lat", "centroid_lng"]],
        on="uf",
        how="left",
        validate="1:1",
    )
    dim = select_contract(
        assign_surrogate_keys(states, ["uf"], "customer_state_key"), columns, "dim_state"
    )
    n_without = int((dim["centroid_lat"].isna() | dim["centroid_lng"].isna()).sum())
    return dim, n_without


def build_dim_customer(customers, used_ids, columns):
    """One row per ``customer_id`` referenced by the fact table (D7, RF-52)."""
    used = customers.loc[customers["customer_id"].isin(used_ids)].rename(
        columns={
            "customer_city": "city",
            "customer_state": "state",
            "customer_region": "region",
            "customer_zip_code_prefix": "zip_prefix",
            "customer_lat": "lat",
            "customer_lng": "lng",
        }
    )
    return select_contract(
        assign_surrogate_keys(used, ["customer_id"], "customer_key"), columns, "dim_customer"
    )


def build_dim_seller(sellers, used_ids, columns):
    """One row per ``seller_id`` referenced by the fact table (D7, RF-53)."""
    used = sellers.loc[sellers["seller_id"].isin(used_ids)].rename(
        columns={"seller_lat": "lat", "seller_lng": "lng"}
    )
    return select_contract(
        assign_surrogate_keys(used, ["seller_id"], "seller_key"), columns, "dim_seller"
    )


def build_dim_product(products, used_ids, columns):
    """One row per ``product_id`` referenced by the fact table (D7, RF-53).

    Returns ``(dim_product, n_null_photos)``; a missing ``photos_qty`` stays null.
    """
    used = products.loc[products["product_id"].isin(used_ids)].rename(
        columns={
            "product_category_name": "category_pt",
            "product_weight_g": "weight_g",
            "product_photos_qty": "photos_qty",
        }
    )
    dim = select_contract(
        assign_surrogate_keys(used, ["product_id"], "product_key"), columns, "dim_product"
    )
    return dim, int(dim["photos_qty"].isna().sum())


def build_catalog(catalog, key_name, code_name, label_name):
    """Fixed catalog ``{key: (code, label)}`` as a table sorted by key (D7, RF-55)."""
    keys = sorted(catalog)
    return pd.DataFrame(
        {
            key_name: np.array(keys, dtype="int64"),
            code_name: [catalog[key][0] for key in keys],
            label_name: [catalog[key][1] for key in keys],
        }
    )


def build_payment_type(catalog, columns):
    """``dim_payment_type`` from the fixed catalog."""
    dim = build_catalog(catalog, "payment_type_key", "payment_type", "payment_label")
    return select_contract(dim, columns, "dim_payment_type")


def build_order_status(catalog, completed_status, columns):
    """``dim_order_status`` from the fixed catalog; ``is_completed`` = 1 only when completed."""
    dim = build_catalog(catalog, "order_status_key", "order_status", "status_label")
    dim = dim.assign(is_completed=dim["order_status"].eq(completed_status).astype("int64"))
    return select_contract(dim, columns, "dim_order_status")


# --------------------------------------------------------------------------------------
# Pure builders: fact table and flat table
# --------------------------------------------------------------------------------------
def build_fact(
    items,
    orders,
    order_payments,
    reviews,
    dim_customer,
    dim_state,
    dim_seller,
    dim_product,
    dim_payment_type,
    dim_order_status,
    sort_columns,
    columns,
):
    """One row per order line with the 9 foreign keys and the measures of D6 (RF-48).

    Rows are sorted by ``sort_columns`` and ``order_item_key`` is their position 1..n.
    ``delivered_date_key`` and ``payment_type_key`` may be null (``Int64``); a null
    ``review_score`` means the order has no review.
    """
    lines = merge_lookup(
        items[_ITEM_FACT_COLUMNS], orders[_ORDER_FACT_COLUMNS], "order_id", "orders"
    )
    lines = merge_lookup(
        lines,
        order_payments[["order_id", "payment_value_order", "main_payment_type", "installments"]],
        "order_id",
        "order payments",
    )
    lines = merge_lookup(
        lines, reviews[["order_id", "review_score", "is_negative_review"]], "order_id", "reviews"
    )
    lookups = (
        (dim_customer[["customer_id", "customer_key", "state"]], "customer_id", "dim_customer"),
        (
            dim_state[["uf", "customer_state_key"]].rename(columns={"uf": "state"}),
            "state",
            "dim_state",
        ),
        (dim_seller[["seller_id", "seller_key"]], "seller_id", "dim_seller"),
        (dim_product[["product_id", "product_key"]], "product_id", "dim_product"),
        (
            dim_payment_type[["payment_type", "payment_type_key"]].rename(
                columns={"payment_type": "main_payment_type"}
            ),
            "main_payment_type",
            "dim_payment_type",
        ),
        (
            dim_order_status[["order_status", "order_status_key"]],
            "order_status",
            "dim_order_status",
        ),
    )
    for right, on, label in lookups:
        lines = merge_lookup(lines, right, on, label)

    lines = lines.assign(
        purchase_date_key=as_key(date_key(lines["order_purchase_timestamp"])),
        delivered_date_key=date_key(lines["delivered_date"]),
        estimated_date_key=as_key(date_key(lines["order_estimated_delivery_date"])),
        customer_key=as_key(lines["customer_key"]),
        customer_state_key=as_key(lines["customer_state_key"]),
        seller_key=as_key(lines["seller_key"]),
        product_key=as_key(lines["product_key"]),
        payment_type_key=lines["payment_type_key"].astype("Int64"),
        order_status_key=as_key(lines["order_status_key"]),
    )
    fact = assign_surrogate_keys(lines, sort_columns, "order_item_key")
    return select_contract(fact, columns, "fact_order_items")


def build_flat(
    fact,
    orders,
    dim_date,
    dim_customer,
    dim_state,
    dim_seller,
    dim_product,
    dim_payment_type,
    dim_order_status,
    ibge,
    columns,
):
    """Fact rows joined to every dimension, without keys (D8, RF-58, RF-59).

    Customer attributes come from ``dim_customer`` through the line's ``customer_key``,
    so each row carries the customer of its own order; the calendar attributes are
    those of the purchase date. Same rows and order as the fact table.
    """
    dates = orders[
        ["order_id", "order_purchase_timestamp", "delivered_date", "order_estimated_delivery_date"]
    ].rename(
        columns={
            "order_purchase_timestamp": "purchase_date",
            "order_estimated_delivery_date": "estimated_date",
        }
    )
    lookups = (
        (dates, "order_id", "orders"),
        (
            dim_date.drop(columns="date").rename(columns={"date_key": "purchase_date_key"}),
            "purchase_date_key",
            "dim_date",
        ),
        (
            dim_customer.drop(columns="state").rename(
                columns={
                    "city": "customer_city",
                    "zip_prefix": "customer_zip_prefix",
                    "lat": "customer_lat",
                    "lng": "customer_lng",
                }
            ),
            "customer_key",
            "dim_customer",
        ),
        (
            dim_state[["customer_state_key", "uf", "state_name", "population_2018"]],
            "customer_state_key",
            "dim_state",
        ),
        (ibge[["uf", "orders_per_100k"]], "uf", "ibge"),
        (
            dim_seller.rename(columns={"lat": "seller_lat", "lng": "seller_lng"}),
            "seller_key",
            "dim_seller",
        ),
        (dim_product, "product_key", "dim_product"),
        (dim_payment_type, "payment_type_key", "dim_payment_type"),
        (dim_order_status, "order_status_key", "dim_order_status"),
    )
    flat = fact
    for right, on, label in lookups:
        flat = merge_lookup(flat, right, on, label)
    return select_contract(flat, columns, "analytics_flat")


def null_counts(fact):
    """Order lines with a null delivered-date key, payment-type key and review score."""
    return {
        "null_delivered_date_key": int(fact["delivered_date_key"].isna().sum()),
        "null_payment_type_key": int(fact["payment_type_key"].isna().sum()),
        "null_review_score": int(fact["review_score"].isna().sum()),
    }


# --------------------------------------------------------------------------------------
# Stage
# --------------------------------------------------------------------------------------
def run(tables, log):
    """Model stage: records the 5 model rules and returns the 9 model tables (D9 order)."""
    items = tables["items"]
    orders = tables["orders"]
    contracts = config.MODEL_CONTRACTS

    dim_date = build_dim_date(
        config.DIM_DATE_START,
        config.DIM_DATE_END,
        tables["calendar"],
        config.MONTH_NAMES,
        config.WEEKDAY_NAMES,
        config.WEEKEND_WEEKDAYS,
        config.DATE_FORMAT,
        config.YEAR_MONTH_FORMAT,
        contracts["dim_date"],
    )
    dim_state, n_without_centroid = build_dim_state(
        tables["ibge"], tables["state_centroids"], contracts["dim_state"]
    )
    used_customers = orders.loc[orders["order_id"].isin(items["order_id"]), "customer_id"]
    dim_customer = build_dim_customer(
        tables["customers"], used_customers, contracts["dim_customer"]
    )
    dim_seller = build_dim_seller(tables["sellers"], items["seller_id"], contracts["dim_seller"])
    dim_product, n_null_photos = build_dim_product(
        tables["products"], items["product_id"], contracts["dim_product"]
    )
    dim_payment_type = build_payment_type(config.PAYMENT_TYPES, contracts["dim_payment_type"])
    dim_order_status = build_order_status(
        config.ORDER_STATUSES, config.COMPLETED_STATUS, contracts["dim_order_status"]
    )

    fact = build_fact(
        items,
        orders,
        tables["order_payments"],
        tables["reviews"],
        dim_customer,
        dim_state,
        dim_seller,
        dim_product,
        dim_payment_type,
        dim_order_status,
        config.FACT_SORT_COLUMNS,
        contracts["fact_order_items"],
    )
    flat = build_flat(
        fact,
        orders,
        dim_date,
        dim_customer,
        dim_state,
        dim_seller,
        dim_product,
        dim_payment_type,
        dim_order_status,
        tables["ibge"],
        contracts["analytics_flat"],
    )

    for rule, n_lines in null_counts(fact).items():
        log.record(rule, n_lines)
    log.record("null_photos_qty", n_null_photos)
    log.record("state_without_centroid", n_without_centroid)

    return {
        "fact_order_items": fact,
        "dim_date": dim_date,
        "dim_customer": dim_customer,
        "dim_seller": dim_seller,
        "dim_product": dim_product,
        "dim_state": dim_state,
        "dim_payment_type": dim_payment_type,
        "dim_order_status": dim_order_status,
        "analytics_flat": flat,
    }
