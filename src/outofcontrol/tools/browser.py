from __future__ import annotations

from pathlib import Path

from outofcontrol.tools.base import ToolRegistry, ToolResult, ToolSpec


def register_browser_tools(
    registry: ToolRegistry,
    *,
    enabled: bool = True,
    workspace: Path | None = None,
) -> None:
    def browser_fetch(url: str, wait_until: str = "domcontentloaded", timeout_ms: int = 30000) -> ToolResult:
        if not enabled:
            return ToolResult(
                ok=False,
                output="Browser tools disabled. Install optional deps: pip install 'outofcontrol[browser]'",
            )
        if not url.startswith(("http://", "https://")):
            return ToolResult(ok=False, output="URL must start with http:// or https://")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ToolResult(
                ok=False,
                output=(
                    "Playwright not installed. Run: pip install 'outofcontrol[browser]' "
                    "&& playwright install chromium"
                ),
            )
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                title = page.title()
                text = page.inner_text("body")
                browser.close()
        except Exception as e:  # noqa: BLE001
            return ToolResult(ok=False, output=f"Browser error: {e}")
        text = " ".join(text.split())
        if len(text) > 20_000:
            text = text[:20_000] + " ...[truncated]"
        return ToolResult(ok=True, output=f"Title: {title}\n\n{text}")

    def browser_screenshot(
        url: str,
        path: str = "data/screenshots/page.png",
        full_page: bool = True,
        timeout_ms: int = 30000,
    ) -> ToolResult:
        if not enabled:
            return ToolResult(ok=False, output="Browser tools disabled.")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ToolResult(
                ok=False,
                output="Playwright not installed. pip install 'outofcontrol[browser]' && playwright install chromium",
            )
        out = Path(path)
        if not out.is_absolute():
            base = workspace or Path.cwd()
            out = (base / out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.screenshot(path=str(out), full_page=full_page)
                title = page.title()
                browser.close()
        except Exception as e:  # noqa: BLE001
            return ToolResult(ok=False, output=f"Screenshot error: {e}")
        return ToolResult(ok=True, output=f"Saved screenshot to {out} (title={title!r})")

    registry.register(
        ToolSpec(
            name="browser_fetch",
            description="Open a URL in headless Chromium and return visible text (requires Playwright).",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "wait_until": {"type": "string", "default": "domcontentloaded"},
                    "timeout_ms": {"type": "integer", "default": 30000},
                },
                "required": ["url"],
            },
            handler=browser_fetch,
        )
    )
    registry.register(
        ToolSpec(
            name="browser_screenshot",
            description="Screenshot a URL with headless Chromium (requires Playwright).",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "path": {"type": "string", "default": "data/screenshots/page.png"},
                    "full_page": {"type": "boolean", "default": True},
                    "timeout_ms": {"type": "integer", "default": 30000},
                },
                "required": ["url"],
            },
            handler=browser_screenshot,
        )
    )
