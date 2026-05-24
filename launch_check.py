from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from config import AppConfig, PROJECT_ROOT, read_csv_schema
from domain_context import (
    SOURCE_BRIEF_PATH,
    official_aws_urls_only,
    select_domain_context,
)
from pipeline import load_hypotheses
from prompts import available_prompt_strategies, build_prompt


@dataclass
class LaunchCheckResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def main() -> int:
    load_dotenv()
    args = parse_args()
    config = AppConfig.from_env()
    result = run_launch_checks(config, real_mode=args.real)
    print_launch_check_result(result, real_mode=args.real)
    return 0 if result.ok else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check offline and real-launch readiness for AI Strike."
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Also require provider API key and model configuration.",
    )
    return parser.parse_args()


def run_launch_checks(config: AppConfig, real_mode: bool = False) -> LaunchCheckResult:
    result = LaunchCheckResult()

    _check_path(result, config.data_path, "CloudTrail CSV")
    _check_path(result, config.hypotheses_path, "hypotheses JSON")
    _check_path(result, config.outcomes_path, "outcomes JSON")
    _check_path(result, config.domain_context_path, "AWS domain prompt context")
    _check_path(result, PROJECT_ROOT / ".env.example", ".env.example")

    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        result.info.append(".env file is present.")
    else:
        result.warnings.append(
            ".env is not present. Offline checks can still pass; create it for real runs."
        )

    if "aws_domain" not in available_prompt_strategies():
        result.errors.append("Prompt strategy 'aws_domain' is not registered.")

    if config.request_budget < 1:
        result.errors.append("AI_STRIKE_REQUEST_BUDGET must be at least 1.")
    else:
        result.info.append(f"Configured request budget: {config.request_budget}.")

    if config.max_completion_tokens < 200:
        result.warnings.append(
            "AI_STRIKE_MAX_COMPLETION_TOKENS is very low; JSON SQL responses may truncate."
        )
    else:
        result.info.append(
            f"Max completion tokens per request: {config.max_completion_tokens}."
        )

    if config.repair_attempts:
        result.warnings.append(
            "Repair attempts are enabled. Keep them at 0 for first real comparisons "
            "unless you intentionally want to spend extra model requests."
        )

    if SOURCE_BRIEF_PATH.exists():
        official_only, non_aws = official_aws_urls_only(SOURCE_BRIEF_PATH)
        if official_only:
            result.info.append("AWS source brief URLs are official docs.aws.amazon.com links.")
        else:
            result.errors.append(
                "AWS source brief contains non-official URLs: " + ", ".join(non_aws)
            )
    else:
        result.errors.append(f"AWS source brief missing: {SOURCE_BRIEF_PATH}")

    _check_prompt_safety(result, config)

    if real_mode:
        if config.provider != "cerebras":
            result.errors.append(
                f"AI_STRIKE_PROVIDER must be 'cerebras'. Got {config.provider!r}."
            )
        if config.provider == "cerebras" and _missing_or_placeholder(
            config.cerebras_api_key
        ):
            result.errors.append(
                "CEREBRAS_API_KEY is missing. Put it in .env before Cerebras runs."
            )
        if not config.model:
            result.errors.append(
                "AI_STRIKE_MODEL is missing. Set it in .env or pass --model."
            )
        if config.prompt_strategy != "aws_domain":
            result.warnings.append(
                "AI_STRIKE_PROMPT_STRATEGY is not aws_domain; use aws_domain for Phase 2 launch tests."
            )
    else:
        result.info.append(
            "Offline mode does not require a provider API key or AI_STRIKE_MODEL."
        )

    return result


def print_launch_check_result(result: LaunchCheckResult, real_mode: bool = False) -> None:
    mode = "real" if real_mode else "offline"
    print(f"Launch check ({mode}): {'PASS' if result.ok else 'FAIL'}")
    for item in result.info:
        print(f"[info] {item}")
    for item in result.warnings:
        print(f"[warn] {item}")
    for item in result.errors:
        print(f"[error] {item}")


def find_prompt_leak_markers(prompt: str, outcomes_path: Path) -> list[str]:
    markers = [
        "hypotheses_outcomes.json",
        "expected_row_count",
        "expected_count",
        "true_positives",
        "false_positives",
        "false_negatives",
        "answer-key row",
    ]
    found = [marker for marker in markers if marker.lower() in prompt.lower()]

    if outcomes_path.exists():
        try:
            data = json.loads(outcomes_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return found
        for value in _iter_outcome_identifier_values(data):
            if value in prompt:
                found.append(f"outcome identifier value {value!r}")

    return sorted(set(found))


def _check_path(result: LaunchCheckResult, path: Path, label: str) -> None:
    if path.exists():
        result.info.append(f"{label} found: {path}")
    else:
        result.errors.append(f"{label} missing: {path}")


def _check_prompt_safety(result: LaunchCheckResult, config: AppConfig) -> None:
    try:
        hypotheses = load_hypotheses(config.hypotheses_path)
        schema = read_csv_schema(config.data_path)
        if not hypotheses:
            result.errors.append("No hypotheses found.")
            return
        sample = hypotheses[0]
        domain_context = select_domain_context(sample, config.domain_context_path)
        prompt = build_prompt(
            sample,
            schema,
            domain_context=domain_context,
            strategy="aws_domain",
        )
    except Exception as exc:
        result.errors.append(f"Could not build sample aws_domain prompt: {exc}")
        return

    leaks = find_prompt_leak_markers(prompt, config.outcomes_path)
    if leaks:
        result.errors.append(
            "Sample aws_domain prompt contains possible outcome leak markers: "
            + ", ".join(leaks)
        )
    else:
        result.info.append(
            "Sample aws_domain prompt excludes outcomes file names and outcome identifiers."
        )


def _iter_outcome_identifier_values(data) -> list[str]:
    values: list[str] = []
    for row in _iter_dicts(data):
        for key in ("eventID", "requestID", "userIdentityaccessKeyId"):
            value = row.get(key)
            if isinstance(value, str) and _looks_like_identifier(value):
                values.append(value)
    return values


def _iter_dicts(value):
    if isinstance(value, dict):
        if any(not isinstance(item, (dict, list)) for item in value.values()):
            yield value
        for item in value.values():
            yield from _iter_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_dicts(item)


def _looks_like_identifier(value: str) -> bool:
    if len(value) < 12:
        return False
    if re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{13,}", value):
        return True
    if re.search(r"[A-Z0-9]{12,}", value):
        return True
    return False


def _missing_or_placeholder(value: str | None) -> bool:
    if not value:
        return True
    lowered = value.strip().lower()
    return "paste_your" in lowered or lowered.startswith("your_")


if __name__ == "__main__":
    raise SystemExit(main())
