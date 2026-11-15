# 02 — Data dictionary

Describes every column of the 10 files that the pipeline (`python scripts/run_pipeline.py`) writes to `data/processed/`. The examples are real values from the last successful run; so are the counts (rows, nulls). The relationships between tables are in [`04-star-schema.md`](04-star-schema.md).

## 0. Conventions

### Files

| File | Rows | Columns | Grain |
| :-- | --: | --: | :-- |
| `fact_order_items.csv` | 112 279 | 30 | One order line |
| `dim_date.csv` | 1 096 | 11 | One day (2016-01-01 to 2018-12-31, continuous) |
| `dim_customer.csv` | 98 353 | 9 | One `customer_id` (in Olist, one per order) used by the fact table |
| `dim_seller.csv` | 3 068 | 7 | One seller used by the fact table |
| `dim_product.csv` | 32 787 | 9 | One product used by the fact table |
| `dim_state.csv` | 27 | 7 | One Brazilian federative unit (UF) |
| `dim_payment_type.csv` | 4 | 3 | One payment type (fixed catalog) |
| `dim_order_status.csv` | 8 | 4 | One order status (fixed catalog) |
| `analytics_flat.csv.gz` | 112 279 | 62 | One order line, with every attribute already joined (no keys) |
| `data_quality_report.csv` | 45 | 4 | One quality rule |

### CSV format

- UTF-8 without BOM, LF line endings, no index column, comma separator, dot as decimal mark and no thousands separator.
- Null = empty field. Booleans as `0`/`1`.
- Datetime `YYYY-MM-DD HH:MM:SS`; `dim_date.date` as `YYYY-MM-DD`.
- `analytics_flat` is written gzip-compressed (`analytics_flat.csv.gz`) because the plain CSV was 77.6 MB; inside, it has the same format.

### Types used in this document

| Type | Meaning |
| :-- | :-- |
| integer | Whole number, never null |
| integer (null) | Whole number that may be empty; written without decimals (for example `20170920`) |
| decimal | Real number, never null |
| decimal (null) | Real number that may be empty |
| 0/1 | Integer boolean flag; "(null)" if it may be empty |
| text | String; "(null)" if it may be empty |
| datetime | `YYYY-MM-DD HH:MM:SS`; "(null)" if it may be empty |
| date | `YYYY-MM-DD` |

### Source names

Source columns are cited as `table.column`, with these abbreviations of the Olist CSV files: `orders` = `olist_orders_dataset`, `items` = `olist_order_items_dataset`, `payments` = `olist_order_payments_dataset`, `reviews` = `olist_order_reviews_dataset`, `customers` = `olist_customers_dataset`, `sellers` = `olist_sellers_dataset`, `products` = `olist_products_dataset`, `translation` = `product_category_name_translation`, `geolocation` = `olist_geolocation_dataset`. The team's own inputs are `ibge` = `data/raw/external/ibge_population_2018.csv`, `calendar` = `data/raw/external/commercial_calendar.csv` and `category_map` = `data/reference/category_macro_map.csv`. "Generated" means a column created by the pipeline with no source column.

**ZIP centroid:** median of `geolocation.geolocation_lat` and `geolocation.geolocation_lng` over all rows of a ZIP prefix (not deduplicated) that fall inside the Brazil bounding box (latitude −34 to 6, longitude −74 to −34).

## 1. `fact_order_items.csv`

Fact table. Rows sorted by `order_id`, `order_item_id`. The examples are the first row (order `00010242fe8c5a6d1ba2dd792cb16214`, delivered).

