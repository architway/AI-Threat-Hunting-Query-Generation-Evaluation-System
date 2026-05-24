# Approach

## Summary

This project builds a threat-hunting query generator for the provided CloudTrail dataset. A natural-language hypothesis and the CSV schema go into a fresh LLM or mock request. The response must be strict JSON containing DuckDB SQL plus explainability fields. DuckDB executes the SQL locally, and a pandas evaluator compares the result set to the expected outcome after execution.

The design goal is not just to get a score. It is to show a repeatable workflow for turning ambiguous hunt language into safe executable queries, measuring the output, and improving prompts without leaking answer-key data.

## Phase Story

Phase 1 built the base engine: CLI orchestration, a mock generator, a Cerebras real-provider client, DuckDB SQL execution, pandas evaluation, output artifacts, and unit tests.

Phase 3 added the bonus layer around that same engine: Streamlit UI, Docker files, prompt strategy experiments, benchmarks, deterministic query suggestions, one-attempt SQL repair after execution failures, and root-level deliverable artifacts.

Phase 2 then added AWS domain prompt tuning. The `aws_domain` strategy injects compact CloudTrail context derived from official AWS documentation so the model can map hypotheses to fields such as `eventSource`, `eventName`, `userIdentitytype`, `errorCode`, `userAgent`, and `requestParametersinstanceType`.

## Architecture

```text
main.py / app.py / experiments.py / benchmark.py
        |
        v
pipeline.py
  loads hypotheses, schema, outcomes, and runtime config
  selects prompt-safe AWS context when requested
  calls QueryGenerator once per hypothesis
  executes generated DuckDB SQL
  optionally repairs SQL after DuckDB errors
  evaluates generated rows against expected rows
  writes JSON, CSV, Markdown, timing, and suggestions
```

Key modules:

- `config.py`: paths, provider settings, model, request budget, prompt strategy, result limits, and repair defaults.
- `prompts.py`: shared JSON contract plus `base`, `structured`, `multi_step`, and `aws_domain` strategies.
- `domain_context.py`: loads compact official-AWS context and selects only relevant snippets for each hypothesis.
- `llm_client.py`: mock mode plus the Cerebras real-provider client.
- `query_generator.py`: prompt dispatch, strict JSON parsing, and validation.
- `executor.py`: read-only DuckDB execution over the CSV-backed `cloudtrail` view.
- `evaluator.py`: pandas set comparison, metric math, and macro summaries.
- `query_advisor.py`: deterministic post-evaluation query-quality suggestions.
- `repair.py`: SQL repair prompt used after DuckDB execution failure.

The CLI, Streamlit app, experiment runner, and benchmark runner all call `pipeline.py`. The UI is therefore a different front door into the same system, not a second implementation.

## Design Choices

### Why DuckDB SQL

SQL is a natural target for an LLM because the hypothesis can be translated into explicit filters, grouping, and selected columns. DuckDB can scan the large CSV directly and expose it as a stable `cloudtrail` table without loading the entire dataset into pandas first. The executor uses `all_varchar=true` to avoid mixed-type parsing surprises in sparse CloudTrail fields, adds a generated `row_id`, rejects mutating SQL, and caps returned rows.

### Why Pandas Evaluation

DuckDB is best for query execution; pandas is convenient for comparing the much smaller generated result set against the expected output. The evaluator normalizes null-like values, normalizes integer counts, ignores generated column order, and allows extra generated columns as long as all expected columns are present.

### Why Cerebras

Cerebras is the real-provider launch path. The CLI, evaluator, prompt strategies, and repair loop share the same small client interface, while provider-specific details stay inside `CerebrasClient`.

The model is selected through `AI_STRIKE_MODEL` or `--model`, and experiments enforce a request budget before real calls begin.

### Why Mock Mode

Mock mode is a deterministic offline generator. It allows development, unit tests, launch checks, Docker/Streamlit validation, experiments, and benchmarks without spending requests or depending on network/provider behavior. Mock mode is not presented as real model quality.

## ROI And Model Strategy

The highest-leverage work was not repeated calls to the most expensive frontier models. The project invests in official AWS documentation research, schema-aware prompt design, deterministic SQL validation, and a clear evaluator. That makes inexpensive Cerebras-hosted models and free-tier-style testing more useful because the prompt gives them the field mappings and output-shape constraints they need.

This is a practical production tradeoff: better domain context and deterministic evaluation reduce dependence on model size, control API spend, and make failures easier to diagnose.

