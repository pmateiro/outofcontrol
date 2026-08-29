from __future__ import annotations

import re
from pathlib import Path

from outofcontrol.tools.base import ConfirmCallback, ToolRegistry, ToolResult, ToolSpec
from outofcontrol.tools.pending import PendingConfirmations

_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}


def _safe_path(workspace: Path, rel: str) -> Path:
    target = (workspace / rel).resolve()
    ws = str(workspace.resolve())
    if target != workspace.resolve() and not str(target).startswith(ws + "/"):
        # allow exact workspace root
        if str(target) != ws:
            raise ValueError(f"Path escapes workspace: {rel}")
    return target


def _should_skip(path: Path) -> bool:
    return any(part in _SKIP_DIRS for part in path.parts)


def register_file_tools(
    registry: ToolRegistry,
    *,
    workspace: Path,
    confirm_sensitive: bool = True,
    confirm: ConfirmCallback | None = None,
    pending: PendingConfirmations | None = None,
) -> None:
    def read_file(path: str) -> ToolResult:
        p = _safe_path(workspace, path)
        if not p.exists():
            return ToolResult(ok=False, output=f"File not found: {path}")
        if not p.is_file():
            return ToolResult(ok=False, output=f"Not a file: {path}")
        text = p.read_text(encoding="utf-8", errors="replace")
        if len(text) > 100_000:
            text = text[:100_000] + "\n...[truncated]"
        return ToolResult(ok=True, output=text)

    def write_file(path: str, content: str) -> ToolResult:
        p = _safe_path(workspace, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return ToolResult(ok=True, output=f"Wrote {len(content)} bytes to {path}")

    def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> ToolResult:
        if old_string == new_string:
            return ToolResult(ok=False, output="old_string and new_string are identical")
        if not old_string:
            return ToolResult(ok=False, output="old_string must not be empty")
        p = _safe_path(workspace, path)
        if not p.exists() or not p.is_file():
            return ToolResult(ok=False, output=f"File not found: {path}")
        text = p.read_text(encoding="utf-8")
        count = text.count(old_string)
        if count == 0:
            return ToolResult(ok=False, output=f"old_string not found in {path}")
        if count > 1 and not replace_all:
            return ToolResult(
                ok=False,
                output=(
                    f"old_string found {count} times in {path}. "
                    "Pass replace_all=true or provide a more unique old_string."
                ),
            )
        if replace_all:
            updated = text.replace(old_string, new_string)
            n = count
        else:
            updated = text.replace(old_string, new_string, 1)
            n = 1
        p.write_text(updated, encoding="utf-8")
        return ToolResult(ok=True, output=f"Updated {path} ({n} replacement(s))")

    def delete_file(path: str) -> ToolResult:
        p = _safe_path(workspace, path)
        if not p.exists():
            return ToolResult(ok=False, output=f"File not found: {path}")
        if not p.is_file():
            return ToolResult(ok=False, output=f"Not a file: {path}")
        if confirm_sensitive:
            payload = {"path": path}
            if confirm is not None:
                approved = confirm("delete_file", payload)
                if not approved:
                    return ToolResult(ok=False, output="User denied file deletion")
                p.unlink()
                return ToolResult(ok=True, output=f"Deleted {path}")
            if pending is None:
                return ToolResult(ok=False, output="Confirmation required but pending store missing")
            token = pending.store("delete_file", payload)
            return ToolResult(
                ok=False,
                output=(
                    "Deleting a file requires confirmation. "
                    "Call confirm_action with the confirmation_token to proceed."
                ),
                needs_confirmation=True,
                confirmation_token=token,
                meta={"kind": "delete_file", "path": path},
            )
        p.unlink()
        return ToolResult(ok=True, output=f"Deleted {path}")

    def list_dir(path: str = ".") -> ToolResult:
        p = _safe_path(workspace, path)
        if not p.exists():
            return ToolResult(ok=False, output=f"Not found: {path}")
        if not p.is_dir():
            return ToolResult(ok=False, output=f"Not a directory: {path}")
        entries = []
        for child in sorted(p.iterdir()):
            kind = "dir" if child.is_dir() else "file"
            entries.append(f"{kind}\t{child.name}")
        return ToolResult(ok=True, output="\n".join(entries) or "(empty)")

    def glob_files(pattern: str, path: str = ".") -> ToolResult:
        root = _safe_path(workspace, path)
        if not root.exists():
            return ToolResult(ok=False, output=f"Not found: {path}")
        matches: list[str] = []
        for file in sorted(root.glob(pattern)):
            if _should_skip(file.relative_to(workspace)):
                continue
            if file.is_file():
                matches.append(str(file.relative_to(workspace)))
            if len(matches) >= 200:
                matches.append("...[truncated]")
                break
        return ToolResult(ok=True, output="\n".join(matches) or "No matches")

    def grep(
        pattern: str,
        path: str = ".",
        glob: str = "**/*",
        case_insensitive: bool = False,
        max_hits: int = 50,
    ) -> ToolResult:
        root = _safe_path(workspace, path)
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            rx = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(ok=False, output=f"Invalid regex: {e}")
        hits: list[str] = []
        for file in root.glob(glob):
            if not file.is_file() or _should_skip(file.relative_to(workspace)):
                continue
            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = file.relative_to(workspace)
            for i, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{rel}:{i}:{line.strip()[:200]}")
                    if len(hits) >= max_hits:
                        hits.append("...[truncated]")
                        return ToolResult(ok=True, output="\n".join(hits))
        return ToolResult(ok=True, output="\n".join(hits) or "No matches")

    def search_files(query: str, path: str = ".", glob: str = "**/*") -> ToolResult:
        # Literal search kept for compatibility; prefer grep for regex.
        return grep(re.escape(query), path=path, glob=glob)

    registry.register(
        ToolSpec(
            name="read_file",
            description="Read a text file relative to the workspace.",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            handler=read_file,
        )
    )
    registry.register(
        ToolSpec(
            name="write_file",
            description="Write/overwrite a text file relative to the workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            handler=write_file,
        )
    )
    registry.register(
        ToolSpec(
            name="edit_file",
            description=(
                "Replace an exact substring in a file (surgical edit). "
                "Fails if old_string is missing or not unique unless replace_all=true."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                    "replace_all": {"type": "boolean", "default": False},
                },
                "required": ["path", "old_string", "new_string"],
            },
            handler=edit_file,
        )
    )
    registry.register(
        ToolSpec(
            name="delete_file",
            description="Delete a file in the workspace (requires confirmation when enabled).",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            handler=delete_file,
            sensitive=True,
        )
    )
    registry.register(
        ToolSpec(
            name="list_dir",
            description="List files and directories under a workspace path.",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}},
            },
            handler=list_dir,
        )
    )
    registry.register(
        ToolSpec(
            name="glob_files",
            description="Find files by glob pattern under a workspace path (e.g. **/*.py).",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                },
                "required": ["pattern"],
            },
            handler=glob_files,
        )
    )
    registry.register(
        ToolSpec(
            name="grep",
            description="Search file contents with a regular expression; returns path:line:snippet.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "glob": {"type": "string", "default": "**/*"},
                    "case_insensitive": {"type": "boolean", "default": False},
                    "max_hits": {"type": "integer", "default": 50},
                },
                "required": ["pattern"],
            },
            handler=grep,
        )
    )
    registry.register(
        ToolSpec(
            name="search_files",
            description="Literal substring search across files (wrapper around grep).",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "glob": {"type": "string", "default": "**/*"},
                },
                "required": ["query"],
            },
            handler=search_files,
        )
    )
