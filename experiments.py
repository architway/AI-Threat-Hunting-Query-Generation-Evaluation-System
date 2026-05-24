from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from config import AppConfig, read_csv_schema
from executor import DuckDBExecutor
from evaluator import summarize_evaluations
from pipeline import (
    build_llm_client,
    load_hypotheses,
    run_pipeline,
    select_hypotheses,
    write_json,
)
from prompts import available_prompt_strategies
from query_generator import QueryGenerator
from utils import load_hypotheses_outcomes


def main() -> int:
    load_dotenv()
    args = parse_args()
    config = apply_cli_overrides(AppConfig.from_env(), args)

    try:
        payload, summary = run_experiments(config, args)
        write_experiment_outputs(config, payload, summary)
        print(
            "Comparison complete: "
            f"{config.comparison_results_path}, comparison_summary.csv, "
            "MODEL_COMPARISON_REPORT.md"
        )
        return 0
    except Exception as exc:
        print(f"Error: {exc}")
        return 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare prompt strategies and model choices."
    )
    parser.add_argument("--mock-llm", action="store_true", help="Run without API key.")
    parser.add_argument(
        "--strategies",
        default="base",
        help="Comma-separated strategies: base,structured,multi_step,aws_domain.",
    )
    parser.add_argument(
        "--models",
        help="Comma-separated model names. In mock mode these are labels only.",
    )
    parser.add_argument("--hypothesis-id", help="Run exactly one hypothesis ID.")
    parser.add_argument("--limit", type=int, help="Run only the first N selected items.")
    parser.add_argument("--data-path", type=Path, help="Path to CloudTrail CSV.")
    parser.add_argument("--hypotheses-path", type=Path, help="Path to hypotheses JSON.")
    parser.add_argument("--outcomes-path", type=Path, help="Path to outcomes JSON.")
    parser.add_argument(
        "--domain-context-path",
        type=Path,
        help="Path to compact AWS domain prompt context.",
    )
    parser.add_argument(
        "--max-result-rows",
        type=int,
        help="Maximum rows fetched from each generated query.",
    )
    parser.add_argument(
        "--repair-attempts",
        type=int,
        default=0,
        help="Optional repair attempts per hypothesis.",
    )
    parser.add_argument(
        "--request-budget",
        type=int,
        help="Maximum real LLM requests allowed for this experiment.",
    )
    return parser.parse_args()


