import pandas as pd

from evaluator import evaluate_result
from models import ExecutionResult


def test_raw_comparison_by_event_id() -> None:
    generated = pd.DataFrame({"eventID": ["a", "b"], "extra": [1, 2]})
    expected = pd.DataFrame({"eventID": ["b", "c"]})

    result = evaluate_result(
        ExecutionResult(True, generated, len(generated)),
        expected,
    )

    assert result.identity_strategy == "eventID"
    assert result.true_positives == 1
    assert result.false_positives == 1
    assert result.false_negatives == 1
    assert result.precision == 0.5
    assert result.recall == 0.5


def test_raw_comparison_by_row_id_when_expected_has_row_id() -> None:
    generated = pd.DataFrame({"row_id": [10, 11]})
    expected = pd.DataFrame({"row_id": [11]})

    result = evaluate_result(
        ExecutionResult(True, generated, len(generated)),
        expected,
    )

    assert result.identity_strategy == "row_id"
    assert result.true_positives == 1
    assert result.false_positives == 1
    assert result.false_negatives == 0


def test_aggregate_comparison_by_tuple_including_count() -> None:
    generated = pd.DataFrame(
        {"eventName": ["GetBucketAcl"], "userIdentityarn": ["arn"], "count": ["3.0"]}
    )
    expected = pd.DataFrame(
        {"eventName": ["GetBucketAcl"], "userIdentityarn": ["arn"], "count": [3]}
    )

    result = evaluate_result(
        ExecutionResult(True, generated, len(generated)),
        expected,
    )

    assert result.identity_strategy == "aggregate_tuple_with_count"
    assert result.exact_match is True
    assert result.f1 == 1.0


def test_null_normalization_for_tuple_fallback() -> None:
    generated = pd.DataFrame({"errorCode": [""], "errorMessage": [" NaN "]})
    expected = pd.DataFrame({"errorCode": [None], "errorMessage": [float("nan")]})

    result = evaluate_result(
        ExecutionResult(True, generated, len(generated)),
        expected,
    )

    assert result.identity_strategy == "fallback_expected_columns_tuple"
    assert result.exact_match is True


def test_missing_expected_columns_fails_clearly() -> None:
    generated = pd.DataFrame({"eventName": ["ConsoleLogin"]})
    expected = pd.DataFrame({"eventID": ["abc"]})

    result = evaluate_result(
        ExecutionResult(True, generated, len(generated)),
        expected,
    )

    assert result.execution_success is False
    assert result.identity_strategy == "missing_expected_columns"
    assert "eventID" in (result.error or "")
