import json

import pandas as pd

from models import ExecutionResult, Hypothesis
from pipeline import run_pipeline
from query_generator import QueryGenerator


class CountingLLMClient:
    model_label = "test-model"

    def __init__(self, sql_responses: list[str]) -> None:
        self.sql_responses = sql_responses
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        index = min(len(self.prompts) - 1, len(self.sql_responses) - 1)
        return json.dumps(
            {
                "sql": self.sql_responses[index],
                "confidence": 0.5,
                "hypothesis_interpretation": "test",
                "query_reasoning": "test",
                "threat_explanation": "test",
                "assumptions": [],
            }
        )


class FailingExecutor:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, sql: str) -> ExecutionResult:
        self.calls += 1
        return ExecutionResult(
            success=False,
            dataframe=pd.DataFrame(),
            row_count=0,
            error="Parser Error: syntax",
        )


class FailsThenSucceedsExecutor:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, sql: str) -> ExecutionResult:
        self.calls += 1
        if self.calls == 1:
            return ExecutionResult(
                success=False,
                dataframe=pd.DataFrame(),
                row_count=0,
                error="Binder Error: missing column",
            )
        dataframe = pd.DataFrame({"eventID": ["abc"]})
        return ExecutionResult(
            success=True,
            dataframe=dataframe,
            row_count=len(dataframe),
        )


def test_repair_loop_does_not_run_when_disabled() -> None:
    llm = CountingLLMClient(["SELECT bad_column FROM cloudtrail"])
    executor = FailingExecutor()

    results = run_pipeline(
        selected_hypotheses=[_hypothesis()],
        schema=["eventID"],
        outcomes={"1": pd.DataFrame({"eventID": ["abc"]})},
        generator=QueryGenerator(llm),
        executor=executor,
        repair_attempts=0,
    )

    assert len(llm.prompts) == 1
    assert executor.calls == 1
    assert results[0].repair_attempts == 0
    assert results[0].evaluation.identity_strategy == "execution_failed"


def test_repair_loop_attempts_once_after_execution_failure() -> None:
    llm = CountingLLMClient(
        [
            "SELECT bad_column FROM cloudtrail",
            "SELECT eventID FROM cloudtrail WHERE eventID = 'abc'",
        ]
    )
    executor = FailsThenSucceedsExecutor()

    results = run_pipeline(
        selected_hypotheses=[_hypothesis()],
        schema=["eventID"],
        outcomes={"1": pd.DataFrame({"eventID": ["abc"]})},
        generator=QueryGenerator(llm),
        executor=executor,
        repair_attempts=1,
    )

    result = results[0]
    assert len(llm.prompts) == 2
    assert executor.calls == 2
    assert result.repair_attempts == 1
    assert result.evaluation.execution_success is True
    assert result.generated_query is not None
    assert "bad_column" not in result.generated_query.sql
    assert "hypotheses_outcomes" not in llm.prompts[1]
    assert "abc" not in llm.prompts[1]


def test_timing_fields_appear_in_run_result_output() -> None:
    llm = CountingLLMClient(["SELECT eventID FROM cloudtrail"])
    executor = FailsThenSucceedsExecutor()
    executor.calls = 1

    results = run_pipeline(
        selected_hypotheses=[_hypothesis()],
        schema=["eventID"],
        outcomes={"1": pd.DataFrame({"eventID": ["abc"]})},
        generator=QueryGenerator(llm),
        executor=executor,
        repair_attempts=0,
    )

    row = results[0].to_dict()
    assert "generation_seconds" in row
    assert "execution_seconds" in row
    assert "evaluation_seconds" in row
    assert "total_seconds" in row


def _hypothesis() -> Hypothesis:
    return Hypothesis(
        id="1",
        name="Test Hypothesis",
        hypothesis="Find one event.",
    )
