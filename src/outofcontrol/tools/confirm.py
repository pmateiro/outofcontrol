from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from outofcontrol.tools.base import ToolRegistry, ToolResult, ToolSpec
from outofcontrol.tools.pending import PendingConfirmations


Executor = Callable[[dict[str, Any]], ToolResult]


def register_confirm_tools(
    registry: ToolRegistry,
    *,
    pending: PendingConfirmations,
    executors: dict[str, Executor],
) -> None:
    def confirm_action(confirmation_token: str, approve: bool = True) -> ToolResult:
        item = pending.pop(confirmation_token)
        if not item:
            return ToolResult(ok=False, output="Invalid or expired confirmation token")
        kind = item.get("kind", "unknown")
        if not approve:
            return ToolResult(
                ok=False,
                output=f"User denied sensitive action ({kind})",
                meta={"kind": kind},
            )
        executor = executors.get(kind)
        if not executor:
            return ToolResult(ok=False, output=f"No executor for pending kind: {kind}")
        payload = {k: v for k, v in item.items() if k != "kind"}
        return executor(payload)

    # Alias for older prompts / API clients
    def confirm_shell(confirmation_token: str, approve: bool = True) -> ToolResult:
        return confirm_action(confirmation_token, approve=approve)

    registry.register(
        ToolSpec(
            name="confirm_action",
            description=(
                "Approve or deny a pending sensitive action (shell, delete_file, etc.) "
                "using its confirmation_token."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "confirmation_token": {"type": "string"},
                    "approve": {"type": "boolean", "default": True},
                },
                "required": ["confirmation_token"],
            },
            handler=confirm_action,
        )
    )
    registry.register(
        ToolSpec(
            name="confirm_shell",
            description="Alias of confirm_action for pending shell commands.",
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


def shell_executor(workspace: Path) -> Executor:
    from outofcontrol.tools.shell import _run

    def execute(payload: dict[str, Any]) -> ToolResult:
        return _run(payload["command"], Path(payload.get("cwd") or workspace))

    return execute


def delete_file_executor(workspace: Path) -> Executor:
    def execute(payload: dict[str, Any]) -> ToolResult:
        from outofcontrol.tools.files import _safe_path

        rel = payload["path"]
        p = _safe_path(workspace, rel)
        if not p.exists():
            return ToolResult(ok=False, output=f"File not found: {rel}")
        if not p.is_file():
            return ToolResult(ok=False, output=f"Not a file: {rel}")
        p.unlink()
        return ToolResult(ok=True, output=f"Deleted {rel}")

    return execute


def github_pr_merge_executor() -> Executor:
    def execute(payload: dict[str, Any]) -> ToolResult:
        import shutil
        import subprocess

        number = payload["number"]
        repo = payload.get("repo")
        method = payload.get("method") or "squash"
        if method not in {"squash", "merge", "rebase"}:
            method = "squash"
        if not shutil.which("gh"):
            return ToolResult(ok=False, output="gh CLI required to merge PR")
        args = ["gh", "pr", "merge", str(number), f"--{method}"]
        if repo:
            args += ["--repo", repo]
        proc = subprocess.run(args, capture_output=True, text=True, timeout=120)
        out = ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")).strip()
        return ToolResult(ok=proc.returncode == 0, output=out or "(no output)")

    return execute
