---
name: verify-ui
description: Use when verifying a web page visually or extracting rendered text via headless browser (Playwright).
---

# Verify UI

1. Prefer `web_fetch` for static HTML; use `browser_fetch` when JS rendering matters.
2. `browser_screenshot` to `data/screenshots/` when the user wants visual proof.
3. If Playwright is missing, tell the user to `pip install 'outofcontrol[browser]' && playwright install chromium`.
4. Report title + key visible text; do not claim pixel-perfect QA.
