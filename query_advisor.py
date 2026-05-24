from __future__ import annotations

import re

from models import EvaluationResult, ExecutionResult


def suggest_query_improvements(
    sql: str | None,
    evaluation: EvaluationResult | None = None,
    execution: ExecutionResult | None = None,
) -> list[str]:
    """Return deterministic query-quality notes without using answer-key rows."""

    if not sql or not sql.strip():
        return ["No SQL was generated; inspect the LLM JSON response first."]

    suggestions: list[str] = []
    normalized = _normalize_sql(sql)

    if not re.search(r"\bwhere\b", normalized):
        suggestions.append("Add a WHERE clause so the query is not a broad scan.")

    if re.search(r"select\s+\*", normalized):
        suggestions.append("Select explicit analyst-facing columns instead of SELECT *.")

    is_aggregate = bool(
        re.search(r"\bgroup\s+by\b", normalized) or re.search(r"\bcount\s*\(", normalized)
    )
    if not is_aggregate and "row_id" not in normalized and "eventid" not in normalized:
        suggestions.append(
            "Include row_id or eventID for raw-event queries to make evaluation traceable."
        )

    if evaluation:
        if not evaluation.execution_success:
            suggestions.append(
                "Fix the SQL execution error before tuning precision or recall."
            )
        if evaluation.generated_row_count >= 1000:
            suggestions.append(
                "Result set is large; consider tighter eventName, errorCode, or userAgent filters."
            )
        if evaluation.precision < 0.9 and evaluation.generated_row_count:
            suggestions.append(
                "Precision is low; add filters that remove false-positive event patterns."
            )
        if evaluation.recall < 0.9 and evaluation.expected_row_count:
            suggestions.append(
                "Recall is low; check for missing equivalent event names or error values."
            )

    if execution and not execution.success and execution.error:
        suggestions.append(f"DuckDB error to repair: {execution.error}")

    if not suggestions:
        suggestions.append("Query shape looks reasonable for this hypothesis.")

    return _dedupe(suggestions)


def _normalize_sql(sql: str) -> str:
    without_line_comments = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
    without_block_comments = re.sub(
        r"/\*.*?\*/", "", without_line_comments, flags=re.DOTALL
    )
    return re.sub(r"\s+", " ", without_block_comments).strip().lower()


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped
