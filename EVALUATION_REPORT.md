# Evaluation Report

Latest run directory: `C:\Users\archi\interview\take_home_assignment\ai_strike\outputs\run_20260524_205335`

## Overall Metrics

- Macro precision: 1.0
- Macro recall: 1.0
- Macro F1: 1.0
- Exact-match rate: 1.0
- Execution-success rate: 1.0

## Timing Summary

- Average generation seconds: 0.0002
- Average execution seconds: 2.3734
- Average evaluation seconds: 0.0101
- Average total seconds: 2.3854

## Before / After

- Phase 1 baseline: mock mode proved the local generator, DuckDB executor, evaluator, and artifact writer.
- Phase 3 enhancements: the same pipeline now records timing, writes root `evaluation_results.json`, adds deterministic query suggestions, and exposes prompt strategy plus optional repair hooks.
- Phase 2 launch layer: the `aws_domain` strategy can inject compact official-AWS CloudTrail context without sending outcome rows to the LLM.

## Per-Hypothesis Results

### 1: Sign-in Failures (Brute Force/Bot Attacks)

- Precision / recall / F1: 1.0 / 1.0 / 1.0
- Exact match: True
- Identity strategy: fallback_expected_columns_tuple
- Generated rows / expected rows: 12 / 12
- Timing seconds: generation=0.0002, execution=2.3734, evaluation=0.0101, total=2.3854
- Repair attempts: 0
- Query suggestions: Include row_id or eventID for raw-event queries to make evaluation traceable.
- Error: None

## Notes

Mock mode remains the offline default for repeatable testing. Real provider runs can use the same CLI, prompt strategies, AWS domain context, repair loop, and reporting once credentials and a model are configured. Expected outcome rows are used only by the evaluator after SQL execution.

Repair/healing defaults to one attempt and only runs after DuckDB rejects the first generated SQL, so successful queries do not spend an extra model request.

Current real-provider documentation and code path are Cerebras-first. Use mock mode for offline testing and Cerebras mode for live runs.
