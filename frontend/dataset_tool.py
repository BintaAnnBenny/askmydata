"""Helpers for the "upload your own data" mode.

Each user's file lives in its own in-memory DuckDB database. Nothing is saved
to disk or to Supabase, and it disappears when the session ends.
"""
import io
import re
import threading

import duckdb
import pandas as pd
import sqlglot
from sqlglot import exp

TABLE = "data"
MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 200_000
MAX_COLS = 60

# Functions that read files or change settings. Blocked even though DuckDB
# external access is also switched off.
BLOCKED_FUNCTION_PREFIXES = (
    "read_", "scan_", "glob", "copy", "pragma", "export", "import",
    "load", "install", "attach", "detach", "query", "sniff",
)


# ---------- loading ----------

class UploadError(ValueError):
    """An upload problem, with a message that tells the user what to do."""


def _read_csv(data):
    last = None
    for encoding in ("utf-8-sig", "latin-1"):
        first_line = data.decode(encoding, errors="ignore").split("\n", 1)[0]
        # Only let pandas guess the delimiter when the header really contains one;
        # on a single-column file the guess is unreliable.
        seps = (None, ",") if any(d in first_line for d in (",", ";", "\t", "|")) else (",",)
        for sep in seps:
            try:
                return pd.read_csv(io.BytesIO(data), sep=sep, engine="python", encoding=encoding)
            except UnicodeDecodeError as e:
                last = e
                break
            except Exception as e:
                last = e
    raise last


def clean_columns(columns):
    used, cleaned = set(), []
    for i, col in enumerate(columns):
        name = re.sub(r"[^0-9a-zA-Z]+", "_", str(col).strip()).strip("_").lower()
        if not name:
            name = f"column_{i + 1}"
        if name[0].isdigit():
            name = "c_" + name
        base, k = name, 2
        while name in used:
            name = f"{base}_{k}"
            k += 1
        used.add(name)
        cleaned.append(name)
    return cleaned


def load_file(filename, data):
    """Return (DataFrame, notes). Raises UploadError with a message the user can act on."""
    if len(data) > MAX_BYTES:
        raise UploadError("That file is larger than 10 MB. Upload a smaller file or a sample of the rows.")

    lower = filename.lower()
    try:
        if lower.endswith(".csv"):
            df = _read_csv(data)
        elif lower.endswith((".xlsx", ".xlsm")):
            df = pd.read_excel(io.BytesIO(data))
        else:
            raise UploadError("Upload a .csv or .xlsx file.")
    except UploadError:
        raise
    except Exception:
        raise UploadError("That file couldn't be read. Check that it is a valid CSV or Excel file with a header row.")

    df = df.dropna(how="all").dropna(axis=1, how="all")
    if df.empty:
        raise UploadError("That file has no data rows.")
    if len(df) > MAX_ROWS:
        raise UploadError(f"That file has more than {MAX_ROWS:,} rows. Upload a smaller file.")
    if len(df.columns) > MAX_COLS:
        raise UploadError(f"That file has more than {MAX_COLS} columns. Remove the columns you don't need.")

    return prepare(df)


DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S",
    "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S",
    "%m-%d-%Y", "%m/%d/%Y", "%m-%d-%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S",
)


def parse_dates(series):
    """Parse a text column as dates. Picks the single format that fits the most values.

    Ambiguous values like 09-11-2013 are read day-first, but a column that
    contains something like 11-25-2013 is detected as month-first.
    """
    text = series.astype("string").str.strip()
    best, best_rate = None, 0.0
    for fmt in DATE_FORMATS:  # day-first formats come before month-first, so ties go to day-first
        rate = pd.to_datetime(text, errors="coerce", format=fmt).notna().mean()
        if rate > best_rate + 1e-9:
            best, best_rate = pd.to_datetime(text, errors="coerce", format=fmt), rate
    if best is not None and best_rate > 0.9:
        return best
    return pd.to_datetime(text, errors="coerce", format="mixed", dayfirst=True)


def prepare(df):
    """Clean column names, parse dates and turn numeric-looking text into numbers."""
    old = [str(c) for c in df.columns]
    df = df.copy()
    df.columns = clean_columns(df.columns)
    notes = [f"{o} \u2192 {n}" for o, n in zip(old, df.columns) if o != n]

    for col in df.columns:
        series = df[col]
        if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
            continue

        # Date-like columns (by name) that mostly parse as dates.
        if re.search(r"(date|time|_dt$|timestamp)", col):
            try:
                parsed = parse_dates(series)
                if parsed.notna().mean() > 0.9:
                    df[col] = parsed
                    continue
            except Exception:
                pass

        # Text that looks numeric (e.g. "1,200") becomes a number only if at
        # least 90% of the non-empty values convert; otherwise it stays text.
        text = series.astype("string").str.strip()
        numeric = pd.to_numeric(text.str.replace(",", "", regex=False), errors="coerce")
        non_empty = text.notna() & text.ne("")
        if non_empty.any() and numeric[non_empty].notna().mean() >= 0.9:
            df[col] = numeric
        else:
            df[col] = series.where(series.isna(), series.astype(str))

    return df, notes



# ---------- database ----------

def make_connection(df):
    con = duckdb.connect(":memory:")
    con.register("src", df)
    con.execute(f"CREATE TABLE {TABLE} AS SELECT * FROM src")
    con.unregister("src")
    con.execute("SET memory_limit='400MB'")
    con.execute("SET threads=2")
    con.execute("SET enable_external_access=false")
    con.execute("SET lock_configuration=true")
    return con


def describe(con, df):
    """Return (columns_text, sample_text) to put in the prompt."""
    rows = con.execute(f"DESCRIBE {TABLE}").fetchall()
    columns_text = "\n".join(f'- "{r[0]}": {r[1]}' for r in rows)
    sample = df.head(3).copy()
    for col in sample.columns:
        sample[col] = sample[col].astype(str).str.slice(0, 40)
    return columns_text, sample.to_csv(index=False)


def is_safe_sql(sql):
    """Allow one SELECT (optionally with CTEs) that reads only the uploaded table."""
    try:
        statements = sqlglot.parse(sql, read="duckdb")
    except Exception:
        return False
    if len(statements) != 1 or statements[0] is None:
        return False
    stmt = statements[0]
    if not isinstance(stmt, (exp.Select, exp.Union)):
        return False

    for func in stmt.find_all(exp.Func):
        name = func.name if isinstance(func, exp.Anonymous) else func.sql_name()
        if str(name).lower().startswith(BLOCKED_FUNCTION_PREFIXES):
            return False

    ctes = {c.alias.lower() for c in stmt.find_all(exp.CTE)}
    real_tables = set()
    for table in stmt.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier) or table.db or table.catalog:
            return False
        if table.name.lower() in ctes:
            continue
        real_tables.add(table.name.lower())
    return bool(real_tables) and real_tables <= {TABLE}


def run_query(con, sql, timeout=20, max_rows=1000):
    """Run a query on a fresh cursor and stop it if it takes longer than `timeout` seconds."""
    cur = con.cursor()
    timer = threading.Timer(timeout, cur.interrupt)
    timer.start()
    try:
        return cur.execute(sql).fetchdf().head(max_rows)
    finally:
        timer.cancel()
