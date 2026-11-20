"""Single source of configuration for the ETL pipeline.

Every path, the analysis period, the random seed, the Brazil bounding box, the
UF -> region map and the fixed catalogs live here and nowhere else (RF-10).
All paths derive from the location of this file, never from absolute strings.
"""

from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------------------
# Reproducibility
# --------------------------------------------------------------------------------------
SEED = 42

# --------------------------------------------------------------------------------------
# Paths (derived from this file: <root>/packages/etl/src/ecbd_etl/config.py)
# --------------------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = ROOT / "data"
RAW_OLIST_DIR = DATA_DIR / "raw" / "olist"
RAW_EXTERNAL_DIR = DATA_DIR / "raw" / "external"
REFERENCE_DIR = DATA_DIR / "reference"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

# Logical name -> file name of the nine Olist CSV files (D1).
OLIST_FILES = {
    "orders": "olist_orders_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "translation": "product_category_name_translation.csv",
    "geolocation": "olist_geolocation_dataset.csv",
}

# Team-provided and project-written inputs (D1).
IBGE_FILE = RAW_EXTERNAL_DIR / "ibge_population_2018.csv"
CALENDAR_FILE = RAW_EXTERNAL_DIR / "commercial_calendar.csv"
CATEGORY_MAP_FILE = REFERENCE_DIR / "category_macro_map.csv"
GEOJSON_FILE = REFERENCE_DIR / "brazil-states.geojson"  # optional (notebook only)
GEOJSON_UF_PROPERTY = "sigla"

# Required header of every input CSV (checked in extract, HU-6).
OLIST_REQUIRED_COLUMNS = {
    "orders": [
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "items": [
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
    ],
    "payments": [
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
    ],
    "reviews": [
        "review_id",
        "order_id",
        "review_score",
        "review_comment_title",
        "review_comment_message",
        "review_creation_date",
        "review_answer_timestamp",
    ],
    "customers": [
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
    ],
    "sellers": [
        "seller_id",
        "seller_zip_code_prefix",
        "seller_city",
        "seller_state",
    ],
    "products": [
        "product_id",
        "product_category_name",
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ],
    "translation": ["product_category_name", "product_category_name_english"],
    "geolocation": [
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
    ],
}
# The geolocation table is large (~1M rows): only these columns are read.
GEOLOCATION_USECOLS = [
    "geolocation_zip_code_prefix",
    "geolocation_lat",
    "geolocation_lng",
    "geolocation_state",
]
IBGE_COLUMNS = ["uf", "state_name", "population_2018"]
CALENDAR_COLUMNS = ["date", "event"]
CATEGORY_MAP_COLUMNS = ["category_pt", "category_en", "macro_category"]

# --------------------------------------------------------------------------------------
# Analysis period and date handling
# --------------------------------------------------------------------------------------
PERIOD_START = pd.Timestamp("2017-01-01 00:00:00")
PERIOD_END = pd.Timestamp("2018-08-31 23:59:59")  # inclusive
DIM_DATE_START = pd.Timestamp("2016-01-01")
DIM_DATE_END = pd.Timestamp("2018-12-31")

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"

# Source datetime columns parsed in clean with DATETIME_FORMAT (RF-23).
DATETIME_COLUMNS = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "items": ["shipping_limit_date"],
    "reviews": ["review_creation_date", "review_answer_timestamp"],
}

# --------------------------------------------------------------------------------------
# Clean: duplicates and natural keys (RF-26, RF-27)
# --------------------------------------------------------------------------------------
# Tables exempt from exact de-duplication (the per-ZIP median uses every row, RF-38).
DEDUP_EXEMPT_TABLES = ("geolocation",)
# Natural keys that must be unique after removing exact duplicates. Reviews (resolved by
# D5) and geolocation (no key) are deliberately absent.
NATURAL_KEYS = {
    "items": ["order_id", "order_item_id"],
    "orders": ["order_id"],
    "customers": ["customer_id"],
    "products": ["product_id"],
    "sellers": ["seller_id"],
    "payments": ["order_id", "payment_sequential"],
    "translation": ["product_category_name"],
}

# Product weight and measures imputed with the category median (RF-34).
PRODUCT_MEASURE_COLUMNS = [
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
]
PRODUCT_WEIGHT_COLUMN = "product_weight_g"

