"""Data minimisation helpers: stable pseudonymous tokens for logs and LLM context."""

from __future__ import annotations

import hashlib
import hmac


class Pseudonymiser:
    """HMAC-SHA256 based, non-reversible, stable tokens (e.g. ``T-3f2a9c1b``)."""

    def __init__(self, key: str) -> None:
        self._key = key.encode("utf-8")

    def token(self, value: str, prefix: str = "P") -> str:
        digest = hmac.new(self._key, value.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{prefix}-{digest[:8]}"
