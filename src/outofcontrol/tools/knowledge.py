from __future__ import annotations

from pathlib import Path

from outofcontrol.tools.base import ToolRegistry, ToolResult, ToolSpec

_SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}


def register_knowledge_tools(registry: ToolRegistry, *, knowledge_dir: Path) -> None:
    def knowledge_list(glob: str = "**/*.{md,txt,rst}") -> ToolResult:
        if not knowledge_dir.exists():
            return ToolResult(
                ok=True,
                output=f"Knowledge dir missing: {knowledge_dir}. Create it or set knowledge_dir.",
            )
        # pathlib doesn't expand brace globs — do simple variants
        patterns = ["**/*.md", "**/*.txt", "**/*.rst"] if "{md" in glob else [glob]
        files: list[str] = []
        for pat in patterns:
            for p in sorted(knowledge_dir.glob(pat)):
                if not p.is_file():
                    continue
                if any(part in _SKIP for part in p.parts):
                    continue
                files.append(str(p.relative_to(knowledge_dir)))
                if len(files) >= 200:
                    files.append("...[truncated]")
                    return ToolResult(ok=True, output="\n".join(files))
        seen: set[str] = set()
        ordered = []
        for f in files:
            if f not in seen:
                seen.add(f)
                ordered.append(f)
        return ToolResult(ok=True, output="\n".join(ordered) or "(no knowledge files)")

    def knowledge_search(query: str, max_hits: int = 30) -> ToolResult:
        if not knowledge_dir.exists():
            return ToolResult(ok=False, output=f"Knowledge dir not found: {knowledge_dir}")
        q = query.lower()
        hits: list[str] = []
        for path in sorted(knowledge_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".rst"}:
                continue
            if any(part in _SKIP for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = path.relative_to(knowledge_dir)
            for i, line in enumerate(text.splitlines(), 1):
                if q in line.lower():
                    hits.append(f"{rel}:{i}:{line.strip()[:200]}")
                    if len(hits) >= max_hits:
                        hits.append("...[truncated]")
                        return ToolResult(ok=True, output="\n".join(hits))
        return ToolResult(ok=True, output="\n".join(hits) or "No matches")

    def knowledge_read(path: str, max_chars: int = 30_000) -> ToolResult:
        target = (knowledge_dir / path).resolve()
        if not str(target).startswith(str(knowledge_dir.resolve())):
            return ToolResult(ok=False, output="Path escapes knowledge_dir")
        if not target.exists() or not target.is_file():
            return ToolResult(ok=False, output=f"Not found: {path}")
        text = target.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...[truncated]"
        return ToolResult(ok=True, output=text)

    registry.register(
        ToolSpec(
            name="knowledge_list",
            description="List documents in the local knowledge directory (docs/ by default).",
            parameters={
                "type": "object",
                "properties": {"glob": {"type": "string"}},
            },
            handler=knowledge_list,
        )
    )
    registry.register(
        ToolSpec(
            name="knowledge_search",
            description="Search local knowledge docs for a substring (case-insensitive).",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_hits": {"type": "integer", "default": 30},
                },
                "required": ["query"],
            },
            handler=knowledge_search,
        )
    )
    registry.register(
        ToolSpec(
            name="knowledge_read",
            description="Read a file from the knowledge directory.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_chars": {"type": "integer", "default": 30000},
                },
                "required": ["path"],
            },
            handler=knowledge_read,
        )
    )
