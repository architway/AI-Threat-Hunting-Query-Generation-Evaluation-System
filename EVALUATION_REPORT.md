# Evaluation Report

## Executive Summary

The final submission target is met. The expected quality bar was approximately 85%+; the selected primary model, `gpt-oss-120b`, reached `0.9888` macro F1 (`98.88%`) across all 11 CloudTrail hypotheses.

`gpt-oss-120b` and `qwen-3-235b-a22b-instruct-2507` tied on macro F1. `gpt-oss-120b` is selected as the primary submission model because it had lower average total latency in the final run. Qwen remains the strongest fallback. `llama3.1-8b` is a lower-cost/light option with lower accuracy. `zai-glm-4.7` is not recommended in this Cerebras setup because it returned empty or invalid responses.

Expected outcomes were used only by the local evaluator after SQL execution. They were not included in generation prompts, repair prompts, domain context, or reused chat history.

## Run Configuration

- Provider: `cerebras`
- Prompt strategy: `aws_domain`
- Primary model: `gpt-oss-120b`
- Repair attempts: `0`
- Hypotheses evaluated: `11`

## Primary Model Metrics

| Model | Macro Precision | Macro Recall | Macro F1 | Exact Match | Execution Success | Avg Total Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gpt-oss-120b` | 0.9797 | 1.0 | 0.9888 | 0.6364 | 1.0 | 10.7991s |

## Per-Hypothesis Breakdown For Primary Model

| ID | Hypothesis | Precision | Recall | F1 | Exact | Rows Generated / Expected | Total s |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: |
| 1 | Sign-in Failures (Brute Force/Bot Attacks) | 1.0 | 1.0 | 1.0 | True | 12 / 12 | 4.7072 |
| 2 | Root Access Through Console | 1.0 | 1.0 | 1.0 | False | 62 / 61 | 4.7083 |
| 3 | CloudTrail Disruption | 1.0 | 1.0 | 1.0 | True | 4 / 4 | 4.9299 |
| 4 | Unauthorized API Calls | 0.99 | 1.0 | 0.995 | False | 2411 / 2387 | 4.5237 |
| 5 | Whoami Reconnaissance | 1.0 | 1.0 | 1.0 | True | 4767 / 4767 | 5.9521 |
| 6 | Secrets Manager Access | 1.0 | 1.0 | 1.0 | True | 1 / 1 | 5.2607 |
| 7 | Large EC2 Instance Creation | 1.0 | 1.0 | 1.0 | True | 34 / 34 | 4.6945 |
| 8 | S3 Bucket Brute Force | 0.797 | 1.0 | 0.887 | False | 266 / 212 | 67.0356 |
| 9a | Suspicious User Agents | 0.9901 | 1.0 | 0.995 | False | 1915 / 1896 | 6.6315 |
| 9b | Suspicious User Agents | 1.0 | 1.0 | 1.0 | True | 101 / 101 | 5.1314 |
| 10 | Permanent Key Creation | 1.0 | 1.0 | 1.0 | True | 40 / 40 | 5.2147 |

## Before / After Improvement

| Stage | Model / Strategy | Scope | Macro F1 | Notes |
| --- | --- | --- | ---: | --- |
| Initial real prompt round | `gpt-oss-120b` + `aws_domain` | all 11 hypotheses | 0.9367 | Strong baseline, but weak H8/H9b behavior. |
| Final tuned prompt round | `gpt-oss-120b` + `aws_domain` | all 11 hypotheses | 0.9888 | Improved weak aggregate/userAgent handling without answer-key rows in prompts. |
| Final tied fallback | `qwen-3-235b-a22b-instruct-2507` + `aws_domain` | all 11 hypotheses | 0.9888 | Same macro F1, higher average total latency in this run. |

## Final Multi-Model Comparison

| Rank | Model | Role | Macro F1 | Exact Match | Success | Avg Total s |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 1 | `gpt-oss-120b` | Primary submission model | 0.9888 | 0.6364 | 1.0 | 10.7991 |
| 2 | `qwen-3-235b-a22b-instruct-2507` | Secondary / strongest fallback | 0.9888 | 0.6364 | 1.0 | 12.8068 |
| 3 | `llama3.1-8b` | Cheap/light option | 0.7166 | 0.4545 | 1.0 | 14.4497 |
| 4 | `zai-glm-4.7` | Not recommended / unavailable in this setup | 0.0 | 0.0 | 0.0 | 11.417 |

## Failure Patterns And Limitations

- H8 S3 bucket probing remains the hardest high-scoring case because the safest general query captures all expected rows but also includes some extra denied bucket-probing patterns, so precision is below 1.0 while recall is 1.0.
- `zai-glm-4.7` is excluded from recommendation because the Cerebras endpoint returned empty or invalid responses during this run.
- `llama3.1-8b` executed valid SQL but missed aggregate output shape or over-broadened some filters, so it is kept only as a light fallback.
- The optional repair loop is intentionally off for final scoring. It repairs SQL execution errors, not semantic low-F1 misses, and it can spend extra model requests.

## Explainability

Each generated query record in `evaluation_results.json` includes model confidence, interpretation, query reasoning, threat explanation, assumptions, generated SQL, execution result, precision/recall/F1 metrics, and timing fields.