## Prompt Strategy

Every hypothesis gets a fresh request. There is no reused chat history, so later hypotheses cannot inherit hidden answer state or accidental context from earlier runs.

All strategies return the same JSON contract:

```json
{
  "sql": "SELECT ... FROM cloudtrail WHERE ...",
  "confidence": 0.0,
  "hypothesis_interpretation": "This hypothesis is asking for...",
  "query_reasoning": "I structured the query this way because...",
  "threat_explanation": "This behavior may indicate...",
  "assumptions": ["..."]
}
```

Strategies:

- `base`: direct translation from hypothesis and schema to DuckDB SQL.
- `structured`: asks the model to identify event/action, identity, error, userAgent, grouping fields, and output shape before final SQL.
- `multi_step`: asks for concise reasoning through actor, API action, error/status signal, source/network signal, and output identity.
- `aws_domain`: injects compact official-AWS CloudTrail facts and hypothesis-specific snippets.

Prompts include the table name, generated `row_id`, CSV columns, current hypothesis, JSON contract, SQL safety rules, and optional prompt-safe domain context. Prompts do not include `hypotheses_outcomes.json`, expected rows, expected counts, answer-key row IDs, or previous hypotheses.

## AWS Domain Context

`aws_cloudtrail_domain_context_by_perplexity.md` is the source brief, with official AWS documentation URLs. `aws_domain_prompt_context.md` is the compact prompt-safe version. `domain_context.py` checks for obvious outcome-leak markers and selects global context plus the snippet relevant to the current hypothesis.

This context is not answer-key leakage. It contains CloudTrail field meanings and service/action mappings, for example:

- `signin.amazonaws.com` with `ConsoleLogin`.
- `sts.amazonaws.com` with `GetCallerIdentity`.
- `iam.amazonaws.com` with `CreateAccessKey`.
- `errorCode` values such as `AccessDenied` and `UnauthorizedOperation`.
- `requestParametersinstanceType` for EC2 `RunInstances`.

It also states uncertainty where AWS documentation does not define a threat label. The `kali`, `parrot`, `powershell`, `command/*`, and `10xlarge+` detections are treated as security heuristics, not AWS-defined malicious categories.

Expected outcomes are loaded only after SQL execution by `evaluator.py`.

## Repair Loop

Repair defaults to one attempt with `AI_STRIKE_REPAIR_ATTEMPTS=1`. It remains budget-friendly because repair only runs after SQL generation succeeds but DuckDB execution fails, so successful first-pass queries do not spend a second model request.

The repair prompt receives the hypothesis, schema, failed SQL, DuckDB error, prompt strategy, and optional domain context. It does not receive expected rows, expected counts, answer-key identifiers, or `hypotheses_outcomes.json`.

## Evaluation Metrics

For each hypothesis \(h_i\), the evaluator constructs a set of generated findings \(G_i\) and a set of expected findings \(E_i\). The set identity depends on the expected output shape: event IDs for raw event outputs when available, `row_id` when expected, normalized tuples over expected columns for raw outputs without IDs, and normalized tuples including `count` for aggregate outputs.

### Finding Sets

| Symbol | Meaning |
| --- | --- |
| \(G_i\) | Findings returned by the generated SQL for hypothesis \(h_i\). |
| \(E_i\) | Expected findings for hypothesis \(h_i\), loaded only after SQL execution. |
| \(N\) | Number of evaluated hypotheses. |

### Confusion Counts

| Count | Formula | Interpretation |
| --- | --- | --- |
| True positives | \(TP_i = |G_i \cap E_i|\) | Generated findings that match expected findings. |
| False positives | \(FP_i = |G_i \setminus E_i|\) | Extra findings returned by the generated query. |
| False negatives | \(FN_i = |E_i \setminus G_i|\) | Expected findings the generated query missed. |

### Per-Hypothesis Scores

| Metric | Formula | Zero-denominator rule |
| --- | --- | --- |
| Precision | \(P_i = \frac{TP_i}{TP_i + FP_i}\) | If \(TP_i + FP_i = 0\), precision is `0`. |
| Recall | \(R_i = \frac{TP_i}{TP_i + FN_i}\) | If \(TP_i + FN_i = 0\), recall is `0`. |
| F1 | \(F1_i = \frac{2P_iR_i}{P_i + R_i}\) | If \(P_i + R_i = 0\), F1 is `0`. |
| Exact match | \(FP_i = 0\), \(FN_i = 0\), and generated row count equals expected row count | Boolean. |
| Execution success | DuckDB accepted and executed the SQL | Boolean; measured separately from row correctness. |

