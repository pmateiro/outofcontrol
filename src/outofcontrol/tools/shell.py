from __future__ import annotations

import re
import secrets
import subprocess
from pathlib import Path
from typing import Any

from outofcontrol.tools.base import ConfirmCallback, ToolRegistry, ToolResult, ToolSpec


class PendingShell:
    def __init__(self) -> None:
        self._pending: dict[str, dict[str, Any]] = {}

    def store(self, command: str, cwd: str) -> str:
        token = secrets.token_urlsafe(12)
        self._pending[token] = {"command": command, "cwd": cwd}
        return token

    def pop(self, token: str) -> dict[str, Any] | None:
        return self._pending.pop(token, None)


def _is_sensitive(command: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if re.search(pat, command, flags=re.IGNORECASE):
            return True
    return False


def _run(command: str, cwd: Path, timeout: int = 120) -> ToolResult:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(ok=False, output=f"Command timed out after {timeout}s")
    out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    out = out.strip() or "(no output)"
    if len(out) > 30_000:
        out = out[:30_000] + "\n...[truncated]"
    return ToolResult(ok=proc.returncode == 0, output=out, meta={"exit_code": proc.returncode})


def register_shell_tools(
    registry: ToolRegistry,
    *,
    workspace: Path,
    patterns: list[str],
    confirm_sensitive: bool,
    confirm: ConfirmCallback | None,
    pending: PendingShell,
) -> None:
    def run_shell(command: str, timeout_seconds: int = 120) -> ToolResult:
        if not command or not str(command).strip():
            return ToolResult(ok=False, output="Empty command")
        cwd = workspace
        if confirm_sensitive and _is_sensitive(command, patterns):
            if confirm is not None:
                approved = confirm("run_shell", {"command": command, "cwd": str(cwd)})
                if not approved:
                    return ToolResult(ok=False, output="User denied sensitive shell command")
                return _run(command, cwd, timeout=timeout_seconds)
            token = pending.store(command, str(cwd))
            return ToolResult(
                ok=False,
                output=(
                    "Sensitive command requires confirmation. "
                    "Call confirm_shell with the confirmation_token to proceed, "
                    "or tell the user and wait."
                ),
                needs_confirmation=True,
                confirmation_token=token,
                meta={"command": command},
            )
        return _run(command, cwd, timeout=timeout_seconds)

    def confirm_shell(confirmation_token: str, approve: bool = True) -> ToolResult:
        item = pending.pop(confirmation_token)
        if not item:
            return ToolResult(ok=False, output="Invalid or expired confirmation token")
        if not approve:
            return ToolResult(ok=False, output="User denied sensitive shell command")
        return _run(item["command"], Path(item["cwd"]))

    registry.register(
        ToolSpec(
            name="run_shell",
            description=(
                "Run a shell command in the workspace. "
                "Sensitive commands may require confirmation."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 120)",
                        "default": 120,
                    },
                },
                "required": ["command"],
            },
            handler=run_shell,
            sensitive=True,
        )
    )
    registry.register(
        ToolSpec(
            name="confirm_shell",
            description=(
                "Approve or deny a pending sensitive shell command using its confirmation_token."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "confirmation_token": {"type": "string"},
                    "approve": {"type": "boolean", "default": True},
                },
                "required": ["confirmation_token"],
            },
            handler=confirm_shell,
        )
    )
