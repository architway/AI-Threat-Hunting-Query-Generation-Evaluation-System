# Benchmark Report

This benchmark records the selected primary submission run: `gpt-oss-120b` on Cerebras with the `aws_domain` prompt strategy and repairs off.

## Average Timings

- Generation seconds: 5.8887
- Execution seconds: 4.7685
- Evaluation seconds: 0.1416
- Total seconds: 10.7991

## Per-Hypothesis Timings

| ID | Name | F1 | Generation | Execution | Evaluation | Total |
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

## Notes

- Timings are the recorded per-hypothesis measurements from the final primary-model run.
- Execution time includes DuckDB scanning the local CloudTrail CSV; generation time is the model-call portion captured by the pipeline.
- Multi-model latency and recommendation details are kept in `MODEL_COMPARISON_REPORT.md`, not mixed into this benchmark JSON.
