from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from config import PROJECT_ROOT
from models import Hypothesis


DEFAULT_DOMAIN_CONTEXT_PATH = PROJECT_ROOT / "aws_domain_prompt_context.md"
SOURCE_BRIEF_PATH = PROJECT_ROOT / "aws_cloudtrail_domain_context_by_perplexity.md"

FORBIDDEN_CONTEXT_MARKERS = (
    "hypotheses_outcomes.json",
    "expected_row_count",
    "expected rows:",
    "expected counts:",
    "answer-key row",
)


def load_domain_context(path: Path | None = None) -> str:
    """Load compact AWS context and reject obvious outcome-leak markers."""

    context_path = path or DEFAULT_DOMAIN_CONTEXT_PATH
    text = _read_context_file(context_path)
    markers = find_forbidden_context_markers(text)
    if markers:
        raise ValueError(
            "Domain context contains prompt-unsafe markers: "
            f"{', '.join(sorted(markers))}"
        )
    return text


def select_domain_context(
    hypothesis: Hypothesis,
    path: Path | None = None,
    max_chars: int = 6000,
) -> str:
    """Return global AWS facts plus the snippet most relevant to one hypothesis."""

    full_context = load_domain_context(path)
    sections = _split_markdown_sections(full_context)
    selected: list[str] = []

    for heading in ("Always Include", "Identity And Error Fields"):
        section = sections.get(heading)
        if section:
            selected.append(section)

    snippet = _hypothesis_section(sections, hypothesis)
    if snippet:
        selected.append(snippet)

    if hypothesis.id.lower() in {"9a", "9b", "7"}:
        # Keep the uncertainty guidance close to the heuristic-heavy prompts.
        for heading, section in sections.items():
            if heading.startswith("H9") and section not in selected:
                selected.append(section)

    compact = "\n\n".join(selected).strip()
    if not compact:
        compact = full_context.strip()

    if len(compact) > max_chars:
        return compact[: max_chars - 80].rstrip() + "\n\n[Domain context truncated.]"
    return compact


def find_forbidden_context_markers(text: str) -> set[str]:
    lowered = text.lower()
    return {marker for marker in FORBIDDEN_CONTEXT_MARKERS if marker in lowered}


def official_aws_urls_only(path: Path = SOURCE_BRIEF_PATH) -> tuple[bool, list[str]]:
    """Check that URLs in the source brief point at official AWS documentation."""

    text = path.read_text(encoding="utf-8")
    urls = re.findall(r"https?://[^\s)>\]]+", text)
    non_aws = [
        url.rstrip(".,")
        for url in urls
        if not url.rstrip(".,").startswith("https://docs.aws.amazon.com/")
    ]
    return not non_aws, non_aws


@lru_cache(maxsize=8)
def _read_context_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Domain context file not found: {path}")
    return path.read_text(encoding="utf-8")


def _split_markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        heading_match = re.match(r"^##\s+(.+?)\s*$", line)
        if heading_match:
            if current_heading:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = heading_match.group(1).strip()
            current_lines = [line]
            continue
        if current_heading:
            current_lines.append(line)

    if current_heading:
        sections[current_heading] = "\n".join(current_lines).strip()
    return sections


def _hypothesis_section(
    sections: dict[str, str],
    hypothesis: Hypothesis,
) -> str | None:
    expected_prefix = f"H{hypothesis.id}".lower()
    for heading, section in sections.items():
        if heading.lower().startswith(expected_prefix):
            return section

    text = f"{hypothesis.name} {hypothesis.hypothesis}".lower()
    keyword_map = {
        "console": "H1",
        "root": "H2",
        "cloudtrail": "H3",
        "unauthorized": "H4",
        "accessdenied": "H4",
        "getcalleridentity": "H5",
        "secret": "H6",
        "runinstances": "H7",
        "10xlarge": "H7",
        "getbucketacl": "H8",
        "kali": "H9a",
        "parrot": "H9a",
        "powershell": "H9a",
        "command/": "H9b",
        "createaccesskey": "H10",
    }
    for keyword, prefix in keyword_map.items():
        if keyword in text:
            for heading, section in sections.items():
                if heading.lower().startswith(prefix.lower()):
                    return section
    return None
