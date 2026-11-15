"""Clean stage: types, text, duplicates, natural keys, geography and products.

The stage is split in two parts that run in order inside ``run``:

- ``clean_sources`` (part A): exact duplicates (items counted apart, geolocation exempt),
  natural-key uniqueness, explicit-format dates, ZIP / city / state / status / payment
  normalization, numeric types, ZIP and state centroids and the product catalog.
- ``apply_domain_rules`` (part B): reviews, payments and the D3 exclusion rules.

Every helper above ``clean_sources`` is a pure function: no I/O, no clock, and every
parameter (format, bounding box, sentinel values) arrives as an argument from ``config``.
"""

import pandas as pd

from ecbd_etl import config
from ecbd_etl.quality import DuplicateKeyError

# Combining diacritical marks left behind by NFKD normalization.
_COMBINING_MARKS = r"[̀-ͯ]"


# --------------------------------------------------------------------------------------
# Pure helpers: types and text
# --------------------------------------------------------------------------------------
def parse_datetimes(series, fmt):
    """Parse text with an explicit format; return ``(parsed, n_unparseable)``.

    A value is unparseable when it was not null before parsing and is null after it.
    """
    parsed = pd.to_datetime(series, format=fmt, errors="coerce")
    n_unparseable = int((series.notna() & parsed.isna()).sum())
    return parsed, n_unparseable


def to_float(series):
    """Convert text to float; non-numeric values become null."""
    return pd.to_numeric(series, errors="coerce").astype("float64")


def to_int(series):
    """Convert text to a nullable integer (``Int64``); non-numeric values become null."""
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def strip_accents_title(series):
    """Remove accents and return the text stripped and in title case (RF-24)."""
    return (
        series.str.strip()
        .str.normalize("NFKD")
        .str.replace(_COMBINING_MARKS, "", regex=True)
        .str.title()
    )


def normalize_zip(series, length):
    """Return ZIP code prefixes as text of ``length`` characters with leading zeros."""
    return series.str.strip().str.zfill(length)


def normalize_lower(series):
    """Lower-case text without surrounding spaces (RF-25)."""
    return series.str.strip().str.lower()


def normalize_upper(series):
    """Upper-case text without surrounding spaces (federative unit codes)."""
    return series.str.strip().str.upper()


# --------------------------------------------------------------------------------------
# Pure helpers: duplicates and keys
# --------------------------------------------------------------------------------------
def drop_exact_duplicates(df):
    """Drop rows identical in every column (first one kept); return ``(df, n_dropped)``."""
    duplicated = df.duplicated(keep="first")
    return df.loc[~duplicated].reset_index(drop=True), int(duplicated.sum())


def check_natural_key(df, keys, table):
    """Raise ``DuplicateKeyError`` when ``keys`` is not unique in ``df``.

    Called after exact duplicates are removed, so any repeated key left has different
    content in at least one column (RF-27).
    """
    repeated = df.duplicated(subset=keys, keep=False)
    if not repeated.any():
        return
    offending = (
        df.loc[repeated, keys]
        .drop_duplicates()
        .sort_values(keys, na_position="first")
        .reset_index(drop=True)
    )
    sample = "; ".join(
        ", ".join(f"{col}={value}" for col, value in row.items())
        for _, row in offending.head(3).iterrows()
    )
    raise DuplicateKeyError(
        f"Natural key ({', '.join(keys)}) of {table} is duplicated with different content "
        f"in {len(offending)} key value(s) ({int(repeated.sum())} rows), e.g. {sample}. "
        "Fix the source file; nothing was written."
    )


# --------------------------------------------------------------------------------------
# Pure helpers: geography
# --------------------------------------------------------------------------------------
def zip_centroids(geo, box, zip_length):
    """Reduce geolocation to ZIP and state centroids inside the bounding box.

    ``geo`` holds the source text columns (no de-duplication, RF-38); ``box`` is
    ``(lat_min, lat_max, lng_min, lng_max)``, inclusive. Rows outside the box, or with
    non-numeric coordinates, are discarded and counted (RF-37). Returns
    ``(zip_centroids, state_centroids, n_outside)`` where the centroid is the median
    latitude and longitude of the remaining rows (state centroid: decision A7 / D-10).
    """
    lat_min, lat_max, lng_min, lng_max = box
    points = pd.DataFrame(
        {
            "zip_prefix": normalize_zip(geo["geolocation_zip_code_prefix"], zip_length),
            "uf": normalize_upper(geo["geolocation_state"]),
            "lat": to_float(geo["geolocation_lat"]),
            "lng": to_float(geo["geolocation_lng"]),
        }
    )
    inside = points["lat"].between(lat_min, lat_max) & points["lng"].between(lng_min, lng_max)
    kept = points.loc[inside]

    zips = (
        kept.groupby("zip_prefix", sort=True, observed=True)[["lat", "lng"]]
        .median()
        .reset_index()
    )
    states = (
        kept.groupby("uf", sort=True, observed=True)[["lat", "lng"]]
        .median()
        .reset_index()
        .rename(columns={"lat": "centroid_lat", "lng": "centroid_lng"})
    )
    return zips, states, int((~inside).sum())


