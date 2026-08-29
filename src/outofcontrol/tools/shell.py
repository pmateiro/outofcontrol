from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from outofcontrol.tools.base import ConfirmCallback, ToolRegistry, ToolResult, ToolSpec
from outofcontrol.tools.pending import PendingConfirmations


def _is_sensitive(command: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if re.search(pat, command, flags=re.IGNORECASE):
            return True
    return False


def _needs_sudo(command: str) -> bool:
    # Match sudo as a command token, not substrings like "ok-sudo-path"
    return bool(re.search(r"(?:^|[\s;|&])sudo(?=\s|$)", command, flags=re.IGNORECASE))


def _inject_sudo_askpass(command: str) -> str:
    """Ensure every sudo invocation uses -A (askpass) for non-interactive daemons."""
    pattern = re.compile(r"(^|[\s;|&])sudo(?=\s|$)", re.IGNORECASE)

    def repl(match: re.Match[str]) -> str:
        end = match.end()
        after = command[end:].lstrip()
        if after.startswith("-A") or re.match(r"-[A-Za-z]*A\b", after):
            return match.group(0)
        return f"{match.group(1)}sudo -A"

    return pattern.sub(repl, command)


def _resolve_askpass() -> str | None:
    explicit = os.environ.get("OOC_ASKPASS") or os.environ.get("SUDO_ASKPASS")
    if explicit:
        if Path(explicit).exists() and os.access(explicit, os.X_OK):
            return explicit
        return None
    # Dev-tree / install fallbacks when unset
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "desktop" / "askpass" / "ooc-askpass",
        Path.home() / ".local/share/outofcontrol/app/desktop/askpass/ooc-askpass",
    ]
    for c in candidates:
        if c.exists() and os.access(c, os.X_OK):
            return str(c)
    return shutil.which("ssh-askpass")


def _run(command: str, cwd: Path, timeout: int = 120) -> ToolResult:
    env = os.environ.copy()
    run_cmd = command
    if _needs_sudo(command):
        askpass = _resolve_askpass()
        if askpass:
            env["SUDO_ASKPASS"] = askpass
            env["OOC_ASKPASS"] = askpass
            env.setdefault("SUDO_ASKPASS_REQUIRE", "force")
            run_cmd = _inject_sudo_askpass(command)
        else:
            # Fail early with a clear message instead of a silent sudo tty error
            return ToolResult(
                ok=False,
                output=(
                    "This command needs sudo, but no graphical askpass is configured.\n"
                    "Install zenity and ensure OOC_ASKPASS points to desktop/askpass/ooc-askpass "
                    "(re-run desktop/install-gnome.sh), or configure a limited sudoers NOPASSWD rule.\n"
                    f"Original command: {command}"
                ),
            )
    try:
        proc = subprocess.run(
            run_cmd,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(ok=False, output=f"Command timed out after {timeout}s")
    out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    out = out.strip() or "(no output)"
    if len(out) > 30_000:
        out = out[:30_000] + "\n...[truncated]"
    # Common non-interactive sudo failure hint
    if proc.returncode != 0 and _needs_sudo(command) and re.search(
        r"a password is required|no askpass|no tty|askpass", out, re.I
    ):
        out += (
            "\n\nHint: After approving in OutOfControl, a graphical password dialog should appear. "
            "If it did not, check that the daemon has your session DISPLAY/WAYLAND "
            "(restart: systemctl --user restart outofcontrol.service) and zenity is installed."
        )
    return ToolResult(
        ok=proc.returncode == 0,
        output=out,
        meta={"exit_code": proc.returncode, "ran": run_cmd},
    )


def register_shell_tools(
    registry: ToolRegistry,
    *,
    workspace: Path,
    patterns: list[str],
    confirm_sensitive: bool,
    confirm: ConfirmCallback | None,
    pending: PendingConfirmations,
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
            token = pending.store("shell", {"command": command, "cwd": str(cwd)})
            return ToolResult(
                ok=False,
                output=(
                    "Sensitive command requires confirmation. "
                    "Call confirm_action with the confirmation_token to proceed, "
                    "or tell the user and wait. "
                    "If the command uses sudo, approval will then trigger a graphical password prompt."
                ),
                needs_confirmation=True,
                confirmation_token=token,
                meta={"kind": "shell", "command": command},
            )
        return _run(command, cwd, timeout=timeout_seconds)

    registry.register(
        ToolSpec(
            name="run_shell",
            description=(
                "Run a shell command in the workspace. "
                "Sensitive commands may require confirmation via confirm_action. "
                "sudo uses a graphical askpass after approval when configured."
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
