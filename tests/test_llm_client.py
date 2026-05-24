import sys
import types

from llm_client import OpenAICompatibleClient


def test_openai_compatible_client_ignores_proxy_env(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyHttpClient:
        def __init__(self, trust_env: bool) -> None:
            captured["trust_env"] = trust_env

    class DummyOpenAI:
        def __init__(self, **kwargs) -> None:
            captured["openai_kwargs"] = kwargs

    monkeypatch.setitem(
        sys.modules,
        "httpx",
        types.SimpleNamespace(Client=DummyHttpClient),
    )
    monkeypatch.setitem(
        sys.modules,
        "openai",
        types.SimpleNamespace(OpenAI=DummyOpenAI),
    )

    client = OpenAICompatibleClient(
        api_key="cer_test_key_value",
        base_url="https://api.cerebras.ai/v1",
        model="gpt-oss-120b",
        provider_name="Cerebras",
        api_key_env_var="CEREBRAS_API_KEY",
    )

    assert captured["trust_env"] is False
    assert captured["openai_kwargs"]["http_client"] is client.http_client
