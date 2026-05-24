from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from config import AppConfig, read_csv_schema
from domain_context import select_domain_context
from evaluator import evaluate_result, summarize_evaluations
from executor import DuckDBExecutor
from llm_client import CerebrasClient, MockLLMClient
from models import EvaluationResult, Hypothesis, RunResult
from query_advisor import suggest_query_improvements
from query_generator import QueryGenerator
from repair import repair_generated_query
from utils import load_hypotheses_outcomes


@dataclass
class PipelineRun:
    """Results plus artifact location for one CLI/demo/experiment run."""

    results: list[RunResult]
    output_dir: Path | None = None

    @property
    def overall(self) -> dict[str, float]:
        return summarize_evaluations([result.evaluation for result in self.results])


def load_hypotheses(path: Path) -> list[Hypothesis]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return [Hypothesis(**item) for item in data]


def select_hypotheses(
    hypotheses: list[Hypothesis],
    hypothesis_id: str | None,
    limit: int | None,
) -> list[Hypothesis]:
    selected = hypotheses
    if hypothesis_id:
        selected = [
            hypothesis for hypothesis in hypotheses if hypothesis.id == hypothesis_id
        ]
        if not selected:
            raise ValueError(f"No hypothesis found with id {hypothesis_id!r}.")

    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be 1 or greater.")
        selected = selected[:limit]

    return selected


