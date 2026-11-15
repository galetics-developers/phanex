"""Extract stage: check every input, then read the sources as text.

The checks (existence, headers, IBGE / calendar / category-map validations) collect
ALL problems and raise a single ``InputError`` before anything is transformed (RF-19).
Nothing here writes to disk; ``data/raw/`` is only ever read (RF-18).
"""

import json

import pandas as pd

from ecbd_etl import config
from ecbd_etl.quality import InputError


def display_path(path):
    """Return a path relative to the repository root, with forward slashes."""
    try:
        return path.relative_to(config.ROOT).as_posix()
    except ValueError:
        return path.as_posix()


# --------------------------------------------------------------------------------------
# Pure validation functions (no I/O)
# --------------------------------------------------------------------------------------
def check_files(paths):
    """Return one problem message per missing file, naming the expected folder.

    ``paths`` is an iterable of ``pathlib.Path`` objects.
    """
    problems = []
    for path in paths:
        if not path.is_file():
            problems.append(
                f"Missing input file: {path.name} (expected in {display_path(path.parent)}/)"
            )
    return problems


def check_columns(columns, required, label):
    """Return a problem message when required columns are absent from ``columns``."""
    absent = [col for col in required if col not in set(columns)]
    if absent:
        return [f"{label}: missing column(s) {', '.join(absent)}"]
    return []


def validate_ibge(df):
    """IBGE table: exactly the 27 unique UF and an integer population > 0."""
    label = display_path(config.IBGE_FILE)
    problems = check_columns(df.columns, config.IBGE_COLUMNS, label)
    if problems:
        return problems
    ufs = df["uf"].astype("string").str.strip()
    expected = set(config.UF_REGION)
    if ufs.isna().any() or ufs.duplicated().any():
        problems.append(f"{label}: 'uf' has empty or duplicated values")
    found = set(ufs.dropna())
    if found != expected:
        absent = sorted(expected - found)
        extra = sorted(found - expected)
        problems.append(
            f"{label}: expected exactly the {len(expected)} Brazilian UF "
            f"(missing: {absent or 'none'}; unexpected: {extra or 'none'})"
        )
    population = pd.to_numeric(df["population_2018"], errors="coerce")
    bad = population.isna() | (population <= 0) | (population != population.round())
    if bad.any():
        problems.append(
            f"{label}: 'population_2018' must be an integer > 0 ({int(bad.sum())} bad value(s))"
        )
    return problems


def validate_calendar(df, start, end):
    """Calendar: interpretable, unique dates inside ``[start, end]`` and a non-empty event."""
    label = display_path(config.CALENDAR_FILE)
    problems = check_columns(df.columns, config.CALENDAR_COLUMNS, label)
    if problems:
        return problems
    dates = pd.to_datetime(df["date"], format=config.DATE_FORMAT, errors="coerce")
    n_bad = int(dates.isna().sum())
    if n_bad:
        problems.append(f"{label}: {n_bad} date(s) not interpretable as {config.DATE_FORMAT}")
    valid = dates.dropna()
    if valid.duplicated().any():
        problems.append(f"{label}: {int(valid.duplicated().sum())} duplicated date(s)")
    outside = int(((valid < start) | (valid > end)).sum())
    if outside:
        problems.append(
            f"{label}: {outside} date(s) outside {start.date()} .. {end.date()}"
        )
    events = df["event"].astype("string").str.strip()
    if events.isna().any() or (events == "").any():
        problems.append(f"{label}: 'event' has empty values")
    return problems


def validate_category_map(df, max_macro):
    """Category map: three columns, no empty macro category, at most ``max_macro`` values."""
    label = display_path(config.CATEGORY_MAP_FILE)
    problems = check_columns(df.columns, config.CATEGORY_MAP_COLUMNS, label)
    if problems:
        return problems
    macro = df["macro_category"].astype("string").str.strip()
    n_empty = int((macro.isna() | (macro == "")).sum())
    if n_empty:
        problems.append(f"{label}: {n_empty} row(s) with an empty 'macro_category'")
    n_distinct = int(macro.dropna().loc[lambda s: s != ""].nunique())
    if n_distinct > max_macro:
        problems.append(
            f"{label}: {n_distinct} distinct macro categories, the maximum is {max_macro}"
        )
    return problems