# --------------------------------------------------------------------------------------
# Clean: reviews and payments (D5)
# --------------------------------------------------------------------------------------
# Valid review scores; any other value (or null) is discarded before choosing the review.
VALID_REVIEW_SCORES = (1, 2, 3, 4, 5)
# Ascending sort (nulls first) whose last row per order is the review kept (full tie-break).
REVIEW_SORT_COLUMNS = ["review_creation_date", "review_answer_timestamp", "review_id"]
# Columns kept from the chosen review (free-text comments are dropped, D-14).
REVIEW_KEEP_COLUMNS = [
    "order_id",
    "review_id",
    "review_score",
    "review_creation_date",
    "review_answer_timestamp",
]
# Payment rows of this type are excluded; 0 installments are imputed with the minimum.
PAYMENT_NOT_DEFINED = "not_defined"
MIN_PAYMENT_INSTALLMENTS = 1

# --------------------------------------------------------------------------------------
# Geography
# --------------------------------------------------------------------------------------
# Bounding box of Brazil used to discard bad geolocation rows (RF-37).
BRAZIL_LAT_MIN = -34.0
BRAZIL_LAT_MAX = 6.0
BRAZIL_LNG_MIN = -74.0
BRAZIL_LNG_MAX = -34.0

# ZIP code prefixes are text of this length, left-padded with zeros (RF-22).
ZIP_PREFIX_LENGTH = 5

EARTH_RADIUS_KM = 6371.0

REGION_NORTE = "Norte"
REGION_NORDESTE = "Nordeste"
REGION_CENTRO_OESTE = "Centro-Oeste"
REGION_SUDESTE = "Sudeste"
REGION_SUL = "Sul"

# The 27 federative units mapped to their macro-region.
UF_REGION = {
    "AC": REGION_NORTE,
    "AP": REGION_NORTE,
    "AM": REGION_NORTE,
    "PA": REGION_NORTE,
    "RO": REGION_NORTE,
    "RR": REGION_NORTE,
    "TO": REGION_NORTE,
    "AL": REGION_NORDESTE,
    "BA": REGION_NORDESTE,
    "CE": REGION_NORDESTE,
    "MA": REGION_NORDESTE,
    "PB": REGION_NORDESTE,
    "PE": REGION_NORDESTE,
    "PI": REGION_NORDESTE,
    "RN": REGION_NORDESTE,
    "SE": REGION_NORDESTE,
    "DF": REGION_CENTRO_OESTE,
    "GO": REGION_CENTRO_OESTE,
    "MT": REGION_CENTRO_OESTE,
    "MS": REGION_CENTRO_OESTE,
    "ES": REGION_SUDESTE,
    "MG": REGION_SUDESTE,
    "RJ": REGION_SUDESTE,
    "SP": REGION_SUDESTE,
    "PR": REGION_SUL,
    "RS": REGION_SUL,
    "SC": REGION_SUL,
}

# --------------------------------------------------------------------------------------
# Delivery delay bands (D4): (order, label, lower bound, upper bound), inclusive, in days.
# --------------------------------------------------------------------------------------
DELAY_BANDS = [
    (1, "≤ -10 (very early)", None, -10),
    (2, "-9 to -1 (early)", -9, -1),
    (3, "0 to 3 (on time / slight)", 0, 3),
    (4, "4 to 10 (late)", 4, 10),
    (5, "> 10 (very late)", 11, None),
]

# --------------------------------------------------------------------------------------
# Enrich: delivery status, satisfaction and per-capita orders (D4, D6, Decision 18)
# --------------------------------------------------------------------------------------
DELIVERED_STATUS = "delivered"
CANCELED_STATUS = "canceled"
# A review is negative when its score is at most this value (is_negative_review).
NEGATIVE_REVIEW_MAX_SCORE = 2
# orders_per_100k = orders / population x this base.
PER_CAPITA_BASE = 100_000

# --------------------------------------------------------------------------------------
# Fixed catalogs (D7): key -> (code, English label)
# --------------------------------------------------------------------------------------
PAYMENT_TYPES = {
    1: ("credit_card", "Credit card"),
    2: ("boleto", "Boleto"),
    3: ("voucher", "Voucher"),
    4: ("debit_card", "Debit card"),
}
ORDER_STATUSES = {
    1: ("created", "Created"),
    2: ("approved", "Approved"),
    3: ("invoiced", "Invoiced"),
    4: ("processing", "Processing"),
    5: ("shipped", "Shipped"),
    6: ("delivered", "Delivered"),
    7: ("unavailable", "Unavailable"),
    8: ("canceled", "Canceled"),
}
COMPLETED_STATUS = DELIVERED_STATUS

