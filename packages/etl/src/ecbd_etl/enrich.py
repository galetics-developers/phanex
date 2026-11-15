"""Enrich stage: delivery metrics, distances, regions, macro categories and per-capita orders.

``run`` adds the derived variables of D4 and D6 to the cleaned tables and records the
5 enrich rules of the closed list:

- ``orders``: ``delivered_date`` (null without a valid delivery), ``delivery_days``,
  ``promised_days``, ``delay_days``, ``is_late``, ``delay_band``, ``delay_band_order``,
  ``delivery_data_missing`` and ``purchase_hour``;
- ``items``: ``item_total``, ``freight_ratio``, ``same_state`` and ``distance_km``;
- ``customers`` / ``sellers``: ``<prefix>_lat``, ``<prefix>_lng`` (ZIP centroid, null
  when the ZIP has no geolocation) and ``<prefix>_region``;
- ``reviews``: ``is_negative_review``;
- ``products``: ``category_en`` and ``macro_category`` from the category map;
- ``ibge``: typed ``population_2018``, ``region`` and ``orders_per_100k``.

Every helper above ``run`` is a pure function: no I/O, no clock, and every parameter
(status codes, bands, radius, base) arrives as an argument from ``config``.
"""

import numpy as np
import pandas as pd

from ecbd_etl import config

_ONE_DAY = pd.Timedelta(days=1)


# --------------------------------------------------------------------------------------
# Pure helpers: delivery (D4)
# --------------------------------------------------------------------------------------
def delay_band(delay_days, bands):
    """Return ``(label, order)`` of the delay band of each value (D4, plan D-7).

    ``bands`` holds ``(order, label, lower, upper)`` tuples with inclusive integer
    bounds (``None`` = unbounded). A null ``delay_days`` gives a null label and order.
    """
    values = delay_days.to_numpy(dtype="float64", na_value=np.nan)
    conditions = []
    for _, _, lower, upper in bands:
        condition = np.ones(len(values), dtype=bool)
        if lower is not None:
            condition &= values >= lower
        if upper is not None:
            condition &= values <= upper
        conditions.append(condition)
    order = np.select(conditions, [band[0] for band in bands], default=0)
    order = pd.Series(order, index=delay_days.index).astype("Int64").mask(delay_days.isna())
    label = order.map({band[0]: band[1] for band in bands})
    return label, order


def delivery_metrics(orders, delivered_status, bands):
    """Add the D4 delivery metrics to the orders; return ``(orders, counts)``.

    - ``delivery_data_missing`` = 1 when the order is delivered and its delivery date is
      null or earlier than the purchase; 0 otherwise (never null).
    - A valid delivery is a delivered order with the flag at 0. Without a valid delivery,
      ``delivered_date``, ``delivery_days``, ``delay_days``, ``is_late``, ``delay_band``
      and ``delay_band_order`` are null (never 0 or empty, RF-41).
    - ``promised_days`` is null only when the estimate is earlier than the purchase.
    - ``delay_days`` = whole days between the delivery and the estimate, both at
      midnight (negative = early); ``is_late`` = ``delay_days > 0``.

    ``counts`` maps the four D4 rules to their number of orders.
    """
    purchase = orders["order_purchase_timestamp"]
    estimated = orders["order_estimated_delivery_date"]
    delivered_at = orders["order_delivered_customer_date"]

    is_delivered = orders["order_status"].eq(delivered_status).fillna(False).astype("bool")
    has_date = delivered_at.notna()
    missing_date = is_delivered & ~has_date
    before_purchase = is_delivered & has_date & (delivered_at < purchase)
    flagged = missing_date | before_purchase
    valid = is_delivered & ~flagged
    estimated_before = estimated < purchase

    delivered_date = delivered_at.where(valid)
    delay_days = (
        (delivered_date.dt.normalize() - estimated.dt.normalize()).dt.days.astype("Int64")
    )
    label, order = delay_band(delay_days, bands)

    enriched = orders.assign(
        delivered_date=delivered_date,
        delivery_days=(delivered_date - purchase) / _ONE_DAY,
        promised_days=((estimated - purchase) / _ONE_DAY).mask(estimated_before),
        delay_days=delay_days,
        is_late=(delay_days > 0).astype("Int64"),
        delay_band=label,
        delay_band_order=order,
        delivery_data_missing=flagged.astype("int64"),
        purchase_hour=purchase.dt.hour.astype("int64"),
    )
    counts = {
        "non_delivered_with_delivery_date": int((~is_delivered & has_date).sum()),
        "delivered_missing_date": int(missing_date.sum()),
        "delivered_before_purchase": int(before_purchase.sum()),
        "estimated_before_purchase": int(estimated_before.sum()),
    }
    return enriched, counts


# --------------------------------------------------------------------------------------
# Pure helpers: geography
# --------------------------------------------------------------------------------------
def haversine_km(lat1, lng1, lat2, lng2, radius_km):
    """Great-circle distance in km between two points given in degrees (vectorized).

    Any null coordinate gives a null distance (NaN propagates).
    """
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    half_dphi = (phi2 - phi1) / 2.0
    half_dlmb = np.radians(np.asarray(lng2) - np.asarray(lng1)) / 2.0
    a = np.sin(half_dphi) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(half_dlmb) ** 2
    return 2.0 * radius_km * np.arcsin(np.minimum(1.0, np.sqrt(a)))


