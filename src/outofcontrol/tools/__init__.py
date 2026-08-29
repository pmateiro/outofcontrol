from __future__ import annotations

from pathlib import Path

from outofcontrol.skills_loader import SkillLoader
from outofcontrol.tools.base import ConfirmCallback, ToolRegistry, ToolResult, ToolSpec
from outofcontrol.tools.calendar import register_calendar_tools
from outofcontrol.tools.confirm import (
    delete_file_executor,
    register_confirm_tools,
    shell_executor,
)
from outofcontrol.tools.files import register_file_tools
from outofcontrol.tools.memory import register_memory_tools
from outofcontrol.tools.pending import PendingConfirmations
from outofcontrol.tools.shell import register_shell_tools
from outofcontrol.tools.web import register_web_tools

# Backwards-compatible export
PendingShell = PendingConfirmations


def build_registry(
    *,
    workspace: Path,
    skills: SkillLoader,
    calendar_path: Path,
    memory_path: Path,
    sensitive_patterns: list[str],
    confirm_sensitive: bool,
    confirm: ConfirmCallback | None = None,
    pending_shell: PendingConfirmations | None = None,
) -> tuple[ToolRegistry, PendingConfirmations]:
    registry = ToolRegistry()
    pending = pending_shell or PendingConfirmations()

    register_file_tools(
        registry,
        workspace=workspace,
        confirm_sensitive=confirm_sensitive,
        confirm=confirm,
        pending=pending,
    )
    register_shell_tools(
        registry,
        workspace=workspace,
        patterns=sensitive_patterns,
        confirm_sensitive=confirm_sensitive,
        confirm=confirm,
        pending=pending,
    )
    register_confirm_tools(
        registry,
        pending=pending,
        executors={
            "shell": shell_executor(workspace),
            "delete_file": delete_file_executor(workspace),
        },
    )
    register_web_tools(registry)
    register_calendar_tools(registry, calendar_path=calendar_path)
    register_memory_tools(registry, memory_path=memory_path)

    def list_skills() -> ToolResult:
        return ToolResult(ok=True, output=skills.inventory_text())

    def load_skill(name: str) -> ToolResult:
        skill = skills.get(name)
        if not skill:
            return ToolResult(
                ok=False,
                output=f"Skill not found: {name}. Available:\n{skills.inventory_text()}",
            )
        return ToolResult(
            ok=True,
            output=f"# Skill: {skill.name}\n\n{skill.description}\n\n{skill.body}",
        )

    registry.register(
        ToolSpec(
            name="list_skills",
            description="List available skills (name + short description).",
            parameters={"type": "object", "properties": {}},
            handler=list_skills,
        )
    )
    registry.register(
        ToolSpec(
            name="load_skill",
            description=(
                "Load the full instructions for a skill by name. "
                "Call this when a skill is relevant to the user task."
            ),
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            handler=load_skill,
        )
    )
    return registry, pending
