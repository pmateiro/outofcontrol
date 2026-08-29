from __future__ import annotations

from outofcontrol.config import Settings
from outofcontrol.providers.base import LLMProvider
from outofcontrol.providers.openai_compatible import OpenAICompatibleProvider


def create_provider(settings: Settings) -> LLMProvider:
    if settings.provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY (or OOC_OPENAI_API_KEY) is required when provider=openai"
            )
        return OpenAICompatibleProvider(
            model=settings.model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    if settings.provider == "ollama":
        return OpenAICompatibleProvider(
            model=settings.model,
            api_key="ollama",
            base_url=settings.ollama_base_url,
        )
    raise ValueError(f"Unknown provider: {settings.provider}")
