# AI Strike Threat Hunting Query Generation

AI Strike turns natural-language AWS CloudTrail threat hunting hypotheses into executable DuckDB SQL, runs the SQL against the provided `nineteenFeaturesDf.csv` dataset, and evaluates the returned rows against `hypotheses_outcomes.json`. Each generated query includes an interpretation, reasoning, assumptions, confidence, execution status, and precision/recall/F1 metrics.

The project is offline-first. Mock mode exercises the full local pipeline without an API key, while live runs use Cerebras. The bonus layer includes a Streamlit demo, prompt strategy comparisons, benchmarking, one-attempt SQL repair after execution failures, Docker files, and AWS domain-context prompt tuning based on official AWS documentation.

The submission strategy is intentionally pragmatic: use official AWS/domain research, schema-aware prompting, deterministic local validation, inexpensive Cerebras-hosted model options, and an offline mock path to get high evaluation value without depending on repeated expensive frontier-model calls.

## Quick Start

Run these commands from the repository root in Windows PowerShell. The assignment CSV, `nineteenFeaturesDf.csv`, must be present in the repo root for CLI, GUI, and Docker paths.

### 1. Create And Activate A Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation on your machine, use the venv Python directly in the commands below:

```powershell
.\.venv\Scripts\python.exe --version
```

### 2. Install Dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Run Offline / Mock CLI Smoke

Mock mode makes no network calls and exercises the generator, DuckDB executor, evaluator, reports, and output artifacts:

```powershell
.\.venv\Scripts\python.exe launch_check.py
.\.venv\Scripts\python.exe main.py --mock-llm --prompt-strategy aws_domain --limit 1
```

### 4. Run Real Cerebras CLI

Copy `.env.example` to `.env`, fill in `CEREBRAS_API_KEY`, and keep the Cerebras settings:

```powershell
Copy-Item .env.example .env
notepad .env
```

```env
CEREBRAS_API_KEY=your_cerebras_key_here
CEREBRAS_BASE_URL=https://api.cerebras.ai/v1
AI_STRIKE_PROVIDER=cerebras
AI_STRIKE_MODEL=gpt-oss-120b
```

Then run a real one-hypothesis check before any broader evaluation:

```powershell
.\.venv\Scripts\python.exe launch_check.py --real
$env:AI_STRIKE_REQUEST_BUDGET="1"; .\.venv\Scripts\python.exe main.py --hypothesis-id 1 --prompt-strategy aws_domain --model gpt-oss-120b --repair-attempts 0 --verbose
```

Repair/healing defaults to `AI_STRIKE_REPAIR_ATTEMPTS=1`. It only uses a second model call when the first generated SQL is rejected by DuckDB; successful SQL does not trigger repair.

### 5. Run The Streamlit GUI

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

Streamlit prints a local URL after it starts. Open this in your browser:

```text
http://localhost:8501
```

The GUI opens in mock mode by default. Keep Mock mode on for an offline demo. Switch Mock mode off only after `.env` has a valid `CEREBRAS_API_KEY` and you select one of the Cerebras models in the sidebar. Press `Ctrl+C` in the terminal to stop the GUI server, and restart it after any `.env` or code changes.

Before switching to real mode in the GUI, run this CLI preflight:

```powershell
.\.venv\Scripts\python.exe launch_check.py --real
```

### 6. Run With Docker Compose

Docker Desktop or Docker Engine must be installed separately. Keep `nineteenFeaturesDf.csv` in the repo root; Compose mounts it into the container read-only.

```powershell
docker compose build
docker compose run --rm ai-strike-cli
docker compose run --rm ai-strike-cli python main.py --mock-llm --prompt-strategy aws_domain --limit 1
docker compose up ai-strike-demo
```

The Docker GUI also opens at `http://localhost:8501`.

## Setup

Use a local virtual environment so the assignment dependencies stay inside this project folder.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Cerebras Configuration

Mock mode does not need credentials. For real model calls, copy `.env.example` to `.env` and set the Cerebras key and model:

```powershell
Copy-Item .env.example .env
```

```env
CEREBRAS_API_KEY=your_cerebras_key_here
CEREBRAS_BASE_URL=https://api.cerebras.ai/v1
AI_STRIKE_PROVIDER=cerebras
AI_STRIKE_MODEL=gpt-oss-120b
AI_STRIKE_PROMPT_STRATEGY=aws_domain
AI_STRIKE_REPAIR_ATTEMPTS=1
AI_STRIKE_REQUEST_BUDGET=25
```

Use `AI_STRIKE_MODEL` for the Cerebras model ID you want to test. The saved comparison report selects `gpt-oss-120b` as the primary submission model, with `qwen-3-235b-a22b-instruct-2507` as the strongest fallback and `llama3.1-8b` as a cheaper/light option. `AI_STRIKE_REPAIR_ATTEMPTS=1` is the default; it only spends the extra request when DuckDB rejects the first generated SQL.