def geojson_state_mismatch(ufs_geojson, ufs):
    """Count the UF present in only one of the two collections."""
    return len(set(ufs_geojson) ^ set(ufs))


# --------------------------------------------------------------------------------------
# I/O functions
# --------------------------------------------------------------------------------------
def _read_csv_text(path, usecols=None):
    """Read a CSV with every column as text; only the empty string is a null."""
    return pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        na_values=[""],
        encoding="utf-8-sig",
        usecols=usecols,
    )


def read_geojson_ufs(path):
    """Return the list of UF found in the GeoJSON features."""
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return [
        str(feature.get("properties", {}).get(config.GEOJSON_UF_PROPERTY, "")).strip()
        for feature in data.get("features", [])
    ]


def _olist_paths():
    return {name: config.RAW_OLIST_DIR / file for name, file in config.OLIST_FILES.items()}


def required_input_paths():
    """Return every mandatory input path (D1) in a fixed order."""
    return [
        *_olist_paths().values(),
        config.IBGE_FILE,
        config.CALENDAR_FILE,
        config.CATEGORY_MAP_FILE,
    ]


def check_inputs():
    """Run every input check; return ``(problems, mismatch)`` without raising.

    ``mismatch`` is the count of UF that differ between the optional GeoJSON and the
    expected UF (0 when the GeoJSON is absent).
    """
    problems = check_files(required_input_paths())

    for name, path in _olist_paths().items():
        if not path.is_file():
            continue
        try:
            header = pd.read_csv(path, nrows=0, dtype=str, encoding="utf-8-sig")
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            problems.append(f"{display_path(path)}: cannot read header ({exc})")
            continue
        problems += check_columns(header.columns, config.OLIST_REQUIRED_COLUMNS[name], path.name)

    manual = (
        (config.IBGE_FILE, lambda df: validate_ibge(df)),
        (
            config.CALENDAR_FILE,
            lambda df: validate_calendar(df, config.DIM_DATE_START, config.DIM_DATE_END),
        ),
        (
            config.CATEGORY_MAP_FILE,
            lambda df: validate_category_map(df, config.MAX_MACRO_CATEGORIES),
        ),
    )
    for path, validator in manual:
        if not path.is_file():
            continue
        try:
            problems += validator(_read_csv_text(path))
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            problems.append(f"{display_path(path)}: cannot read file ({exc})")

    mismatch = 0
    if config.GEOJSON_FILE.is_file():
        try:
            mismatch = geojson_state_mismatch(
                read_geojson_ufs(config.GEOJSON_FILE), config.UF_REGION
            )
        except (OSError, ValueError) as exc:
            problems.append(f"{display_path(config.GEOJSON_FILE)}: cannot read GeoJSON ({exc})")
    return problems, mismatch


def read_tables():
    """Read every validated source as text; geolocation only with the needed columns."""
    tables = {}
    for name, path in _olist_paths().items():
        usecols = config.GEOLOCATION_USECOLS if name == "geolocation" else None
        tables[name] = _read_csv_text(path, usecols=usecols)
    tables["ibge"] = _read_csv_text(config.IBGE_FILE)
    tables["calendar"] = _read_csv_text(config.CALENDAR_FILE)
    tables["category_map"] = _read_csv_text(config.CATEGORY_MAP_FILE)
    return tables


def run(log):
    """Extract stage: validate all inputs, record its rules and return the raw tables.

    Raises ``InputError`` listing every problem before anything is read in full.
    """
    problems, mismatch = check_inputs()
    if problems:
        raise InputError(problems)
    if not config.GEOJSON_FILE.is_file():
        print(
            f"WARNING: optional file {config.GEOJSON_FILE.name} not found in "
            f"{display_path(config.GEOJSON_FILE.parent)}/ (only the notebook needs it)."
        )
    elif mismatch:
        print(f"WARNING: GeoJSON UF differ from the expected UF in {mismatch} case(s).")
    log.record("inputs_valid", 0)
    log.record("geojson_state_mismatch", mismatch)
    return read_tables()