### Macro Scores

```text
macro_precision = (1 / N) * sum(P_i for i = 1..N)
macro_recall    = (1 / N) * sum(R_i for i = 1..N)
macro_f1        = (1 / N) * sum(F1_i for i = 1..N)
```

| Rate | Formula |
| --- | --- |
| Exact-match rate | \(\frac{\text{number of exact-match hypotheses}}{N}\) |
| Execution-success rate | \(\frac{\text{number of DuckDB-successful hypotheses}}{N}\) |

### Why These Metrics

| Metric | Why it matters for threat hunting |
| --- | --- |
| Precision | False positives waste analyst time and can hide real incidents in noise. |
| Recall | False negatives are missed detections and therefore direct security risk. |
| F1 | Balances precision and recall into one detection-quality score. |
| Exact match | Catches perfect row-set equality and flags broad-but-partial answers. |
| Execution success | Separates SQL validity from detection quality. |
| Macro averages | Give each hypothesis equal weight, so high-volume hunts do not dominate small but high-signal hunts such as root console login. |

The generated `confidence` field is model-reported and should be treated as an explanation aid, not a statistically calibrated probability. In a production version, confidence calibration would compare confidence buckets against observed correctness, for example checking whether queries with confidence near 0.8 succeed roughly 80% of the time. In this submission, confidence is useful for analyst triage and report readability, while precision, recall, F1, exact match, and execution success are the measured outcomes.

## Raw And Aggregate Comparison

The evaluator chooses the comparison identity based on the expected output shape:

- Aggregate outputs with `count`: compare normalized tuples over all expected columns.
- Raw event outputs with `eventID`: compare by `eventID`.
- Raw event outputs with `row_id`: compare by generated row identity.
- Raw outputs without `eventID` or `row_id`: compare normalized tuples over the expected columns.

This supports both event-level hunts and aggregate hunts. It also keeps the evaluator honest when the correct answer is not a list of raw event IDs.

## Query Suggestions

`query_advisor.py` is deterministic. It inspects the generated SQL, execution status, row count, and metrics after evaluation. It can suggest adding filters, avoiding `SELECT *`, including `row_id` or `eventID`, or tightening overly broad queries.

It does not call the LLM and does not generate new SQL from expected rows. It is an analyst-facing quality note.

## Limitations And Future Work

- Real model behavior varies by provider, model version, latency, and prompt adherence.
- Provider API budget limits how much live A/B testing can be done.
- User-agent rules for `kali`, `parrot`, `powershell`, and `command/*` are heuristics, not AWS-defined threat labels.
- The `10xlarge+` EC2 rule is a custom assignment heuristic based on instance-type string parsing.
- Docker files are included, but Docker must be installed outside the project and may not be locally run where Docker is unavailable.
- More datasets need schema mapping updates, prompt context changes, and possibly evaluator identity changes.
- The evaluator checks known expected outputs, not analyst usefulness on unseen hypotheses.
- Repair is intentionally conservative; a richer repair loop could rank multiple candidate SQL queries but would cost more requests.

## Round 4 Modification Map

Common live changes are intentionally localized:

- Prompt wording: edit `prompts.py`.
- AWS/domain facts: edit `aws_domain_prompt_context.md`; source notes live in `aws_cloudtrail_domain_context_by_perplexity.md`.
- Domain snippet selection: edit `domain_context.py`.
- Cerebras model selection: edit `.env`, `AI_STRIKE_MODEL`, or pass `--model`.
- Evaluation rules and metric behavior: edit `evaluator.py`.
- SQL execution safety or row limits: edit `executor.py` or `AI_STRIKE_MAX_RESULT_ROWS`.
- Repair behavior: edit `repair.py` or set `AI_STRIKE_REPAIR_ATTEMPTS`.
- Streamlit controls and display: edit `app.py`.
- Experiments and budget checks: edit `experiments.py`.
- Benchmark reporting: edit `benchmark.py`.

The safest live workflow is:

1. Run `.\.venv\Scripts\python.exe launch_check.py`.
2. Run `.\.venv\Scripts\python.exe main.py --mock-llm --limit 1`.
3. Run `.\.venv\Scripts\python.exe launch_check.py --real`.
4. Run one Cerebras hypothesis with `--hypothesis-id`.
5. Only then run broader experiments or a full real evaluation.