# --------------------------------------------------------------------------------------
# Pure helpers: products
# --------------------------------------------------------------------------------------
def clean_products(products, uncategorized, measure_columns, weight_column):
    """Clean the product catalog (RF-33 to RF-36).

    - Columns spelled ``lenght`` are renamed to ``length``.
    - An empty category becomes ``uncategorized`` (``sem_categoria``).
    - Weight 0 g counts as missing; missing weight or measures are imputed with the
      median of the product category, or of the whole catalog when the category has no
      valid value. ``dims_imputed`` = 1 when any of them was imputed.
    - ``volume_cm3`` = length x height x width; ``product_photos_qty`` stays null if absent.
    """
    df = products.rename(columns=lambda col: col.replace("lenght", "length"))

    category = df["product_category_name"].str.strip()
    category = category.mask(category == "").fillna(uncategorized)

    measures = {col: to_float(df[col]) for col in measure_columns}
    measures[weight_column] = measures[weight_column].mask(measures[weight_column] == 0)
    measures = pd.DataFrame(measures)
    missing = measures.isna().any(axis=1)

    imputed = {}
    for col in measure_columns:
        by_category = measures[col].groupby(category, sort=True, observed=True).transform(
            "median"
        )
        imputed[col] = measures[col].fillna(by_category).fillna(measures[col].median())

    return df.assign(
        product_category_name=category,
        product_name_length=to_int(df["product_name_length"]),
        product_description_length=to_int(df["product_description_length"]),
        product_photos_qty=to_int(df["product_photos_qty"]),
        **imputed,
        volume_cm3=(
            imputed["product_length_cm"]
            * imputed["product_height_cm"]
            * imputed["product_width_cm"]
        ),
        dims_imputed=missing.astype("int64"),
    )


# --------------------------------------------------------------------------------------
# Part A: per-table cleaning
# --------------------------------------------------------------------------------------
def _clean_location(df, prefix):
    """Normalize ZIP prefix, city and state of the customer or seller table."""
    return df.assign(
        **{
            f"{prefix}_zip_code_prefix": normalize_zip(
                df[f"{prefix}_zip_code_prefix"], config.ZIP_PREFIX_LENGTH
            ),
            f"{prefix}_city": strip_accents_title(df[f"{prefix}_city"]),
            f"{prefix}_state": normalize_upper(df[f"{prefix}_state"]),
        }
    )


def _remove_exact_duplicates(tables, log):
    """Drop exact duplicates of every Olist table except the exempt ones (RF-26)."""
    out = dict(tables)
    n_items = n_other = 0
    for name in config.OLIST_FILES:
        if name in config.DEDUP_EXEMPT_TABLES:
            continue
        out[name], n_dropped = drop_exact_duplicates(out[name])
        if name == "items":
            n_items = n_dropped
        else:
            n_other += n_dropped
    log.record("exact_duplicates_items", n_items)
    log.record("exact_duplicates_other", n_other)
    return out


def _parse_dates(tables, log):
    """Parse every source datetime column with the explicit format (RF-23)."""
    out = dict(tables)
    n_unparseable = 0
    for name, columns in config.DATETIME_COLUMNS.items():
        parsed = {}
        for col in columns:
            parsed[col], n_bad = parse_datetimes(out[name][col], config.DATETIME_FORMAT)
            n_unparseable += n_bad
        out[name] = out[name].assign(**parsed)
    log.record("unparseable_dates", n_unparseable)
    return out


def _normalize_tables(tables):
    """Apply text normalization and numeric types to the transactional tables."""
    out = dict(tables)
    orders = out["orders"]
    out["orders"] = orders.assign(order_status=normalize_lower(orders["order_status"]))
    items = out["items"]
    out["items"] = items.assign(
        order_item_id=to_int(items["order_item_id"]),
        price=to_float(items["price"]),
        freight_value=to_float(items["freight_value"]),
    )
    payments = out["payments"]
    out["payments"] = payments.assign(
        payment_sequential=to_int(payments["payment_sequential"]),
        payment_type=normalize_lower(payments["payment_type"]),
        payment_installments=to_int(payments["payment_installments"]),
        payment_value=to_float(payments["payment_value"]),
    )
    reviews = out["reviews"]
    out["reviews"] = reviews.assign(review_score=to_float(reviews["review_score"]))
    out["customers"] = _clean_location(out["customers"], "customer")
    out["sellers"] = _clean_location(out["sellers"], "seller")
    return out


