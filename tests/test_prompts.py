from models import Hypothesis
from prompts import available_prompt_strategies, build_prompt


def test_prompt_strategies_return_valid_prompt_text() -> None:
    hypothesis = Hypothesis(
        id="1",
        name="Sign-in Failures",
        hypothesis="Find failed console logins.",
    )

    for strategy in available_prompt_strategies():
        prompt = build_prompt(
            hypothesis,
            schema=["eventName", "eventSource"],
            strategy=strategy,
        )

        assert "Return only valid JSON" in prompt
        assert '"sql": "SELECT ... FROM cloudtrail WHERE ..."' in prompt
        assert f"- ID: {hypothesis.id}" in prompt


def test_aws_domain_prompt_includes_mapping_and_heuristic_caveat() -> None:
    hypothesis = Hypothesis(
        id="7",
        name="Large EC2 Instance Creation",
        hypothesis="Find RunInstances with 10xlarge or bigger instance types.",
    )
    domain_context = (
        "- EC2 launches use eventSource = 'ec2.amazonaws.com' and "
        "eventName = 'RunInstances'.\n"
        "- 10xlarge or larger is not an AWS-defined threat category."
    )

    prompt = build_prompt(
        hypothesis,
        schema=["eventName", "eventSource", "requestParametersinstanceType"],
        domain_context=domain_context,
        strategy="aws_domain",
    )

    assert "ec2.amazonaws.com" in prompt
    assert "RunInstances" in prompt
    assert "not AWS-defined threat labels" in prompt
    assert "hypotheses_outcomes.json" not in prompt


def test_unknown_prompt_strategy_fails_clearly() -> None:
    hypothesis = Hypothesis(id="1", name="x", hypothesis="y")

    try:
        build_prompt(hypothesis, schema=["eventName"], strategy="unknown")
    except ValueError as exc:
        assert "Unknown prompt strategy" in str(exc)
    else:
        raise AssertionError("Expected unknown strategy to be rejected.")
