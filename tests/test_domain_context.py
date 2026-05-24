from domain_context import (
    DEFAULT_DOMAIN_CONTEXT_PATH,
    find_forbidden_context_markers,
    official_aws_urls_only,
    select_domain_context,
)
from models import Hypothesis


def test_domain_context_selects_relevant_aws_mapping() -> None:
    hypothesis = Hypothesis(
        id="5",
        name="Whoami Reconnaissance",
        hypothesis="Find GetCallerIdentity calls.",
    )

    context = select_domain_context(hypothesis, DEFAULT_DOMAIN_CONTEXT_PATH)

    assert "sts.amazonaws.com" in context
    assert "GetCallerIdentity" in context
    assert "hypotheses_outcomes.json" not in context
    assert not find_forbidden_context_markers(context)


def test_domain_context_keeps_heuristic_uncertainty() -> None:
    hypothesis = Hypothesis(
        id="9a",
        name="Suspicious User Agents",
        hypothesis="Find kali, parrot, and powershell user agents.",
    )

    context = select_domain_context(hypothesis, DEFAULT_DOMAIN_CONTEXT_PATH)

    assert "AWS documentation does not classify" in context
    assert "heuristic" in context.lower()


def test_source_brief_uses_only_official_aws_urls() -> None:
    official_only, non_aws = official_aws_urls_only()

    assert official_only is True
    assert non_aws == []