def clean_sources(tables, log):
    """Part A of clean: records 4 of the 19 clean rules and returns the cleaned tables.

    The raw ``geolocation`` table is replaced by ``zip_centroids`` (``zip_prefix``,
    ``lat``, ``lng``) and ``state_centroids`` (``uf``, ``centroid_lat``,
    ``centroid_lng``). Raises ``DuplicateKeyError`` before any type conversion when a
    natural key is still duplicated after removing exact duplicates (RF-27).
    """
    out = _remove_exact_duplicates(tables, log)
    for name, keys in config.NATURAL_KEYS.items():
        check_natural_key(out[name], keys, config.OLIST_FILES[name])
    out = _parse_dates(out, log)
    out = _normalize_tables(out)

    box = (
        config.BRAZIL_LAT_MIN,
        config.BRAZIL_LAT_MAX,
        config.BRAZIL_LNG_MIN,
        config.BRAZIL_LNG_MAX,
    )
    zips, states, n_outside = zip_centroids(
        out.pop("geolocation"), box, config.ZIP_PREFIX_LENGTH
    )
    log.record("coordinates_outside_box", n_outside)
    out["zip_centroids"] = zips
    out["state_centroids"] = states

    out["products"] = clean_products(
        out["products"],
        config.UNCATEGORIZED_PT,
        config.PRODUCT_MEASURE_COLUMNS,
        config.PRODUCT_WEIGHT_COLUMN,
    )
    return out


# --------------------------------------------------------------------------------------
# Pure helpers: reviews, payments and D3 exclusion rules
# --------------------------------------------------------------------------------------
def latest_review_per_order(reviews, valid_scores, sort_columns, keep_columns):
    """Keep at most one review per order (D5, RF-30, RF-31).

    Reviews with a null score or a score outside ``valid_scores`` are discarded first.
    The rest are sorted ascending by ``order_id`` and ``sort_columns`` (nulls first,
    stable sort) and the last row of each order is kept. Returns
    ``(reviews_per_order, n_out_of_range, n_extra)``; both counts are source rows.
    """
    in_range = reviews["review_score"].isin(valid_scores)
    ordered = reviews.loc[in_range].sort_values(
        ["order_id", *sort_columns], na_position="first", kind="stable"
    )
    latest = ordered.drop_duplicates(subset="order_id", keep="last")
    n_extra = len(ordered) - len(latest)
    latest = (
        latest[keep_columns]
        .assign(review_score=latest["review_score"].astype("Int64"))
        .sort_values("order_id", kind="stable")
        .reset_index(drop=True)
    )
    return latest, int((~in_range).sum()), int(n_extra)


def aggregate_payments(payments, not_defined, min_installments):
    """Aggregate payments to one row per order (D5, RF-32).

    Rows of type ``not_defined`` are excluded; 0 installments become
    ``min_installments``. Per order: ``payment_value_order`` = sum of values,
    ``main_payment_type`` = type with the largest summed value (tie: name ascending),
    ``installments`` = maximum. Returns ``(order_payments, n_not_defined, n_zero)``;
    both counts are source rows.
    """
    defined = payments["payment_type"] != not_defined
    valid = payments.loc[defined]
    zero = valid["payment_installments"] == 0
    zero = zero.fillna(False).astype("bool")
    valid = valid.assign(
        payment_installments=valid["payment_installments"].mask(zero, min_installments)
    )

    by_order = valid.groupby("order_id", sort=True, observed=True).agg(
        payment_value_order=("payment_value", "sum"),
        installments=("payment_installments", "max"),
    )
    by_type = (
        valid.groupby(["order_id", "payment_type"], sort=True, observed=True)["payment_value"]
        .sum()
        .reset_index()
        .sort_values(
            ["order_id", "payment_value", "payment_type"],
            ascending=[True, False, True],
            kind="stable",
        )
        .drop_duplicates(subset="order_id", keep="first")
        .rename(columns={"payment_type": "main_payment_type"})
    )
    order_payments = by_order.reset_index().merge(
        by_type[["order_id", "main_payment_type"]], on="order_id", how="left", validate="1:1"
    )
    order_payments = order_payments[
        ["order_id", "payment_value_order", "main_payment_type", "installments"]
    ].astype({"installments": "Int64"})
    return order_payments, int((~defined).sum()), int(zero.sum())


