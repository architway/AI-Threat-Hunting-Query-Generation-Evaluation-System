import json
from pathlib import Path
from uuid import uuid4

from config import AppConfig
from launch_check import find_prompt_leak_markers, run_launch_checks


def test_launch_check_passes_offline_without_api_key() -> None:
    config = _write_launch_project(_workspace_tmp())

    result = run_launch_checks(config, real_mode=False)

    assert result.ok is True
    assert any("Offline mode" in item for item in result.info)


def test_launch_check_reports_missing_real_key_and_model() -> None:
    config = _write_launch_project(_workspace_tmp())

    result = run_launch_checks(config, real_mode=True)

    assert result.ok is False
    assert any("CEREBRAS_API_KEY" in item for item in result.errors)
    assert any("AI_STRIKE_MODEL" in item for item in result.errors)


def test_launch_check_rejects_unknown_provider() -> None:
    config = _write_launch_project(_workspace_tmp())
    config = AppConfig(
        data_path=config.data_path,
        hypotheses_path=config.hypotheses_path,
        outcomes_path=config.outcomes_path,
        output_root=config.output_root,
        root_evaluation_results_path=config.root_evaluation_results_path,
        comparison_results_path=config.comparison_results_path,
        benchmark_results_path=config.benchmark_results_path,
        domain_context_path=config.domain_context_path,
        provider="other-provider",
        model="some/provider-model",
    )

    result = run_launch_checks(config, real_mode=True)

    assert result.ok is False
    assert any("AI_STRIKE_PROVIDER must be 'cerebras'" in item for item in result.errors)


def test_prompt_leak_marker_detects_outcome_identifier() -> None:
    tmp_path = _workspace_tmp()
    outcomes_path = tmp_path / "hypotheses_outcomes.json"
    outcomes_path.write_text(
        json.dumps([{"1": [{"eventID": "11111111-2222-3333-4444-555555555555"}]}]),
        encoding="utf-8",
    )

    markers = find_prompt_leak_markers(
        "Generated prompt accidentally includes 11111111-2222-3333-4444-555555555555",
        outcomes_path,
    )

    assert markers


def _write_launch_project(tmp_path: Path) -> AppConfig:
    data_path = tmp_path / "events.csv"
    hypotheses_path = tmp_path / "hypotheses.json"
    outcomes_path = tmp_path / "hypotheses_outcomes.json"
    domain_context_path = tmp_path / "aws_domain_prompt_context.md"

    data_path.write_text(
        (
            "eventID,eventTime,sourceIPAddress,userAgent,eventName,eventSource,"
            "awsRegion,eventVersion,userIdentitytype,eventType,requestID,"
            "userIdentityaccountId,userIdentityprincipalId,userIdentityarn,"
            "userIdentityaccessKeyId,userIdentityuserName,errorCode,errorMessage,"
            "requestParametersinstanceType\n"
        ),
        encoding="utf-8",
    )
    hypotheses_path.write_text(
        json.dumps(
            [
                {
                    "id": "1",
                    "name": "Sign-in Failures",
                    "hypothesis": "Find failed console logins.",
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
                            "eventID": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                        }
                    ]
                }
            ]
        ),
        encoding="utf-8",
    )
    domain_context_path.write_text(
        "\n".join(
            [
                "# Test Domain Context",
                "## Always Include",
                "- CloudTrail uses eventName and eventSource.",
                "## Identity And Error Fields",
                "- errorCode marks failed API calls.",
                "## H1 - Failed Console Login",
                "- Use eventSource = 'signin.amazonaws.com' and eventName = 'ConsoleLogin'.",
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
        domain_context_path=domain_context_path,
        request_budget=50,
    )


def _workspace_tmp() -> Path:
    path = Path("outputs") / "test_launch_check" / uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path
