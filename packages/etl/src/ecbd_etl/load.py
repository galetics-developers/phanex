"""Load stage: write the 10 output files of D9 to ``data/processed/`` (RF-60, RF-63).

Only called after ``validate`` passed. Every file uses the D9 CSV format (UTF-8 without
BOM, LF line endings, no index, empty nulls, explicit datetime format). ``analytics_flat``
is written as ``analytics_flat.csv`` or, when ``config.ANALYTICS_FLAT_GZIP`` is set
(decision A13), as a deterministic ``analytics_flat.csv.gz``; the other variant is
removed so exactly 10 files remain. A write failure raises ``LoadError`` naming the file.
"""

from ecbd_etl import config
from ecbd_etl.quality import LoadError


def output_name(table, use_gzip):
    """Return ``(file name, compression)`` of a model table (A13 for ``analytics_flat``)."""
    name = f"{table}{config.CSV_SUFFIX}"
    if table == config.ANALYTICS_FLAT_TABLE and use_gzip:
        return f"{name}{config.GZIP_SUFFIX}", dict(config.ANALYTICS_FLAT_COMPRESSION)
    return name, None


def obsolete_flat_name(use_gzip):
    """Return the name of the ``analytics_flat`` variant that must not remain."""
    plain = f"{config.ANALYTICS_FLAT_TABLE}{config.CSV_SUFFIX}"
    return plain if use_gzip else f"{plain}{config.GZIP_SUFFIX}"


def write_csv(df, path, date_format, compression):
    """Write one CSV with the D9 format; raise ``LoadError`` naming the file on failure."""
    try:
        df.to_csv(
            path, **config.CSV_WRITE_OPTIONS, date_format=date_format, compression=compression
        )
    except (OSError, ValueError) as exc:
        raise LoadError(
            f"Could not write {path.name} in {path.parent.name}/: {exc}. "
            "Fix the cause and re-run the pipeline."
        ) from exc


def write_all(tables, log):
    """Write the 9 model tables and the 45-row quality report; return ``[(path, rows)]``."""
    missing = [table for table in config.MODEL_CONTRACTS if table not in tables]
    if missing:
        raise LoadError(f"Cannot load, missing model table(s): {', '.join(missing)}")
    # Export the log first: an incomplete log fails before any file is written.
    report = log.to_frame()

    use_gzip = config.ANALYTICS_FLAT_GZIP
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    obsolete = config.PROCESSED_DIR / obsolete_flat_name(use_gzip)
    if obsolete.exists():
        obsolete.unlink()

    written = []
    for table in config.MODEL_CONTRACTS:
        name, compression = output_name(table, use_gzip)
        path = config.PROCESSED_DIR / name
        date_format = config.CSV_DATE_FORMATS.get(table, config.DATETIME_FORMAT)
        write_csv(tables[table], path, date_format, compression)
        written.append((path, len(tables[table])))

    report_path = config.PROCESSED_DIR / config.QUALITY_REPORT_FILE
    write_csv(report, report_path, config.DATETIME_FORMAT, None)
    written.append((report_path, len(report)))
    return written
