from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from config import AppConfig
from pipeline import execute_run, write_json
from prompts import available_prompt_strategies


def main() -> int:
    load_dotenv()
    args = parse_args()
    config = apply_cli_overrides(AppConfig.from_env(), args)

    try:
        run = execute_run(
            config=config,
            use_mock=args.mock_llm,
            hypothesis_id=args.hypothesis_id,
            limit=args.limit,
            verbose=False,
            write_outputs=False,
        )
        payload = build_benchmark_payload(run.results)
        write_json(config.benchmark_results_path, payload)
        (config.benchmark_results_path.parent / "BENCHMARK_REPORT.md").write_text(
            build_benchmark_report(payload),
            encoding="utf-8",
        )
        print(
            "Benchmark complete: "
            f"{config.benchmark_results_path}, BENCHMARK_REPORT.md"
        )
        return 0
    except Exception as exc:
        print(f"Error: {exc}")
        return 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure query-generation, execution, and evaluation latency."
    )
    parser.add_argument("--mock-llm", action="store_true", help="Run without API key.")
    parser.add_argument("--hypothesis-id", help="Run exactly one hypothesis ID.")
    parser.add_argument("--limit", type=int, help="Run only the first N selected items.")
    parser.add_argument("--model", help="Model ID for real LLM mode.")
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
        "--prompt-strategy",
        choices=available_prompt_strategies(),
        help="Prompt strategy: base, structured, multi_step, or aws_domain.",
    )
    parser.add_argument(
        "--repair-attempts",
        type=int,
        help="Optional repair attempts per hypothesis.",
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
        model=args.model or config.model,
        temperature=config.temperature,
        max_completion_tokens=config.max_completion_tokens,
        max_result_rows=args.max_result_rows or config.max_result_rows,
        prompt_strategy=args.prompt_strategy or config.prompt_strategy,
        repair_attempts=(
            args.repair_attempts
            if args.repair_attempts is not None
            else config.repair_attempts
        ),
        request_budget=config.request_budget,
    )


def build_benchmark_payload(results) -> dict:
    per_hypothesis = [result.to_dict() for result in results]
    return {
        "averages": {
            "generation_seconds": _average(
                result.generation_seconds for result in results
            ),
            "execution_seconds": _average(result.execution_seconds for result in results),
            "evaluation_seconds": _average(
                result.evaluation_seconds for result in results
            ),
            "total_seconds": _average(result.total_seconds for result in results),
        },
        "per_hypothesis": per_hypothesis,
    }


def build_benchmark_report(payload: dict) -> str:
    averages = payload["averages"]
    lines = [
        "# Benchmark Report",
        "",
        "## Average Timings",
        "",
        f"- Generation seconds: {averages['generation_seconds']}",
        f"- Execution seconds: {averages['execution_seconds']}",
        f"- Evaluation seconds: {averages['evaluation_seconds']}",
        f"- Total seconds: {averages['total_seconds']}",
        "",
        "## Per-Hypothesis Timings",
        "",
        "| ID | Name | Generation | Execution | Evaluation | Total |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["per_hypothesis"]:
        lines.append(
            f"| {row['id']} | {row['name']} | {row['generation_seconds']} | "
            f"{row['execution_seconds']} | {row['evaluation_seconds']} | "
            f"{row['total_seconds']} |"
        )
    lines.extend(
        [
            "",
            "Timings are measured around the same pipeline used by the CLI and "
            "Streamlit demo. Mock mode isolates local orchestration and DuckDB "
            "latency from network/model latency. The same benchmark path can use "
            "the aws_domain prompt strategy for Phase 2 real-model launch tests.",
        ]
    )
    return "\n".join(lines) + "\n"


def _average(values) -> float:
    materialized = list(values)
    if not materialized:
        return 0.0
    return round(sum(materialized) / len(materialized), 4)


if __name__ == "__main__":
    raise SystemExit(main())
