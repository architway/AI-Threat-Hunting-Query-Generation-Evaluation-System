from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class Hypothesis:
    """One natural-language threat hunting request from hypotheses.json."""

    id: str
    name: str
    hypothesis: str


@dataclass
class GeneratedQuery:
    """Structured query object returned by the LLM or mock client."""

    sql: str
    confidence: float
    hypothesis_interpretation: str
    query_reasoning: str
    threat_explanation: str
    assumptions: list[str] = field(default_factory=list)
    prompt_strategy: str | None = None
    model_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sql": self.sql,
            "confidence": self.confidence,
            "hypothesis_interpretation": self.hypothesis_interpretation,
            "query_reasoning": self.query_reasoning,
            "threat_explanation": self.threat_explanation,
            "assumptions": self.assumptions,
            "prompt_strategy": self.prompt_strategy,
            "model_name": self.model_name,
        }


@dataclass
class ExecutionResult:
    """Result of executing generated SQL against DuckDB."""

    success: bool
    dataframe: pd.DataFrame
    row_count: int
    error: str | None = None


@dataclass
class EvaluationResult:
    """Precision/recall/F1 comparison for one hypothesis."""

    execution_success: bool
    generated_row_count: int
    expected_row_count: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    exact_match: bool
    identity_strategy: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_success": self.execution_success,
            "generated_row_count": self.generated_row_count,
            "expected_row_count": self.expected_row_count,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "exact_match": self.exact_match,
            "identity_strategy": self.identity_strategy,
            "error": self.error,
        }


@dataclass
class RunResult:
    """Flattened per-hypothesis artifact row."""

    hypothesis: Hypothesis
    generated_query: GeneratedQuery | None
    evaluation: EvaluationResult
    error: str | None = None
    execution: ExecutionResult | None = None
    prompt_strategy: str | None = None
    model_name: str | None = None
    generation_seconds: float = 0.0
    execution_seconds: float = 0.0
    evaluation_seconds: float = 0.0
    total_seconds: float = 0.0
    repair_attempts: int = 0
    query_suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        generated = self.generated_query.to_dict() if self.generated_query else {}
        return {
            "id": self.hypothesis.id,
            "name": self.hypothesis.name,
            "hypothesis": self.hypothesis.hypothesis,
            "sql": generated.get("sql"),
            "confidence": generated.get("confidence"),
            "hypothesis_interpretation": generated.get("hypothesis_interpretation"),
            "query_reasoning": generated.get("query_reasoning"),
            "threat_explanation": generated.get("threat_explanation"),
            "assumptions": generated.get("assumptions", []),
            "prompt_strategy": self.prompt_strategy or generated.get("prompt_strategy"),
            "model_name": self.model_name or generated.get("model_name"),
            **self.evaluation.to_dict(),
            "generation_seconds": self.generation_seconds,
            "execution_seconds": self.execution_seconds,
            "evaluation_seconds": self.evaluation_seconds,
            "total_seconds": self.total_seconds,
            "repair_attempts": self.repair_attempts,
            "query_suggestions": self.query_suggestions,
            "error": self.error or self.evaluation.error,
        }
