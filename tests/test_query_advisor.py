import pandas as pd

from models import EvaluationResult, ExecutionResult
from query_advisor import suggest_query_improvements


def test_query_advisor_flags_broad_query_and_low_precision() -> None:
    evaluation = EvaluationResult(
        execution_success=True,
        generated_row_count=1500,
        expected_row_count=10,
        true_positives=5,
        false_positives=1495,
        false_negatives=5,
        precision=0.0033,
        recall=0.5,
        f1=0.0066,
        exact_match=False,
        identity_strategy="eventID",
    )

    suggestions = suggest_query_improvements(
        "SELECT * FROM cloudtrail",
        evaluation=evaluation,
    )

    assert any("WHERE clause" in suggestion for suggestion in suggestions)
    assert any("SELECT *" in suggestion for suggestion in suggestions)
    assert any("Precision is low" in suggestion for suggestion in suggestions)
    assert any("Result set is large" in suggestion for suggestion in suggestions)


def test_query_advisor_includes_duckdb_error_for_failed_execution() -> None:
    suggestions = suggest_query_improvements(
        "SELECT missing FROM cloudtrail WHERE eventName = 'ConsoleLogin'",
        execution=ExecutionResult(
            success=False,
            dataframe=pd.DataFrame(),
            row_count=0,
            error="Binder Error: missing column",
        ),
    )

    assert any("Binder Error" in suggestion for suggestion in suggestions)