def apply_cli_overrides(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    return AppConfig(
        data_path=args.data_path or config.data_path,
        hypotheses_path=args.hypotheses_path or config.hypotheses_path,
        outcomes_path=args.outcomes_path or config.outcomes_path,
        output_root=config.output_root,
        root_evaluation_results_path=config.root_evaluation_results_path,
        comparison_results_path=config.comparison_results_path,
        benchmark_results_path=config.benchmark_results_path,
        domain_context_path=args.domain_context_path or config.domain_context_path,
        provider=config.provider,
        cerebras_api_key=config.cerebras_api_key,
        cerebras_base_url=config.cerebras_base_url,
        model=config.model,
        temperature=config.temperature,
        max_completion_tokens=config.max_completion_tokens,
        max_result_rows=args.max_result_rows or config.max_result_rows,
        prompt_strategy=config.prompt_strategy,
        repair_attempts=args.repair_attempts,
        request_budget=(
            args.request_budget
            if args.request_budget is not None
            else config.request_budget
        ),
    )


def run_experiments(
    config: AppConfig,
    args: argparse.Namespace,
) -> tuple[dict, list[dict]]:
    strategies = _parse_strategies(args.strategies)
    models = _parse_models(args.models, config, args.mock_llm)
    hypotheses = select_hypotheses(
        load_hypotheses(config.hypotheses_path),
        hypothesis_id=args.hypothesis_id,
        limit=args.limit,
    )
    schema = read_csv_schema(config.data_path)
    outcomes = load_hypotheses_outcomes(config.outcomes_path)
    estimated_requests = estimate_request_count(
        model_count=len(models),
        strategy_count=len(strategies),
        hypothesis_count=len(hypotheses),
        repair_attempts=config.repair_attempts,
    )
    enforce_request_budget(
        estimated_requests=estimated_requests,
        request_budget=config.request_budget,
        use_mock=args.mock_llm,
    )

    runs = []
    summary_rows: list[dict] = []
    for model_name in models:
        for strategy in strategies:
            llm_client = build_llm_client(
                config,
                use_mock=args.mock_llm,
                model_name=model_name,
            )
            generator = QueryGenerator(llm_client)
            executor = DuckDBExecutor(config.data_path, config.max_result_rows)

            started = time.perf_counter()
            results = run_pipeline(
                selected_hypotheses=hypotheses,
                schema=schema,
                outcomes=outcomes,
                generator=generator,
                executor=executor,
                prompt_strategy=strategy,
                repair_attempts=config.repair_attempts,
                domain_context_path=config.domain_context_path,
                verbose=False,
            )
            total_seconds = round(time.perf_counter() - started, 4)
            overall = summarize_evaluations(
                [result.evaluation for result in results]
            )
            summary_row = {
                "model_name": model_name,
                "prompt_strategy": strategy,
                "hypothesis_count": len(results),
                "total_seconds": total_seconds,
                "avg_total_seconds": _average(
                    result.total_seconds for result in results
                ),
                **overall,
            }
            summary_rows.append(summary_row)
            runs.append(
                {
                    **summary_row,
                    "results": [result.to_dict() for result in results],
                }
            )

    return {"runs": runs}, summary_rows


def estimate_request_count(
    model_count: int,
    strategy_count: int,
    hypothesis_count: int,
    repair_attempts: int = 0,
) -> int:
    """Estimate worst-case LLM calls before starting real experiments."""

    per_hypothesis = 1 + max(repair_attempts, 0)
    return model_count * strategy_count * hypothesis_count * per_hypothesis


def enforce_request_budget(
    estimated_requests: int,
    request_budget: int,
    use_mock: bool,
) -> None:
    if use_mock:
        return
    if request_budget < 1:
        raise ValueError("--request-budget must be 1 or greater for real runs.")
    if estimated_requests > request_budget:
        raise ValueError(
            "Experiment would exceed the real request budget: "
            f"estimated {estimated_requests}, budget {request_budget}. "
            "Reduce --models, --strategies, --limit, or --repair-attempts."
        )


def write_experiment_outputs(
    config: AppConfig,
    payload: dict,
    summary_rows: list[dict],
) -> None:
    output_dir = config.comparison_results_path.parent
    write_json(config.comparison_results_path, payload)
    pd.DataFrame(summary_rows).to_csv(
        output_dir / "comparison_summary.csv",
        index=False,
    )
    (output_dir / "MODEL_COMPARISON_REPORT.md").write_text(
        _build_model_comparison_report(summary_rows),
        encoding="utf-8",
    )


def _build_model_comparison_report(summary_rows: list[dict]) -> str:
    lines = [
        "# Model Comparison Report",
        "",
        "This report compares prompt strategies and model labels using the same "
        "local execution and evaluation pipeline.",
        "",
        "| Model | Strategy | Hypotheses | Macro F1 | Exact Match | Success | Avg Seconds |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['model_name']} | {row['prompt_strategy']} | "
            f"{row['hypothesis_count']} | {row['macro_f1']} | "
            f"{row['exact_match_rate']} | {row['execution_success_rate']} | "
            f"{row['avg_total_seconds']} |"
        )
    lines.extend(
        [
            "",
            "Mock mode is useful for checking pipeline behavior offline. Real model "
            "quality still requires provider credentials and live model runs. "
            "Real experiments estimate request count before starting and refuse "
            "to exceed the configured request budget.",
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_strategies(raw: str) -> list[str]:
    strategies = [item.strip() for item in raw.split(",") if item.strip()]
    valid = set(available_prompt_strategies())
    invalid = [strategy for strategy in strategies if strategy not in valid]
    if invalid:
        raise ValueError(f"Unknown prompt strategies: {invalid}")
    return strategies


def _parse_models(
    raw: str | None,
    config: AppConfig,
    use_mock: bool,
) -> list[str]:
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]
    if use_mock:
        return ["mock-llm"]
    if config.model:
        return [config.model]
    raise ValueError(
        "Real model experiments require --models or AI_STRIKE_MODEL. "
        "Use --mock-llm for offline comparisons."
    )


def _average(values) -> float:
    materialized = list(values)
    if not materialized:
        return 0.0
    return round(sum(materialized) / len(materialized), 4)


if __name__ == "__main__":
    raise SystemExit(main())