## Mock / Offline Mode

Mock mode runs the generator, DuckDB executor, evaluator, artifact writer, reports, benchmark hooks, and Streamlit path without network access:

```powershell
.\.venv\Scripts\python.exe main.py --mock-llm --limit 1
.\.venv\Scripts\python.exe main.py --hypothesis-id 1 --mock-llm --verbose
.\.venv\Scripts\python.exe main.py --mock-llm --prompt-strategy aws_domain --limit 2
```

The mock generator is deterministic. It is for smoke testing and repeatable local evaluation, not a claim about live model quality.

## Real Cerebras Runs

Real runs spend provider requests and tokens. Start small, verify JSON/SQL behavior on one hypothesis, then expand only after the launch check passes.

```powershell
.\.venv\Scripts\python.exe launch_check.py --real
$env:AI_STRIKE_REQUEST_BUDGET="1"; .\.venv\Scripts\python.exe main.py --hypothesis-id 1 --prompt-strategy aws_domain --model gpt-oss-120b --repair-attempts 0 --verbose
.\.venv\Scripts\python.exe main.py --hypothesis-id 4 --model gpt-oss-120b
.\.venv\Scripts\python.exe main.py --prompt-strategy aws_domain
```

Offline launch checks are also available:

```powershell
.\.venv\Scripts\python.exe launch_check.py
```

## Streamlit GUI

The Streamlit demo is a thin UI over the same pipeline used by the CLI. It supports hypothesis selection, mock or real mode, prompt strategy selection, repair-attempt control, SQL/explanation display, metrics, query suggestions, and result previews.

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

The GUI defaults to mock mode so it opens without an API key.

Real-mode troubleshooting:

- If `.env` changed, stop all running Streamlit terminals with `Ctrl+C`, then restart:
  `.\.venv\Scripts\streamlit.exe run app.py`
- If you see `[WinError 10061]` / `ConnectionRefusedError`, the local machine could not
  connect to `https://api.cerebras.ai/v1` from the running Streamlit process. Common causes:
  no internet, firewall/proxy policy, DNS/network issues, or a stale Streamlit process.
  This is a provider connectivity problem, not a SQL/prompt/custom-instruction failure.
- Some environments export dead local proxy variables (for example
  `HTTP_PROXY=http://127.0.0.1:9`, `HTTPS_PROXY=http://127.0.0.1:9`,
  `ALL_PROXY=http://127.0.0.1:9`). The Cerebras/OpenAI client in this project now ignores
  proxy environment variables by default (`trust_env=False`) to avoid that failure mode.
- To diagnose proxy variables in your shell:
  `Get-ChildItem Env: | Where-Object { $_.Name -match 'proxy' }`
- Run `.\.venv\Scripts\python.exe launch_check.py --real` before retrying real GUI mode.

Repair/healing defaults to one attempt. It only triggers when DuckDB rejects the first generated SQL, so successful first-pass queries do not spend an extra model request. You can still override it per run:

```powershell
.\.venv\Scripts\python.exe main.py --hypothesis-id 4 --repair-attempts 1
.\.venv\Scripts\python.exe main.py --hypothesis-id 4 --repair-attempts 0
$env:AI_STRIKE_REPAIR_ATTEMPTS = "1"; .\.venv\Scripts\streamlit.exe run app.py
```

## Experiments

Compare prompt strategies and model labels with the same evaluator:

```powershell
.\.venv\Scripts\python.exe experiments.py --mock-llm --strategies base,structured,multi_step,aws_domain --limit 2
.\.venv\Scripts\python.exe experiments.py --models gpt-oss-120b,qwen-3-235b-a22b-instruct-2507 --strategies aws_domain --limit 3 --request-budget 20
```

Outputs:

- `comparison_results.json`
- `comparison_summary.csv`
- `MODEL_COMPARISON_REPORT.md`

Real experiments estimate request count before starting and refuse to exceed `AI_STRIKE_REQUEST_BUDGET` or `--request-budget`.

## Benchmarking

Benchmark generation, DuckDB execution, evaluation, and total runtime:

```powershell
.\.venv\Scripts\python.exe benchmark.py --mock-llm --limit 2
.\.venv\Scripts\python.exe benchmark.py --mock-llm --prompt-strategy aws_domain --limit 2
.\.venv\Scripts\python.exe benchmark.py --hypothesis-id 4 --prompt-strategy aws_domain
```

Outputs:

- `benchmark_results.json`
- `BENCHMARK_REPORT.md`

## Output Files

Each CLI run writes a timestamped folder under `outputs/`:

```text
outputs/
  run_YYYYMMDD_HHMMSS/
    generated_queries.json
    evaluation_results.json
    summary.csv
    errors.json
```

