# Benchmark Report

This report records the final real Cerebras benchmark from the all-hypothesis evaluation. It replaces earlier mock-only benchmark numbers as the submission-facing benchmark.

## Overall Model Latency

| Model | Requests | Total s | Avg Generation | Avg Execution | Avg Evaluation | Avg Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `zai-glm-4.7` | 11 | 127.0302 | 0.0 | 0.0 | 0.0 | 11.417 |
| `gpt-oss-120b` | 11 | 119.1511 | 5.8887 | 4.7685 | 0.1416 | 10.7991 |
| `qwen-3-235b-a22b-instruct-2507` | 11 | 141.2777 | 0.8649 | 11.4506 | 0.4907 | 12.8068 |
| `llama3.1-8b` | 11 | 160.1374 | 0.6263 | 12.689 | 1.1336 | 14.4497 |

## Primary Model Per-Hypothesis Timing

| ID | Hypothesis | F1 | Generation | Execution | Evaluation | Total |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | Sign-in Failures (Brute Force/Bot Attacks) | 1.0 | 0.9687 | 3.7271 | 0.0112 | 4.7072 |
| 2 | Root Access Through Console | 1.0 | 0.6655 | 4.0414 | 0.0012 | 4.7083 |
| 3 | CloudTrail Disruption | 1.0 | 0.6992 | 4.2186 | 0.0119 | 4.9299 |
| 4 | Unauthorized API Calls | 0.995 | 0.7536 | 3.4108 | 0.3592 | 4.5237 |
| 5 | Whoami Reconnaissance | 1.0 | 0.8365 | 4.3338 | 0.7806 | 5.9521 |
| 6 | Secrets Manager Access | 1.0 | 1.0311 | 4.2287 | 0.0006 | 5.2607 |
| 7 | Large EC2 Instance Creation | 1.0 | 0.8908 | 3.7919 | 0.0115 | 4.6945 |
| 8 | S3 Bucket Brute Force | 0.887 | 56.2014 | 10.7847 | 0.0493 | 67.0356 |
| 9a | Suspicious User Agents | 0.995 | 0.782 | 5.563 | 0.2863 | 6.6315 |
| 9b | Suspicious User Agents | 1.0 | 0.9948 | 4.1164 | 0.02 | 5.1314 |
| 10 | Permanent Key Creation | 1.0 | 0.9518 | 4.237 | 0.0257 | 5.2147 |

## Benchmark Notes

- `gpt-oss-120b` and Qwen tied on quality; `gpt-oss-120b` had lower average total latency and is selected as primary.
- Execution time includes DuckDB scanning the large local CSV; generation time is only the model call portion captured by the pipeline.
- `zai-glm-4.7` benchmark time is provider wait/failure time because it did not return usable generated SQL.