def apply_item_rules(items, orders, customers, sellers, products, valid_ufs, start, end):
    """Apply the 8 D3 exclusion rules in order (RF-28).

    Rules 1-5 are evaluated per line, rules 6-8 per order (every remaining line of a
    failing order). A line is counted only in the first rule it fails. ``start`` and
    ``end`` bound the purchase timestamp, both inclusive. Returns
    ``(kept_items, kept_orders, counts)`` where ``counts`` maps each D3 rule, plus
    ``orders_without_items`` (orders left without any line), to its count.
    """
    valid_ufs = list(valid_ufs)
    order_customer = items["order_id"].map(orders.set_index("order_id")["customer_id"])
    seller_state = items["seller_id"].map(sellers.set_index("seller_id")["seller_state"])
    customer_state = orders["customer_id"].map(
        customers.set_index("customer_id")["customer_state"]
    )
    purchase = orders["order_purchase_timestamp"]

    line_rules = (
        ("items_without_order", ~items["order_id"].isin(orders["order_id"])),
        (
            "orphan_reference",
            ~(
                order_customer.isin(customers["customer_id"])
                & items["seller_id"].isin(sellers["seller_id"])
                & items["product_id"].isin(products["product_id"])
            ),
        ),
        ("price_not_positive", ~(items["price"] > 0)),
        ("freight_negative", ~(items["freight_value"] >= 0)),
        ("seller_state_invalid", ~seller_state.isin(valid_ufs)),
    )
    order_rules = (
        ("estimated_date_missing", orders["order_estimated_delivery_date"].isna()),
        ("purchase_outside_period", ~purchase.between(start, end, inclusive="both")),
        ("customer_state_invalid", ~customer_state.isin(valid_ufs)),
    )

    remaining = pd.Series(True, index=items.index)
    counts = {}
    for rule, failing in line_rules:
        hit = remaining & failing
        counts[rule] = int(hit.sum())
        remaining = remaining & ~hit
    for rule, failing_orders in order_rules:
        hit = remaining & items["order_id"].isin(orders.loc[failing_orders, "order_id"])
        counts[rule] = int(hit.sum())
        remaining = remaining & ~hit

    kept_items = items.loc[remaining].reset_index(drop=True)
    has_lines = orders["order_id"].isin(kept_items["order_id"])
    kept_orders = orders.loc[has_lines].reset_index(drop=True)
    counts["orders_without_items"] = int((~has_lines).sum())
    return kept_items, kept_orders, counts


# --------------------------------------------------------------------------------------
# Part B: reviews, payments and D3 exclusion rules
# --------------------------------------------------------------------------------------
def apply_domain_rules(tables, log):
    """Part B of clean: records the other 15 of the 19 clean rules.

    D5 runs on every source review and payment row; the D3 rules then filter the order
    lines. Orders left without lines do not reach later stages: ``orders``, ``reviews``
    and payments keep only the surviving orders. The raw ``payments`` table is replaced
    by ``order_payments`` (``order_id``, ``payment_value_order``, ``main_payment_type``,
    ``installments``); ``reviews`` holds at most one review per order.
    """
    out = dict(tables)

    reviews, n_out_of_range, n_extra = latest_review_per_order(
        out["reviews"],
        config.VALID_REVIEW_SCORES,
        config.REVIEW_SORT_COLUMNS,
        config.REVIEW_KEEP_COLUMNS,
    )
    log.record("review_score_out_of_range", n_out_of_range)
    log.record("review_extra_per_order", n_extra)

    order_payments, n_not_defined, n_zero = aggregate_payments(
        out.pop("payments"), config.PAYMENT_NOT_DEFINED, config.MIN_PAYMENT_INSTALLMENTS
    )
    log.record("payment_not_defined", n_not_defined)
    log.record("payment_installments_zero", n_zero)

    items, orders, counts = apply_item_rules(
        out["items"],
        out["orders"],
        out["customers"],
        out["sellers"],
        out["products"],
        sorted(config.UF_REGION),
        config.PERIOD_START,
        config.PERIOD_END,
    )
    for rule, n_rows in counts.items():
        log.record(rule, n_rows)

    kept_orders = orders["order_id"]
    out["items"] = items
    out["orders"] = orders
    out["reviews"] = reviews.loc[reviews["order_id"].isin(kept_orders)].reset_index(drop=True)
    out["order_payments"] = order_payments.loc[
        order_payments["order_id"].isin(kept_orders)
    ].reset_index(drop=True)
    log.record(
        "orders_without_payment",
        int((~kept_orders.isin(out["order_payments"]["order_id"])).sum()),
    )

    products = out["products"]
    referenced = products["product_id"].isin(items["product_id"])
    log.record("product_dims_imputed", int(products.loc[referenced, "dims_imputed"].sum()))
    return out


def run(tables, log):
    """Clean stage: part A then part B; returns the cleaned tables."""
    return apply_domain_rules(clean_sources(tables, log), log)