| Column | Type | Description | Example | Source | Formula / rule |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `order_item_key` | integer | Surrogate key of the order line | `1` | Generated | Position 1..n after sorting by `order_id`, `order_item_id` |
| `order_id` | text | Order identifier (32 hexadecimal characters) | `00010242fe8c5a6d1ba2dd792cb16214` | `items.order_id` | — |
| `order_item_id` | integer | Line number within the order (1..21) | `1` | `items.order_item_id` | — |
| `purchase_date_key` | integer | `dim_date` key of the purchase date (active relationship) | `20170913` | `orders.order_purchase_timestamp` | year × 10000 + month × 100 + day |
| `delivered_date_key` | integer (null) | `dim_date` key of the delivery to the customer (inactive relationship). Null without a valid delivery (2 407 lines) | `20170920` | `orders.order_delivered_customer_date` | YYYYMMDD of the delivery; null if the status is not `delivered` or `delivery_data_missing = 1` |
| `estimated_date_key` | integer | `dim_date` key of the estimated delivery date (inactive relationship); never null | `20170929` | `orders.order_estimated_delivery_date` | YYYYMMDD of the estimated date |
| `customer_key` | integer | `dim_customer` key (customer of the order) | `23451` | Generated | Lookup of `orders.customer_id` in `dim_customer` |
| `customer_state_key` | integer | `dim_state` key (customer's UF) | `19` | Generated | Lookup of `customers.customer_state` in `dim_state.uf` (19 = RJ) |
| `seller_key` | integer | `dim_seller` key | `852` | Generated | Lookup of `items.seller_id` in `dim_seller` |
| `product_key` | integer | `dim_product` key | `8590` | Generated | Lookup of `items.product_id` in `dim_product` |
| `payment_type_key` | integer (null) | `dim_payment_type` key of the order's main payment method. Null if the order has no valid payments (0 lines in the last run) | `1` | `payments.payment_type` | Type with the highest accumulated amount in the order (tie: name ascending), excluding `not_defined` |
| `order_status_key` | integer | `dim_order_status` key | `6` | `orders.order_status` | Lookup of the lower-case status in `dim_order_status` |
| `price` | decimal | Line price in R$ (> 0) | `58.9` | `items.price` | Lines with a null price or a price ≤ 0 are excluded |
| `freight_value` | decimal | Line freight in R$ (≥ 0; 0 is valid) | `13.29` | `items.freight_value` | Lines with a null freight or a freight < 0 are excluded |
| `item_total` | decimal | Total amount of the line in R$ | `72.19` | Derived | `price + freight_value` |
| `freight_ratio` | decimal | Freight as a share of the price | `0.22563667232597623` | Derived | `freight_value / price` |
| `payment_value_order` | decimal (null) | Total amount paid **for the order** in R$ (repeated on every line) | `72.19` | `payments.payment_value` | Sum of the order's `payment_value`, excluding `not_defined`; null without valid payments |
| `installments` | integer (null) | Maximum number of installments of the order (repeated on every line) | `2` | `payments.payment_installments` | Maximum per order; 0 installments are imputed as 1 |
| `purchase_hour` | integer | Purchase hour (0–23) | `8` | `orders.order_purchase_timestamp` | Hour of the purchase datetime |
| `delivery_days` | decimal (null) | Days (fractional) between purchase and delivery | `7.614421296296296` | `orders` (purchase and delivery) | `(delivery − purchase) / 1 day`; null without a valid delivery |
| `promised_days` | decimal (null) | Days (fractional) promised between purchase and estimated date | `15.625671296296296` | `orders` (purchase and estimated) | `(estimated − purchase) / 1 day`; null if the estimated date is earlier than the purchase (0 cases) |
| `delay_days` | integer (null) | Whole days of delay against the estimated date; **negative = early** | `-9` | `orders` (delivery and estimated) | `date(delivery) − date(estimated)`, both at midnight; null without a valid delivery |
| `is_late` | 0/1 (null) | Late delivery | `0` | Derived | `1` if `delay_days > 0`; null without a valid delivery |
| `delay_band` | text (null) | Delay band | `-9 to -1 (early)` | Derived | `≤ -10 (very early)`, `-9 to -1 (early)`, `0 to 3 (on time / slight)`, `4 to 10 (late)`, `> 10 (very late)` according to `delay_days` |
| `delay_band_order` | integer (null) | Order 1–5 of `delay_band` (to sort axes and legends) | `2` | Derived | 1 = very early … 5 = very late |
| `delivery_data_missing` | 0/1 | Invalid-delivery flag: `delivered` order without a delivery date or with a delivery earlier than the purchase (8 lines) | `0` | Derived | `1` if `order_status = delivered` and (delivery null or delivery < purchase); `0` otherwise; never null |
| `review_score` | integer (null) | Score 1–5 of the order's most recent review (repeated on every line); not a foreign key | `5` | `reviews.review_score` | Review with the latest `review_creation_date`, then `review_answer_timestamp`, then `review_id`; null without a review (936 lines) |
| `is_negative_review` | 0/1 (null) | Negative review (repeated on every line) | `0` | Derived | `1` if `review_score <= 2`; null without a review |
| `distance_km` | decimal (null) | Straight-line distance between seller and customer, in km | `301.22920531102295` | ZIP centroids (`geolocation`) | Haversine with a 6371 km radius between the seller's and the customer's ZIP centroids; null if either is missing (555 lines) |
| `same_state` | 0/1 | Seller and customer in the same UF | `0` | `customers.customer_state`, `sellers.seller_state` | `1` if `customer_state = seller_state` |

## 2. `dim_date.csv`

Continuous calendar from 2016-01-01 to 2018-12-31, with English names. Example: the first row (2016-01-01), except `commercial_event`, taken from 2017-11-24.

| Column | Type | Description | Example | Source | Formula / rule |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `date_key` | integer | Natural key of the day | `20160101` | Generated | year × 10000 + month × 100 + day |
| `date` | date | Date | `2016-01-01` | Generated | Continuous daily range |
| `year` | integer | Year | `2016` | Generated | Year of `date` |
| `quarter` | integer | Quarter (1–4) | `1` | Generated | Quarter of `date` |
| `month_number` | integer | Month (1–12) | `1` | Generated | Month of `date` |
| `month_name` | text | Month name in English (January … December) | `January` | Generated | Fixed table of names (independent of the system locale) |
| `year_month` | text | Year-month | `2016-01` | Generated | `YYYY-MM` |
| `weekday_number` | integer | Day of the week, 1 = Monday … 7 = Sunday | `5` | Generated | ISO day of the week |
| `weekday_name` | text | Day name in English (Monday … Sunday) | `Friday` | Generated | Fixed table of names |
| `is_weekend` | 0/1 | Saturday or Sunday | `0` | Generated | `1` if `weekday_number` ∈ {6, 7} |
| `commercial_event` | text (null) | Commercial event of the day (at most one): Black Friday, Christmas, Mother's Day or World Cup 2018; empty on 1 055 days | `Black Friday` | `calendar.event` | Join by date with the commercial calendar |

## 3. `dim_customer.csv`

One row per `customer_id` used by the fact table, in ascending `customer_id` order. Example: the first row.

| Column | Type | Description | Example | Source | Formula / rule |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `customer_key` | integer | Surrogate key | `1` | Generated | 1..n in ascending `customer_id` order |
| `customer_id` | text | Customer identifier **per order** (in Olist every order has its own `customer_id`) | `00012a2ce6f8dcda20d059ce98491703` | `customers.customer_id` | — |
| `customer_unique_id` | text | Person identifier; groups the orders of the same customer | `248ffe10d632bebe4f7267f1f44844c9` | `customers.customer_unique_id` | — |
| `city` | text | Customer's city, without accents and in title case | `Osasco` | `customers.customer_city` | Remove accents (NFKD) and title case |
| `state` | text | Customer's UF (2 letters) | `SP` | `customers.customer_state` | Upper case without spaces; must be one of the 27 UF |
| `region` | text | Brazilian region | `Sudeste` | Derived | UF → region map (Norte, Nordeste, Centro-Oeste, Sudeste, Sul) |
| `zip_prefix` | text | 5-character ZIP prefix with leading zeros | `06273` | `customers.customer_zip_code_prefix` | `zfill(5)` |
| `lat` | decimal (null) | Latitude of the ZIP centroid | `-23.49931402937304` | `geolocation` | ZIP centroid; null if the ZIP has no geolocation (275 customers) |
| `lng` | decimal (null) | Longitude of the ZIP centroid | `-46.76754974911981` | `geolocation` | ZIP centroid; null if the ZIP has no geolocation |

## 4. `dim_seller.csv`

One row per seller used by the fact table, in ascending `seller_id` order. Example: the first row.

| Column | Type | Description | Example | Source | Formula / rule |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `seller_key` | integer | Surrogate key | `1` | Generated | 1..n in ascending `seller_id` order |
| `seller_id` | text | Seller identifier | `0015a82c2db000af6aaaf3ae2ecb0532` | `sellers.seller_id` | — |
| `seller_city` | text | Seller's city, without accents and in title case | `Santo Andre` | `sellers.seller_city` | Remove accents (NFKD) and title case |
| `seller_state` | text | Seller's UF | `SP` | `sellers.seller_state` | Upper case without spaces; must be one of the 27 UF |
| `seller_region` | text | Seller's region | `Sudeste` | Derived | UF → region map |
| `lat` | decimal (null) | Latitude of the seller's ZIP centroid | `-23.641516814251723` | `geolocation` | ZIP centroid; null without geolocation (7 sellers) |
| `lng` | decimal (null) | Longitude of the seller's ZIP centroid | `-46.54210469718399` | `geolocation` | ZIP centroid; null without geolocation |

## 5. `dim_product.csv`

One row per product used by the fact table, in ascending `product_id` order. Example: the first row.

| Column | Type | Description | Example | Source | Formula / rule |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `product_key` | integer | Surrogate key | `1` | Generated | 1..n in ascending `product_id` order |
| `product_id` | text | Product identifier | `00066f42aeeb9f3007548bb9d3f33c38` | `products.product_id` | — |
| `category_pt` | text | Category in Portuguese; `sem_categoria` if it was empty | `perfumaria` | `products.product_category_name` | Empty → `sem_categoria` |
| `category_en` | text | Category in English | `perfumery` | `category_map.category_en` | Join by `category_pt` (based on `translation`; the two categories without an original translation, `pc_gamer` and `portateis_cozinha_e_preparadores_de_alimentos`, were translated by hand; `sem_categoria` → `uncategorized`) |
| `macro_category` | text | Macro category in English (8 values, including `uncategorized`) | `Fashion & Beauty` | `category_map.macro_category` | Join by `category_pt` |
| `weight_g` | decimal | Weight in grams (> 0) | `300.0` | `products.product_weight_g` | Weight 0 or null → median of the category (or of the catalog if the category has no values) |
| `volume_cm3` | decimal | Volume in cm³ | `5120.0` | `products.product_length_cm`, `product_height_cm`, `product_width_cm` | length × height × width (null dimensions imputed like the weight) |
| `photos_qty` | integer (null) | Number of product photos; null if missing in the source (610 products) | `6` | `products.product_photos_qty` | Kept null, not imputed |
| `dims_imputed` | 0/1 | Weight or any dimension imputed | `0` | Derived | `1` if weight, length, height or width was imputed (6 products) |

## 6. `dim_state.csv`

The 27 UF in alphabetical order. Example: the first row.

| Column | Type | Description | Example | Source | Formula / rule |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `customer_state_key` | integer | Surrogate key | `1` | Generated | 1..27 in alphabetical order of `uf` |
| `uf` | text | Federative unit code | `AC` | `ibge.uf` | — |
| `state_name` | text | State name | `Acre` | `ibge.state_name` | — |
| `region` | text | Brazilian region | `Norte` | Derived | UF → region map |
| `population_2018` | integer | Estimated resident population in 2018 | `869265` | `ibge.population_2018` | — |
| `centroid_lat` | decimal (null) | Latitude of the state centroid | `-9.96204619900166` | `geolocation` | Median of `geolocation_lat` over the UF's rows inside the Brazil bounding box; null without rows (0 states) |
| `centroid_lng` | decimal (null) | Longitude of the state centroid | `-67.83063844823705` | `geolocation` | Median of `geolocation_lng`, same filter |

## 7. `dim_payment_type.csv`

Fixed catalog of 4 rows: 1 `credit_card` Credit card, 2 `boleto` Boleto, 3 `voucher` Voucher, 4 `debit_card` Debit card.

| Column | Type | Description | Example | Source | Formula / rule |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `payment_type_key` | integer | Fixed key 1–4 | `1` | Generated (fixed catalog) | — |
| `payment_type` | text | Payment type code, in lower case | `credit_card` | Fixed catalog (values of `payments.payment_type`) | `not_defined` is not part of the catalog: those payments are excluded |
| `payment_label` | text | Display label in English | `Credit card` | Fixed catalog | — |

## 8. `dim_order_status.csv`

Fixed catalog of 8 rows: 1 `created` Created, 2 `approved` Approved, 3 `invoiced` Invoiced, 4 `processing` Processing, 5 `shipped` Shipped, 6 `delivered` Delivered, 7 `unavailable` Unavailable, 8 `canceled` Canceled.

| Column | Type | Description | Example | Source | Formula / rule |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `order_status_key` | integer | Fixed key 1–8 | `1` | Generated (fixed catalog) | — |
| `order_status` | text | Status code, in lower case | `created` | Fixed catalog (values of `orders.order_status`) | — |
| `status_label` | text | Display label in English | `Created` | Fixed catalog | — |
| `is_completed` | 0/1 | Completed order | `0` | Derived | `1` only for `delivered` |

## 9. `analytics_flat.csv.gz`

Flat table for the notebook: one row per order line, in the same order and with the same 112 279 rows as the fact table, without surrogate or foreign keys, so charts need no joins. Read it with `pd.read_csv("data/processed/analytics_flat.csv.gz", compression="gzip", dtype={"customer_zip_prefix": str})`. Examples: the first row (same order as in the fact table), except `commercial_event`.

| Column | Type | Description | Example | Source | Formula / rule |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `order_id` | text | Order identifier | `00010242fe8c5a6d1ba2dd792cb16214` | `fact_order_items.order_id` | — |
| `order_item_id` | integer | Line number within the order | `1` | `fact_order_items.order_item_id` | — |
| `price` | decimal | Line price in R$ | `58.9` | `fact_order_items.price` | Same as in the fact table |
| `freight_value` | decimal | Line freight in R$ | `13.29` | `fact_order_items.freight_value` | Same as in the fact table |
| `item_total` | decimal | Total amount of the line in R$ | `72.19` | `fact_order_items.item_total` | `price + freight_value` |
| `freight_ratio` | decimal | Freight as a share of the price | `0.22563667232597623` | `fact_order_items.freight_ratio` | `freight_value / price` |
| `payment_value_order` | decimal (null) | Amount paid for the order (repeated per line) | `72.19` | `fact_order_items.payment_value_order` | Sum of the order's payments |
| `installments` | integer (null) | Maximum installments of the order (repeated per line) | `2` | `fact_order_items.installments` | Maximum per order |
| `purchase_hour` | integer | Purchase hour (0–23) | `8` | `fact_order_items.purchase_hour` | Hour of `purchase_date` |
| `delivery_days` | decimal (null) | Days between purchase and delivery | `7.614421296296296` | `fact_order_items.delivery_days` | `(delivery − purchase) / 1 day` |
| `promised_days` | decimal (null) | Promised days | `15.625671296296296` | `fact_order_items.promised_days` | `(estimated − purchase) / 1 day` |
| `delay_days` | integer (null) | Days of delay (negative = early) | `-9` | `fact_order_items.delay_days` | `date(delivery) − date(estimated)` |
| `is_late` | 0/1 (null) | Late delivery | `0` | `fact_order_items.is_late` | `delay_days > 0` |
| `delay_band` | text (null) | Delay band | `-9 to -1 (early)` | `fact_order_items.delay_band` | Bands of §1 |
| `delay_band_order` | integer (null) | Order 1–5 of the band | `2` | `fact_order_items.delay_band_order` | — |
| `delivery_data_missing` | 0/1 | Invalid-delivery flag | `0` | `fact_order_items.delivery_data_missing` | See §1 |
| `review_score` | integer (null) | Review score (repeated per line) | `5` | `fact_order_items.review_score` | Most recent review |
| `is_negative_review` | 0/1 (null) | Negative review (repeated per line) | `0` | `fact_order_items.is_negative_review` | `review_score <= 2` |
| `distance_km` | decimal (null) | Seller–customer distance in km | `301.22920531102295` | `fact_order_items.distance_km` | Haversine |
| `same_state` | 0/1 | Seller and customer in the same UF | `0` | `fact_order_items.same_state` | — |
| `purchase_date` | datetime | Purchase datetime | `2017-09-13 08:59:02` | `orders.order_purchase_timestamp` | — |
| `delivered_date` | datetime (null) | Datetime of the delivery to the customer; null without a valid delivery | `2017-09-20 23:43:48` | `orders.order_delivered_customer_date` | Null if the status is not `delivered` or `delivery_data_missing = 1` |
| `estimated_date` | datetime | Estimated delivery date | `2017-09-29 00:00:00` | `orders.order_estimated_delivery_date` | — |
| `year` | integer | Purchase year | `2017` | `dim_date.year` (via `purchase_date_key`) | — |
| `quarter` | integer | Purchase quarter | `3` | `dim_date.quarter` | — |
| `month_number` | integer | Purchase month | `9` | `dim_date.month_number` | — |
| `month_name` | text | Name of the purchase month | `September` | `dim_date.month_name` | — |
| `year_month` | text | Purchase year-month | `2017-09` | `dim_date.year_month` | — |
| `weekday_number` | integer | Purchase day of the week (1 = Monday) | `3` | `dim_date.weekday_number` | — |
| `weekday_name` | text | Name of the purchase day | `Wednesday` | `dim_date.weekday_name` | — |
| `is_weekend` | 0/1 | Purchase on a weekend | `0` | `dim_date.is_weekend` | — |
| `commercial_event` | text (null) | Commercial event of the purchase day | `World Cup 2018` | `dim_date.commercial_event` | Empty on 103 922 lines |
| `customer_id` | text | Customer of the order | `3ce436f183e68e07877b285a838db11a` | `dim_customer.customer_id` (via `customer_key`) | — |
| `customer_unique_id` | text | Customer person | `871766c5855e863f6eccc05f988b23cb` | `dim_customer.customer_unique_id` | — |
| `customer_city` | text | Customer's city | `Campos Dos Goytacazes` | `dim_customer.city` | — |
| `uf` | text | Customer's UF | `RJ` | `dim_state.uf` (via `customer_state_key`) | — |
| `state_name` | text | Name of the customer's state | `Rio de Janeiro` | `dim_state.state_name` | — |
| `region` | text | Customer's region | `Sudeste` | `dim_customer.region` | — |
| `customer_zip_prefix` | text | Customer's ZIP prefix (5 characters) | `28013` | `dim_customer.zip_prefix` | — |
| `customer_lat` | decimal (null) | Latitude of the customer's ZIP centroid | `-21.762829433744784` | `dim_customer.lat` | Null on 303 lines |
| `customer_lng` | decimal (null) | Longitude of the customer's ZIP centroid | `-41.3106050334548` | `dim_customer.lng` | Null on 303 lines |
| `population_2018` | integer | 2018 population of the customer's state (repeated per line) | `17159960` | `dim_state.population_2018` | — |
| `orders_per_100k` | decimal | Orders per 100 000 inhabitants of the customer's state (static; repeated per line) | `73.74143063270543` | Derived (`fact_order_items`, `ibge`) | Distinct orders of the fact table with an `order_status` other than `canceled`, by customer UF, ÷ `population_2018` × 100 000 |
| `seller_id` | text | Seller of the line | `48436dade18ac8b2bce089ec2a041202` | `dim_seller.seller_id` (via `seller_key`) | — |
| `seller_city` | text | Seller's city | `Volta Redonda` | `dim_seller.seller_city` | — |
| `seller_state` | text | Seller's UF | `SP` | `dim_seller.seller_state` | — |
| `seller_region` | text | Seller's region | `Sudeste` | `dim_seller.seller_region` | — |
| `seller_lat` | decimal (null) | Latitude of the seller's ZIP centroid | `-22.49841879739165` | `dim_seller.lat` | Null on 253 lines |
| `seller_lng` | decimal (null) | Longitude of the seller's ZIP centroid | `-44.12527158572528` | `dim_seller.lng` | Null on 253 lines |
| `product_id` | text | Product of the line | `4244733e06e7ecb4970a6e2683c13e61` | `dim_product.product_id` (via `product_key`) | — |
| `category_pt` | text | Category in Portuguese | `cool_stuff` | `dim_product.category_pt` | — |
| `category_en` | text | Category in English | `cool_stuff` | `dim_product.category_en` | — |
| `macro_category` | text | Macro category in English | `Leisure & Culture` | `dim_product.macro_category` | — |
| `weight_g` | decimal | Product weight in g | `650.0` | `dim_product.weight_g` | — |
| `volume_cm3` | decimal | Product volume in cm³ | `3528.0` | `dim_product.volume_cm3` | — |
| `photos_qty` | integer (null) | Product photos | `4` | `dim_product.photos_qty` | Null on 1 601 lines |
| `dims_imputed` | 0/1 | Weight or dimensions imputed | `0` | `dim_product.dims_imputed` | — |
| `payment_type` | text | Code of the main payment type | `credit_card` | `dim_payment_type.payment_type` (via `payment_type_key`) | — |
| `payment_label` | text | Payment type label | `Credit card` | `dim_payment_type.payment_label` | — |
| `order_status` | text | Order status code | `delivered` | `dim_order_status.order_status` (via `order_status_key`) | — |
| `status_label` | text | Status label | `Delivered` | `dim_order_status.status_label` | — |
| `is_completed` | 0/1 | Completed order | `1` | `dim_order_status.is_completed` | `1` only for `delivered` |

## 10. `data_quality_report.csv`

Quality log of the run: one row for each of the 45 rules of the closed list, including those with 0 rows, in stage order. Each rule and its counts are explained in `docs/03`.

| Column | Type | Description | Example | Source | Formula / rule |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `stage` | text | Stage that logs the rule: `extract`, `clean`, `enrich`, `model` or `validate` | `extract` | Generated | — |
| `rule` | text | Rule name (unique) | `inputs_valid` | Generated | Closed list of 45 rules |
| `rows_affected` | integer | Affected elements. The unit depends on the rule: order lines (default), orders, source rows, values, products or states. In `validate`, failing rows (0 = pass) | `0` | Generated | Count of the rule; in exclusion rules 6–8 (`estimated_date_missing`, `purchase_outside_period`, `customer_state_invalid`) it only counts the order's lines not already counted by another rule |
| `action` | text | Action: `excluded`, `nullified`, `flagged`, `imputed`, `reported` or `validated` | `validated` | Generated | — |

## 11. Field taxonomy

Classification of the analytical variables (R5). Surrogate keys (`*_key`) and identifiers (`*_id`) are **identifiers**, not analysis variables. There is no `price_band`.

| Type | Fields |
| :-- | :-- |
| Continuous | `price`, `freight_value`, `item_total`, `freight_ratio`, `payment_value_order`, `delivery_days`, `promised_days`, `delay_days` (integer, interval scale), `distance_km`, `weight_g`, `volume_cm3`, `population_2018`, `orders_per_100k`; discrete counts: `installments`, `photos_qty`, `order_item_id` |
| Categorical (nominal) | `order_status`, `status_label`, `payment_type`, `payment_label`, `category_pt`, `category_en`, `macro_category`, `commercial_event`; 0/1 flags: `is_late`, `is_negative_review`, `delivery_data_missing`, `same_state`, `dims_imputed`, `is_completed`, `is_weekend` |
| Ordinal | `review_score` (1–5), `delay_band` with its order `delay_band_order` (1–5) |
| Temporal | `purchase_date`, `delivered_date`, `estimated_date`, `date`, `date_key`, `purchase_date_key`, `delivered_date_key`, `estimated_date_key`, `year`, `quarter`, `month_number`, `month_name`, `year_month`, `weekday_number`, `weekday_name`, `purchase_hour` |
| Geospatial | `lat`, `lng`, `customer_lat`, `customer_lng`, `seller_lat`, `seller_lng`, `centroid_lat`, `centroid_lng`, `zip_prefix`, `customer_zip_prefix`, `uf`, `state`, `seller_state`, `state_name`, `region`, `seller_region`, `city`, `customer_city`, `seller_city` |

## 12. Usage rules and warnings

### `canceled` and `unavailable` statuses

- The fact table **keeps every order status** present in the valid lines. In the last run: `delivered` 109 880 lines (96 211 orders), `shipped` 1 174, `canceled` 527 (448 orders), `processing` 355, `invoiced` 340 and `approved` 3.
- `canceled`: stays in the fact table with `is_completed = 0`, `delivery_data_missing = 0` and every delivery metric null (even if the source has a delivery date: rule `non_delivered_with_delivery_date`). It does not count in `orders_per_100k`.
- `unavailable` (and `created`): they are in the `dim_order_status` catalog but **have no lines** in the fact table of the last run: their orders have no items in the source (counted in `orders_without_items`) or fall outside the period. If they appeared, they would be treated like any other non-delivered status.
- The delivery metrics (`delivery_days`, `delay_days`, `is_late`, `delay_band`) only exist for `delivered` orders with `delivery_data_missing = 0`. **Late delivery rate denominator:** distinct orders with a non-null `is_late`.

### GMV definition (dashboard)

- The dashboard **GMV** is the sum of `price` over the lines of every order whose status is not `canceled`. Freight is **not** part of the GMV.
- Freight is a separate measure (sum of `freight_value`, same filter).
- `item_total` = `price` + `freight_value`; it is the total amount of the line, not the GMV.
- See [`04-star-schema.md`](04-star-schema.md) for the grain and relationships the measures rely on, and `apps/bi-dashboard/dax/measures.dax` for the measure definitions.

### Allowed nulls

| Column | Where | When it is null | Count (last run) |
| :-- | :-- | :-- | --: |
| `delivered_date_key` | fact | No valid delivery (status other than `delivered`, or flag 1) | 2 407 lines |
| `payment_type_key` | fact | Order without valid payments | 0 lines |
| `review_score` | fact and flat | Order without a valid review | 936 lines (744 orders) |
| `photos_qty` | `dim_product` and flat | Missing in the source | 610 products |

All four are allowed with no "unknown" members in the dimensions; `validate` ignores them when looking for orphans only in their legitimate case: a null `delivered_date_key` with a null `delivery_days`, and a null `payment_type_key` with a null `payment_value_order` (a non-null payment type outside the catalog is an orphan). The following are also null by definition: `delivered_date`, `delivery_days`, `delay_days`, `is_late`, `delay_band` and `delay_band_order` without a valid delivery; `promised_days` if the estimated date is earlier than the purchase; `is_negative_review`, `payment_value_order` and `installments` together with `review_score` / `payment_type_key`; `distance_km` and coordinates when the ZIP centroid is missing; `commercial_event` on days without an event. A null is never replaced by 0 or by an empty string in the model.

### Do not sum or average order-level fields at line level

The fact table has a **line** grain: an order with several lines (9 767 orders in the last run) repeats the order's values on each of them. These fields **are repeated on every line of the order**: `payment_value_order`, `installments`, `review_score`, `is_negative_review`, `delay_days`, `delivery_days` and `promised_days` (and, in the flat table, also `population_2018` and `orders_per_100k`).

- They are **never** summed or averaged directly over the lines: that over-represents orders with more lines.
- They are aggregated **per order**: distinct count of `order_id` (in Power BI, `DISTINCTCOUNT` / `AVERAGEX` over `VALUES(order_id)`), or by deduplicating on `order_id` before averaging (in pandas, `drop_duplicates("order_id")`).
- `price`, `freight_value` and `item_total` can be summed per line (they are line amounts; the GMV uses `price` only, see above).

### Distinct customers

**Distinct customers = distinct count of `customer_unique_id`** (95 121 in the last run). `customer_id` identifies the customer of one order, and its distinct count equals the number of orders (98 353). Repeat purchases are measured by grouping on `customer_unique_id`.

### Source

Olist data, *Brazilian E-Commerce Public Dataset by Olist* (Kaggle, `olistbr/brazilian-ecommerce`, CC BY-NC-SA 4.0), original archive versioned in `data/raw/olist/`; IBGE 2018 population (SIDRA, table 6579); commercial calendar and category map authored by the team. The files in `data/processed/` are distributed under CC BY-NC-SA 4.0 (see `data/LICENSE`).

### Known limitations

- **Period:** only purchases from 2017-01-01 to 2018-08-31 (the first purchase present is from 2017-01-05 and the last from 2018-08-29). Undelivered orders (for example, 1 097 `shipped`, spread over the whole period) are left out of the delivery metrics.
- **Approximate coordinates:** coordinates are ZIP-prefix centroids (5 digits), not exact addresses, and `distance_km` is a straight-line distance, not the real route. 555 lines have no distance because the customer's or the seller's ZIP has no geolocation.
- **Source inconsistencies:** Olist contains some inconsistent city/UF combinations that the ETL does not fix (for example, the first line has a seller in `Volta Redonda` with UF `SP`).
- **Static population:** `population_2018` is the 2018 estimate and is used for the whole period; `orders_per_100k` is static (computed once over the full fact table) and does not change with filters.
- **Reviews:** only the most recent review per order is kept (551 additional reviews discarded).
- **Category map:** the macro categories are a team proposal; `uncategorized` groups 610 products without a category in the source.
- **Number format:** decimals are written at full precision, without rounding. 8 values come out in **scientific notation** in the star schema (7 latitudes of `dim_customer.lat`, e.g. `-4.367379244740171e-05`, and one `fact_order_items.freight_ratio`, `8.849557522123894e-05`), and the same 8 in `analytics_flat` (`customer_lat`, `freight_ratio`). pandas and Power BI (en-US regional settings) read them correctly; other tools may need adjustments.
- **Reading with pandas without types:** `zip_prefix` and `customer_zip_prefix` would be read as integers and lose the leading zero (read them with `dtype=str`), and the "integer (null)" columns would be read as decimals (`20170920.0`); use `dtype="Int64"` if you need integers.
