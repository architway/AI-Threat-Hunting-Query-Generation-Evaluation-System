# Evaluation Report

Latest run directory: `C:\Users\archi\interview\take_home_assignment\ai_strike\outputs\run_20260524_214551`

## Overall Metrics

- Macro precision: 0.9975
- Macro recall: 1.0
- Macro F1: 0.9988
- Exact-match rate: 0.5
- Execution-success rate: 1.0

## Timing Summary

- Average generation seconds: 1.0497
- Average execution seconds: 2.1208
- Average evaluation seconds: 0.0408
- Average total seconds: 3.2117

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
- Timing seconds: generation=1.5073, execution=2.2196, evaluation=0.0042, total=3.732
- Repair attempts: 0
- Query suggestions: Query shape looks reasonable for this hypothesis.
- Error: None

### 2: Root Access Through Console

- Precision / recall / F1: 1.0 / 1.0 / 1.0
- Exact match: False
- Identity strategy: eventID
- Generated rows / expected rows: 62 / 61
- Timing seconds: generation=1.1172, execution=2.1818, evaluation=0.0005, total=3.2997
- Repair attempts: 0
- Query suggestions: Query shape looks reasonable for this hypothesis.
- Error: None

### 3: CloudTrail Disruption

- Precision / recall / F1: 1.0 / 1.0 / 1.0
- Exact match: True
- Identity strategy: fallback_expected_columns_tuple
- Generated rows / expected rows: 4 / 4
- Timing seconds: generation=0.8074, execution=2.1973, evaluation=0.0051, total=3.0099
- Repair attempts: 0
- Query suggestions: Query shape looks reasonable for this hypothesis.
- Error: None

### 4: Unauthorized API Calls

- Precision / recall / F1: 0.99 / 1.0 / 0.995
- Exact match: False
- Identity strategy: aggregate_tuple_with_count
- Generated rows / expected rows: 2411 / 2387
- Timing seconds: generation=0.7671, execution=1.8845, evaluation=0.1533, total=2.8051
- Repair attempts: 0
- Query suggestions: Result set is large; consider tighter eventName, errorCode, or userAgent filters.
- Error: None

## Notes

Mock mode remains the offline default for repeatable testing. Real provider runs can use the same CLI, prompt strategies, AWS domain context, repair loop, and reporting once credentials and a model are configured. Expected outcome rows are used only by the evaluator after SQL execution.

Repair/healing defaults to one attempt and only runs after DuckDB rejects the first generated SQL, so successful queries do not spend an extra model request.

Current real-provider documentation and code path are Cerebras-first. Use mock mode for offline testing and Cerebras mode for live runs.
