from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AppConfig:
    """Runtime settings collected from defaults, environment, and CLI flags."""

    data_path: Path = PROJECT_ROOT / "nineteenFeaturesDf.csv"
    hypotheses_path: Path = PROJECT_ROOT / "hypotheses.json"
    outcomes_path: Path = PROJECT_ROOT / "hypotheses_outcomes.json"
    output_root: Path = PROJECT_ROOT / "outputs"
    root_evaluation_results_path: Path = PROJECT_ROOT / "evaluation_results.json"
    comparison_results_path: Path = PROJECT_ROOT / "comparison_results.json"
    benchmark_results_path: Path = PROJECT_ROOT / "benchmark_results.json"
    domain_context_path: Path = PROJECT_ROOT / "aws_domain_prompt_context.md"
    provider: str = "cerebras"
    cerebras_api_key: str | None = None
    cerebras_base_url: str = "https://api.cerebras.ai/v1"
    model: str | None = None
    temperature: float = 0.0
    max_completion_tokens: int = 1200
    max_result_rows: int = 10000
    prompt_strategy: str = "base"
    repair_attempts: int = 1
    request_budget: int = 50

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            data_path=Path(
                os.getenv("AI_STRIKE_DATA_PATH", str(PROJECT_ROOT / "nineteenFeaturesDf.csv"))
            ),
            hypotheses_path=Path(
                os.getenv("AI_STRIKE_HYPOTHESES_PATH", str(PROJECT_ROOT / "hypotheses.json"))
            ),
            outcomes_path=Path(
                os.getenv(
                    "AI_STRIKE_OUTCOMES_PATH",
                    str(PROJECT_ROOT / "hypotheses_outcomes.json"),
                )
            ),
            output_root=Path(
                os.getenv("AI_STRIKE_OUTPUT_ROOT", str(PROJECT_ROOT / "outputs"))
            ),
            root_evaluation_results_path=Path(
                os.getenv(
                    "AI_STRIKE_ROOT_EVALUATION_PATH",
                    str(PROJECT_ROOT / "evaluation_results.json"),
                )
            ),
            comparison_results_path=Path(
                os.getenv(
                    "AI_STRIKE_COMPARISON_RESULTS_PATH",
                    str(PROJECT_ROOT / "comparison_results.json"),
                )
            ),
            benchmark_results_path=Path(
                os.getenv(
                    "AI_STRIKE_BENCHMARK_RESULTS_PATH",
                    str(PROJECT_ROOT / "benchmark_results.json"),
                )
            ),
            domain_context_path=Path(
                os.getenv(
                    "AI_STRIKE_DOMAIN_CONTEXT_PATH",
                    str(PROJECT_ROOT / "aws_domain_prompt_context.md"),
                )
            ),
            provider=os.getenv("AI_STRIKE_PROVIDER", "cerebras").lower(),
            cerebras_api_key=os.getenv("CEREBRAS_API_KEY"),
            cerebras_base_url=os.getenv(
                "CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1"
            ),
            model=os.getenv("AI_STRIKE_MODEL"),
            temperature=float(os.getenv("AI_STRIKE_TEMPERATURE", "0")),
            max_completion_tokens=int(
                os.getenv("AI_STRIKE_MAX_COMPLETION_TOKENS", "1200")
            ),
            max_result_rows=int(os.getenv("AI_STRIKE_MAX_RESULT_ROWS", "10000")),
            prompt_strategy=os.getenv("AI_STRIKE_PROMPT_STRATEGY", "base"),
            repair_attempts=int(os.getenv("AI_STRIKE_REPAIR_ATTEMPTS", "1")),
            request_budget=int(os.getenv("AI_STRIKE_REQUEST_BUDGET", "50")),
        )


def read_csv_schema(csv_path: Path) -> list[str]:
    """Read only the CSV header so prompts never include the full dataset."""

    with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        return next(reader)
