# Model Comparison Report

This report records the final live Cerebras model comparison across all 11 hypotheses with `aws_domain` prompts and repairs off.

## Recommendation

`gpt-oss-120b` is the primary submission model. It tied `qwen-3-235b-a22b-instruct-2507` at `0.9888` macro F1 (`98.88%`) and was faster on average. Qwen is the strongest fallback, `llama3.1-8b` is a cheap/light option, and `zai-glm-4.7` is not recommended because this Cerebras setup returned empty or invalid responses.

| Rank | Model | Role | Macro Precision | Macro Recall | Macro F1 | Exact Match | Success | Avg Total s |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `gpt-oss-120b` | Primary submission model | 0.9797 | 1.0 | 0.9888 | 0.6364 | 1.0 | 10.7991 |
| 2 | `qwen-3-235b-a22b-instruct-2507` | Secondary / strongest fallback | 0.9797 | 1.0 | 0.9888 | 0.6364 | 1.0 | 12.8068 |
| 3 | `llama3.1-8b` | Cheap/light option | 0.708 | 0.8182 | 0.7166 | 0.4545 | 1.0 | 14.4497 |
| 4 | `zai-glm-4.7` | Not recommended / unavailable in this setup | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 11.417 |

Expected outcomes are used only by the evaluator after SQL execution and are not included in prompts.
