from __future__ import annotations

import math
from collections.abc import Hashable
from typing import Any

import pandas as pd

from models import EvaluationResult, ExecutionResult


NULL_SENTINEL = "<NULL>"


def evaluate_result(
    execution: ExecutionResult,
    expected_df: pd.DataFrame,
) -> EvaluationResult:
    """Compare generated rows to expected rows using the best available identity."""

    if not execution.success:
        return _failed_result(
            execution=execution,
            expected_df=expected_df,
            strategy="execution_failed",
            error=execution.error or "SQL execution failed.",
        )

    generated_df = execution.dataframe
    expected_columns = list(expected_df.columns)
    missing_columns = [
        column for column in expected_columns if column not in generated_df.columns
    ]
    if missing_columns:
        return _failed_result(
            execution=execution,
            expected_df=expected_df,
            strategy="missing_expected_columns",
            error=f"Generated output missing expected columns: {missing_columns}",
        )

    generated_items, expected_items, strategy = _comparison_sets(
        generated_df=generated_df,
        expected_df=expected_df,
        expected_columns=expected_columns,
    )
    return _score_sets(
        execution=execution,
        expected_df=expected_df,
        generated_items=generated_items,
        expected_items=expected_items,
        strategy=strategy,
        error=None,
    )


def _comparison_sets(
    generated_df: pd.DataFrame,
    expected_df: pd.DataFrame,
    expected_columns: list[str],
) -> tuple[set[Hashable], set[Hashable], str]:
    if "count" in expected_columns:
        return (
            _tuple_set(generated_df, expected_columns),
            _tuple_set(expected_df, expected_columns),
            "aggregate_tuple_with_count",
        )

    if "eventID" in expected_columns:
        return (
            _column_set(generated_df, "eventID"),
            _column_set(expected_df, "eventID"),
            "eventID",
        )

    if "row_id" in expected_columns:
        return (
            _column_set(generated_df, "row_id"),
            _column_set(expected_df, "row_id"),
            "row_id",
        )

    # Some answer files contain raw rows without eventID. In that case comparing
    # normalized expected-column tuples is more meaningful than a default 0..N index.
    return (
        _tuple_set(generated_df, expected_columns),
        _tuple_set(expected_df, expected_columns),
        "fallback_expected_columns_tuple",
    )


def _score_sets(
    execution: ExecutionResult,
    expected_df: pd.DataFrame,
    generated_items: set[Hashable],
    expected_items: set[Hashable],
    strategy: str,
    error: str | None,
) -> EvaluationResult:
    true_positives = len(generated_items & expected_items)
    false_positives = len(generated_items - expected_items)
    false_negatives = len(expected_items - generated_items)

    # Precision asks "of what I returned, how much was right?"
    precision = (
        true_positives / (true_positives + false_positives)
        if true_positives + false_positives
        else 0.0
    )
    # Recall asks "of what was expected, how much did I find?"
    recall = (
        true_positives / (true_positives + false_negatives)
        if true_positives + false_negatives
        else 0.0
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    return EvaluationResult(
        execution_success=execution.success,
        generated_row_count=execution.row_count,
        expected_row_count=len(expected_df),
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        exact_match=(
            false_positives == 0
            and false_negatives == 0
            and execution.row_count == len(expected_df)
        ),
        identity_strategy=strategy,
        error=error,
    )


def _failed_result(
    execution: ExecutionResult,
    expected_df: pd.DataFrame,
    strategy: str,
    error: str,
) -> EvaluationResult:
    return EvaluationResult(
        execution_success=False,
        generated_row_count=execution.row_count,
        expected_row_count=len(expected_df),
        true_positives=0,
        false_positives=0,
        false_negatives=len(expected_df),
        precision=0.0,
        recall=0.0,
        f1=0.0,
        exact_match=False,
        identity_strategy=strategy,
        error=error,
    )


def _column_set(dataframe: pd.DataFrame, column: str) -> set[Hashable]:
    return {_normalize_value(value, column) for value in dataframe[column].tolist()}


def _tuple_set(dataframe: pd.DataFrame, columns: list[str]) -> set[tuple[Hashable, ...]]:
    return {
        tuple(_normalize_value(row[column], column) for column in columns)
        for _, row in dataframe[columns].iterrows()
    }


def _normalize_value(value: Any, column: str | None = None) -> Hashable:
    """Normalize only comparison noise while preserving meaningful CloudTrail case."""

    if value is None:
        return NULL_SENTINEL

    if isinstance(value, float) and math.isnan(value):
        return NULL_SENTINEL

    if pd.isna(value):
        return NULL_SENTINEL

    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "" or stripped.lower() == "nan":
            return NULL_SENTINEL
        value = stripped

    if column and column.lower() == "count":
        count_value = _normalize_count(value)
        if count_value is not None:
            return count_value

    return value


def _normalize_count(value: Any) -> int | None:
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return None
    if as_float.is_integer():
        return int(as_float)
    return None


def summarize_evaluations(results: list[EvaluationResult]) -> dict[str, float]:
    if not results:
        return {
            "macro_precision": 0.0,
            "macro_recall": 0.0,
            "macro_f1": 0.0,
            "exact_match_rate": 0.0,
            "execution_success_rate": 0.0,
        }

    count = len(results)
    return {
        "macro_precision": round(sum(result.precision for result in results) / count, 4),
        "macro_recall": round(sum(result.recall for result in results) / count, 4),
        "macro_f1": round(sum(result.f1 for result in results) / count, 4),
        "exact_match_rate": round(
            sum(1 for result in results if result.exact_match) / count, 4
        ),
        "execution_success_rate": round(
            sum(1 for result in results if result.execution_success) / count, 4
        ),
    }