# Fixed English names (no locale dependency, for determinism).
MONTH_NAMES = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}
WEEKDAY_NAMES = {
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
    7: "Sunday",
}
# dim_date: weekday numbers (1 = Monday) that count as weekend, and the year-month format.
WEEKEND_WEEKDAYS = (6, 7)
YEAR_MONTH_FORMAT = "%Y-%m"

# --------------------------------------------------------------------------------------
# Model: column contracts, in their exact order (D6, D7, D8)
# --------------------------------------------------------------------------------------
# Fact rows are sorted by this natural key; order_item_key is the position 1..n.
FACT_SORT_COLUMNS = ["order_id", "order_item_id"]
FACT_COLUMNS = [
    # keys
    "order_item_key",
    "order_id",
    "order_item_id",
    # foreign keys (9)
    "purchase_date_key",
    "delivered_date_key",
    "estimated_date_key",
    "customer_key",
    "customer_state_key",
    "seller_key",
    "product_key",
    "payment_type_key",
    "order_status_key",
    # amounts
    "price",
    "freight_value",
    "item_total",
    "freight_ratio",
    "payment_value_order",
    "installments",
    # time
    "purchase_hour",
    # delivery
    "delivery_days",
    "promised_days",
    "delay_days",
    "is_late",
    "delay_band",
    "delay_band_order",
    "delivery_data_missing",
    # satisfaction
    "review_score",
    "is_negative_review",
    # geography
    "distance_km",
    "same_state",
]
DIM_DATE_COLUMNS = [
    "date_key",
    "date",
    "year",
    "quarter",
    "month_number",
    "month_name",
    "year_month",
    "weekday_number",
    "weekday_name",
    "is_weekend",
    "commercial_event",
]
DIM_CUSTOMER_COLUMNS = [
    "customer_key",
    "customer_id",
    "customer_unique_id",
    "city",
    "state",
    "region",
    "zip_prefix",
    "lat",
    "lng",
]
DIM_STATE_COLUMNS = [
    "customer_state_key",
    "uf",
    "state_name",
    "region",
    "population_2018",
    "centroid_lat",
    "centroid_lng",
]
DIM_SELLER_COLUMNS = [
    "seller_key",
    "seller_id",
    "seller_city",
    "seller_state",
    "seller_region",
    "lat",
    "lng",
]
DIM_PRODUCT_COLUMNS = [
    "product_key",
    "product_id",
    "category_pt",
    "category_en",
    "macro_category",
    "weight_g",
    "volume_cm3",
    "photos_qty",
    "dims_imputed",
]
DIM_PAYMENT_TYPE_COLUMNS = ["payment_type_key", "payment_type", "payment_label"]
DIM_ORDER_STATUS_COLUMNS = ["order_status_key", "order_status", "status_label", "is_completed"]
# Fact columns without keys (no foreign keys, no surrogate key), then dates, calendar of
# the purchase date, customer, seller, product, payment and status attributes (D8).
ANALYTICS_FLAT_COLUMNS = [
    "order_id",
    "order_item_id",
    "price",
    "freight_value",
    "item_total",
    "freight_ratio",
    "payment_value_order",
    "installments",
    "purchase_hour",
    "delivery_days",
    "promised_days",
    "delay_days",
    "is_late",
    "delay_band",
    "delay_band_order",
    "delivery_data_missing",
    "review_score",
    "is_negative_review",
    "distance_km",
    "same_state",
    # dates (with time)
    "purchase_date",
    "delivered_date",
    "estimated_date",
    # calendar of the purchase date
    "year",
    "quarter",
    "month_number",
    "month_name",
    "year_month",
    "weekday_number",
    "weekday_name",
    "is_weekend",
    "commercial_event",
    # customer
    "customer_id",
    "customer_unique_id",
    "customer_city",
    "uf",
    "state_name",
    "region",
    "customer_zip_prefix",
    "customer_lat",
    "customer_lng",
    "population_2018",
    "orders_per_100k",
    # seller
    "seller_id",
    "seller_city",
    "seller_state",
    "seller_region",
    "seller_lat",
    "seller_lng",
    # product
    "product_id",
    "category_pt",
    "category_en",
    "macro_category",
    "weight_g",
    "volume_cm3",
    "photos_qty",
    "dims_imputed",
    # payment and status
    "payment_type",
    "payment_label",
    "order_status",
    "status_label",
    "is_completed",
]
# The 9 model tables in D9 order, with their column contract.
MODEL_CONTRACTS = {
    "fact_order_items": FACT_COLUMNS,
    "dim_date": DIM_DATE_COLUMNS,
    "dim_customer": DIM_CUSTOMER_COLUMNS,
    "dim_seller": DIM_SELLER_COLUMNS,
    "dim_product": DIM_PRODUCT_COLUMNS,
    "dim_state": DIM_STATE_COLUMNS,
    "dim_payment_type": DIM_PAYMENT_TYPE_COLUMNS,
    "dim_order_status": DIM_ORDER_STATUS_COLUMNS,
    "analytics_flat": ANALYTICS_FLAT_COLUMNS,
}

