from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from config import AppConfig, PROJECT_ROOT, read_csv_schema
from executor import DuckDBExecutor
from pipeline import (
    build_llm_client,
    execute_run,
    load_hypotheses,
    print_run_summary,
    run_pipeline,
)
from prompts import available_prompt_strategies
from query_generator import QueryGenerator
from utils import load_hypotheses_outcomes


CEREBRAS_MODEL_OPTIONS = [
    "gpt-oss-120b",
    "qwen-3-235b-a22b-instruct-2507",
    "llama3.1-8b",
]
DEFAULT_CEREBRAS_MODEL = "gpt-oss-120b"


st.set_page_config(
    page_title="AI Strike Threat Hunting",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    base_config = AppConfig.from_env()
    _inject_css()

    st.title("AI Strike Threat Hunting Console")

    hypotheses = _load_hypotheses(base_config.hypotheses_path)
    selected = _sidebar_controls(base_config, hypotheses)
    config = selected["config"]

    if st.sidebar.button("Run hypothesis", type="primary", use_container_width=True):
        try:
            with st.spinner("Running local pipeline"):
                result = _run_selected_hypothesis(
                    config=config,
                    hypothesis=selected["hypothesis"],
                    use_mock=selected["use_mock"],
                    model_label=selected["model_label"],
                )
            st.session_state["last_result"] = result
        except Exception as exc:
            st.error(_display_error(exc))
            _render_real_mode_guidance(exc, use_mock=selected["use_mock"])

    if selected["use_mock"] and st.sidebar.button(
        "Run full mock evaluation",
        use_container_width=True,
    ):
        try:
            with st.spinner("Running all hypotheses in mock mode"):
                run = execute_run(
                    config=config,
                    use_mock=True,
                    write_outputs=True,
                )
            st.success(f"Saved run artifacts to {run.output_dir}")
            st.dataframe(
                [result.to_dict() for result in run.results],
                use_container_width=True,
                hide_index=True,
            )
            print_run_summary(run.output_dir, run.results)
        except Exception as exc:
            st.error(_display_error(exc))

    result = st.session_state.get("last_result")
    if result:
        _render_result(result)
    else:
        st.info("Select a hypothesis and run the pipeline.")


def _sidebar_controls(base_config: AppConfig, hypotheses: list) -> dict:
    st.sidebar.header("Run Controls")
    use_mock = st.sidebar.toggle("Mock LLM", value=True)
    provider = "cerebras"
    st.sidebar.selectbox("Provider", [provider], disabled=True)
    model_label = _model_selector(
        base_model=base_config.model,
        use_mock=use_mock,
    )
    if use_mock:
        st.sidebar.caption("Mock mode runs offline and never calls a model API.")
    else:
        st.sidebar.caption(
            "Cerebras is the real-provider launch path. Keep request budgets low "
            "during live comparisons."
        )
        st.sidebar.caption(_real_provider_status(base_config))

    prompt_strategy = st.sidebar.selectbox(
        "Prompt strategy",
        available_prompt_strategies(),
        index=available_prompt_strategies().index(base_config.prompt_strategy)
        if base_config.prompt_strategy in available_prompt_strategies()
        else 0,
    )
    repair_attempts = st.sidebar.number_input(
        "Repair attempts",
        min_value=0,
        max_value=3,
        value=base_config.repair_attempts,
        step=1,
    )
    max_result_rows = st.sidebar.number_input(
        "Max result rows",
        min_value=1,
        max_value=100000,
        value=base_config.max_result_rows,
        step=100,
    )
    selected_label = st.sidebar.selectbox(
        "Hypothesis",
        [f"{hypothesis.id}: {hypothesis.name}" for hypothesis in hypotheses],
    )
    selected_hypothesis = hypotheses[
        [f"{hypothesis.id}: {hypothesis.name}" for hypothesis in hypotheses].index(
            selected_label
        )
    ]

    config = AppConfig(
        data_path=base_config.data_path,
        hypotheses_path=base_config.hypotheses_path,
        outcomes_path=base_config.outcomes_path,
        output_root=base_config.output_root,
        root_evaluation_results_path=base_config.root_evaluation_results_path,
        comparison_results_path=base_config.comparison_results_path,
        benchmark_results_path=base_config.benchmark_results_path,
        domain_context_path=base_config.domain_context_path,
        provider=provider,
        cerebras_api_key=base_config.cerebras_api_key,
        cerebras_base_url=base_config.cerebras_base_url,
        model=model_label or base_config.model,
        temperature=base_config.temperature,
        max_completion_tokens=base_config.max_completion_tokens,
        max_result_rows=int(max_result_rows),
        prompt_strategy=prompt_strategy,
        repair_attempts=int(repair_attempts),
        request_budget=base_config.request_budget,
    )
    return {
        "config": config,
        "use_mock": use_mock,
        "model_label": model_label or "mock-llm",
        "hypothesis": selected_hypothesis,
    }


def _run_selected_hypothesis(
    config: AppConfig,
    hypothesis,
    use_mock: bool,
    model_label: str,
):
    schema = read_csv_schema(config.data_path)
    outcomes = load_hypotheses_outcomes(config.outcomes_path)
    llm_client = build_llm_client(
        config,
        use_mock=use_mock,
        model_name=model_label or config.model,
    )
    generator = QueryGenerator(llm_client)
    executor = DuckDBExecutor(config.data_path, config.max_result_rows)
    results = run_pipeline(
        selected_hypotheses=[hypothesis],
        schema=schema,
        outcomes=outcomes,
        generator=generator,
        executor=executor,
        prompt_strategy=config.prompt_strategy,
        repair_attempts=config.repair_attempts,
        domain_context_path=config.domain_context_path,
        verbose=False,
    )
    return results[0]


def _render_result(result) -> None:
    st.subheader(f"{result.hypothesis.id}: {result.hypothesis.name}")

    metrics = st.columns(6)
    metrics[0].metric("Precision", result.evaluation.precision)
    metrics[1].metric("Recall", result.evaluation.recall)
    metrics[2].metric("F1", result.evaluation.f1)
    metrics[3].metric("Rows", result.evaluation.generated_row_count)
    metrics[4].metric("Expected", result.evaluation.expected_row_count)
    metrics[5].metric("Seconds", result.total_seconds)

    if result.evaluation.execution_success:
        st.success("Execution succeeded")
    else:
        st.error(result.evaluation.error or "Execution failed")

    tabs = st.tabs(["SQL", "Explanation", "Suggestions", "Rows", "Artifact Row"])
    with tabs[0]:
        st.code(result.generated_query.sql if result.generated_query else "", "sql")
    with tabs[1]:
        generated = result.generated_query
        if generated:
            st.write("Hypothesis interpretation")
            st.write(generated.hypothesis_interpretation)
            st.write("Query reasoning")
            st.write(generated.query_reasoning)
            st.write("Threat explanation")
            st.write(generated.threat_explanation)
            st.write("Assumptions")
            st.write(generated.assumptions)
            st.write(f"Confidence: {generated.confidence}")
    with tabs[2]:
        for suggestion in result.query_suggestions:
            st.write(f"- {suggestion}")
    with tabs[3]:
        if result.execution and result.execution.success:
            st.dataframe(
                result.execution.dataframe.head(100),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.write("No generated rows to preview.")
    with tabs[4]:
        st.json(result.to_dict())


def _model_selector(base_model: str | None, use_mock: bool) -> str:
    if use_mock:
        st.sidebar.selectbox("Model", ["mock-llm"], disabled=True)
        return "mock-llm"

    options = CEREBRAS_MODEL_OPTIONS
    default_model = base_model if base_model in options else DEFAULT_CEREBRAS_MODEL
    index = options.index(default_model)
    return st.sidebar.selectbox("Model", options, index=index)


def _display_error(exc: Exception) -> str:
    message = str(exc).strip()
    return message or f"{type(exc).__name__}: see terminal logs for details."


def _render_real_mode_guidance(exc: Exception, use_mock: bool) -> None:
    if use_mock:
        return

    st.info(
        "Real Cerebras mode preflight: run `./.venv/Scripts/python.exe launch_check.py --real` "
        "in a terminal, then rerun this hypothesis."
    )
    st.info(
        "If you changed `.env`, stop all Streamlit terminals with Ctrl+C and restart with "
        "`./.venv/Scripts/streamlit.exe run app.py`."
    )

    text = str(exc).lower()
    if "winerror 10061" in text or "connectionrefusederror" in text:
        st.warning(
            "Connection refused ([WinError 10061]) means this machine could not connect "
            "to the Cerebras endpoint. Check internet access, firewall/proxy/DNS settings, "
            "or stale Streamlit processes. This is a provider connectivity issue, not a SQL "
            "or prompt-strategy failure."
        )


def _real_provider_status(config: AppConfig) -> str:
    key_loaded = "yes" if config.cerebras_api_key else "no"
    key_name = "CEREBRAS_API_KEY"
    return f"{key_name} loaded: {key_loaded}. Project .env reloads on each rerun."


@st.cache_data(show_spinner=False)
def _load_hypotheses(path: Path):
    return load_hypotheses(path)


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
          --strike-bg: #f5f2e9;
          --strike-panel: #ffffff;
          --strike-sidebar: #122018;
          --strike-sidebar-muted: #cbd8cb;
          --strike-text: #161a16;
          --strike-muted: #59635d;
          --strike-border: #d9d2c2;
          --strike-accent: #cf3f31;
          --strike-code: #101720;
        }
        .stApp {
          background: var(--strike-bg);
          color: var(--strike-text);
        }
        .stApp h1, .stApp h2, .stApp h3, .stApp h4,
        .stApp p, .stApp li, .stApp label, .stApp span {
          color: var(--strike-text);
        }
        [data-testid="stSidebar"] {
          background: var(--strike-sidebar);
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span {
          color: #f5f1e8;
        }
        [data-testid="stSidebar"] small,
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
          color: var(--strike-sidebar-muted);
        }
        [data-testid="stSidebar"] [data-baseweb="select"] > div,
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea,
        [data-testid="stSidebar"] [data-testid="stNumberInput"] input {
          background: #f8f5ed;
          color: #111712;
          border-color: #839184;
        }
        [data-testid="stSidebar"] [data-testid="stNumberInput"] button {
          background: #eef1e7;
          border-color: #839184;
          color: #111712;
        }
        [data-testid="stSidebar"] [data-testid="stNumberInput"] button svg {
          color: #111712;
          fill: #111712;
        }
        [data-testid="stSidebar"] svg {
          color: #111712;
          fill: #111712;
        }
        .stButton button {
          border-radius: 6px;
          border: 1px solid #26362e;
          font-weight: 650;
        }
        div[data-testid="stMetric"] {
          background: var(--strike-panel);
          border: 1px solid var(--strike-border);
          border-radius: 8px;
          padding: 0.7rem 0.8rem;
          color: var(--strike-text);
        }
        div[data-testid="stMetric"] * {
          color: var(--strike-text);
          opacity: 1;
        }
        div[data-testid="stAlert"] {
          color: var(--strike-text);
        }
        .stCodeBlock, .stJson, pre {
          background: var(--strike-code);
          color: #eef5ee;
          border-radius: 8px;
        }
        code, pre code {
          color: #eef5ee;
        }
        .stTabs [data-baseweb="tab-list"] {
          gap: 0.25rem;
        }
        .stTabs [data-baseweb="tab"] {
          border-radius: 6px 6px 0 0;
          color: var(--strike-muted);
        }
        .stTabs [aria-selected="true"] {
          color: var(--strike-accent);
        }
        div[data-testid="stDataFrame"],
        div[data-testid="stJson"] {
          border: 1px solid var(--strike-border);
          border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
