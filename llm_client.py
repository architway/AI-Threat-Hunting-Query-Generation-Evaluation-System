from __future__ import annotations

import json
import re
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit


RAW_CLOUDTRAIL_COLUMNS = (
    "eventID, eventTime, sourceIPAddress, userAgent, eventName, eventSource, "
    "awsRegion, eventVersion, userIdentitytype, eventType, requestID, "
    "userIdentityaccountId, userIdentityprincipalId, userIdentityarn, "
    "userIdentityaccessKeyId, userIdentityuserName, errorCode, errorMessage, "
    "requestParametersinstanceType"
)


class LLMClient(Protocol):
    """Small interface shared by real provider clients and mock mode."""

    def complete(self, prompt: str) -> str:
        """Return the raw model text for one prompt."""


class LLMProviderError(RuntimeError):
    """Provider failures safe to surface in CLI and Streamlit diagnostics."""


class OpenAICompatibleClient:
    """Generic Chat Completions client used by the Cerebras path."""

    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        model: str | None,
        temperature: float = 0.0,
        max_completion_tokens: int = 1200,
        provider_name: str = "provider",
        api_key_env_var: str = "API key",
        default_headers: dict[str, str] | None = None,
    ) -> None:
        if _missing_or_placeholder_key(api_key):
            raise ValueError(
                f"{api_key_env_var} is required for real LLM mode. "
                "Use --mock-llm to run offline without an API key."
            )
        if not model:
            raise ValueError(
                f"AI_STRIKE_MODEL is required for {provider_name} mode. "
                "Set it in .env or pass --model."
            )
        if not base_url or not base_url.strip():
            raise ValueError(f"Base URL is required for {provider_name} mode.")

        from openai import OpenAI

        self.model = model
        self.model_label = model
        self.base_url = base_url.strip()
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens
        self.provider_name = provider_name
        kwargs = {"api_key": api_key, "base_url": self.base_url, "max_retries": 3}
        if default_headers:
            kwargs["default_headers"] = default_headers
        self.client = OpenAI(**kwargs)

    def complete(self, prompt: str) -> str:
        # This method creates a fresh request with a fresh message list every time.
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_completion_tokens=self.max_completion_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": self._system_prompt(),
                    },
                    {"role": "user", "content": self._user_prompt(prompt)},
                ],
            )
        except Exception as exc:
            raise LLMProviderError(_format_provider_error(self, exc)) from exc
        content = response.choices[0].message.content
        if not content:
            raise ValueError("The model returned an empty response.")
        return content

    def _system_prompt(self) -> str:
        prompt = (
            "You are an expert AWS threat hunter. Return only strict JSON that "
            "matches the requested schema."
        )
        if _uses_llama_contract_hint(self.model):
            prompt += (
                " For any hypothesis that asks for repeated, broad, clustered, "
                "volume, probing, reconnaissance, or grouped behavior, generate "
                "an aggregate SELECT: include every grouping column in both "
                "SELECT and GROUP BY, and include count(*) AS count in SELECT. "
                "When the user prompt or domain context gives an exact aggregate "
                "shape, follow those selected columns exactly and do not return "
                "the full raw CloudTrail event column set. Missing the requested "
                "count column is an invalid answer for aggregate hunts. "
                "If the expected shape is raw events, return identifying raw "
                "CloudTrail columns instead of aggregates. In DuckDB, "
                "regexp_matches(...) returns a boolean predicate; use it directly "
                "in WHERE clauses instead of appending IS NOT NULL. Common AWS "
                "aggregate hunt shapes are: Unauthorized API Calls -> eventName, "
                "userIdentityarn, count; Whoami/GetCallerIdentity -> "
                "userIdentityarn, sourceIPAddress, userAgent, count; S3 "
                "GetBucketAcl probing -> userIdentityarn, sourceIPAddress, "
                "userAgent, errorCode, count; suspicious kali/parrot/powershell "
                "user agents -> userIdentityarn, userAgent, count; suspicious "
                "command user agents -> the extracted command userAgent token, "
                "count; large EC2 RunInstances -> instanceType, count. The sql "
                "value must be one complete DuckDB SELECT or WITH query."
            )
        return prompt

    def _user_prompt(self, prompt: str) -> str:
        if not _uses_llama_contract_hint(self.model):
            return prompt

        return (
            prompt
            + "\n\nLlama model-specific contract reminder:\n"
            + "- If your SQL uses GROUP BY, the SELECT list must include "
            + "count(*) AS count.\n"
            + "- If the hypothesis asks for repeated, broad, clustered, volume, "
            + "probing, reconnaissance, or grouped behavior, use an aggregate "
            + "query and return the grouping columns plus count(*) AS count.\n"
            + "- Do not output an aggregate query with only group keys; that "
            + "omits the required count column.\n"
            + "- Keep raw-event hypotheses as raw identifying CloudTrail rows.\n"
        )


