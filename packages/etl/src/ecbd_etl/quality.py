"""Data quality: the closed list of 45 rules, the strict log, the ETL exceptions and the
14 validate rules.

The rule list is closed (RF-65, D9): the log rejects unknown rules and refuses to
export unless every rule was recorded exactly once. The export schema has four
columns: ``stage, rule, rows_affected, action``. ``evaluate_rules`` computes all 14
validate rules before deciding (RF-61); ``write_failed_log`` is the only writer of
``data/interim/`` and ``clear_failed_log`` deletes a previous failure log after load.

Units of ``rows_affected`` (see plan section 4):
- order lines: ``exact_duplicates_items``, the 8 D3 rules, ``zip_without_geolocation``,
  ``null_delivered_date_key``, ``null_payment_type_key``, ``null_review_score``;
- source rows: ``exact_duplicates_other``, ``coordinates_outside_box``,
  ``review_score_out_of_range``, ``review_extra_per_order``, ``payment_not_defined``,
  ``payment_installments_zero``;
- values: ``unparseable_dates``;
- orders: ``orders_without_items``, ``orders_without_payment`` and the four D4 delivery
  rules;
- products: ``product_dims_imputed`` and ``null_photos_qty``;
- states: ``state_without_centroid`` and ``geojson_state_mismatch``;
- problems: ``inputs_valid``.
"""

import pandas as pd

from ecbd_etl import config

LOG_COLUMNS = ["stage", "rule", "rows_affected", "action"]
VALID_ACTIONS = ("excluded", "nullified", "flagged", "imputed", "reported", "validated")

# Closed list of rules, in log order: (stage, rule, action).
RULES = (
    # extract (2)
    ("extract", "inputs_valid", "validated"),
    ("extract", "geojson_state_mismatch", "reported"),
    # clean (19)
    ("clean", "exact_duplicates_items", "excluded"),
    ("clean", "exact_duplicates_other", "excluded"),
    ("clean", "unparseable_dates", "nullified"),
    ("clean", "coordinates_outside_box", "excluded"),
    ("clean", "items_without_order", "excluded"),
    ("clean", "orphan_reference", "excluded"),
    ("clean", "price_not_positive", "excluded"),
    ("clean", "freight_negative", "excluded"),
    ("clean", "seller_state_invalid", "excluded"),
    ("clean", "estimated_date_missing", "excluded"),
    ("clean", "purchase_outside_period", "excluded"),
    ("clean", "customer_state_invalid", "excluded"),
    ("clean", "orders_without_items", "reported"),
    ("clean", "review_score_out_of_range", "excluded"),
    ("clean", "review_extra_per_order", "excluded"),
    ("clean", "payment_not_defined", "excluded"),
    ("clean", "payment_installments_zero", "imputed"),
    ("clean", "orders_without_payment", "reported"),
    ("clean", "product_dims_imputed", "imputed"),
    # enrich (5)
    ("enrich", "non_delivered_with_delivery_date", "nullified"),
    ("enrich", "delivered_missing_date", "flagged"),
    ("enrich", "delivered_before_purchase", "flagged"),
    ("enrich", "estimated_before_purchase", "nullified"),
    ("enrich", "zip_without_geolocation", "nullified"),
    # model (5)
    ("model", "null_delivered_date_key", "reported"),
    ("model", "null_payment_type_key", "reported"),
    ("model", "null_review_score", "reported"),
    ("model", "null_photos_qty", "reported"),
    ("model", "state_without_centroid", "reported"),
    # validate (14)
    ("validate", "dim_keys_unique", "validated"),
    ("validate", "fact_item_key_unique", "validated"),
    ("validate", "fact_order_item_unique", "validated"),
    ("validate", "fact_no_orphans", "validated"),
    ("validate", "fact_rows_preserved", "validated"),
    ("validate", "csp_dims_only_used_keys", "validated"),
    ("validate", "fact_within_period", "validated"),
    ("validate", "dim_date_coverage", "validated"),
    ("validate", "is_late_consistent", "validated"),
    ("validate", "delivery_nulls_consistent", "validated"),
    ("validate", "categories_mapped", "validated"),
    ("validate", "macro_categories_max_8", "validated"),
    ("validate", "dim_state_27", "validated"),
    ("validate", "fact_min_rows", "validated"),
)

RULE_COUNT = 45
_RULE_ACTION = {rule: action for _, rule, action in RULES}

