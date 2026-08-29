from __future__ import annotations

from outofcontrol.agent.loop import Agent
from outofcontrol.config import Settings
from outofcontrol.providers import create_provider
from outofcontrol.skills_loader import SkillLoader
from outofcontrol.tools import PendingConfirmations, build_registry
from outofcontrol.tools.base import ConfirmCallback


def create_agent(
    settings: Settings | None = None,
    *,
    confirm: ConfirmCallback | None = None,
    pending_shell: PendingConfirmations | None = None,
    on_event=None,
) -> tuple[Agent, PendingConfirmations, Settings]:
    settings = settings or Settings.load()
    workspace = settings.resolve_workspace()
    skills = SkillLoader(settings.resolve_skills_dir())
    registry, pending = build_registry(
        workspace=workspace,
        skills=skills,
        calendar_path=settings.resolve_calendar_path(),
        memory_path=settings.resolve_memory_path(),
        tasks_path=settings.resolve_tasks_path(),
        knowledge_dir=settings.resolve_knowledge_dir(),
        github_repo=settings.github_repo,
        browser_enabled=settings.browser_enabled,
        sensitive_patterns=settings.sensitive_shell_patterns,
        confirm_sensitive=settings.shell_confirm_sensitive,
        confirm=confirm,
        pending_shell=pending_shell,
        default_remind_minutes=settings.default_remind_minutes,
    )
    provider = create_provider(settings)
    agent = Agent(
        provider=provider,
        registry=registry,
        skills=skills,
        workspace=str(workspace),
        max_tool_rounds=settings.max_tool_rounds,
        system_prompt_extra=settings.system_prompt_extra,
        on_event=on_event,
    )
    return agent, pending, settings
