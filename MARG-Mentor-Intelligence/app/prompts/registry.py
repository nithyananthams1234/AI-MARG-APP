"""Versioned prompt files: ``app/prompts/<prompt_id>/<version>.md``.

Every LLM call records the prompt id and version. Prompts contain no volatile values (dates, IDs),
so the system prompt prefix stays stable and cacheable.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPT_ROOT = Path(__file__).parent
PREAMBLE_ID = "_shared_preamble"
DEFAULT_VERSION = "v1"


class PromptNotFoundError(LookupError):
    pass


@lru_cache
def load_prompt(prompt_id: str, version: str = DEFAULT_VERSION) -> str:
    if "/" in prompt_id or "\\" in prompt_id or ".." in prompt_id:
        raise PromptNotFoundError(f"Invalid prompt id {prompt_id!r}")
    path = PROMPT_ROOT / prompt_id / f"{version}.md"
    if not path.is_file():
        raise PromptNotFoundError(f"Prompt {prompt_id}/{version} not found")
    return path.read_text(encoding="utf-8").strip()


def system_prompt(prompt_id: str, version: str = DEFAULT_VERSION) -> str:
    return f"{load_prompt(PREAMBLE_ID)}\n\n{load_prompt(prompt_id, version)}"
