from types import SimpleNamespace

import json
from pathlib import Path
from uuid import uuid4

from benchmark import build_benchmark_payload
from config import AppConfig
from experiments import run_experiments, write_experiment_outputs
from models import EvaluationResult, Hypothesis, RunResult
from pipeline import execute_run, write_artifacts


def test_root_evaluation_results_json_is_written() -> None:
    tmp_path = _workspace_tmp()
    output_dir = tmp_path / "outputs" / "run_test"
    output_dir.mkdir(parents=True)
    root_results = tmp_path / "evaluation_results.json"
    result = RunResult(
        hypothesis=Hypothesis(id="1", name="Test", hypothesis="Find events."),
        generated_query=None,
        evaluation=EvaluationResult(
            execution_success=False,
            generated_row_count=0,
            expected_row_count=1,
            true_positives=0,
            false_positives=0,
            false_negatives=1,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            exact_match=False,
            identity_strategy="generation_failed",
            error="no query",
        ),
        error="no query",
    )

    write_artifacts(output_dir, [result], root_evaluation_path=root_results)

    assert root_results.exists()
    payload = json.loads(root_results.read_text(encoding="utf-8"))
    assert payload["overall"]["macro_f1"] == 0.0


def test_experiment_summary_works_in_mock_mode() -> None:
    tmp_path = _workspace_tmp()
    config = _write_small_project(tmp_path)
    args = SimpleNamespace(
        mock_llm=True,
        strategies="base,structured",
        models=None,
        hypothesis_id=None,
        limit=1,
    )

    payload, summary = run_experiments(config, args)
    write_experiment_outputs(config, payload, summary)

    assert len(summary) == 2
    assert summary[0]["model_name"] == "mock-llm"
    assert config.comparison_results_path.exists()
    assert (tmp_path / "comparison_summary.csv").exists()


def test_benchmark_summary_works_in_mock_mode() -> None:
    tmp_path = _workspace_tmp()
    config = _write_small_project(tmp_path)

    run = execute_run(
        config=config,
        use_mock=True,
        limit=1,
        write_outputs=False,
    )
    payload = build_benchmark_payload(run.results)

    assert len(payload["per_hypothesis"]) == 1
    assert "total_seconds" in payload["averages"]


def _write_small_project(tmp_path) -> AppConfig:
    data_path = tmp_path / "events.csv"
    hypotheses_path = tmp_path / "hypotheses.json"
    outcomes_path = tmp_path / "hypotheses_outcomes.json"
    data_path.write_text(
        "\n".join(
            [
                (
                    "eventID,eventTime,sourceIPAddress,userAgent,eventName,"
                    "eventSource,awsRegion,eventVersion,userIdentitytype,eventType,"
                    "requestID,userIdentityaccountId,userIdentityprincipalId,"
                    "userIdentityarn,userIdentityaccessKeyId,userIdentityuserName,"
                    "errorCode,errorMessage,requestParametersinstanceType"
                ),
                (
                    "abc,2020-01-01T00:00:00Z,1.2.3.4,console,"
                    "ConsoleLogin,signin.amazonaws.com,us-east-1,1.0,IAMUser,"
                    "AwsConsoleSignIn,req,123,pid,arn,key,bob,,Failure,"
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    hypotheses_path.write_text(
        json.dumps(
            [
                {
                    "id": "1",
                    "name": "Sign-in Failures",
                    "hypothesis": "Find failed console login attempts.",
                }
            ]
        ),
        encoding="utf-8",
    )
    outcomes_path.write_text(
        json.dumps(
            [
                {
                    "1": [
                        {
                            "eventTime": "2020-01-01T00:00:00Z",
                            "sourceIPAddress": "1.2.3.4",
                            "errorMessage": "Failure",
                            "awsRegion": "us-east-1",
                            "userIdentityuserName": "bob",
                        }
                    ]
                }
            ]
        ),
        encoding="utf-8",
    )
    return AppConfig(
        data_path=data_path,
        hypotheses_path=hypotheses_path,
        outcomes_path=outcomes_path,
        output_root=tmp_path / "outputs",
        root_evaluation_results_path=tmp_path / "evaluation_results.json",
        comparison_results_path=tmp_path / "comparison_results.json",
        benchmark_results_path=tmp_path / "benchmark_results.json",
        prompt_strategy="base",
        repair_attempts=0,
    )


def _workspace_tmp() -> Path:
    path = Path("outputs") / "test_phase3_tools" / uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path
