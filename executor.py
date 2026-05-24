from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd

from models import ExecutionResult


BLOCKED_SQL_KEYWORDS = {
    "alter",
    "attach",
    "call",
    "copy",
    "create",
    "delete",
    "detach",
    "drop",
    "export",
    "insert",
    "install",
    "load",
    "pragma",
    "update",
}


class DuckDBExecutor:
    """Executes read-only generated SQL against the CloudTrail CSV."""

    def __init__(self, csv_path: Path, max_result_rows: int = 10000) -> None:
        self.csv_path = csv_path
        self.max_result_rows = max_result_rows

    def execute(self, sql: str) -> ExecutionResult:
        try:
            cleaned_sql = validate_read_only_sql(sql)
            with duckdb.connect(database=":memory:") as connection:
                self._create_cloudtrail_view(connection)
                guarded_sql = (
                    f"SELECT * FROM ({cleaned_sql}) AS generated_query "
                    f"LIMIT {self.max_result_rows}"
                )
                dataframe = connection.execute(guarded_sql).fetchdf()
                return ExecutionResult(
                    success=True,
                    dataframe=dataframe,
                    row_count=len(dataframe),
                )
        except Exception as exc:
            return ExecutionResult(
                success=False,
                dataframe=pd.DataFrame(),
                row_count=0,
                error=str(exc),
            )

    def _create_cloudtrail_view(self, connection: duckdb.DuckDBPyConnection) -> None:
        # DuckDB scans the large CSV directly. all_varchar avoids mixed-type surprises
        # from sparse CloudTrail fields, and row_id gives raw events a stable identity.
        csv_path_literal = _duckdb_string_literal(self.csv_path)
        connection.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW cloudtrail AS
            SELECT row_number() OVER () - 1 AS row_id, *
            FROM read_csv_auto({csv_path_literal}, header=true, all_varchar=true, ignore_errors=true)
            """
        )


def validate_read_only_sql(sql: str) -> str:
    """Allow only a single SELECT/WITH statement and reject mutation keywords."""

    without_comments = _strip_sql_comments(sql).strip()
    if not without_comments:
        raise ValueError("Generated SQL is empty.")

    if ";" in without_comments.rstrip(";"):
        raise ValueError("Generated SQL must contain only one statement.")

    cleaned = without_comments.rstrip(";").strip()
    first_token = re.match(r"^\s*(\w+)", cleaned)
    if not first_token or first_token.group(1).lower() not in {"select", "with"}:
        raise ValueError("Generated SQL must start with SELECT or WITH.")

    lowered = cleaned.lower()
    for keyword in BLOCKED_SQL_KEYWORDS:
        if re.search(rf"\b{keyword}\b", lowered):
            raise ValueError(f"Generated SQL contains blocked keyword: {keyword}")

    return cleaned


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql


def _duckdb_string_literal(path: Path) -> str:
    normalized = str(path).replace("\\", "/")
    escaped = normalized.replace("'", "''")
    return f"'{escaped}'"