# --------------------------------------------------------------------------------------
# Validate: keys checked by the 14 validate rules (D9)
# --------------------------------------------------------------------------------------
# Dimension -> (surrogate key, natural key); both must be unique and non-null.
DIM_KEYS = {
    "dim_date": ("date_key", "date"),
    "dim_customer": ("customer_key", "customer_id"),
    "dim_seller": ("seller_key", "seller_id"),
    "dim_product": ("product_key", "product_id"),
    "dim_state": ("customer_state_key", "uf"),
    "dim_payment_type": ("payment_type_key", "payment_type"),
    "dim_order_status": ("order_status_key", "order_status"),
}
FACT_ITEM_KEY = "order_item_key"
# Fact foreign key -> referenced dimension (joined on that dimension's surrogate key).
FACT_FOREIGN_KEYS = {
    "purchase_date_key": "dim_date",
    "delivered_date_key": "dim_date",
    "estimated_date_key": "dim_date",
    "customer_key": "dim_customer",
    "customer_state_key": "dim_state",
    "seller_key": "dim_seller",
    "product_key": "dim_product",
    "payment_type_key": "dim_payment_type",
    "order_status_key": "dim_order_status",
}
# Foreign keys allowed to be null (Decision 4) -> fact column that is null in exactly the
# rows where that null is legitimate (no valid delivery / no valid payments). A null key
# whose companion is present (e.g. a payment type outside the catalogue) is an orphan.
# Every other foreign key must reference a row.
NULLABLE_FOREIGN_KEYS = {
    "delivered_date_key": "delivery_days",
    "payment_type_key": "payment_value_order",
}
# Date keys that must never be null (dim_date_coverage).
REQUIRED_DATE_KEYS = ("purchase_date_key", "estimated_date_key")
# Dimensions that keep only the keys used by the fact table (Decision 10).
USED_KEY_DIMENSIONS = ("dim_customer", "dim_seller", "dim_product")
# Fact columns that are all present for a valid delivery and all null otherwise (D4).
DELIVERY_METRIC_COLUMNS = (
    "delivered_date_key",
    "delivery_days",
    "delay_days",
    "is_late",
    "delay_band",
    "delay_band_order",
)

# --------------------------------------------------------------------------------------
# Thresholds and output decisions
# --------------------------------------------------------------------------------------
MIN_FACT_ROWS = 5000
MAX_MACRO_CATEGORIES = 8
UNCATEGORIZED_PT = "sem_categoria"
UNCATEGORIZED_MACRO = "uncategorized"

# A13: write analytics_flat as gzip because the plain CSV exceeded FLAT_SIZE_LIMIT_BYTES.
ANALYTICS_FLAT_GZIP = True
FLAT_SIZE_LIMIT_BYTES = 50_000_000
ANALYTICS_FLAT_TABLE = "analytics_flat"
ANALYTICS_FLAT_COMPRESSION = {"method": "gzip", "mtime": 0}
GZIP_SUFFIX = ".gz"

# File names written by load (D9): each model table is written as "<table>.csv".
CSV_SUFFIX = ".csv"
QUALITY_REPORT_FILE = "data_quality_report.csv"
QUALITY_REPORT_FAILED_FILE = "data_quality_report_failed.csv"

# CSV format of every output (D9): UTF-8 without BOM, LF, no index, empty nulls.
CSV_WRITE_OPTIONS = {"index": False, "encoding": "utf-8", "lineterminator": "\n"}
# Datetime columns are written with DATETIME_FORMAT, except these tables.
CSV_DATE_FORMATS = {"dim_date": DATE_FORMAT}

# --------------------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------------------
STAGES = ("extract", "clean", "enrich", "model", "validate", "load")
PROJECT_NAME = "ECBD Olist Insights - ETL pipeline"
