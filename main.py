from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from config import AppConfig
from pipeline import execute_run, print_run_summary
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
            verbose=args.verbose,
            write_outputs=True,
        )
        print_run_summary(run.output_dir, run.results)
        return 0
    except Exception as exc:
        print(f"Error: {exc}")
        return 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and evaluate CloudTrail threat hunting SQL."
    )
    parser.add_argument("--mock-llm", action="store_true", help="Run without API key.")
    parser.add_argument("--hypothesis-id", help="Run exactly one hypothesis ID.")
    parser.add_argument("--limit", type=int, help="Run only the first N selected items.")
    parser.add_argument("--model", help="Model ID for real LLM mode.")
    parser.add_argument("--verbose", action="store_true", help="Print per-item details.")
    parser.add_argument("--data-path", type=Path, help="Path to CloudTrail CSV.")
    parser.add_argument("--hypotheses-path", type=Path, help="Path to hypotheses JSON.")
    parser.add_argument("--outcomes-path", type=Path, help="Path to outcomes JSON.")
    parser.add_argument("--output-root", type=Path, help="Directory for run artifacts.")
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
        help="Retry failed DuckDB SQL this many times through the LLM.",
    )
    return parser.parse_args()


def apply_cli_overrides(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    return AppConfig(
        data_path=args.data_path or config.data_path,
        hypotheses_path=args.hypotheses_path or config.hypotheses_path,
        outcomes_path=args.outcomes_path or config.outcomes_path,
        output_root=args.output_root or config.output_root,
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


if __name__ == "__main__":
    raise SystemExit(main())
