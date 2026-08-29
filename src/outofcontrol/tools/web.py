from __future__ import annotations

import json
from urllib.parse import quote_plus

import httpx

from outofcontrol.tools.base import ToolRegistry, ToolResult, ToolSpec


def register_web_tools(registry: ToolRegistry) -> None:
    def web_search(query: str, max_results: int = 5) -> ToolResult:
        # DuckDuckGo Instant Answer API (no key). Good enough for MVP discovery.
        url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1&skip_disambig=1"
        try:
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                r = client.get(url, headers={"User-Agent": "outofcontrol-agent/0.1"})
                r.raise_for_status()
                data = r.json()
        except Exception as e:  # noqa: BLE001
            return ToolResult(ok=False, output=f"Search failed: {e}")

        results: list[dict] = []
        if data.get("AbstractText"):
            results.append(
                {
                    "title": data.get("Heading") or query,
                    "snippet": data.get("AbstractText"),
                    "url": data.get("AbstractURL"),
                }
            )
        for topic in data.get("RelatedTopics") or []:
            if len(results) >= max_results:
                break
            if isinstance(topic, dict) and "Text" in topic:
                results.append(
                    {
                        "title": topic.get("Text", "")[:80],
                        "snippet": topic.get("Text"),
                        "url": topic.get("FirstURL"),
                    }
                )
            elif isinstance(topic, dict) and "Topics" in topic:
                for sub in topic["Topics"]:
                    if len(results) >= max_results:
                        break
                    results.append(
                        {
                            "title": sub.get("Text", "")[:80],
                            "snippet": sub.get("Text"),
                            "url": sub.get("FirstURL"),
                        }
                    )
        if not results:
            return ToolResult(
                ok=True,
                output=(
                    "No structured results from DuckDuckGo Instant Answer. "
                    "Try web_fetch on a known URL, or refine the query."
                ),
            )
        return ToolResult(ok=True, output=json.dumps(results, ensure_ascii=False, indent=2))

    def web_fetch(url: str, max_chars: int = 15_000) -> ToolResult:
        if not url.startswith(("http://", "https://")):
            return ToolResult(ok=False, output="URL must start with http:// or https://")
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                r = client.get(url, headers={"User-Agent": "outofcontrol-agent/0.1"})
                r.raise_for_status()
                text = r.text
        except Exception as e:  # noqa: BLE001
            return ToolResult(ok=False, output=f"Fetch failed: {e}")
        # crude HTML strip for readability
        import re

        text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
        text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_chars:
            text = text[:max_chars] + " ...[truncated]"
        return ToolResult(ok=True, output=text or "(empty body)")

    registry.register(
        ToolSpec(
            name="web_search",
            description="Search the public web for information (DuckDuckGo Instant Answer).",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
            handler=web_search,
        )
    )
    registry.register(
        ToolSpec(
            name="web_fetch",
            description="Fetch a URL and return readable text content.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "max_chars": {"type": "integer", "default": 15000},
                },
                "required": ["url"],
            },
            handler=web_fetch,
        )
    )