# The 8 D3 exclusion rules, used by the fact_rows_preserved formula.
EXCLUSION_RULES = (
    "items_without_order",
    "orphan_reference",
    "price_not_positive",
    "freight_negative",
    "seller_state_invalid",
    "estimated_date_missing",
    "purchase_outside_period",
    "customer_state_invalid",
)

if len(RULES) != RULE_COUNT or len(_RULE_ACTION) != RULE_COUNT:
    raise RuntimeError("The closed rule list must hold exactly 45 unique rules")
if not set(EXCLUSION_RULES) <= set(_RULE_ACTION):
    raise RuntimeError("Every D3 exclusion rule must belong to the closed rule list")


class ETLError(Exception):
    """Base class of controlled pipeline failures (exit code 1, no quality log)."""


class InputError(ETLError):
    """Missing or invalid input files, raised by extract (RF-19)."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__(f"{len(self.problems)} input problem(s) found")


class DuplicateKeyError(ETLError):
    """A natural key is still duplicated with different content after de-duplication."""


class LoadError(ETLError):
    """An output file could not be written; the message names the file (RF-60)."""


class QualityLog:
    """Strict log: one record per rule of the closed list, nothing more, nothing less."""

    def __init__(self):
        self._counts = {}

    def record(self, rule, rows_affected):
        """Record the count of one rule; unknown rules and repeats are rejected."""
        if rule not in _RULE_ACTION:
            raise KeyError(f"Unknown quality rule: {rule!r}")
        if rule in self._counts:
            raise ValueError(f"Quality rule recorded twice: {rule!r}")
        if isinstance(rows_affected, bool) or int(rows_affected) != rows_affected:
            raise ValueError(f"rows_affected of {rule!r} must be an integer")
        if rows_affected < 0:
            raise ValueError(f"rows_affected of {rule!r} must not be negative")
        self._counts[rule] = int(rows_affected)

    def stage_rules(self, stage):
        """Return the rule names of a stage in log order."""
        return [rule for st, rule, _ in RULES if st == stage]

    def count(self, rule):
        """Return the recorded count of a rule; fail if it was not recorded yet."""
        if rule not in self._counts:
            raise ETLError(f"Quality rule {rule!r} has not been recorded yet")
        return self._counts[rule]

    def missing_rules(self):
        """Return the rules not recorded yet, in log order."""
        return [rule for _, rule, _ in RULES if rule not in self._counts]

    def to_frame(self):
        """Export the 45-row log; fail if any rule is missing."""
        missing = self.missing_rules()
        if missing:
            raise ETLError(
                f"Quality log is incomplete, {len(missing)} rule(s) missing: "
                + ", ".join(missing)
            )
        rows = [(st, rule, self._counts[rule], action) for st, rule, action in RULES]
        return pd.DataFrame(rows, columns=LOG_COLUMNS).astype(
            {"stage": "str", "rule": "str", "rows_affected": "int64", "action": "str"}
        )


# --------------------------------------------------------------------------------------
# Validate rules (D9): pure functions, each returns the number of failing rows (0 = pass)
# --------------------------------------------------------------------------------------
def _as_bool(mask):
    """Turn a (possibly nullable) boolean mask into a plain bool Series; NA -> False."""
    return mask.fillna(False).astype("bool")


def _key_of(timestamp):
    """YYYYMMDD integer key of one timestamp."""
    return timestamp.year * 10000 + timestamp.month * 100 + timestamp.day


def _null_or_duplicated(df, columns):
    """Rows whose ``columns`` hold a null or a value repeated in another row."""
    return df[list(columns)].isna().any(axis=1) | df.duplicated(subset=list(columns), keep=False)


def dim_keys_unique(tables, dim_keys):
    """Dimension rows with a null or repeated surrogate key or natural key."""
    n_bad = 0
    for table, keys in dim_keys.items():
        df = tables[table]
        bad = pd.Series(False, index=df.index)
        for key in keys:
            bad = bad | _null_or_duplicated(df, [key])
        n_bad += int(bad.sum())
    return n_bad


def fact_key_unique(fact, columns):
    """Fact rows whose key ``columns`` are null or repeated."""
    return int(_null_or_duplicated(fact, columns).sum())


def fact_no_orphans(fact, tables, foreign_keys, dim_keys, nullable):
    """Fact rows with at least one foreign key absent from its dimension.

    ``nullable`` maps each foreign key that may be null (Decision 4) to its companion
    column; the null is accepted only where the companion is null too (e.g. a null
    ``payment_type_key`` only for an order without valid payments), so a non-null
    value missing from the catalogue, which the lookup leaves null, counts as orphan.
    """
    bad = pd.Series(False, index=fact.index)
    for fk, dim in foreign_keys.items():
        values = fact[fk]
        present = _as_bool(values.isin(tables[dim][dim_keys[dim][0]]))
        if fk in nullable:
            allowed_null = values.isna() & fact[nullable[fk]].isna()
        else:
            allowed_null = pd.Series(False, index=fact.index)
        bad = bad | ~(present | allowed_null)
    return int(bad.sum())


def fact_rows_preserved(n_fact_rows, n_source_lines, n_exact_duplicates, n_excluded):
    """Absolute difference between the source lines and the lines accounted for (D9).

    Source lines = fact rows + exact item duplicates + lines excluded by the 8 D3 rules.
    """
    return abs(n_source_lines - (n_fact_rows + n_exact_duplicates + n_excluded))


def csp_dims_only_used_keys(fact, tables, dimensions, foreign_keys, dim_keys):
    """Rows of the customer, seller and product dimensions not used by the fact table."""
    n_unused = 0
    for dim in dimensions:
        key = dim_keys[dim][0]
        fact_columns = [fk for fk, target in foreign_keys.items() if target == dim]
        used = pd.concat([fact[col] for col in fact_columns], ignore_index=True)
        n_unused += int((~_as_bool(tables[dim][key].isin(used))).sum())
    return n_unused


def fact_within_period(fact, start, end):
    """Fact rows whose purchase date is null or outside ``[start, end]`` (day level)."""
    inside = _as_bool(fact["purchase_date_key"].between(_key_of(start), _key_of(end)))
    return int((~inside).sum())


def dim_date_coverage(fact, dim_date, start, end, date_fks, required, nullable):
    """``dim_date`` continuity plus the coverage of the fact date keys (D9).

    Counts the ``dim_date`` rows outside ``[start, end]`` or repeated, the days of the
    range absent from ``dim_date``, and the fact rows with a required date key null or
    with any non-null date key outside the range or absent from ``dim_date``.
    """
    days = pd.Series(pd.date_range(start, end, freq="D"))
    expected = days.dt.year * 10000 + days.dt.month * 100 + days.dt.day
    keys = dim_date["date_key"]
    n_dim = (
        int((~_as_bool(keys.isin(expected))).sum())
        + int(keys.duplicated(keep="first").sum())
        + int((~_as_bool(expected.isin(keys))).sum())
    )
    covered = _as_bool(keys.isin(expected))
    valid_keys = keys.loc[covered]
    bad = pd.Series(False, index=fact.index)
    for fk in date_fks:
        values = fact[fk]
        known = _as_bool(values.isin(valid_keys))
        if fk in nullable:
            bad = bad | (values.notna() & ~known)
        else:
            bad = bad | ~known
    for fk in required:
        bad = bad | fact[fk].isna()
    return n_dim + int(bad.sum())


def is_late_consistent(fact):
    """Fact rows where ``is_late`` is not exactly ``delay_days > 0`` (null when unknown)."""
    delay = fact["delay_days"]
    late = fact["is_late"]
    known = delay.notna() & late.notna()
    expected = (delay.where(known, 0) > 0).astype("int64")
    observed = late.where(known, 0).astype("int64")
    bad = (delay.isna() != late.isna()) | (known & (observed != expected))
    return int(bad.sum())


def delivery_nulls_consistent(fact, dim_order_status, delivered_status, metric_columns):
    """Fact rows whose delivery metrics break D4.

    A valid delivery (status ``delivered`` and ``delivery_data_missing`` = 0) needs every
    metric present; any other row needs every metric null. The flag must be 0 or 1, and
    0 for every status other than ``delivered``.
    """
    status = fact["order_status_key"].map(
        dim_order_status.set_index("order_status_key")["order_status"]
    )
    delivered = _as_bool(status.eq(delivered_status))
    flag = fact["delivery_data_missing"]
    valid = delivered & _as_bool(flag.eq(0))
    metrics = fact[list(metric_columns)]
    flag_ok = _as_bool(flag.isin([0, 1])) & (delivered | _as_bool(flag.eq(0)))
    bad = (
        (valid & ~metrics.notna().all(axis=1))
        | (~valid & ~metrics.isna().all(axis=1))
        | ~flag_ok
    )
    return int(bad.sum())


def categories_mapped(dim_product):
    """Products without an English category or a macro category from the map."""
    bad = pd.Series(False, index=dim_product.index)
    for col in ("category_en", "macro_category"):
        values = dim_product[col]
        bad = bad | values.isna() | _as_bool(values.astype("string").str.strip().eq(""))
    return int(bad.sum())


def macro_categories_max(dim_product, max_macro):
    """Distinct macro categories above ``max_macro`` (0 = pass)."""
    return max(0, int(dim_product["macro_category"].dropna().nunique()) - max_macro)


def dim_state_exact(dim_state, valid_ufs):
    """Rows outside the expected UF or repeated, plus expected UF missing from the table."""
    ufs = dim_state["uf"]
    extra = ~_as_bool(ufs.isin(list(valid_ufs))) | ufs.duplicated(keep="first")
    missing = set(valid_ufs) - set(ufs.dropna())
    return int(extra.sum()) + len(missing)


def fact_min_rows(fact, min_rows):
    """Rows missing to reach ``min_rows`` in the fact table (0 = pass)."""
    return max(0, min_rows - len(fact))


def evaluate_rules(tables, log, n_source_lines):
    """Evaluate ALL 14 validate rules, record each one and return the violated ones.

    Every rule is computed before anything is decided, so the first violation never
    interrupts the evaluation (RF-61). ``n_source_lines`` is the number of order-item
    lines read by extract (fact_rows_preserved).
    """
    fact = tables["fact_order_items"]
    n_excluded = sum(log.count(rule) for rule in EXCLUSION_RULES)
    results = {
        "dim_keys_unique": dim_keys_unique(tables, config.DIM_KEYS),
        "fact_item_key_unique": fact_key_unique(fact, [config.FACT_ITEM_KEY]),
        "fact_order_item_unique": fact_key_unique(fact, config.FACT_SORT_COLUMNS),
        "fact_no_orphans": fact_no_orphans(
            fact,
            tables,
            config.FACT_FOREIGN_KEYS,
            config.DIM_KEYS,
            config.NULLABLE_FOREIGN_KEYS,
        ),
        "fact_rows_preserved": fact_rows_preserved(
            len(fact), n_source_lines, log.count("exact_duplicates_items"), n_excluded
        ),
        "csp_dims_only_used_keys": csp_dims_only_used_keys(
            fact,
            tables,
            config.USED_KEY_DIMENSIONS,
            config.FACT_FOREIGN_KEYS,
            config.DIM_KEYS,
        ),
        "fact_within_period": fact_within_period(fact, config.PERIOD_START, config.PERIOD_END),
        "dim_date_coverage": dim_date_coverage(
            fact,
            tables["dim_date"],
            config.DIM_DATE_START,
            config.DIM_DATE_END,
            [fk for fk, dim in config.FACT_FOREIGN_KEYS.items() if dim == "dim_date"],
            config.REQUIRED_DATE_KEYS,
            config.NULLABLE_FOREIGN_KEYS,
        ),
        "is_late_consistent": is_late_consistent(fact),
        "delivery_nulls_consistent": delivery_nulls_consistent(
            fact,
            tables["dim_order_status"],
            config.DELIVERED_STATUS,
            config.DELIVERY_METRIC_COLUMNS,
        ),
        "categories_mapped": categories_mapped(tables["dim_product"]),
        "macro_categories_max_8": macro_categories_max(
            tables["dim_product"], config.MAX_MACRO_CATEGORIES
        ),
        "dim_state_27": dim_state_exact(tables["dim_state"], config.UF_REGION),
        "fact_min_rows": fact_min_rows(fact, config.MIN_FACT_ROWS),
    }
    rules = log.stage_rules("validate")
    if set(results) != set(rules):
        raise ETLError("The validate rules evaluated do not match the closed rule list")
    for rule in rules:
        log.record(rule, results[rule])
    return [rule for rule in rules if results[rule] > 0]


# --------------------------------------------------------------------------------------
# Failure log (the only writer of data/interim/)
# --------------------------------------------------------------------------------------
def failed_log_path():
    """Path of the failure log in ``data/interim/`` (D9)."""
    return config.INTERIM_DIR / config.QUALITY_REPORT_FAILED_FILE


def write_failed_log(log):
    """Write the full 45-row failure log to ``data/interim/`` and return its path (RF-62).

    This is the only function that creates ``data/interim/``.
    """
    report = log.to_frame()
    path = failed_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(path, **config.CSV_WRITE_OPTIONS)
    except OSError as exc:
        raise ETLError(f"Could not write the failure log {path.name}: {exc}") from exc
    return path


def clear_failed_log():
    """Delete a previous failure log if it exists (no mkdir, no write)."""
    path = failed_log_path()
    if path.exists():
        path.unlink()
