from __future__ import annotations

from pathlib import Path

from outofcontrol.tools.base import ToolRegistry, ToolResult, ToolSpec


def _safe_path(workspace: Path, rel: str) -> Path:
    target = (workspace / rel).resolve()
    if not str(target).startswith(str(workspace.resolve())):
        raise ValueError(f"Path escapes workspace: {rel}")
    return target


def register_file_tools(registry: ToolRegistry, *, workspace: Path) -> None:
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

    def search_files(query: str, path: str = ".", glob: str = "**/*") -> ToolResult:
        root = _safe_path(workspace, path)
        hits: list[str] = []
        for file in root.glob(glob):
            if not file.is_file():
                continue
            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if query in text:
                rel = file.relative_to(workspace)
                # first matching line
                for i, line in enumerate(text.splitlines(), 1):
                    if query in line:
                        hits.append(f"{rel}:{i}:{line.strip()[:200]}")
                        break
            if len(hits) >= 50:
                hits.append("...[truncated]")
                break
        return ToolResult(ok=True, output="\n".join(hits) or "No matches")

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
            name="search_files",
            description="Search for a literal string across files in the workspace.",
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