def create_run_directory(output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    base_name = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    for counter in range(100):
        suffix = "" if counter == 0 else f"_{counter}"
        run_dir = output_root / f"{base_name}{suffix}"
        try:
            run_dir.mkdir()
            return run_dir
        except FileExistsError:
            continue
    raise RuntimeError("Could not create a unique run directory.")


def build_llm_client(config: AppConfig, use_mock: bool, model_name: str | None = None):
    if use_mock:
        return MockLLMClient(model_label=model_name or "mock-llm")
    if config.provider == "cerebras":
        return CerebrasClient(
            api_key=config.cerebras_api_key,
            base_url=config.cerebras_base_url,
            model=model_name or config.model,
            temperature=config.temperature,
            max_completion_tokens=config.max_completion_tokens,
        )
    raise ValueError(
        f"AI_STRIKE_PROVIDER must be 'cerebras'. Got {config.provider!r}."
    )


def execute_run(
    config: AppConfig,
    use_mock: bool,
    hypothesis_id: str | None = None,
    limit: int | None = None,
    verbose: bool = False,
    write_outputs: bool = True,
) -> PipelineRun:
    hypotheses = select_hypotheses(
        load_hypotheses(config.hypotheses_path),
        hypothesis_id=hypothesis_id,
        limit=limit,
    )
    schema = read_csv_schema(config.data_path)
    outcomes = load_hypotheses_outcomes(config.outcomes_path)
    llm_client = build_llm_client(config, use_mock=use_mock)
    generator = QueryGenerator(llm_client)
    executor = DuckDBExecutor(config.data_path, config.max_result_rows)

    results = run_pipeline(
        selected_hypotheses=hypotheses,
        schema=schema,
        outcomes=outcomes,
        generator=generator,
        executor=executor,
        prompt_strategy=config.prompt_strategy,
        repair_attempts=config.repair_attempts,
        domain_context_path=config.domain_context_path,
        verbose=verbose,
    )

    output_dir = None
    if write_outputs:
        output_dir = create_run_directory(config.output_root)
        write_artifacts(
            output_dir=output_dir,
            run_results=results,
            root_evaluation_path=config.root_evaluation_results_path,
        )
        write_evaluation_report(Path("EVALUATION_REPORT.md"), output_dir, results)

    return PipelineRun(results=results, output_dir=output_dir)


def run_pipeline(
    selected_hypotheses: list[Hypothesis],
    schema: list[str],
    outcomes: dict[str, pd.DataFrame],
    generator: QueryGenerator,
    executor: DuckDBExecutor,
    prompt_strategy: str = "base",
    repair_attempts: int = 0,
    domain_context_path: Path | None = None,
    verbose: bool = False,
) -> list[RunResult]:
    run_results: list[RunResult] = []

    for hypothesis in selected_hypotheses:
        expected_df = outcomes.get(hypothesis.id)
        if expected_df is None:
            raise ValueError(f"Missing expected outcome for hypothesis {hypothesis.id}.")

        run_result = _run_one_hypothesis(
            hypothesis=hypothesis,
            expected_df=expected_df,
            schema=schema,
            generator=generator,
            executor=executor,
            prompt_strategy=prompt_strategy,
            repair_attempts=repair_attempts,
            domain_context_path=domain_context_path,
        )
        run_results.append(run_result)
        if verbose:
            print_verbose_result(run_result)

    return run_results


def _run_one_hypothesis(
    hypothesis: Hypothesis,
    expected_df: pd.DataFrame,
    schema: list[str],
    generator: QueryGenerator,
    executor: DuckDBExecutor,
    prompt_strategy: str,
    repair_attempts: int,
    domain_context_path: Path | None,
) -> RunResult:
    total_started = time.perf_counter()
    generation_seconds = 0.0
    execution_seconds = 0.0
    evaluation_seconds = 0.0
    attempts_used = 0
    generated_query = None
    execution = None

    try:
        domain_context = _domain_context_for_hypothesis(
            hypothesis=hypothesis,
            prompt_strategy=prompt_strategy,
            domain_context_path=domain_context_path,
        )
        generation_started = time.perf_counter()
        generated_query = generator.generate(
            hypothesis,
            schema,
            domain_context=domain_context,
            prompt_strategy=prompt_strategy,
        )
        generation_seconds += time.perf_counter() - generation_started

        execution_started = time.perf_counter()
        execution = executor.execute(generated_query.sql)
        execution_seconds += time.perf_counter() - execution_started

        while (
            not execution.success
            and generated_query is not None
            and attempts_used < repair_attempts
        ):
            attempts_used += 1
            generation_started = time.perf_counter()
            generated_query = repair_generated_query(
                llm_client=generator.llm_client,
                hypothesis=hypothesis,
                schema=schema,
                failed_sql=generated_query.sql,
                duckdb_error=execution.error or "DuckDB execution failed.",
                prompt_strategy=prompt_strategy,
                domain_context=domain_context,
            )
            generation_seconds += time.perf_counter() - generation_started

            execution_started = time.perf_counter()
            execution = executor.execute(generated_query.sql)
            execution_seconds += time.perf_counter() - execution_started

        evaluation_started = time.perf_counter()
        evaluation = evaluate_result(execution, expected_df)
        evaluation_seconds += time.perf_counter() - evaluation_started
        error = evaluation.error
    except Exception as exc:
        evaluation = EvaluationResult(
            execution_success=False,
            generated_row_count=0,
            expected_row_count=len(expected_df),
            true_positives=0,
            false_positives=0,
            false_negatives=len(expected_df),
            precision=0.0,
            recall=0.0,
            f1=0.0,
            exact_match=False,
            identity_strategy="generation_failed",
            error=str(exc),
        )
        error = str(exc)

    total_seconds = time.perf_counter() - total_started
    suggestions = suggest_query_improvements(
        generated_query.sql if generated_query else None,
        evaluation=evaluation,
        execution=execution,
    )

    return RunResult(
        hypothesis=hypothesis,
        generated_query=generated_query,
        evaluation=evaluation,
        error=error,
        execution=execution,
        prompt_strategy=prompt_strategy,
        model_name=_model_label(generator.llm_client),
        generation_seconds=round(generation_seconds, 4),
        execution_seconds=round(execution_seconds, 4),
        evaluation_seconds=round(evaluation_seconds, 4),
        total_seconds=round(total_seconds, 4),
        repair_attempts=attempts_used,
        query_suggestions=suggestions,
    )


def print_verbose_result(result: RunResult) -> None:
    _safe_print(f"\n[{result.hypothesis.id}] {result.hypothesis.name}")
    if result.generated_query:
        _safe_print(result.generated_query.sql)
        _safe_print(f"Reasoning: {result.generated_query.query_reasoning}")
    _safe_print(
        "Metrics: "
        f"precision={result.evaluation.precision}, "
        f"recall={result.evaluation.recall}, "
        f"f1={result.evaluation.f1}, "
        f"strategy={result.evaluation.identity_strategy}"
    )
    _safe_print(
        "Timing: "
        f"generation={result.generation_seconds}s, "
        f"execution={result.execution_seconds}s, "
        f"evaluation={result.evaluation_seconds}s, "
        f"total={result.total_seconds}s"
    )
    if result.query_suggestions:
        _safe_print(f"Suggestions: {'; '.join(result.query_suggestions)}")
    if result.error:
        _safe_print(f"Error: {result.error}")


def write_artifacts(
    output_dir: Path,
    run_results: list[RunResult],
    root_evaluation_path: Path | None = None,
) -> None:
    rows = [result.to_dict() for result in run_results]
    evaluations = [result.evaluation for result in run_results]
    errors = [row for row in rows if row.get("error")]
    evaluation_payload = {"overall": summarize_evaluations(evaluations), "results": rows}

    write_json(output_dir / "generated_queries.json", rows)
    write_json(output_dir / "evaluation_results.json", evaluation_payload)
    if root_evaluation_path:
        write_json(root_evaluation_path, evaluation_payload)
    write_json(output_dir / "errors.json", errors)
    pd.DataFrame(rows).to_csv(output_dir / "summary.csv", index=False)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def write_evaluation_report(
    report_path: Path,
    output_dir: Path,
    run_results: list[RunResult],
) -> None:
    overall = summarize_evaluations([result.evaluation for result in run_results])
    avg_generation = _average(result.generation_seconds for result in run_results)
    avg_execution = _average(result.execution_seconds for result in run_results)
    avg_evaluation = _average(result.evaluation_seconds for result in run_results)
    avg_total = _average(result.total_seconds for result in run_results)
    lines = [
        "# Evaluation Report",
        "",
        f"Latest run directory: `{output_dir}`",
        "",
        "## Overall Metrics",
        "",
        f"- Macro precision: {overall['macro_precision']}",
        f"- Macro recall: {overall['macro_recall']}",
        f"- Macro F1: {overall['macro_f1']}",
        f"- Exact-match rate: {overall['exact_match_rate']}",
        f"- Execution-success rate: {overall['execution_success_rate']}",
        "",
        "## Timing Summary",
        "",
        f"- Average generation seconds: {avg_generation}",
        f"- Average execution seconds: {avg_execution}",
        f"- Average evaluation seconds: {avg_evaluation}",
        f"- Average total seconds: {avg_total}",
        "",
        "## Before / After",
        "",
        "- Phase 1 baseline: mock mode proved the local generator, DuckDB "
        "executor, evaluator, and artifact writer.",
        "- Phase 3 enhancements: the same pipeline now records timing, writes "
        "root `evaluation_results.json`, adds deterministic query suggestions, "
        "and exposes prompt strategy plus optional repair hooks.",
        "- Phase 2 launch layer: the `aws_domain` strategy can inject compact "
        "official-AWS CloudTrail context without sending outcome rows to the LLM.",
        "",
        "## Per-Hypothesis Results",
        "",
    ]

    for result in run_results:
        evaluation = result.evaluation
        lines.extend(
            [
                f"### {result.hypothesis.id}: {result.hypothesis.name}",
                "",
                f"- Precision / recall / F1: {evaluation.precision} / "
                f"{evaluation.recall} / {evaluation.f1}",
                f"- Exact match: {evaluation.exact_match}",
                f"- Identity strategy: {evaluation.identity_strategy}",
                f"- Generated rows / expected rows: "
                f"{evaluation.generated_row_count} / {evaluation.expected_row_count}",
                f"- Timing seconds: generation={result.generation_seconds}, "
                f"execution={result.execution_seconds}, "
                f"evaluation={result.evaluation_seconds}, total={result.total_seconds}",
                f"- Repair attempts: {result.repair_attempts}",
                f"- Query suggestions: {'; '.join(result.query_suggestions)}",
                f"- Error: {evaluation.error or 'None'}",
                "",
            ]
        )

    lines.extend(
        [
            "## Notes",
            "",
            "Mock mode remains the offline default for repeatable testing. "
            "Real provider runs can use the same CLI, prompt strategies, AWS domain "
            "context, repair loop, and reporting once credentials and a model are "
            "configured. Expected outcome rows are used only by the evaluator "
            "after SQL execution.",
            "",
            "Repair/healing defaults to one attempt and only runs after DuckDB "
            "rejects the first generated SQL, so successful queries do not spend "
            "an extra model request.",
            "",
            "Current real-provider documentation and code path are Cerebras-first. "
            "Use mock mode for offline testing and Cerebras mode for live runs.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_run_summary(output_dir: Path | None, run_results: list[RunResult]) -> None:
    overall = summarize_evaluations([result.evaluation for result in run_results])
    print(f"Run complete: {output_dir or 'artifacts not written'}")
    print(
        "Overall: "
        f"macro_precision={overall['macro_precision']}, "
        f"macro_recall={overall['macro_recall']}, "
        f"macro_f1={overall['macro_f1']}, "
        f"execution_success_rate={overall['execution_success_rate']}"
    )


def _average(values) -> float:
    materialized = list(values)
    if not materialized:
        return 0.0
    return round(sum(materialized) / len(materialized), 4)


def _model_label(llm_client) -> str:
    label = getattr(llm_client, "model_label", None)
    if label:
        return str(label)
    model = getattr(llm_client, "model", None)
    if model:
        return str(model)
    return type(llm_client).__name__


def _domain_context_for_hypothesis(
    hypothesis: Hypothesis,
    prompt_strategy: str,
    domain_context_path: Path | None,
) -> str | None:
    if prompt_strategy != "aws_domain":
        return None
    return select_domain_context(hypothesis, domain_context_path)


def _safe_print(value: object) -> None:
    text = str(value)
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))