class CerebrasClient(OpenAICompatibleClient):
    """Cerebras client using its Chat Completions API."""

    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        model: str | None,
        temperature: float = 0.0,
        max_completion_tokens: int = 1200,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
            provider_name="Cerebras",
            api_key_env_var="CEREBRAS_API_KEY",
        )


class MockLLMClient:
    """Deterministic local generator for exercising the full pipeline offline."""

    def __init__(self, model_label: str = "mock-llm") -> None:
        self.model_label = model_label

    def complete(self, prompt: str) -> str:
        hypothesis_id = self._extract_field(prompt, "ID")
        name = self._extract_field(prompt, "Name")
        text = self._extract_field(prompt, "Text")
        sql = self._sql_for_hypothesis(name=name, text=text)

        return json.dumps(
            {
                "sql": sql,
                "confidence": 0.55,
                "hypothesis_interpretation": (
                    f"Mock interpretation for hypothesis {hypothesis_id}: {text}"
                ),
                "query_reasoning": (
                    "The mock client uses simple keyword rules so the local "
                    "DuckDB and evaluation pipeline can be tested without an API key."
                ),
                "threat_explanation": (
                    "These CloudTrail patterns can indicate suspicious AWS account "
                    "activity and should be reviewed by an analyst."
                ),
                "assumptions": [
                    "Mock mode is deterministic and is not scored as an LLM.",
                    "No expected outcome rows were used to build this SQL.",
                ],
            }
        )

    @staticmethod
    def _extract_field(prompt: str, field_name: str) -> str:
        match = re.search(rf"- {re.escape(field_name)}: (.+)", prompt)
        return match.group(1).strip() if match else ""

    def _sql_for_hypothesis(self, name: str, text: str) -> str:
        combined = f"{name} {text}".lower()

        if "sign-in" in combined or "failed console" in combined:
            return """
SELECT eventTime, sourceIPAddress, errorMessage, awsRegion, userIdentityuserName
FROM cloudtrail
WHERE eventName = 'ConsoleLogin'
  AND eventSource = 'signin.amazonaws.com'
  AND (
    errorCode IS NOT NULL
    OR errorMessage IS NOT NULL
    OR lower(coalesce(errorMessage, '')) LIKE '%fail%'
  )
""".strip()

        if "root" in combined and "console" in combined:
            return f"""
SELECT DISTINCT {RAW_CLOUDTRAIL_COLUMNS}
FROM cloudtrail
WHERE eventName = 'ConsoleLogin'
  AND userIdentitytype = 'Root'
""".strip()

        if "cloudtrail disruption" in combined or "disrupt cloudtrail" in combined:
            return """
SELECT eventTime, errorMessage, userIdentityarn, sourceIPAddress, eventName, userAgent, awsRegion
FROM cloudtrail
WHERE eventName IN ('StopLogging', 'DeleteTrail', 'UpdateTrail')
""".strip()

        if "unauthorized" in combined or "accessdenied" in combined:
            return """
SELECT eventName, userIdentityarn, count(*) AS count
FROM cloudtrail
WHERE errorCode IN ('AccessDenied', 'UnauthorizedOperation')
GROUP BY eventName, userIdentityarn
ORDER BY count DESC
""".strip()

        if "whoami" in combined or "getcalleridentity" in combined:
            return """
SELECT userIdentityarn, sourceIPAddress, userAgent, count(*) AS count
FROM cloudtrail
WHERE eventName = 'GetCallerIdentity'
GROUP BY userIdentityarn, sourceIPAddress, userAgent
ORDER BY count DESC
""".strip()

        if "secrets manager" in combined or "secret" in combined:
            return f"""
SELECT DISTINCT {RAW_CLOUDTRAIL_COLUMNS}
FROM cloudtrail
WHERE eventName = 'GetSecretValue'
""".strip()

        if "ec2" in combined or "10xlarge" in combined or "cryptomining" in combined:
            return """
SELECT requestParametersinstanceType AS instanceType, count(*) AS count
FROM cloudtrail
WHERE eventName = 'RunInstances'
  AND regexp_matches(coalesce(requestParametersinstanceType, ''), '[0-9]{2,}xlarge')
GROUP BY requestParametersinstanceType
ORDER BY count DESC
""".strip()

        if "s3" in combined or "getbucketacl" in combined:
            return """
SELECT userIdentityarn, sourceIPAddress, userAgent, errorCode, count(*) AS count
FROM cloudtrail
WHERE eventName = 'GetBucketAcl'
  AND errorCode IN ('AccessDenied', 'NoSuchBucket')
GROUP BY userIdentityarn, sourceIPAddress, userAgent, errorCode
ORDER BY count DESC
""".strip()

        if "command/*" in combined or "command/" in combined:
            return """
SELECT regexp_extract(userAgent, 'command/[^ ]+', 0) AS userAgent, count(*) AS count
FROM cloudtrail
WHERE lower(coalesce(userAgent, '')) LIKE '%command/%'
GROUP BY regexp_extract(userAgent, 'command/[^ ]+', 0)
ORDER BY count DESC
""".strip()

        if "user agent" in combined or "kali" in combined or "powershell" in combined:
            return """
SELECT userIdentityarn, userAgent, count(*) AS count
FROM cloudtrail
WHERE lower(coalesce(userAgent, '')) LIKE '%kali%'
   OR lower(coalesce(userAgent, '')) LIKE '%parrot%'
   OR lower(coalesce(userAgent, '')) LIKE '%powershell%'
GROUP BY userIdentityarn, userAgent
ORDER BY count DESC
""".strip()

        if "createaccesskey" in combined or "key creation" in combined:
            return """
SELECT sourceIPAddress, userIdentityarn, errorCode, errorMessage
FROM cloudtrail
WHERE eventName = 'CreateAccessKey'
  AND userIdentitytype = 'IAMUser'
""".strip()

        return "SELECT row_id, * FROM cloudtrail WHERE 1 = 0"


