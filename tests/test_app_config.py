from app import DEFAULT_CEREBRAS_MODEL, CEREBRAS_MODEL_OPTIONS
from config import AppConfig


def test_streamlit_model_options_include_cerebras_models() -> None:
    assert CEREBRAS_MODEL_OPTIONS[0] == DEFAULT_CEREBRAS_MODEL
    assert "llama3.1-8b" in CEREBRAS_MODEL_OPTIONS
    assert "custom..." in CEREBRAS_MODEL_OPTIONS


def test_config_defaults_to_one_repair_attempt(monkeypatch) -> None:
    monkeypatch.delenv("AI_STRIKE_REPAIR_ATTEMPTS", raising=False)

    assert AppConfig().repair_attempts == 1
    assert AppConfig.from_env().repair_attempts == 1
