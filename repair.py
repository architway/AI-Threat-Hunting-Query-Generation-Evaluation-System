from __future__ import annotations

from llm_client import LLMClient
from models import GeneratedQuery, Hypothesis
from query_generator import parse_generated_query


def repair_generated_query(
    llm_client: LLMClient,
    hypothesis: Hypothesis,
    schema: list[str],
    failed_sql: str,
    duckdb_error: str,
    prompt_strategy: str = "base",
    domain_context: str | None = None,
) -> GeneratedQuery:
    """Ask the LLM to repair SQL after DuckDB rejects it."""

    prompt = build_repair_prompt(
        hypothesis=hypothesis,
        schema=schema,
        failed_sql=failed_sql,
        duckdb_error=duckdb_error,
        prompt_strategy=prompt_strategy,
        domain_context=domain_context,
    )
    generated = parse_generated_query(llm_client.complete(prompt))
    generated.prompt_strategy = prompt_strategy
    generated.model_name = _model_label(llm_client)
    return generated


def build_repair_prompt(
    hypothesis: Hypothesis,
    schema: list[str],
    failed_sql: str,
    duckdb_error: str,
    prompt_strategy: str = "base",
    domain_context: str | None = None,
) -> str:
    """Build a repair prompt that excludes expected outcome rows."""

    schema_lines = "\n".join(f"- {column}" for column in schema)
    context_block = ""
    if domain_context:
        context_block = f"\nPrompt-safe AWS domain context:\n{domain_context}\n"
    return f"""Repair a DuckDB SQL query for AWS CloudTrail threat hunting.

Use only the schema, hypothesis, failed SQL, and DuckDB error below. Do not
assume access to expected outcome rows, answer keys, or previous hypotheses.

DuckDB table:
- Name: cloudtrail
- It includes a generated row_id column plus these CSV columns:
{schema_lines}
{context_block}

Current hypothesis:
- ID: {hypothesis.id}
- Name: {hypothesis.name}
- Text: {hypothesis.hypothesis}

Prompt strategy: {prompt_strategy}

Failed SQL:
{failed_sql}

DuckDB error:
{duckdb_error}

Return only valid JSON. Do not include Markdown fences.

The JSON must have this shape:
{{
  "sql": "SELECT ... FROM cloudtrail WHERE ...",
  "confidence": 0.0,
  "hypothesis_interpretation": "This hypothesis is asking for...",
  "query_reasoning": "I repaired the query this way because...",
  "threat_explanation": "This behavior may indicate...",
  "assumptions": ["..."]
}}

SQL rules:
- Query only the cloudtrail table.
- Use DuckDB SQL.
- Return SELECT or WITH queries only.
- Do not mutate data or create objects.
"""


def _model_label(llm_client: LLMClient) -> str:
    label = getattr(llm_client, "model_label", None)
    if label:
        return str(label)
    model = getattr(llm_client, "model", None)
    if model:
        return str(model)
    return type(llm_client).__name__
