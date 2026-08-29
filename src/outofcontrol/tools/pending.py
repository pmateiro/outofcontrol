from __future__ import annotations

import secrets
from typing import Any


class PendingConfirmations:
    """Token store for sensitive actions that need user approval (shell, delete, etc.)."""

    def __init__(self) -> None:
        self._pending: dict[str, dict[str, Any]] = {}

    def store(self, kind: str, payload: dict[str, Any]) -> str:
        token = secrets.token_urlsafe(12)
        self._pending[token] = {"kind": kind, **payload}
        return token

    def pop(self, token: str) -> dict[str, Any] | None:
        return self._pending.pop(token, None)

    def peek(self, token: str) -> dict[str, Any] | None:
        return self._pending.get(token)


# Backwards-compatible alias used by older call sites
PendingShell = PendingConfirmations
