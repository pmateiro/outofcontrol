from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OOC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider: Literal["openai", "ollama"] = "openai"
    model: str = "gpt-4.1-mini"
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: str | None = None
    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    workspace: Path = Path(".")
    skills_dir: Path = Path("skills")
    max_tool_rounds: int = 20
    shell_confirm_sensitive: bool = True
    sensitive_shell_patterns: list[str] = Field(
        default_factory=lambda: [
            r"\brm\b",
            r"\bsudo\b",
            r"\bmkfs\b",
            r"\bdd\b",
            r"\bshutdown\b",
            r"\breboot\b",
            r"\bchmod\s+777\b",
            r">\s*/",
            r"\bcurl\b.*\|\s*(ba)?sh",
            r"\bwget\b.*\|\s*(ba)?sh",
            r"\bgit\s+push\b",
            r"\bgit\s+reset\s+--hard\b",
        ]
    )
    calendar_path: Path = Path("data/calendar.json")
    system_prompt_extra: str = ""

    @classmethod
    def load(cls, config_path: Path | None = None) -> Settings:
        data: dict = {}
        path = config_path or Path("config.yaml")
        if not path.exists():
            example = Path("config.example.yaml")
            if example.exists() and config_path is None:
                path = example
        if path.exists():
            with path.open(encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            if isinstance(loaded, dict):
                data = loaded
        return cls(**data)

    def resolve_workspace(self) -> Path:
        return self.workspace.expanduser().resolve()

    def resolve_skills_dir(self) -> Path:
        p = self.skills_dir
        if not p.is_absolute():
            p = self.resolve_workspace() / p
        return p.resolve()

    def resolve_calendar_path(self) -> Path:
        p = self.calendar_path
        if not p.is_absolute():
            p = self.resolve_workspace() / p
        return p.resolve()