def _missing_or_placeholder_key(value: str | None) -> bool:
    if not value:
        return True
    lowered = value.strip().lower()
    return "paste_your" in lowered or lowered.startswith("your_")


def _format_provider_error(client: OpenAICompatibleClient, exc: Exception) -> str:
    status_code = getattr(exc, "status_code", None)
    error_code = getattr(exc, "code", None)
    exc_name = type(exc).__name__
    root = _root_cause(exc)
    root_name = type(root).__name__
    reason = _safe_exception_text(root) or _safe_exception_text(exc) or exc_name

    parts = [
        f"{client.provider_name} request failed",
        f"model={client.model}",
        f"base_url={_sanitize_url(client.base_url)}",
        f"error={exc_name}",
    ]
    if status_code:
        parts.append(f"status={status_code}")
    if error_code:
        parts.append(f"code={error_code}")
    if root is not exc:
        parts.append(f"root_cause={root_name}: {reason}")
    else:
        parts.append(f"detail={reason}")

    hint = _provider_error_hint(exc=exc, root=root, status_code=status_code)
    if hint:
        parts.append(f"hint={hint}")
    return "; ".join(parts)


def _root_cause(exc: Exception) -> BaseException:
    current: BaseException = exc
    seen: set[int] = set()
    while id(current) not in seen:
        seen.add(id(current))
        next_exc = current.__cause__ or current.__context__
        if next_exc is None:
            break
        current = next_exc
    return current


def _safe_exception_text(exc: BaseException) -> str:
    text = str(exc).strip()
    if not text:
        return ""
    return _redact_secrets(text)


def _provider_error_hint(
    exc: Exception,
    root: BaseException,
    status_code: int | None,
) -> str:
    names = f"{type(exc).__name__} {type(root).__name__}".lower()
    text = f"{_safe_exception_text(exc)} {_safe_exception_text(root)}".lower()
    if status_code in {401, 403}:
        return "check that the provider API key is valid and loaded by this process"
    if status_code == 404:
        return "check the model ID and provider base URL"
    if status_code == 429:
        return "provider rate limit or quota was reached; retry later or reduce requests"
    if "timeout" in names or "timed out" in text:
        return "request timed out; retry or lower completion tokens"
    if "connection" in names or "connection error" in text or "connect" in names:
        return (
            "check DNS/network/proxy/firewall access from the running Streamlit "
            "process, and restart Streamlit after .env changes"
        )
    return ""


def _sanitize_url(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return _redact_secrets(value.strip())
    if not parsed.scheme or not parsed.netloc:
        return _redact_secrets(value.strip())

    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path.rstrip("/"), "", ""))


def _redact_secrets(text: str) -> str:
    redacted = re.sub(
        r"(?i)(api[-_\s]?key\s*[:=]\s*)[^\s,;]+",
        r"\1[redacted]",
        text,
    )
    redacted = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+",
        r"\1[redacted]",
        redacted,
    )
    redacted = re.sub(
        r"\b(?:sk|csk|cer)[-_][A-Za-z0-9._-]{12,}\b",
        "[redacted]",
        redacted,
    )
    return redacted


def _uses_llama_contract_hint(model: str | None) -> bool:
    return bool(model and "llama3.1-8b" in model.lower())