def attach_location(df, prefix, zip_centroids, uf_region):
    """Add ``<prefix>_lat``, ``<prefix>_lng`` and ``<prefix>_region`` to a location table.

    Coordinates are the centroid of ``<prefix>_zip_code_prefix`` (null when the ZIP has
    no geolocation inside the box); the region comes from ``<prefix>_state``.
    """
    zip_column = f"{prefix}_zip_code_prefix"
    coordinates = zip_centroids.rename(
        columns={"zip_prefix": zip_column, "lat": f"{prefix}_lat", "lng": f"{prefix}_lng"}
    )
    located = df.merge(coordinates, on=zip_column, how="left", validate="m:1")
    return located.assign(
        **{f"{prefix}_region": located[f"{prefix}_state"].map(uf_region)}
    )


def line_geography(items, orders, customers, sellers, radius_km):
    """Add ``same_state`` (0/1) and ``distance_km`` to each order line.

    The customer is the one of the line's order; the distance joins the ZIP centroids of
    seller and customer and is null when either is missing. Returns
    ``(items, n_without_distance)``, the count being order lines.
    """
    lines = (
        items[["order_id", "seller_id"]]
        .merge(orders[["order_id", "customer_id"]], on="order_id", how="left", validate="m:1")
        .merge(
            customers[["customer_id", "customer_state", "customer_lat", "customer_lng"]],
            on="customer_id",
            how="left",
            validate="m:1",
        )
        .merge(
            sellers[["seller_id", "seller_state", "seller_lat", "seller_lng"]],
            on="seller_id",
            how="left",
            validate="m:1",
        )
    )
    distance = haversine_km(
        lines["seller_lat"].to_numpy(dtype="float64"),
        lines["seller_lng"].to_numpy(dtype="float64"),
        lines["customer_lat"].to_numpy(dtype="float64"),
        lines["customer_lng"].to_numpy(dtype="float64"),
        radius_km,
    )
    same_state = lines["customer_state"].eq(lines["seller_state"]).fillna(False)
    enriched = items.assign(
        same_state=same_state.astype("int64").to_numpy(),
        distance_km=distance,
    )
    return enriched, int(np.isnan(distance).sum())


# --------------------------------------------------------------------------------------
# Pure helpers: line measures, satisfaction, categories and per-capita orders
# --------------------------------------------------------------------------------------
def item_measures(items):
    """Add ``item_total`` = price + freight and ``freight_ratio`` = freight / price."""
    return items.assign(
        item_total=items["price"] + items["freight_value"],
        freight_ratio=items["freight_value"] / items["price"],
    )


def negative_review(reviews, max_score):
    """Add ``is_negative_review`` (1 when ``review_score <= max_score``, else 0)."""
    return reviews.assign(
        is_negative_review=(reviews["review_score"] <= max_score).astype("Int64")
    )


def attach_macro_category(products, category_map):
    """Add ``category_en`` and ``macro_category`` from the category map (D2, RF-46).

    A category absent from the map keeps both columns null; the ``categories_mapped``
    validate rule reports it.
    """
    mapping = category_map[["category_pt", "category_en", "macro_category"]].rename(
        columns={"category_pt": "product_category_name"}
    )
    return products.merge(mapping, on="product_category_name", how="left", validate="m:1")


def orders_per_100k(orders, customers, ibge, canceled_status, base, uf_region):
    """Return the IBGE table typed, with ``region`` and ``orders_per_100k`` (Decision 18).

    ``orders_per_100k`` = distinct orders with a status other than ``canceled_status``
    among ``orders`` (the orders present in the fact table), by customer UF, divided by
    the 2018 population and multiplied by ``base``. A UF without orders gets 0.
    """
    states = ibge.assign(
        uf=ibge["uf"].str.strip(),
        state_name=ibge["state_name"].str.strip(),
        population_2018=pd.to_numeric(ibge["population_2018"].str.strip()).astype("int64"),
    )
    active = orders.loc[orders["order_status"].ne(canceled_status), ["order_id", "customer_id"]]
    active_uf = active["customer_id"].map(customers.set_index("customer_id")["customer_state"])
    n_orders = (
        active.assign(uf=active_uf)
        .groupby("uf", sort=True, observed=True)["order_id"]
        .nunique()
    )
    order_count = states["uf"].map(n_orders).fillna(0).astype("int64")
    return (
        states.assign(
            region=states["uf"].map(uf_region),
            orders_per_100k=order_count / states["population_2018"] * base,
        )
        .sort_values("uf", kind="stable")
        .reset_index(drop=True)
    )


# --------------------------------------------------------------------------------------
# Stage
# --------------------------------------------------------------------------------------
def run(tables, log):
    """Enrich stage: records the 5 enrich rules and returns the enriched tables."""
    out = dict(tables)

    orders, counts = delivery_metrics(
        out["orders"], config.DELIVERED_STATUS, config.DELAY_BANDS
    )
    for rule, n_orders in counts.items():
        log.record(rule, n_orders)

    customers = attach_location(
        out["customers"], "customer", out["zip_centroids"], config.UF_REGION
    )
    sellers = attach_location(out["sellers"], "seller", out["zip_centroids"], config.UF_REGION)
    items, n_without_distance = line_geography(
        item_measures(out["items"]), orders, customers, sellers, config.EARTH_RADIUS_KM
    )
    log.record("zip_without_geolocation", n_without_distance)

    out["orders"] = orders
    out["items"] = items
    out["customers"] = customers
    out["sellers"] = sellers
    out["reviews"] = negative_review(out["reviews"], config.NEGATIVE_REVIEW_MAX_SCORE)
    out["products"] = attach_macro_category(out["products"], out["category_map"])
    out["ibge"] = orders_per_100k(
        orders,
        customers,
        out["ibge"],
        config.CANCELED_STATUS,
        config.PER_CAPITA_BASE,
        config.UF_REGION,
    )
    return out
