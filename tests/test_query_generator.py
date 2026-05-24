import json

from domain_context import DEFAULT_DOMAIN_CONTEXT_PATH, select_domain_context
from llm_client import MockLLMClient, _uses_llama_contract_hint
from models import Hypothesis
from query_generator import QueryGenerator, parse_generated_query


def test_query_parser_rejects_malformed_json() -> None:
    try:
        parse_generated_query("not json")
    except ValueError as exc:
        assert "valid JSON" in str(exc)
    else:
        raise AssertionError("Expected malformed JSON to be rejected.")


def test_query_parser_accepts_markdown_fenced_json() -> None:
    parsed = parse_generated_query(
        "```json\n"
        + json.dumps(
            {
                "sql": "SELECT eventName FROM cloudtrail",
                "confidence": 0.7,
                "hypothesis_interpretation": "Find events.",
                "query_reasoning": "Use the event table.",
                "threat_explanation": "Suspicious activity.",
                "assumptions": [],
            }
        )
        + "\n```"
    )

    assert parsed.sql == "SELECT eventName FROM cloudtrail"
    assert parsed.confidence == 0.7


def test_query_parser_accepts_valid_contract() -> None:
    parsed = parse_generated_query(
        json.dumps(
            {
                "sql": "SELECT * FROM cloudtrail",
                "confidence": 0.8,
                "hypothesis_interpretation": "Find events.",
                "query_reasoning": "Use the event table.",
                "threat_explanation": "Suspicious activity.",
                "assumptions": [],
            }
        )
    )

    assert parsed.sql == "SELECT * FROM cloudtrail"
    assert parsed.confidence == 0.8


def test_mock_llm_path_runs_without_api_key() -> None:
    generator = QueryGenerator(MockLLMClient())
    hypothesis = Hypothesis(
        id="4",
        name="Unauthorized API Calls",
        hypothesis="Unauthorized API calls can reveal malicious activity",
    )

    generated = generator.generate(
        hypothesis,
        schema=["eventName", "userIdentityarn", "errorCode"],
    )

    assert "AccessDenied" in generated.sql
    assert generated.confidence > 0


def test_aws_domain_strategy_preserves_generated_query_contract() -> None:
    generator = QueryGenerator(MockLLMClient())
    hypothesis = Hypothesis(
        id="5",
        name="Whoami Reconnaissance",
        hypothesis="Find GetCallerIdentity calls.",
    )

    generated = generator.generate(
        hypothesis,
        schema=["eventName", "eventSource", "userIdentityarn"],
        domain_context=select_domain_context(hypothesis, DEFAULT_DOMAIN_CONTEXT_PATH),
        prompt_strategy="aws_domain",
    )

    assert generated.prompt_strategy == "aws_domain"
    assert generated.model_name == "mock-llm"
    assert "GetCallerIdentity" in generated.sql


def test_llama_contract_hint_is_model_specific() -> None:
    assert _uses_llama_contract_hint("llama3.1-8b")
    assert not _uses_llama_contract_hint("qwen-3-235b-a22b-instruct-2507")
    assert not _uses_llama_contract_hint("gpt-oss-120b")
