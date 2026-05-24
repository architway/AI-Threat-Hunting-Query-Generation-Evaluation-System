from __future__ import annotations

from models import Hypothesis


PROMPT_STRATEGIES = ("base", "structured", "multi_step", "aws_domain")


def available_prompt_strategies() -> tuple[str, ...]:
    return PROMPT_STRATEGIES


def build_prompt(
    hypothesis: Hypothesis,
    schema: list[str],
    domain_context: str | None = None,
    strategy: str = "base",
) -> str:
    """Build a prompt from schema plus one hypothesis only."""

    if strategy not in PROMPT_STRATEGIES:
        raise ValueError(
            f"Unknown prompt strategy {strategy!r}. "
            f"Choose one of: {', '.join(PROMPT_STRATEGIES)}."
        )

    schema_lines = "\n".join(f"- {column}" for column in schema)
    context_block = ""
    if domain_context:
        context_block = f"\nPrompt-safe AWS domain context:\n{domain_context}\n"

    strategy_block = _strategy_instructions(strategy)

    return f"""You generate DuckDB SQL for AWS CloudTrail threat hunting.

Use only the information in this prompt. Do not assume access to answer keys,
expected rows, or previous hypotheses.

DuckDB table:
- Name: cloudtrail
- It includes a generated row_id column plus these CSV columns:
{schema_lines}
{context_block}
Current hypothesis:
- ID: {hypothesis.id}
- Name: {hypothesis.name}
- Text: {hypothesis.hypothesis}

Prompt strategy:
{strategy_block}

Return only valid JSON. Do not include Markdown fences.

The JSON must have this shape:
{{
  "sql": "SELECT ... FROM cloudtrail WHERE ...",
  "confidence": 0.0,
  "hypothesis_interpretation": "This hypothesis is asking for...",
  "query_reasoning": "I structured the query this way because...",
  "threat_explanation": "This behavior may indicate...",
  "assumptions": ["..."]
}}

SQL rules:
- Query only the cloudtrail table.
- Use DuckDB SQL.
- Return SELECT or WITH queries only.
- Prefer explicit output columns that help explain the detection.
- Preserve original dataset column names in SELECT output. Do not alias raw
  CloudTrail fields, cast timestamps into new names, or rename counts except
  `count(*) AS count` for aggregate queries.
- Include row_id for raw event queries when useful.
- Do not mutate data or create objects.
"""


def _strategy_instructions(strategy: str) -> str:
    if strategy == "structured":
        return """- First identify the likely CloudTrail eventName, eventSource,
  identity, errorCode, userAgent, and grouping fields.
- Prefer explicit WHERE filters over broad scans.
- For aggregate hypotheses, return the grouping columns plus count.
- For raw-event hypotheses, include eventID or row_id when it helps evaluation."""

    if strategy == "multi_step":
        return """- Think through the detection in this order: actor, API action,
  error/status signal, source/network signal, and output identity.
- Put the concise reasoning in query_reasoning, not outside the JSON.
- Then return one final DuckDB query that best matches the hypothesis.
- Keep the same JSON contract as the other strategies."""

    if strategy == "aws_domain":
        return """- Use the AWS domain context when it is relevant to map hypotheses to
  CloudTrail eventSource, eventName, identity type, error, userAgent, and
  requestParameters fields.
- Prefer exact CloudTrail service/action mappings such as
  eventSource = 'signin.amazonaws.com' with eventName = 'ConsoleLogin'.
- For cross-service detections such as authorization failures or userAgent
  heuristics, keep eventSource broad and make the signal column explicit.
- Match CloudTrail errorCode values with exact equality or IN lists for the
  known values in the context; avoid substring matching for errorCode.
- Do not invent thresholds, time windows, or HAVING limits unless the hypothesis
  explicitly includes them.
- For hypotheses about reconnaissance volume, bucket probing, broad
  authorization failures, or tool/userAgent clustering, prefer an
  aggregate query with count(*) AS count grouped by the relevant actor,
  sourceIPAddress, userAgent, eventName, or eventSource fields.
- For raw event detections such as root console login, failed console login,
  CloudTrail disruption, Secrets Manager access, or IAM key creation, return
  original CloudTrail columns that identify the event and preserve their exact
  dataset column names.
- When the AWS domain context specifies an output shape or alias, follow it
  exactly, such as `count(*) AS count` or
  `requestParametersinstanceType AS instanceType`.
- When extracting a tool token from userAgent, group by the same expression
  selected, not by the output alias, and keep the output alias as the original
  field name.
- Treat kali, parrot, powershell, command/*, and 10xlarge+ as heuristics,
  not AWS-defined threat labels; mention that uncertainty in assumptions.
- Use the flat dataset columns exactly as provided, especially
  userIdentitytype and requestParametersinstanceType.
- Keep the same JSON contract as the other strategies."""

    return """- Use the baseline direct translation from hypothesis to DuckDB SQL.
- Keep the query simple, readable, and limited to the cloudtrail table."""