The root-level `evaluation_results.json` is also written because the assignment calls it out as a deliverable. In the checked-in state it reflects the latest offline smoke run. `EVALUATION_REPORT.md` preserves that current artifact and also summarizes the saved final all-hypothesis Cerebras comparison from `benchmark_results.json` and `MODEL_COMPARISON_REPORT.md`.

Primary submission deliverables:

- `main.py`, `pipeline.py`, `query_generator.py`, `evaluator.py`, `executor.py`
- `README.md`, `APPROACH.md`, `EVALUATION_REPORT.md`
- `evaluation_results.json`
- `requirements.txt`
- Bonus artifacts: `app.py`, `Dockerfile`, `docker-compose.yml`, `benchmark.py`, `experiments.py`, `BENCHMARK_REPORT.md`, `MODEL_COMPARISON_REPORT.md`

## Submission Checklists

Required deliverables:

- [x] Core query generation logic: `query_generator.py`, `prompts.py`, `llm_client.py`, and `pipeline.py`
- [x] Evaluation framework implementation: `evaluator.py`
- [x] Entry point to run full evaluation: `main.py`
- [x] Dependencies: `requirements.txt`
- [x] Unit tests for key components
- [x] README with setup instructions, architecture overview, design decisions, trade-offs, and extension guidance
- [x] APPROACH.md with prompting strategy, iteration process, challenges, solutions, limitations, and future work
- [x] `evaluation_results.json` included evaluation output artifact
- [x] `EVALUATION_REPORT.md` with overall metrics, per-hypothesis breakdown, and before/after notes
- [x] Explainable generated output: interpretation, reasoning, assumptions, threat explanation, and confidence
- [x] Guardrail that expected outcomes are used only after SQL execution by the evaluator

Optional and bonus items:

- [x] Interactive demo: Streamlit UI in `app.py`
- [x] Containerization: `Dockerfile` and `docker-compose.yml`
- [x] Query optimization suggestions: deterministic post-evaluation advice in `query_advisor.py`
- [x] Prompt strategies and multi-step prompting: `base`, `structured`, `multi_step`, and `aws_domain`
- [x] Confidence scoring with explanations in each generated query
- [x] Automated SQL repair/healing after DuckDB failures via default `AI_STRIKE_REPAIR_ATTEMPTS=1`, `--repair-attempts`, or Streamlit
- [x] Extended evaluation: prompt strategy comparison with `experiments.py`
- [x] A/B model testing support through `experiments.py --models`
- [x] Performance benchmarks with `benchmark.py` and `BENCHMARK_REPORT.md`
- [x] Cerebras model comparison in `MODEL_COMPARISON_REPORT.md`
- [x] Offline mock mode for tests, demos, Docker smoke checks, and repeatable local evaluation

## Architecture

```text
hypotheses.json + CSV schema + optional AWS domain context
        |
        v
prompts.py -> query_generator.py -> Cerebras or MockLLMClient
        |
        v
DuckDB SQL against cloudtrail view over nineteenFeaturesDf.csv
        |
        v
executor.py -> evaluator.py -> query_advisor.py
        |
        v
outputs/, evaluation_results.json, reports, Streamlit, experiments, benchmarks
```

The expected outcomes are loaded only after SQL execution by the evaluator. They are not included in prompts, repair prompts, domain context, or reused chat history.

## Docker Optional

Docker is optional and separate from the `.venv` workflow. Docker Desktop or Docker Engine must be installed externally; it is not required for normal local runs.

Place `nineteenFeaturesDf.csv` in the project root first. The large CSV is excluded from the image by `.dockerignore` and mounted read-only at runtime by Compose.

Mock CLI smoke test:

```powershell
docker compose build
docker compose run --rm ai-strike-cli
docker compose run --rm ai-strike-cli python main.py --mock-llm --prompt-strategy aws_domain --limit 2
```

Streamlit demo:

```powershell
docker compose up ai-strike-demo
```

The demo service listens on `http://localhost:8501`.

Live Cerebras one-hypothesis run from PowerShell, using an environment variable already loaded on the host:

```powershell
$env:CEREBRAS_API_KEY = "your_cerebras_key_here"
docker compose run --rm -e CEREBRAS_API_KEY -e AI_STRIKE_PROVIDER=cerebras -e AI_STRIKE_MODEL=gpt-oss-120b ai-strike-cli python main.py --hypothesis-id 1 --prompt-strategy aws_domain
```

## Extending To Other Datasets

To adapt the project to another security dataset:

1. Point `AI_STRIKE_DATA_PATH` to the new CSV or update the executor for another source.
2. Update `hypotheses.json` and `hypotheses_outcomes.json`.
3. Adjust `aws_domain_prompt_context.md` or add a new domain-context file for the new schema and platform.
4. Update evaluator identity rules if the dataset uses different stable identifiers than `eventID`, `row_id`, or aggregate `count`.
5. Add prompt examples or strategy instructions only from safe domain knowledge, never from expected outcome rows.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe main.py --mock-llm --limit 1
```
