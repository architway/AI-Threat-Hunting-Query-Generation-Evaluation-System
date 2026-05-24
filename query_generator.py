from __future__ import annotations

import json
from typing import Any

from llm_client import LLMClient
from models import GeneratedQuery, Hypothesis
from prompts import build_prompt


REQUIRED_RESPONSE_FIELDS = {
    "sql",
    "confidence",
    "hypothesis_interpretation",
    "query_reasoning",
    "threat_explanation",
    "assumptions",
}


class QueryGenerator:
    """Turns one hypothesis into one generated DuckDB SQL object."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def generate(
        self,
        hypothesis: Hypothesis,
        schema: list[str],
        domain_context: str | None = None,
        prompt_strategy: str = "base",
    ) -> GeneratedQuery:
        prompt = build_prompt(
            hypothesis,
            schema,
            domain_context=domain_context,
            strategy=prompt_strategy,
        )
        raw_response = self.llm_client.complete(prompt)
        generated = parse_generated_query(raw_response)
        generated.prompt_strategy = prompt_strategy
        generated.model_name = _model_label(self.llm_client)
        return generated


def parse_generated_query(raw_response: str) -> GeneratedQuery:
    """Parse strict JSON and fail clearly when a model drifts from the contract."""

    try:
        parsed = _loads_model_json(raw_response)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "LLM response was not valid JSON. The model must return JSON only, "
            "without Markdown fences."
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object.")

    missing = REQUIRED_RESPONSE_FIELDS - set(parsed)
    if missing:
        raise ValueError(f"LLM response missing required fields: {sorted(missing)}")

    return _dict_to_generated_query(parsed)


def _loads_model_json(raw_response: str) -> Any:
    """Load JSON while tolerating common provider wrappers around the object."""

    text = raw_response.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = _strip_markdown_fence(text)
    if fenced != text:
        return json.loads(fenced)

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if text[index + end :].strip():
            continue
        return parsed

    return json.loads(text)


def _strip_markdown_fence(text: str) -> str:
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) < 3 or not lines[-1].strip().startswith("```"):
        return text

    opening = lines[0].strip().lower()
    if opening not in {"```", "```json"}:
        return text

    return "\n".join(lines[1:-1]).strip()


def _dict_to_generated_query(data: dict[str, Any]) -> GeneratedQuery:
    sql = data["sql"]
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("LLM response field 'sql' must be a non-empty string.")

    try:
        confidence = float(data["confidence"])
    except (TypeError, ValueError) as exc:
        raise ValueError("LLM response field 'confidence' must be numeric.") from exc

    if not 0 <= confidence <= 1:
        raise ValueError("LLM response field 'confidence' must be between 0 and 1.")

    assumptions = data["assumptions"]
    if not isinstance(assumptions, list) or not all(
        isinstance(item, str) for item in assumptions
    ):
        raise ValueError("LLM response field 'assumptions' must be a list of strings.")

    return GeneratedQuery(
        sql=sql.strip(),
        confidence=confidence,
        hypothesis_interpretation=str(data["hypothesis_interpretation"]),
        query_reasoning=str(data["query_reasoning"]),
        threat_explanation=str(data["threat_explanation"]),
        assumptions=assumptions,
    )


def _model_label(llm_client: LLMClient) -> str:
    label = getattr(llm_client, "model_label", None)
    if label:
        return str(label)
    model = getattr(llm_client, "model", None)
    if model:
        return str(model)
    return type(llm_client).__name__
