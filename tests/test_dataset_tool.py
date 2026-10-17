import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "frontend"))
from dataset_tool import (  # noqa: E402
    UploadError, clean_columns, is_safe_sql, load_file, make_connection, parse_dates, run_query,
)


def csv(text):
    return text.encode("utf-8")


# ---------- loading ----------

def test_column_names_are_cleaned_and_made_unique():
    assert clean_columns(["Order Date", "Sub-Category", "Sales", "sales", "2024", ""]) == [
        "order_date", "sub_category", "sales", "sales_2", "c_2024", "column_6",
    ]


def test_numeric_text_becomes_numbers_but_mixed_text_stays_text():
    df, _ = load_file("a.csv", csv('id,amount,mixed\n1,"1,200",a\n2,300,b\n3,50,3\n4,10,c\n'))
    assert pd.api.types.is_numeric_dtype(df["amount"])
    assert df["amount"].tolist() == [1200, 300, 50, 10]
    assert not pd.api.types.is_numeric_dtype(df["mixed"])  # nothing is silently deleted
    assert df["mixed"].notna().all()


def test_column_named_value_is_not_forced_to_numeric():
    df, _ = load_file("a.csv", csv("value\nhello\nworld\n"))
    assert df["value"].tolist() == ["hello", "world"]


def test_day_first_dates_are_read_correctly():
    s = pd.Series(["09-11-2013", "13-06-2013"])
    assert parse_dates(s).tolist() == [pd.Timestamp("2013-11-09"), pd.Timestamp("2013-06-13")]


def test_month_first_is_detected_when_the_data_proves_it():
    s = pd.Series(["11/25/2013", "01/02/2013"])
    assert parse_dates(s).tolist() == [pd.Timestamp("2013-11-25"), pd.Timestamp("2013-01-02")]


def test_iso_dates():
    assert parse_dates(pd.Series(["2024-01-05", "2024-02-10"])).tolist() == [
        pd.Timestamp("2024-01-05"), pd.Timestamp("2024-02-10"),
    ]


def test_bad_uploads_give_clear_errors():
    with pytest.raises(UploadError):
        load_file("a.txt", b"hello")
    with pytest.raises(UploadError):
        load_file("a.csv", b"")
    with pytest.raises(UploadError):
        load_file("big.csv", b"x" * (10 * 1024 * 1024 + 1))


# ---------- SQL safety ----------

@pytest.mark.parametrize("sql", [
    "SELECT SUM(value) FROM data",
    "SELECT a FROM data WHERE b > 1 GROUP BY a ORDER BY a LIMIT 10",
    "WITH t AS (SELECT * FROM data) SELECT a FROM t",
    "SELECT a FROM data UNION ALL SELECT a FROM data",
])
def test_safe_queries_are_allowed(sql):
    assert is_safe_sql(sql)


@pytest.mark.parametrize("sql", [
    "DROP TABLE data",
    "DELETE FROM data",
    "INSERT INTO data VALUES (1)",
    "SELECT * FROM data; DROP TABLE data",
    "SELECT * FROM other_table",
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT * FROM glob('*')",
    "SELECT * FROM information_schema.tables",
    "COPY data TO 'x.csv'",
    "ATTACH 'x.db'",
    "",
])
def test_dangerous_queries_are_blocked(sql):
    assert not is_safe_sql(sql)


# ---------- database ----------

def test_query_runs_on_uploaded_data():
    df, _ = load_file("a.csv", csv("region,profit\nW,10\nE,5\nW,2\n"))
    con = make_connection(df)
    out = run_query(con, "SELECT region, SUM(profit) AS p FROM data GROUP BY region ORDER BY p DESC")
    assert out.to_dict("records") == [{"region": "W", "p": 12}, {"region": "E", "p": 5}]


def test_external_access_is_disabled():
    df, _ = load_file("a.csv", csv("a\n1\n"))
    con = make_connection(df)
    with pytest.raises(Exception):
        run_query(con, "SELECT * FROM read_csv('/etc/passwd')")
